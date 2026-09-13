using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Cpc.Plugins
{
    /// <summary>
    /// Fires after a process task is completed. Reads the outcome the agent selected, applies the
    /// outcome's side effects (stage advance, case priority, case resolution) and instantiates the
    /// task the outcome points at. This is what makes the process a graph rather than a checklist.
    /// </summary>
    public class AdvanceProcess : IPlugin
    {
        private const string P = "cpc_";

        public void Execute(IServiceProvider sp)
        {
            var ctx = (IPluginExecutionContext)sp.GetService(typeof(IPluginExecutionContext));
            var factory = (IOrganizationServiceFactory)sp.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(ctx.UserId);
            var trace = (ITracingService)sp.GetService(typeof(ITracingService));

            if (ctx.PrimaryEntityName != "task") return;
            if (ctx.Depth > 3) return;

            var task = svc.Retrieve("task", ctx.PrimaryEntityId, new ColumnSet(
                "subject", "statecode", "regardingobjectid", P + "sourcetask", P + "sourcetemplate",
                P + "selectedoutcome", P + "outcomelabel", P + "branchpath", P + "stagename"));

            // Only interested in completed tasks that came from a process template.
            var state = task.GetAttributeValue<OptionSetValue>("statecode");
            if (state == null || state.Value != 1) return;

            // The countdown stops the moment the task is done, whoever closed it - a human in the
            // form or the agent through cpc_CompleteAgentTask. Doing it here rather than in each
            // caller keeps a single place responsible for it.
            ProcessRuntime.CloseSlaTimer(svc, ctx.PrimaryEntityId, DateTime.UtcNow);

            var sourceTask = task.GetAttributeValue<EntityReference>(P + "sourcetask");
            var sourceTemplate = task.GetAttributeValue<EntityReference>(P + "sourcetemplate");
            var regarding = task.GetAttributeValue<EntityReference>("regardingobjectid");
            if (sourceTask == null || sourceTemplate == null || regarding == null
                || regarding.LogicalName != "incident") return;

            var log = new StringBuilder();
            log.AppendLine("Task '" + task.GetAttributeValue<string>("subject") + "' completed.");

            var outcomes = ProcessRuntime.LoadOutcomes(svc, sourceTask.Id);
            if (outcomes.Count == 0)
            {
                trace.Trace("No outcomes configured; nothing to advance.");
                return;
            }

            // Work out which outcome applies: explicit lookup, then label match, then the default.
            Entity chosen = null;
            var sel = task.GetAttributeValue<EntityReference>(P + "selectedoutcome");
            if (sel != null) chosen = outcomes.FirstOrDefault(o => o.Id == sel.Id);

            if (chosen == null)
            {
                var lbl = task.GetAttributeValue<string>(P + "outcomelabel");
                if (!string.IsNullOrEmpty(lbl))
                    chosen = outcomes.FirstOrDefault(o => string.Equals(
                        o.GetAttributeValue<string>(P + "name"), lbl, StringComparison.OrdinalIgnoreCase));
            }
            if (chosen == null)
                chosen = outcomes.FirstOrDefault(o => o.GetAttributeValue<bool>(P + "isdefault"));
            if (chosen == null) chosen = outcomes[0];

            var outcomeName = chosen.GetAttributeValue<string>(P + "name");
            log.AppendLine("Outcome recorded: " + outcomeName + ".");

            // Keep the denormalised label in step so the timeline reads well without a join.
            if (sel == null || task.GetAttributeValue<string>(P + "outcomelabel") != outcomeName)
            {
                var stamp = new Entity("task", task.Id);
                stamp[P + "selectedoutcome"] = new EntityReference(P + "taskoutcome", chosen.Id);
                stamp[P + "outcomelabel"] = outcomeName;
                svc.Update(stamp);
            }

            var incident = svc.Retrieve("incident", regarding.Id, new ColumnSet(true));
            var template = svc.Retrieve(P + "caseprocesstemplate", sourceTemplate.Id, new ColumnSet(true));

            ApplyOutcomeEffects(svc, incident, template, task, chosen, log);

            // Spawn whatever comes next.
            var next = chosen.GetAttributeValue<EntityReference>(P + "nexttask");
            var spawned = 0;
            if (next != null)
            {
                var def = svc.Retrieve(P + "processtask", next.Id, new ColumnSet(true));
                var openAlready = HasOpenInstance(svc, incident.Id, next.Id);
                if (openAlready)
                {
                    log.AppendLine("Next task '" + def.GetAttributeValue<string>(P + "name")
                                   + "' is already open; not duplicated.");
                }
                else
                {
                    var path = task.GetAttributeValue<string>(P + "branchpath");
                    path = string.IsNullOrEmpty(path)
                        ? outcomeName
                        : path + " > " + outcomeName;
                    ProcessRuntime.Instantiate(svc, incident, def, template.Id, DateTime.UtcNow, path);
                    spawned = 1;
                    log.AppendLine("Started next task: " + def.GetAttributeValue<string>(P + "name") + ".");
                }
            }
            else
            {
                log.AppendLine("This outcome ends its branch - no follow up task configured.");
            }

            AppendJournal(svc, incident.Id, template.Id, log.ToString());
            trace.Trace("AdvanceProcess: outcome={0} spawned={1}", outcomeName, spawned);
        }

        private static void ApplyOutcomeEffects(IOrganizationService svc, Entity incident, Entity template,
                                                Entity task, Entity outcome, StringBuilder log)
        {
            var update = new Entity("incident", incident.Id);
            var dirty = false;

            var pr = outcome.GetAttributeValue<OptionSetValue>(P + "setcasepriority");
            if (pr != null && pr.Value > 0)
            {
                update["prioritycode"] = new OptionSetValue(pr.Value);
                dirty = true;
                log.AppendLine("Case priority set by the outcome.");
            }

            if (dirty) svc.Update(update);

            var processId = ProcessRuntime.ParseGuid(template.GetAttributeValue<string>(P + "bpfid"));
            var bpfEntity = template.GetAttributeValue<string>(P + "bpfentityname");

            var jump = outcome.GetAttributeValue<string>(P + "targetstagename");
            if (!string.IsNullOrEmpty(jump))
            {
                ProcessRuntime.MoveStage(svc, incident.Id, bpfEntity, processId, jump, log);
            }
            else if (outcome.GetAttributeValue<bool>(P + "advancestage"))
            {
                var current = task.GetAttributeValue<string>(P + "stagename");
                var nextStage = ProcessRuntime.NextStageName(svc, processId, current);
                if (!string.IsNullOrEmpty(nextStage))
                    ProcessRuntime.MoveStage(svc, incident.Id, bpfEntity, processId, nextStage, log);
            }

            if (outcome.GetAttributeValue<bool>(P + "closecase"))
            {
                CancelOpenTasks(svc, incident.Id, task.Id, log);
                ResolveCase(svc, incident.Id, outcome.GetAttributeValue<string>(P + "name"), log);
            }
        }

        private static bool HasOpenInstance(IOrganizationService svc, Guid caseId, Guid processTaskId)
        {
            var q = new QueryExpression("task") { ColumnSet = new ColumnSet("activityid"), TopCount = 1 };
            q.Criteria.AddCondition("regardingobjectid", ConditionOperator.Equal, caseId);
            q.Criteria.AddCondition(P + "sourcetask", ConditionOperator.Equal, processTaskId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            return svc.RetrieveMultiple(q).Entities.Count > 0;
        }

        private static void CancelOpenTasks(IOrganizationService svc, Guid caseId, Guid exceptTaskId,
                                            StringBuilder log)
        {
            var q = new QueryExpression("task") { ColumnSet = new ColumnSet("activityid", "subject") };
            q.Criteria.AddCondition("regardingobjectid", ConditionOperator.Equal, caseId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            q.Criteria.AddCondition(P + "sourcetask", ConditionOperator.NotNull);
            var open = svc.RetrieveMultiple(q).Entities;
            var n = 0;
            foreach (var t in open)
            {
                if (t.Id == exceptTaskId) continue;
                var cancel = new Entity("task", t.Id);
                cancel["statecode"] = new OptionSetValue(2);
                cancel["statuscode"] = new OptionSetValue(6);
                svc.Update(cancel);
                n++;
            }
            if (n > 0) log.AppendLine("Cancelled " + n + " task(s) still open on the abandoned branches.");
        }

        private static void ResolveCase(IOrganizationService svc, Guid caseId, string reason, StringBuilder log)
        {
            var incident = svc.Retrieve("incident", caseId, new ColumnSet("statecode"));
            var st = incident.GetAttributeValue<OptionSetValue>("statecode");
            if (st != null && st.Value != 0)
            {
                log.AppendLine("Case is not active; resolution skipped.");
                return;
            }

            var deactivate = new Entity("incident", caseId);
            deactivate["statecode"] = new OptionSetValue(0);
            deactivate["statuscode"] = new OptionSetValue(1);
            svc.Update(deactivate);

            var resolution = new Entity("incidentresolution");
            resolution["subject"] = "Resolved by process outcome: " + reason;
            resolution["incidentid"] = new EntityReference("incident", caseId);

            var close = new Microsoft.Crm.Sdk.Messages.CloseIncidentRequest
            {
                IncidentResolution = resolution,
                Status = new OptionSetValue(5)
            };
            svc.Execute(close);
            log.AppendLine("Case resolved by the outcome.");
        }

        /// <summary>Appends the branch decision to the applied process record so the path is auditable.</summary>
        private static void AppendJournal(IOrganizationService svc, Guid caseId, Guid templateId, string entry)
        {
            var q = new QueryExpression(P + "appliedprocess")
            {
                ColumnSet = new ColumnSet(P + "appliedprocessid", P + "evaluationlog"),
                TopCount = 1,
                Orders = { new OrderExpression("createdon", OrderType.Descending) }
            };
            q.Criteria.AddCondition(P + "case", ConditionOperator.Equal, caseId);
            var found = svc.RetrieveMultiple(q).Entities;
            if (found.Count == 0) return;

            var existing = found[0].GetAttributeValue<string>(P + "evaluationlog") ?? "";
            var stamped = existing + Environment.NewLine
                          + "[" + DateTime.UtcNow.ToString("u") + "] " + entry;

            var upd = new Entity(P + "appliedprocess", found[0].Id);
            upd[P + "evaluationlog"] = ProcessRuntime.Truncate(stamped, 100000);
            svc.Update(upd);
        }
    }
}

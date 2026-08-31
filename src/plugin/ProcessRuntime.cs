using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Cpc.Plugins
{
    /// <summary>
    /// Shared runtime used by both the apply engine and the outcome driven advance engine.
    /// Owns task instantiation, owner resolution and outcome serialisation so the two plug-ins
    /// cannot drift apart.
    /// </summary>
    internal static class ProcessRuntime
    {
        public const string P = "cpc_";

        // ------------------------------------------------------------------ loading

        public static List<Entity> LoadTemplateTasks(IOrganizationService svc, Guid templateId)
        {
            var q = new QueryExpression(P + "processtask")
            {
                ColumnSet = new ColumnSet(true),
                Orders = { new OrderExpression(P + "sequence", OrderType.Ascending) }
            };
            q.Criteria.AddCondition(P + "template", ConditionOperator.Equal, templateId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            return svc.RetrieveMultiple(q).Entities.ToList();
        }

        public static List<Entity> LoadOutcomes(IOrganizationService svc, Guid processTaskId)
        {
            var q = new QueryExpression(P + "taskoutcome")
            {
                ColumnSet = new ColumnSet(true),
                Orders = { new OrderExpression(P + "sequence", OrderType.Ascending) }
            };
            q.Criteria.AddCondition(P + "task", ConditionOperator.Equal, processTaskId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            return svc.RetrieveMultiple(q).Entities.ToList();
        }

        public static List<Entity> LoadTemplateOutcomes(IOrganizationService svc, Guid templateId)
        {
            var q = new QueryExpression(P + "taskoutcome") { ColumnSet = new ColumnSet(true) };
            q.Criteria.AddCondition(P + "template", ConditionOperator.Equal, templateId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            return svc.RetrieveMultiple(q).Entities.ToList();
        }

        /// <summary>
        /// Entry tasks are those explicitly flagged as entry points. When nobody has been flagged we
        /// fall back to any task that no outcome points at, and finally to the lowest sequence task, so
        /// a template authored before branching existed still starts somewhere.
        /// </summary>
        public static List<Entity> EntryTasks(IOrganizationService svc, Guid templateId, List<Entity> tasks)
        {
            var flagged = tasks.Where(t => t.GetAttributeValue<bool>(P + "isstart")).ToList();
            if (flagged.Count > 0) return flagged;

            var outcomes = LoadTemplateOutcomes(svc, templateId);
            var targeted = new HashSet<Guid>(outcomes
                .Select(o => o.GetAttributeValue<EntityReference>(P + "nexttask"))
                .Where(r => r != null)
                .Select(r => r.Id));

            if (outcomes.Count > 0)
            {
                var roots = tasks.Where(t => !targeted.Contains(t.Id)).ToList();
                if (roots.Count > 0) return roots;
            }

            // No graph authored at all - behave like the original linear model and start everything.
            return tasks;
        }

        // ------------------------------------------------------------------ instantiation

        /// <summary>Creates the live task record for a process task definition and returns its id.</summary>
        public static Guid Instantiate(IOrganizationService svc, Entity incident, Entity tt,
                                       Guid templateId, DateTime clock, string branchPath)
        {
            var task = new Entity("task");
            task["subject"] = tt.GetAttributeValue<string>(P + "name");
            task["description"] = tt.GetAttributeValue<string>(P + "description");
            task["regardingobjectid"] = new EntityReference("incident", incident.Id);
            task[P + "sequence"] = tt.GetAttributeValue<int>(P + "sequence");
            task[P + "stagename"] = tt.GetAttributeValue<string>(P + "stagename");
            task[P + "blocksstage"] = tt.GetAttributeValue<bool>(P + "blocksstage");
            task[P + "mandatory"] = tt.GetAttributeValue<bool>(P + "mandatory");
            task[P + "sourcetask"] = new EntityReference(P + "processtask", tt.Id);
            task[P + "sourcetemplate"] = new EntityReference(P + "caseprocesstemplate", templateId);
            if (!string.IsNullOrEmpty(branchPath))
                task[P + "branchpath"] = Truncate(branchPath, 1000);

            var onBreach = tt.GetAttributeValue<OptionSetValue>(P + "onbreach");
            if (onBreach != null) task[P + "onbreach"] = new OptionSetValue(onBreach.Value);

            var due = tt.GetAttributeValue<decimal?>(P + "duehours");
            if (due.HasValue && due.Value > 0)
                task["scheduledend"] = clock.AddHours((double)due.Value);

            var target = tt.GetAttributeValue<decimal?>(P + "slatargethours");
            if (target.HasValue && target.Value > 0)
            {
                var warnPct = tt.GetAttributeValue<int?>(P + "slawarnpercent") ?? 75;
                task[P + "sladue"] = clock.AddHours((double)target.Value);
                task[P + "slawarn"] = clock.AddHours((double)target.Value * warnPct / 100.0);
                task[P + "slastatus"] = new OptionSetValue(1);
            }

            string ownerLabel;
            var owner = ResolveOwner(svc, incident, tt, out ownerLabel);
            if (owner != null) task["ownerid"] = owner;
            task[P + "assignedteamname"] = ownerLabel;

            var outcomes = LoadOutcomes(svc, tt.Id);
            task[P + "availableoutcomes"] = Truncate(SerialiseOutcomes(outcomes), 4000);

            var id = svc.Create(task);

            var queue = tt.GetAttributeValue<EntityReference>(P + "queue");
            if (queue != null)
            {
                var qi = new Entity("queueitem");
                qi["queueid"] = new EntityReference("queue", queue.Id);
                qi["objectid"] = new EntityReference("task", id);
                svc.Create(qi);
            }
            return id;
        }

        /// <summary>Compact JSON the outcome picker renders as buttons without another round trip.</summary>
        public static string SerialiseOutcomes(List<Entity> outcomes)
        {
            var sb = new StringBuilder("[");
            var first = true;
            foreach (var o in outcomes)
            {
                if (!first) sb.Append(",");
                first = false;
                var sentiment = o.GetAttributeValue<OptionSetValue>(P + "sentiment");
                var next = o.GetAttributeValue<EntityReference>(P + "nexttask");
                sb.Append("{")
                  .Append(Json.Q("id")).Append(":").Append(Json.Q(o.Id.ToString())).Append(",")
                  .Append(Json.Q("label")).Append(":").Append(Json.Q(o.GetAttributeValue<string>(P + "name"))).Append(",")
                  .Append(Json.Q("guidance")).Append(":").Append(Json.Q(o.GetAttributeValue<string>(P + "description"))).Append(",")
                  .Append(Json.Q("sentiment")).Append(":").Append(sentiment == null ? 2 : sentiment.Value).Append(",")
                  .Append(Json.Q("requireComment")).Append(":")
                  .Append(o.GetAttributeValue<bool>(P + "requirecomment") ? "true" : "false").Append(",")
                  .Append(Json.Q("isDefault")).Append(":")
                  .Append(o.GetAttributeValue<bool>(P + "isdefault") ? "true" : "false").Append(",")
                  .Append(Json.Q("nextTask")).Append(":")
                  .Append(Json.Q(next == null ? "" : next.Name))
                  .Append("}");
            }
            return sb.Append("]").ToString();
        }

        // ------------------------------------------------------------------ ownership

        public static EntityReference ResolveOwner(IOrganizationService svc, Entity incident,
                                                   Entity tt, out string label)
        {
            label = null;
            var type = tt.GetAttributeValue<OptionSetValue>(P + "assigntype");
            var mode = type == null ? 1 : type.Value;

            switch (mode)
            {
                case 1:
                    {
                        var team = tt.GetAttributeValue<EntityReference>(P + "team");
                        if (team != null) { label = "Team: " + team.Name; return new EntityReference("team", team.Id); }
                        break;
                    }
                case 2:
                    {
                        var user = tt.GetAttributeValue<EntityReference>(P + "user");
                        if (user != null) { label = "User: " + user.Name; return new EntityReference("systemuser", user.Id); }
                        break;
                    }
                case 3:
                    {
                        var role = tt.GetAttributeValue<string>(P + "rolename");
                        label = "Role: " + role;
                        var u = FirstUserInRole(svc, role);
                        if (u != Guid.Empty) return new EntityReference("systemuser", u);
                        break;
                    }
                case 4:
                    {
                        var q = tt.GetAttributeValue<EntityReference>(P + "queue");
                        label = "Queue: " + (q == null ? "unspecified" : q.Name);
                        return incident.GetAttributeValue<EntityReference>("ownerid");
                    }
                case 5:
                    {
                        label = "Manager of case owner";
                        var caseOwner = incident.GetAttributeValue<EntityReference>("ownerid");
                        if (caseOwner != null && caseOwner.LogicalName == "systemuser")
                        {
                            var u = svc.Retrieve("systemuser", caseOwner.Id, new ColumnSet("parentsystemuserid"));
                            var mgr = u.GetAttributeValue<EntityReference>("parentsystemuserid");
                            if (mgr != null) { label = "Manager: " + mgr.Name; return mgr; }
                            return caseOwner;
                        }
                        break;
                    }
                case 6:
                    {
                        label = "Case owner";
                        return incident.GetAttributeValue<EntityReference>("ownerid");
                    }
            }

            var fallback = tt.GetAttributeValue<EntityReference>(P + "fallbackteam");
            if (fallback != null)
            {
                label = (label ?? "Unresolved") + " -> fallback team: " + fallback.Name;
                return new EntityReference("team", fallback.Id);
            }
            return incident.GetAttributeValue<EntityReference>("ownerid");
        }

        public static Guid FirstUserInRole(IOrganizationService svc, string roleName)
        {
            if (string.IsNullOrEmpty(roleName)) return Guid.Empty;
            var q = new QueryExpression("systemuser") { ColumnSet = new ColumnSet("systemuserid"), TopCount = 1 };
            q.Criteria.AddCondition("isdisabled", ConditionOperator.Equal, false);
            var sur = q.AddLink("systemuserroles", "systemuserid", "systemuserid");
            var role = sur.AddLink("role", "roleid", "roleid");
            role.LinkCriteria.AddCondition("name", ConditionOperator.Equal, roleName);
            var r = svc.RetrieveMultiple(q);
            return r.Entities.Count > 0 ? r.Entities[0].Id : Guid.Empty;
        }

        // ------------------------------------------------------------------ business process flow

        public static void MoveStage(IOrganizationService svc, Guid caseId, string bpfEntityName,
                                     Guid processId, string stageName, StringBuilder log)
        {
            if (string.IsNullOrEmpty(bpfEntityName) || processId == Guid.Empty || string.IsNullOrEmpty(stageName))
                return;

            var stageQ = new QueryExpression("processstage")
            {
                ColumnSet = new ColumnSet("processstageid", "stagename"),
                TopCount = 1
            };
            stageQ.Criteria.AddCondition("processid", ConditionOperator.Equal, processId);
            stageQ.Criteria.AddCondition("stagename", ConditionOperator.Equal, stageName);
            var stages = svc.RetrieveMultiple(stageQ);
            if (stages.Entities.Count == 0)
            {
                log.AppendLine("  Stage '" + stageName + "' not found on the process.");
                return;
            }
            var stageId = stages.Entities[0].Id;

            // The case itself carries the active stage, and the process instance mirrors it. Update
            // both so the header widget and any stage based logic agree.
            var caseUpd = new Entity("incident", caseId);
            caseUpd["stageid"] = stageId;
            svc.Update(caseUpd);

            SyncInstance(svc, bpfEntityName, caseId, processId, stageId, log);
            log.AppendLine("  Business process stage moved to '" + stageName + "'.");
        }

        /// <summary>
        /// The lookup back to the case differs between business process flow instance entities:
        /// the out of the box Phone to Case entity calls it "incidentid" while every custom flow
        /// generated by Dataverse calls it "bpf_incidentid". Probe both, and if no instance row
        /// exists yet create one, so the process header always renders with the right active stage.
        /// </summary>
        public static void SyncInstance(IOrganizationService svc, string bpfEntityName, Guid caseId,
                                        Guid processId, Guid stageId, StringBuilder log)
        {
            if (string.IsNullOrEmpty(bpfEntityName) || stageId == Guid.Empty) return;

            string usedLookup = null;
            Guid instanceId = Guid.Empty;

            foreach (var lookup in new[] { "bpf_incidentid", "incidentid" })
            {
                try
                {
                    var q = new QueryExpression(bpfEntityName)
                    {
                        ColumnSet = new ColumnSet("businessprocessflowinstanceid"),
                        TopCount = 1
                    };
                    q.Criteria.AddCondition(lookup, ConditionOperator.Equal, caseId);
                    var found = svc.RetrieveMultiple(q);
                    usedLookup = lookup;
                    if (found.Entities.Count > 0) { instanceId = found.Entities[0].Id; }
                    break;
                }
                catch (Exception) { /* lookup does not exist on this entity, try the other name */ }
            }

            if (usedLookup == null)
            {
                log.AppendLine("  Could not resolve the case lookup on '" + bpfEntityName + "'.");
                return;
            }

            try
            {
                if (instanceId == Guid.Empty)
                {
                    var row = new Entity(bpfEntityName);
                    row[usedLookup] = new EntityReference("incident", caseId);
                    row["processid"] = new EntityReference("workflow", processId);
                    row["activestageid"] = new EntityReference("processstage", stageId);
                    instanceId = svc.Create(row);
                    log.AppendLine("  Created the business process flow instance.");
                }
                else
                {
                    var upd = new Entity(bpfEntityName, instanceId);
                    upd["activestageid"] = new EntityReference("processstage", stageId);
                    svc.Update(upd);
                }
            }
            catch (Exception ex)
            {
                log.AppendLine("  Business process flow instance sync failed: " + ex.Message);
            }
        }

        /// <summary>
        /// Returns the stages of a business process flow in the order a user actually walks them.
        /// Dataverse does not expose an order column on processstage: stagecategory is a category,
        /// not a sequence. The authoritative order is the order the stage ids appear inside the
        /// workflow's clientdata definition, so that is what is used here, with a name sort as a
        /// last resort if clientdata cannot be read.
        /// </summary>
        public static List<Entity> OrderedStages(IOrganizationService svc, Guid processId)
        {
            var q = new QueryExpression("processstage")
            {
                ColumnSet = new ColumnSet("processstageid", "stagename", "stagecategory")
            };
            q.Criteria.AddCondition("processid", ConditionOperator.Equal, processId);
            var all = svc.RetrieveMultiple(q).Entities.ToList();
            if (all.Count < 2) return all;

            string clientData = null;
            try
            {
                var wf = svc.Retrieve("workflow", processId, new ColumnSet("clientdata"));
                clientData = wf.GetAttributeValue<string>("clientdata");
            }
            catch (Exception) { }

            if (string.IsNullOrEmpty(clientData))
                return all.OrderBy(e => e.GetAttributeValue<string>("stagename"),
                                   StringComparer.OrdinalIgnoreCase).ToList();

            var lower = clientData.ToLowerInvariant();
            return all
                .Select(e => new
                {
                    Stage = e,
                    Pos = IndexOfStage(lower, e.Id)
                })
                .OrderBy(x => x.Pos < 0 ? int.MaxValue : x.Pos)
                .ThenBy(x => x.Stage.GetAttributeValue<string>("stagename"), StringComparer.OrdinalIgnoreCase)
                .Select(x => x.Stage)
                .ToList();
        }

        private static int IndexOfStage(string lowerClientData, Guid id)
        {
            var plain = id.ToString("D");
            var i = lowerClientData.IndexOf(plain, StringComparison.Ordinal);
            if (i >= 0) return i;
            return lowerClientData.IndexOf(id.ToString("N"), StringComparison.Ordinal);
        }

        public static string NextStageName(IOrganizationService svc, Guid processId, string currentStage)
        {
            var all = OrderedStages(svc, processId);
            for (var i = 0; i < all.Count; i++)
            {
                if (string.Equals(all[i].GetAttributeValue<string>("stagename"), currentStage,
                        StringComparison.OrdinalIgnoreCase) && i + 1 < all.Count)
                    return all[i + 1].GetAttributeValue<string>("stagename");
            }
            return null;
        }

        // ------------------------------------------------------------------ misc

        public static string Truncate(string s, int max)
        {
            if (string.IsNullOrEmpty(s)) return s;
            return s.Length <= max ? s : s.Substring(0, max - 3) + "...";
        }

        public static Guid ParseGuid(string s)
        {
            Guid g;
            return Guid.TryParse(s, out g) ? g : Guid.Empty;
        }

        public static string Hours(decimal? v)
        {
            return v.HasValue && v.Value > 0
                ? v.Value.ToString("0.##", CultureInfo.InvariantCulture) + "h"
                : "";
        }
    }
}

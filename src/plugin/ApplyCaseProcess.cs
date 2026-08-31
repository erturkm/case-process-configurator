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
    /// Fires on Create of incident. Finds the highest ranked published Case Process Template whose
    /// match rules are satisfied by the case, then applies it: SLA targets, business process flow and
    /// stage, stage linked tasks with resolved owners and task SLAs, and the required document checklist.
    /// </summary>
    public class ApplyCaseProcess : IPlugin
    {
        private const string P = "cpc_";

        public void Execute(IServiceProvider sp)
        {
            var ctx = (IPluginExecutionContext)sp.GetService(typeof(IPluginExecutionContext));
            var factory = (IOrganizationServiceFactory)sp.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(ctx.UserId);
            var trace = (ITracingService)sp.GetService(typeof(ITracingService));

            if (ctx.PrimaryEntityName != "incident") return;
            if (!ctx.InputParameters.Contains("Target") || !(ctx.InputParameters["Target"] is Entity)) return;
            if (ctx.Depth > 2) return;

            var started = DateTime.UtcNow;
            var caseId = ctx.PrimaryEntityId;
            var log = new StringBuilder();

            {
                var incident = svc.Retrieve("incident", caseId, new ColumnSet(true));
                if (incident.Contains(P + "appliedtemplate"))
                {
                    trace.Trace("Template already applied, skipping.");
                    return;
                }

                var templates = LoadTemplates(svc);
                log.AppendLine("Evaluating " + templates.Count + " published template(s) in rank order.");

                Entity winner = null;
                foreach (var t in templates)
                {
                    var rules = LoadRules(svc, t.Id);
                    string why;
                    var ok = Evaluate(incident, rules, out why);
                    log.AppendLine(string.Format(CultureInfo.InvariantCulture,
                        "  rank {0,-4} {1,-40} => {2}  {3}",
                        t.GetAttributeValue<int>(P + "rank"),
                        t.GetAttributeValue<string>(P + "name"),
                        ok ? "MATCH" : "no match", why));
                    if (ok && winner == null) winner = t;
                }

                if (winner == null)
                {
                    log.AppendLine("No template matched. Case left untouched.");
                    StampApplied(svc, caseId, null, 2, 0, 0, null, null, null, log, started);
                    return;
                }

                log.AppendLine("Winner: " + winner.GetAttributeValue<string>(P + "name"));

                var slaName = ApplySla(svc, incident, winner, log);
                string bpfName, stageName;
                ApplyBpf(svc, incident, winner, log, out bpfName, out stageName);
                var taskCount = GenerateTasks(svc, incident, winner, log);
                var docCount = GenerateDocuments(svc, incident, winner, log);

                var update = new Entity("incident", caseId);
                update[P + "appliedtemplate"] = new EntityReference(P + "caseprocesstemplate", winner.Id);
                update[P + "processappliedon"] = DateTime.UtcNow;
                update[P + "processsummary"] = string.Format(CultureInfo.InvariantCulture,
                    "{0} - {1} task(s), {2} document(s), SLA {3}",
                    winner.GetAttributeValue<string>(P + "name"), taskCount, docCount, slaName ?? "none");
                update[P + "taskstotal"] = taskCount;
                update[P + "tasksopen"] = taskCount;
                update[P + "docstotal"] = docCount;
                update[P + "docsreceived"] = 0;

                var setPriority = winner.GetAttributeValue<OptionSetValue>(P + "setcasepriority");
                if (setPriority != null && setPriority.Value > 0)
                    update["prioritycode"] = new OptionSetValue(setPriority.Value);

                svc.Update(update);

                var bump = new Entity(P + "caseprocesstemplate", winner.Id);
                bump[P + "appliedcount"] = winner.GetAttributeValue<int>(P + "appliedcount") + 1;
                svc.Update(bump);

                StampApplied(svc, caseId, winner, 1, taskCount, docCount, slaName, bpfName, stageName, log, started);
                trace.Trace(log.ToString());
            }
        }

        // ------------------------------------------------------------------ configuration load

        private static List<Entity> LoadTemplates(IOrganizationService svc)
        {
            var q = new QueryExpression(P + "caseprocesstemplate")
            {
                ColumnSet = new ColumnSet(true),
                Orders = { new OrderExpression(P + "rank", OrderType.Ascending) }
            };
            q.Criteria.AddCondition(P + "publishstatus", ConditionOperator.Equal, 2);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);

            var now = DateTime.UtcNow;
            var eff = new FilterExpression(LogicalOperator.Or);
            eff.AddCondition(P + "effectivefrom", ConditionOperator.Null);
            eff.AddCondition(P + "effectivefrom", ConditionOperator.OnOrBefore, now);
            q.Criteria.AddFilter(eff);

            var exp = new FilterExpression(LogicalOperator.Or);
            exp.AddCondition(P + "effectiveto", ConditionOperator.Null);
            exp.AddCondition(P + "effectiveto", ConditionOperator.OnOrAfter, now);
            q.Criteria.AddFilter(exp);

            return svc.RetrieveMultiple(q).Entities.ToList();
        }

        private static List<Entity> LoadRules(IOrganizationService svc, Guid templateId)
        {
            var q = new QueryExpression(P + "matchrule")
            {
                ColumnSet = new ColumnSet(true),
                Orders = { new OrderExpression(P + "sequence", OrderType.Ascending) }
            };
            q.Criteria.AddCondition(P + "template", ConditionOperator.Equal, templateId);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            return svc.RetrieveMultiple(q).Entities.ToList();
        }

        private static List<Entity> LoadTasks(IOrganizationService svc, Guid templateId)
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

        // ------------------------------------------------------------------ rule evaluation

        /// <summary>Conditions in the same group are ORed. Groups are ANDed.</summary>
        private static bool Evaluate(Entity incident, List<Entity> rules, out string why)
        {
            why = string.Empty;
            if (rules.Count == 0) { why = "(no rules)"; return false; }

            var groups = rules.GroupBy(r => r.GetAttributeValue<int>(P + "groupnumber"));
            foreach (var g in groups)
            {
                var any = false;
                foreach (var r in g)
                {
                    if (Matches(incident, r)) { any = true; break; }
                }
                if (!any)
                {
                    why = "failed on " + g.First().GetAttributeValue<string>(P + "attributelabel");
                    return false;
                }
            }
            return true;
        }

        private static bool Matches(Entity incident, Entity rule)
        {
            var attr = rule.GetAttributeValue<string>(P + "attributename");
            var op = rule.GetAttributeValue<OptionSetValue>(P + "operator");
            var raw = rule.GetAttributeValue<string>(P + "value") ?? string.Empty;
            if (string.IsNullOrEmpty(attr) || op == null) return false;

            var actual = ValueOf(incident, attr);
            var values = raw.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries)
                            .Select(v => v.Trim()).ToList();

            switch (op.Value)
            {
                case 1: return Eq(actual, raw);
                case 2: return !Eq(actual, raw);
                case 3: return values.Any(v => Eq(actual, v));
                case 4: return !values.Any(v => Eq(actual, v));
                case 5: return actual != null &&
                               actual.IndexOf(raw, StringComparison.OrdinalIgnoreCase) >= 0;
                case 6: return actual != null &&
                               actual.StartsWith(raw, StringComparison.OrdinalIgnoreCase);
                case 7: return Num(actual) > Num(raw);
                case 8: return Num(actual) < Num(raw);
                case 9: return string.IsNullOrEmpty(actual);
                case 10: return !string.IsNullOrEmpty(actual);
                default: return false;
            }
        }

        private static bool Eq(string a, string b)
        {
            return string.Equals(a ?? string.Empty, (b ?? string.Empty).Trim(),
                                 StringComparison.OrdinalIgnoreCase);
        }

        private static double Num(string s)
        {
            double d;
            return double.TryParse(s, NumberStyles.Any, CultureInfo.InvariantCulture, out d) ? d : double.NaN;
        }

        /// <summary>Normalises any case attribute to a comparable string.</summary>
        private static string ValueOf(Entity e, string attr)
        {
            if (!e.Contains(attr)) return null;
            var v = e[attr];
            if (v == null) return null;
            var osv = v as OptionSetValue; if (osv != null) return osv.Value.ToString(CultureInfo.InvariantCulture);
            var er = v as EntityReference; if (er != null) return er.Id.ToString();
            var money = v as Money; if (money != null) return money.Value.ToString(CultureInfo.InvariantCulture);
            if (v is bool) return ((bool)v) ? "1" : "0";
            if (v is DateTime) return ((DateTime)v).ToString("o", CultureInfo.InvariantCulture);
            return Convert.ToString(v, CultureInfo.InvariantCulture);
        }

        // ------------------------------------------------------------------ apply

        private static string ApplySla(IOrganizationService svc, Entity incident, Entity t, StringBuilder log)
        {
            var created = incident.Contains("createdon")
                ? incident.GetAttributeValue<DateTime>("createdon") : DateTime.UtcNow;

            var fr = t.GetAttributeValue<decimal?>(P + "firstresponsehours");
            var res = t.GetAttributeValue<decimal?>(P + "resolutionhours");

            var u = new Entity("incident", incident.Id);
            if (fr.HasValue && fr.Value > 0)
            {
                var due = created.AddHours((double)fr.Value);
                u[P + "firstresponsedue"] = due;
                u[P + "firstresponsewarn"] = created.AddHours((double)fr.Value * 0.75);
                u[P + "firstresponsestatus"] = new OptionSetValue(1);
            }
            if (res.HasValue && res.Value > 0)
            {
                u[P + "resolutiondue"] = created.AddHours((double)res.Value);
                u[P + "resolutionwarn"] = created.AddHours((double)res.Value * 0.75);
                u[P + "resolutionstatus"] = new OptionSetValue(1);
            }

            string slaName = null;
            var slaRef = t.GetAttributeValue<EntityReference>(P + "sla");
            if (slaRef != null)
            {
                var sla = svc.Retrieve("sla", slaRef.Id, new ColumnSet("statecode", "name"));
                slaName = sla.GetAttributeValue<string>("name");
                var slaState = sla.GetAttributeValue<OptionSetValue>("statecode");
                if (slaState != null && slaState.Value == 1)
                {
                    u["slaid"] = new EntityReference("sla", slaRef.Id);
                    log.AppendLine("  SLA record attached: " + slaName);
                }
                else
                {
                    log.AppendLine("  SLA '" + slaName + "' is not active, targets computed directly.");
                }
            }

            if (u.Attributes.Count > 0) svc.Update(u);
            log.AppendLine("  SLA targets set: first response " + fr + "h, resolution " + res + "h.");
            return slaName;
        }

        private static void ApplyBpf(IOrganizationService svc, Entity incident, Entity t,
                                     StringBuilder log, out string bpfName, out string stageName)
        {
            bpfName = t.GetAttributeValue<string>(P + "bpfname");
            stageName = t.GetAttributeValue<string>(P + "startstagename");
            var bpfId = t.GetAttributeValue<string>(P + "bpfid");
            var stageId = t.GetAttributeValue<string>(P + "startstageid");
            if (string.IsNullOrEmpty(bpfId)) { log.AppendLine("  No business process flow configured."); return; }

            Guid processGuid, stageGuid;
            if (!Guid.TryParse(bpfId, out processGuid))
            {
                log.AppendLine("  Business process flow id is not a valid guid, skipped.");
                return;
            }

            var u = new Entity("incident", incident.Id);
            u["processid"] = processGuid;
            var haveStage = Guid.TryParse(stageId, out stageGuid);
            if (haveStage) u["stageid"] = stageGuid;
            svc.Update(u);
            log.AppendLine("  Business process flow set to '" + bpfName + "' at stage '" + stageName + "'.");

            // Stamping processid/stageid on the case is not enough for the header to render: the
            // process instance row carries the active stage the UI actually reads.
            if (haveStage)
                ProcessRuntime.SyncInstance(svc, t.GetAttributeValue<string>(P + "bpfentityname"),
                                            incident.Id, processGuid, stageGuid, log);
        }

        /// <summary>
        /// Creates only the entry tasks of the graph. Everything downstream is created later by
        /// AdvanceProcess when an agent records an outcome on the task that precedes it.
        /// </summary>
        private static int GenerateTasks(IOrganizationService svc, Entity incident, Entity t, StringBuilder log)
        {
            var clock = incident.Contains("createdon")
                ? incident.GetAttributeValue<DateTime>("createdon") : DateTime.UtcNow;
            var all = ProcessRuntime.LoadTemplateTasks(svc, t.Id);
            var entry = ProcessRuntime.EntryTasks(svc, t.Id, all);

            foreach (var tt in entry)
                ProcessRuntime.Instantiate(svc, incident, tt, t.Id, clock, "Start");

            log.AppendLine("  Started " + entry.Count + " of " + all.Count
                           + " task(s); the rest unlock as outcomes are recorded.");
            return entry.Count;
        }

        private static int GenerateDocuments(IOrganizationService svc, Entity incident, Entity t, StringBuilder log)
        {
            var pkg = t.GetAttributeValue<EntityReference>(P + "documentpackage");
            if (pkg == null) { log.AppendLine("  No document package configured."); return 0; }

            var created = incident.Contains("createdon")
                ? incident.GetAttributeValue<DateTime>("createdon") : DateTime.UtcNow;

            var q = new QueryExpression(P + "documentitem")
            {
                ColumnSet = new ColumnSet(true),
                Orders = { new OrderExpression(P + "sequence", OrderType.Ascending) }
            };
            q.Criteria.AddCondition(P + "package", ConditionOperator.Equal, pkg.Id);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);

            var count = 0;
            foreach (var item in svc.RetrieveMultiple(q).Entities)
            {
                var d = new Entity(P + "caserequireddocument");
                d[P + "name"] = item.GetAttributeValue<string>(P + "name");
                d[P + "case"] = new EntityReference("incident", incident.Id);
                d[P + "packageitem"] = new EntityReference(P + "documentitem", item.Id);
                d[P + "sequence"] = item.GetAttributeValue<int>(P + "sequence");
                d[P + "mandatory"] = item.GetAttributeValue<bool>(P + "mandatory");
                d[P + "received"] = false;

                var resp = item.GetAttributeValue<OptionSetValue>(P + "responsible");
                if (resp != null) d[P + "responsible"] = new OptionSetValue(resp.Value);

                var due = item.GetAttributeValue<decimal?>(P + "duehours");
                if (due.HasValue && due.Value > 0) d[P + "duedate"] = created.AddHours((double)due.Value);

                var team = item.GetAttributeValue<EntityReference>(P + "ownerteam");
                if (team != null) d[P + "ownerteam"] = new EntityReference("team", team.Id);

                var url = item.GetAttributeValue<string>(P + "templateurl");
                if (!string.IsNullOrEmpty(url)) d[P + "templateurl"] = url;

                svc.Create(d);
                count++;
            }

            log.AppendLine("  Created " + count + " required document row(s) from package '" + pkg.Name + "'.");
            return count;
        }

        private static void StampApplied(IOrganizationService svc, Guid caseId, Entity template, int result,
                                         int tasks, int docs, string sla, string bpf, string stage,
                                         StringBuilder log, DateTime started)
        {
            var a = new Entity(P + "appliedprocess");
            a[P + "name"] = template == null
                ? "No template matched"
                : template.GetAttributeValue<string>(P + "name");
            a[P + "case"] = new EntityReference("incident", caseId);
            if (template != null)
                a[P + "template"] = new EntityReference(P + "caseprocesstemplate", template.Id);
            a[P + "appliedon"] = DateTime.UtcNow;
            a[P + "result"] = new OptionSetValue(result);
            a[P + "tasksgenerated"] = tasks;
            a[P + "docsrequired"] = docs;
            if (sla != null) a[P + "slaapplied"] = sla;
            if (bpf != null) a[P + "bpfapplied"] = bpf;
            if (stage != null) a[P + "stageset"] = stage;
            a[P + "durationms"] = (int)(DateTime.UtcNow - started).TotalMilliseconds;
            var text = log.ToString();
            a[P + "evaluationlog"] = text.Length > 90000 ? text.Substring(0, 90000) : text;
            svc.Create(a);
        }
    }
}

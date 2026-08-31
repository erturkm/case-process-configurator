using System;
using System.Linq;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Cpc.Plugins
{
    /// <summary>
    /// Keeps the case level progress counters in step when a process task is completed
    /// or a required document is marked as received.
    /// </summary>
    public class UpdateCaseRollups : IPlugin
    {
        private const string P = "cpc_";

        public void Execute(IServiceProvider sp)
        {
            var ctx = (IPluginExecutionContext)sp.GetService(typeof(IPluginExecutionContext));
            var factory = (IOrganizationServiceFactory)sp.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(ctx.UserId);
            var trace = (ITracingService)sp.GetService(typeof(ITracingService));
            if (ctx.Depth > 3) return;

            {
                Guid caseId = Guid.Empty;

                if (ctx.PrimaryEntityName == "task")
                {
                    var task = svc.Retrieve("task", ctx.PrimaryEntityId,
                        new ColumnSet("regardingobjectid", "statecode", P + "sladue", P + "slastatus"));
                    var regarding = task.GetAttributeValue<EntityReference>("regardingobjectid");
                    if (regarding == null || regarding.LogicalName != "incident") return;
                    caseId = regarding.Id;

                    var state = task.GetAttributeValue<OptionSetValue>("statecode");
                    if (state != null && state.Value == 1)
                    {
                        var due = task.GetAttributeValue<DateTime?>(P + "sladue");
                        var status = due.HasValue && DateTime.UtcNow > due.Value ? 4 : 3;
                        svc.Update(new Entity("task", task.Id) { [P + "slastatus"] = new OptionSetValue(status) });
                    }
                }
                else if (ctx.PrimaryEntityName == P + "caserequireddocument")
                {
                    var doc = svc.Retrieve(P + "caserequireddocument", ctx.PrimaryEntityId,
                        new ColumnSet(P + "case", P + "received", P + "receivedon"));
                    var c = doc.GetAttributeValue<EntityReference>(P + "case");
                    if (c == null) return;
                    caseId = c.Id;

                    if (doc.GetAttributeValue<bool>(P + "received") &&
                        doc.GetAttributeValue<DateTime?>(P + "receivedon") == null)
                    {
                        svc.Update(new Entity(P + "caserequireddocument", doc.Id)
                        { [P + "receivedon"] = DateTime.UtcNow });
                    }
                }

                if (caseId == Guid.Empty) return;
                Rollup(svc, caseId);
                trace.Trace("Rollup complete for case " + caseId);
            }
        }

        private static void Rollup(IOrganizationService svc, Guid caseId)
        {
            var tq = new QueryExpression("task") { ColumnSet = new ColumnSet("statecode") };
            tq.Criteria.AddCondition("regardingobjectid", ConditionOperator.Equal, caseId);
            tq.Criteria.AddCondition(P + "sourcetask", ConditionOperator.NotNull);
            var tasks = svc.RetrieveMultiple(tq).Entities;

            var dq = new QueryExpression(P + "caserequireddocument") { ColumnSet = new ColumnSet(P + "received") };
            dq.Criteria.AddCondition(P + "case", ConditionOperator.Equal, caseId);
            dq.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
            var docs = svc.RetrieveMultiple(dq).Entities;

            var open = tasks.Count(t =>
            {
                var s = t.GetAttributeValue<OptionSetValue>("statecode");
                return s == null || s.Value == 0;
            });
            var received = docs.Count(d => d.GetAttributeValue<bool>(P + "received"));

            svc.Update(new Entity("incident", caseId)
            {
                [P + "taskstotal"] = tasks.Count,
                [P + "tasksopen"] = open,
                [P + "docstotal"] = docs.Count,
                [P + "docsreceived"] = received,
            });
        }
    }
}

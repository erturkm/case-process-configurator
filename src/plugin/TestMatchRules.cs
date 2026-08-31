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
    /// Custom API cpc_TestMatchRules. Takes the targeting filter the maker is drawing and answers the
    /// only question they actually care about: which of my real cases would this have caught? Returns
    /// a plain English summary, the equivalent FetchXML, a match count and a handful of sample cases.
    /// </summary>
    public class TestMatchRules : IPlugin
    {
        private const string P = "cpc_";
        private const int SampleSize = 8;

        public void Execute(IServiceProvider sp)
        {
            var ctx = (IPluginExecutionContext)sp.GetService(typeof(IPluginExecutionContext));
            var factory = (IOrganizationServiceFactory)sp.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(ctx.UserId);

            var raw = ctx.InputParameters.Contains("Rules") ? (string)ctx.InputParameters["Rules"] : null;
            var rules = ParseRules(raw);

            var query = new QueryExpression("incident")
            {
                ColumnSet = new ColumnSet("title", "ticketnumber", "createdon", "prioritycode"),
                TopCount = 200,
                Orders = { new OrderExpression("createdon", OrderType.Descending) }
            };
            query.Criteria.FilterOperator = LogicalOperator.And;

            var unsupported = new List<string>();
            foreach (var group in rules.GroupBy(r => r.Group).OrderBy(g => g.Key))
            {
                var f = new FilterExpression(LogicalOperator.Or);
                foreach (var r in group)
                {
                    var c = Condition(r);
                    if (c == null) { unsupported.Add(r.Label); continue; }
                    f.AddCondition(c);
                }
                if (f.Conditions.Count > 0) query.Criteria.AddFilter(f);
            }

            var sb = new StringBuilder();
            sb.Append("{").Append(Json.Q("summary")).Append(":").Append(Json.Q(Summary(rules)));
            sb.Append(",").Append(Json.Q("fetchXml")).Append(":").Append(Json.Q(Fetch(rules)));
            sb.Append(",").Append(Json.Q("unsupported")).Append(":[");
            for (var i = 0; i < unsupported.Count; i++)
            {
                if (i > 0) sb.Append(",");
                sb.Append(Json.Q(unsupported[i]));
            }
            sb.Append("]");

            if (rules.Count == 0)
            {
                sb.Append(",").Append(Json.Q("matchCount")).Append(":0")
                  .Append(",").Append(Json.Q("capped")).Append(":false")
                  .Append(",").Append(Json.Q("samples")).Append(":[]}");
                ctx.OutputParameters["Result"] = sb.ToString();
                return;
            }

            var found = svc.RetrieveMultiple(query).Entities;
            sb.Append(",").Append(Json.Q("matchCount")).Append(":")
              .Append(found.Count.ToString(CultureInfo.InvariantCulture));
            sb.Append(",").Append(Json.Q("capped")).Append(":")
              .Append(found.Count >= query.TopCount.Value ? "true" : "false");
            sb.Append(",").Append(Json.Q("samples")).Append(":[");
            for (var i = 0; i < Math.Min(SampleSize, found.Count); i++)
            {
                if (i > 0) sb.Append(",");
                var e = found[i];
                var created = e.GetAttributeValue<DateTime?>("createdon");
                sb.Append("{").Append(Json.Q("id")).Append(":").Append(Json.Q(e.Id.ToString()))
                  .Append(",").Append(Json.Q("title")).Append(":")
                  .Append(Json.Q(e.GetAttributeValue<string>("title") ?? "(untitled)"))
                  .Append(",").Append(Json.Q("number")).Append(":")
                  .Append(Json.Q(e.GetAttributeValue<string>("ticketnumber") ?? ""))
                  .Append(",").Append(Json.Q("createdOn")).Append(":")
                  .Append(Json.Q(created.HasValue
                      ? created.Value.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) : ""))
                  .Append("}");
            }
            sb.Append("]}");

            ctx.OutputParameters["Result"] = sb.ToString();
        }

        // ------------------------------------------------------------------ model

        private class Rule
        {
            public string Attribute;
            public string Label;
            public int Operator;
            public string Value;
            public string ValueLabel;
            public int Group;
        }

        private static List<Rule> ParseRules(string raw)
        {
            var list = new List<Rule>();
            if (string.IsNullOrWhiteSpace(raw)) return list;
            var arr = Json.Arr(Json.Parse(raw));
            foreach (var item in arr)
            {
                var d = Json.Obj(item);
                if (d == null) continue;
                var attr = Json.Str(d, "attribute", "");
                if (string.IsNullOrWhiteSpace(attr)) continue;
                list.Add(new Rule
                {
                    Attribute = attr,
                    Label = Json.Str(d, "attributeLabel", attr),
                    Operator = Json.Int(d, "operator") ?? 1,
                    Value = Json.Str(d, "value", ""),
                    ValueLabel = Json.Str(d, "valueLabel", ""),
                    Group = Json.Int(d, "group") ?? 1
                });
            }
            return list;
        }

        // ------------------------------------------------------------------ translation

        private static ConditionExpression Condition(Rule r)
        {
            var values = Split(r.Value);
            switch (r.Operator)
            {
                case 1:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.Equal, values[0]);
                case 2:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.NotEqual, values[0]);
                case 3:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.In, values.Cast<object>().ToArray());
                case 4:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.NotIn, values.Cast<object>().ToArray());
                case 5:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.Like, "%" + r.Value + "%");
                case 6:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.Like, r.Value + "%");
                case 7:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.GreaterThan, values[0]);
                case 8:
                    return values.Count == 0 ? null
                        : new ConditionExpression(r.Attribute, ConditionOperator.LessThan, values[0]);
                case 9:
                    return new ConditionExpression(r.Attribute, ConditionOperator.Null);
                case 10:
                    return new ConditionExpression(r.Attribute, ConditionOperator.NotNull);
                default:
                    return null;
            }
        }

        private static List<string> Split(string v)
        {
            if (string.IsNullOrWhiteSpace(v)) return new List<string>();
            return v.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries)
                    .Select(x => x.Trim()).Where(x => x.Length > 0).ToList();
        }

        /// <summary>Builds the same filter as FetchXML so a maker can see and reuse the query.</summary>
        private static string Fetch(List<Rule> rules)
        {
            var sb = new StringBuilder();
            sb.Append("<fetch top=\"50\"><entity name=\"incident\">");
            sb.Append("<attribute name=\"title\" /><attribute name=\"ticketnumber\" />");
            sb.Append("<filter type=\"and\">");
            foreach (var g in rules.GroupBy(r => r.Group).OrderBy(g => g.Key))
            {
                sb.Append("<filter type=\"or\">");
                foreach (var r in g)
                {
                    var op = FetchOp(r.Operator);
                    sb.Append("<condition attribute=\"").Append(Xml(r.Attribute))
                      .Append("\" operator=\"").Append(op).Append("\"");
                    var values = Split(r.Value);
                    if (r.Operator == 9 || r.Operator == 10) sb.Append(" />");
                    else if (r.Operator == 3 || r.Operator == 4)
                    {
                        sb.Append(">");
                        foreach (var v in values) sb.Append("<value>").Append(Xml(v)).Append("</value>");
                        sb.Append("</condition>");
                    }
                    else
                    {
                        var v = r.Value;
                        if (r.Operator == 5) v = "%" + v + "%";
                        if (r.Operator == 6) v = v + "%";
                        sb.Append(" value=\"").Append(Xml(v)).Append("\" />");
                    }
                }
                sb.Append("</filter>");
            }
            sb.Append("</filter></entity></fetch>");
            return sb.ToString();
        }

        private static string FetchOp(int op)
        {
            switch (op)
            {
                case 1: return "eq";
                case 2: return "ne";
                case 3: return "in";
                case 4: return "not-in";
                case 5: return "like";
                case 6: return "like";
                case 7: return "gt";
                case 8: return "lt";
                case 9: return "null";
                case 10: return "not-null";
                default: return "eq";
            }
        }

        private static string Xml(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;");
        }

        private static string Summary(List<Rule> rules)
        {
            if (rules.Count == 0)
                return "No conditions yet, so this process would never be selected automatically.";
            var parts = new List<string>();
            foreach (var g in rules.GroupBy(r => r.Group).OrderBy(g => g.Key))
            {
                var any = g.Select(r => r.Label + " " + SaveProcessGraph.OperatorWord(r.Operator)
                    + Tail(r)).ToList();
                parts.Add(any.Count == 1 ? any[0] : "(" + string.Join(" or ", any.ToArray()) + ")");
            }
            return "Apply to a new case when " + string.Join(" and ", parts.ToArray()) + ".";
        }

        private static string Tail(Rule r)
        {
            if (r.Operator == 9 || r.Operator == 10) return "";
            var v = string.IsNullOrWhiteSpace(r.ValueLabel) ? r.Value : r.ValueLabel;
            return " " + v;
        }
    }
}

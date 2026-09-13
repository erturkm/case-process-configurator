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
            var links = new Dictionary<string, LinkEntity>(StringComparer.OrdinalIgnoreCase);
            foreach (var group in rules.GroupBy(r => r.Group).OrderBy(g => g.Key))
            {
                var f = new FilterExpression(LogicalOperator.Or);
                foreach (var r in group)
                {
                    var c = Condition(r);
                    if (c == null) { unsupported.Add(r.Label); continue; }

                    // A dotted rule targets the record behind a lookup. A hierarchy rule needs the
                    // same join for a different reason: Dataverse only accepts "under" against the
                    // primary key of the hierarchical table, never against the lookup on the case.
                    var hop = HopOf(r);
                    if (hop != null)
                    {
                        var link = LinkFor(query, links, hop, r);
                        if (link == null) { unsupported.Add(r.Label); continue; }
                        c.EntityName = link.EntityAlias;
                    }
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
            // Once a rule is bound to its join, the condition names the column on the far table,
            // not the path (or lookup) used to get there.
            var attr = ColumnOf(r);
            switch (r.Operator)
            {
                case 1:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.Equal, values[0]);
                case 2:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.NotEqual, values[0]);
                case 3:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.In, values.Cast<object>().ToArray());
                case 4:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.NotIn, values.Cast<object>().ToArray());
                case 5:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.Like, "%" + r.Value + "%");
                case 6:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.Like, r.Value + "%");
                case 7:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.GreaterThan, values[0]);
                case 8:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.LessThan, values[0]);
                case 9:
                    return new ConditionExpression(attr, ConditionOperator.Null);
                case 10:
                    return new ConditionExpression(attr, ConditionOperator.NotNull);
                case 11:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.UnderOrEqual,
                                                  values.Cast<object>().ToArray());
                case 12:
                    return values.Count == 0 ? null
                        : new ConditionExpression(attr, ConditionOperator.NotUnder,
                                                  values.Cast<object>().ToArray());
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

        // ------------------------------------------------------------------ related record joins

        private static bool IsHierarchyOp(int op) { return op == 11 || op == 12; }

        /// <summary>
        /// The lookup a rule has to traverse, or null when it can be evaluated on the case itself.
        /// Dotted rules name their hop; hierarchy rules imply one, because "under" is only legal
        /// against the primary key of the hierarchical table.
        /// </summary>
        private static string HopOf(Rule r)
        {
            var dot = r.Attribute.IndexOf('.');
            if (dot > 0) return r.Attribute.Substring(0, dot);
            return IsHierarchyOp(r.Operator) ? r.Attribute : null;
        }

        /// <summary>The column a condition names once its rule has been bound to a join.</summary>
        private static string ColumnOf(Rule r)
        {
            var dot = r.Attribute.IndexOf('.');
            if (dot > 0) return r.Attribute.Substring(dot + 1);
            if (IsHierarchyOp(r.Operator))
            {
                var target = TargetFor(r.Attribute, "");
                return target == null ? r.Attribute : target + "id";
            }
            return r.Attribute;
        }

        /// <summary>
        /// Adds (or reuses) the join a rule needs. A polymorphic lookup such as customerid can point
        /// at more than one table, and a query can only join one of them, so the preview joins the
        /// target that actually carries the column, preferring contact when both do. Runtime matching
        /// has no such limit because it reads whichever record the case really points at.
        /// </summary>
        private static LinkEntity LinkFor(QueryExpression query, Dictionary<string, LinkEntity> cache,
                                          string hop, Rule r)
        {
            LinkEntity existing;
            if (cache.TryGetValue(hop, out existing)) return existing;

            var dot = r.Attribute.IndexOf('.');
            var column = dot > 0 ? r.Attribute.Substring(dot + 1) : "";
            var target = TargetFor(hop, column);
            if (target == null) return null;

            var link = new LinkEntity("incident", target, hop, target + "id", JoinOperator.Inner)
            {
                EntityAlias = "rel_" + hop
            };
            query.LinkEntities.Add(link);
            cache[hop] = link;
            return link;
        }

        private static string TargetFor(string hop, string column)
        {
            // The rule builder only offers hops off the case that resolve to a customer or a user,
            // so a short static map keeps this off the metadata service on every preview call.
            switch (hop.ToLowerInvariant())
            {
                case "customerid":
                case "primarycontactid":
                case "responsiblecontactid":
                    return column.StartsWith("account", StringComparison.OrdinalIgnoreCase)
                        ? "account" : "contact";
                case "parentaccountid":
                case "accountid":
                    return "account";
                case "contactid":
                    return "contact";
                case "ownerid":
                    return "systemuser";
                case "subjectid":
                    return "subject";
                default:
                    return null;
            }
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
                var direct = g.Where(x => HopOf(x) == null).ToList();
                if (direct.Count == 0) continue;   // group is entirely joins, emitted below
                sb.Append("<filter type=\"or\">");
                foreach (var r in direct) AppendCondition(sb, r);
                sb.Append("</filter>");
            }
            sb.Append("</filter>");

            // Joined rules are grouped by the lookup they traverse so each hop is emitted once.
            foreach (var hop in rules.Where(r => HopOf(r) != null)
                                     .GroupBy(HopOf, StringComparer.OrdinalIgnoreCase))
            {
                var sample = hop.First();
                var dot = sample.Attribute.IndexOf('.');
                var target = TargetFor(hop.Key, dot > 0 ? sample.Attribute.Substring(dot + 1) : "");
                if (target == null) continue;
                sb.Append("<link-entity name=\"").Append(Xml(target))
                  .Append("\" from=\"").Append(Xml(target)).Append("id\" to=\"").Append(Xml(hop.Key))
                  .Append("\" alias=\"rel_").Append(Xml(hop.Key)).Append("\" link-type=\"inner\">");
                foreach (var byGroup in hop.GroupBy(r => r.Group).OrderBy(x => x.Key))
                {
                    sb.Append("<filter type=\"or\">");
                    foreach (var r in byGroup) AppendCondition(sb, r);
                    sb.Append("</filter>");
                }
                sb.Append("</link-entity>");
            }

            sb.Append("</entity></fetch>");
            return sb.ToString();
        }

        private static void AppendCondition(StringBuilder sb, Rule r)
        {
            sb.Append("<condition attribute=\"").Append(Xml(ColumnOf(r)))
              .Append("\" operator=\"").Append(FetchOp(r.Operator)).Append("\"");
            var values = Split(r.Value);
            if (r.Operator == 9 || r.Operator == 10) { sb.Append(" />"); return; }
            if (r.Operator == 3 || r.Operator == 4 || IsHierarchyOp(r.Operator))
            {
                sb.Append(">");
                foreach (var v in values) sb.Append("<value>").Append(Xml(v)).Append("</value>");
                sb.Append("</condition>");
                return;
            }
            var single = r.Value;
            if (r.Operator == 5) single = "%" + single + "%";
            if (r.Operator == 6) single = single + "%";
            sb.Append(" value=\"").Append(Xml(single)).Append("\" />");
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
                case 11: return "under-or-equal";
                case 12: return "not-under";
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

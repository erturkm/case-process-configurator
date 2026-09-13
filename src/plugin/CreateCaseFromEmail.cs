using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Cpc.Plugins
{
    /// <summary>
    /// Turns customer email delivered to a watched queue into a case.
    ///
    /// This is the same job an automatic record creation rule does, written as a
    /// plugin so the whole pipeline can be deployed and regression-tested from
    /// source rather than reproduced by hand in a wizard.
    ///
    /// Deliberately conservative. A case is only opened when every one of these
    /// holds, because the alternative - a queue mailbox quietly manufacturing
    /// cases from newsletters, bounces and internal chatter - is far worse than
    /// missing one:
    ///
    ///   * the email is inbound, not something an agent sent;
    ///   * it is not already regarding a record, so replies stay on their case;
    ///   * it was addressed to a queue that is configured to create cases;
    ///   * the sender matches a known contact or account;
    ///   * that customer has no open case on the same subject line, so a customer
    ///     chasing themselves does not open a second case.
    ///
    /// Creating the incident triggers TriageInboundCase (pre-operation), which
    /// derives the subject, and then ApplyCaseProcess (post-operation), which
    /// matches a process template and stamps SLA, tasks and documents.
    /// </summary>
    public sealed class CreateCaseFromEmail : IPlugin
    {
        private const int DirectionIncoming = 0;   // directioncode false == received
        private const int OriginEmail = 2;
        private const int StateActive = 0;

        public void Execute(IServiceProvider provider)
        {
            var ctx = (IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
            var trace = (ITracingService)provider.GetService(typeof(ITracingService));

            if (!ctx.InputParameters.Contains("Target")) return;
            var target = ctx.InputParameters["Target"] as Entity;
            if (target == null || target.LogicalName != "email") return;

            var factory = (IOrganizationServiceFactory)provider.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(null);   // run as the system user

            var email = svc.Retrieve("email", target.Id, new ColumnSet(
                "subject", "description", "directioncode", "regardingobjectid",
                "sender", "from", "to", "torecipients", "createdon"));

            if (email.GetAttributeValue<bool>("directioncode"))
            {
                trace.Trace("outbound email, ignoring");
                return;
            }

            if (email.GetAttributeValue<EntityReference>("regardingobjectid") != null)
            {
                trace.Trace("email already regarding a record, ignoring");
                return;
            }

            var queue = MatchedQueue(svc, email, trace);
            if (queue == null)
            {
                trace.Trace("not addressed to a case-creating queue, ignoring");
                return;
            }

            var customer = ResolveSender(svc, email, trace);
            if (customer == null)
            {
                trace.Trace("sender not recognised, leaving for manual triage");
                return;
            }

            string subject = (email.GetAttributeValue<string>("subject") ?? "Customer enquiry").Trim();
            if (subject.Length == 0) subject = "Customer enquiry";

            var duplicate = ExistingOpenCase(svc, customer, subject);
            if (duplicate != null)
            {
                trace.Trace("open case {0} already covers this thread, linking instead", duplicate.Id);
                Link(svc, email.Id, duplicate);
                return;
            }

            var incident = new Entity("incident");
            incident["title"] = Truncate(StripReplyPrefix(subject), 200);
            incident["description"] = Truncate(PlainText(
                email.GetAttributeValue<string>("description")), 100000);
            incident["customerid"] = customer;
            incident["caseorigincode"] = new OptionSetValue(OriginEmail);
            incident["casetypecode"] = new OptionSetValue(3);   // Question
            incident["cpc_sourcequeue"] = queue;

            var caseId = svc.Create(incident);
            trace.Trace("created case {0} for {1}", caseId, customer.LogicalName);

            Link(svc, email.Id, new EntityReference("incident", caseId));
        }

        /// <summary>
        /// Attaches the email to the case so it lands on the timeline rather than
        /// sitting orphaned in the queue.
        /// </summary>
        private static void Link(IOrganizationService svc, Guid emailId, EntityReference caseRef)
        {
            var update = new Entity("email", emailId);
            update["regardingobjectid"] = caseRef;
            svc.Update(update);
        }

        /// <summary>
        /// Finds a queue whose address appears in the recipients. Only queues
        /// flagged cpc_createcases participate, so adding a queue to the org does
        /// not silently enrol it in case creation.
        /// </summary>
        private static EntityReference MatchedQueue(IOrganizationService svc, Entity email,
                                                    ITracingService trace)
        {
            var addresses = Recipients(email);
            if (addresses.Count == 0) return null;
            trace.Trace("recipients: {0}", string.Join(", ", addresses.ToArray()));

            var q = new QueryExpression("queue") { NoLock = true };
            q.ColumnSet = new ColumnSet("queueid", "name", "emailaddress");
            q.Criteria.AddCondition("emailaddress", ConditionOperator.NotNull);
            q.Criteria.AddCondition("cpc_createcases", ConditionOperator.Equal, true);

            foreach (var queue in svc.RetrieveMultiple(q).Entities)
            {
                var address = queue.GetAttributeValue<string>("emailaddress");
                if (address != null && addresses.Contains(address.Trim().ToLowerInvariant()))
                    return new EntityReference("queue", queue.Id);
            }
            return null;
        }

        private static HashSet<string> Recipients(Entity email)
        {
            var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach (var field in new[] { "to", "cc" })
            {
                var parties = email.GetAttributeValue<EntityCollection>(field);
                if (parties == null) continue;
                foreach (var party in parties.Entities)
                {
                    var address = party.GetAttributeValue<string>("addressused");
                    if (!string.IsNullOrEmpty(address)) set.Add(address.Trim().ToLowerInvariant());
                }
            }

            // Server-side sync sometimes lands the address only in torecipients.
            var raw = email.GetAttributeValue<string>("torecipients");
            if (!string.IsNullOrEmpty(raw))
                foreach (var part in raw.Split(';', ','))
                    if (part.Trim().Length > 0) set.Add(part.Trim().ToLowerInvariant());

            return set;
        }

        /// <summary>
        /// Prefers the contact or account the platform already resolved on the
        /// sender party, and falls back to an email-address lookup for senders the
        /// platform left unmatched.
        /// </summary>
        private static EntityReference ResolveSender(IOrganizationService svc, Entity email,
                                                     ITracingService trace)
        {
            string address = null;

            var from = email.GetAttributeValue<EntityCollection>("from");
            if (from != null && from.Entities.Count > 0)
            {
                var party = from.Entities[0];
                var resolved = party.GetAttributeValue<EntityReference>("partyid");
                if (resolved != null &&
                    (resolved.LogicalName == "contact" || resolved.LogicalName == "account"))
                    return resolved;

                address = party.GetAttributeValue<string>("addressused");
            }

            address = (address ?? email.GetAttributeValue<string>("sender") ?? "").Trim();
            if (address.Length == 0) return null;
            trace.Trace("resolving sender by address: {0}", address);

            var contact = FirstMatch(svc, "contact", address,
                                     new[] { "emailaddress1", "emailaddress2", "emailaddress3" });
            if (contact != null) return contact;

            return FirstMatch(svc, "account", address,
                              new[] { "emailaddress1", "emailaddress2" });
        }

        private static EntityReference FirstMatch(IOrganizationService svc, string entity,
                                                  string address, string[] fields)
        {
            var q = new QueryExpression(entity) { NoLock = true, TopCount = 1 };
            q.ColumnSet = new ColumnSet(entity + "id");
            q.Criteria.FilterOperator = LogicalOperator.Or;
            foreach (var field in fields)
                q.Criteria.AddCondition(field, ConditionOperator.Equal, address);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, StateActive);

            var found = svc.RetrieveMultiple(q).Entities.FirstOrDefault();
            return found == null ? null : new EntityReference(entity, found.Id);
        }

        /// <summary>
        /// A customer replying outside the thread, or chasing with a fresh mail,
        /// should not spawn a parallel case for the same issue.
        /// </summary>
        private static EntityReference ExistingOpenCase(IOrganizationService svc,
                                                        EntityReference customer, string subject)
        {
            var title = Truncate(StripReplyPrefix(subject), 200);

            var q = new QueryExpression("incident") { NoLock = true, TopCount = 1 };
            q.ColumnSet = new ColumnSet("incidentid");
            q.Criteria.AddCondition("customerid", ConditionOperator.Equal, customer.Id);
            q.Criteria.AddCondition("statecode", ConditionOperator.Equal, StateActive);
            q.Criteria.AddCondition("title", ConditionOperator.Equal, title);

            var found = svc.RetrieveMultiple(q).Entities.FirstOrDefault();
            return found == null ? null : new EntityReference("incident", found.Id);
        }

        /// <summary>
        /// "RE: RE: FW: Card dispute" is the same issue as "Card dispute";
        /// keeping the prefixes would defeat the duplicate check above.
        /// </summary>
        private static string StripReplyPrefix(string subject)
        {
            var s = subject.Trim();
            var pattern = new Regex(@"^\s*(re|fw|fwd|aw|tr)\s*(\[\d+\])?\s*:\s*",
                                    RegexOptions.IgnoreCase);
            while (pattern.IsMatch(s)) s = pattern.Replace(s, "", 1).Trim();
            return s.Length == 0 ? subject.Trim() : s;
        }

        private static string PlainText(string html)
        {
            if (string.IsNullOrEmpty(html)) return string.Empty;
            var s = Regex.Replace(html, @"<\s*br\s*/?\s*>", "\n", RegexOptions.IgnoreCase);
            s = Regex.Replace(s, @"<\s*/\s*(p|div|tr|li|h\d)\s*>", "\n", RegexOptions.IgnoreCase);
            s = Regex.Replace(s, "<[^>]+>", " ");
            s = s.Replace("&nbsp;", " ").Replace("&amp;", "&").Replace("&lt;", "<")
                 .Replace("&gt;", ">").Replace("&quot;", "\"").Replace("&#39;", "'");
            s = Regex.Replace(s, @"[ \t]+", " ");
            s = Regex.Replace(s, @"\n\s*\n\s*\n+", "\n\n");
            return s.Trim();
        }

        private static string Truncate(string value, int max)
        {
            if (string.IsNullOrEmpty(value)) return value;
            return value.Length <= max ? value : value.Substring(0, max);
        }
    }
}

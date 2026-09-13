using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

namespace Cpc.Plugins
{
    /// <summary>
    /// Gives an incoming case a subject and a priority before the rest of the
    /// engine sees it.
    ///
    /// Cases raised by the automatic record creation rule arrive with nothing but
    /// a title and description copied from the customer's email. Without a subject
    /// no match rule can fire, so ApplyCaseProcess would find no template and the
    /// case would land bare. This runs pre-operation on Create, reads the text the
    /// customer actually wrote, and picks the best-fitting leaf subject.
    ///
    /// Scoring is deliberately simple and explainable: each candidate subject owns
    /// a set of weighted phrases, a phrase only counts on a whole-word boundary,
    /// and the highest total wins provided it clears a floor. Anything below the
    /// floor is left for a human rather than guessed at, because a wrong subject
    /// silently applies a wrong process.
    /// </summary>
    public sealed class TriageInboundCase : IPlugin
    {
        // Subject title -> weighted phrases. Weights: 3 unmistakable, 2 strong, 1 supporting.
        private static readonly Dictionary<string, Tuple<string, int>[]> Rules =
            new Dictionary<string, Tuple<string, int>[]>(StringComparer.OrdinalIgnoreCase)
        {
            { "Unauthorised Transaction", new[] {
                P("did not authorise", 3), P("did not authorize", 3), P("unauthorised", 3),
                P("unauthorized", 3), P("i did not make", 3), P("someone has used", 3),
                P("fraudulent", 2), P("stolen money", 2), P("without my knowledge", 2) } },

            { "Phishing and Scam Report", new[] {
                P("phishing", 3), P("smishing", 3), P("scam", 2), P("suspicious link", 2),
                P("impersonating", 2), P("fake message", 2), P("fake sms", 2) } },

            { "Lost or Stolen Card", new[] {
                P("lost my card", 3), P("card was stolen", 3), P("stolen card", 3),
                P("lost card", 3), P("card is missing", 2), P("misplaced my card", 2),
                P("block my card", 2), P("replacement card", 1) } },

            { "Card Disputes", new[] {
                P("dispute", 3), P("charged twice", 3), P("double charge", 3),
                P("duplicate charge", 3), P("chargeback", 3), P("merchant", 2),
                P("refund", 2), P("cancelled my subscription", 2), P("still being charged", 2),
                P("cash not dispensed", 3), P("atm did not dispense", 3) } },

            { "Card Limit Increase", new[] {
                P("limit increase", 3), P("increase my limit", 3), P("credit limit", 2),
                P("raise my limit", 3), P("higher limit", 2), P("limit decrease", 3),
                P("reduce my limit", 3), P("temporary limit", 2) } },

            { "Card Application", new[] {
                P("apply for a credit card", 3), P("new credit card", 2),
                P("credit card application", 3), P("world elite", 2) } },

            { "Card Delivery and PIN", new[] {
                P("card declined", 3), P("declined abroad", 3), P("pin", 2),
                P("card not delivered", 3), P("card has not arrived", 3),
                P("travel notification", 2), P("activate my card", 2) } },

            { "New Account Opening", new[] {
                P("open an account", 3), P("open a new account", 3), P("account opening", 3),
                P("new customer", 2), P("current account", 2), P("savings account", 2),
                P("joint account", 2), P("relocating", 1), P("start a new job", 1) } },

            { "KYC Refresh", new[] {
                P("kyc", 3), P("know your customer", 3), P("update my documents", 2),
                P("emirates id has expired", 3), P("expired id", 2), P("periodic review", 2) } },

            { "International Transfer", new[] {
                P("international transfer", 3), P("swift", 3), P("overseas transfer", 3),
                P("transfer to the uk", 2), P("transfer abroad", 3), P("foreign transfer", 3),
                P("beneficiary bank", 2) } },

            { "Domestic Transfer", new[] {
                P("domestic transfer", 3), P("local transfer", 3), P("transfer within the uae", 3),
                P("iban", 1) } },

            { "Salary Transfer and Payroll", new[] {
                P("salary", 3), P("payroll", 3), P("wps", 3), P("salary not credited", 3),
                P("my employer", 2), P("wage", 2) } },

            { "Direct Debit and Utility Payment", new[] {
                P("direct debit", 3), P("dewa", 3), P("utility", 2), P("standing instruction", 3),
                P("recurring payment", 2), P("bill payment", 2) } },

            { "Payments", new[] {
                P("payment", 1), P("transfer", 1), P("not received", 1) } },

            { "Online Banking Login", new[] {
                P("cannot log in", 3), P("can not log in", 3), P("cannot login", 3),
                P("locked out", 3), P("online banking", 2), P("reset my password", 3),
                P("password", 2) } },

            { "Mobile App Access", new[] {
                P("mobile app", 3), P("app crashes", 3), P("app not working", 3),
                P("cannot open the app", 3) } },

            { "Digital Registration and Devices", new[] {
                P("new device", 3), P("changed my phone", 3), P("otp", 2),
                P("register my device", 3), P("not receiving otp", 3) } },

            { "Mortgage", new[] {
                P("mortgage", 3), P("home loan", 3), P("property purchase", 2),
                P("rate switch", 2), P("fixed rate", 1), P("variable rate", 1) } },

            { "Personal Loan", new[] {
                P("personal loan", 3), P("loan application", 2), P("borrow", 1) } },

            { "Auto Loan", new[] {
                P("car loan", 3), P("auto loan", 3), P("vehicle finance", 3) } },

            { "Loan Settlement and Early Payoff", new[] {
                P("settle my loan", 3), P("early settlement", 3), P("settlement quote", 3),
                P("pay off my loan", 3), P("liability letter", 2) } },

            { "Arrears and Repayment Plan", new[] {
                P("arrears", 3), P("missed a payment", 3), P("repayment plan", 3),
                P("behind on my payments", 3), P("collections", 2) } },

            { "Fee Reversal Request", new[] {
                P("reverse the fee", 3), P("refund the charge", 3), P("waive", 3),
                P("late fee", 2), P("annual fee", 2), P("charged a fee", 2) } },

            { "Interest and Profit Query", new[] {
                P("interest rate", 3), P("profit rate", 3), P("interest charged", 2) } },

            { "Statements", new[] {
                P("statement", 3), P("bank statement", 3), P("statements for", 3),
                P("for my visa", 2) } },

            { "Balance Certificate", new[] {
                P("balance certificate", 3), P("certificate of balance", 3) } },

            { "Liability and Clearance Letter", new[] {
                P("clearance letter", 3), P("liability letter", 3), P("no liability", 3) } },

            { "Account Closure", new[] {
                P("close my account", 3), P("account closure", 3), P("closing my account", 3) } },

            { "Address and Contact Update", new[] {
                P("change my address", 3), P("update my address", 3),
                P("update my mobile", 3), P("change my phone number", 3),
                P("new email address", 2) } },

            { "Cheque Book and Standing Instructions", new[] {
                P("cheque", 3), P("check book", 3), P("cheque book", 3),
                P("returned unpaid", 2), P("bounced", 2) } },

            { "Account Servicing", new[] {
                P("my account", 1), P("account details", 2) } },

            { "Regulatory Complaint", new[] {
                P("central bank", 3), P("regulator", 3), P("ombudsman", 3),
                P("formal complaint to the", 2), P("escalate to the central bank", 3) } },

            { "Service Quality Complaint", new[] {
                P("complaint", 3), P("unacceptable", 2), P("very disappointed", 2),
                P("poor service", 3), P("no one has responded", 2), P("repeated calls", 2),
                P("this is unacceptable", 3) } },
        };

        private static Tuple<string, int> P(string phrase, int weight)
        {
            return Tuple.Create(phrase, weight);
        }

        private const int MinimumScore = 3;

        public void Execute(IServiceProvider provider)
        {
            var ctx = (IPluginExecutionContext)provider.GetService(typeof(IPluginExecutionContext));
            var trace = (ITracingService)provider.GetService(typeof(ITracingService));

            if (!ctx.InputParameters.Contains("Target")) return;
            var target = ctx.InputParameters["Target"] as Entity;
            if (target == null || target.LogicalName != "incident") return;

            // Only fill gaps. A case created by an agent or by a seeding script that
            // already chose a subject must never be second-guessed.
            if (target.Contains("subjectid") && target["subjectid"] != null) return;

            var factory = (IOrganizationServiceFactory)provider.GetService(typeof(IOrganizationServiceFactory));
            var svc = factory.CreateOrganizationService(ctx.UserId);

            string text = Normalise(
                Value(target, "title") + " \n " + Value(target, "description"));
            if (text.Trim().Length == 0) return;

            string best = null;
            int bestScore = 0;
            var runnerUp = 0;

            foreach (var rule in Rules)
            {
                int score = 0;
                foreach (var phrase in rule.Value)
                    if (Contains(text, phrase.Item1)) score += phrase.Item2;

                if (score > bestScore) { runnerUp = bestScore; bestScore = score; best = rule.Key; }
                else if (score > runnerUp) runnerUp = score;
            }

            trace.Trace("triage: best={0} score={1} runnerUp={2}", best, bestScore, runnerUp);

            if (best == null || bestScore < MinimumScore)
            {
                trace.Trace("triage: below threshold, leaving subject empty for manual review");
                return;
            }

            var subject = FindSubject(svc, best);
            if (subject == null)
            {
                trace.Trace("triage: subject '{0}' not found in this org", best);
                return;
            }

            target["subjectid"] = subject;
            trace.Trace("triage: subject set to {0}", best);

            if (!target.Contains("prioritycode") || target["prioritycode"] == null)
            {
                var priority = Priority(text, best);
                if (priority.HasValue)
                {
                    target["prioritycode"] = new OptionSetValue(priority.Value);
                    trace.Trace("triage: priority set to {0}", priority.Value);
                }
            }

            if (!target.Contains("caseorigincode") || target["caseorigincode"] == null)
                target["caseorigincode"] = new OptionSetValue(2); // Email
        }

        /// <summary>
        /// Fraud, unauthorised spend and regulatory escalations cost the bank money
        /// or goodwill by the hour, so they open at High regardless of wording.
        /// </summary>
        private static int? Priority(string text, string subject)
        {
            if (subject == "Unauthorised Transaction" || subject == "Lost or Stolen Card" ||
                subject == "Phishing and Scam Report" || subject == "Regulatory Complaint")
                return 1;

            if (Contains(text, "urgent") || Contains(text, "immediately") ||
                Contains(text, "as soon as possible") || Contains(text, "emergency"))
                return 1;

            return null;
        }

        private static EntityReference FindSubject(IOrganizationService svc, string title)
        {
            var q = new QueryExpression("subject") { NoLock = true, TopCount = 1 };
            q.ColumnSet = new ColumnSet("subjectid");
            q.Criteria.AddCondition("title", ConditionOperator.Equal, title);
            var found = svc.RetrieveMultiple(q).Entities.FirstOrDefault();
            return found == null ? null : new EntityReference("subject", found.Id);
        }

        private static string Value(Entity e, string field)
        {
            return e.Contains(field) && e[field] != null ? e[field].ToString() : string.Empty;
        }

        /// <summary>
        /// Strips HTML, collapses whitespace and lower-cases, so a phrase can be
        /// matched the same way whether the mail arrived as HTML or plain text.
        /// </summary>
        private static string Normalise(string raw)
        {
            if (string.IsNullOrEmpty(raw)) return string.Empty;
            var s = Regex.Replace(raw, "<[^>]+>", " ");
            s = s.Replace("&nbsp;", " ").Replace("&amp;", "&")
                 .Replace("&lt;", "<").Replace("&gt;", ">").Replace("&#39;", "'")
                 .Replace("\u2019", "'").Replace("\u2018", "'");
            s = Regex.Replace(s, @"\s+", " ");
            return s.ToLowerInvariant();
        }

        /// <summary>
        /// Whole-word containment, so "pin" does not match "shopping" and
        /// "loan" does not match "loaned" inside an unrelated sentence.
        /// </summary>
        private static bool Contains(string haystack, string needle)
        {
            int i = 0;
            while ((i = haystack.IndexOf(needle, i, StringComparison.Ordinal)) >= 0)
            {
                bool leftOk = i == 0 || !char.IsLetterOrDigit(haystack[i - 1]);
                int end = i + needle.Length;
                bool rightOk = end >= haystack.Length || !char.IsLetterOrDigit(haystack[end]);
                if (leftOk && rightOk) return true;
                i = end;
            }
            return false;
        }
    }
}

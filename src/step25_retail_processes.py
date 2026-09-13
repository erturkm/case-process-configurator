"""Step 25: retail banking case processes for the RAKBANK demo.

Adds three retail business process flows (card dispute, complaint handling and service
fulfilment), the document packages retail journeys demand, and thirteen case process
templates covering the everyday work of a retail bank contact centre - disputes, fraud,
payment traces, digital access, lending applications, servicing, collections and complaints.

Re-runnable: writes are keyed on name.
"""
import time

import dv
import bpfgen
from step19_banking_processes import upsert_package, apply_graph, layout

P = dv.PREFIX
NOW = "2026-08-31T06:00:00Z"
CAL = "UAE Sun-Thu 08:00-18:00"

POS, NEU, NEG, END = 1, 2, 3, 4
TEAM_, USER_, ROLE_, QUEUE_, MGR_, OWNER_ = 1, 2, 3, 4, 5, 6

# ---------------------------------------------------------------- business process flows
BPF_DISPUTE = [
    ("Capture", "identify", [
        ("Cardholder", "customerid", "lookup", True),
        ("Dispute type", "subjectid", "lookup", False)]),
    ("Verify", "research", [
        ("Investigator", "ownerid", "lookup", False)]),
    ("Provisional Credit", "research", [
        ("Provisional credit given", "cpc_provisionalcredit", "boolean", False)]),
    ("Investigate", "research", [
        ("Findings", "description", "memo", False)]),
    ("Resolution", "resolve", [
        ("Resolved on", "followupby", "datetime", False)]),
]

BPF_COMPLAINT = [
    ("Acknowledge", "identify", [
        ("Complainant", "customerid", "lookup", True),
        ("Severity", "prioritycode", "picklist", False)]),
    ("Investigate", "research", [
        ("Investigator", "ownerid", "lookup", False),
        ("Root cause", "description", "memo", False)]),
    ("Redress", "research", [
        ("Redress agreed", "cpc_redressamount", "money", False)]),
    ("Closure", "resolve", [
        ("Final response sent", "followupby", "datetime", False)]),
]

BPF_SERVICE = [
    ("Log", "identify", [
        ("Customer", "customerid", "lookup", True),
        ("Request type", "subjectid", "lookup", False)]),
    ("Validate", "research", [
        ("Handler", "ownerid", "lookup", False)]),
    ("Fulfil", "research", [
        ("Target date", "followupby", "datetime", False)]),
    ("Confirm", "resolve", [
        ("Confirmation notes", "description", "memo", False)]),
]

ORDER = {
    "dispute":  ["Capture", "Verify", "Provisional Credit", "Investigate", "Resolution"],
    "complaint": ["Acknowledge", "Investigate", "Redress", "Closure"],
    "service":  ["Log", "Validate", "Fulfil", "Confirm"],
    "retail":   ["Application", "Assessment", "Decision", "Fulfilment"],
}

# ---------------------------------------------------------------- document packages
PACKAGES = {
"Chargeback Evidence Pack": [
    ("Signed Dispute Declaration", 1, True, 1, 24, "dispute_declaration.docx", "Card Operations"),
    ("Transaction Statement Extract", 2, True, 3, 4, "", "Card Operations"),
    ("Merchant Correspondence", 3, False, 1, 48, "", "Card Operations"),
    ("Proof of Cancellation or Return", 4, False, 1, 48, "", "Card Operations"),
    ("Scheme Chargeback Submission", 5, True, 3, 72, "chargeback_form.docx", "Card Operations"),
],
"Payment Trace Pack": [
    ("Signed Transfer Instruction", 1, True, 1, 8, "", "Payments Investigations"),
    ("SWIFT Message Copy", 2, True, 3, 8, "", "Payments Investigations"),
    ("Beneficiary Bank Confirmation", 3, False, 4, 72, "", "Payments Investigations"),
    ("Trace Request (MT199)", 4, True, 3, 24, "trace_request.docx", "Payments Investigations"),
],
"Digital Access Verification Pack": [
    ("Emirates ID Copy", 1, True, 1, 4, "", "Digital Banking Support"),
    ("Device and Login History", 2, True, 3, 2, "", "Digital Banking Support"),
    ("Signed Re-registration Consent", 3, False, 1, 24, "", "Digital Banking Support"),
],
"Account Closure Pack": [
    ("Signed Closure Request", 1, True, 1, 24, "closure_request.docx", "Branch Operations"),
    ("Emirates ID Copy", 2, True, 1, 24, "", "Branch Operations"),
    ("Cards and Cheque Books Returned", 3, True, 1, 72, "", "Branch Operations"),
    ("Liability Clearance Letter", 4, True, 3, 48, "clearance_letter.docx", "Loan Operations"),
    ("Final Balance Settlement Advice", 5, True, 3, 24, "", "Branch Operations"),
],
"Card Replacement Pack": [
    ("Card Block Confirmation", 1, True, 3, 1, "", "Card Operations"),
    ("Police Report (if stolen)", 2, False, 1, 48, "", "Card Operations"),
    ("Delivery Address Confirmation", 3, True, 1, 8, "", "Card Operations"),
],
"Collections Arrangement Pack": [
    ("Current Statement of Account", 1, True, 3, 4, "", "Collections and Recoveries"),
    ("Income and Expenditure Declaration", 2, True, 1, 72, "income_expenditure.docx",
     "Collections and Recoveries"),
    ("Signed Repayment Arrangement", 3, True, 1, 96, "repayment_plan.docx",
     "Collections and Recoveries"),
],
"Credit Card Application Pack": [
    ("Emirates ID and Passport Copy", 1, True, 1, 24, "", "Retail Lending Operations"),
    ("Salary Certificate", 2, True, 1, 48, "", "Retail Lending Operations"),
    ("Bank Statements (3 months)", 3, True, 1, 48, "", "Retail Lending Operations"),
    ("Credit Bureau Report", 4, True, 3, 12, "", "Retail Lending Operations"),
    ("Signed Card Application and Key Facts", 5, True, 1, 48, "card_application.docx",
     "Retail Lending Operations"),
],
"Auto Loan Pack": [
    ("Emirates ID and Passport Copy", 1, True, 1, 24, "", "Retail Lending Operations"),
    ("Salary Certificate", 2, True, 1, 48, "", "Retail Lending Operations"),
    ("Vehicle Quotation and Proforma Invoice", 3, True, 1, 48, "", "Retail Lending Operations"),
    ("Credit Bureau Report", 4, True, 3, 12, "", "Retail Lending Operations"),
    ("Comprehensive Insurance Cover Note", 5, True, 1, 96, "", "Loan Operations"),
    ("Vehicle Registration (Mulkiya)", 6, True, 1, 120, "", "Loan Operations"),
],
"Customer Details Update Pack": [
    ("Signed Amendment Request", 1, True, 1, 24, "amendment_request.docx", "Branch Operations"),
    ("Emirates ID Copy", 2, True, 1, 24, "", "Branch Operations"),
    ("Proof of Address (Tenancy or DEWA)", 3, True, 1, 48, "", "Branch Operations"),
],
"Standing Instruction Pack": [
    ("Signed Standing Instruction Mandate", 1, True, 1, 24, "si_mandate.docx",
     "Branch Operations"),
    ("Beneficiary Details Confirmation", 2, True, 1, 24, "", "Branch Operations"),
],
"KYC Refresh Pack": [
    ("Valid Emirates ID", 1, True, 1, 72, "", "Onboarding Operations"),
    ("Valid Passport and Visa Page", 2, True, 1, 72, "", "Onboarding Operations"),
    ("Updated Proof of Address", 3, True, 1, 96, "", "Onboarding Operations"),
    ("Source of Funds Declaration", 4, True, 1, 96, "source_of_funds.docx",
     "Onboarding Operations"),
    ("Screening and Risk Rating Result", 5, True, 3, 24, "", "Onboarding Operations"),
],
"Complaint Redress Pack": [
    ("Customer Complaint Statement", 1, True, 1, 24, "", "Complaints Management"),
    ("Supporting Evidence from Customer", 2, False, 1, 72, "", "Complaints Management"),
    ("Investigation Findings Report", 3, True, 3, 96, "investigation_findings.docx",
     "Complaints Management"),
    ("Final Response Letter", 4, True, 3, 120, "final_response.docx", "Complaints Management"),
],
"Regulatory Referral Pack": [
    ("Central Bank Referral Notice", 1, True, 4, 4, "", "Quality and Regulatory"),
    ("Complete Case Chronology", 2, True, 3, 48, "case_chronology.docx", "Quality and Regulatory"),
    ("Investigation Findings Report", 3, True, 3, 96, "investigation_findings.docx",
     "Quality and Regulatory"),
    ("Regulator Response Submission", 4, True, 3, 120, "regulator_response.docx",
     "Quality and Regulatory"),
],
"Fee Review Pack": [
    ("Statement Extract Showing the Charge", 1, True, 3, 4, "", "Contact Centre Tier 1"),
    ("Fee Schedule Extract", 2, True, 3, 8, "", "Contact Centre Tier 1"),
    ("Waiver Approval", 3, False, 3, 24, "", "Complaints Management"),
],
}


# ---------------------------------------------------------------- extra case columns
EXTRA_COLUMNS = [
    ("cpc_provisionalcredit", "Provisional Credit Given", "BooleanAttributeMetadata",
     "Set when a temporary credit has been posted to the cardholder while the dispute runs."),
    ("cpc_redressamount", "Redress Amount", "MoneyAttributeMetadata",
     "Goodwill or compensation agreed with the customer as part of a complaint outcome."),
]


def ensure_columns():
    for logical, display, kind, desc in EXTRA_COLUMNS:
        try:
            dv.get(f"EntityDefinitions(LogicalName='incident')/Attributes(LogicalName='{logical}')"
                   "?$select=LogicalName")
            print("  = column", logical)
            continue
        except RuntimeError:
            pass
        body = {
            "@odata.type": f"Microsoft.Dynamics.CRM.{kind}",
            "SchemaName": logical.replace("cpc_", "cpc_"), "LogicalName": logical,
            "DisplayName": dv.label(display), "Description": dv.label(desc),
            "RequiredLevel": {"Value": "None"},
        }
        if kind == "BooleanAttributeMetadata":
            body["OptionSet"] = {
                "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                "TrueOption": {"Value": 1, "Label": dv.label("Yes")},
                "FalseOption": {"Value": 0, "Label": dv.label("No")},
            }
            body["DefaultValue"] = False
        else:
            body["Precision"] = 2
            body["PrecisionSource"] = 2
            body["ImeMode"] = "Disabled"
        for attempt in range(12):
            try:
                dv.post("EntityDefinitions(LogicalName='incident')/Attributes", body)
                break
            except RuntimeError as e:
                # Another solution import or publish is holding the customization lock.
                if "another [Import]" in str(e) or "-> 429" in str(e):
                    print("    waiting for the customization lock...")
                    time.sleep(20)
                    continue
                raise
        print("  + column", logical)


# ---------------------------------------------------------------- templates
# task tuple: (seq, name, stage, assigntype, assignee, duehours, slastartwhen,
#              slatargethours, warn%, onbreach, blocksstage, mandatory, instruction)
# graph tuple: (from task, outcome label, sentiment, next task or None, flags, guidance)
TEMPLATES = [

# ---------------------------------------------------------------------------- 1
{
 "name": "Card Dispute - Chargeback", "rank": 17, "status": 2,
 "desc": "A cardholder disputes a transaction they recognise but believe is wrong - goods never "
         "arrived, the amount is incorrect, a cancelled subscription kept billing, or a duplicate "
         "posted. Runs the scheme chargeback clock, posts provisional credit where policy allows, "
         "and branches on whether the merchant defends the claim.",
 "bpf": "dispute", "startstage": "Capture", "sla": "Standard 24-Hour Response",
 "package": "Chargeback Evidence Pack", "fr": 4, "res": 720, "priority": 2,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Card Disputes")],
 "tasks": [
  (1, "Capture dispute details and reason code", "Capture", QUEUE_, "Card Disputes and Chargebacks",
   4, 1, 2, 75, 2, True, True,
   "Confirm the card, the transaction date, the merchant and the amount, and map the customer's "
   "story to a scheme reason code. The reason code drives every deadline that follows."),
  (2, "Collect the dispute declaration and evidence", "Capture", QUEUE_, "Card Disputes and Chargebacks",
   48, 3, 24, 75, 2, True, True,
   "Send the declaration for signature and chase the supporting evidence. Nothing can be raised "
   "with the scheme without a signed declaration."),
  (3, "Verify the transaction against the card record", "Verify", TEAM_, "Card Operations",
   8, 3, 4, 75, 2, True, True,
   "Check the authorisation, the terminal and the 3-D Secure result. Rule out a genuine "
   "cardholder-present purchase before going further."),
  (4, "Assess provisional credit eligibility", "Provisional Credit", TEAM_, "Card Operations",
   8, 3, 4, 80, 2, False, True,
   "Apply the provisional credit policy for the amount and reason code, and post it if the "
   "customer qualifies. Tell the customer it is temporary and reversible."),
  (5, "Raise chargeback with the scheme", "Investigate", TEAM_, "Card Operations",
   72, 3, 48, 75, 3, True, True,
   "Submit within the scheme deadline for the reason code. Late submission loses the right to "
   "recover, regardless of the merits."),
  (6, "Handle merchant representment", "Investigate", TEAM_, "Card Operations",
   240, 3, 168, 80, 2, False, False,
   "The merchant has defended the chargeback. Weigh their evidence against the customer's and "
   "decide whether to accept, or escalate to pre-arbitration."),
  (7, "Resolve and notify the customer", "Resolution", QUEUE_, "Card Disputes and Chargebacks",
   24, 3, 12, 80, 2, True, True,
   "Confirm the final position in writing, make the provisional credit permanent or reverse it, "
   "and explain the customer's next options."),
 ],
 "graph": [
  ("Capture dispute details and reason code", "Dispute is valid - proceed", POS,
   "Collect the dispute declaration and evidence", ["default"],
   "The transaction is disputable under a scheme reason code and is within the time limit."),
  ("Capture dispute details and reason code", "Customer recognises the transaction", END,
   None, ["close", "comment"],
   "On review the customer accepts the charge. Close with the explanation recorded."),
  ("Capture dispute details and reason code", "Suspected fraud - not a dispute", NEG,
   None, ["comment"],
   "The customer did not make the transaction at all. This belongs with Fraud Operations, "
   "not the chargeback team."),

  ("Collect the dispute declaration and evidence", "Evidence complete", POS,
   "Verify the transaction against the card record", ["default", "advance"],
   "Signed declaration and supporting documents are on file."),
  ("Collect the dispute declaration and evidence", "Customer did not respond", END,
   None, ["close", "comment"],
   "Two chases and no declaration. Close and tell the customer they can reopen within the "
   "scheme window."),

  ("Verify the transaction against the card record", "Transaction confirmed disputable", POS,
   "Assess provisional credit eligibility", ["default", "advance"],
   "Authorisation and 3-D Secure data support the customer's account of events."),
  ("Verify the transaction against the card record", "Cardholder present and authenticated", NEG,
   "Resolve and notify the customer", ["comment", "stage:Resolution"],
   "Chip and PIN or a successful 3-D Secure challenge makes the claim very hard to win. "
   "Explain this to the customer before closing."),

  ("Assess provisional credit eligibility", "Provisional credit posted", POS,
   "Raise chargeback with the scheme", ["default", "advance"],
   "Temporary credit is on the account and the customer has been told it is reversible."),
  ("Assess provisional credit eligibility", "Not eligible for provisional credit", NEU,
   "Raise chargeback with the scheme", ["advance"],
   "Amount or reason code falls outside policy. Proceed without the temporary credit."),

  ("Raise chargeback with the scheme", "Merchant did not defend", POS,
   "Resolve and notify the customer", ["default", "stage:Resolution"],
   "The chargeback stood. Funds are recovered and the credit becomes permanent."),
  ("Raise chargeback with the scheme", "Merchant defended the claim", NEU,
   "Handle merchant representment", [],
   "Representment received. Review their evidence before conceding anything."),
  ("Raise chargeback with the scheme", "Missed the scheme deadline", NEG,
   "Resolve and notify the customer", ["comment", "stage:Resolution"],
   "Out of time with the scheme. Consider a goodwill decision and record why the deadline "
   "was missed."),

  ("Handle merchant representment", "Customer evidence prevails", POS,
   "Resolve and notify the customer", ["default", "stage:Resolution"],
   "Escalated to pre-arbitration and won, or the merchant withdrew."),
  ("Handle merchant representment", "Merchant evidence prevails", NEG,
   "Resolve and notify the customer", ["comment", "stage:Resolution"],
   "The claim cannot be sustained. Reverse the provisional credit and explain clearly."),

  ("Resolve and notify the customer", "Resolved in customer's favour", POS,
   None, ["default", "close"],
   "Funds recovered, credit made permanent, customer notified."),
  ("Resolve and notify the customer", "Resolved against the customer", NEU,
   None, ["close", "comment"],
   "Claim not upheld. The customer has been told why and what they can do next."),
 ],
},

# ---------------------------------------------------------------------------- 2
{
 "name": "Payment Investigation - Transfer Trace", "rank": 19, "status": 2,
 "desc": "A transfer has not reached the beneficiary, arrived short, or went to the wrong "
         "account. Traces the payment through the correspondent chain, requests a recall where "
         "the funds are recoverable, and keeps the customer informed on a clock.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Payment Trace Pack", "fr": 2, "res": 240, "priority": 2,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Payments and Transfers")],
 "tasks": [
  (1, "Capture the payment details in dispute", "Log", QUEUE_, "Payments Investigations",
   2, 1, 1, 75, 2, True, True,
   "Get the value date, amount, currency, beneficiary name, IBAN and the reference the customer "
   "quoted. One wrong digit in the IBAN changes the whole investigation."),
  (2, "Confirm the payment left the bank correctly", "Validate", TEAM_, "Payments Investigations",
   4, 3, 2, 75, 2, True, True,
   "Pull the SWIFT message and the debit entry. Establish whether this is our error, the "
   "correspondent's, or the beneficiary bank's."),
  (3, "Raise a trace with the correspondent bank", "Fulfil", TEAM_, "Payments Investigations",
   72, 3, 48, 80, 2, True, False,
   "Send the trace request and diarise the chase. Correspondents rarely answer first time."),
  (4, "Request recall of the funds", "Fulfil", TEAM_, "Payments Investigations",
   120, 3, 96, 80, 3, True, False,
   "Ask the beneficiary bank to return the funds. Recall needs the beneficiary's consent unless "
   "the payment was clearly misdirected by us."),
  (5, "Correct the payment and reimburse the customer", "Fulfil", TEAM_, "Payments Investigations",
   24, 3, 8, 80, 3, True, False,
   "Where the bank is at fault, put the customer back where they should have been - principal, "
   "charges and any interest lost."),
  (6, "Confirm the outcome to the customer", "Confirm", QUEUE_, "Payments Investigations",
   8, 3, 4, 80, 2, True, True,
   "Explain what happened, what was recovered and what the customer needs to do, in plain "
   "language and in writing."),
 ],
 "graph": [
  ("Capture the payment details in dispute", "Details captured", POS,
   "Confirm the payment left the bank correctly", ["default", "advance"],
   "Enough detail to identify the payment uniquely in the payment system."),
  ("Capture the payment details in dispute", "Payment already credited", END,
   None, ["close", "comment"],
   "The funds are with the beneficiary and the customer simply had not seen it. Close with "
   "the value date."),

  ("Confirm the payment left the bank correctly", "Sent correctly - trace needed", NEU,
   "Raise a trace with the correspondent bank", ["default", "advance"],
   "We processed the payment as instructed. It has stalled somewhere down the chain."),
  ("Confirm the payment left the bank correctly", "Bank error - wrong details applied", NEG,
   "Request recall of the funds", ["comment", "stage:Fulfil"],
   "We mis-keyed or mis-routed the payment. Recall immediately and prepare to reimburse."),
  ("Confirm the payment left the bank correctly", "Customer gave wrong beneficiary details", NEU,
   "Request recall of the funds", ["comment", "stage:Fulfil"],
   "The instruction was followed exactly. Recall is possible but depends on the beneficiary "
   "agreeing to return the funds."),

  ("Raise a trace with the correspondent bank", "Funds located and credited", POS,
   "Confirm the outcome to the customer", ["default", "stage:Confirm"],
   "The correspondent applied the credit. Get the value date corrected if it was late."),
  ("Raise a trace with the correspondent bank", "Funds returned to us", POS,
   "Correct the payment and reimburse the customer", [],
   "The payment came back unapplied. Re-credit the customer and re-send if they still want it."),
  ("Raise a trace with the correspondent bank", "No response - escalate", NEG,
   "Request recall of the funds", ["comment"],
   "The correspondent has not answered within the agreed window. Escalate through the "
   "relationship channel."),

  ("Request recall of the funds", "Funds recovered", POS,
   "Correct the payment and reimburse the customer", ["default"],
   "The beneficiary bank returned the funds."),
  ("Request recall of the funds", "Beneficiary refused to return funds", NEG,
   "Confirm the outcome to the customer", ["comment", "stage:Confirm"],
   "Recall declined. Tell the customer honestly and explain their legal options."),

  ("Correct the payment and reimburse the customer", "Customer made whole", POS,
   "Confirm the outcome to the customer", ["default", "advance"],
   "Principal, charges and lost interest all restored."),

  ("Confirm the outcome to the customer", "Investigation closed", POS,
   None, ["default", "close"],
   "Customer informed in writing and the case is complete."),
  ("Confirm the outcome to the customer", "Customer disputes the outcome", NEG,
   None, ["close", "comment"],
   "The customer is not satisfied. Raise a complaint case and hand it to Complaints Management."),
 ],
},
]

TEMPLATES += [

# ---------------------------------------------------------------------------- 3
{
 "name": "Fraud - Unauthorised Transaction", "rank": 14, "status": 2,
 "desc": "The customer says they did not make the transaction. Blocks the card inside the hour, "
         "screens the account for further exposure, decides liability against the authentication "
         "evidence, and reimburses where the customer is not at fault.",
 "bpf": "dispute", "startstage": "Capture", "sla": "Fraud Dispute 1-Hour Response",
 "package": "Fraud Dispute Pack", "fr": 1, "res": 240, "priority": 1,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Fraud and Security"),
   (2, 2, "subjectid", "Subject", 1, "", "Unauthorised Transaction"),
 ],
 "tasks": [
  (1, "Block the card and secure the account", "Capture", QUEUE_, "Fraud Investigations",
   1, 1, 1, 60, 3, True, True,
   "Block the card, stop any pending transactions and lock digital access. Containment first - "
   "the investigation can wait an hour, further losses cannot."),
  (2, "Take the customer's fraud statement", "Capture", QUEUE_, "Fraud Investigations",
   4, 3, 2, 75, 2, True, True,
   "Record exactly what the customer knows: last genuine use, whether the card is in their "
   "possession, and whether they shared an OTP or clicked a link."),
  (3, "Screen the account for further exposure", "Verify", TEAM_, "Fraud Operations",
   4, 3, 2, 75, 3, True, True,
   "Look for related attempts on other cards, changed contact details, new beneficiaries and "
   "device enrolments. Fraud rarely arrives alone."),
  (4, "Post provisional credit under regulation", "Provisional Credit", TEAM_, "Fraud Operations",
   24, 3, 12, 80, 3, False, True,
   "Where the customer is not liable on the face of it, credit them while the investigation "
   "runs. Waiting for certainty before crediting is what customers complain about."),
  (5, "Determine liability from the evidence", "Investigate", TEAM_, "Fraud Operations",
   120, 3, 72, 80, 2, True, True,
   "Weigh the authentication evidence, the device history and the customer's statement against "
   "the gross negligence test. Document the reasoning, not just the conclusion."),
  (6, "Reissue the card and restore access", "Resolution", TEAM_, "Card Operations",
   72, 3, 48, 80, 2, False, True,
   "Issue the replacement card, re-register the device and confirm the delivery address."),
  (7, "Close and notify the customer", "Resolution", QUEUE_, "Fraud Investigations",
   24, 3, 8, 80, 2, True, True,
   "Confirm the liability decision, the amount refunded and the security advice, in writing."),
 ],
 "graph": [
  ("Block the card and secure the account", "Card blocked and account secured", POS,
   "Take the customer's fraud statement", ["default"],
   "Exposure is contained. Now capture the detail."),
  ("Block the card and secure the account", "Customer found the card - no fraud", END,
   None, ["close", "comment"],
   "False alarm. Unblock the card and close with the reason recorded."),

  ("Take the customer's fraud statement", "Statement taken", POS,
   "Screen the account for further exposure", ["default", "advance"],
   "The customer's account of events is on file."),
  ("Take the customer's fraud statement", "Customer shared credentials or OTP", NEU,
   "Screen the account for further exposure", ["comment", "advance"],
   "Authorised push payment or social engineering. Liability is more finely balanced - flag it "
   "for the analyst."),

  ("Screen the account for further exposure", "No further exposure", POS,
   "Post provisional credit under regulation", ["default", "advance"],
   "Contained to the reported transactions."),
  ("Screen the account for further exposure", "Wider compromise found", NEG,
   "Post provisional credit under regulation", ["comment", "advance"],
   "Other products or channels are affected. Widen the block and tell the customer immediately."),

  ("Post provisional credit under regulation", "Provisional credit posted", POS,
   "Determine liability from the evidence", ["default", "advance"],
   "Customer is whole while the investigation runs."),
  ("Post provisional credit under regulation", "Withheld pending investigation", NEU,
   "Determine liability from the evidence", ["comment", "advance"],
   "The evidence already points to customer liability. Record why credit was withheld - this "
   "decision gets challenged."),

  ("Determine liability from the evidence", "Bank bears the loss", POS,
   "Reissue the card and restore access", ["default", "stage:Resolution"],
   "The customer is not liable. Make the credit permanent."),
  ("Determine liability from the evidence", "Customer liable - gross negligence", NEG,
   "Close and notify the customer", ["comment", "stage:Resolution"],
   "The evidence meets the gross negligence test. Reverse any provisional credit and explain "
   "the appeal route."),
  ("Determine liability from the evidence", "Merchant chargeback route", NEU,
   "Reissue the card and restore access", ["comment", "stage:Resolution"],
   "Recoverable from the merchant instead. Hand the recovery to Card Operations."),

  ("Reissue the card and restore access", "Card reissued", POS,
   "Close and notify the customer", ["default"],
   "New card despatched and digital access restored."),

  ("Close and notify the customer", "Case closed", POS,
   None, ["default", "close"],
   "Decision communicated and the customer knows how to appeal."),
 ],
},

# ---------------------------------------------------------------------------- 4
{
 "name": "Card Replacement - Lost or Stolen", "rank": 16, "status": 2,
 "desc": "A card has been lost or stolen. Blocks it immediately, checks for transactions after "
         "the loss, and gets a replacement into the customer's hands with the right delivery "
         "and PIN arrangements.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Card Replacement Pack", "fr": 1, "res": 96, "priority": 1,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Lost or Stolen Card")],
 "tasks": [
  (1, "Block the card immediately", "Log", QUEUE_, "Card Services",
   1, 1, 1, 60, 3, True, True,
   "Block on first contact, before anything else is discussed. Confirm the block reference "
   "back to the customer."),
  (2, "Review transactions since the reported loss", "Validate", TEAM_, "Card Operations",
   4, 3, 2, 75, 2, True, True,
   "Check for anything after the time the customer last had the card. Any hit becomes a fraud "
   "case in its own right."),
  (3, "Order the replacement card", "Fulfil", TEAM_, "Card Operations",
   24, 3, 8, 80, 2, True, True,
   "Order the replacement, confirm the embossing name and the delivery address, and set the "
   "PIN delivery method."),
  (4, "Reinstate standing payments on the new card", "Fulfil", TEAM_, "Card Operations",
   48, 3, 24, 80, 2, False, False,
   "Move recurring merchant subscriptions and standing authorisations onto the new card number "
   "so nothing silently fails."),
  (5, "Confirm delivery and activation", "Confirm", QUEUE_, "Card Services",
   96, 3, 72, 85, 2, True, True,
   "Confirm the card arrived and was activated. An undelivered card is a security incident, "
   "not a service delay."),
 ],
 "graph": [
  ("Block the card immediately", "Card blocked", POS,
   "Review transactions since the reported loss", ["default", "advance"],
   "Block confirmed and reference given to the customer."),
  ("Block the card immediately", "Card found before blocking", END,
   None, ["close", "comment"],
   "The customer located the card. No block applied and no replacement needed."),

  ("Review transactions since the reported loss", "No suspicious transactions", POS,
   "Order the replacement card", ["default", "advance"],
   "Nothing after the reported time of loss."),
  ("Review transactions since the reported loss", "Suspicious transactions found", NEG,
   "Order the replacement card", ["comment", "advance"],
   "Raise a fraud case for the transactions and continue the replacement in parallel."),

  ("Order the replacement card", "Card ordered", POS,
   "Reinstate standing payments on the new card", ["default"],
   "Replacement in production with the delivery address confirmed."),
  ("Order the replacement card", "Customer declined replacement", END,
   None, ["close", "comment"],
   "The customer does not want a new card. Close the product and confirm in writing."),

  ("Reinstate standing payments on the new card", "Standing payments moved", POS,
   "Confirm delivery and activation", ["default", "advance"],
   "Recurring authorisations re-pointed to the new card."),
  ("Reinstate standing payments on the new card", "No standing payments", NEU,
   "Confirm delivery and activation", ["advance"],
   "Nothing recurring on the old card."),

  ("Confirm delivery and activation", "Card delivered and active", POS,
   None, ["default", "close"],
   "Customer has the card and has used it."),
  ("Confirm delivery and activation", "Card not received", NEG,
   "Order the replacement card", ["comment", "stage:Fulfil"],
   "The card never arrived. Block the undelivered card and reissue - treat this as a "
   "security event."),
 ],
},

# ---------------------------------------------------------------------------- 5
{
 "name": "Retail Complaint - Service Quality", "rank": 11, "status": 2,
 "desc": "A customer is unhappy with how the bank handled something. Acknowledges within the "
         "regulatory window, investigates the root cause rather than the symptom, agrees redress "
         "where the bank got it wrong, and sends a final response the customer can act on.",
 "bpf": "complaint", "startstage": "Acknowledge", "sla": "Standard 24-Hour Response",
 "package": "Complaint Redress Pack", "fr": 4, "res": 240, "priority": 2,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Complaints")],
 "tasks": [
  (1, "Acknowledge the complaint to the customer", "Acknowledge", QUEUE_, "Complaints and Redress",
   4, 1, 2, 75, 3, True, True,
   "Send the acknowledgement with the case reference and the expected timeline. The clock the "
   "regulator measures starts here."),
  (2, "Capture the complaint statement and evidence", "Acknowledge", QUEUE_, "Complaints and Redress",
   24, 3, 12, 75, 2, True, True,
   "Get the customer's account in their own words, plus what they want as a resolution. Ask "
   "the second question - most complaints are cheaper to resolve than to argue."),
  (3, "Investigate the root cause", "Investigate", TEAM_, "Complaints Management",
   96, 3, 72, 80, 2, True, True,
   "Pull the call recordings, the system trail and the staff account. Establish what actually "
   "happened before deciding whether the bank was at fault."),
  (4, "Agree redress and approval", "Redress", MGR_, None,
   48, 3, 24, 80, 2, True, False,
   "Where the bank was at fault, decide the remedy: fee reversal, interest correction, goodwill "
   "or an apology, and get it approved within delegated authority."),
  (5, "Issue the final response", "Closure", TEAM_, "Complaints Management",
   48, 3, 24, 85, 3, True, True,
   "Send the final response setting out the findings, the remedy and the customer's right to "
   "escalate to the central bank."),
 ],
 "graph": [
  ("Acknowledge the complaint to the customer", "Acknowledged", POS,
   "Capture the complaint statement and evidence", ["default"],
   "Acknowledgement sent within the regulatory window."),

  ("Capture the complaint statement and evidence", "Statement captured", POS,
   "Investigate the root cause", ["default", "advance"],
   "We know what happened, and what the customer wants."),
  ("Capture the complaint statement and evidence", "Resolved on the call", END,
   None, ["close", "comment"],
   "Fixed there and then and the customer is happy. Record what was done."),

  ("Investigate the root cause", "Bank at fault", NEG,
   "Agree redress and approval", ["default"],
   "The bank made an error or fell below its service standard."),
  ("Investigate the root cause", "Bank acted correctly", NEU,
   "Issue the final response", ["comment", "stage:Closure"],
   "The bank followed policy. Explain the position clearly rather than defensively."),
  ("Investigate the root cause", "Partially upheld", NEU,
   "Agree redress and approval", ["comment"],
   "Some elements stand, others do not. Be specific about which."),

  ("Agree redress and approval", "Redress approved", POS,
   "Issue the final response", ["default", "advance"],
   "Remedy agreed and authorised."),
  ("Agree redress and approval", "Above delegated authority", NEG,
   "Issue the final response", ["comment", "advance"],
   "Escalate for senior approval before committing to the customer."),

  ("Issue the final response", "Customer accepted", POS,
   None, ["default", "close"],
   "Final response sent and accepted."),
  ("Issue the final response", "Customer escalating to the regulator", NEG,
   None, ["close", "comment"],
   "The customer is taking it to the central bank. Hand the file to Quality and Regulatory "
   "complete and unedited."),
 ],
},

# ---------------------------------------------------------------------------- 6
{
 "name": "Regulatory Complaint - Central Bank Referral", "rank": 6, "status": 2,
 "desc": "A complaint that arrived from, or is heading to, the central bank. Runs to the "
         "regulator's deadlines rather than the bank's, builds a defensible chronology, and puts "
         "a second pair of eyes on the response before it leaves the building.",
 "bpf": "complaint", "startstage": "Acknowledge", "sla": "Premier 4-Hour Response",
 "package": "Regulatory Referral Pack", "fr": 2, "res": 120, "priority": 1,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Complaints"),
   (2, 2, "subjectid", "Subject", 1, "", "Regulatory Complaint"),
 ],
 "tasks": [
  (1, "Log the referral and confirm the deadline", "Acknowledge", QUEUE_, "Regulatory Referrals",
   2, 1, 1, 60, 3, True, True,
   "Record the regulator's reference and the response deadline. Every downstream date works "
   "backwards from it."),
  (2, "Build the case chronology", "Investigate", TEAM_, "Quality and Regulatory",
   48, 3, 24, 75, 3, True, True,
   "Assemble a dated, sourced chronology from the systems of record. No gaps and no "
   "interpretation - the facts alone."),
  (3, "Review the original handling", "Investigate", TEAM_, "Quality and Regulatory",
   72, 3, 48, 80, 2, True, True,
   "Assess what the bank did against policy and the regulation. Say so plainly where it fell "
   "short."),
  (4, "Agree the bank's position and remedy", "Redress", MGR_, None,
   48, 3, 24, 80, 3, True, True,
   "Decide the position, the remedy and the tone. This response is on the record with the "
   "regulator."),
  (5, "Submit the response to the regulator", "Closure", TEAM_, "Quality and Regulatory",
   48, 3, 24, 85, 3, True, True,
   "Submit before the deadline with the full evidence bundle, and copy the customer."),
 ],
 "graph": [
  ("Log the referral and confirm the deadline", "Referral logged", POS,
   "Build the case chronology", ["default", "advance"],
   "Regulator reference and deadline recorded."),

  ("Build the case chronology", "Chronology complete", POS,
   "Review the original handling", ["default"],
   "Dated and sourced end to end."),
  ("Build the case chronology", "Records incomplete", NEG,
   "Review the original handling", ["comment"],
   "Gaps in the record. Say so in the response rather than papering over it."),

  ("Review the original handling", "Handling was compliant", NEU,
   "Agree the bank's position and remedy", ["default", "advance"],
   "The bank followed policy and the regulation."),
  ("Review the original handling", "Handling fell short", NEG,
   "Agree the bank's position and remedy", ["comment", "advance"],
   "The bank got it wrong. Concede early - it costs less than being found out."),

  ("Agree the bank's position and remedy", "Position agreed", POS,
   "Submit the response to the regulator", ["default", "advance"],
   "Approved at the right level and ready to submit."),

  ("Submit the response to the regulator", "Submitted and accepted", POS,
   None, ["default", "close"],
   "Response filed within the deadline and the regulator has closed the referral."),
  ("Submit the response to the regulator", "Regulator requires more", NEG,
   "Build the case chronology", ["comment", "stage:Investigate"],
   "Further information requested. Reopen the chronology and answer precisely what was asked."),
 ],
},
]

TEMPLATES += [

# ---------------------------------------------------------------------------- 7
{
 "name": "Credit Card Application", "rank": 21, "status": 2,
 "desc": "A retail credit card application from receipt to card in hand. Verifies income, "
         "checks the bureau and the debt burden ratio against central bank limits, decides, and "
         "either issues or declines with a reason the customer can act on.",
 "bpf": "retail", "startstage": "Application", "sla": "Standard 24-Hour Response",
 "package": "Credit Card Application Pack", "fr": 8, "res": 168, "priority": 2,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Card Application"),
 ],
 "tasks": [
  (1, "Capture the application and product choice", "Application", QUEUE_, "Retail Lending Applications",
   8, 1, 4, 75, 2, True, True,
   "Record the card product, the requested limit and the customer's stated income. Confirm the "
   "customer understands the profit rate and the annual fee."),
  (2, "Collect income and identity documents", "Application", TEAM_, "Retail Lending Operations",
   48, 3, 24, 75, 2, True, True,
   "Chase the salary certificate, statements and Emirates ID. An application without a salary "
   "certificate cannot be scored."),
  (3, "Verify income and employment", "Assessment", TEAM_, "Retail Lending Operations",
   24, 3, 16, 80, 2, True, True,
   "Confirm the salary credit on the statements matches the certificate, and that the employer "
   "is on the approved list."),
  (4, "Run bureau check and debt burden ratio", "Assessment", TEAM_, "Retail Lending Operations",
   12, 3, 8, 80, 3, True, True,
   "Pull the bureau report and calculate the debt burden ratio including this facility. The "
   "central bank cap is not negotiable."),
  (5, "Credit decision and limit setting", "Decision", MGR_, None,
   24, 3, 16, 80, 2, True, True,
   "Approve at the requested limit, approve at a lower limit, or decline. Record the reason "
   "either way."),
  (6, "Issue the card and welcome the customer", "Fulfilment", TEAM_, "Card Operations",
   72, 3, 48, 85, 2, True, True,
   "Produce and despatch the card, set the PIN delivery, and send the welcome pack with the "
   "key facts document."),
 ],
 "graph": [
  ("Capture the application and product choice", "Application captured", POS,
   "Collect income and identity documents", ["default"],
   "Product, limit and income recorded."),
  ("Capture the application and product choice", "Customer withdrew", END,
   None, ["close", "comment"],
   "The customer no longer wants the card."),

  ("Collect income and identity documents", "Documents complete", POS,
   "Verify income and employment", ["default", "advance"],
   "Full pack on file and legible."),
  ("Collect income and identity documents", "Customer unresponsive", END,
   None, ["close", "comment"],
   "Two chases without response. Close and invite the customer to reapply."),

  ("Verify income and employment", "Income verified", POS,
   "Run bureau check and debt burden ratio", ["default"],
   "Salary credits reconcile to the certificate."),
  ("Verify income and employment", "Income does not reconcile", NEG,
   "Collect income and identity documents", ["comment", "stage:Application"],
   "The certificate and the statements disagree. Go back for a corrected certificate before "
   "scoring anything."),

  ("Run bureau check and debt burden ratio", "Within appetite", POS,
   "Credit decision and limit setting", ["default", "advance"],
   "Bureau clean and the debt burden ratio is inside the cap."),
  ("Run bureau check and debt burden ratio", "Debt burden ratio exceeded", NEG,
   "Credit decision and limit setting", ["comment", "advance"],
   "Over the cap at the requested limit. A lower limit may still work."),
  ("Run bureau check and debt burden ratio", "Adverse bureau history", NEG,
   "Credit decision and limit setting", ["comment", "advance"],
   "Defaults or returned cheques on the bureau. This is usually a decline."),

  ("Credit decision and limit setting", "Approved as requested", POS,
   "Issue the card and welcome the customer", ["default", "advance"],
   "Approved at the limit the customer asked for."),
  ("Credit decision and limit setting", "Approved at a lower limit", NEU,
   "Issue the card and welcome the customer", ["comment", "advance"],
   "Counter-offer. Get the customer's acceptance of the reduced limit before issuing."),
  ("Credit decision and limit setting", "Declined", END,
   None, ["close", "comment"],
   "Declined. Give the customer the principal reason and tell them when they can reapply."),

  ("Issue the card and welcome the customer", "Card issued", POS,
   None, ["default", "close"],
   "Card despatched and the welcome pack sent."),
 ],
},

# ---------------------------------------------------------------------------- 8
{
 "name": "Auto Loan Application", "rank": 22, "status": 2,
 "desc": "A vehicle finance application. Runs the usual affordability assessment alongside the "
         "things only auto lending needs - the dealer quotation, comprehensive insurance and "
         "registration of the bank's interest on the mulkiya before funds are released.",
 "bpf": "retail", "startstage": "Application", "sla": "Standard 24-Hour Response",
 "package": "Auto Loan Pack", "fr": 8, "res": 240, "priority": 2,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Lending"),
   (2, 2, "subjectid", "Subject", 1, "", "Auto Loan"),
 ],
 "tasks": [
  (1, "Capture the vehicle and finance request", "Application", QUEUE_, "Retail Lending Applications",
   8, 1, 4, 75, 2, True, True,
   "Record the vehicle, the dealer, the price, the down payment and the tenor requested. New "
   "and used vehicles carry different loan to value limits."),
  (2, "Collect income documents and the dealer quotation", "Application", TEAM_, "Retail Lending Operations",
   48, 3, 24, 75, 2, True, True,
   "Salary certificate, statements, Emirates ID and the proforma invoice from an approved "
   "dealer."),
  (3, "Assess affordability and loan to value", "Assessment", TEAM_, "Retail Lending Operations",
   24, 3, 16, 80, 2, True, True,
   "Score the debt burden ratio and check the advance against the vehicle's value and age."),
  (4, "Credit decision", "Decision", MGR_, None,
   24, 3, 16, 80, 2, True, True,
   "Approve, counter-offer on tenor or down payment, or decline."),
  (5, "Confirm insurance and register the bank's interest", "Fulfilment", TEAM_, "Loan Operations",
   96, 3, 72, 80, 3, True, True,
   "Comprehensive cover with the bank as loss payee, and the bank's interest noted on the "
   "registration. No disbursement before both are in place."),
  (6, "Disburse to the dealer and hand over", "Fulfilment", TEAM_, "Loan Operations",
   24, 3, 8, 85, 2, True, True,
   "Release funds to the dealer, book the loan and confirm the first instalment date to the "
   "customer."),
 ],
 "graph": [
  ("Capture the vehicle and finance request", "Request captured", POS,
   "Collect income documents and the dealer quotation", ["default"],
   "Vehicle, dealer and finance structure recorded."),
  ("Capture the vehicle and finance request", "Vehicle outside policy", END,
   None, ["close", "comment"],
   "Age, type or dealer falls outside the lending policy. Decline at source and explain why."),

  ("Collect income documents and the dealer quotation", "Pack complete", POS,
   "Assess affordability and loan to value", ["default", "advance"],
   "Income evidence and dealer quotation on file."),
  ("Collect income documents and the dealer quotation", "Customer unresponsive", END,
   None, ["close", "comment"],
   "No response to chases. Close the application."),

  ("Assess affordability and loan to value", "Within policy", POS,
   "Credit decision", ["default", "advance"],
   "Affordable and inside the loan to value limit."),
  ("Assess affordability and loan to value", "Loan to value too high", NEU,
   "Credit decision", ["comment", "advance"],
   "A larger down payment would bring it into policy. Put that to the customer."),
  ("Assess affordability and loan to value", "Not affordable", NEG,
   "Credit decision", ["comment", "advance"],
   "Debt burden ratio fails even at the longest tenor."),

  ("Credit decision", "Approved", POS,
   "Confirm insurance and register the bank's interest", ["default", "advance"],
   "Approved on the requested terms."),
  ("Credit decision", "Approved with conditions", NEU,
   "Confirm insurance and register the bank's interest", ["comment", "advance"],
   "Approved subject to a higher down payment or shorter tenor, accepted by the customer."),
  ("Credit decision", "Declined", END,
   None, ["close", "comment"],
   "Declined with the principal reason recorded."),

  ("Confirm insurance and register the bank's interest", "Security in place", POS,
   "Disburse to the dealer and hand over", ["default"],
   "Comprehensive cover noted and the bank's interest registered."),
  ("Confirm insurance and register the bank's interest", "Insurance not acceptable", NEG,
   "Confirm insurance and register the bank's interest", ["comment"],
   "Cover is third party only or the bank is not loss payee. Go back to the customer before "
   "releasing anything."),

  ("Disburse to the dealer and hand over", "Disbursed", POS,
   None, ["default", "close"],
   "Funds released, loan booked and the customer has the vehicle."),
 ],
},

# ---------------------------------------------------------------------------- 9
{
 "name": "Digital Banking Access Recovery", "rank": 26, "status": 2,
 "desc": "The customer cannot get into the mobile app or online banking. Establishes whether "
         "this is a locked credential, a lost device or a compromised account - because the "
         "third one is a fraud case wearing a service request's clothes.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Digital Access Verification Pack", "fr": 2, "res": 24, "priority": 2,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Digital Banking")],
 "tasks": [
  (1, "Capture the access failure and the error", "Log", QUEUE_, "Digital Banking Support",
   2, 1, 1, 75, 2, True, True,
   "Get the exact error, the device, the app version and when it last worked. 'It doesn't work' "
   "is not a diagnosis."),
  (2, "Verify the customer's identity", "Validate", TEAM_, "Digital Banking Support",
   4, 3, 2, 75, 3, True, True,
   "Full identity verification before touching credentials. This is exactly the call a fraudster "
   "makes."),
  (3, "Check the account for compromise indicators", "Validate", TEAM_, "Digital Banking Support",
   4, 3, 2, 75, 3, True, True,
   "Look for recent device enrolments, contact detail changes and new beneficiaries. A lockout "
   "is often the first visible symptom of a takeover."),
  (4, "Reset credentials and re-register the device", "Fulfil", TEAM_, "Digital Banking Support",
   8, 3, 4, 80, 2, True, True,
   "Reset the password, clear the device binding and walk the customer through re-registration "
   "while they are on the line."),
  (5, "Confirm access restored", "Confirm", QUEUE_, "Digital Banking Support",
   24, 3, 8, 85, 2, True, True,
   "Have the customer log in and confirm before closing. Do not close on the assumption it "
   "worked."),
 ],
 "graph": [
  ("Capture the access failure and the error", "Details captured", POS,
   "Verify the customer's identity", ["default", "advance"],
   "The specific failure and the device are known."),
  ("Capture the access failure and the error", "Known outage - no action needed", END,
   None, ["close", "comment"],
   "Platform incident already being handled. Tell the customer when service resumes."),

  ("Verify the customer's identity", "Identity verified", POS,
   "Check the account for compromise indicators", ["default"],
   "Full verification passed."),
  ("Verify the customer's identity", "Verification failed", NEG,
   None, ["comment"],
   "The caller could not be verified. Do not reset anything. Direct them to a branch with "
   "their Emirates ID."),

  ("Check the account for compromise indicators", "No compromise found", POS,
   "Reset credentials and re-register the device", ["default", "advance"],
   "Nothing suspicious. This is a genuine lockout."),
  ("Check the account for compromise indicators", "Account takeover suspected", NEG,
   None, ["comment"],
   "Freeze digital access, raise a fraud case and hand to Fraud Operations. Do not restore "
   "access on this call."),

  ("Reset credentials and re-register the device", "Credentials reset", POS,
   "Confirm access restored", ["default", "advance"],
   "Password reset and device re-bound with the customer on the line."),

  ("Confirm access restored", "Access confirmed working", POS,
   None, ["default", "close"],
   "Customer logged in successfully."),
  ("Confirm access restored", "Still failing - escalate to IT", NEG,
   "Reset credentials and re-register the device", ["comment", "stage:Fulfil"],
   "The reset did not fix it. Raise a technical incident with the digital channels team."),
 ],
},
]

TEMPLATES += [

# ---------------------------------------------------------------------------- 10
{
 "name": "KYC Refresh - Periodic Review", "rank": 27, "status": 2,
 "desc": "A periodic know-your-customer refresh on an existing relationship. Collects expiring "
         "documents, re-screens, re-rates the customer's risk, and restricts the account only "
         "when the customer has genuinely stopped engaging.",
 "bpf": "service", "startstage": "Log", "sla": "Onboarding 2-Day Response",
 "package": "KYC Refresh Pack", "fr": 24, "res": 720, "priority": 3,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Onboarding and KYC"),
   (2, 2, "subjectid", "Subject", 1, "", "KYC Refresh"),
 ],
 "tasks": [
  (1, "Identify what has expired or changed", "Log", TEAM_, "Onboarding Operations",
   24, 1, 12, 75, 2, True, True,
   "List the expired documents and the data points that need reconfirming. Only ask for what "
   "is actually missing - customers resent being asked for what the bank already holds."),
  (2, "Request the refreshed documents", "Validate", TEAM_, "Onboarding Operations",
   168, 3, 120, 80, 2, True, True,
   "Send the request with a clear deadline and the consequence of not responding. Chase twice "
   "before restricting anything."),
  (3, "Re-screen and re-rate the customer", "Fulfil", TEAM_, "Onboarding Operations",
   48, 3, 24, 80, 3, True, True,
   "Run sanctions, PEP and adverse media, then apply the risk rating model to the refreshed "
   "profile."),
  (4, "Restrict the account pending refresh", "Fulfil", TEAM_, "Onboarding Operations",
   24, 3, 8, 80, 3, True, False,
   "Apply the debit restriction and tell the customer exactly what will lift it. Restriction "
   "is a lever to get engagement, not a punishment."),
  (5, "Complete the refresh and confirm", "Confirm", TEAM_, "Onboarding Operations",
   24, 3, 12, 85, 2, True, True,
   "Update the record, lift any restriction and confirm the next review date to the customer."),
 ],
 "graph": [
  ("Identify what has expired or changed", "Refresh needed", POS,
   "Request the refreshed documents", ["default", "advance"],
   "Specific gaps identified."),
  ("Identify what has expired or changed", "Record already current", END,
   None, ["close", "comment"],
   "Nothing has expired. Reset the review date and close without contacting the customer."),

  ("Request the refreshed documents", "Documents received", POS,
   "Re-screen and re-rate the customer", ["default", "advance"],
   "Full refreshed pack on file."),
  ("Request the refreshed documents", "No response after two chases", NEG,
   "Restrict the account pending refresh", ["comment", "advance"],
   "The customer has not engaged. Restriction is now the only remaining lever."),

  ("Re-screen and re-rate the customer", "Screening clear", POS,
   "Complete the refresh and confirm", ["default", "advance"],
   "No hits and the rating is unchanged or improved."),
  ("Re-screen and re-rate the customer", "Risk rating increased", NEU,
   "Complete the refresh and confirm", ["comment", "advance"],
   "Higher risk band. Apply enhanced due diligence and shorten the next review cycle."),
  ("Re-screen and re-rate the customer", "Screening hit - escalate", NEG,
   None, ["comment"],
   "Sanctions or adverse media hit. Refer to financial crime for disposition before doing "
   "anything else."),

  ("Restrict the account pending refresh", "Customer responded after restriction", POS,
   "Re-screen and re-rate the customer", ["default", "stage:Fulfil"],
   "The restriction produced the documents. Lift it as soon as screening is clear."),
  ("Restrict the account pending refresh", "Still no response - exit review", NEG,
   None, ["close", "comment"],
   "Refer for relationship exit. Record the full chase history."),

  ("Complete the refresh and confirm", "Refresh complete", POS,
   None, ["default", "close"],
   "Record updated, restriction lifted, next review diarised."),
 ],
},

# ---------------------------------------------------------------------------- 11
{
 "name": "Collections - Early Arrears", "rank": 13, "status": 2,
 "desc": "An account has fallen behind in the first sixty days. Makes contact early, "
         "understands whether this is an oversight or genuine hardship, and agrees an "
         "arrangement the customer can actually keep.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Collections Arrangement Pack", "fr": 8, "res": 336, "priority": 2,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Arrears and Repayment Plan")],
 "tasks": [
  (1, "Review the arrears position", "Log", TEAM_, "Collections and Recoveries",
   8, 1, 4, 75, 2, True, True,
   "Establish how much is overdue, for how long, and whether this is the first time. A first "
   "missed payment and a fourth are different conversations."),
  (2, "Make contact with the customer", "Validate", QUEUE_, "Collections - Early Arrears",
   48, 3, 24, 80, 2, True, True,
   "Reach the customer and ask what changed. Most early arrears are an oversight or a salary "
   "timing issue, not an inability to pay."),
  (3, "Assess affordability and hardship", "Fulfil", TEAM_, "Collections and Recoveries",
   72, 3, 48, 80, 2, True, False,
   "Complete the income and expenditure review. Do not agree an instalment the customer has "
   "no realistic prospect of paying."),
  (4, "Agree and document the arrangement", "Fulfil", TEAM_, "Collections and Recoveries",
   96, 3, 72, 80, 3, True, False,
   "Put the arrangement in writing with the amounts and dates, and confirm the effect on the "
   "customer's bureau record."),
  (5, "Monitor the first two instalments", "Confirm", TEAM_, "Collections and Recoveries",
   336, 3, 240, 85, 2, False, True,
   "Watch the first two payments land. A broken arrangement in month one needs a different "
   "conversation, quickly."),
 ],
 "graph": [
  ("Review the arrears position", "Arrears confirmed", POS,
   "Make contact with the customer", ["default", "advance"],
   "Amount and age of arrears established."),
  ("Review the arrears position", "Payment already received", END,
   None, ["close", "comment"],
   "Cleared before contact. Close and check why the alert fired late."),
  ("Review the arrears position", "Bank error caused the arrears", NEG,
   None, ["close", "comment"],
   "A failed direct debit or misposting on our side. Correct it, remove any fees and repair "
   "the bureau entry."),

  ("Make contact with the customer", "Customer will pay immediately", POS,
   "Monitor the first two instalments", ["default", "stage:Confirm"],
   "Oversight rather than hardship. Confirm the payment date and monitor."),
  ("Make contact with the customer", "Customer reports hardship", NEU,
   "Assess affordability and hardship", ["comment"],
   "Genuine change in circumstances. Move to a proper affordability assessment."),
  ("Make contact with the customer", "No contact made", NEG,
   "Assess affordability and hardship", ["comment"],
   "Unreachable across every channel. Escalate the contact strategy before the account ages "
   "further."),

  ("Assess affordability and hardship", "Arrangement is affordable", POS,
   "Agree and document the arrangement", ["default", "advance"],
   "The income and expenditure review supports a workable instalment."),
  ("Assess affordability and hardship", "Refer to restructuring", NEG,
   None, ["comment"],
   "Beyond an instalment plan. Refer for restructuring or settlement."),

  ("Agree and document the arrangement", "Arrangement signed", POS,
   "Monitor the first two instalments", ["default", "advance"],
   "Signed and loaded onto the account."),

  ("Monitor the first two instalments", "Arrangement holding", POS,
   None, ["default", "close"],
   "Payments landing as agreed. Close and let normal monitoring take over."),
  ("Monitor the first two instalments", "Arrangement broken", NEG,
   "Make contact with the customer", ["comment", "stage:Validate"],
   "The plan failed at the first hurdle. Re-contact before the account rolls into late "
   "collections."),
 ],
},

# ---------------------------------------------------------------------------- 12
{
 "name": "Account Servicing - Customer Details Update", "rank": 31, "status": 2,
 "desc": "A change to the customer's address, phone or email. Small, high volume, and a "
         "favourite fraud vector - so it verifies identity properly and notifies the old contact "
         "details as well as the new ones.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Customer Details Update Pack", "fr": 8, "res": 72, "priority": 3,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Accounts and Servicing"),
   (2, 2, "subjectid", "Subject", 1, "", "Address and Contact Update"),
 ],
 "tasks": [
  (1, "Capture the requested change", "Log", QUEUE_, "Retail Contact Centre",
   8, 1, 4, 75, 2, True, True,
   "Record exactly which details change and from what. Keep the old values - they are the "
   "control for the notification step."),
  (2, "Verify identity and supporting proof", "Validate", TEAM_, "Branch Operations",
   24, 3, 12, 80, 3, True, True,
   "Verify the customer and check the proof of address. Contact detail changes are the first "
   "move in most account takeovers."),
  (3, "Apply the update across the systems", "Fulfil", TEAM_, "Branch Operations",
   24, 3, 8, 80, 2, True, True,
   "Update the core record and confirm it propagated to cards, statements and digital "
   "channels. A half-updated address sends statements to the wrong place."),
  (4, "Notify the customer on old and new details", "Confirm", QUEUE_, "Retail Contact Centre",
   8, 3, 4, 85, 2, True, True,
   "Send confirmation to both the old and the new contact details. If the change was not "
   "genuine, this is how the customer finds out."),
 ],
 "graph": [
  ("Capture the requested change", "Change captured", POS,
   "Verify identity and supporting proof", ["default", "advance"],
   "Old and new values recorded."),

  ("Verify identity and supporting proof", "Verified", POS,
   "Apply the update across the systems", ["default", "advance"],
   "Identity confirmed and the proof of address is acceptable."),
  ("Verify identity and supporting proof", "Proof of address not acceptable", NEU,
   "Capture the requested change", ["comment", "stage:Log"],
   "Document is out of date or not in the customer's name. Go back for a valid one."),
  ("Verify identity and supporting proof", "Possible impersonation", NEG,
   None, ["comment"],
   "Do not apply the change. Raise a fraud case and contact the customer on the details "
   "already on file."),

  ("Apply the update across the systems", "Update applied", POS,
   "Notify the customer on old and new details", ["default", "advance"],
   "Core record updated and downstream systems confirmed."),

  ("Notify the customer on old and new details", "Confirmed", POS,
   None, ["default", "close"],
   "Both notifications sent and no objection raised."),
  ("Notify the customer on old and new details", "Customer denies the change", NEG,
   None, ["close", "comment"],
   "The old contact details reported they did not request this. Reverse immediately and raise "
   "a fraud case."),
 ],
},

# ---------------------------------------------------------------------------- 13
{
 "name": "Account Closure Request", "rank": 32, "status": 2,
 "desc": "The customer wants to close an account. Establishes why - because a closure driven by "
         "dissatisfaction is a retention conversation, not a form - then clears liabilities, "
         "recovers cards and settles the final balance.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Account Closure Pack", "fr": 8, "res": 168, "priority": 3,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Accounts and Servicing"),
   (2, 2, "subjectid", "Subject", 1, "", "Account Closure"),
 ],
 "tasks": [
  (1, "Capture the closure request and reason", "Log", QUEUE_, "Retail Contact Centre",
   8, 1, 4, 75, 2, True, True,
   "Record which accounts and, more importantly, why. A closure driven by a bad experience is "
   "a complaint that has not been logged yet."),
  (2, "Offer retention where appropriate", "Validate", TEAM_, "Premier Banking",
   24, 3, 12, 80, 2, False, False,
   "Where the reason is fixable - a fee, a rate, a service failure - make one genuine offer. "
   "Do not obstruct a customer who has decided."),
  (3, "Check liabilities and standing instructions", "Validate", TEAM_, "Branch Operations",
   48, 3, 24, 80, 3, True, True,
   "Identify outstanding loans, cards, standing instructions and direct debits. Closing an "
   "account with a live salary transfer causes real harm."),
  (4, "Settle the balance and recover cards", "Fulfil", TEAM_, "Branch Operations",
   72, 3, 48, 80, 2, True, True,
   "Clear the final balance, recover cards and cheque books, and issue the clearance letter."),
  (5, "Close the account and confirm", "Confirm", TEAM_, "Branch Operations",
   24, 3, 12, 85, 2, True, True,
   "Close the account, issue the closure confirmation and confirm the customer's remaining "
   "relationship, if any."),
 ],
 "graph": [
  ("Capture the closure request and reason", "Closure requested", POS,
   "Offer retention where appropriate", ["default", "advance"],
   "Accounts and reason recorded."),
  ("Capture the closure request and reason", "Closing due to a service failure", NEG,
   "Offer retention where appropriate", ["comment", "advance"],
   "Raise a complaint case alongside this one. The bank should understand why it is losing "
   "the customer."),

  ("Offer retention where appropriate", "Customer stays", END,
   None, ["close", "comment"],
   "Retained. Record what changed their mind - it is useful."),
  ("Offer retention where appropriate", "Customer proceeds with closure", NEU,
   "Check liabilities and standing instructions", ["default", "advance"],
   "The decision stands. Make the closure clean and quick."),

  ("Check liabilities and standing instructions", "No blockers", POS,
   "Settle the balance and recover cards", ["default"],
   "Nothing outstanding and no live instructions."),
  ("Check liabilities and standing instructions", "Outstanding liability found", NEG,
   "Settle the balance and recover cards", ["comment"],
   "A loan or card balance must be cleared first. Tell the customer the amount and the route."),

  ("Settle the balance and recover cards", "Settled", POS,
   "Close the account and confirm", ["default", "advance"],
   "Balance cleared, cards recovered and clearance letter issued."),

  ("Close the account and confirm", "Account closed", POS,
   None, ["default", "close"],
   "Closed and confirmed in writing."),
 ],
},

# ---------------------------------------------------------------------------- 14
{
 "name": "Standing Instruction Setup", "rank": 33, "status": 2,
 "desc": "Setting up a recurring payment or standing instruction. Short, high volume, and worth "
         "getting right first time because a failed standing instruction usually surfaces as a "
         "complaint weeks later.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Standing Instruction Pack", "fr": 8, "res": 72, "priority": 3,
 "rules": [
   (1, 1, "subjectid", "Subject", 11, "", "Accounts and Servicing"),
   (2, 2, "subjectid", "Subject", 1, "", "Cheque Book and Standing Instructions"),
 ],
 "tasks": [
  (1, "Capture the instruction details", "Log", QUEUE_, "Retail Contact Centre",
   8, 1, 4, 75, 2, True, True,
   "Beneficiary, amount, frequency, start date and end condition. Confirm what should happen "
   "when there are insufficient funds."),
  (2, "Validate the beneficiary and mandate", "Validate", TEAM_, "Branch Operations",
   24, 3, 12, 80, 2, True, True,
   "Check the IBAN, confirm the beneficiary name matches and obtain the signed mandate."),
  (3, "Set up the instruction", "Fulfil", TEAM_, "Branch Operations",
   24, 3, 12, 80, 2, True, True,
   "Load the standing instruction and verify the first execution date is what the customer "
   "expects."),
  (4, "Confirm the first execution", "Confirm", QUEUE_, "Retail Contact Centre",
   72, 3, 48, 85, 2, True, True,
   "Confirm the first payment ran. This is where errors surface, not at setup."),
 ],
 "graph": [
  ("Capture the instruction details", "Details captured", POS,
   "Validate the beneficiary and mandate", ["default", "advance"],
   "All parameters recorded including the insufficient funds treatment."),

  ("Validate the beneficiary and mandate", "Validated", POS,
   "Set up the instruction", ["default", "advance"],
   "IBAN and beneficiary confirmed and the mandate is signed."),
  ("Validate the beneficiary and mandate", "Beneficiary details incorrect", NEG,
   "Capture the instruction details", ["comment", "stage:Log"],
   "IBAN fails validation or the name does not match. Go back before anything is loaded."),

  ("Set up the instruction", "Instruction active", POS,
   "Confirm the first execution", ["default", "advance"],
   "Loaded with the correct first execution date."),

  ("Confirm the first execution", "First payment successful", POS,
   None, ["default", "close"],
   "Ran as expected. Close."),
  ("Confirm the first execution", "First payment failed", NEG,
   "Set up the instruction", ["comment", "stage:Fulfil"],
   "Failed on insufficient funds or a rejected beneficiary. Fix it and tell the customer "
   "before they find out from the beneficiary."),
 ],
},

# ---------------------------------------------------------------------------- 15
{
 "name": "Fee Reversal Review", "rank": 34, "status": 2,
 "desc": "The customer is challenging a fee or charge. Checks whether the fee was applied "
         "correctly, and where it was, decides whether to waive it anyway - because the cost of "
         "the fee is almost always less than the cost of the argument.",
 "bpf": "service", "startstage": "Log", "sla": "Standard 24-Hour Response",
 "package": "Fee Review Pack", "fr": 4, "res": 72, "priority": 3,
 "rules": [(1, 1, "subjectid", "Subject", 11, "", "Fees and Charges")],
 "tasks": [
  (1, "Identify the charge being disputed", "Log", QUEUE_, "Retail Contact Centre",
   4, 1, 2, 75, 2, True, True,
   "Pin down the exact charge, date and amount from the statement. 'Some fees' is not "
   "actionable."),
  (2, "Check the charge against the fee schedule", "Validate", TEAM_, "Contact Centre Tier 1",
   8, 3, 4, 80, 2, True, True,
   "Confirm whether the fee was correctly applied under the published schedule and the "
   "customer's product terms."),
  (3, "Decide the waiver", "Fulfil", MGR_, None,
   24, 3, 12, 80, 2, True, False,
   "Where the fee was correct but the customer has a reasonable case or a good history, "
   "consider a goodwill waiver within the delegated limit."),
  (4, "Reverse the charge and confirm", "Confirm", TEAM_, "Contact Centre Tier 1",
   24, 3, 8, 85, 2, True, False,
   "Post the reversal, confirm the value date and explain how to avoid the charge in future."),
 ],
 "graph": [
  ("Identify the charge being disputed", "Charge identified", POS,
   "Check the charge against the fee schedule", ["default", "advance"],
   "Exact charge located on the statement."),

  ("Check the charge against the fee schedule", "Charge applied in error", NEG,
   "Reverse the charge and confirm", ["default", "stage:Confirm"],
   "The bank charged something it should not have. Reverse it without further debate."),
  ("Check the charge against the fee schedule", "Charge correct - consider goodwill", NEU,
   "Decide the waiver", ["comment"],
   "Correctly applied, but the customer may still have a case worth honouring."),

  ("Decide the waiver", "Waiver approved", POS,
   "Reverse the charge and confirm", ["default", "advance"],
   "Goodwill waiver authorised."),
  ("Decide the waiver", "Waiver declined", NEU,
   None, ["close", "comment"],
   "The charge stands. Explain the terms clearly and tell the customer how to avoid it next "
   "time."),

  ("Reverse the charge and confirm", "Charge reversed", POS,
   None, ["default", "close"],
   "Reversal posted and the customer notified."),
 ],
},
]


# ---------------------------------------------------------------- existing template fix-ups
# Retail cases now carry a specific subject, so the two lending templates that used to match on
# broad subjects are re-pointed and re-ranked to sit ahead of the generic personal loan template.
RERANK = [
    ("Retail Mortgage Application", 23, "Mortgage"),
    ("Retail Card Limit Increase", 24, "Card Limit Increase"),
]


def upsert_template(t, ctx):
    """Same contract as step 19, with a retail fallback team on queue and team tasks."""
    bpf, stages = ctx["bpfs"][t["bpf"]]
    body = {
        f"{P}_name": t["name"], f"{P}_rank": t["rank"], f"{P}_publishstatus": t["status"],
        f"{P}_description": t["desc"], f"{P}_matchlogic": 3,
        f"{P}_bpfid": bpf["id"], f"{P}_bpfname": bpf["name"], f"{P}_bpfentityname": bpf["unique"],
        f"{P}_startstageid": stages[t["startstage"]], f"{P}_startstagename": t["startstage"],
        f"{P}_firstresponsehours": t["fr"], f"{P}_resolutionhours": t["res"],
        f"{P}_setcasepriority": t["priority"], f"{P}_effectivefrom": NOW,
        f"{P}_documentpackage@odata.bind": f"/{P}_documentpackages({ctx['pkgs'][t['package']]})",
    }
    if t["sla"] in ctx["slas"]:
        body[f"{P}_sla@odata.bind"] = f"/slas({ctx['slas'][t['sla']]})"

    ex = dv.find_one(f"{P}_caseprocesstemplates", f"{P}_name eq '{t['name']}'",
                     f"{P}_caseprocesstemplateid")
    if ex:
        tid = ex[f"{P}_caseprocesstemplateid"]
        dv.patch(f"{P}_caseprocesstemplates({tid})", body)
        print("  ~ template", t["name"])
    else:
        body[f"{P}_appliedcount"] = 0
        tid = dv.new_id(dv.post(f"{P}_caseprocesstemplates", body))
        print("  + template", t["name"])

    have = {r[f"{P}_name"] for r in dv.get(
        f"{P}_matchrules?$select={P}_name&$filter=_{P}_template_value eq {tid}")["value"]}
    for seq, grp, attr, lbl, op, val, vlbl in t["rules"]:
        rn = f"{t['name']} :: {lbl} {seq}"
        if rn in have:
            continue
        if attr == "subjectid" and not val:
            s = dv.find_one("subjects", f"title eq '{vlbl}'", "subjectid")
            if not s:
                print("    ! subject not found:", vlbl)
                continue
            val = s["subjectid"]
        dv.post(f"{P}_matchrules", {
            f"{P}_name": rn, f"{P}_sequence": seq, f"{P}_groupnumber": grp,
            f"{P}_attributename": attr, f"{P}_attributelabel": lbl,
            f"{P}_operator": op, f"{P}_value": val, f"{P}_valuelabel": vlbl,
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})"})

    have_tasks = {r[f"{P}_name"]: r[f"{P}_processtaskid"] for r in dv.get(
        f"{P}_processtasks?$select={P}_name,{P}_processtaskid"
        f"&$filter=_{P}_template_value eq {tid}")["value"]}
    fallback = ctx["teams"].get("Contact Centre Tier 1")
    prev = None
    for (seq, tname, stage, atype, assignee, due, slastart, slatarget,
         warn, breach, blocks, mand, instr) in t["tasks"]:
        if tname in have_tasks:
            prev = have_tasks[tname]
            continue
        b = {
            f"{P}_name": tname, f"{P}_sequence": seq, f"{P}_description": instr,
            f"{P}_stagename": stage, f"{P}_stageid": stages.get(stage, ""),
            f"{P}_assigntype": atype, f"{P}_duehours": due,
            f"{P}_slastartwhen": slastart, f"{P}_slatargethours": slatarget,
            f"{P}_slawarnpercent": warn, f"{P}_onbreach": breach,
            f"{P}_blocksstage": blocks, f"{P}_mandatory": mand,
            f"{P}_calendarname": CAL, f"{P}_pauseonwaiting": True,
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        if atype == TEAM_ and assignee in ctx["teams"]:
            b[f"{P}_team@odata.bind"] = f"/teams({ctx['teams'][assignee]})"
        elif atype == QUEUE_ and assignee in ctx["queues"]:
            b[f"{P}_queue@odata.bind"] = f"/queues({ctx['queues'][assignee]})"
        elif atype == ROLE_ and assignee:
            b[f"{P}_rolename"] = assignee
        if fallback and atype in (TEAM_, QUEUE_):
            b[f"{P}_fallbackteam@odata.bind"] = f"/teams({fallback})"
        if prev:
            b[f"{P}_predecessor@odata.bind"] = f"/{P}_processtasks({prev})"
        prev = dv.new_id(dv.post(f"{P}_processtasks", b))
    return tid


def fix_existing():
    for name, rank, subject in RERANK:
        ex = dv.find_one(f"{P}_caseprocesstemplates", f"{P}_name eq '{name}'",
                         f"{P}_caseprocesstemplateid")
        if not ex:
            continue
        tid = ex[f"{P}_caseprocesstemplateid"]
        dv.patch(f"{P}_caseprocesstemplates({tid})", {f"{P}_rank": rank})
        s = dv.find_one("subjects", f"title eq '{subject}'", "subjectid")
        if not s:
            continue
        for r in dv.get(f"{P}_matchrules?$select={P}_matchruleid,{P}_attributename"
                        f"&$filter=_{P}_template_value eq {tid}")["value"]:
            if r[f"{P}_attributename"] == "subjectid":
                dv.patch(f"{P}_matchrules({r[f'{P}_matchruleid']})",
                         {f"{P}_value": s["subjectid"], f"{P}_valuelabel": subject})
        print(f"  ~ {name}: rank {rank}, subject {subject}")

    # An earlier build seeded "Customer onboarding" twice; keep the first and retire the rest.
    dupes = dv.get(f"{P}_caseprocesstemplates?$select={P}_caseprocesstemplateid,{P}_name"
                   f"&$filter={P}_name eq 'Customer onboarding'")["value"]
    for d in dupes[1:]:
        dv.patch(f"{P}_caseprocesstemplates({d[f'{P}_caseprocesstemplateid']})",
                 {"statecode": 1, "statuscode": 2})
        print("  ~ retired duplicate 'Customer onboarding'")


def main():
    print("Case columns")
    ensure_columns()

    print("Business process flows")
    dis_id, dis_stages = bpfgen.upsert_bpf(
        "Retail Card Dispute", "cpc_retailcarddispute",
        "Card dispute lifecycle from capture through provisional credit to scheme resolution.",
        BPF_DISPUTE)
    cmp_id, cmp_stages = bpfgen.upsert_bpf(
        "Retail Complaint Handling", "cpc_retailcomplainthandling",
        "Regulated complaint handling from acknowledgement through investigation and redress.",
        BPF_COMPLAINT)
    svc_id, svc_stages = bpfgen.upsert_bpf(
        "Retail Service Fulfilment", "cpc_retailservicefulfilment",
        "Everyday retail service requests from logging through validation to confirmation.",
        BPF_SERVICE)
    ret = dv.find_one("workflows", "uniquename eq 'cpc_retaillendingjourney'", "workflowid")
    ret_id = ret["workflowid"]
    ret_stages = {r["stagename"]: r["processstageid"] for r in dv.get(
        f"processstages?$select=processstageid,stagename&$filter=_processid_value eq {ret_id}"
    )["value"]}

    ctx = {
        "teams": {t["name"]: t["teamid"] for t in
                  dv.get("teams?$select=teamid,name&$top=500")["value"]},
        "queues": {q["name"]: q["queueid"] for q in
                   dv.get("queues?$select=queueid,name&$top=500")["value"]},
        "slas": {s["name"]: s["slaid"] for s in dv.get("slas?$select=slaid,name")["value"]},
        "bpfs": {
            "dispute": ({"id": dis_id, "name": "Retail Card Dispute",
                         "unique": "cpc_retailcarddispute"}, dis_stages),
            "complaint": ({"id": cmp_id, "name": "Retail Complaint Handling",
                           "unique": "cpc_retailcomplainthandling"}, cmp_stages),
            "service": ({"id": svc_id, "name": "Retail Service Fulfilment",
                         "unique": "cpc_retailservicefulfilment"}, svc_stages),
            "retail": ({"id": ret_id, "name": "Retail Lending Journey",
                        "unique": "cpc_retaillendingjourney"}, ret_stages),
        },
    }

    print("Document packages")
    # Templates may reference packages seeded by earlier steps, so start from what is there.
    ctx["pkgs"] = {p[f"{P}_name"]: p[f"{P}_documentpackageid"] for p in dv.get(
        f"{P}_documentpackages?$select={P}_documentpackageid,{P}_name&$top=500")["value"]}
    for n, items in PACKAGES.items():
        ctx["pkgs"][n] = upsert_package(n, items, ctx["teams"])

    print("Templates")
    for t in TEMPLATES:
        tid = upsert_template(t, ctx)
        apply_graph(tid, t["graph"], ORDER[t["bpf"]])

    print("Existing template fix-ups")
    fix_existing()

    dv.publish_all()
    print("\nDone.")


if __name__ == "__main__":
    main()

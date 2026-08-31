"""Step 19: corporate and retail banking sample processes.

Adds two purpose built business process flows (a six stage corporate credit lifecycle and a
four stage retail lending journey), the operating teams behind them, the document packages
they demand, and six case process templates - the flagship being an end to end corporate
credit facility from origination through to ongoing covenant monitoring.

Safe to re-run: every write is an upsert keyed on name.
"""
import dv
import bpfgen

P = dv.PREFIX
NOW = "2026-08-31T06:00:00Z"
CAL = "UAE Sun-Thu 08:00-18:00"

POS, NEU, NEG, END = 1, 2, 3, 4          # outcome sentiment
TEAM_, USER_, ROLE_, QUEUE_, MGR_, OWNER_ = 1, 2, 3, 4, 5, 6   # task assign type

# ---------------------------------------------------------------- case category options
NEW_CATEGORIES = [
    (8, "Corporate Credit"),
    (9, "Retail Lending"),
    (10, "Trade Finance"),
    (11, "Credit Review"),
]

# ---------------------------------------------------------------- teams
NEW_TEAMS = [
    ("Credit Origination", "Relationship managers who originate and package credit proposals."),
    ("Credit Risk", "Credit analysts who underwrite, rate and stress test proposals."),
    ("Credit Committee", "Delegated approval authority for facilities above analyst limits."),
    ("Legal and Documentation", "Drafts facility agreements, security and legal opinions."),
    ("Loan Operations", "Sets up limits, perfects security and releases funds."),
    ("Portfolio Monitoring", "Tracks covenants, reviews and early warning indicators."),
    ("Retail Lending Operations", "Processes retail loan, card and mortgage applications."),
]

# ---------------------------------------------------------------- business process flows
BPF_CORPORATE = [
    ("Origination", "identify", [
        ("Borrower", "customerid", "lookup", True),
        ("Facility type", "cpc_casecategory", "picklist", False)]),
    ("Underwriting", "research", [
        ("Credit analyst", "ownerid", "lookup", True),
        ("Segment", "cpc_customersegment", "picklist", False)]),
    ("Credit Decision", "research", [
        ("Decision rationale", "description", "memo", False)]),
    ("Documentation", "research", [
        ("Target completion", "followupby", "datetime", False)]),
    ("Disbursement", "resolve", [
        ("Loan operations owner", "ownerid", "lookup", False)]),
    ("Monitoring", "resolve", [
        ("Next review date", "followupby", "datetime", False)]),
]

BPF_RETAIL = [
    ("Application", "identify", [
        ("Applicant", "customerid", "lookup", True),
        ("Product", "cpc_casecategory", "picklist", False)]),
    ("Assessment", "research", [
        ("Assessor", "ownerid", "lookup", False)]),
    ("Decision", "research", [
        ("Decision rationale", "description", "memo", False)]),
    ("Fulfilment", "resolve", [
        ("Completion date", "followupby", "datetime", False)]),
]

# ---------------------------------------------------------------- document packages
# (name, sequence, mandatory, responsible, due hours, template file, owning team)
PACKAGES = {
"Corporate Credit Application Pack": [
    ("Signed Facility Application", 1, True, 1, 24, "facility_application.docx", "Credit Origination"),
    ("Audited Financial Statements (3 years)", 2, True, 1, 72, "", "Credit Origination"),
    ("Interim Management Accounts", 3, True, 1, 72, "", "Credit Origination"),
    ("Trade Licence and Constitutional Documents", 4, True, 1, 48, "", "Credit Origination"),
    ("Board Resolution to Borrow", 5, True, 1, 72, "board_resolution.docx", "Legal and Documentation"),
    ("Group Structure and Ownership Chart", 6, True, 1, 72, "", "Credit Origination"),
    ("Bank Statements (12 months)", 7, True, 1, 72, "", "Credit Origination"),
    ("Aging of Receivables and Payables", 8, False, 1, 96, "", "Credit Risk"),
    ("Credit Bureau Report", 9, True, 3, 24, "", "Credit Risk"),
],
"Credit Security and Legal Pack": [
    ("Approved Credit Memorandum", 1, True, 3, 24, "credit_memo.docx", "Credit Risk"),
    ("Facility Agreement", 2, True, 3, 72, "facility_agreement.docx", "Legal and Documentation"),
    ("Security and Mortgage Documents", 3, True, 3, 96, "security_documents.docx", "Legal and Documentation"),
    ("Corporate or Personal Guarantee", 4, True, 1, 96, "guarantee.docx", "Legal and Documentation"),
    ("Insurance Assignment", 5, False, 1, 120, "", "Legal and Documentation"),
    ("External Legal Opinion", 6, False, 4, 120, "", "Legal and Documentation"),
    ("Disbursement Authorisation", 7, True, 3, 24, "disbursement_auth.docx", "Loan Operations"),
],
"Credit Monitoring Pack": [
    ("Covenant Compliance Certificate", 1, True, 1, 168, "covenant_certificate.docx", "Portfolio Monitoring"),
    ("Latest Management Accounts", 2, True, 1, 168, "", "Portfolio Monitoring"),
    ("Updated Collateral Valuation", 3, False, 4, 336, "", "Portfolio Monitoring"),
    ("Annual Review Memorandum", 4, True, 3, 168, "annual_review.docx", "Credit Risk"),
],
"Trade Finance LC Pack": [
    ("LC Application Form", 1, True, 1, 8, "lc_application.docx", "Credit Origination"),
    ("Underlying Sales Contract", 2, True, 1, 24, "", "Credit Origination"),
    ("Proforma Invoice", 3, True, 1, 24, "", "Credit Origination"),
    ("Sanctions Screening Result", 4, True, 3, 8, "", "Credit Risk"),
    ("Issued Letter of Credit", 5, True, 3, 48, "", "Loan Operations"),
],
"Retail Lending Pack": [
    ("Emirates ID and Passport Copy", 1, True, 1, 24, "", "Retail Lending Operations"),
    ("Salary Certificate", 2, True, 1, 48, "", "Retail Lending Operations"),
    ("Bank Statements (6 months)", 3, True, 1, 48, "", "Retail Lending Operations"),
    ("Liability Letter", 4, False, 1, 72, "", "Retail Lending Operations"),
    ("Credit Bureau Report", 5, True, 3, 12, "", "Retail Lending Operations"),
    ("Signed Loan Agreement", 6, True, 1, 96, "loan_agreement.docx", "Retail Lending Operations"),
],
"Mortgage Application Pack": [
    ("Emirates ID and Passport Copy", 1, True, 1, 24, "", "Retail Lending Operations"),
    ("Salary Certificate", 2, True, 1, 48, "", "Retail Lending Operations"),
    ("Bank Statements (6 months)", 3, True, 1, 48, "", "Retail Lending Operations"),
    ("Sale and Purchase Agreement", 4, True, 1, 72, "", "Retail Lending Operations"),
    ("Property Title Deed", 5, True, 1, 72, "", "Legal and Documentation"),
    ("Independent Property Valuation", 6, True, 4, 120, "", "Legal and Documentation"),
    ("Signed Mortgage Offer Letter", 7, True, 1, 168, "mortgage_offer.docx", "Legal and Documentation"),
],
}

# ---------------------------------------------------------------- templates
# rules: (sequence, group, attribute, label, operator, value, value label)
# tasks: (seq, name, stage, assigntype, assignee, duehours, slastart, slatarget,
#         warn%, onbreach, blocks stage, mandatory, instructions)
TEMPLATES = [
{
 "name": "Corporate Credit Lifecycle - New Facility", "rank": 5, "status": 2,
 "desc": "The end to end journey for a new corporate credit facility: origination and document "
         "collection, financial spreading and risk rating, delegated or committee approval, "
         "legal documentation and security perfection, drawdown, and the first covenant review. "
         "Every task publishes its own outcomes so the path adapts to the credit decision.",
 "bpf": "corporate", "startstage": "Origination", "sla": "Standard 24-Hour Response",
 "package": "Corporate Credit Application Pack", "fr": 4, "res": 480, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "8", "Corporate Credit"),
   (2, 2, "cpc_customersegment", "Customer Segment", 3, "4", "Corporate"),
   (3, 2, "cpc_customersegment", "Customer Segment", 3, "5", "SME"),
 ],
 "tasks": [
   (1, "Capture facility request and indicative terms", "Origination", TEAM_, "Credit Origination",
    8, 1, 4, 75, 2, True, True,
    "Record the amount, tenor, purpose, pricing and security offered. Confirm the borrowing entity "
    "and the group it belongs to."),
   (2, "Collect credit application documents", "Origination", TEAM_, "Credit Origination",
    72, 3, 48, 75, 2, True, True,
    "Chase the borrower for the full application pack. Do not release to Credit Risk until the "
    "mandatory items are on file."),
   (3, "Run KYC and sanctions screening", "Origination", TEAM_, "Credit Risk",
    24, 3, 12, 75, 3, True, True,
    "Screen the borrower, its owners and directors. Record any hit and the disposition."),
   (4, "Spread financials and build the credit model", "Underwriting", TEAM_, "Credit Risk",
    72, 2, 48, 75, 2, True, True,
    "Spread three years of audited accounts plus interims. Produce leverage, coverage and "
    "liquidity ratios and the base and stress cases."),
   (5, "Assign internal risk rating", "Underwriting", TEAM_, "Credit Risk",
    24, 3, 16, 75, 3, True, True,
    "Apply the rating model, override with justification if needed, and record the probability "
    "of default grade."),
   (6, "Value and confirm collateral", "Underwriting", TEAM_, "Credit Risk",
    96, 2, 72, 75, 2, False, True,
    "Obtain or refresh valuations and calculate the loan to value against the proposed limit."),
   (7, "Draft credit memorandum and recommendation", "Underwriting", TEAM_, "Credit Risk",
    48, 3, 32, 80, 3, True, True,
    "Write the credit memo with the recommendation, conditions precedent and covenant package."),
   (8, "Credit approval decision", "Credit Decision", MGR_, None,
    48, 2, 24, 50, 3, True, True,
    "Approve, decline or return the proposal within the delegated authority for this exposure."),
   (9, "Credit committee review", "Credit Decision", TEAM_, "Credit Committee",
    120, 3, 96, 75, 3, True, True,
    "Table the proposal at committee for exposures above delegated authority or with policy "
    "exceptions."),
   (10, "Issue offer letter and obtain acceptance", "Documentation", TEAM_, "Credit Origination",
    72, 2, 48, 80, 2, True, True,
    "Send the approved terms to the borrower and obtain a countersigned acceptance."),
   (11, "Draft and execute facility agreement", "Documentation", TEAM_, "Legal and Documentation",
    120, 3, 96, 80, 2, True, True,
    "Produce the facility agreement reflecting the approved conditions and get it executed."),
   (12, "Perfect security and register charges", "Documentation", TEAM_, "Legal and Documentation",
    168, 3, 120, 80, 3, True, True,
    "Register mortgages and charges, take guarantees and assign insurance."),
   (13, "Verify conditions precedent", "Disbursement", TEAM_, "Loan Operations",
    48, 2, 24, 75, 3, True, True,
    "Tick off every condition precedent before any limit is loaded."),
   (14, "Set up limits and release funds", "Disbursement", TEAM_, "Loan Operations",
    24, 3, 16, 80, 3, True, True,
    "Load the facility limits, book the drawdown and confirm value date to the borrower."),
   (15, "Establish covenant monitoring schedule", "Monitoring", TEAM_, "Portfolio Monitoring",
    72, 2, 48, 80, 2, False, True,
    "Diarise every financial and non financial covenant test date and the reporting requirements."),
   (16, "First covenant compliance review", "Monitoring", TEAM_, "Portfolio Monitoring",
    720, 3, 600, 85, 2, False, True,
    "Collect the first compliance certificate and management accounts and confirm the facility "
    "is performing."),
   (17, "Remediate covenant breach", "Monitoring", TEAM_, "Credit Risk",
    120, 4, 72, 75, 3, True, False,
    "A covenant has been breached. Agree waiver, amendment or acceleration with Credit Risk."),
   (18, "Rework proposal after committee feedback", "Underwriting", TEAM_, "Credit Risk",
    72, 4, 48, 75, 3, True, False,
    "Address the points the approver raised and resubmit the credit memorandum."),
 ],
 "graph": [
   ("Capture facility request and indicative terms", "Request captured", POS,
    "Collect credit application documents", ["default"],
    "Amount, tenor, purpose and security are recorded and the borrower is confirmed."),
   ("Capture facility request and indicative terms", "Outside credit appetite", END,
    None, ["close", "comment"],
    "The request falls outside policy on sector, tenor or jurisdiction. Decline at source."),

   ("Collect credit application documents", "Pack complete", POS,
    "Run KYC and sanctions screening", ["default"],
    "Every mandatory document is on file and legible."),
   ("Collect credit application documents", "Borrower unresponsive", END,
    None, ["close", "comment"],
    "The borrower has stopped supplying documents. Close and record the reason."),

   ("Run KYC and sanctions screening", "Screening clear", POS,
    "Spread financials and build the credit model", ["default", "advance"],
    "No hits. The proposal moves into underwriting."),
   ("Run KYC and sanctions screening", "Screening hit - escalate", NEG,
    None, ["comment"],
    "A sanctions or adverse media hit needs financial crime disposition before underwriting."),

   ("Spread financials and build the credit model", "Model complete", POS,
    "Assign internal risk rating", ["default"],
    "Ratios and stress cases are built and the numbers reconcile to the audited accounts."),
   ("Spread financials and build the credit model", "Financials unreliable", NEG,
    "Collect credit application documents", ["comment", "stage:Origination"],
    "The accounts are qualified or inconsistent. Go back and get restated figures."),

   ("Assign internal risk rating", "Rating within appetite", POS,
    "Value and confirm collateral", ["default"],
    "The obligor grade is acceptable for the proposed structure."),
   ("Assign internal risk rating", "Rating below appetite", NEG,
    "Draft credit memorandum and recommendation", ["comment"],
    "Weak grade. Only proceed with a decline recommendation or a heavily secured structure."),

   ("Value and confirm collateral", "Collateral acceptable", POS,
    "Draft credit memorandum and recommendation", ["default"],
    "Valuation supports the proposed loan to value."),
   ("Value and confirm collateral", "Unsecured - proceed on covenants", NEU,
    "Draft credit memorandum and recommendation", [],
    "No tangible security. The structure will rely on covenants and guarantees."),

   ("Draft credit memorandum and recommendation", "Within delegated authority", POS,
    "Credit approval decision", ["default", "advance"],
    "Exposure sits inside the approver's limit. Route for a single signature decision."),
   ("Draft credit memorandum and recommendation", "Requires credit committee", NEU,
    "Credit committee review", ["advance"],
    "Above delegated authority or contains a policy exception. Route to committee."),

   ("Credit approval decision", "Approved", POS,
    "Issue offer letter and obtain acceptance", ["default", "advance"],
    "Approved as recommended. Move to documentation."),
   ("Credit approval decision", "Approved with conditions", NEU,
    "Issue offer letter and obtain acceptance", ["advance", "comment"],
    "Approved subject to additional conditions precedent. Record them on the offer."),
   ("Credit approval decision", "Refer to committee", NEU,
    "Credit committee review", [],
    "The approver wants committee cover for this exposure."),
   ("Credit approval decision", "Declined", END,
    None, ["close", "comment"],
    "The facility is declined. Communicate the decision to the client."),

   ("Credit committee review", "Committee approved", POS,
    "Issue offer letter and obtain acceptance", ["default", "advance"],
    "Committee approved the facility as presented."),
   ("Credit committee review", "Deferred - rework required", NEG,
    "Rework proposal after committee feedback", ["comment"],
    "Committee wants more analysis or a different structure before deciding."),
   ("Credit committee review", "Committee declined", END,
    None, ["close", "comment"],
    "Committee declined the proposal."),

   ("Rework proposal after committee feedback", "Reworked and resubmitted", POS,
    "Credit committee review", ["default"],
    "The revised memorandum goes back to the same committee."),
   ("Rework proposal after committee feedback", "Client withdrew", END,
    None, ["close", "comment"],
    "The client withdrew the request while it was being reworked."),

   ("Issue offer letter and obtain acceptance", "Offer accepted", POS,
    "Draft and execute facility agreement", ["default"],
    "The borrower countersigned the offer within the validity period."),
   ("Issue offer letter and obtain acceptance", "Terms renegotiated", NEU,
    "Draft credit memorandum and recommendation", ["comment", "stage:Underwriting"],
    "The borrower wants different pricing or tenor. The memo has to be revisited."),
   ("Issue offer letter and obtain acceptance", "Offer lapsed", END,
    None, ["close", "comment"],
    "The offer expired without acceptance."),

   ("Draft and execute facility agreement", "Agreement executed", POS,
    "Perfect security and register charges", ["default"],
    "The facility agreement is signed by all parties."),

   ("Perfect security and register charges", "Security perfected", POS,
    "Verify conditions precedent", ["default", "advance"],
    "All charges are registered and guarantees are in place."),
   ("Perfect security and register charges", "Registration delayed", NEG,
    "Verify conditions precedent", ["comment"],
    "Registration is pending at the authority. Track it as an outstanding condition."),

   ("Verify conditions precedent", "All conditions met", POS,
    "Set up limits and release funds", ["default"],
    "Every condition precedent is satisfied and evidenced."),
   ("Verify conditions precedent", "Conditions outstanding", NEG,
    "Perfect security and register charges", ["comment", "stage:Documentation"],
    "One or more conditions are not met. Send it back to documentation."),

   ("Set up limits and release funds", "Funds disbursed", POS,
    "Establish covenant monitoring schedule", ["default", "advance"],
    "Limits are live and the drawdown has value dated."),
   ("Set up limits and release funds", "Facility not drawn", NEU,
    "Establish covenant monitoring schedule", ["advance"],
    "The limit is available but undrawn. Monitoring still applies."),

   ("Establish covenant monitoring schedule", "Schedule in place", POS,
    "First covenant compliance review", ["default"],
    "Every test date and reporting obligation is diarised."),

   ("First covenant compliance review", "Compliant - facility performing", POS,
    None, ["default", "close"],
    "All covenants are met. The facility moves into business as usual monitoring."),
   ("First covenant compliance review", "Covenant breached", NEG,
    "Remediate covenant breach", ["comment"],
    "A covenant test failed. Credit Risk has to agree the remedy."),
   ("First covenant compliance review", "Reporting overdue", NEG,
    "Remediate covenant breach", ["comment"],
    "The borrower has not supplied compliance reporting on time."),

   ("Remediate covenant breach", "Waiver granted", NEU,
    "First covenant compliance review", ["default"],
    "A waiver or amendment was agreed. Re-test at the next date."),
   ("Remediate covenant breach", "Facility accelerated", END,
    None, ["close", "comment"],
    "The breach was not curable. The facility has been called and moves to recoveries."),
 ],
},
{
 "name": "Corporate Credit - Annual Review", "rank": 12, "status": 2,
 "desc": "The periodic review of a live corporate facility: refresh the financials, re-rate the "
         "obligor, confirm covenant compliance and renew, amend or exit the exposure.",
 "bpf": "corporate", "startstage": "Underwriting", "sla": "Standard 24-Hour Response",
 "package": "Credit Monitoring Pack", "fr": 8, "res": 336, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "11", "Credit Review"),
 ],
 "tasks": [
   (1, "Request annual review information pack", "Underwriting", TEAM_, "Portfolio Monitoring",
    72, 1, 48, 75, 2, True, True,
    "Ask the borrower for audited accounts, management accounts and the compliance certificate."),
   (2, "Refresh financial spreading", "Underwriting", TEAM_, "Credit Risk",
    96, 3, 72, 75, 2, True, True,
    "Update the spread with the latest audited numbers and compare against last year's base case."),
   (3, "Re-rate the obligor", "Underwriting", TEAM_, "Credit Risk",
    48, 3, 32, 75, 3, True, True,
    "Re-run the rating model and record any migration and its cause."),
   (4, "Test covenant compliance", "Underwriting", TEAM_, "Portfolio Monitoring",
    48, 2, 32, 75, 3, True, True,
    "Test every financial covenant against the certified figures."),
   (5, "Write the annual review memorandum", "Credit Decision", TEAM_, "Credit Risk",
    72, 3, 48, 80, 2, True, True,
    "Recommend renew, amend, reduce or exit with supporting rationale."),
   (6, "Approve the annual review", "Credit Decision", MGR_, None,
    48, 3, 24, 50, 3, True, True,
    "Sign off the review outcome and any change to limits or pricing."),
   (7, "Implement renewed terms", "Documentation", TEAM_, "Loan Operations",
    96, 3, 72, 80, 2, False, True,
    "Update limits, pricing and expiry dates and issue amended documentation where needed."),
   (8, "Transfer to watchlist", "Monitoring", TEAM_, "Credit Risk",
    48, 4, 24, 75, 3, True, False,
    "Rating or performance has deteriorated. Move the name onto the watchlist with an action plan."),
 ],
 "graph": [
   ("Request annual review information pack", "Information received", POS,
    "Refresh financial spreading", ["default"], "The borrower supplied the full review pack."),
   ("Request annual review information pack", "Information not supplied", NEG,
    "Transfer to watchlist", ["comment"],
    "Persistent failure to report is itself an early warning signal."),

   ("Refresh financial spreading", "Spreading complete", POS,
    "Re-rate the obligor", ["default"], "The latest financials are spread and reconciled."),

   ("Re-rate the obligor", "Rating stable or improved", POS,
    "Test covenant compliance", ["default"], "No adverse migration."),
   ("Re-rate the obligor", "Rating downgraded", NEG,
    "Test covenant compliance", ["comment"], "The grade has migrated down. Flag it in the memo."),

   ("Test covenant compliance", "All covenants met", POS,
    "Write the annual review memorandum", ["default", "advance"], "Facility is compliant."),
   ("Test covenant compliance", "Breach identified", NEG,
    "Transfer to watchlist", ["comment"], "A covenant failed. Move to watchlist before deciding."),

   ("Write the annual review memorandum", "Recommend renewal", POS,
    "Approve the annual review", ["default"], "Renew on existing or improved terms."),
   ("Write the annual review memorandum", "Recommend reduction or exit", NEG,
    "Approve the annual review", ["comment"], "Reduce the limit or plan an orderly exit."),

   ("Approve the annual review", "Renewed", POS,
    "Implement renewed terms", ["default", "advance"], "Approved. Implement the renewed terms."),
   ("Approve the annual review", "Exit agreed", END,
    None, ["close", "comment"], "The bank will not renew. Close the review and plan the exit."),

   ("Implement renewed terms", "Terms implemented", POS,
    None, ["default", "close"], "Limits, pricing and expiry are updated in the systems."),

   ("Transfer to watchlist", "Watchlist action plan agreed", NEU,
    "Write the annual review memorandum", ["default"],
    "The name is on watchlist with an agreed plan. Continue the review."),
   ("Transfer to watchlist", "Move to recoveries", END,
    None, ["close", "comment"], "Deterioration is severe. Hand over to recoveries."),
 ],
},
{
 "name": "Trade Finance - Letter of Credit Issuance", "rank": 18, "status": 2,
 "desc": "Issuing a documentary letter of credit against an approved trade line: application "
         "capture, sanctions screening, limit availability, drafting and issuance.",
 "bpf": "corporate", "startstage": "Origination", "sla": "Premier 4-Hour Response",
 "package": "Trade Finance LC Pack", "fr": 2, "res": 48, "priority": 1,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "10", "Trade Finance"),
 ],
 "tasks": [
   (1, "Capture LC application and underlying contract", "Origination", TEAM_, "Credit Origination",
    4, 1, 2, 75, 2, True, True,
    "Record the beneficiary, amount, tenor, incoterms and the underlying sales contract."),
   (2, "Screen counterparties, goods and vessel", "Origination", TEAM_, "Credit Risk",
    4, 3, 2, 50, 3, True, True,
    "Screen the beneficiary, the goods, the countries and the carrying vessel against sanctions."),
   (3, "Confirm trade limit availability", "Underwriting", TEAM_, "Credit Risk",
    8, 2, 4, 75, 3, True, True,
    "Check the approved trade line has headroom for this issuance and margin is held."),
   (4, "Draft the letter of credit", "Documentation", TEAM_, "Legal and Documentation",
    12, 2, 8, 80, 2, True, True,
    "Draft the LC terms in line with UCP 600 and the underlying contract."),
   (5, "Authorise and transmit the LC", "Disbursement", TEAM_, "Loan Operations",
    8, 3, 4, 80, 3, True, True,
    "Obtain dual authorisation and transmit the LC over SWIFT to the advising bank."),
   (6, "Obtain limit exception approval", "Underwriting", MGR_, None,
    8, 4, 4, 50, 3, True, False,
    "The trade line has insufficient headroom. Seek a temporary excess or a limit increase."),
 ],
 "graph": [
   ("Capture LC application and underlying contract", "Application complete", POS,
    "Screen counterparties, goods and vessel", ["default"], "All LC particulars are captured."),
   ("Capture LC application and underlying contract", "Application incomplete", NEG,
    None, ["close", "comment"], "The client could not supply the underlying contract."),

   ("Screen counterparties, goods and vessel", "Screening clear", POS,
    "Confirm trade limit availability", ["default", "advance"], "No sanctions concerns."),
   ("Screen counterparties, goods and vessel", "Sanctions concern - reject", END,
    None, ["close", "comment"], "The transaction touches a restricted party, port or good."),

   ("Confirm trade limit availability", "Limit available", POS,
    "Draft the letter of credit", ["default", "advance"], "Headroom confirmed and margin held."),
   ("Confirm trade limit availability", "Insufficient limit", NEG,
    "Obtain limit exception approval", ["comment"], "Not enough headroom on the trade line."),

   ("Obtain limit exception approval", "Excess approved", POS,
    "Draft the letter of credit", ["default", "advance"], "A temporary excess was approved."),
   ("Obtain limit exception approval", "Excess declined", END,
    None, ["close", "comment"], "No appetite for the excess. The LC cannot be issued."),

   ("Draft the letter of credit", "Draft agreed with client", POS,
    "Authorise and transmit the LC", ["default", "advance"], "The client approved the LC wording."),
   ("Draft the letter of credit", "Client amended the terms", NEU,
    "Draft the letter of credit", ["comment"], "The client changed the terms. Redraft and reconfirm."),

   ("Authorise and transmit the LC", "LC issued", POS,
    None, ["default", "close"], "The LC has been transmitted and the advising bank acknowledged."),
 ],
},
{
 "name": "Retail Personal Loan Application", "rank": 25, "status": 2,
 "desc": "A retail unsecured personal loan from application through affordability assessment, "
         "automated or manual decision, and disbursement.",
 "bpf": "retail", "startstage": "Application", "sla": "Onboarding 2-Day Response",
 "package": "Retail Lending Pack", "fr": 4, "res": 120, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "9", "Retail Lending"),
   (2, 2, "cpc_customersegment", "Customer Segment", 3, "3", "Retail"),
   (3, 2, "cpc_customersegment", "Customer Segment", 3, "1", "Premier"),
   (4, 2, "cpc_customersegment", "Customer Segment", 3, "2", "Priority"),
 ],
 "tasks": [
   (1, "Capture application and consent", "Application", TEAM_, "Retail Lending Operations",
    4, 1, 2, 75, 2, True, True,
    "Capture the amount, tenor and purpose and take credit bureau consent."),
   (2, "Collect income and identity documents", "Application", TEAM_, "Retail Lending Operations",
    48, 3, 24, 75, 2, True, True,
    "Obtain the Emirates ID, salary certificate and six months of bank statements."),
   (3, "Verify employment and income", "Assessment", TEAM_, "Retail Lending Operations",
    24, 2, 16, 75, 2, True, True,
    "Confirm the employer, salary transfer arrangement and length of service."),
   (4, "Run affordability and DBR assessment", "Assessment", TEAM_, "Retail Lending Operations",
    12, 3, 8, 75, 3, True, True,
    "Calculate the debt burden ratio against the regulatory cap including the new instalment."),
   (5, "Underwriter decision", "Decision", MGR_, None,
    24, 2, 12, 50, 3, True, True,
    "Approve, decline or counter offer a lower amount or longer tenor."),
   (6, "Prepare and issue loan agreement", "Fulfilment", TEAM_, "Retail Lending Operations",
    48, 2, 24, 80, 2, True, True,
    "Generate the loan agreement and schedule and send it for signature."),
   (7, "Disburse the loan", "Fulfilment", TEAM_, "Loan Operations",
    24, 3, 12, 80, 3, False, True,
    "Book the loan, settle any buyout and credit the customer account."),
   (8, "Present counter offer to customer", "Decision", TEAM_, "Retail Lending Operations",
    24, 4, 12, 75, 2, True, False,
    "Explain the revised amount or tenor and capture the customer's decision."),
 ],
 "graph": [
   ("Capture application and consent", "Application submitted", POS,
    "Collect income and identity documents", ["default"], "Application and bureau consent captured."),
   ("Capture application and consent", "Customer abandoned", END,
    None, ["close", "comment"], "The customer did not complete the application."),

   ("Collect income and identity documents", "Documents complete", POS,
    "Verify employment and income", ["default", "advance"], "All mandatory documents are on file."),
   ("Collect income and identity documents", "Documents outstanding", NEG,
    "Collect income and identity documents", ["comment"], "Chase the missing items and re-check."),

   ("Verify employment and income", "Income verified", POS,
    "Run affordability and DBR assessment", ["default"], "Employment and salary confirmed."),
   ("Verify employment and income", "Verification failed", END,
    None, ["close", "comment"], "Income could not be verified. Decline the application."),

   ("Run affordability and DBR assessment", "Within DBR limit", POS,
    "Underwriter decision", ["default", "advance"], "Affordable at the requested amount."),
   ("Run affordability and DBR assessment", "Exceeds DBR limit", NEG,
    "Underwriter decision", ["advance", "comment"],
    "The requested amount breaches the debt burden cap. Only a reduced offer is possible."),

   ("Underwriter decision", "Approved as requested", POS,
    "Prepare and issue loan agreement", ["default", "advance"], "Approved at the requested amount."),
   ("Underwriter decision", "Counter offer", NEU,
    "Present counter offer to customer", [], "Approved at a lower amount or longer tenor."),
   ("Underwriter decision", "Declined", END,
    None, ["close", "comment"], "The application does not meet credit policy."),

   ("Present counter offer to customer", "Counter offer accepted", POS,
    "Prepare and issue loan agreement", ["default", "advance"], "The customer accepted the revised terms."),
   ("Present counter offer to customer", "Counter offer declined", END,
    None, ["close", "comment"], "The customer did not want the revised terms."),

   ("Prepare and issue loan agreement", "Agreement signed", POS,
    "Disburse the loan", ["default"], "The customer signed the loan agreement and schedule."),
   ("Prepare and issue loan agreement", "Customer did not sign", END,
    None, ["close", "comment"], "The agreement lapsed unsigned."),

   ("Disburse the loan", "Loan disbursed", POS,
    None, ["default", "close"], "Funds are credited and the loan is live."),
 ],
},
{
 "name": "Retail Mortgage Application", "rank": 28, "status": 2,
 "desc": "A residential mortgage from pre approval through property valuation, legal checks, "
         "final offer and disbursement to the seller.",
 "bpf": "retail", "startstage": "Application", "sla": "Onboarding 2-Day Response",
 "package": "Mortgage Application Pack", "fr": 8, "res": 720, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "9", "Retail Lending"),
   (2, 2, "subjectid", "Subject", 1, "", "Lending"),
 ],
 "tasks": [
   (1, "Capture mortgage application", "Application", TEAM_, "Retail Lending Operations",
    8, 1, 4, 75, 2, True, True,
    "Capture the property, purchase price, down payment, tenor and applicant details."),
   (2, "Issue pre approval in principle", "Application", TEAM_, "Retail Lending Operations",
    72, 3, 48, 75, 2, True, True,
    "Assess income and liabilities and issue a pre approval letter with its validity date."),
   (3, "Collect property and income documents", "Assessment", TEAM_, "Retail Lending Operations",
    120, 2, 96, 75, 2, True, True,
    "Obtain the sale and purchase agreement, title deed and the full income pack."),
   (4, "Commission independent valuation", "Assessment", TEAM_, "Legal and Documentation",
    168, 3, 120, 80, 2, True, True,
    "Instruct a panel valuer and record the valuation against the purchase price."),
   (5, "Legal and title verification", "Assessment", TEAM_, "Legal and Documentation",
    120, 3, 96, 80, 2, True, True,
    "Verify title, encumbrances, service charges and developer no objection."),
   (6, "Final credit decision", "Decision", MGR_, None,
    48, 2, 24, 50, 3, True, True,
    "Approve the final loan amount against the lower of price and valuation."),
   (7, "Issue final mortgage offer", "Fulfilment", TEAM_, "Legal and Documentation",
    72, 2, 48, 80, 2, True, True,
    "Issue the binding offer letter and obtain the customer's signature."),
   (8, "Register mortgage and disburse", "Fulfilment", TEAM_, "Loan Operations",
    168, 3, 120, 80, 3, False, True,
    "Register the mortgage with the land department and release funds to the seller."),
   (9, "Renegotiate price after down valuation", "Assessment", TEAM_, "Retail Lending Operations",
    120, 4, 96, 75, 2, True, False,
    "The valuation came in under the purchase price. Agree a larger down payment or a lower price."),
 ],
 "graph": [
   ("Capture mortgage application", "Application captured", POS,
    "Issue pre approval in principle", ["default"], "Property and applicant details are recorded."),

   ("Issue pre approval in principle", "Pre approved", POS,
    "Collect property and income documents", ["default", "advance"],
    "A pre approval letter has been issued and is within validity."),
   ("Issue pre approval in principle", "Not eligible", END,
    None, ["close", "comment"], "Income or liabilities do not support any mortgage."),

   ("Collect property and income documents", "Documents complete", POS,
    "Commission independent valuation", ["default"], "The property and income pack is complete."),
   ("Collect property and income documents", "Purchase fell through", END,
    None, ["close", "comment"], "The customer did not proceed with the property."),

   ("Commission independent valuation", "Valuation supports the price", POS,
    "Legal and title verification", ["default"], "The valuation is at or above the purchase price."),
   ("Commission independent valuation", "Down valuation", NEG,
    "Renegotiate price after down valuation", ["comment"],
    "The valuation is below the price, so the loan to value no longer works."),

   ("Renegotiate price after down valuation", "Revised terms agreed", POS,
    "Legal and title verification", ["default"], "A larger down payment or lower price was agreed."),
   ("Renegotiate price after down valuation", "Customer withdrew", END,
    None, ["close", "comment"], "The customer walked away from the purchase."),

   ("Legal and title verification", "Title clear", POS,
    "Final credit decision", ["default", "advance"], "Title and encumbrances are satisfactory."),
   ("Legal and title verification", "Title defect found", END,
    None, ["close", "comment"], "A title or developer issue makes the property unmortgageable."),

   ("Final credit decision", "Approved", POS,
    "Issue final mortgage offer", ["default", "advance"], "Final loan amount approved."),
   ("Final credit decision", "Declined", END,
    None, ["close", "comment"], "The mortgage was declined at final credit."),

   ("Issue final mortgage offer", "Offer signed", POS,
    "Register mortgage and disburse", ["default"], "The customer signed the binding offer."),
   ("Issue final mortgage offer", "Offer lapsed", END,
    None, ["close", "comment"], "The offer expired before signature."),

   ("Register mortgage and disburse", "Mortgage registered and funded", POS,
    None, ["default", "close"], "The mortgage is registered and the seller has been paid."),
 ],
},
{
 "name": "Retail Card Limit Increase", "rank": 35, "status": 2,
 "desc": "A fast track credit card limit increase: eligibility check, affordability test and "
         "same day limit load. Two stages only, most requests close within a day.",
 "bpf": "retail", "startstage": "Assessment", "sla": "Standard 24-Hour Response",
 "package": "Retail Lending Pack", "fr": 2, "res": 24, "priority": 3,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "9", "Retail Lending"),
   (2, 2, "subjectid", "Subject", 1, "", "Account Servicing"),
 ],
 "tasks": [
   (1, "Check eligibility and conduct history", "Assessment", TEAM_, "Retail Lending Operations",
    4, 1, 2, 75, 2, True, True,
    "Check card age, payment history, utilisation and any delinquency in the last twelve months."),
   (2, "Run affordability check", "Assessment", TEAM_, "Retail Lending Operations",
    4, 3, 2, 75, 2, True, True,
    "Re-test the debt burden ratio at the requested limit."),
   (3, "Approve the new limit", "Decision", MGR_, None,
    8, 2, 4, 50, 2, True, True,
    "Approve the requested limit, offer a lower one, or decline."),
   (4, "Load the limit and notify the customer", "Fulfilment", TEAM_, "Retail Lending Operations",
    8, 3, 4, 80, 2, False, True,
    "Apply the new limit on the card and confirm it to the customer."),
 ],
 "graph": [
   ("Check eligibility and conduct history", "Eligible", POS,
    "Run affordability check", ["default"], "Card conduct meets the policy minimum."),
   ("Check eligibility and conduct history", "Not eligible", END,
    None, ["close", "comment"], "Card age or payment history does not qualify."),

   ("Run affordability check", "Affordable at requested limit", POS,
    "Approve the new limit", ["default", "advance"], "The requested limit sits inside the DBR cap."),
   ("Run affordability check", "Affordable at a lower limit", NEU,
    "Approve the new limit", ["advance", "comment"], "Only a partial increase is affordable."),
   ("Run affordability check", "Not affordable", END,
    None, ["close", "comment"], "Any increase would breach the debt burden cap."),

   ("Approve the new limit", "Increase approved", POS,
    "Load the limit and notify the customer", ["default", "advance"], "The new limit is approved."),
   ("Approve the new limit", "Increase declined", END,
    None, ["close", "comment"], "The increase was declined at underwriting."),

   ("Load the limit and notify the customer", "Limit applied", POS,
    None, ["default", "close"], "The new limit is live and the customer has been told."),
 ],
},
]


# ============================================================================ writers
def ensure_categories():
    for value, label in NEW_CATEGORIES:
        try:
            dv.post("InsertOptionValue", {
                "EntityLogicalName": "incident", "AttributeLogicalName": f"{P}_casecategory",
                "Value": value, "Label": {"LocalizedLabels": [
                    {"Label": label, "LanguageCode": 1033,
                     "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel"}],
                    "@odata.type": "Microsoft.Dynamics.CRM.Label"}})
            print("  + category", value, label)
        except RuntimeError as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("  = category", value, label)
            else:
                raise


def ensure_teams(bu):
    for name, desc in NEW_TEAMS:
        if dv.find_one("teams", f"name eq '{name}'", "teamid"):
            continue
        dv.post("teams", {"name": name, "description": desc, "teamtype": 0,
                          "businessunitid@odata.bind": f"/businessunits({bu})"})
        print("  + team", name)


def upsert_package(name, items, teams):
    pkg = dv.find_one(f"{P}_documentpackages", f"{P}_name eq '{name}'", f"{P}_documentpackageid")
    if pkg:
        pid = pkg[f"{P}_documentpackageid"]
    else:
        pid = dv.new_id(dv.post(f"{P}_documentpackages", {
            f"{P}_name": name, f"{P}_active": True,
            f"{P}_description": f"Documents required for the {name.lower()}."}))
        print("  + package", name)
    have = {r[f"{P}_name"] for r in dv.get(
        f"{P}_documentitems?$select={P}_name&$filter=_{P}_package_value eq {pid}")["value"]}
    for iname, seq, mand, resp, due, tmpl, team in items:
        if iname in have:
            continue
        body = {f"{P}_name": iname, f"{P}_sequence": seq, f"{P}_mandatory": mand,
                f"{P}_responsible": resp, f"{P}_duehours": due,
                f"{P}_package@odata.bind": f"/{P}_documentpackages({pid})"}
        if tmpl:
            body[f"{P}_templatefile"] = tmpl
        if team in teams:
            body[f"{P}_ownerteam@odata.bind"] = f"/teams({teams[team]})"
        dv.post(f"{P}_documentitems", body)
    return pid


def upsert_template(t, ctx):
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
        # Subject rules are written by display name, so resolve the record id here.
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
            fb = ctx["teams"].get("Credit Risk")
            if fb:
                b[f"{P}_fallbackteam@odata.bind"] = f"/teams({fb})"
        elif atype == ROLE_ and assignee:
            b[f"{P}_rolename"] = assignee
        elif atype == QUEUE_ and assignee in ctx["queues"]:
            b[f"{P}_queue@odata.bind"] = f"/queues({ctx['queues'][assignee]})"
        if prev:
            b[f"{P}_predecessor@odata.bind"] = f"/{P}_processtasks({prev})"
        prev = dv.new_id(dv.post(f"{P}_processtasks", b))
    return tid


# ---------------------------------------------------------------- outcome graph + layout
# Mirrors the designer's elastic swimlane geometry so a seeded process opens laid out correctly.
SUB_W, ROWS_PER_LANE, STAGE_PAD, STAGE_GAP = 268, 3, 30, 18
ROW_H, ROW_Y0, LANE_STAGGER = 215, 200, 0.3


def layout(tid, tasks, stage_names):
    by_stage = {}
    for t in sorted(tasks.values(), key=lambda r: r[f"{P}_sequence"] or 0):
        by_stage.setdefault(t.get(f"{P}_stagename") or (stage_names[0] if stage_names else ""),
                            []).append(t)

    left = 0
    for name in stage_names:
        nodes = by_stage.get(name, [])
        lanes = max(1, -(-len(nodes) // ROWS_PER_LANE))
        width = lanes * SUB_W + 2 * STAGE_PAD
        for i, t in enumerate(nodes):
            lane, row = divmod(i, ROWS_PER_LANE)
            x = left + STAGE_PAD + lane * SUB_W + SUB_W / 2
            y = ROW_Y0 + (row + (lane % 2) * LANE_STAGGER) * ROW_H
            dv.patch(f"{P}_processtasks({t[f'{P}_processtaskid']})",
                     {f"{P}_posx": int(x), f"{P}_posy": int(y)})
        left += width + STAGE_GAP


def apply_graph(tid, spec, stage_names):
    tasks = {r[f"{P}_name"]: r for r in dv.get(
        f"{P}_processtasks?$select={P}_name,{P}_processtaskid,{P}_stagename,{P}_sequence"
        f"&$filter=_{P}_template_value eq {tid}")["value"]}

    missing = {n for e in spec for n in (e[0], e[3]) if n and n not in tasks}
    if missing:
        print("    ! unknown task(s):", missing)

    for o in dv.get(f"{P}_taskoutcomes?$select={P}_taskoutcomeid"
                    f"&$filter=_{P}_template_value eq {tid}")["value"]:
        dv.call("DELETE", f"{P}_taskoutcomes({o[f'{P}_taskoutcomeid']})")

    entry = spec[0][0]
    for name, t in tasks.items():
        dv.patch(f"{P}_processtasks({t[f'{P}_processtaskid']})", {f"{P}_isstart": name == entry})

    seq = 0
    for frm, lbl, sent, to, flags, guidance in spec:
        if frm not in tasks:
            continue
        seq += 1
        b = {
            f"{P}_name": lbl, f"{P}_description": guidance, f"{P}_sequence": seq,
            f"{P}_sentiment": sent,
            f"{P}_advancestage": "advance" in flags, f"{P}_closecase": "close" in flags,
            f"{P}_requirecomment": "comment" in flags, f"{P}_isdefault": "default" in flags,
            f"{P}_setcasepriority": 0,
            f"{P}_task@odata.bind": f"/{P}_processtasks({tasks[frm][f'{P}_processtaskid']})",
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        jump = next((f.split(":", 1)[1] for f in flags if f.startswith("stage:")), None)
        if jump:
            b[f"{P}_targetstagename"] = jump
        if to and to in tasks:
            b[f"{P}_nexttask@odata.bind"] = f"/{P}_processtasks({tasks[to][f'{P}_processtaskid']})"
        dv.post(f"{P}_taskoutcomes", b)

    layout(tid, tasks, stage_names)
    print(f"    {seq} outcome(s), {len(tasks)} task(s)")


def main():
    bu = dv.get("businessunits?$select=businessunitid"
                "&$filter=parentbusinessunitid eq null")["value"][0]["businessunitid"]
    print("Case categories")
    ensure_categories()
    print("Teams")
    ensure_teams(bu)

    print("Business process flows")
    corp_id, corp_stages = bpfgen.upsert_bpf(
        "Corporate Credit Lifecycle", "cpc_corporatecreditlifecycle",
        "End to end corporate credit facility lifecycle from origination through to monitoring.",
        BPF_CORPORATE)
    retail_id, retail_stages = bpfgen.upsert_bpf(
        "Retail Lending Journey", "cpc_retaillendingjourney",
        "Retail lending application journey from application through assessment to fulfilment.",
        BPF_RETAIL)

    ctx = {
        "teams": {t["name"]: t["teamid"] for t in dv.get("teams?$select=teamid,name")["value"]},
        "queues": {q["name"]: q["queueid"] for q in dv.get("queues?$select=queueid,name")["value"]},
        "slas": {s["name"]: s["slaid"] for s in dv.get("slas?$select=slaid,name")["value"]},
        "bpfs": {
            "corporate": ({"id": corp_id, "name": "Corporate Credit Lifecycle",
                           "unique": "cpc_corporatecreditlifecycle"}, corp_stages),
            "retail": ({"id": retail_id, "name": "Retail Lending Journey",
                        "unique": "cpc_retaillendingjourney"}, retail_stages),
        },
    }
    ORDER = {
        "corporate": ["Origination", "Underwriting", "Credit Decision",
                      "Documentation", "Disbursement", "Monitoring"],
        "retail": ["Application", "Assessment", "Decision", "Fulfilment"],
    }

    print("Document packages")
    ctx["pkgs"] = {n: upsert_package(n, items, ctx["teams"]) for n, items in PACKAGES.items()}

    print("Templates")
    for t in TEMPLATES:
        tid = upsert_template(t, ctx)
        apply_graph(tid, t["graph"], ORDER[t["bpf"]])

    dv.publish_all()
    print("done")


if __name__ == "__main__":
    main()

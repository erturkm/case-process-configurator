"""Step 6: seed document packages and case process templates with rules and stage-linked tasks."""
import dv

P = dv.PREFIX
NOW = "2026-08-26T06:00:00Z"

BPF = dv.find_one("workflows", "uniquename eq 'phonetocaseprocess'", "workflowid,name,uniquename")
STAGES = {s["stagename"]: s["processstageid"] for s in dv.get(
    f"processstages?$select=processstageid,stagename&$filter=_processid_value eq {BPF['workflowid']}")["value"]}

BPF_WO = dv.find_one("workflows", "name eq 'Case to Work Order Business Process'",
                     "workflowid,name,uniquename")
STAGES_WO = {s["stagename"]: s["processstageid"] for s in dv.get(
    f"processstages?$select=processstageid,stagename&$filter=_processid_value eq {BPF_WO['workflowid']}")["value"]}

TEAM = {t["name"]: t["teamid"] for t in dv.get("teams?$select=teamid,name")["value"]}
QUEUE = {q["name"]: q["queueid"] for q in dv.get("queues?$select=queueid,name")["value"]}
SLA = {s["name"]: s["slaid"] for s in dv.get("slas?$select=slaid,name")["value"]}

CAL = "UAE Sun-Thu 08:00-18:00"

# ------------------------------------------------------------------ document packages
PACKAGES = {
"Complaint Evidence Pack": [
    ("Signed Complaint Form", 1, True, 1, 48, "complaint_form.docx", "Contact Centre Tier 1"),
    ("Customer Identification Document", 2, True, 1, 24, "", "Contact Centre Tier 1"),
    ("Supporting Correspondence", 3, False, 1, 72, "", "Contact Centre Tier 1"),
    ("Final Response Letter", 4, True, 3, 120, "final_response_letter.docx", "Correspondence"),
],
"Fraud Dispute Pack": [
    ("Signed Dispute Declaration", 1, True, 1, 24, "dispute_declaration.docx", "Fraud Operations"),
    ("Identification Document", 2, True, 1, 12, "", "Fraud Operations"),
    ("Transaction Statement Extract", 3, True, 3, 8, "statement_extract.xlsx", "Fraud Operations"),
    ("Police Report", 4, False, 1, 168, "", "Fraud Operations"),
    ("Chargeback Submission Receipt", 5, True, 3, 72, "", "Fraud Operations"),
],
"KYC Onboarding Pack": [
    ("Identification Document", 1, True, 1, 48, "", "Onboarding Operations"),
    ("Proof of Address", 2, True, 1, 48, "", "Onboarding Operations"),
    ("Source of Funds Declaration", 3, True, 1, 72, "source_of_funds.docx", "Onboarding Operations"),
    ("Signature Specimen", 4, True, 1, 72, "", "Onboarding Operations"),
    ("Risk Screening Result", 5, True, 3, 96, "", "Onboarding Operations"),
],
"Corporate Escalation Pack": [
    ("Executive Summary Brief", 1, True, 3, 8, "exec_brief.docx", "Complaints Management"),
    ("Impact Assessment", 2, True, 3, 24, "impact_assessment.xlsx", "Complaints Management"),
    ("Remediation Plan", 3, True, 3, 48, "remediation_plan.docx", "Complaints Management"),
],
"Service Request Pack": [
    ("Request Confirmation", 1, True, 2, 24, "", "Contact Centre Tier 1"),
    ("Completion Evidence", 2, False, 2, 72, "", "Contact Centre Tier 1"),
],
"Field Service Pack": [
    ("Site Access Authorisation", 1, True, 1, 24, "", "Field Service Dispatch"),
    ("Engineer Work Sheet", 2, True, 3, 72, "work_sheet.docx", "Field Service Dispatch"),
],
}

# ------------------------------------------------------------------ templates
# rules: (sequence, group, attribute, label, operator, value, value label)
# tasks: (seq, name, stage, assigntype, assignee, duehours, slastart, slatarget, warn%, onbreach,
#         blocks, mandatory, instructions)
TEMPLATES = [
{
 "name": "Premier Complaint (High Priority)", "rank": 10, "status": 2,
 "desc": "Complaints raised by Premier segment customers at high or urgent priority. "
         "Applies the four hour SLA, the Phone to Case process and the full evidence pack.",
 "bpf": "phone", "startstage": "Identify", "sla": "Premier 4-Hour Response",
 "package": "Complaint Evidence Pack", "fr": 1, "res": 4, "priority": 1,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "1", "Complaint"),
   (2, 2, "prioritycode", "Priority", 3, "1", "High"),
   (3, 3, "cpc_customersegment", "Customer Segment", 1, "1", "Premier"),
 ],
 "tasks": [
   (1, "Acknowledge customer and log complaint", "Identify", 1, "Contact Centre Tier 1",
    2, 1, 0.5, 75, 3, True, True,
    "Call the customer within 30 minutes, confirm the complaint details and log the reference number."),
   (2, "Verify customer identity", "Identify", 3, "Tier 1 Agent",
    4, 2, 1, 75, 2, True, True,
    "Complete identity verification before any account detail is discussed."),
   (3, "Collect complaint evidence", "Research", 1, "Complaints Management",
    8, 2, 4, 75, 3, True, True,
    "Gather statements, call recordings and prior correspondence into the case."),
   (4, "Root cause investigation", "Research", 1, "Complaints Management",
    24, 3, 8, 75, 3, True, True,
    "Establish what went wrong, which control failed and whether other customers are affected."),
   (5, "Complaints manager approval", "Resolve", 5, None,
    4, 3, 4, 50, 3, True, True,
    "Manager reviews the proposed outcome and any redress before it is communicated."),
   (6, "Issue final response letter", "Resolve", 1, "Correspondence",
    48, 3, 24, 80, 2, False, True,
    "Produce and send the final response letter using the approved template."),
 ],
},
{
 "name": "Fraud Dispute - Card", "rank": 20, "status": 2,
 "desc": "Disputed or unauthorised card transactions. Runs the one hour fraud SLA, "
         "routes investigation to Fraud Operations and enforces the chargeback evidence pack.",
 "bpf": "phone", "startstage": "Identify", "sla": "Fraud Dispute 1-Hour Response",
 "package": "Fraud Dispute Pack", "fr": 0.5, "res": 1, "priority": 1,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "2", "Fraud Dispute"),
 ],
 "tasks": [
   (1, "Block card and confirm exposure", "Identify", 1, "Fraud Operations",
    1, 1, 0.5, 50, 5, True, True,
    "Block the affected card immediately and confirm the total disputed amount."),
   (2, "Capture signed dispute declaration", "Identify", 1, "Contact Centre Tier 1",
    4, 2, 2, 75, 2, True, True,
    "Send the dispute declaration to the customer and chase until signed."),
   (3, "Collect transaction evidence", "Research", 1, "Fraud Operations",
    8, 2, 4, 75, 3, True, True,
    "Pull the statement extract, device and location data for the disputed transactions."),
   (4, "Risk and pattern assessment", "Research", 5, None,
    24, 3, 8, 75, 3, True, True,
    "Assess whether this is an isolated event or part of a wider pattern."),
   (5, "Raise chargeback with scheme", "Resolve", 1, "Fraud Operations",
    48, 3, 24, 80, 3, True, True,
    "Submit the chargeback to the card scheme and record the reference."),
   (6, "Provisional credit and customer update", "Resolve", 1, "Correspondence",
    24, 3, 12, 80, 2, False, True,
    "Apply provisional credit where eligible and notify the customer."),
 ],
},
{
 "name": "Corporate Escalation", "rank": 15, "status": 2,
 "desc": "Any high priority case raised by a Corporate customer. Adds executive oversight, "
         "an impact assessment and a remediation plan.",
 "bpf": "phone", "startstage": "Identify", "sla": "Premier 4-Hour Response",
 "package": "Corporate Escalation Pack", "fr": 1, "res": 8, "priority": 1,
 "rules": [
   (1, 1, "cpc_customersegment", "Customer Segment", 1, "4", "Corporate"),
   (2, 2, "prioritycode", "Priority", 3, "1", "High"),
 ],
 "tasks": [
   (1, "Notify relationship manager", "Identify", 5, None,
    1, 1, 1, 50, 2, True, True,
    "Alert the relationship manager before the client escalates further."),
   (2, "Produce executive summary brief", "Identify", 1, "Complaints Management",
    8, 1, 4, 75, 3, True, True,
    "One page brief covering what happened, who is affected and the current position."),
   (3, "Impact assessment", "Research", 1, "Complaints Management",
    24, 2, 12, 75, 3, True, True,
    "Quantify financial, operational and reputational impact."),
   (4, "Agree remediation plan with client", "Resolve", 5, None,
    48, 3, 24, 80, 3, True, True,
    "Walk the client through the remediation plan and agree milestones."),
   (5, "Executive sign off", "Resolve", 4, "Complaints Queue",
    72, 3, 24, 80, 3, False, True,
    "Route to the executive queue for final sign off before closure."),
 ],
},
{
 "name": "Retail Onboarding - KYC", "rank": 30, "status": 2,
 "desc": "New retail or SME account opening. Drives the KYC document pack and the "
         "two day onboarding SLA.",
 "bpf": "phone", "startstage": "Identify", "sla": "Onboarding 2-Day Response",
 "package": "KYC Onboarding Pack", "fr": 8, "res": 48, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "3", "Onboarding / KYC"),
   (2, 2, "cpc_customersegment", "Customer Segment", 3, "3;5", "Retail or SME"),
 ],
 "tasks": [
   (1, "Send document checklist to customer", "Identify", 1, "Onboarding Operations",
    8, 1, 4, 75, 2, True, True,
    "Send the KYC checklist and explain what each document is for."),
   (2, "Validate identification documents", "Research", 1, "Onboarding Operations",
    48, 2, 24, 75, 2, True, True,
    "Check the identification documents are valid, legible and unexpired."),
   (3, "Sanctions and PEP screening", "Research", 1, "Onboarding Operations",
    48, 2, 24, 75, 3, True, True,
    "Run screening and record the result against the case."),
   (4, "Risk rating and approval", "Resolve", 5, None,
    72, 3, 24, 80, 3, True, True,
    "Assign the customer risk rating and approve or refer the application."),
   (5, "Activate account and welcome pack", "Resolve", 1, "Onboarding Operations",
    96, 3, 24, 80, 2, False, True,
    "Activate the account and issue the welcome pack."),
 ],
},
{
 "name": "Service Request - Standard", "rank": 90, "status": 2,
 "desc": "Catch all for standard service requests and billing queries. "
         "Lightweight two task process on the twenty four hour SLA.",
 "bpf": "phone", "startstage": "Identify", "sla": "Standard 24-Hour Response",
 "package": "Service Request Pack", "fr": 4, "res": 24, "priority": 0,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 3, "4;7", "Service Request or Billing Query"),
 ],
 "tasks": [
   (1, "Acknowledge and confirm the request", "Identify", 1, "Contact Centre Tier 1",
    4, 1, 4, 75, 2, True, True,
    "Confirm what the customer needs and set expectations on timing."),
   (2, "Complete the request", "Research", 1, "Contact Centre Tier 1",
    24, 1, 24, 75, 2, True, True,
    "Carry out the request and record the evidence of completion."),
   (3, "Confirm completion with customer", "Resolve", 6, None,
    28, 3, 4, 80, 1, False, False,
    "Close the loop with the customer before resolving the case."),
 ],
},
{
 "name": "Technical Issue - Field Visit", "rank": 40, "status": 1,
 "desc": "Draft template. Technical issues that need an engineer on site. "
         "Uses the Case to Work Order business process.",
 "bpf": "workorder", "startstage": "Identify", "sla": "Standard 24-Hour Response",
 "package": "Field Service Pack", "fr": 4, "res": 72, "priority": 2,
 "rules": [
   (1, 1, "cpc_casecategory", "Case Category", 1, "6", "Technical Issue"),
 ],
 "tasks": [
   (1, "Triage the fault remotely", "Identify", 1, "Contact Centre Tier 1",
    4, 1, 2, 75, 2, True, True,
    "Attempt remote resolution before dispatching an engineer."),
   (2, "Confirm site access", "Research", 1, "Field Service Dispatch",
    12, 2, 8, 75, 2, True, True,
    "Confirm the site contact, access hours and any permits required."),
   (3, "Schedule the engineer", "Schedule Work Order", 1, "Field Service Dispatch",
    24, 2, 12, 75, 3, True, True,
    "Book the work order slot and notify the customer."),
   (4, "Close out the work order", "Close Work Order", 1, "Field Service Dispatch",
    96, 3, 24, 80, 2, False, True,
    "Capture the engineer work sheet and close the work order."),
 ],
},
]


def upsert_package(name, items):
    pkg = dv.find_one(f"{P}_documentpackages", f"{P}_name eq '{name}'", f"{P}_documentpackageid")
    if pkg:
        pid = pkg[f"{P}_documentpackageid"]
    else:
        pid = dv.new_id(dv.post(f"{P}_documentpackages", {
            f"{P}_name": name, f"{P}_active": True,
            f"{P}_description": f"Documents required for the {name.lower()}."}))
        print("  + package", name)
    existing = {r[f"{P}_name"]: r for r in dv.get(
        f"{P}_documentitems?$select={P}_name,{P}_documentitemid&$filter=_{P}_package_value eq {pid}")["value"]}
    ids = {}
    for iname, seq, mand, resp, due, tmpl, team in items:
        if iname in existing:
            ids[iname] = existing[iname][f"{P}_documentitemid"]
            continue
        body = {f"{P}_name": iname, f"{P}_sequence": seq, f"{P}_mandatory": mand,
                f"{P}_responsible": resp, f"{P}_duehours": due,
                f"{P}_package@odata.bind": f"/{P}_documentpackages({pid})"}
        if tmpl:
            body[f"{P}_templatefile"] = tmpl
        if team and team in TEAM:
            body[f"{P}_ownerteam@odata.bind"] = f"/teams({TEAM[team]})"
        ids[iname] = dv.new_id(dv.post(f"{P}_documentitems", body))
    return pid


def upsert_template(t):
    ex = dv.find_one(f"{P}_caseprocesstemplates", f"{P}_name eq '{t['name']}'",
                     f"{P}_caseprocesstemplateid")
    bpf = BPF if t["bpf"] == "phone" else BPF_WO
    stages = STAGES if t["bpf"] == "phone" else STAGES_WO
    body = {
        f"{P}_name": t["name"], f"{P}_rank": t["rank"], f"{P}_publishstatus": t["status"],
        f"{P}_description": t["desc"], f"{P}_matchlogic": 3,
        f"{P}_bpfid": bpf["workflowid"], f"{P}_bpfname": bpf["name"],
        f"{P}_bpfentityname": bpf["uniquename"],
        f"{P}_startstageid": stages[t["startstage"]], f"{P}_startstagename": t["startstage"],
        f"{P}_firstresponsehours": t["fr"], f"{P}_resolutionhours": t["res"],
        f"{P}_setcasepriority": t["priority"], f"{P}_appliedcount": 0,
        f"{P}_effectivefrom": NOW,
        f"{P}_documentpackage@odata.bind": f"/{P}_documentpackages({PKG[t['package']]})",
    }
    if t["sla"] in SLA:
        body[f"{P}_sla@odata.bind"] = f"/slas({SLA[t['sla']]})"
    if ex:
        tid = ex[f"{P}_caseprocesstemplateid"]
        dv.patch(f"{P}_caseprocesstemplates({tid})", body)
        print("  ~ template", t["name"])
    else:
        tid = dv.new_id(dv.post(f"{P}_caseprocesstemplates", body))
        print("  + template", t["name"])

    have = {r[f"{P}_name"] for r in dv.get(
        f"{P}_matchrules?$select={P}_name&$filter=_{P}_template_value eq {tid}")["value"]}
    for seq, grp, attr, lbl, op, val, vlbl in t["rules"]:
        rn = f"{t['name']} :: {lbl}"
        if rn in have:
            continue
        dv.post(f"{P}_matchrules", {
            f"{P}_name": rn, f"{P}_sequence": seq, f"{P}_groupnumber": grp,
            f"{P}_attributename": attr, f"{P}_attributelabel": lbl,
            f"{P}_operator": op, f"{P}_value": val, f"{P}_valuelabel": vlbl,
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})"})

    have_tasks = {r[f"{P}_name"]: r[f"{P}_processtaskid"] for r in dv.get(
        f"{P}_processtasks?$select={P}_name,{P}_processtaskid&$filter=_{P}_template_value eq {tid}")["value"]}
    prev = None
    for (seq, tname, stage, atype, assignee, due, slastart, slatarget,
         warn, breach, blocks, mand, instr) in t["tasks"]:
        if tname in have_tasks:
            prev = have_tasks[tname]
            continue
        body = {
            f"{P}_name": tname, f"{P}_sequence": seq, f"{P}_description": instr,
            f"{P}_stagename": stage, f"{P}_stageid": stages.get(stage, ""),
            f"{P}_assigntype": atype, f"{P}_duehours": due,
            f"{P}_slastartwhen": slastart, f"{P}_slatargethours": slatarget,
            f"{P}_slawarnpercent": warn, f"{P}_onbreach": breach,
            f"{P}_blocksstage": blocks, f"{P}_mandatory": mand,
            f"{P}_calendarname": CAL, f"{P}_pauseonwaiting": True,
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        if atype == 1 and assignee in TEAM:
            body[f"{P}_team@odata.bind"] = f"/teams({TEAM[assignee]})"
            body[f"{P}_fallbackteam@odata.bind"] = f"/teams({TEAM['Complaints Management']})"
        elif atype == 3 and assignee:
            body[f"{P}_rolename"] = assignee
        elif atype == 4 and assignee in QUEUE:
            body[f"{P}_queue@odata.bind"] = f"/queues({QUEUE[assignee]})"
        if prev:
            body[f"{P}_predecessor@odata.bind"] = f"/{P}_processtasks({prev})"
        prev = dv.new_id(dv.post(f"{P}_processtasks", body))
    return tid


if __name__ == "__main__":
    print("Document packages")
    PKG = {name: upsert_package(name, items) for name, items in PACKAGES.items()}
    print("Templates")
    for t in TEMPLATES:
        upsert_template(t)
    print("done")

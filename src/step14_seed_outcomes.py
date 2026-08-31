"""Step 14: turn the seeded templates into real outcome graphs and lay them out on the canvas.

Explicit graphs are defined for the templates that show off branching, retry loops and stage skips.
Everything else gets a sensible linear chain so no template is left without outcomes.
"""
import dv

P = dv.PREFIX

POS = 1  # sentiment: positive
NEU = 2
NEG = 3
END = 4  # terminal

# Extra tasks that only exist to make a branch meaningful.
# template -> list of (name, stage, sequence, assigntype, assignee, duehours, slahours, instructions)
EXTRA_TASKS = {
    "Premier Complaint (High Priority)": [
        ("Chase customer for outstanding evidence", "Research", 7, 1, "Contact Centre Tier 1",
         24, 12, "The customer has not supplied the agreed evidence. Chase daily and hold the case."),
    ],
    "Fraud Dispute - Card": [
        ("Refer to financial crime investigations", "Research", 7, 1, "Fraud Operations",
         48, 24, "Pattern suggests organised fraud. Hand over to financial crime with the full evidence pack."),
    ],
    "Retail Onboarding - KYC": [
        ("Request corrected documents from customer", "Research", 6, 1, "Onboarding Operations",
         48, 24, "One or more documents failed validation. Tell the customer exactly what to resupply."),
        ("Enhanced due diligence review", "Research", 7, 5, None,
         72, 48, "Screening produced a hit. Complete enhanced due diligence before any approval."),
    ],
}

# template -> list of (from task, outcome label, sentiment, to task or None, flags, guidance)
# flags: advance = advance BPF stage, close = resolve the case, default = preselected,
#        comment = comment required, stage:<Name> = jump to a specific stage
GRAPHS = {
"Premier Complaint (High Priority)": [
    ("Acknowledge customer and log complaint", "Complaint confirmed", POS,
     "Verify customer identity", ["default"],
     "The customer confirmed the details and wants the complaint investigated."),
    ("Acknowledge customer and log complaint", "Actually a service request", NEU,
     None, ["close", "comment"],
     "Not a complaint. Log the service request separately and close this case."),

    ("Verify customer identity", "Identity verified", POS,
     "Collect complaint evidence", ["default", "advance"],
     "Verification passed. The investigation can start."),
    ("Verify customer identity", "Verification failed - call back", NEG,
     "Acknowledge customer and log complaint", ["comment"],
     "Could not verify. Go back and re-contact the customer through a trusted channel."),

    ("Collect complaint evidence", "Evidence complete", POS,
     "Root cause investigation", ["default"],
     "Everything needed to investigate is on the case."),
    ("Collect complaint evidence", "Customer evidence outstanding", NEG,
     "Chase customer for outstanding evidence", [],
     "The customer still owes documents. Park the investigation and chase."),

    ("Chase customer for outstanding evidence", "Evidence received", POS,
     "Collect complaint evidence", ["default"],
     "The customer supplied the documents. Re-run the evidence check."),
    ("Chase customer for outstanding evidence", "No response - close as abandoned", END,
     None, ["close", "comment"],
     "The customer stopped engaging after repeated chasing."),

    ("Root cause investigation", "Bank at fault - redress due", NEG,
     "Complaints manager approval", ["default", "advance"],
     "A control failed. Redress needs manager approval before it is offered."),
    ("Root cause investigation", "No fault found", NEU,
     "Issue final response letter", ["advance"],
     "Nothing went wrong. Skip approval and go straight to the final response."),

    ("Complaints manager approval", "Approved", POS,
     "Issue final response letter", ["default"],
     "The manager approved the outcome and any redress."),
    ("Complaints manager approval", "Rejected - reinvestigate", NEG,
     "Root cause investigation", ["comment", "stage:Research"],
     "The manager was not satisfied. The investigation goes back a stage."),

    ("Issue final response letter", "Final response sent", POS,
     None, ["default", "close"],
     "The final response has been sent and the complaint is closed."),
],

"Fraud Dispute - Card": [
    ("Block card and confirm exposure", "Card blocked", POS,
     "Capture signed dispute declaration", ["default"], "The card is blocked and exposure is known."),
    ("Block card and confirm exposure", "Transaction recognised by customer", NEU,
     None, ["close", "comment"], "The customer recognises the transaction. No dispute to raise."),

    ("Capture signed dispute declaration", "Declaration received", POS,
     "Collect transaction evidence", ["default", "advance"], "Signed declaration is on file."),
    ("Capture signed dispute declaration", "Customer will not sign", END,
     None, ["close", "comment"], "Without a signed declaration the dispute cannot proceed."),

    ("Collect transaction evidence", "Evidence gathered", POS,
     "Risk and pattern assessment", ["default"], "Statement, device and location data are attached."),

    ("Risk and pattern assessment", "Isolated incident", NEU,
     "Raise chargeback with scheme", ["default", "advance"], "A one off event. Proceed to chargeback."),
    ("Risk and pattern assessment", "Part of a wider fraud pattern", NEG,
     "Refer to financial crime investigations", ["comment"],
     "Linked to other cases. Financial crime must take this over."),

    ("Refer to financial crime investigations", "Referral accepted", POS,
     "Raise chargeback with scheme", ["default", "advance"], "Financial crime has the case; still recover the funds."),

    ("Raise chargeback with scheme", "Chargeback raised", POS,
     "Provisional credit and customer update", ["default"], "The scheme has accepted the chargeback."),
    ("Raise chargeback with scheme", "Outside scheme time limits", NEG,
     "Provisional credit and customer update", ["comment"],
     "Too late to recover through the scheme. The customer still needs an answer."),

    ("Provisional credit and customer update", "Customer updated and credited", POS,
     None, ["default", "close"], "Funds credited and the customer has been told the outcome."),
],

"Retail Onboarding - KYC": [
    ("Send document checklist to customer", "Documents received", POS,
     "Validate identification documents", ["default", "advance"], "The customer returned the checklist."),
    ("Send document checklist to customer", "Customer withdrew", END,
     None, ["close", "comment"], "The customer no longer wants to open the account."),

    ("Validate identification documents", "Documents valid", POS,
     "Sanctions and PEP screening", ["default"], "Identification passed validation."),
    ("Validate identification documents", "Documents rejected", NEG,
     "Request corrected documents from customer", [], "One or more documents failed validation."),

    ("Request corrected documents from customer", "Replacements received", POS,
     "Validate identification documents", ["default"], "Re-run validation on the new documents."),
    ("Request corrected documents from customer", "Nothing received", END,
     None, ["close", "comment"], "The customer never resupplied. Close the application."),

    ("Sanctions and PEP screening", "Clear", POS,
     "Risk rating and approval", ["default", "advance"], "No screening hits."),
    ("Sanctions and PEP screening", "Screening hit", NEG,
     "Enhanced due diligence review", ["comment"], "A hit needs enhanced due diligence."),

    ("Enhanced due diligence review", "Cleared after review", POS,
     "Risk rating and approval", ["default", "advance"], "The hit was a false positive or acceptable."),
    ("Enhanced due diligence review", "Decline the relationship", END,
     None, ["close", "comment"], "Risk appetite does not allow this relationship."),

    ("Risk rating and approval", "Approved", POS,
     "Activate account and welcome pack", ["default"], "Risk rated and approved."),
    ("Risk rating and approval", "Declined", END,
     None, ["close", "comment"], "The application was declined at approval."),

    ("Activate account and welcome pack", "Account live", POS,
     None, ["default", "close"], "The account is open and the welcome pack has gone out."),
],
}


def load_templates():
    return {t[f"{P}_name"]: t[f"{P}_caseprocesstemplateid"] for t in dv.get(
        f"{P}_caseprocesstemplates?$select={P}_name,{P}_caseprocesstemplateid")["value"]}


def load_tasks(tid):
    return {t[f"{P}_name"]: t for t in dv.get(
        f"{P}_processtasks?$select={P}_name,{P}_processtaskid,{P}_stagename,{P}_sequence"
        f"&$filter=_{P}_template_value eq {tid}")["value"]}


def stage_order(tid):
    t = dv.get(f"{P}_caseprocesstemplates({tid})?$select={P}_bpfid")
    pid = t.get(f"{P}_bpfid")
    if not pid:
        return []
    rows = dv.get(f"processstages?$select=stagename,stagecategory&$filter=_processid_value eq {pid}")["value"]
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: x.get("stagecategory") or 0):
        n = r["stagename"]
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def add_extra_tasks(tname, tid, teams):
    for name, stage, seq, atype, assignee, due, sla, instr in EXTRA_TASKS.get(tname, []):
        ex = dv.find_one(f"{P}_processtasks",
                         f"{P}_name eq '{name}' and _{P}_template_value eq {tid}",
                         f"{P}_processtaskid")
        if ex:
            continue
        body = {
            f"{P}_name": name, f"{P}_sequence": seq, f"{P}_description": instr,
            f"{P}_stagename": stage, f"{P}_assigntype": atype,
            f"{P}_duehours": due, f"{P}_slatargethours": sla,
            f"{P}_slastartwhen": 4, f"{P}_slawarnpercent": 75, f"{P}_onbreach": 2,
            f"{P}_blocksstage": True, f"{P}_mandatory": True, f"{P}_pauseonwaiting": True,
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        if atype == 1 and assignee in teams:
            body[f"{P}_team@odata.bind"] = f"/teams({teams[assignee]})"
        dv.post(f"{P}_processtasks", body)
        print("    + extra task", name)


def layout(tid, tasks, stages, edges):
    """Column per stage, row assigned by walking the graph so branches sit side by side."""
    cols = {s: i for i, s in enumerate(stages)}
    used = {}
    order = sorted(tasks.values(), key=lambda t: t[f"{P}_sequence"] or 0)
    for t in order:
        stage = t.get(f"{P}_stagename") or (stages[0] if stages else "")
        c = cols.get(stage, 0)
        row = used.get(c, 0)
        used[c] = row + 1
        x = 160 + c * 280
        y = 140 + row * 190
        dv.patch(f"{P}_processtasks({t[f'{P}_processtaskid']})",
                 {f"{P}_posx": x, f"{P}_posy": y})


def apply_graph(tname, tid, spec, teams):
    add_extra_tasks(tname, tid, teams)
    tasks = load_tasks(tid)

    missing = {n for e in spec for n in (e[0], e[3]) if n and n not in tasks}
    if missing:
        print("    ! unknown task(s):", missing)

    existing = dv.get(f"{P}_taskoutcomes?$select={P}_taskoutcomeid"
                      f"&$filter=_{P}_template_value eq {tid}")["value"]
    for o in existing:
        dv.call("DELETE", f"{P}_taskoutcomes({o[f'{P}_taskoutcomeid']})")

    entry = spec[0][0]
    for name, t in tasks.items():
        dv.patch(f"{P}_processtasks({t[f'{P}_processtaskid']})", {f"{P}_isstart": name == entry})

    seq = 0
    for frm, lbl, sent, to, flags, guidance in spec:
        if frm not in tasks:
            continue
        seq += 1
        body = {
            f"{P}_name": lbl, f"{P}_description": guidance, f"{P}_sequence": seq,
            f"{P}_sentiment": sent,
            f"{P}_advancestage": "advance" in flags,
            f"{P}_closecase": "close" in flags,
            f"{P}_requirecomment": "comment" in flags,
            f"{P}_isdefault": "default" in flags,
            f"{P}_setcasepriority": 0,
            f"{P}_task@odata.bind": f"/{P}_processtasks({tasks[frm][f'{P}_processtaskid']})",
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        jump = next((f.split(":", 1)[1] for f in flags if f.startswith("stage:")), None)
        if jump:
            body[f"{P}_targetstagename"] = jump
        if to and to in tasks:
            body[f"{P}_nexttask@odata.bind"] = f"/{P}_processtasks({tasks[to][f'{P}_processtaskid']})"
        dv.post(f"{P}_taskoutcomes", body)

    layout(tid, load_tasks(tid), stage_order(tid), spec)
    print(f"    {seq} outcome(s)")


def linear_graph(tid):
    """Fallback for templates without an explicit graph: complete / cannot complete per task."""
    tasks = sorted(load_tasks(tid).values(), key=lambda t: t[f"{P}_sequence"] or 0)
    if not tasks:
        return
    existing = dv.get(f"{P}_taskoutcomes?$select={P}_taskoutcomeid"
                      f"&$filter=_{P}_template_value eq {tid}")["value"]
    for o in existing:
        dv.call("DELETE", f"{P}_taskoutcomes({o[f'{P}_taskoutcomeid']})")

    for i, t in enumerate(tasks):
        dv.patch(f"{P}_processtasks({t[f'{P}_processtaskid']})", {f"{P}_isstart": i == 0})
        nxt = tasks[i + 1] if i + 1 < len(tasks) else None
        last = nxt is None
        body = {
            f"{P}_name": "Completed" if not last else "Request fulfilled",
            f"{P}_description": "The task was completed as expected.",
            f"{P}_sequence": i * 2 + 1, f"{P}_sentiment": POS,
            f"{P}_advancestage": bool(nxt and nxt.get(f"{P}_stagename") != t.get(f"{P}_stagename")),
            f"{P}_closecase": last, f"{P}_isdefault": True, f"{P}_requirecomment": False,
            f"{P}_setcasepriority": 0,
            f"{P}_task@odata.bind": f"/{P}_processtasks({t[f'{P}_processtaskid']})",
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        }
        if nxt:
            body[f"{P}_nexttask@odata.bind"] = f"/{P}_processtasks({nxt[f'{P}_processtaskid']})"
        dv.post(f"{P}_taskoutcomes", body)

        dv.post(f"{P}_taskoutcomes", {
            f"{P}_name": "Cannot proceed", f"{P}_sentiment": END,
            f"{P}_description": "Blocked and cannot be taken further. Record why.",
            f"{P}_sequence": i * 2 + 2, f"{P}_requirecomment": True,
            f"{P}_closecase": False, f"{P}_advancestage": False, f"{P}_isdefault": False,
            f"{P}_setcasepriority": 1,
            f"{P}_task@odata.bind": f"/{P}_processtasks({t[f'{P}_processtaskid']})",
            f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({tid})",
        })

    layout(tid, load_tasks(tid), stage_order(tid), [])
    print(f"    linear graph, {len(tasks)} task(s)")


def main():
    teams = {t["name"]: t["teamid"] for t in dv.get("teams?$select=teamid,name")["value"]}
    templates = load_templates()
    for name, tid in templates.items():
        print("==", name)
        if name in GRAPHS:
            apply_graph(name, tid, GRAPHS[name], teams)
        else:
            # Never flatten a graph that was authored elsewhere (designer, step19, a maker).
            has = dv.get(f"{P}_taskoutcomes?$select={P}_taskoutcomeid&$top=1"
                         f"&$filter=_{P}_template_value eq {tid}")["value"]
            if has:
                print("    has outcomes already, left alone")
            else:
                linear_graph(tid)
    dv.publish_all()
    print("done")


if __name__ == "__main__":
    main()

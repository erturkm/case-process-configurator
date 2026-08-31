"""Step 20: live end to end test of the corporate credit lifecycle.

Creates a real corporate credit case, then walks the outcome graph the way a credit officer would:
read the outcomes the engine published on each open task, record one, and assert that the correct
next task appears in the correct stage with the correct owner - and that the BPF advances.

Three scenarios are walked:
  A  committee route with a deferral loop, ending at a performing facility
  B  delegated authority route, ending at an accelerated facility after a covenant breach
  C  a hard decline at origination, proving terminal outcomes close the case

Safe to re-run. Cases it creates are prefixed "TEST CC" so they are easy to find and delete.
"""
import json
import sys
import time

import dv

P = dv.PREFIX
TEMPLATE = "Corporate Credit Lifecycle - New Facility"
BPF_SET = "cpc_corporatecreditlifecycles"   # entity set of the custom BPF
CATEGORY_CORPORATE_CREDIT = 8
SEGMENT_CORPORATE = 4

SETTLE = 6      # seconds to let the async create plug-in finish
STEP = 5        # seconds to let the outcome plug-in create the next task

failures = []
_case_ids = []


# ------------------------------------------------------------------ helpers
def check(label, ok, detail=""):
    print(("   PASS  " if ok else "   FAIL  ") + label + (("  -> " + detail) if detail else ""))
    if not ok:
        failures.append(label + ((" :: " + detail) if detail else ""))
    return ok


def make_case(title):
    acct = dv.find_one("accounts", "name eq 'Meridian Industrial Group'", "accountid")
    if acct:
        aid = acct["accountid"]
    else:
        aid = dv.new_id(dv.post("accounts", {
            "name": "Meridian Industrial Group",
            "description": "Corporate borrower used by the credit lifecycle demo."}))
    cid = dv.new_id(dv.post("incidents", {
        "title": title,
        "customerid_account@odata.bind": f"/accounts({aid})",
        f"{P}_casecategory": CATEGORY_CORPORATE_CREDIT,
        f"{P}_customersegment": SEGMENT_CORPORATE,
        "prioritycode": 2,
    }))
    _case_ids.append(cid)
    return cid


_tmpl_names = {}


def template_name(row):
    """cpc_appliedtemplatename exists in metadata only as the lookup's child attribute and cannot
    be $selected, and this org does not return formatted values for it either, so resolve the
    lookup guid against the template table and cache the answer."""
    tid = row.get(f"_{P}_appliedtemplate_value")
    if not tid:
        return None
    if tid not in _tmpl_names:
        _tmpl_names[tid] = dv.get(f"{P}_caseprocesstemplates({tid})"
                                  f"?$select={P}_name")[f"{P}_name"]
    return _tmpl_names[tid]


def case_row(case_id):
    return dv.get(f"incidents({case_id})?$select=title,statecode,ticketnumber,"
                  f"_{P}_appliedtemplate_value,{P}_processsummary,"
                  f"{P}_taskstotal,{P}_tasksopen,{P}_docstotal,{P}_docsreceived,"
                  f"{P}_firstresponsedue,{P}_resolutiondue,{P}_processappliedon,prioritycode")


def open_tasks(case_id):
    return dv.get(f"tasks?$select=activityid,subject,{P}_stagename,{P}_sladue,scheduledend,"
                  f"{P}_assignedteamname,{P}_availableoutcomes,{P}_branchpath,{P}_sequence"
                  f"&$filter=_regardingobjectid_value eq {case_id} and statecode eq 0"
                  f"&$orderby={P}_sequence")["value"]


def all_tasks(case_id):
    return dv.get(f"tasks?$select=subject,statecode,{P}_outcomelabel,{P}_stagename"
                  f"&$filter=_regardingobjectid_value eq {case_id}")["value"]


def owner_label(task):
    """cpc_assignedteamname is a display string that carries its assignment kind as a prefix,
    for example "Team: Credit Risk". Compare on the bare name."""
    raw = task.get(f"{P}_assignedteamname") or ""
    return raw.split(":", 1)[1].strip() if ":" in raw else raw.strip()


def outcomes_of(task):
    return json.loads(task.get(f"{P}_availableoutcomes") or "[]")


def stage_of(case_id):
    """The engine stamps incident.stageid, which is the cheapest source of the live stage."""
    row = dv.get(f"incidents({case_id})?$select=stageid")
    sid = row.get("stageid")
    if not sid:
        # Custom business process flow instance entities name the case lookup bpf_incidentid;
        # only the out of the box Phone to Case entity calls it incidentid.
        inst = dv.get(f"{BPF_SET}?$select=_activestageid_value"
                      f"&$filter=_bpf_incidentid_value eq {case_id}")["value"]
        sid = inst[0].get("_activestageid_value") if inst else None
    if not sid:
        return None
    return dv.get(f"processstages({sid})?$select=stagename")["stagename"]


def record(task, label, comment=None):
    body = {f"{P}_outcomelabel": label, "statecode": 1, "statuscode": 5}
    if comment:
        body[f"{P}_outcomecomment"] = comment
    dv.patch(f"tasks({task['activityid']})", body)
    time.sleep(STEP)


def find_open(case_id, name):
    return next((t for t in open_tasks(case_id) if t["subject"] == name), None)


def show(case_id, header):
    print("\n  " + header + "   [stage: %s]" % stage_of(case_id))
    for t in open_tasks(case_id):
        labels = [o["label"] for o in outcomes_of(t)]
        print(f"     OPEN  {t['subject']}")
        print(f"           stage={t.get(f'{P}_stagename')}  owner={t.get(f'{P}_assignedteamname')}"
              f"  due={(t.get(f'{P}_sladue') or '')[:16]}")
        print(f"           path={t.get(f'{P}_branchpath')}")
        print(f"           outcomes={labels}")


def advance(case_id, from_task, outcome, expect_next, expect_stage=None,
            expect_owner=None, comment=None):
    """Record an outcome and assert the engine produced the task the graph promised."""
    t = find_open(case_id, from_task)
    if not check(f"open task present: {from_task}", t is not None):
        return None

    labels = [o["label"] for o in outcomes_of(t)]
    check(f"  outcome '{outcome}' is offered on {from_task}", outcome in labels,
          "offered: " + str(labels))

    record(t, outcome, comment)

    if expect_next is None:
        # Terminal outcome: nothing new should be open.
        still = [x["subject"] for x in open_tasks(case_id)]
        check(f"  terminal outcome closed the branch after {from_task}", not still,
              "still open: " + str(still))
        return None

    nxt = find_open(case_id, expect_next)
    ok = check(f"  next task created: {expect_next}", nxt is not None,
               "open now: " + str([x["subject"] for x in open_tasks(case_id)]))
    if not ok:
        return None
    if expect_stage:
        check(f"    in stage {expect_stage}", nxt.get(f"{P}_stagename") == expect_stage,
              "got " + str(nxt.get(f"{P}_stagename")))
    if expect_owner:
        check(f"    owned by {expect_owner}",
              owner_label(nxt) == expect_owner,
              "got " + str(nxt.get(f"{P}_assignedteamname")))
    check("    carries its own outcomes", len(outcomes_of(nxt)) > 0,
          "%d outcomes" % len(outcomes_of(nxt)))
    check("    has an SLA due stamp", bool(nxt.get(f"{P}_sladue")))
    return nxt


def expect_stage(case_id, name):
    got = stage_of(case_id)
    check(f"  BPF stage is now {name}", got == name, "got " + str(got))


# ------------------------------------------------------------------ scenarios
def scenario_a():
    print("=" * 78)
    print("SCENARIO A  Committee route: deferred once, reworked, approved, facility performs")
    print("=" * 78)
    case = make_case("TEST CC - Meridian expansion facility")
    time.sleep(SETTLE)

    c = case_row(case)
    print(f"\n  Case {c.get('ticketnumber')}  template={template_name(c)!r}")
    check("template applied on create", template_name(c) == TEMPLATE, str(template_name(c)))
    check("first response SLA stamped", bool(c.get(f"{P}_firstresponsedue")))
    check("resolution SLA stamped", bool(c.get(f"{P}_resolutiondue")))
    check("document requirements created", (c.get(f"{P}_docstotal") or 0) >= 9,
          "docstotal=%s" % c.get(f"{P}_docstotal"))
    expect_stage(case, "Origination")

    show(case, "After create")
    first = open_tasks(case)
    check("exactly one task open at start", len(first) == 1,
          str([t["subject"] for t in first]))
    check("the start task is the origination capture",
          bool(first) and first[0]["subject"] == "Capture facility request and indicative terms")

    advance(case, "Capture facility request and indicative terms", "Request captured",
            "Collect credit application documents", "Origination", "Credit Origination")
    advance(case, "Collect credit application documents", "Pack complete",
            "Run KYC and sanctions screening", "Origination", "Credit Risk")

    # This outcome carries advance=true, so the BPF should move on.
    advance(case, "Run KYC and sanctions screening", "Screening clear",
            "Spread financials and build the credit model", "Underwriting", "Credit Risk")
    expect_stage(case, "Underwriting")

    advance(case, "Spread financials and build the credit model", "Model complete",
            "Assign internal risk rating", "Underwriting", "Credit Risk")
    advance(case, "Assign internal risk rating", "Rating within appetite",
            "Value and confirm collateral", "Underwriting", "Credit Risk")
    advance(case, "Value and confirm collateral", "Unsecured - proceed on covenants",
            "Draft credit memorandum and recommendation", "Underwriting", "Credit Risk")

    # Branch: route to committee rather than the delegated approver.
    advance(case, "Draft credit memorandum and recommendation", "Requires credit committee",
            "Credit committee review", "Credit Decision", "Credit Committee")
    expect_stage(case, "Credit Decision")
    check("  the delegated approval task was NOT created",
          find_open(case, "Credit approval decision") is None)

    # The deferral loop: committee sends it back, then it returns to the same committee task.
    advance(case, "Credit committee review", "Deferred - rework required",
            "Rework proposal after committee feedback", "Underwriting", "Credit Risk",
            comment="Committee wants a downside case at 20 percent lower EBITDA.")
    advance(case, "Rework proposal after committee feedback", "Reworked and resubmitted",
            "Credit committee review", "Credit Decision", "Credit Committee")
    check("  loop returned to the committee task a second time",
          find_open(case, "Credit committee review") is not None)

    advance(case, "Credit committee review", "Committee approved",
            "Issue offer letter and obtain acceptance", "Documentation", "Credit Origination")
    expect_stage(case, "Documentation")

    advance(case, "Issue offer letter and obtain acceptance", "Offer accepted",
            "Draft and execute facility agreement", "Documentation", "Legal and Documentation")
    advance(case, "Draft and execute facility agreement", "Agreement executed",
            "Perfect security and register charges", "Documentation", "Legal and Documentation")
    advance(case, "Perfect security and register charges", "Security perfected",
            "Verify conditions precedent", "Disbursement", "Loan Operations")
    expect_stage(case, "Disbursement")

    advance(case, "Verify conditions precedent", "All conditions met",
            "Set up limits and release funds", "Disbursement", "Loan Operations")
    advance(case, "Set up limits and release funds", "Funds disbursed",
            "Establish covenant monitoring schedule", "Monitoring", "Portfolio Monitoring")
    expect_stage(case, "Monitoring")

    advance(case, "Establish covenant monitoring schedule", "Schedule in place",
            "First covenant compliance review", "Monitoring", "Portfolio Monitoring")

    show(case, "At the final review")
    advance(case, "First covenant compliance review", "Compliant - facility performing", None)

    time.sleep(SETTLE)
    c = case_row(case)
    check("case resolved by the terminal outcome", c.get("statecode") == 1,
          "statecode=%s" % c.get("statecode"))
    done = [t for t in all_tasks(case) if t["statecode"] == 1]
    check("every task completed", len(done) == len(all_tasks(case)),
          "%d of %d" % (len(done), len(all_tasks(case))))
    print("\n  Tasks walked: %d" % len(done))
    return case


def scenario_b():
    print("\n" + "=" * 78)
    print("SCENARIO B  Delegated authority, backward stage jump, covenant breach, acceleration")
    print("=" * 78)
    case = make_case("TEST CC - Meridian working capital line")
    time.sleep(SETTLE)
    expect_stage(case, "Origination")

    advance(case, "Capture facility request and indicative terms", "Request captured",
            "Collect credit application documents")
    advance(case, "Collect credit application documents", "Pack complete",
            "Run KYC and sanctions screening")
    advance(case, "Run KYC and sanctions screening", "Screening clear",
            "Spread financials and build the credit model")
    expect_stage(case, "Underwriting")

    # Backward jump: a negative outcome with stage:Origination should pull the BPF back.
    advance(case, "Spread financials and build the credit model", "Financials unreliable",
            "Collect credit application documents", "Origination", "Credit Origination",
            comment="Auditor issued a qualified opinion on the FY25 accounts.")
    expect_stage(case, "Origination")
    print("   note: the graph deliberately sends this back a stage for restated figures")

    advance(case, "Collect credit application documents", "Pack complete",
            "Run KYC and sanctions screening")
    advance(case, "Run KYC and sanctions screening", "Screening clear",
            "Spread financials and build the credit model")
    advance(case, "Spread financials and build the credit model", "Model complete",
            "Assign internal risk rating")
    advance(case, "Assign internal risk rating", "Rating within appetite",
            "Value and confirm collateral")
    advance(case, "Value and confirm collateral", "Collateral acceptable",
            "Draft credit memorandum and recommendation")

    # Delegated route this time: manager of the case owner, not the committee team.
    t = advance(case, "Draft credit memorandum and recommendation", "Within delegated authority",
                "Credit approval decision", "Credit Decision")
    check("  the committee task was NOT created",
          find_open(case, "Credit committee review") is None)
    if t:
        check("  delegated approval is assigned to a manager, not a team",
              "manager" in (t.get(f"{P}_assignedteamname") or "").lower(),
              "assignment=" + str(t.get(f"{P}_assignedteamname")))

    advance(case, "Credit approval decision", "Approved with conditions",
            "Issue offer letter and obtain acceptance", "Documentation",
            comment="Approved subject to a 25 percent cash margin on all LCs.")
    advance(case, "Issue offer letter and obtain acceptance", "Offer accepted",
            "Draft and execute facility agreement")
    advance(case, "Draft and execute facility agreement", "Agreement executed",
            "Perfect security and register charges")

    # Negative but non-terminal: registration delayed still moves forward.
    advance(case, "Perfect security and register charges", "Registration delayed",
            "Verify conditions precedent", comment="Land department registration pending.")

    # Backward jump inside documentation.
    advance(case, "Verify conditions precedent", "Conditions outstanding",
            "Perfect security and register charges", "Documentation",
            comment="Insurance assignment not yet received.")
    expect_stage(case, "Documentation")

    advance(case, "Perfect security and register charges", "Security perfected",
            "Verify conditions precedent", "Disbursement")
    advance(case, "Verify conditions precedent", "All conditions met",
            "Set up limits and release funds")
    advance(case, "Set up limits and release funds", "Facility not drawn",
            "Establish covenant monitoring schedule", "Monitoring")
    advance(case, "Establish covenant monitoring schedule", "Schedule in place",
            "First covenant compliance review")

    # Breach loop: review -> remediate -> waiver -> review again -> breach -> accelerate.
    advance(case, "First covenant compliance review", "Covenant breached",
            "Remediate covenant breach", "Monitoring", "Credit Risk",
            comment="Net leverage 4.1x against a 3.5x covenant.")
    advance(case, "Remediate covenant breach", "Waiver granted",
            "First covenant compliance review", "Monitoring", "Portfolio Monitoring")
    check("  the breach loop returned to the review task",
          find_open(case, "First covenant compliance review") is not None)

    advance(case, "First covenant compliance review", "Reporting overdue",
            "Remediate covenant breach", "Monitoring", "Credit Risk",
            comment="No compliance certificate received for two consecutive quarters.")
    advance(case, "Remediate covenant breach", "Facility accelerated", None,
            comment="Breach not curable. Facility called and passed to recoveries.")

    time.sleep(SETTLE)
    c = case_row(case)
    check("case resolved by the acceleration outcome", c.get("statecode") == 1,
          "statecode=%s" % c.get("statecode"))
    print("\n  Tasks walked: %d" % len(all_tasks(case)))
    return case


def scenario_c():
    print("\n" + "=" * 78)
    print("SCENARIO C  Declined at origination: a terminal outcome on the very first task")
    print("=" * 78)
    case = make_case("TEST CC - Offshore SPV bridge request")
    time.sleep(SETTLE)

    c = case_row(case)
    check("template applied", template_name(c) == TEMPLATE, str(template_name(c)))
    show(case, "After create")

    t = find_open(case, "Capture facility request and indicative terms")
    if t:
        labels = [o["label"] for o in outcomes_of(t)]
        check("both a positive and a terminal outcome are offered",
              "Request captured" in labels and "Outside credit appetite" in labels,
              str(labels))

    advance(case, "Capture facility request and indicative terms", "Outside credit appetite",
            None, comment="Offshore SPV in a restricted jurisdiction. Outside policy.")

    time.sleep(SETTLE)
    c = case_row(case)
    check("case closed at the first step", c.get("statecode") == 1,
          "statecode=%s" % c.get("statecode"))
    check("no downstream tasks were ever created", len(all_tasks(case)) == 1,
          "%d tasks" % len(all_tasks(case)))
    return case


def cleanup():
    if "--keep" in sys.argv:
        print("\nKeeping %d test case(s) for inspection." % len(_case_ids))
        for c in _case_ids:
            print("  ", dv.ORG + "/main.aspx?pagetype=entityrecord&etn=incident&id=" + c)
        return
    print("\nCleaning up test cases")
    for c in _case_ids:
        for t in all_tasks(c):
            pass
        for t in dv.get(f"tasks?$select=activityid"
                        f"&$filter=_regardingobjectid_value eq {c}")["value"]:
            dv.call("DELETE", f"tasks({t['activityid']})")
        for d in dv.get(f"{P}_caserequireddocuments?$select={P}_caserequireddocumentid"
                        f"&$filter=_{P}_case_value eq {c}")["value"]:
            dv.call("DELETE", f"{P}_caserequireddocuments({d[f'{P}_caserequireddocumentid']})")
        dv.call("DELETE", f"incidents({c})")
    print("  removed %d case(s)" % len(_case_ids))


def main():
    scenario_a()
    scenario_b()
    scenario_c()
    cleanup()

    print("\n" + "=" * 78)
    if failures:
        print("RESULT: %d FAILURE(S)" % len(failures))
        for f in failures:
            print("   -", f)
    else:
        print("RESULT: ALL PASS")
    print("=" * 78)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""Step 15: end to end test of the outcome driven engine.

Creates a Premier complaint, then walks the branch the way an agent would: complete each open task
by recording an outcome and assert that the correct next task appears.
"""
import time
import dv

P = dv.PREFIX


def open_tasks(case_id):
    return dv.get(f"tasks?$select=activityid,subject,{P}_stagename,{P}_sladue,{P}_assignedteamname,"
                  f"{P}_availableoutcomes,{P}_branchpath"
                  f"&$filter=_regardingobjectid_value eq {case_id} and statecode eq 0"
                  f"&$orderby={P}_sequence")["value"]


def all_tasks(case_id):
    return dv.get(f"tasks?$select=subject,statecode,{P}_outcomelabel"
                  f"&$filter=_regardingobjectid_value eq {case_id}")["value"]


def complete(task_id, outcome_label, comment=None):
    body = {f"{P}_outcomelabel": outcome_label, "statecode": 1, "statuscode": 5}
    if comment:
        body[f"{P}_outcomecomment"] = comment
    dv.patch(f"tasks({task_id})", body)


def subject_id(title):
    return dv.find_one("subjects", f"title eq '{title}'", "subjectid")["subjectid"]


def make_case(title, subject, priority):
    c = dv.find_one("contacts", "lastname eq 'Outcome Demo'", "contactid")
    if not c:
        cid = dv.new_id(dv.post("contacts", {"firstname": "Nadia", "lastname": "Outcome Demo",
                                             "emailaddress1": "nadia.demo@contoso.ae"}))
    else:
        cid = c["contactid"]
    return dv.new_id(dv.post("incidents", {
        "title": title,
        "customerid_contact@odata.bind": f"/contacts({cid})",
        "subjectid@odata.bind": f"/subjects({subject_id(subject)})",
        "prioritycode": priority,
    }))


def show(case_id, header):
    print("\n" + header)
    for t in open_tasks(case_id):
        outs = t.get(f"{P}_availableoutcomes") or "[]"
        import json
        labels = [o["label"] for o in json.loads(outs)]
        print(f"   OPEN  {t['subject']}  [{t.get(f'{P}_stagename')}]"
              f"  owner={t.get(f'{P}_assignedteamname')}")
        print(f"         path={t.get(f'{P}_branchpath')}  outcomes={labels}")


def stage_of(case_id):
    inst = dv.get(f"phonetocaseprocesses?$select=businessprocessflowinstanceid,_activestageid_value"
                  f"&$filter=_incidentid_value eq {case_id}")["value"]
    if not inst:
        return None
    sid = inst[0].get("_activestageid_value")
    if not sid:
        return None
    return dv.get(f"processstages({sid})?$select=stagename")["stagename"]


def main():
    failures = []

    print("=" * 78)
    print("SCENARIO A  Premier complaint, bank at fault, manager rejects once")
    print("=" * 78)
    case = make_case("Premier complaint - mis-sold product", "Complaints", 1)
    time.sleep(6)
    show(case, "After create")

    o = open_tasks(case)
    if len(o) != 1 or o[0]["subject"] != "Acknowledge customer and log complaint":
        failures.append(f"A1 expected only the acknowledge task, got {[x['subject'] for x in o]}")
    print("   stage:", stage_of(case))

    complete(o[0]["activityid"], "Complaint confirmed")
    time.sleep(5)
    show(case, "After 'Complaint confirmed'")
    o = open_tasks(case)
    if not any(x["subject"] == "Verify customer identity" for x in o):
        failures.append("A2 verify identity task was not created")

    complete(o[0]["activityid"], "Identity verified")
    time.sleep(5)
    show(case, "After 'Identity verified' (should advance to Research)")
    print("   stage:", stage_of(case))
    if stage_of(case) != "Research":
        failures.append(f"A3 expected stage Research, got {stage_of(case)}")

    o = open_tasks(case)
    if not any(x["subject"] == "Collect complaint evidence" for x in o):
        failures.append("A4 collect evidence task missing")

    # Take the unhappy path first: evidence outstanding -> chase -> back to collect evidence
    complete(o[0]["activityid"], "Customer evidence outstanding")
    time.sleep(5)
    show(case, "After 'Customer evidence outstanding' (retry loop)")
    o = open_tasks(case)
    if not any(x["subject"] == "Chase customer for outstanding evidence" for x in o):
        failures.append("A5 chase task missing")

    complete(o[0]["activityid"], "Evidence received")
    time.sleep(5)
    show(case, "After 'Evidence received' (loops back to collect evidence)")
    o = open_tasks(case)
    if not any(x["subject"] == "Collect complaint evidence" for x in o):
        failures.append("A6 loop back to collect evidence failed")

    complete(o[0]["activityid"], "Evidence complete")
    time.sleep(5)
    o = open_tasks(case)
    if not any(x["subject"] == "Root cause investigation" for x in o):
        failures.append("A7 root cause task missing")

    complete(o[0]["activityid"], "Bank at fault - redress due")
    time.sleep(5)
    show(case, "After 'Bank at fault' (should advance to Resolve, approval required)")
    print("   stage:", stage_of(case))
    o = open_tasks(case)
    if not any(x["subject"] == "Complaints manager approval" for x in o):
        failures.append("A8 manager approval task missing")

    complete(o[0]["activityid"], "Rejected - reinvestigate", "Redress calculation looks wrong.")
    time.sleep(5)
    show(case, "After 'Rejected - reinvestigate' (back to Research)")
    print("   stage:", stage_of(case))
    if stage_of(case) != "Research":
        failures.append(f"A9 expected jump back to Research, got {stage_of(case)}")
    o = open_tasks(case)
    if not any(x["subject"] == "Root cause investigation" for x in o):
        failures.append("A10 reinvestigation task missing")

    complete(o[0]["activityid"], "Bank at fault - redress due")
    time.sleep(5)
    o = open_tasks(case)
    complete(o[0]["activityid"], "Approved")
    time.sleep(5)
    show(case, "After 'Approved'")
    o = open_tasks(case)
    if not any(x["subject"] == "Issue final response letter" for x in o):
        failures.append("A11 final response task missing")

    complete(o[0]["activityid"], "Final response sent")
    time.sleep(6)
    inc = dv.get(f"incidents({case})?$select=statecode,statuscode,title")
    print("\n   Case state after final outcome:", inc["statecode"], "status", inc["statuscode"])
    if inc["statecode"] != 1:
        failures.append(f"A12 case should be resolved, statecode={inc['statecode']}")

    print("\n   Full task journal:")
    for t in all_tasks(case):
        print(f"     [{'done' if t['statecode'] else 'open'}] {t['subject']}"
              f"  -> {t.get(f'{P}_outcomelabel')}")

    print("\n" + "=" * 78)
    print("SCENARIO B  Premier complaint, no fault found (skips manager approval)")
    print("=" * 78)
    case2 = make_case("Premier complaint - statement dispute", "Complaints", 1)
    time.sleep(6)
    o = open_tasks(case2)
    complete(o[0]["activityid"], "Complaint confirmed"); time.sleep(4)
    o = open_tasks(case2)
    complete(o[0]["activityid"], "Identity verified"); time.sleep(4)
    o = open_tasks(case2)
    complete(o[0]["activityid"], "Evidence complete"); time.sleep(4)
    o = open_tasks(case2)
    complete(o[0]["activityid"], "No fault found"); time.sleep(5)
    show(case2, "After 'No fault found' (approval should be skipped)")
    o = open_tasks(case2)
    subs = [x["subject"] for x in o]
    if "Issue final response letter" not in subs:
        failures.append(f"B1 expected final response letter, got {subs}")
    if "Complaints manager approval" in subs:
        failures.append("B2 manager approval should have been skipped")

    print("\n" + "=" * 78)
    print("SCENARIO C  Complaint that turns out to be a service request (early close)")
    print("=" * 78)
    case3 = make_case("Premier complaint - address change", "Complaints", 1)
    time.sleep(6)
    o = open_tasks(case3)
    complete(o[0]["activityid"], "Actually a service request", "Customer just wanted an address change.")
    time.sleep(6)
    inc3 = dv.get(f"incidents({case3})?$select=statecode")
    print("   Case state:", inc3["statecode"], "(1 = resolved)")
    if inc3["statecode"] != 1:
        failures.append(f"C1 case should be resolved early, statecode={inc3['statecode']}")
    if open_tasks(case3):
        failures.append("C2 tasks should not remain open after early close")

    print("\n" + "=" * 78)
    if failures:
        print("RESULT: FAILURES")
        for f in failures:
            print("  -", f)
    else:
        print("RESULT: ALL PASS")
    print("=" * 78)


if __name__ == "__main__":
    main()

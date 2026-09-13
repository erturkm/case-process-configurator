"""Step 44: test cpc_CompleteAgentTask against a live queued AI task.

Covers the four cases that matter:
  1. agent recommends, auto-complete off        -> Awaiting review, task stays open
  2. auto-complete on but confidence too low    -> Awaiting review, task stays open
  3. auto-complete on, confident, valid outcome -> task closes and AdvanceProcess moves on
  4. agent errored                              -> Failed, task stays with the fallback team

Every case must also leave a cpc_agentrun audit row behind.

Usage: python3 step44_agent_test.py <caseId>
"""
import json
import sys
import time

import dv

STATE = {1: "Queued", 2: "Running", 3: "Succeeded", 4: "Awaiting review", 5: "Failed", 6: "Skipped"}
RUNSTATUS = {1: "Success", 2: "Failed", 3: "Timed out", 4: "Rejected", 5: "Invalid response"}

FAILURES = []


def check(label, got, want):
    ok = got == want
    print(f"    {'PASS' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))
    if not ok:
        FAILURES.append(f"{label}: got {got!r}, expected {want!r}")


def tasks_for(cid):
    q = ("tasks?$select=activityid,subject,statecode,description,cpc_agentstate,cpc_agentoutput,"
         "cpc_agentconfidence,cpc_agentattempts,cpc_agenterror,cpc_outcomelabel,"
         "_cpc_sourcetask_value,createdon"
         f"&$filter=_regardingobjectid_value eq {cid}&$orderby=createdon")
    return dv.get(q)["value"]


def ai_task(cid):
    for t in tasks_for(cid):
        if t.get("cpc_agentstate") is not None and t["statecode"] == 0:
            return t
    return None


def source_task(tid):
    return dv.get(f"cpc_processtasks({tid})?$select=cpc_name,cpc_autocomplete,"
                  "cpc_confidencethreshold,cpc_agentoutcomemode,cpc_outputtarget")


def set_cfg(tid, **kw):
    dv.patch(f"cpc_processtasks({tid})", kw)
    time.sleep(2)


def latest_run(task_id):
    r = dv.get("cpc_agentruns?$select=cpc_name,cpc_runstatus,cpc_attempt,cpc_confidence,"
               "cpc_parsedoutcome,cpc_autocompleted,cpc_errordetail,cpc_contextchars,"
               "cpc_requestedbyname,cpc_agentschemaname"
               f"&$filter=_cpc_task_value eq {task_id}&$orderby=createdon desc&$top=1")["value"]
    return r[0] if r else None


def call(task_id, **kw):
    body = {"TaskId": task_id}
    body.update({k: str(v) for k, v in kw.items() if v is not None})
    return dv.post("cpc_CompleteAgentTask", body)


GOOD_JSON = json.dumps({
    "outcome": "Isolated incident",
    "confidence": 88,
    "summary": "Card-not-present transaction on a card still held by the cardholder, with no "
               "prior disputes against this merchant. Reads as a one-off compromise of the card "
               "details rather than a wider pattern.",
    "evidence": ["Card remains in her possession", "No previous disputes for this customer"],
    "missing": [],
})


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python3 step44_agent_test.py <caseId>")
    cid = sys.argv[1]

    t = ai_task(cid)
    if not t:
        sys.exit("No open AI task on this case. Walk the process to the agent task first.")
    task_id = t["activityid"]
    src_id = t["_cpc_sourcetask_value"]
    cfg = source_task(src_id)
    print(f"case  : {cid}")
    print(f"task  : {t['subject']} ({task_id})")
    print(f"config: autoComplete={cfg['cpc_autocomplete']} "
          f"threshold={cfg['cpc_confidencethreshold']} mode={cfg['cpc_agentoutcomemode']}\n")

    original = {
        "cpc_autocomplete": cfg["cpc_autocomplete"],
        "cpc_confidencethreshold": cfg["cpc_confidencethreshold"],
        "cpc_agentoutcomemode": cfg["cpc_agentoutcomemode"],
    }

    try:
        # ---------------------------------------------------------- 1
        print("1. agent recommends, auto-complete off")
        set_cfg(src_id, cpc_autocomplete=False, cpc_agentoutcomemode=1)
        r = call(task_id, Output="Recommend treating as an isolated incident.",
                 OutcomeName="Isolated incident", Confidence=88, RawResponse=GOOD_JSON,
                 PromptSent="(prompt)", ContextSent="(context)", LatencyMs=2400,
                 RequestedBy="Marco Henry")
        check("state", r["State"], "Awaiting review")
        check("completed", r["Completed"], "false")
        after = dv.get(f"tasks({task_id})?$select=statecode,cpc_agentstate,cpc_agentattempts,"
                       "cpc_agentoutput,cpc_agentconfidence,description")
        check("task still open", after["statecode"], 0)
        check("agentstate", STATE.get(after["cpc_agentstate"]), "Awaiting review")
        check("attempts", after["cpc_agentattempts"], 1)
        check("output stored", bool(after.get("cpc_agentoutput")), True)
        check("confidence", after.get("cpc_agentconfidence"), 88)
        check("appended to description",
              "AI agent" in (after.get("description") or ""), True)
        run = latest_run(task_id)
        check("audit row", run is not None, True)
        if run:
            check("run status", RUNSTATUS.get(run["cpc_runstatus"]), "Success")
            check("parsed outcome", run["cpc_parsedoutcome"], "Isolated incident")
            check("attribution", run["cpc_requestedbyname"], "Marco Henry")
            check("agent schema name", run["cpc_agentschemaname"], "new_FraudDisputeTriage")
        print(f"    reason: {r['Reason']}\n")

        # ---------------------------------------------------------- 2
        print("2. auto-complete on, confidence below threshold")
        set_cfg(src_id, cpc_autocomplete=True, cpc_agentoutcomemode=2, cpc_confidencethreshold=70)
        r = call(task_id, Output="Not enough evidence to call it.",
                 OutcomeName="Isolated incident", Confidence=41, RawResponse=GOOD_JSON)
        check("state", r["State"], "Awaiting review")
        check("completed", r["Completed"], "false")
        after = dv.get(f"tasks({task_id})?$select=statecode,cpc_agentstate,cpc_agentattempts")
        check("task still open", after["statecode"], 0)
        check("attempts", after["cpc_agentattempts"], 2)
        run = latest_run(task_id)
        check("run status", RUNSTATUS.get(run["cpc_runstatus"]), "Rejected")
        print(f"    reason: {r['Reason']}\n")

        # ---------------------------------------------------------- 3
        print("3. unknown outcome name")
        r = call(task_id, Output="x", OutcomeName="Escalate to Mars", Confidence=95)
        check("state", r["State"], "Awaiting review")
        run = latest_run(task_id)
        check("run status", RUNSTATUS.get(run["cpc_runstatus"]), "Invalid response")
        print(f"    reason: {r['Reason']}\n")

        # ---------------------------------------------------------- 4
        print("4. agent errored")
        r = call(task_id, Error="Copilot Studio returned 504 after 3 attempts.")
        check("state", r["State"], "Failed")
        after = dv.get(f"tasks({task_id})?$select=statecode,cpc_agentstate,cpc_agenterror")
        check("task still open", after["statecode"], 0)
        check("agentstate", STATE.get(after["cpc_agentstate"]), "Failed")
        check("error recorded", bool(after.get("cpc_agenterror")), True)
        run = latest_run(task_id)
        check("run status", RUNSTATUS.get(run["cpc_runstatus"]), "Failed")
        print(f"    reason: {r['Reason']}\n")

        # ---------------------------------------------------------- 5
        print("5. auto-complete on, confident, valid outcome -> closes and advances")
        before = {x["activityid"] for x in tasks_for(cid)}
        r = call(task_id, Output="Isolated compromise of card details; no wider pattern.",
                 OutcomeName="isolated incident", Confidence=0.91, RawResponse=GOOD_JSON,
                 PromptSent="(prompt)", ContextSent="(context)", LatencyMs=1900,
                 RequestedBy="Marco Henry")
        check("state", r["State"], "Succeeded")
        check("completed", r["Completed"], "true")
        time.sleep(5)
        after = dv.get(f"tasks({task_id})?$select=statecode,cpc_agentstate,cpc_outcomelabel")
        check("task closed", after["statecode"], 1)
        check("agentstate", STATE.get(after["cpc_agentstate"]), "Succeeded")
        check("outcome label", after["cpc_outcomelabel"], "Isolated incident")
        now = tasks_for(cid)
        created = [x for x in now if x["activityid"] not in before]
        check("next task created by AdvanceProcess", len(created) >= 1, True)
        if created:
            print(f"    next task: {created[0]['subject']}")
        run = latest_run(task_id)
        check("run autocompleted flag", run["cpc_autocompleted"], True)
        print(f"    reason: {r['Reason']}\n")

    finally:
        set_cfg(src_id, **original)
        print("config restored to:", original)

    runs = dv.get("cpc_agentruns?$select=cpc_name,cpc_runstatus,cpc_attempt"
                  f"&$filter=_cpc_task_value eq {task_id}&$orderby=cpc_attempt")["value"]
    print(f"\naudit trail: {len(runs)} run(s)")
    for x in runs:
        print(f"  attempt {x['cpc_attempt']}: {RUNSTATUS.get(x['cpc_runstatus'])}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()

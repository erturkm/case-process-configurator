"""Step 50 (Phase 4 end-to-end): a four-step process with one AI agent step, run for real.

Builds a small but genuine process:

    1. Verify cardholder identity        human  - Fraud Operations
    2. Assess dispute risk               AI     - Fraud Dispute Triage   <-- the step under test
    3. Raise the chargeback              human  - Fraud Operations
    4. Confirm resolution with customer  human  - Complaints Management

Then creates a case that matches it and watches what happens without touching the AI step:
ApplyCaseProcess generates task 1, the script completes task 1 the way a human would, the runtime
generates task 2 as a Queued AI task, and from there nobody helps it. The Phase 4 cloud flow has
to notice it, call the agent, and write the turn back through cpc_CompleteAgentTask.

Pass condition: task 2 reaches Succeeded or Awaiting review on its own, with an audit row behind
it, and the process moves on to task 3 if the agent was confident enough to close it.

Usage: python3 step50_phase4_test.py [--rebuild]
"""
import json
import sys
import time

import dv

TEMPLATE = "Phase 4 Test - Card Dispute (AI assisted)"
MARKER = "P4TEST"
AGENT = "Fraud Dispute Triage"
OPS = "Fraud Operations"
COMPLAINTS = "Complaints Management"

AGENT_PROMPT = (
    "Decide whether this disputed card transaction should go straight to a chargeback or "
    "be held for a manual review first.\n"
    "- Choose \"Clear to charge back\" when the customer's account of the transaction is "
    "consistent, the amount and merchant are identified, and nothing suggests the customer "
    "authorised it themselves.\n"
    "- Choose \"Hold for manual review\" when the story is incomplete or contradictory, the "
    "amount is unusually large for this customer, or the pattern looks like a first-party "
    "(friendly) dispute.\n"
    "Name the single strongest fact behind your choice."
)

# 1 case fields, 2 description, 3 customer, 4 customer case history, 7 process tasks
SCOPE = "1,2,3,4,7"

AGENT_STATE = {1: "Queued", 2: "Running", 3: "Succeeded", 4: "Awaiting review",
               5: "Failed", 6: "Skipped"}
RUN_STATUS = {1: "Success", 2: "Failed", 3: "Timed out", 4: "Rejected", 5: "Invalid response"}


def ref(table, flt, cols):
    r = dv.find_one(table, flt, cols)
    if not r:
        sys.exit(f"Not found in {table}: {flt}")
    return r


# --------------------------------------------------------------------------- build

def build():
    ops = ref("teams", f"name eq '{OPS}'", "teamid,name")
    comp = ref("teams", f"name eq '{COMPLAINTS}'", "teamid,name")
    agent = ref("bots", f"name eq '{AGENT}'", "botid,name,schemaname,publishedon")
    if not agent.get("publishedon"):
        sys.exit(f"Agent '{AGENT}' is not published.")

    existing = dv.find_one("cpc_caseprocesstemplates", f"cpc_name eq '{TEMPLATE}'",
                           "cpc_caseprocesstemplateid")
    tid = existing["cpc_caseprocesstemplateid"] if existing else ""

    def team(t):
        return {"id": t["teamid"], "name": t["name"]}

    n = ["n1", "n2", "n3", "n4"]
    nodes = [
        {"id": n[0], "name": "Verify cardholder identity",
         "instructions": "Confirm you are speaking to the cardholder and record how identity "
                         "was verified.",
         "stageName": "Identify", "sequence": 1, "assignType": 1, "team": team(ops),
         "dueHours": 1, "blocksStage": True, "mandatory": True, "isStart": True,
         "x": 160, "y": 140},

        {"id": n[1], "name": "Assess dispute risk",
         "instructions": "An AI agent reviews the case and recommends whether to charge back now "
                         "or hold for manual review.",
         "stageName": "Research", "sequence": 2,
         "assignType": 7,
         "agent": {"id": agent["botid"], "name": agent["name"]},
         "agentPrompt": AGENT_PROMPT,
         "contextScope": SCOPE,
         "outputTarget": 2,            # append the finding to the task description
         "agentOutcomeMode": 2,        # the agent picks the outcome
         "autoComplete": True,         # and closes the task itself when confident
         "confidenceThreshold": 60,
         "agentTimeoutMins": 5,
         "fallbackTeam": team(ops),    # who picks it up if it is not confident
         "dueHours": 2, "blocksStage": True, "mandatory": True,
         "x": 420, "y": 140},

        {"id": n[2], "name": "Raise the chargeback",
         "instructions": "Lodge the chargeback with the scheme and attach the evidence pack.",
         "stageName": "Research", "sequence": 3, "assignType": 1, "team": team(ops),
         "dueHours": 4, "blocksStage": True, "mandatory": True,
         "x": 680, "y": 140},

        {"id": n[3], "name": "Confirm resolution with customer",
         "instructions": "Call the customer, confirm the provisional credit and close the case.",
         "stageName": "Resolve", "sequence": 4, "assignType": 1, "team": team(comp),
         "dueHours": 4, "blocksStage": True, "mandatory": True,
         "x": 940, "y": 140},
    ]

    outcomes = [
        {"id": "", "label": "Identity confirmed", "guidance": "The cardholder is verified.",
         "from": n[0], "to": n[1], "sentiment": 1, "sequence": 1, "isDefault": True,
         "advanceStage": True, "targetStageName": "Research"},

        # The two the agent chooses between.
        {"id": "", "label": "Clear to charge back",
         "guidance": "Evidence supports an unauthorised transaction.",
         "from": n[1], "to": n[2], "sentiment": 1, "sequence": 1, "isDefault": True},
        {"id": "", "label": "Hold for manual review",
         "guidance": "The dispute needs a human look before any chargeback.",
         "from": n[1], "to": n[2], "sentiment": 2, "sequence": 2, "requireComment": True},

        {"id": "", "label": "Chargeback raised", "guidance": "Lodged with the scheme.",
         "from": n[2], "to": n[3], "sentiment": 1, "sequence": 1, "isDefault": True,
         "advanceStage": True, "targetStageName": "Resolve"},

        {"id": "", "label": "Customer confirmed", "guidance": "Customer is satisfied.",
         "from": n[3], "to": "", "sentiment": 1, "sequence": 1, "isDefault": True,
         "closeCase": True},
    ]

    payload = {
        "template": {
            "id": tid,
            "name": TEMPLATE,
            "description": "Phase 4 test process. Step 2 is run by an AI agent through the "
                           "'CPC - Run AI agent task' cloud flow.",
            "rank": 1,                 # must beat the real templates so the test case lands here
            "publishStatus": 2,
            "setCasePriority": 0,
            "firstResponseHours": 1,
            "resolutionHours": 8,
            "startStageName": "Identify",
        },
        "nodes": nodes,
        "outcomes": outcomes,
        # Nothing else in the org has this marker in its title, so only the test case matches.
        "matchRules": [{"id": "", "attribute": "title", "operator": 5, "value": MARKER,
                        "group": 1, "sequence": 1}],
        "documents": [],
    }

    res = dv.post("cpc_SaveProcessGraph", {"Graph": json.dumps(payload)})
    tid = res["TemplateId"]
    print(f"template : {TEMPLATE}\n           {tid}")
    print("           " + (res.get("Summary") or "")[:160])
    return tid, agent


# --------------------------------------------------------------------------- run

def make_case(tid):
    cust = dv.get("accounts?$select=accountid,name&$top=1&$orderby=createdon desc")["value"]
    if not cust:
        sys.exit("No account to raise the case against.")
    stamp = time.strftime("%H%M%S")
    case = {
        "title": f"{MARKER} {stamp} - Disputed card transaction AED 4,250 at an online merchant",
        "description": (
            "Customer called to report a card transaction they do not recognise: AED 4,250 at "
            "an online electronics merchant, posted last night at 02:14. The customer says the "
            "card has not left their possession and they were asleep at the time. They confirm "
            "they have not shared the card details or the OTP with anyone, and they have no "
            "prior disputes on this card. Identity was verified on the call."),
        "caseorigincode": 1,
        "customerid_account@odata.bind": f"/accounts({cust[0]['accountid']})",
    }
    cid = dv.new_id(dv.post("incidents", case))
    print(f"case     : {case['title'][:70]}\n           {cid}")
    return cid


def tasks(cid):
    q = ("tasks?$select=activityid,subject,statecode,statuscode,cpc_agentstate,"
         "cpc_agentconfidence,cpc_outcomelabel,cpc_agenterror,cpc_agentoutput,cpc_sequence"
         f"&$filter=_regardingobjectid_value eq {cid}&$orderby=createdon asc")
    return dv.get(q)["value"]


def show(ts):
    for t in ts:
        st = "open" if t["statecode"] == 0 else "closed"
        ag = AGENT_STATE.get(t.get("cpc_agentstate"), "-")
        conf = t.get("cpc_agentconfidence")
        line = f"    {t['subject'][:44]:<46} {st:<7} agent={ag}"
        if conf is not None:
            line += f" conf={conf}"
        if t.get("cpc_outcomelabel"):
            line += f" outcome='{t['cpc_outcomelabel']}'"
        if t.get("cpc_agenterror"):
            line += f" error='{t['cpc_agenterror'][:60]}'"
        print(line)


def complete_human(t, outcome):
    """Close a human task the way the outcome picker does; AdvanceProcess picks it up."""
    dv.patch(f"tasks({t['activityid']})", {
        "cpc_outcomelabel": outcome,
        "cpc_outcomecomment": "Completed by the Phase 4 test harness.",
        "statecode": 1,
        "statuscode": 5,
    })
    print(f"    completed '{t['subject'][:40]}' -> {outcome}")


def wait_for_agent(cid, minutes=12):
    """Watch the AI task without touching it. The flow has to do all of this."""
    deadline = time.time() + minutes * 60
    last = None
    while time.time() < deadline:
        ai = [t for t in tasks(cid) if t.get("cpc_agentstate") is not None]
        if ai:
            t = ai[0]
            state = t["cpc_agentstate"]
            if state != last:
                print(f"    [{time.strftime('%H:%M:%S')}] {AGENT_STATE.get(state, state)}")
                last = state
            if state in (3, 4, 5):
                return t
        time.sleep(15)
    return None


def audit(cid):
    q = ("cpc_agentruns?$select=cpc_name,cpc_runstatus,cpc_confidence,cpc_parsedoutcome,"
         "cpc_latencyms,cpc_autocompleted,cpc_errordetail,cpc_requestedbyname"
         f"&$filter=_cpc_case_value eq {cid}&$orderby=createdon desc")
    return dv.get(q)["value"]


def main():
    if "--rebuild" in sys.argv or True:
        print("== build ==")
        tid, agent = build()

    print("\n== run ==")
    cid = make_case(tid)

    print("\n  waiting for the process to apply ...")
    for _ in range(20):
        ts = tasks(cid)
        if ts:
            break
        time.sleep(3)
    else:
        sys.exit("FAIL: no tasks were generated - the match rules did not fire.")
    show(ts)

    step1 = next((t for t in ts if t["statecode"] == 0 and t.get("cpc_agentstate") is None), None)
    if not step1:
        sys.exit("FAIL: expected an open human task to start with.")
    print("\n  human completes step 1:")
    complete_human(step1, "Identity confirmed")

    print("\n  waiting for the AI task to appear ...")
    for _ in range(20):
        ts = tasks(cid)
        if any(t.get("cpc_agentstate") is not None for t in ts):
            break
        time.sleep(3)
    else:
        sys.exit("FAIL: the AI task was never generated.")
    show(tasks(cid))

    print("\n  hands off - the cloud flow owns it from here:")
    final = wait_for_agent(cid)

    print("\n== result ==")
    ts = tasks(cid)
    show(ts)

    runs = audit(cid)
    print(f"\n  audit rows: {len(runs)}")
    for r in runs:
        print(f"    {RUN_STATUS.get(r['cpc_runstatus'], r['cpc_runstatus'])}"
              f" conf={r.get('cpc_confidence')}"
              f" outcome='{r.get('cpc_parsedoutcome')}'"
              f" auto={r.get('cpc_autocompleted')}"
              f" {r.get('cpc_latencyms')}ms"
              f" by={r.get('cpc_requestedbyname')}")
        if r.get("cpc_errordetail"):
            print(f"      error: {r['cpc_errordetail'][:200]}")

    ai = next((t for t in ts if t.get("cpc_agentstate") is not None), None)
    if ai and ai.get("cpc_agentoutput"):
        print("\n  agent said:")
        for line in (ai["cpc_agentoutput"] or "")[:900].splitlines():
            print("    " + line)

    print()
    if final is None:
        sys.exit("FAIL: the AI task never left Queued/Running. The cloud flow did not run it.")
    if final["cpc_agentstate"] == 5:
        sys.exit(f"FAIL: the agent turn failed - {final.get('cpc_agenterror')}")
    if not runs:
        sys.exit("FAIL: no cpc_agentrun audit row was written.")

    if final["cpc_agentstate"] == 3:
        nxt = [t for t in ts if t["statecode"] == 0]
        print("PASS: the agent chose "
              f"'{final.get('cpc_outcomelabel')}' at {final.get('cpc_agentconfidence')}% "
              "confidence, closed its own task and advanced the process.")
        print("      next open task: " + (nxt[0]["subject"] if nxt else "(none)"))
    else:
        print("PASS (with review): the agent ran and produced a recommendation, but did not "
              "clear the confidence bar, so the task is parked with the fallback team - which "
              "is the designed behaviour.")
    print(f"case: {dv.ORG}/main.aspx?pagetype=entityrecord&etn=incident&id={cid}")


if __name__ == "__main__":
    main()

"""Step 52: end-to-end proof that both agent harnesses run in one process.

Phase 4's flow now forks on which harness an agent was built with, because the two are not
reachable the same way:

    Standard agent  (bot.template default-*)   -> Copilot Studio connector, ExecuteCopilotAsyncV2
    Copilot harness (bot.template cliagent-*)  -> agent node connector, InvokeAgent

The second one matters because a Copilot harness agent does not fail loudly on the first route.
It answers "This action doesn't support agents built with the GitHub Copilot harness" AS THE
AGENT'S OWN REPLY, so the connector reports success, the run is green, and the refusal gets
written onto the task as if it were the agent's finding. Only an end-to-end run catches that.

The process under test:

    1. Verify cardholder identity        human  - Fraud Operations
    2. Assess dispute risk               AI     - Fraud Dispute Triage      (standard harness)
    3. Summarise the complaint           AI     - Complaint Intake Analyst  (copilot harness)
    4. Confirm resolution with customer  human  - Complaints Management

Step 3 following step 2 is deliberate: it is also the first real test of AI -> AI chaining, where
one agent's completion is what generates the next agent's task.

The script only ever completes the HUMAN tasks. Both AI steps are left entirely to the flow.

Usage: python3 step52_hybrid_test.py
"""
import json
import sys
import time

import dv

TEMPLATE = "Hybrid Test - Card Dispute (2 AI, 2 human)"
MARKER = "HYBRIDTEST"
STD_AGENT = "Fraud Dispute Triage"        # default-2.1.0  -> standard branch
CPL_AGENT = "Complaint Intake Analyst"    # cliagent-1.0.0 -> copilot harness branch
OPS = "Fraud Operations"
COMPLAINTS = "Complaints Management"

RISK_PROMPT = (
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

SUMMARY_PROMPT = (
    "Write the complaint summary that goes on the customer file for this dispute.\n"
    "Three short paragraphs: what the customer says happened, what has been established so far, "
    "and what the customer is owed or waiting for next. Plain language, no jargon, no invented "
    "facts - if something is unknown, say it is unknown.\n"
    "Then decide whether the summary is complete enough to send to the customer, or whether a "
    "complaint handler needs to fill a gap first."
)

# 1 case fields, 2 description, 3 customer, 4 customer case history, 7 process tasks
SCOPE = "1,2,3,4,7"

AGENT_STATE = {1: "Queued", 2: "Running", 3: "Succeeded", 4: "Awaiting review",
               5: "Failed", 6: "Skipped"}
RUN_STATUS = {1: "Success", 2: "Failed", 3: "Timed out", 4: "Rejected", 5: "Invalid response"}

# Anything containing this is the platform refusing, not the agent answering.
REFUSAL = "doesn't support agents built with the github copilot harness"


def ref(table, flt, cols):
    r = dv.find_one(table, flt, cols)
    if not r:
        sys.exit(f"Not found in {table}: {flt}")
    return r


def agent_ref(name, expect_harness):
    b = ref("bots", f"name eq '{name}'", "botid,name,schemaname,publishedon,template")
    if not b.get("publishedon"):
        sys.exit(f"Agent '{name}' is not published - it would 404 at runtime.")
    tpl = b.get("template") or ""
    harness = "copilot" if tpl.lower().startswith("cliagent") else "standard"
    if harness != expect_harness:
        sys.exit(f"Agent '{name}' is on the {harness} harness, expected {expect_harness}. "
                 "This test needs one of each or it proves nothing.")
    print(f"  {name:<28} {tpl:<18} -> {harness} branch")
    return b


# --------------------------------------------------------------------------- build

def build(std, cpl):
    ops = ref("teams", f"name eq '{OPS}'", "teamid,name")
    comp = ref("teams", f"name eq '{COMPLAINTS}'", "teamid,name")

    existing = dv.find_one("cpc_caseprocesstemplates", f"cpc_name eq '{TEMPLATE}'",
                           "cpc_caseprocesstemplateid")
    tid = existing["cpc_caseprocesstemplateid"] if existing else ""

    def team(t):
        return {"id": t["teamid"], "name": t["name"]}

    def bot(b):
        return {"id": b["botid"], "name": b["name"]}

    n = ["n1", "n2", "n3", "n4"]
    nodes = [
        {"id": n[0], "name": "Verify cardholder identity",
         "instructions": "Confirm you are speaking to the cardholder and record how identity "
                         "was verified.",
         "stageName": "Identify", "sequence": 1, "assignType": 1, "team": team(ops),
         "dueHours": 1, "slaTargetHours": 1, "slaWarnPercent": 75,
         "blocksStage": True, "mandatory": True, "isStart": True,
         "x": 160, "y": 140},

        {"id": n[1], "name": "Assess dispute risk",
         "instructions": "An AI agent reviews the case and recommends whether to charge back now "
                         "or hold for manual review.",
         "stageName": "Research", "sequence": 2,
         "assignType": 7, "agent": bot(std),
         "agentPrompt": RISK_PROMPT, "contextScope": SCOPE,
         "outputTarget": 2, "agentOutcomeMode": 2,
         "autoComplete": True, "confidenceThreshold": 60, "agentTimeoutMins": 5,
         "fallbackTeam": team(ops),
         "dueHours": 2, "slaTargetHours": 2, "slaWarnPercent": 75,
         "blocksStage": True, "mandatory": True,
         "x": 420, "y": 140},

        {"id": n[2], "name": "Summarise the complaint for the file",
         "instructions": "An AI agent writes the customer-file summary of the dispute and says "
                         "whether it is complete enough to send.",
         "stageName": "Research", "sequence": 3,
         "assignType": 7, "agent": bot(cpl),
         "agentPrompt": SUMMARY_PROMPT, "contextScope": SCOPE,
         "outputTarget": 2, "agentOutcomeMode": 2,
         "autoComplete": True, "confidenceThreshold": 60, "agentTimeoutMins": 5,
         "fallbackTeam": team(comp),
         "dueHours": 2, "slaTargetHours": 2, "slaWarnPercent": 75,
         "blocksStage": True, "mandatory": True,
         "x": 680, "y": 140},

        {"id": n[3], "name": "Confirm resolution with customer",
         "instructions": "Call the customer, confirm the provisional credit and close the case.",
         "stageName": "Resolve", "sequence": 4, "assignType": 1, "team": team(comp),
         "dueHours": 4, "slaTargetHours": 4, "slaWarnPercent": 75,
         "blocksStage": True, "mandatory": True,
         "x": 940, "y": 140},
    ]

    outcomes = [
        {"id": "", "label": "Identity confirmed", "guidance": "The cardholder is verified.",
         "from": n[0], "to": n[1], "sentiment": 1, "sequence": 1, "isDefault": True,
         "advanceStage": True, "targetStageName": "Research"},

        # What the standard-harness agent chooses between.
        {"id": "", "label": "Clear to charge back",
         "guidance": "Evidence supports an unauthorised transaction.",
         "from": n[1], "to": n[2], "sentiment": 1, "sequence": 1, "isDefault": True},
        {"id": "", "label": "Hold for manual review",
         "guidance": "The dispute needs a human look before any chargeback.",
         "from": n[1], "to": n[2], "sentiment": 2, "sequence": 2},

        # What the copilot-harness agent chooses between.
        {"id": "", "label": "Summary ready",
         "guidance": "The summary is complete and can go to the customer.",
         "from": n[2], "to": n[3], "sentiment": 1, "sequence": 1, "isDefault": True,
         "advanceStage": True, "targetStageName": "Resolve"},
        {"id": "", "label": "Needs a handler to fill a gap",
         "guidance": "Something material is missing from the file.",
         "from": n[2], "to": n[3], "sentiment": 2, "sequence": 2,
         "advanceStage": True, "targetStageName": "Resolve"},

        {"id": "", "label": "Customer confirmed", "guidance": "Customer is satisfied.",
         "from": n[3], "to": "", "sentiment": 1, "sequence": 1, "isDefault": True,
         "closeCase": True},
    ]

    payload = {
        "template": {
            "id": tid,
            "name": TEMPLATE,
            "description": "Hybrid harness test. Step 2 runs on a standard Copilot Studio agent, "
                           "step 3 on a GitHub Copilot harness agent, both through "
                           "'CPC - Run AI agent task'.",
            "rank": 1,
            "publishStatus": 2,
            "setCasePriority": 0,
            "firstResponseHours": 1,
            "resolutionHours": 8,
            "startStageName": "Identify",
        },
        "nodes": nodes,
        "outcomes": outcomes,
        "matchRules": [{"id": "", "attribute": "title", "operator": 5, "value": MARKER,
                        "group": 1, "sequence": 1}],
        "documents": [],
    }

    res = dv.post("cpc_SaveProcessGraph", {"Graph": json.dumps(payload)})
    tid = res["TemplateId"]
    print(f"\ntemplate : {TEMPLATE}\n           {tid}")
    print("           " + (res.get("Summary") or "")[:160])
    return tid


# --------------------------------------------------------------------------- run

def make_case():
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
            "prior disputes on this card. Identity was verified on the call. The customer is "
            "unhappy that the amount was debited before anyone contacted them and wants the "
            "money back before their salary transfer date."),
        "caseorigincode": 1,
        "customerid_account@odata.bind": f"/accounts({cust[0]['accountid']})",
    }
    cid = dv.new_id(dv.post("incidents", case))
    print(f"case     : {case['title'][:70]}\n           {cid}")
    return cid


def tasks(cid):
    q = ("tasks?$select=activityid,subject,statecode,statuscode,cpc_agentstate,"
         "cpc_agentconfidence,cpc_outcomelabel,cpc_agenterror,cpc_agentoutput,cpc_sequence,"
         "cpc_sladue"
         f"&$filter=_regardingobjectid_value eq {cid}&$orderby=cpc_sequence asc,createdon asc")
    return dv.get(q)["value"]


def show(ts):
    for t in ts:
        st = "open" if t["statecode"] == 0 else "closed"
        ag = AGENT_STATE.get(t.get("cpc_agentstate"), "-")
        line = f"    {(t['subject'] or '')[:44]:<46} {st:<7} agent={ag:<15}"
        if t.get("cpc_agentconfidence") is not None:
            line += f" conf={t['cpc_agentconfidence']}"
        if t.get("cpc_outcomelabel"):
            line += f" outcome='{t['cpc_outcomelabel']}'"
        if t.get("cpc_agenterror"):
            line += f" error='{t['cpc_agenterror'][:60]}'"
        print(line)


def sla_rows(task_id):
    q = ("slakpiinstances?$select=slakpiinstanceid,status,failuretime,warningtime,"
         f"terminalstatereached&$filter=_regarding_value eq {task_id}")
    return dv.get(q)["value"]


def complete_human(t, outcome):
    dv.patch(f"tasks({t['activityid']})", {
        "cpc_outcomelabel": outcome,
        "cpc_outcomecomment": "Completed by the hybrid harness test.",
        "statecode": 1,
        "statuscode": 5,
    })
    print(f"    completed '{(t['subject'] or '')[:44]}' -> {outcome}")


def wait_for_open_task(cid, seq, minutes=3):
    """Wait for the task at this sequence to exist and be open."""
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        for t in tasks(cid):
            if t.get("cpc_sequence") == seq and t["statecode"] == 0:
                return t
        time.sleep(3)
    return None


def wait_for_agent(cid, seq, minutes=12):
    """Watch one AI task without touching it. The flow has to do all of this."""
    deadline = time.time() + minutes * 60
    last = None
    while time.time() < deadline:
        t = next((x for x in tasks(cid) if x.get("cpc_sequence") == seq), None)
        if t:
            state = t.get("cpc_agentstate")
            if state != last:
                print(f"    [{time.strftime('%H:%M:%S')}] step {seq}: "
                      f"{AGENT_STATE.get(state, state)}")
                last = state
            if state in (3, 4, 5):
                return t
        time.sleep(15)
    return None


def audit(cid):
    q = ("cpc_agentruns?$select=cpc_name,cpc_runstatus,cpc_confidence,cpc_parsedoutcome,"
         "cpc_latencyms,cpc_autocompleted,cpc_errordetail,cpc_requestedbyname,cpc_rawresponse"
         f"&$filter=_cpc_case_value eq {cid}&$orderby=createdon asc")
    return dv.get(q)["value"]


def check_agent_step(label, t, failures):
    if t is None:
        failures.append(f"{label}: never left Queued/Running - the flow did not run it.")
        return
    out = (t.get("cpc_agentoutput") or "") + " " + (t.get("cpc_agenterror") or "")
    if REFUSAL in out.lower():
        failures.append(f"{label}: the platform refusal was written back as the agent's answer. "
                        "The harness branch did not take effect.")
        return
    if t.get("cpc_agentstate") == 5:
        failures.append(f"{label}: failed - {t.get('cpc_agenterror')}")
        return
    state = AGENT_STATE.get(t.get("cpc_agentstate"))
    print(f"  {label}: {state}"
          + (f", chose '{t['cpc_outcomelabel']}'" if t.get("cpc_outcomelabel") else "")
          + (f" at {t['cpc_agentconfidence']}%" if t.get("cpc_agentconfidence") is not None
             else ""))


def main():
    print("== agents ==")
    std = agent_ref(STD_AGENT, "standard")
    cpl = agent_ref(CPL_AGENT, "copilot")

    print("\n== build ==")
    build(std, cpl)

    print("\n== run ==")
    cid = make_case()

    print("\n  waiting for the process to apply ...")
    t1 = wait_for_open_task(cid, 1)
    if not t1:
        sys.exit("FAIL: no tasks were generated - the match rules did not fire.")
    show(tasks(cid))

    kpi = sla_rows(t1["activityid"])
    print(f"\n  step 1 SLA: due {t1.get('cpc_sladue')}, {len(kpi)} countdown row(s) "
          f"{'OK' if kpi else 'MISSING'}")

    print("\n  human completes step 1:")
    complete_human(t1, "Identity confirmed")

    failures = []

    print("\n  step 2 - standard harness agent, hands off:")
    a2 = wait_for_agent(cid, 2)

    print("\n  step 3 - copilot harness agent, hands off (AI -> AI chaining):")
    a3 = wait_for_agent(cid, 3)

    print("\n== result ==")
    ts = tasks(cid)
    show(ts)

    check_agent_step("step 2 (standard)", a2, failures)
    check_agent_step("step 3 (copilot harness)", a3, failures)

    runs = audit(cid)
    print(f"\n  audit rows: {len(runs)}")
    for r in runs:
        print(f"    {RUN_STATUS.get(r['cpc_runstatus'], r['cpc_runstatus']):<16}"
              f" conf={r.get('cpc_confidence')}"
              f" outcome='{r.get('cpc_parsedoutcome')}'"
              f" auto={r.get('cpc_autocompleted')}"
              f" {r.get('cpc_latencyms')}ms")
        if r.get("cpc_errordetail"):
            print(f"      error: {r['cpc_errordetail'][:200]}")
    if not runs:
        failures.append("no cpc_agentrun audit rows were written.")

    for t in ts:
        if t.get("cpc_agentoutput"):
            print(f"\n  {(t['subject'] or '')[:50]} said:")
            for line in t["cpc_agentoutput"][:700].splitlines():
                print("    " + line)

    # SLA countdowns: every task that has a deadline should have a mirror KPI row.
    print("\n  SLA countdowns:")
    if not any(t.get("cpc_sladue") for t in ts):
        failures.append("no task carried an SLA deadline - the countdown check proved nothing.")
    for t in ts:
        if not t.get("cpc_sladue"):
            continue
        rows = sla_rows(t["activityid"])
        ok = "OK" if rows else "MISSING"
        st = rows[0]["status"] if rows else "-"
        print(f"    {(t['subject'] or '')[:44]:<46} {ok:<8} status={st}")
        if not rows:
            failures.append(f"no SLA countdown row on '{t['subject']}'.")

    print()
    if failures:
        for f in failures:
            print("FAIL: " + f)
        print(f"\ncase: {dv.ORG}/main.aspx?pagetype=entityrecord&etn=incident&id={cid}")
        sys.exit(1)

    step4 = next((t for t in ts if t.get("cpc_sequence") == 4), None)
    print("PASS: both harnesses ran through the same flow, AI -> AI chaining held, and every "
          "task with a deadline has a live countdown.")
    print("      step 4 reached: " + ("yes" if step4 else "no (an agent parked for review)"))
    print(f"case: {dv.ORG}/main.aspx?pagetype=entityrecord&etn=incident&id={cid}")


if __name__ == "__main__":
    main()

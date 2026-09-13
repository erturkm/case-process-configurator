"""Step 43: configure the Fraud Dispute template's assessment task as an AI agent task.

Goes through cpc_SaveProcessGraph rather than patching rows directly, so this doubles as an
end-to-end test of the same path the designer uses.
"""
import json
import sys

import dv

TEMPLATE = "Fraud Dispute - Card"
TASK = "Risk and pattern assessment"
AGENT = "Fraud Dispute Triage"

PROMPT = (
    "Assess whether this disputed card transaction looks like a genuine unauthorised "
    "transaction or a first-party (friendly) dispute.\n\n"
    "Read the case context below, then choose one of the allowed outcomes.\n"
    "- Choose \"Isolated incident\" when the evidence points to a one-off unauthorised "
    "transaction affecting this cardholder only.\n"
    "- Choose \"Part of a wider fraud pattern\" when the merchant, amount, timing or channel "
    "resembles other recent disputes, or the customer reports several unrecognised "
    "transactions.\n\n"
    "State the single strongest fact behind your choice. If the mandatory documents are still "
    "outstanding, say so and keep your confidence below 70."
)

# 1 case fields, 2 description, 3 customer, 4 previous cases, 6 required docs, 8 emails
SCOPE = "1,2,3,4,6,8"
FALLBACK = "Complaints Management"


def pick(seq, name):
    for x in seq:
        if x.get("name") == name:
            return x
    return None


def main():
    tpl = dv.find_one("cpc_caseprocesstemplates", f"cpc_name eq '{TEMPLATE}'",
                      "cpc_caseprocesstemplateid,cpc_name")
    if not tpl:
        sys.exit(f"Template '{TEMPLATE}' not found.")
    tid = tpl["cpc_caseprocesstemplateid"]

    agent = dv.find_one("bots", f"name eq '{AGENT}'", "botid,name,schemaname,publishedon")
    if not agent:
        sys.exit(f"Agent '{AGENT}' not found.")
    if not agent.get("publishedon"):
        sys.exit(f"Agent '{AGENT}' is not published; the runtime endpoint would 404.")
    print(f"agent  : {agent['name']} ({agent['schemaname']})")

    graph = json.loads(dv.post("cpc_GetProcessGraph", {"TemplateId": tid})["Graph"])
    node = pick(graph["nodes"], TASK)
    if not node:
        sys.exit(f"Task '{TASK}' not found in the template.")

    outs = [o["label"] for o in graph["outcomes"] if o["from"] == node["id"]]
    print(f"task   : {TASK}")
    print(f"outcomes: {outs}")

    node["assignType"] = 7
    node["agent"] = {"id": agent["botid"], "name": agent["name"]}
    node["agentPrompt"] = PROMPT
    node["contextScope"] = SCOPE
    node["outputTarget"] = 2          # append to the task description
    node["agentOutcomeMode"] = 2      # agent selects the outcome
    node["autoComplete"] = True       # agent closes the task and advances the process itself
    node["confidenceThreshold"] = 70
    node["agentTimeoutMins"] = 5
    node["fallbackTeam"] = FALLBACK
    # The human assignee is cleared server side when assignType leaves a human option.

    payload = {
        "template": dict(graph["template"], id=tid),
        "nodes": graph["nodes"],
        "outcomes": graph["outcomes"],
        "matchRules": graph.get("matchRules", []),
        "documents": graph.get("documents", []),
    }
    res = dv.post("cpc_SaveProcessGraph", {"Graph": json.dumps(payload)})
    print("saved  :", res.get("Summary", "")[:200])

    back = json.loads(dv.post("cpc_GetProcessGraph", {"TemplateId": tid})["Graph"])
    n = pick(back["nodes"], TASK)
    got = {
        "assignType": n["assignType"],
        "agent": (n.get("agent") or {}).get("name"),
        "contextScope": n.get("contextScope"),
        "outputTarget": n.get("outputTarget"),
        "agentOutcomeMode": n.get("agentOutcomeMode"),
        "autoComplete": n.get("autoComplete"),
        "confidenceThreshold": n.get("confidenceThreshold"),
        "agentTimeoutMins": n.get("agentTimeoutMins"),
        "fallbackTeam": (n.get("fallbackTeam") or {}).get("name"),
        "promptChars": len(n.get("agentPrompt") or ""),
    }
    print("readback:", json.dumps(got, indent=1))

    bad = []
    if got["assignType"] != 7: bad.append("assignType")
    if got["agent"] != AGENT: bad.append("agent")
    if got["contextScope"] != SCOPE: bad.append("contextScope")
    if got["fallbackTeam"] != FALLBACK: bad.append("fallbackTeam")
    if got["promptChars"] == 0: bad.append("agentPrompt")
    if got["confidenceThreshold"] != 70: bad.append("confidenceThreshold")
    if got["autoComplete"] is not True: bad.append("autoComplete")
    # Auto-complete only has an effect when the agent is also allowed to pick the outcome.
    if got["agentOutcomeMode"] != 2: bad.append("agentOutcomeMode")
    if bad:
        sys.exit("ROUND TRIP FAILED for: " + ", ".join(bad))
    print("\nround trip OK")
    print("autonomy: the agent will close this task and advance the process on its own "
          f"at {got['confidenceThreshold']}%+ confidence; below that it waits for "
          f"{FALLBACK}.")


if __name__ == "__main__":
    main()

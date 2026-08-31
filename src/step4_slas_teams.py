"""Step 4: demo teams, queues and enhanced SLAs used by the process templates."""
import dv

BU = dv.get("businessunits?$select=businessunitid&$filter=parentbusinessunitid eq null")["value"][0]["businessunitid"]

TEAMS = [
    ("Contact Centre Tier 1", "Front line agents handling first contact and acknowledgement."),
    ("Fraud Operations", "Investigates disputed and unauthorised transactions."),
    ("Correspondence", "Produces and issues customer letters and final responses."),
    ("Complaints Management", "Owns complaint oversight, approvals and escalations."),
    ("Onboarding Operations", "Handles KYC and account opening documentation."),
    ("Field Service Dispatch", "Schedules engineers and work orders."),
]

QUEUES = [
    ("Complaints Queue", "Unassigned complaint work."),
    ("Fraud Queue", "Unassigned fraud investigation work."),
    ("Onboarding Queue", "Unassigned onboarding work."),
]

# name, first response minutes, resolve minutes, warn percent
SLAS = [
    ("Premier 4-Hour Response", 60, 240, 75),
    ("Standard 24-Hour Response", 240, 1440, 75),
    ("Fraud Dispute 1-Hour Response", 30, 60, 50),
    ("Onboarding 2-Day Response", 480, 2880, 80),
]

FIRST_RESPONSE_SUCCESS = ('<condition entityname="incident" attribute="firstresponsesent" '
                          'operator="eq" value="1" />')
RESOLVE_SUCCESS = '<condition entityname="incident" attribute="statecode" operator="eq" value="1" />'
PAUSE_NONE = ""


def team(name, desc):
    e = dv.find_one("teams", f"name eq '{name}'", "teamid,name")
    if e:
        print("  exists team", name)
        return e["teamid"]
    r = dv.post("teams", {"name": name, "description": desc,
                          "teamtype": 0})
    tid = dv.new_id(r)
    print("  + team", name)
    return tid


def queue(name, desc):
    e = dv.find_one("queues", f"name eq '{name}'", "queueid,name")
    if e:
        print("  exists queue", name)
        return e["queueid"]
    r = dv.post("queues", {"name": name, "description": desc, "queueviewtype": 0})
    print("  + queue", name)
    return dv.new_id(r)


def sla(name, fr_min, res_min, warn):
    e = dv.find_one("slas", f"name eq '{name}'", "slaid,name,statecode")
    if e:
        print("  exists sla", name)
        return e["slaid"]
    r = dv.post("slas", {
        "name": name,
        "description": f"Enhanced SLA: first response {fr_min} minutes, resolution {res_min} minutes.",
        "objecttypecode": 112,
        "applicablefrom": "createdon",
        "slatype": 1,
    })
    sid = dv.new_id(r)
    for label, minutes, related, success in (
        ("First Response", fr_min, "firstresponsebykpiid", FIRST_RESPONSE_SUCCESS),
        ("Resolution", res_min, "resolvebykpiid", RESOLVE_SUCCESS),
    ):
        dv.post("slaitems", {
            "name": f"{name} - {label}",
            "slaid@odata.bind": f"/slas({sid})",
            "relatedfield": related,
            "applicablewhenxml": "",
            "successconditionsxml": success,
            "failureafter": minutes,
            "warnafter": max(1, int(minutes * warn / 100)),
            "sequencenumber": 1 if related.startswith("first") else 2,
            "allowpauseresume": True,
        })
    dv.patch(f"slas({sid})", {"statecode": 1, "statuscode": 2})
    print("  + sla", name, "activated")
    return sid


if __name__ == "__main__":
    print("Teams");   [team(*t) for t in TEAMS]
    print("Queues");  [queue(*q) for q in QUEUES]
    print("SLAs");    [sla(*s) for s in SLAS]
    print("done")

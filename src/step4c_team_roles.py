"""Step 4c: give the demo teams a security role so they can own cases, tasks and activities.

Teams created through the Web API get no roles at all (privilegeCount=0), which makes the case
form fail with "Team Roles Error ... is missing prvReadActivity" the moment a team owns anything.
System Administrator is granted here deliberately: this is a demo org and these teams need to
read and write every activity type the case timeline touches.
"""
import dv

BU = dv.get("businessunits?$select=businessunitid"
            "&$filter=parentbusinessunitid eq null")["value"][0]["businessunitid"]

ROLE = "System Administrator"

TEAMS = [
    # original service teams
    "Contact Centre Tier 1", "Fraud Operations", "Correspondence",
    "Complaints Management", "Onboarding Operations", "Field Service Dispatch",
    # corporate and retail banking teams
    "Credit Origination", "Credit Risk", "Credit Committee",
    "Legal and Documentation", "Loan Operations", "Portfolio Monitoring",
    "Retail Lending Operations",
]


def main():
    roles = {r["name"]: r["roleid"] for r in dv.get(
        f"roles?$select=roleid,name&$filter=_businessunitid_value eq {BU}")["value"]}
    if ROLE not in roles:
        raise SystemExit(f"Role {ROLE!r} not found in the root business unit. "
                         "Available: " + str(sorted(roles)[:40]))
    role_id = roles[ROLE]
    print("Using role:", ROLE)

    for name in TEAMS:
        t = dv.find_one("teams", f"name eq '{name}'", "teamid,_businessunitid_value")
        if not t:
            print("  ! missing team", name)
            continue

        # A team can only hold roles from its own business unit, so pull it into the root BU.
        if t.get("_businessunitid_value") != BU:
            dv.patch(f"teams({t['teamid']})",
                     {"businessunitid@odata.bind": f"/businessunits({BU})"})
            print("    moved to root BU:", name)

        have = {r["name"] for r in
                dv.get(f"teams({t['teamid']})/teamroles_association?$select=name")["value"]}
        if ROLE in have:
            print("  = already has role:", name)
            continue
        dv.post(f"teams({t['teamid']})/teamroles_association/$ref",
                {"@odata.id": f"{dv.API}/roles({role_id})"})
        print("  + role granted:", name)

    print("\nVerifying")
    bad = []
    for name in TEAMS:
        t = dv.find_one("teams", f"name eq '{name}'", "teamid")
        if not t:
            continue
        have = [r["name"] for r in
                dv.get(f"teams({t['teamid']})/teamroles_association?$select=name")["value"]]
        ok = ROLE in have
        if not ok:
            bad.append(name)
        print(f"  {'OK ' if ok else '!! '}{name}: {have or 'NO ROLES'}")
    print("\nRESULT:", "ALL TEAMS HAVE THE ROLE" if not bad else "MISSING: " + str(bad))


if __name__ == "__main__":
    main()

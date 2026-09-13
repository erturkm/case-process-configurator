"""Repair the demo SLAs so they are modern (unified interface) and actually run.

Three problems are fixed here:

1. The four custom SLAs were created as web-client SLAs (slaversion null). Once a
   case picked up the org's modern Default SLA, assigning a legacy SLA failed with
   "One cannot change from unified interface to web client service level agreement".
2. Their SLA items held bare <condition> fragments instead of full <fetch>
   documents, so activation failed with "Entity Name was not specified in FetchXml".
3. Premier 4-Hour Response had no items at all, so it tracked nothing and the
   SLA timer control had no KPI instance to render.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step31_fix_slas.py
"""
import dv

MODERN = 100000001

FETCH = ('<fetch version="1.0" output-format="xml-platform" mapping="logical">'
         '<entity name="incident"><filter type="and">{}</filter></entity></fetch>')

FR_WHEN = FETCH.format('<condition attribute="firstresponsesent" operator="ne" value="1"/>')
FR_OK = FETCH.format('<condition attribute="firstresponsesent" operator="eq" value="1"/>')
RES_WHEN = FETCH.format('<condition attribute="statecode" operator="not-in">'
                        '<value>1</value><value>2</value></condition>')
RES_OK = FETCH.format('<condition attribute="statecode" operator="eq" value="1"/>')

# name -> (first response warn/fail, resolution warn/fail) in minutes
TARGETS = {
    "Premier 4-Hour Response":      ((180, 240), (720, 960)),
    "Standard 24-Hour Response":    ((1080, 1440), (3240, 4320)),
    "Fraud Dispute 1-Hour Response": ((45, 60), (1080, 1440)),
    "Onboarding 2-Day Response":    ((360, 480), (2160, 2880)),
}


def kpis():
    rows = dv.get("msdyn_slakpis?$select=msdyn_slakpiid,msdyn_name&$top=50")["value"]
    by = {r["msdyn_name"]: r["msdyn_slakpiid"] for r in rows}
    fr = by.get("First Response By") or by.get("First Response")
    rs = by.get("Resolve By") or by.get("ResolveByKPI")
    if not (fr and rs):
        raise SystemExit(f"Could not find the standard case KPIs. Found: {sorted(by)}")
    return fr, rs


def deactivate(sla):
    if sla["statecode"] == 1:
        dv.patch(f"slas({sla['slaid']})", {"statecode": 0, "statuscode": 1})


def item(sla_id, kpi_id, name, seq, when, ok, warn, fail, changed):
    return {
        "name": name,
        "slaid@odata.bind": f"/slas({sla_id})",
        "msdyn_SLAKPIID@odata.bind": f"/msdyn_slakpis({kpi_id})",
        "applicableentity": "incident",
        "applicablewhenxml": when,
        "successconditionsxml": ok,
        "warnafter": warn,
        "failureafter": fail,
        "sequencenumber": seq,
        "allowpauseresume": True,
        "changedattributelist": changed,
    }


def main():
    fr_kpi, res_kpi = kpis()
    slas = {s["name"]: s for s in
            dv.get("slas?$select=slaid,name,slaversion,statecode&$top=50")["value"]}

    for name, ((frw, frf), (rw, rf)) in TARGETS.items():
        s = slas.get(name)
        if not s:
            print("  ! missing SLA:", name)
            continue
        print(name)
        deactivate(s)

        if s.get("slaversion") != MODERN:
            dv.patch(f"slas({s['slaid']})", {"slaversion": MODERN})
            print("    upgraded to unified interface")

        # Legacy items carry fragment XML that can never activate; replace wholesale.
        for old in dv.get(f"slaitems?$select=slaitemid&$filter=_slaid_value eq {s['slaid']}")["value"]:
            dv.call("DELETE", f"slaitems({old['slaitemid']})")

        dv.post("slaitems", item(s["slaid"], fr_kpi, f"{name} - First Response", 1,
                                 FR_WHEN, FR_OK, frw, frf,
                                 "firstresponsesent,createdon,slaid,statuscode,entitlementid,customerid"))
        dv.post("slaitems", item(s["slaid"], res_kpi, f"{name} - Resolution", 2,
                                 RES_WHEN, RES_OK, rw, rf,
                                 "statecode,createdon,slaid,statuscode,entitlementid,customerid"))
        print(f"    items rebuilt: first response {frf}m, resolution {rf}m")

        dv.patch(f"slas({s['slaid']})", {"statecode": 1, "statuscode": 2})
        print("    ACTIVATED")

    print("\nFinal state")
    for s in dv.get("slas?$select=name,slaversion,statecode&$top=50")["value"]:
        state = "ACTIVE" if s["statecode"] == 1 else "draft"
        modern = "modern" if s.get("slaversion") == MODERN else "LEGACY"
        print(f"  {s['name'][:40]:<40} {modern:<7} {state}")


if __name__ == "__main__":
    main()

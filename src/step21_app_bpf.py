"""Add the banking business process flows to the apps where cases are actually worked.

A business process flow header only renders inside a model driven app when the flow is a
component of that app. The flows created by bpfgen.py are not attached to anything, so a case
would carry the right process instance in data while the form showed nothing at all.
"""
import dv

COMPONENT_TYPE_WORKFLOW = 29

TARGET_APPS = (
    "Customer Service Hub",
    "Copilot Service workspace",
    "Case Process Configurator",
    "Omnichannel for Customer Service",
)

BPF_NAMES = (
    "Corporate Credit Lifecycle",
    "Retail Lending Journey",
)


def bpf_ids():
    rows = dv.get("workflows?$select=workflowid,name&$filter=category eq 4")["value"]
    by_name = {r["name"]: r["workflowid"] for r in rows}
    out = []
    for n in BPF_NAMES:
        if n in by_name:
            out.append((n, by_name[n]))
        else:
            print(f"  ! business process flow not found: {n}")
    return out


def app_ids():
    rows = dv.get("appmodules?$select=appmoduleid,appmoduleidunique,name")["value"]
    by_name = {r["name"]: r for r in rows}
    out = []
    for n in TARGET_APPS:
        if n in by_name:
            out.append((n, by_name[n]))
        else:
            print(f"  - app not present, skipped: {n}")
    return out


def already_in(app_unique):
    rows = dv.get("appmodulecomponents?$select=objectid&$filter="
                  f"_appmoduleidunique_value eq {app_unique}&$top=5000")["value"]
    return {str(r["objectid"]).lower() for r in rows}


def main():
    bpfs = bpf_ids()
    apps = app_ids()
    if not bpfs or not apps:
        print("nothing to do")
        return 1

    for app_name, app in apps:
        have = already_in(app["appmoduleidunique"])
        missing = [(n, g) for n, g in bpfs if g.lower() not in have]
        if not missing:
            print(f"  = {app_name}: both flows already present")
            continue
        try:
            dv.post("AddAppComponents", {
                "AppId": app["appmoduleid"],
                "Components": [{"@odata.type": "Microsoft.Dynamics.CRM.workflow",
                                "workflowid": g} for _, g in missing],
            })
            print(f"  + {app_name}: added {', '.join(n for n, _ in missing)}")
        except RuntimeError as e:
            print(f"  ! {app_name}: {str(e)[-260:]}")

    dv.publish_all()

    print("\nverify")
    ok = True
    for app_name, app in apps:
        for n, g in bpfs:
            # Query per component: the collection is far larger than one page, so a broad
            # retrieve silently misses rows that were only just added.
            hit = dv.get("appmodulecomponents?$select=appmodulecomponentid&$filter="
                         f"_appmoduleidunique_value eq {app['appmoduleidunique']} "
                         f"and objectid eq {g}")["value"]
            ok &= bool(hit)
            print(f"  {app_name:36} {n:30} {'OK' if hit else 'MISSING'}")
    print("\nRESULT:", "ALL FLOWS ARE IN THE APPS" if ok else "SOME FLOWS STILL MISSING")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

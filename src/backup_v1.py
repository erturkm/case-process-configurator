"""Full pre-v2 backup: solution zips, configuration + demo data, org state manifest.

Run:  python3 backup_v1.py
Everything lands in backups/v1-<timestamp>/ next to this script.
"""
import base64
import datetime
import json
import os
import pathlib
import subprocess
import sys

import dv

STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M")
ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "backups" / f"v1-{STAMP}"
SOLUTION = "CaseProcessConfigurator"

# Configuration tables: the process model itself. These define the solution's behaviour.
CONFIG_TABLES = [
    "cpc_caseprocesstemplate",
    "cpc_matchrule",
    "cpc_processtask",
    "cpc_taskoutcome",
    "cpc_documentpackage",
    "cpc_documentitem",
]

# Demo/runtime data: seeded records and evidence of runs.
DATA_TABLES = [
    "cpc_appliedprocess",
    "cpc_caserequireddocument",
]

# Platform config the solution depends on but does not own.
PLATFORM_QUERIES = {
    "slas": "slas?$select=name,slaid,isdefault,statecode,statuscode,applicablefrom,objecttypecode",
    "sla_items": "slaitems?$select=name,slaitemid,_slaid_value,relatedfield,failureafter,warnafter",
    "teams": "teams?$select=name,teamid,teamtype,isdefault",
    "queues": "queues?$select=name,queueid,emailaddress,queuetypecode,cpc_createcases",
    "subjects": "subjects?$select=title,subjectid,_parentsubject_value,featuremask",
    "mailboxes": ("mailboxes?$select=name,mailboxid,emailaddress,processingstatecode,"
                  "emailrouteraccessapproval,incomingemaildeliverymethod,outgoingemaildeliverymethod"),
    "email_categories": ("msdyn_emailclassificationcategories?$select=msdyn_name,"
                         "msdyn_emailclassificationcategoryid,_msdyn_parentcategoryid_value,"
                         "_msdyn_activeversion_value,statecode,statuscode"),
    "bots": "bots?$select=name,schemaname,botid,statecode,publishedon,authenticationmode",
    "bpfs": ("workflows?$select=name,workflowid,category,statecode,uniquename,primaryentity"
             "&$filter=category eq 4"),
    "webresources": ("webresourceset?$select=name,webresourceid,webresourcetype,displayname"
                     "&$filter=startswith(name,'cpc_')"),
    "plugin_assemblies": ("pluginassemblies?$select=name,pluginassemblyid,version,publickeytoken"
                          "&$filter=startswith(name,'Cpc')"),
}


def log(msg):
    print(msg, flush=True)


_SETS = {}


def entity_set(logical):
    """Plural set name is not always logical+'s' (cpc_appliedprocess -> cpc_appliedprocesses)."""
    if logical not in _SETS:
        _SETS[logical] = dv.get(
            f"EntityDefinitions(LogicalName='{logical}')?$select=EntitySetName")["EntitySetName"]
    return _SETS[logical]


def export_solution(managed):
    kind = "managed" if managed else "unmanaged"
    log(f"  exporting {kind} ...")
    body = {"SolutionName": SOLUTION, "Managed": managed}
    res = dv.post("ExportSolution", body)
    blob = base64.b64decode(res["ExportSolutionFile"])
    path = OUT / f"{SOLUTION}_{kind}_{STAMP}.zip"
    path.write_bytes(blob)
    log(f"    {path.name}  ({len(blob):,} bytes)")
    return path


def page_all(query):
    """Follow @odata.nextLink so large tables are captured in full."""
    rows = []
    res = dv.get(query)
    rows.extend(res.get("value", []))
    nxt = res.get("@odata.nextLink")
    while nxt:
        res = dv.get(nxt.split("/api/data/v9.2/", 1)[1])
        rows.extend(res.get("value", []))
        nxt = res.get("@odata.nextLink")
    return rows


FAILURES = []


def dump(name, query, folder):
    try:
        rows = page_all(query)
    except Exception as exc:
        FAILURES.append({"name": name, "query": query, "error": str(exc)[:400]})
        log(f"    {name:<34} ** FAILED ** ({str(exc)[:80]})")
        return None
    path = folder / f"{name}.json"
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    log(f"    {name:<34} {len(rows):>5} rows")
    return len(rows)


def snapshot_source():
    log("  archiving source ...")
    archive = OUT / f"source_{STAMP}.tar.gz"
    excludes = ["--exclude=backups", "--exclude=__pycache__", "--exclude=plugin/bin",
                "--exclude=plugin/obj", "--exclude=.DS_Store"]
    subprocess.run(["tar", "-czf", str(archive)] + excludes + ["-C", str(ROOT.parent), ROOT.name],
                   check=True)
    log(f"    {archive.name}  ({archive.stat().st_size:,} bytes)")
    return archive


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"Backup -> {OUT}\n")

    log("Solution")
    sol = dv.get(f"solutions?$select=uniquename,version,ismanaged&$filter=uniquename eq '{SOLUTION}'")["value"]
    if not sol:
        sys.exit(f"solution {SOLUTION} not found")
    log(f"  {SOLUTION} v{sol[0]['version']}")
    zips = [export_solution(False), export_solution(True)]

    log("\nConfiguration (the process model)")
    cfg = OUT / "config"
    cfg.mkdir(exist_ok=True)
    counts = {}
    for t in CONFIG_TABLES:
        counts[t] = dump(t, f"{entity_set(t)}?$top=5000", cfg)

    log("\nDemo / runtime data")
    dat = OUT / "data"
    dat.mkdir(exist_ok=True)
    for t in DATA_TABLES:
        counts[t] = dump(t, f"{entity_set(t)}?$top=5000", dat)
    counts["incident"] = dump(
        "incidents",
        "incidents?$select=title,ticketnumber,incidentid,_subjectid_value,_customerid_value,"
        "prioritycode,statecode,statuscode,createdon,_cpc_sourcequeue_value&$top=5000",
        dat)
    counts["task"] = dump(
        "tasks",
        "tasks?$select=subject,activityid,_regardingobjectid_value,cpc_sequence,cpc_stagename,"
        "_cpc_selectedoutcome_value,cpc_slastatus,cpc_availableoutcomes,cpc_outcomelabel,"
        "statecode,statuscode&$top=5000",
        dat)

    log("\nPlatform configuration")
    plat = OUT / "platform"
    plat.mkdir(exist_ok=True)
    for name, q in PLATFORM_QUERIES.items():
        counts[name] = dump(name, q, plat)

    log("\nPlugin registration")
    asm = dv.get("pluginassemblies?$select=name,pluginassemblyid,version"
                 "&$filter=name eq 'CpcPlugins'")["value"]
    (plat / "plugin_assembly.json").write_text(json.dumps(asm, indent=1))
    types = []
    for a in asm:
        types += page_all("plugintypes?$select=typename,name,plugintypeid&$filter="
                          f"_pluginassemblyid_value eq {a['pluginassemblyid']}")
    (plat / "plugin_types.json").write_text(json.dumps(types, indent=1))
    log(f"    plugin_types                       {len(types):>5} rows")
    ids = [t["plugintypeid"] for t in types]
    ours = []
    for tid in ids:
        ours += page_all(
            "sdkmessageprocessingsteps?$select=name,stage,mode,rank,statecode,"
            "filteringattributes,sdkmessageprocessingstepid,_plugintypeid_value"
            f"&$expand=sdkmessageid($select=name)&$filter=_plugintypeid_value eq {tid}")
    bytype = {t["plugintypeid"]: t["typename"].split(".")[-1] for t in types}
    for s in ours:
        s["_typename"] = bytype.get(s.get("_plugintypeid_value"))
    (plat / "plugin_steps.json").write_text(json.dumps(ours, indent=1))
    log(f"    plugin_steps                       {len(ours):>5} rows")
    if not ours:
        FAILURES.append({"name": "plugin_steps", "query": "per-type",
                         "error": "no steps found for CpcPlugins types"})
    for s in sorted(ours, key=lambda x: (x.get("_typename") or "")):
        mn = (s.get("sdkmessageid") or {}).get("name")
        log(f"      {s.get('_typename'):<22} {mn:<10} stage={s['stage']} "
            f"rank={s['rank']} mode={s['mode']} state={s['statecode']}")

    log("\nSource")
    archive = snapshot_source()

    manifest = {
        "created": datetime.datetime.now().isoformat(),
        "purpose": "Pre-v2 (AI Agent Tasks) full backup",
        "org": dv.ORG,
        "environment_id": "ad5dd938-824d-e154-aac2-97f7c4678f5a",
        "solution": {"uniquename": SOLUTION, "version": sol[0]["version"]},
        "files": {
            "solution_unmanaged": zips[0].name,
            "solution_managed": zips[1].name,
            "source_archive": archive.name,
        },
        "row_counts": counts,
        "failures": FAILURES,
        "restore": [
            "Solution:  import the unmanaged zip with 'Overwrite customizations', then Publish All.",
            "Source:    tar -xzf <source archive>",
            "Data:      the JSON dumps are a reference/diff aid, not an auto-restore. "
            "Re-seed with the stepNN scripts, which are idempotent.",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))

    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    log(f"\nDone. {OUT}")
    log(f"{sum(1 for f in OUT.rglob('*') if f.is_file())} files, {total:,} bytes")
    if FAILURES:
        log(f"\n** {len(FAILURES)} dump(s) FAILED - backup is incomplete **")
        for f in FAILURES:
            log(f"   {f['name']}: {f['error'][:120]}")
        sys.exit(1)
    log("All dumps succeeded.")


if __name__ == "__main__":
    main()

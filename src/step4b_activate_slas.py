"""Deduplicate SLAs, then activate them all."""
import time, collections
import dv

rows = dv.get("slas?$select=slaid,name,statecode,createdon&$orderby=createdon asc")["value"]
by_name = collections.defaultdict(list)
for r in rows:
    by_name[r["name"]].append(r)

keep = {}
for name, rs in by_name.items():
    keep[name] = rs[0]
    for extra in rs[1:]:
        for it in dv.get(f"slaitems?$select=slaitemid&$filter=_slaid_value eq {extra['slaid']}")["value"]:
            dv.call("DELETE", f"slaitems({it['slaitemid']})")
        dv.call("DELETE", f"slas({extra['slaid']})")
        print("  removed duplicate", name)

for name, r in keep.items():
    cur = dv.get(f"slas({r['slaid']})?$select=statecode")["statecode"]
    if cur == 1:
        print("  active", name)
        continue
    for attempt in range(5):
        try:
            dv.patch(f"slas({r['slaid']})", {"statecode": 1, "statuscode": 2})
            print("  activated", name)
            break
        except Exception as e:
            print("   retry", name, attempt, str(e)[:80])
            time.sleep(8)

print([(x["name"], x["statecode"]) for x in
       dv.get("slas?$select=name,statecode&$orderby=name")["value"]])

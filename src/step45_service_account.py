"""Provision the CPC agent service account in Dataverse: security roles + bot share."""
import dv, json

SVC_SYSTEMUSER = "f30d3a2a-3caf-f111-aaac-e4fb1ef76b0b"
BOT_ID = "0d5bec47-35af-f111-aaac-e4fb1ef76b0b"

WANT = ["Basic User", "Customer Service Representative", "Environment Maker"]

roles = dv.get("roles?$select=roleid,name,_businessunitid_value")["value"]
bu = dv.get("businessunits?$select=businessunitid&$filter=parentbusinessunitid eq null")["value"][0]["businessunitid"]
root = {r["name"]: r["roleid"] for r in roles if r["_businessunitid_value"] == bu}

have = {r["name"] for r in dv.get(
    f"systemusers({SVC_SYSTEMUSER})/systemuserroles_association?$select=name")["value"]}
print("existing roles:", sorted(have) or "(none)")

for name in WANT:
    if name in have:
        print(f"  = {name} (already)"); continue
    rid = root.get(name)
    if not rid:
        print(f"  ! {name} not found in root BU"); continue
    try:
        dv.post(f"systemusers({SVC_SYSTEMUSER})/systemuserroles_association/$ref",
                {"@odata.id": f"{dv.API}/roles({rid})"})
        print(f"  + {name}")
    except Exception as e:
        print(f"  ! {name}: {str(e)[:160]}")

print("\nsharing bot with service account (read/write/append-to)...")
try:
    dv.post("GrantAccess", {
        "Target": {"botid": BOT_ID, "@odata.type": "Microsoft.Dynamics.CRM.bot"},
        "PrincipalAccess": {
            "Principal": {"systemuserid": SVC_SYSTEMUSER,
                          "@odata.type": "Microsoft.Dynamics.CRM.systemuser"},
            "AccessMask": "ReadAccess,WriteAccess,AppendToAccess"}})
    print("  bot shared")
except Exception as e:
    print("  share result:", str(e)[:300])

print("\nfinal roles:", sorted(
    r["name"] for r in dv.get(
        f"systemusers({SVC_SYSTEMUSER})/systemuserroles_association?$select=name")["value"]))

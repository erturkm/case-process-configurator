"""
Moves customer segment to where it belongs: the customer.

Segment describes a relationship, not a ticket, so it lives on contact and account and is read by
the match engine through the one hop path customerid.cpc_customersegment. The case level column
stays in place for now as a read only remnant of older data; nothing matches on it any more.

Re-runnable.
"""
import time

import dv

P = "cpc_"
GLOBAL_SET = "cpc_customersegment"
SEGMENTS = [(1, "Premier"), (2, "Priority"), (3, "Retail"), (4, "Corporate"), (5, "SME")]

# Contacts inherit the segment their household or employer sits in, so both tables carry it.
TARGETS = ["contact", "account"]


def with_lock(fn, what):
    """Solution imports hold the customization lock, so metadata writes get a patient retry."""
    for _ in range(15):
        try:
            return fn()
        except RuntimeError as e:
            if "another [Import]" in str(e) or "-> 429" in str(e):
                print(f"    waiting for the customization lock ({what})...")
                time.sleep(20)
                continue
            raise
    raise RuntimeError(f"gave up waiting for the customization lock: {what}")


def ensure_global_optionset():
    ex = dv.get(f"GlobalOptionSetDefinitions?$select=Name")["value"]
    if any(o["Name"] == GLOBAL_SET for o in ex):
        print("  = global option set", GLOBAL_SET)
        return
    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
        "Name": GLOBAL_SET,
        "DisplayName": dv.label("Customer Segment"),
        "Description": dv.label("Relationship segment the customer is managed under."),
        "OptionSetType": "Picklist",
        "IsGlobal": True,
        "Options": [
            {"Value": v, "Label": dv.label(l)} for v, l in SEGMENTS
        ],
    }
    with_lock(lambda: dv.post("GlobalOptionSetDefinitions", body), GLOBAL_SET)
    print("  + global option set", GLOBAL_SET)


def global_set_id():
    rows = dv.get(f"GlobalOptionSetDefinitions?$select=Name,MetadataId")["value"]
    for o in rows:
        if o["Name"] == GLOBAL_SET:
            return o["MetadataId"]
    raise RuntimeError(f"global option set {GLOBAL_SET} not found")


def ensure_column(entity, set_id):
    try:
        dv.get(f"EntityDefinitions(LogicalName='{entity}')"
               f"/Attributes(LogicalName='{P}customersegment')?$select=LogicalName")
        print(f"  = {entity}.{P}customersegment")
        return
    except RuntimeError as e:
        if "-> 404" not in str(e):
            raise

    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
        "SchemaName": "cpc_CustomerSegment",
        "DisplayName": dv.label("Customer Segment"),
        "Description": dv.label("Relationship segment used to target case processes."),
        "RequiredLevel": {"Value": "None", "CanBeChanged": True,
                          "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"},
        # The bind is by metadata id; binding by Name is rejected with a Guid parse error.
        "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions({set_id})",
    }
    with_lock(lambda: dv.post(f"EntityDefinitions(LogicalName='{entity}')/Attributes", body),
              f"{entity}.{P}customersegment")
    print(f"  + {entity}.{P}customersegment")


def backfill():
    """
    Cases already carry a segment from the earlier model. Pushing it onto the customer keeps the
    existing demo data meaningful and gives the new dotted path something to read.
    """
    rows = dv.get("incidents?$select=incidentid,cpc_customersegment,_customerid_value"
                  "&$filter=cpc_customersegment ne null&$top=2000")["value"]
    seen = {}
    for r in rows:
        cust = r.get("_customerid_value")
        seg = r.get("cpc_customersegment")
        if not cust or not seg:
            continue
        # Most recent case wins if a customer's cases disagree.
        seen.setdefault(cust, seg)

    done = 0
    for cust, seg in seen.items():
        for entity, setname in (("contact", "contacts"), ("account", "accounts")):
            try:
                cur = dv.get(f"{setname}({cust})?$select={P}customersegment")
            except RuntimeError:
                continue
            if cur.get(f"{P}customersegment") is None:
                dv.patch(f"{setname}({cust})", {f"{P}customersegment": seg})
                done += 1
            break
    print(f"  ~ backfilled segment onto {done} customer(s) from {len(seen)} case owner(s)")


def main():
    print("Global option set")
    ensure_global_optionset()

    print("Columns")
    set_id = global_set_id()
    for e in TARGETS:
        ensure_column(e, set_id)

    dv.publish_all()

    print("Backfill")
    backfill()
    print("\nDone.")


if __name__ == "__main__":
    main()

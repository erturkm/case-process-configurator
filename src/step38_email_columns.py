"""Columns that let the email-to-case pipeline be configured rather than hardcoded.

Two additions:

  * queue.cpc_createcases - opts a queue in to automatic case creation. Without
    it the plugin would have to carry a hardcoded queue name, and every queue in
    the org would be a candidate.
  * incident.cpc_sourcequeue - records which queue a case arrived through, so the
    demo can show provenance and so reporting can split channel volumes.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step38_email_columns.py
"""
import dv

P = dv.PREFIX
SOLUTION = "CaseProcessConfigurator"


def label(text):
    return {"LocalizedLabels": [{"Label": text, "LanguageCode": 1033}]}


def ensure_boolean(entity, name, display, description):
    try:
        dv.get(f"EntityDefinitions(LogicalName='{entity}')/Attributes(LogicalName='{name}')"
               "?$select=LogicalName")
        print(f"  = {entity}.{name}")
        return
    except RuntimeError:
        pass

    dv.post(f"EntityDefinitions(LogicalName='{entity}')/Attributes", {
        "@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
        "SchemaName": name.replace(P + "_", P.capitalize() + "_"),
        "LogicalName": name,
        "DisplayName": label(display),
        "Description": label(description),
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {
            "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
            "TrueOption": {"Value": 1, "Label": label("Yes")},
            "FalseOption": {"Value": 0, "Label": label("No")},
        },
        "DefaultValue": False,
    }, solution=True)
    print(f"  + {entity}.{name}")


def ensure_lookup(name, display, description, target, referenced_entity):
    try:
        dv.get(f"EntityDefinitions(LogicalName='incident')/Attributes(LogicalName='{name}')"
               "?$select=LogicalName")
        print(f"  = incident.{name}")
        return
    except RuntimeError:
        pass

    schema = name.replace(P + "_", P.capitalize() + "_")
    dv.post("RelationshipDefinitions", {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        "SchemaName": f"{P}_{referenced_entity}_incident_sourcequeue",
        "ReferencedEntity": referenced_entity,
        "ReferencingEntity": "incident",
        "CascadeConfiguration": {
            "Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
            "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade",
        },
        "Lookup": {
            "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "SchemaName": schema,
            "LogicalName": name,
            "DisplayName": label(display),
            "Description": label(description),
            "RequiredLevel": {"Value": "None"},
        },
        "AssociatedMenuConfiguration": {
            "Behavior": "DoNotDisplay", "Group": "Details", "Order": 10000,
            "IsCustomizable": True,
        },
    }, solution=True)
    print(f"  + incident.{name}")


def main():
    print("Columns")
    ensure_boolean("queue", f"{P}_createcases", "Create Cases from Email",
                   "When enabled, inbound email delivered to this queue opens a case "
                   "and is matched to a process template.")
    ensure_lookup(f"{P}_sourcequeue", "Source Queue",
                  "The queue the case arrived through.", "queue", "queue")

    dv.publish_all()

    queue = dv.find_one("queues", "name eq 'RAKBANK Customer Care'", "queueid,name")
    if queue:
        dv.patch(f"queues({queue['queueid']})", {f"{P}_createcases": True})
        print(f"\n  {queue['name']} is now creating cases from inbound email")
    else:
        print("\n  ! queue 'RAKBANK Customer Care' not found")


if __name__ == "__main__":
    main()

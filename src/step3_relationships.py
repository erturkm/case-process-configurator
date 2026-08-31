"""Step 3: create lookup columns via one-to-many relationships."""
import dv
from dv import label

P = dv.PREFIX

# (referenced table, referencing table, lookup schema suffix, lookup display, required, nav name)
RELS = [
    # config hierarchy
    ("cpc_caseprocesstemplate", "cpc_matchrule", "template", "Case Process Template", "ApplicationRequired"),
    ("cpc_caseprocesstemplate", "cpc_processtask", "template", "Case Process Template", "ApplicationRequired"),
    ("cpc_documentpackage", "cpc_documentitem", "package", "Document Package", "ApplicationRequired"),
    ("cpc_documentpackage", "cpc_caseprocesstemplate", "documentpackage", "Document Package", "None"),
    ("cpc_processtask", "cpc_processtask", "predecessor", "Predecessor Task", "None"),
    # ownership targets on the task template
    ("team", "cpc_processtask", "team", "Team", "None"),
    ("systemuser", "cpc_processtask", "user", "User", "None"),
    ("queue", "cpc_processtask", "queue", "Queue", "None"),
    ("team", "cpc_processtask", "fallbackteam", "Fallback Team", "None"),
    ("team", "cpc_documentitem", "ownerteam", "Owning Team", "None"),
    # SLA on the template
    ("sla", "cpc_caseprocesstemplate", "sla", "SLA", "None"),
    ("entitlement", "cpc_caseprocesstemplate", "entitlement", "Entitlement", "None"),
    # runtime
    ("incident", "cpc_appliedprocess", "case", "Case", "ApplicationRequired"),
    ("cpc_caseprocesstemplate", "cpc_appliedprocess", "template", "Case Process Template", "None"),
    ("incident", "cpc_caserequireddocument", "case", "Case", "ApplicationRequired"),
    ("cpc_documentitem", "cpc_caserequireddocument", "packageitem", "Document Package Item", "None"),
    ("team", "cpc_caserequireddocument", "ownerteam", "Owning Team", "None"),
    # link generated tasks back to their template row
    ("cpc_processtask", "task", "sourcetask", "Source Process Task", "None"),
    ("cpc_caseprocesstemplate", "task", "sourcetemplate", "Source Case Process Template", "None"),
    ("cpc_caseprocesstemplate", "incident", "appliedtemplate", "Applied Case Process Template", "None"),
]


def make(referenced, referencing, suffix, display, req):
    lookup = f"{P}_{suffix}" if not suffix.startswith(P) else suffix
    rel = f"{P}_{referenced}_{referencing}_{suffix}".replace("cpc_cpc_", "cpc_")
    if len(rel) > 100:
        rel = rel[:100]
    try:
        dv.get(f"EntityDefinitions(LogicalName='{referencing}')/Attributes(LogicalName='{lookup}')?$select=LogicalName")
        print("  exists", referencing, lookup)
        return
    except RuntimeError:
        pass
    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
        "SchemaName": rel,
        "ReferencedEntity": referenced,
        "ReferencingEntity": referencing,
        "CascadeConfiguration": {"Assign": "NoCascade", "Delete": "RemoveLink", "Merge": "NoCascade",
                                 "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade"},
        "Lookup": {
            "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
            "SchemaName": lookup, "LogicalName": lookup,
            "DisplayName": label(display),
            "RequiredLevel": {"Value": req},
        },
        "AssociatedMenuConfiguration": {
            "Behavior": "UseCollectionName", "Group": "Details", "Order": 10000, "IsCustomizable": True,
        },
    }
    if referencing.startswith(P) and referenced.startswith(P):
        body["CascadeConfiguration"]["Delete"] = "Cascade" if suffix in ("template", "package") else "RemoveLink"
    dv.post("RelationshipDefinitions", body, solution=True)
    print("  +", referencing, lookup, "->", referenced)


if __name__ == "__main__":
    for r in RELS:
        make(*r)
    dv.publish_all()
    print("done")

"""Step 5: clean probe records, add runtime SLA columns to incident and task."""
import dv
from dv import label

P = dv.PREFIX
SLA_STATUS = [(1, "In progress"), (2, "Nearing breach"), (3, "Met"), (4, "Breached"), (5, "Paused")]


def add(entity, col):
    ln = f"{P}_{col['name']}"
    try:
        dv.get(f"EntityDefinitions(LogicalName='{entity}')/Attributes(LogicalName='{ln}')?$select=LogicalName")
        print("  exists", entity, ln)
        return
    except RuntimeError:
        pass
    t = col["type"]
    b = {"SchemaName": ln, "LogicalName": ln, "DisplayName": label(col["display"]),
         "RequiredLevel": {"Value": "None"}}
    if t == "datetime":
        b["@odata.type"] = "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata"
        b["Format"] = "DateAndTime"
        b["DateTimeBehavior"] = {"Value": "UserLocal"}
    elif t == "str":
        b["@odata.type"] = "Microsoft.Dynamics.CRM.StringAttributeMetadata"
        b["MaxLength"] = col.get("len", 200)
        b["FormatName"] = {"Value": "Text"}
    elif t == "int":
        b["@odata.type"] = "Microsoft.Dynamics.CRM.IntegerAttributeMetadata"
        b["MinValue"] = 0; b["MaxValue"] = 1000000; b["Format"] = "None"
    elif t == "bool":
        b["@odata.type"] = "Microsoft.Dynamics.CRM.BooleanAttributeMetadata"
        b["DefaultValue"] = False
        b["OptionSet"] = {"@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                          "TrueOption": {"Value": 1, "Label": label(col.get("true", "Yes"))},
                          "FalseOption": {"Value": 0, "Label": label(col.get("false", "No"))}}
    elif t == "choice":
        b["@odata.type"] = "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
        b["OptionSet"] = {"@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                          "OptionSetType": "Picklist", "IsGlobal": False,
                          "Name": f"{entity}_{ln}", "DisplayName": label(col["display"]),
                          "Options": [{"Value": v, "Label": label(l)} for v, l in col["options"]]}
        if "default" in col:
            b["DefaultFormValue"] = col["default"]
    dv.post(f"EntityDefinitions(LogicalName='{entity}')/Attributes", b, solution=True)
    print("  +", entity, ln)


INCIDENT = [
    dict(name="firstresponsedue", display="First Response Due", type="datetime"),
    dict(name="firstresponsewarn", display="First Response Warning At", type="datetime"),
    dict(name="firstresponsestatus", display="First Response SLA Status", type="choice",
         options=SLA_STATUS, default=1),
    dict(name="resolutiondue", display="Resolution Due", type="datetime"),
    dict(name="resolutionwarn", display="Resolution Warning At", type="datetime"),
    dict(name="resolutionstatus", display="Resolution SLA Status", type="choice",
         options=SLA_STATUS, default=1),
    dict(name="processappliedon", display="Process Applied On", type="datetime"),
    dict(name="processsummary", display="Applied Process Summary", type="str", len=400),
    dict(name="customersegment", display="Customer Segment", type="choice",
         options=[(1, "Premier"), (2, "Priority"), (3, "Retail"), (4, "Corporate"), (5, "SME")]),
    dict(name="tasksopen", display="Open Process Tasks", type="int"),
    dict(name="taskstotal", display="Total Process Tasks", type="int"),
    dict(name="docsreceived", display="Documents Received", type="int"),
    dict(name="docstotal", display="Documents Required", type="int"),
]

TASK = [
    dict(name="sequence", display="Sequence", type="int"),
    dict(name="stagename", display="Business Process Stage", type="str"),
    dict(name="blocksstage", display="Blocks Stage Completion", type="bool",
         true="Blocks", false="Does not block"),
    dict(name="mandatory", display="Mandatory", type="bool", true="Mandatory", false="Optional"),
    dict(name="sladue", display="Task SLA Due", type="datetime"),
    dict(name="slawarn", display="Task SLA Warning At", type="datetime"),
    dict(name="slastatus", display="Task SLA Status", type="choice", options=SLA_STATUS, default=1),
    dict(name="onbreach", display="On Breach", type="choice",
         options=[(1, "Do nothing"), (2, "Notify task owner"), (3, "Escalate to manager"),
                  (4, "Escalate to queue"), (5, "Raise case priority")], default=1),
    dict(name="assignedteamname", display="Assigned Team", type="str"),
]


def cleanup_probes():
    for s in dv.get("slas?$select=slaid,name&$filter=startswith(name,'ZZ Probe')")["value"]:
        for it in dv.get(f"slaitems?$select=slaitemid&$filter=_slaid_value eq {s['slaid']}")["value"]:
            dv.call("DELETE", f"slaitems({it['slaitemid']})")
        dv.call("DELETE", f"slas({s['slaid']})")
        print("  removed probe", s["name"])


if __name__ == "__main__":
    print("Cleanup"); cleanup_probes()
    print("Incident columns"); [add("incident", c) for c in INCIDENT]
    print("Task columns"); [add("task", c) for c in TASK]
    dv.publish_all()
    print("done")

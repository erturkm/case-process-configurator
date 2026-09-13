"""
End to end check of the new match engine.

Proves the two things the refactor is meant to deliver:
  1. a rule on a parent subject catches a case tagged with a grandchild subject
  2. a rule can read customer segment from the contact rather than from the case

Creates a throwaway template, contact and case, asserts the plug-in picked the template, then
removes everything it made. Safe to run repeatedly.
"""
import datetime

import dv

P = "cpc_"
TAG = "ZZ Engine Test"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def subject(title):
    s = dv.find_one("subjects", f"title eq '{title}'", "subjectid,title")
    if not s:
        raise SystemExit(f"subject not found: {title}")
    return s["subjectid"]


def cleanup():
    for c in dv.get(f"incidents?$select=incidentid&$filter=startswith(title,'{TAG}')")["value"]:
        dv.call("DELETE", f"incidents({c['incidentid']})")
    for t in dv.get(f"{P}caseprocesstemplates?$select={P}caseprocesstemplateid"
                    f"&$filter=startswith({P}name,'{TAG}')")["value"]:
        dv.call("DELETE", f"{P}caseprocesstemplates({t[P + 'caseprocesstemplateid']})")
    for c in dv.get(f"contacts?$select=contactid&$filter=startswith(lastname,'{TAG}')")["value"]:
        dv.call("DELETE", f"contacts({c['contactid']})")


def main():
    print("Cleaning up any previous run")
    cleanup()

    parent = subject("Cards")            # rule points here
    leaf = subject("Card Limit Increase")  # case is tagged here, two levels down
    print(f"  parent subject Cards        {parent}")
    print(f"  leaf subject Card Limit Inc {leaf}")

    bpf = dv.find_one("workflows", "category eq 4 and statecode eq 1 and primaryentity eq 'incident'",
                      "workflowid,name,uniquename")
    stage = dv.get(f"processstages?$select=processstageid,stagename"
                   f"&$filter=_processid_value eq {bpf['workflowid']}")["value"][0]

    print("Creating the test contact (Premier, segment on the contact only)")
    contact_id = dv.new_id(dv.post("contacts", {
        "firstname": "Segment", "lastname": TAG,
        "emailaddress1": "zz.engine.test@example.com",
        f"{P}customersegment": 1,
    }))

    print("Creating the test template")
    tid = dv.new_id(dv.post(f"{P}caseprocesstemplates", {
        f"{P}name": f"{TAG} Template", f"{P}rank": 1, f"{P}publishstatus": 2,
        f"{P}description": "Temporary template used to verify the match engine.",
        f"{P}matchlogic": 3, f"{P}effectivefrom": NOW, f"{P}appliedcount": 0,
        f"{P}bpfid": bpf["workflowid"], f"{P}bpfname": bpf["name"],
        f"{P}bpfentityname": bpf["uniquename"],
        f"{P}startstageid": stage["processstageid"], f"{P}startstagename": stage["stagename"],
        f"{P}firstresponsehours": 1, f"{P}resolutionhours": 8, f"{P}setcasepriority": 0,
    }))

    # Group 1: subject anywhere at or under Cards.  Group 2: the customer is Premier.
    # Both must hold, and neither value is stored on the case.
    dv.post(f"{P}matchrules", {
        f"{P}name": f"{TAG} :: subject under Cards", f"{P}sequence": 1, f"{P}groupnumber": 1,
        f"{P}attributename": "subjectid", f"{P}attributelabel": "Subject",
        f"{P}operator": 11, f"{P}value": parent, f"{P}valuelabel": "Cards",
        f"{P}template@odata.bind": f"/{P}caseprocesstemplates({tid})"})
    dv.post(f"{P}matchrules", {
        f"{P}name": f"{TAG} :: customer is Premier", f"{P}sequence": 2, f"{P}groupnumber": 2,
        f"{P}attributename": "customerid.cpc_customersegment",
        f"{P}attributelabel": "Customer \u203a Customer Segment",
        f"{P}operator": 1, f"{P}value": "1", f"{P}valuelabel": "Premier",
        f"{P}template@odata.bind": f"/{P}caseprocesstemplates({tid})"})
    dv.post(f"{P}processtasks", {
        f"{P}name": f"{TAG} task", f"{P}sequence": 1,
        f"{P}stagename": stage["stagename"], f"{P}stageid": stage["processstageid"],
        f"{P}assigntype": 6, f"{P}duehours": 4, f"{P}slastartwhen": 2,
        f"{P}slatargethours": 2, f"{P}slawarnpercent": 75, f"{P}onbreach": 2,
        f"{P}blocksstage": True, f"{P}mandatory": True,
        f"{P}template@odata.bind": f"/{P}caseprocesstemplates({tid})"})

    print("Creating the case (subject two levels under Cards, no segment on the case)")
    case_id = dv.new_id(dv.post("incidents", {
        "title": f"{TAG} card limit increase",
        "description": "Verifies subject hierarchy matching and customer segment lookup.",
        "customerid_contact@odata.bind": f"/contacts({contact_id})",
        "subjectid@odata.bind": f"/subjects({leaf})",
        "caseorigincode": 2, "prioritycode": 2,
    }))

    got = dv.get(f"incidents({case_id})?$select={P}processsummary,{P}taskstotal,"
                 f"_{P}appliedtemplate_value")
    applied = got.get(f"_{P}appliedtemplate_value")
    print("\nResult")
    print("  applied template:", applied)
    print("  summary         :", got.get(f"{P}processsummary"))
    ok = applied == tid
    print("\n" + ("PASS - hierarchy and customer lookup both matched."
                  if ok else "FAIL - the template did not match."))

    print("\nCleaning up")
    cleanup()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

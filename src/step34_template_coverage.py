"""Close the template coverage gaps found while seeding the second wave of cases.

Three subjects had no template that could match them, so cases landed with no
process at all: Salary Transfer and Payroll, Card Delivery and PIN, and
Statements and Certificates. Rather than invent new templates, the existing ones
are widened - rules inside the same group are OR'd, so adding a second subject to
group 1 extends the template's reach without disturbing its other conditions.

Retail Onboarding - KYC is also broadened: it was restricted to Retail and SME
customers, which meant a Priority customer opening an account fell through to the
generic fallback template.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step34_template_coverage.py
"""
import dv

P = dv.PREFIX
AT_OR_UNDER = 11

# template name -> subject titles to add as alternatives in the given rule group
WIDEN = [
    ("Payment Investigation - Transfer Trace", 1, ["Salary Transfer and Payroll"]),
    ("Card Replacement - Lost or Stolen", 1, ["Card Delivery and PIN"]),
    ("Service Request - Standard", 1, ["Statements and Certificates"]),
]

# template name -> segment option values to add to the given rule group
SEGMENTS = [
    ("Retail Onboarding - KYC", 2, {"1": "Premier", "2": "Priority"}),
]


def index(entity, key, label):
    return {r[label]: r[key] for r in
            dv.get(f"{entity}?$select={key},{label}&$top=400")["value"]}


def rules_for(template_id):
    return dv.get(f"{P}_matchrules?$select={P}_matchruleid,{P}_groupnumber,{P}_sequence,"
                  f"{P}_attributename,{P}_value,{P}_valuelabel,{P}_operator"
                  f"&$filter=_{P}_template_value eq {template_id}")["value"]


def add_rule(template_id, group, seq, attr, label, op, value, value_label):
    dv.post(f"{P}_matchrules", {
        f"{P}_name": f"{label} {value_label}",
        f"{P}_template@odata.bind": f"/{P}_caseprocesstemplates({template_id})",
        f"{P}_groupnumber": group,
        f"{P}_sequence": seq,
        f"{P}_attributename": attr,
        f"{P}_attributelabel": label,
        f"{P}_operator": op,
        f"{P}_value": value,
        f"{P}_valuelabel": value_label,
    })


def main():
    subjects = index("subjects", "subjectid", "title")
    templates = index(f"{P}_caseprocesstemplates", f"{P}_caseprocesstemplateid", f"{P}_name")

    print("Widening subject coverage")
    for tname, group, titles in WIDEN:
        tid = templates.get(tname)
        if not tid:
            print("  ! missing template", tname)
            continue
        existing = rules_for(tid)
        have = {r[f"{P}_valuelabel"] for r in existing if r[f"{P}_groupnumber"] == group}
        nxt = max((r[f"{P}_sequence"] or 0) for r in existing) + 1 if existing else 1
        for title in titles:
            if title in have:
                print(f"  = {tname}: already covers {title}")
                continue
            if title not in subjects:
                print(f"  ! unknown subject {title}")
                continue
            add_rule(tid, group, nxt, "subjectid", "Subject",
                     AT_OR_UNDER, subjects[title], title)
            nxt += 1
            print(f"  + {tname}: OR subject at or under {title}")

    print("\nBroadening segment coverage")
    for tname, group, values in SEGMENTS:
        tid = templates.get(tname)
        if not tid:
            print("  ! missing template", tname)
            continue
        existing = rules_for(tid)
        grp = [r for r in existing if r[f"{P}_groupnumber"] == group]
        have = {r[f"{P}_value"] for r in grp}
        nxt = max((r[f"{P}_sequence"] or 0) for r in existing) + 1 if existing else 1
        attr = grp[0][f"{P}_attributename"] if grp else "customerid.cpc_customersegment"
        for val, lbl in values.items():
            if val in have:
                print(f"  = {tname}: already covers {lbl}")
                continue
            add_rule(tid, group, nxt, attr, "Customer \u203a Customer Segment", 1, val, lbl)
            nxt += 1
            print(f"  + {tname}: OR segment {lbl}")

    print("\nCases still without a process")
    orphans = [c for c in dv.get(f"incidents?$select=incidentid,title,_subjectid_value,"
                                 f"_{P}_appliedtemplate_value&$top=800")["value"]
               if c.get("_subjectid_value") and not c.get(f"_{P}_appliedtemplate_value")]
    by_id = {v: k for k, v in subjects.items()}
    for c in orphans:
        print(f"  - {c['title'][:56]:<56} {by_id.get(c['_subjectid_value'], '?')}")
    if not orphans:
        print("  none")


if __name__ == "__main__":
    main()

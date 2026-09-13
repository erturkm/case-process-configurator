"""
Retires the denormalised targeting columns.

Case category duplicated what the subject tree already says, and customer segment described the
customer rather than the ticket. This script re-points every match rule onto the real model:

  cpc_casecategory     -> subjectid with the "is at or under" operator, so a rule on a parent
                          subject also catches every child beneath it
  cpc_customersegment  -> customerid.cpc_customersegment, read from the contact or account

It also extends the subject tree to cover the corporate and service processes, which previously
had no home in it, and cleans up two rank collisions plus a duplicated template.

Re-runnable.
"""
import time

import dv

# featuremask bit 1 = "available for cases". Subjects created via the Web API
# default to null, which hides them from the case subject lookup.
CASE_SUBJECT = 1

P = "cpc_"

# ---------------------------------------------------------------- subject tree additions
# Retail was seeded in step 24. Corporate and cross cutting service work needs the same treatment
# before their templates can be re-pointed off case category.
TREE = [
    ("Corporate Banking", [
        ("Credit and Lending", ["Corporate Credit", "Annual Credit Review",
                                "Covenant Monitoring", "Limit Amendment"]),
        ("Trade Finance", ["Letter of Credit", "Bank Guarantee", "Documentary Collection"]),
        ("Cash Management", ["Corporate Payments", "Liquidity and Sweeps"]),
        ("Corporate Escalations", []),
    ]),
    ("Service and Technical", [
        ("Service Requests", ["General Service Request", "Channel Enablement"]),
        ("Technical Support", ["Device and Terminal Fault", "Field Visit"]),
        ("Billing and Invoicing", []),
    ]),
]

# Every case category value mapped onto the subject it was really standing in for.
CATEGORY_TO_SUBJECT = {
    "Complaint": "Complaints",
    "Fraud Dispute": "Fraud and Security",
    "Card Dispute": "Card Disputes",
    "Payment Investigation": "Payments and Transfers",
    "Retail Lending": "Lending",
    "Onboarding / KYC": "Onboarding and KYC",
    "Digital Banking": "Digital Banking",
    "Account Servicing": "Accounts and Servicing",
    "Card Services": "Cards",
    "Collections": "Arrears and Repayment Plan",
    "Corporate Credit": "Corporate Credit",
    "Credit Review": "Annual Credit Review",
    "Trade Finance": "Trade Finance",
    "Technical Issue": "Technical Support",
    "Service Request": "Service Requests",
    "Billing Query": "Billing and Invoicing",
}

# Two templates outranked the ones they should defer to, and their rules pointed at subjects far
# broader than the process they drive.
RERANK = [
    ("Retail Mortgage Application", 23, "Mortgage"),
    ("Retail Card Limit Increase", 24, "Card Limit Increase"),
]


def with_lock(fn, what):
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


def subject_index():
    return {s["title"]: s["subjectid"] for s in
            dv.get("subjects?$select=subjectid,title&$top=1000")["value"]}


def ensure_subject(title, parent_id, index):
    if title in index:
        return index[title]
    body = {"title": title, "featuremask": CASE_SUBJECT}
    if parent_id:
        body["parentsubject@odata.bind"] = f"/subjects({parent_id})"
    sid = dv.new_id(dv.post("subjects", body))
    index[title] = sid
    print("  + subject", title)
    return sid


def build_tree():
    index = subject_index()
    root = dv.find_one("subjects", "title eq 'Default Subject'", "subjectid")
    root_id = root["subjectid"] if root else None
    for top, groups in TREE:
        tid = ensure_subject(top, root_id, index)
        for group, leaves in groups:
            gid = ensure_subject(group, tid, index)
            for leaf in leaves:
                ensure_subject(leaf, gid, index)
    return subject_index()


def category_labels():
    """Option value -> label for the column being retired, so old rules can be read back."""
    a = dv.get(f"EntityDefinitions(LogicalName='incident')/Attributes"
               f"(LogicalName='{P}casecategory')/Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
               f"?$expand=OptionSet")
    return {str(o["Value"]): o["Label"]["UserLocalizedLabel"]["Label"]
            for o in a["OptionSet"]["Options"]}


def migrate_rules(subjects, cats):
    rows = dv.get(f"{P}matchrules?$select={P}matchruleid,{P}name,{P}attributename,{P}operator,"
                  f"{P}value,{P}valuelabel&$top=500")["value"]
    moved_cat = moved_seg = skipped = 0

    for r in rows:
        rid = r[f"{P}matchruleid"]
        attr = r[f"{P}attributename"]

        if attr == f"{P}customersegment":
            # Same option values, just read from the customer instead of the case.
            dv.patch(f"{P}matchrules({rid})", {
                f"{P}attributename": "customerid.cpc_customersegment",
                f"{P}attributelabel": "Customer \u203a Customer Segment"})
            moved_seg += 1
            continue

        if attr != f"{P}casecategory":
            continue

        titles, ids = [], []
        for v in str(r[f"{P}value"] or "").split(";"):
            v = v.strip()
            if not v:
                continue
            title = CATEGORY_TO_SUBJECT.get(cats.get(v, ""))
            sid = subjects.get(title) if title else None
            if sid:
                titles.append(title)
                ids.append(sid)
            else:
                print(f"    ! no subject for category {cats.get(v, v)!r}")

        if not ids:
            skipped += 1
            continue

        # "is at or under" keeps a rule written against a broad category working once that
        # category becomes a parent node with children hanging off it.
        dv.patch(f"{P}matchrules({rid})", {
            f"{P}attributename": "subjectid",
            f"{P}attributelabel": "Subject",
            f"{P}operator": 11,
            f"{P}value": ";".join(ids),
            f"{P}valuelabel": " or ".join(titles),
            f"{P}name": r[f"{P}name"].replace("Case Category", "Subject")[:100]})
        moved_cat += 1

    print(f"  ~ {moved_cat} category rule(s) moved to the subject tree")
    print(f"  ~ {moved_seg} segment rule(s) moved to the customer")
    if skipped:
        print(f"  ! {skipped} rule(s) left alone, no subject mapping")


def fix_templates(subjects):
    for name, rank, subject_title in RERANK:
        ex = dv.find_one(f"{P}caseprocesstemplates", f"{P}name eq '{name}'",
                         f"{P}caseprocesstemplateid")
        if not ex:
            continue
        tid = ex[f"{P}caseprocesstemplateid"]
        dv.patch(f"{P}caseprocesstemplates({tid})", {f"{P}rank": rank})
        sid = subjects.get(subject_title)
        if not sid:
            continue
        for r in dv.get(f"{P}matchrules?$select={P}matchruleid,{P}attributename"
                        f"&$filter=_{P}template_value eq {tid}")["value"]:
            if r[f"{P}attributename"] == "subjectid":
                dv.patch(f"{P}matchrules({r[f'{P}matchruleid']})", {
                    f"{P}operator": 11, f"{P}value": sid, f"{P}valuelabel": subject_title})
        print(f"  ~ {name}: rank {rank}, subject {subject_title}")

    dupes = dv.get(f"{P}caseprocesstemplates?$select={P}caseprocesstemplateid,{P}name"
                   f"&$filter={P}name eq 'Customer onboarding' and statecode eq 0")["value"]
    for d in dupes[1:]:
        dv.patch(f"{P}caseprocesstemplates({d[f'{P}caseprocesstemplateid']})",
                 {"statecode": 1, "statuscode": 2})
        print("  ~ retired duplicate 'Customer onboarding'")


def hide_category():
    """
    The column stays in the database so historic cases keep their value, but it is taken off
    advanced find so it can no longer be picked as a targeting attribute in the rule builder.
    """
    meta = dv.get(f"EntityDefinitions(LogicalName='incident')/Attributes"
                  f"(LogicalName='{P}casecategory')?$select=MetadataId,SchemaName")
    body = {
        "@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
        "MetadataId": meta["MetadataId"],
        "SchemaName": meta["SchemaName"],
        "IsValidForAdvancedFind": {"Value": False, "CanBeChanged": True,
                                   "ManagedPropertyLogicalName": "canmodifysearchsettings"},
        "DisplayName": dv.label("Case Category (retired - use Subject)"),
    }
    # The update is addressed by metadata id; addressing it by logical name is rejected.
    with_lock(lambda: dv.call(
        "PUT", f"EntityDefinitions(LogicalName='incident')/Attributes({meta['MetadataId']})", body),
        "hide case category")
    print("  ~ case category hidden from advanced find")


def main():
    print("Subject tree")
    subjects = build_tree()

    print("Match rules")
    migrate_rules(subjects, category_labels())

    print("Templates")
    fix_templates(subjects)

    print("Retiring case category")
    try:
        hide_category()
    except RuntimeError as e:
        print("  ! could not hide the column:", str(e)[:200])

    dv.publish_all()
    print("\nDone.")


if __name__ == "__main__":
    main()

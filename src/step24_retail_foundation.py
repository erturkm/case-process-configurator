"""Step 24: retail banking foundation for the RAKBANK demo.

Builds the service catalogue (subject tree), the retail operating teams, the public queues
those teams work from, and the extra case categories the retail processes match on.

Safe to re-run: every write is keyed on name and skipped when it already exists.
"""
import dv

# featuremask bit 1 = "available for cases". Subjects created via the Web API
# default to null, which hides them from the case subject lookup.
CASE_SUBJECT = 1

P = dv.PREFIX

# ---------------------------------------------------------------- case categories
NEW_CATEGORIES = [
    (12, "Card Dispute"),
    (13, "Payment Investigation"),
    (14, "Digital Banking"),
    (15, "Account Servicing"),
    (16, "Card Services"),
    (17, "Collections"),
]

# ---------------------------------------------------------------- teams
NEW_TEAMS = [
    ("Card Operations", "Issues, replaces and blocks debit and credit cards and runs chargebacks."),
    ("Payments Investigations", "Traces domestic and international transfers and recalls funds."),
    ("Digital Banking Support", "Restores access to the mobile app and online banking."),
    ("Premier Banking", "Relationship managers for Premier and Priority customers."),
    ("Collections and Recoveries", "Works early arrears and agrees repayment arrangements."),
    ("Branch Operations", "Handles in-branch verification, signatures and cash services."),
    ("Quality and Regulatory", "Reviews regulated complaints and central bank referrals."),
]

# ---------------------------------------------------------------- queues (name, team, description)
QUEUES = [
    ("Retail Contact Centre", "Contact Centre Tier 1",
     "First line queue for all inbound retail service requests."),
    ("Card Disputes and Chargebacks", "Card Operations",
     "Disputed card transactions worked through the scheme chargeback cycle."),
    ("Fraud Investigations", "Fraud Operations",
     "Suspected unauthorised transactions, scams and compromised credentials."),
    ("Payments Investigations", "Payments Investigations",
     "Missing, delayed or misdirected transfers requiring a trace or recall."),
    ("Retail Lending Applications", "Retail Lending Operations",
     "Personal loan, auto loan, mortgage and credit card applications."),
    ("Onboarding and KYC", "Onboarding Operations",
     "New account opening, KYC refresh and document remediation."),
    ("Complaints and Redress", "Complaints Management",
     "Logged complaints under investigation and redress."),
    ("Regulatory Referrals", "Quality and Regulatory",
     "Complaints escalated to or received from the central bank."),
    ("Digital Banking Support", "Digital Banking Support",
     "Login, registration and mobile app access failures."),
    ("Premier Service Desk", "Premier Banking",
     "Dedicated queue for Premier and Priority relationships."),
    ("Collections - Early Arrears", "Collections and Recoveries",
     "Accounts one to sixty days past due."),
    ("Card Services", "Card Operations",
     "Replacements, limit changes, PIN and card delivery."),
]

# ---------------------------------------------------------------- subject tree
# (title, [children]) nested under the "Retail Banking" root.
TREE = [
 ("Accounts and Servicing", [
    "Account Servicing",                 # existing, reparented
    "Address and Contact Update",
    "Account Closure",
    "Cheque Book and Standing Instructions",
    "Salary Transfer and Payroll",
 ]),
 ("Statements and Certificates", [
    "Statements",                        # existing
    "Balance Certificate",
    "Liability and Clearance Letter",
 ]),
 ("Cards", [
    "Card Disputes",                     # existing
    "Card Application",
    "Card Limit Increase",
    "Lost or Stolen Card",
    "Card Delivery and PIN",
 ]),
 ("Lending", [                            # existing subject, promoted to a group
    "Personal Loan",
    "Auto Loan",
    "Mortgage",
    "Loan Settlement and Early Payoff",
    "Arrears and Repayment Plan",
 ]),
 ("Payments and Transfers", [
    "Payments",                          # existing
    "Domestic Transfer",
    "International Transfer",
    "Direct Debit and Utility Payment",
 ]),
 ("Digital Banking", [                    # existing subject, promoted to a group
    "Mobile App Access",
    "Online Banking Login",
    "Digital Registration and Devices",
 ]),
 ("Fees and Charges", [                   # existing subject, promoted to a group
    "Fee Reversal Request",
    "Interest and Profit Query",
 ]),
 ("Fraud and Security", [
    "Fraud",                             # existing
    "Unauthorised Transaction",
    "Phishing and Scam Report",
 ]),
 ("Complaints", [                         # existing subject, promoted to a group
    "Service Quality Complaint",
    "Regulatory Complaint",
 ]),
 ("Onboarding and KYC", [
    "KYC and Onboarding",                # existing
    "New Account Opening",
    "KYC Refresh",
    "Document Remediation",
 ]),
]


def ensure_categories():
    for value, lbl in NEW_CATEGORIES:
        try:
            dv.post("InsertOptionValue", {
                "EntityLogicalName": "incident", "AttributeLogicalName": f"{P}_casecategory",
                "Value": value, "Label": dv.label(lbl)})
            print("  + category", value, lbl)
        except RuntimeError as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                print("  = category", value, lbl)
            else:
                raise


def ensure_teams(bu):
    out = {}
    for t in dv.get("teams?$select=name,teamid&$filter=teamtype eq 0&$top=500")["value"]:
        out[t["name"]] = t["teamid"]
    for name, desc in NEW_TEAMS:
        if name in out:
            print("  = team", name)
            continue
        out[name] = dv.new_id(dv.post("teams", {
            "name": name, "description": desc, "teamtype": 0,
            "businessunitid@odata.bind": f"/businessunits({bu})"}))
        print("  + team", name)
    return out


def ensure_queues(teams):
    have = {q["name"]: q["queueid"] for q in
            dv.get("queues?$select=name,queueid&$top=500")["value"]}
    out = {}
    for name, team, desc in QUEUES:
        if name in have:
            out[name] = have[name]
            print("  = queue", name)
            continue
        body = {"name": name, "description": desc, "queueviewtype": 0}
        qid = dv.new_id(dv.post("queues", body))
        out[name] = qid
        print("  + queue", name)
    return out


def ensure_subjects():
    have = {s["title"]: s for s in
            dv.get("subjects?$select=title,subjectid,_parentsubject_value&$top=500")["value"]}
    root_name = "Retail Banking"
    default = have.get("Default Subject")
    default_id = default["subjectid"] if default else None

    if root_name in have:
        root = have[root_name]["subjectid"]
        print("  = subject", root_name)
    else:
        body = {"title": root_name, "featuremask": CASE_SUBJECT,
                "description": "Everything a retail banking customer can contact the bank about."}
        if default_id:
            body["parentsubject@odata.bind"] = f"/subjects({default_id})"
        root = dv.new_id(dv.post("subjects", body))
        print("  + subject", root_name)

    for group, children in TREE:
        if group in have:
            gid = have[group]["subjectid"]
            if have[group].get("_parentsubject_value") != root:
                dv.patch(f"subjects({gid})", {"parentsubject@odata.bind": f"/subjects({root})"})
                print("  ~ subject", group, "-> Retail Banking")
        else:
            gid = dv.new_id(dv.post("subjects", {
                "title": group, "featuremask": CASE_SUBJECT,
                "parentsubject@odata.bind": f"/subjects({root})"}))
            print("  + subject", group)
            have[group] = {"subjectid": gid}

        for child in children:
            if child in have:
                cid = have[child]["subjectid"]
                if have[child].get("_parentsubject_value") != gid:
                    dv.patch(f"subjects({cid})",
                             {"parentsubject@odata.bind": f"/subjects({gid})"})
                    print("    ~ subject", child, "->", group)
            else:
                cid = dv.new_id(dv.post("subjects", {
                    "title": child, "featuremask": CASE_SUBJECT,
                    "parentsubject@odata.bind": f"/subjects({gid})"}))
                have[child] = {"subjectid": cid, "_parentsubject_value": gid}
                print("    + subject", child)


def main():
    bu = dv.get("businessunits?$select=businessunitid"
                "&$filter=parentbusinessunitid eq null")["value"][0]["businessunitid"]
    print("Case categories")
    ensure_categories()
    print("Teams")
    teams = ensure_teams(bu)
    print("Queues")
    ensure_queues(teams)
    print("Subject tree")
    ensure_subjects()
    print("\nDone.")


if __name__ == "__main__":
    main()

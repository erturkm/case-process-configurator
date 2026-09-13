"""Build the email classification categories that match the cases in this org.

The three categories created by hand - Credit Cards, Loans, Accounts - are far
coarser than the process templates the configurator can apply, so a classified
email tells an agent very little that the subject tree does not already say. This
replaces them with a two-level set derived from the actual case mix, mirroring the
subject tree so an AI category and a case subject line up.

What the model classifies against is msdyn_categorydescription on the category's
version record, not the name, so each description here is written the way a
customer would describe the problem rather than the way the bank labels it.

Categories are created deactivated by design: Dataverse only trains and activates
them through the Customer Service admin centre, so the final activation stays a
deliberate admin action.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step40_email_categories.py            # create or update
    python3 step40_email_categories.py --prune    # also remove the three originals
"""
import argparse

import dv

# parent -> [(child, description)]
TREE = {
    "Cards": [
        ("Card Disputes",
         "The customer disputes one or more card transactions: charged twice for the "
         "same purchase, billed by a merchant after cancelling a subscription, an ATM "
         "that did not dispense cash, a hotel or restaurant amount higher than agreed, "
         "or a refund that never arrived. The customer accepts they used the card but "
         "disagrees with what was charged."),
        ("Lost or Stolen Card",
         "The customer has lost their card, had it stolen, or believes it is no longer "
         "in their possession, and wants it blocked and replaced."),
        ("Card Limit Increase",
         "The customer asks to change the credit limit on a card, either an increase, a "
         "temporary increase for a specific expense, or a reduction."),
        ("Card Application",
         "The customer wants to apply for a new credit card or asks about the status of "
         "a card application already submitted."),
        ("Card Delivery and PIN",
         "The customer's card was declined, has not been delivered, needs activating, or "
         "there is a problem with the PIN. Includes cards refused while travelling "
         "despite a travel notification."),
    ],
    "Payments and Transfers": [
        ("International Transfer",
         "A cross-border or SWIFT payment has not arrived, is delayed, was sent to the "
         "wrong beneficiary, or the customer is asking about charges and exchange rates "
         "on an overseas transfer."),
        ("Domestic Transfer",
         "A transfer within the UAE has failed, been delayed, or gone to the wrong "
         "account, including transfers made by IBAN between local banks."),
        ("Salary Transfer and Payroll",
         "The customer's salary or wage has not been credited, was credited late or for "
         "the wrong amount, or they are asking about WPS and their employer's payroll "
         "transfer."),
        ("Direct Debit and Standing Instructions",
         "A recurring payment, standing instruction, direct debit or utility bill "
         "payment has failed, been duplicated, or needs setting up or cancelling."),
    ],
    "Accounts and Servicing": [
        ("New Account Opening",
         "A prospective or existing customer wants to open an account - current, "
         "savings, joint or business - and is asking about eligibility, required "
         "documents or how long it takes."),
        ("KYC and Documents",
         "The bank needs updated identification or proof of address, the customer's "
         "Emirates ID or passport has expired, or an account has been restricted "
         "pending a periodic KYC review."),
        ("Account Closure",
         "The customer wants to close an account, asks what the closure process "
         "involves, or needs a clearance letter confirming the account is settled."),
        ("Personal Details Update",
         "The customer wants to change the address, mobile number, email address or "
         "other personal details held on their record."),
        ("Cheques",
         "A cheque has been returned unpaid or bounced, or the customer wants to order "
         "a cheque book or stop a cheque."),
    ],
    "Lending": [
        ("Mortgage",
         "Anything concerning a home loan: a new mortgage application, a rate switch "
         "between fixed and variable, early repayment, or the status of a property "
         "purchase in progress."),
        ("Personal Loan",
         "A new personal loan application, a question about eligibility or instalments, "
         "or the status of a loan already applied for."),
        ("Auto Loan",
         "A car or vehicle finance application, or a question about an existing auto "
         "loan and its instalments."),
        ("Loan Settlement",
         "The customer wants to settle a loan early or in full and needs a settlement "
         "quote, an outstanding balance, or a liability and clearance letter."),
        ("Arrears and Collections",
         "The customer has missed payments, is in arrears, wants a repayment plan, or "
         "is responding to contact from the collections team - including complaints "
         "about being chased after the debt was already paid."),
    ],
    "Digital Banking": [
        ("Online and Mobile Access",
         "The customer cannot log in to online or mobile banking, is locked out, needs "
         "a password reset, or the app is not working."),
        ("Device Registration and OTP",
         "The customer has changed phone or device, is not receiving one-time "
         "passcodes, or needs to re-register for digital banking."),
    ],
    "Fraud and Security": [
        ("Unauthorised Transaction",
         "The customer says money left their account or card without their authorisation "
         "and they did not make the transaction. Treat as urgent."),
        ("Phishing and Scams",
         "The customer has received a suspicious message, call or link claiming to be "
         "from the bank, or believes they have been targeted by a scam. Includes "
         "reports made without any financial loss."),
    ],
    "Complaints": [
        ("Service Quality Complaint",
         "The customer is dissatisfied with how the bank has handled something: no "
         "response, repeated calls, long waits, conflicting information, or a poor "
         "branch or contact centre experience. The tone is one of grievance rather "
         "than a request."),
        ("Regulatory Complaint",
         "The customer refers to the Central Bank, a regulator, an ombudsman or legal "
         "action, or states they intend to escalate the matter outside the bank."),
    ],
    "Fees and Statements": [
        ("Fee Dispute",
         "The customer questions a fee or charge applied to their account and asks for "
         "it to be waived, reversed or explained - annual fees, late fees, or charges "
         "they did not expect."),
        ("Statements and Certificates",
         "The customer requests bank statements, a balance certificate, an audit "
         "confirmation or a similar document, often for a visa, an embassy or a "
         "third party."),
    ],
}

ORIGINALS = ["Credit Cards", "Loans", "Accounts"]

DRAFT = 1          # msdyn_categorystatus: created but not trained
INACTIVE = 1       # statecode


def existing():
    return {c["msdyn_name"]: c for c in
            dv.get("msdyn_emailclassificationcategories?$select="
                   "msdyn_emailclassificationcategoryid,msdyn_name,msdyn_categorystatus,"
                   "_msdyn_parentcategoryid_value,_msdyn_activeversion_value&$top=200")["value"]}


def ensure_category(name, description, parent_id=None):
    have = existing().get(name)
    if have:
        cid = have["msdyn_emailclassificationcategoryid"]
        verb = "="
    else:
        body = {"msdyn_name": name}
        if parent_id:
            body["msdyn_emailclassificationcategory_ParentCategory_Children@odata.bind"] = \
                f"/msdyn_emailclassificationcategories({parent_id})"
        cid = dv.new_id(dv.post("msdyn_emailclassificationcategories", body))
        verb = "+"

    if description:
        set_description(cid, description)

    print(f"  {verb} {'  ' if parent_id else ''}{name}")
    return cid


def set_description(category_id, description):
    """The description lives on a version record, which is what the model reads."""
    versions = dv.get("msdyn_emailclassificationcategoryversions?$select="
                      "msdyn_emailclassificationcategoryversionid,msdyn_categorydescription,"
                      f"msdyn_categoryversion&$filter=_msdyn_emailclassificationcategory_value "
                      f"eq {category_id}&$orderby=msdyn_categoryversion desc")["value"]

    if versions:
        current = versions[0]
        if (current.get("msdyn_categorydescription") or "").strip() == description.strip():
            return
        dv.patch("msdyn_emailclassificationcategoryversions"
                 f"({current['msdyn_emailclassificationcategoryversionid']})",
                 {"msdyn_categorydescription": description})
        return

    vid = dv.new_id(dv.post("msdyn_emailclassificationcategoryversions", {
        "msdyn_categorydescription": description,
        "msdyn_categoryversion": 1,
        "msdyn_emailclassificationcategory@odata.bind":
            f"/msdyn_emailclassificationcategories({category_id})",
    }))
    dv.patch(f"msdyn_emailclassificationcategories({category_id})", {
        "msdyn_ActiveVersion@odata.bind":
            f"/msdyn_emailclassificationcategoryversions({vid})",
    })


def prune():
    have = existing()
    for name in ORIGINALS:
        row = have.get(name)
        if not row:
            continue
        cid = row["msdyn_emailclassificationcategoryid"]
        try:
            dv.patch(f"msdyn_emailclassificationcategories({cid})",
                     {"msdyn_ActiveVersion@odata.bind": None})
        except RuntimeError:
            pass
        for v in dv.get("msdyn_emailclassificationcategoryversions?$select="
                        "msdyn_emailclassificationcategoryversionid&$filter="
                        f"_msdyn_emailclassificationcategory_value eq {cid}")["value"]:
            dv.call("DELETE", "msdyn_emailclassificationcategoryversions"
                    f"({v['msdyn_emailclassificationcategoryversionid']})")
        dv.call("DELETE", f"msdyn_emailclassificationcategories({cid})")
        print(f"  - removed {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="delete the three hand-made starter categories")
    args = ap.parse_args()

    print("Email classification categories")
    total = 0
    for parent, children in TREE.items():
        pid = ensure_category(parent, None)
        for name, description in children:
            ensure_category(name, description, pid)
            total += 1

    if args.prune:
        print("\nRemoving starter categories")
        prune()

    print(f"\n{len(TREE)} group(s), {total} classifiable categor(ies).")
    print("Train and activate them in Customer Service admin centre > "
          "Productivity > Email classification.")


if __name__ == "__main__":
    main()

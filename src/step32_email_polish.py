"""Re-render the demo email threads on RAKBANK letterhead.

The first pass produced readable but plain correspondence: no signature, no case
reference, no stated commitment, no footer.

Emails are rebuilt from the scenario prose in step30_retail_cases rather than by
re-parsing what is already in Dataverse, so this script is idempotent - running it
twice produces the same result instead of nesting letterhead inside letterhead.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step32_email_polish.py
"""
import datetime as dt
import re

import dv
import emailfmt
import step30_retail_cases as src

# Which advisor persona owns the correspondence for each case.
ADVISOR = {
    "Disputed card transaction": "disputes",
    "Unauthorised transfer": "fraud",
    "Phishing SMS reported": "fraud",
    "International transfer": "payments",
    "Domestic transfer credited": "payments",
    "Cannot log in to online banking": "digital",
    "Mobile app crashes": "digital",
    "Credit card application": "premier",
    "Auto loan application": "lending",
    "Mortgage application": "mortgage",
    "Personal loan application": "lending",
    "Credit card limit increase": "cards",
    "Lost card in Bangkok": "cards",
    "Complaint - branch service quality": "branch",
    "Regulatory complaint": "regulatory",
    "Update registered address": "servicing",
    "Request to close current account": "servicing",
    "Set up standing instruction": "servicing",
    "Dispute of late payment fee": "complaints",
    "Missed instalments": "collections",
    "Periodic KYC refresh": "compliance",
    "New account opening": "onboarding",
}

# The commitment each bank reply makes.
NEXT_STEP = {
    "Disputed card transaction":
        "Your replacement card is being couriered and will arrive within three working days. "
        "We will write to you with the chargeback outcome by <b>18 September</b>, and the "
        "provisional credit stands in the meantime.",
    "Unauthorised transfer":
        "A fraud specialist will call you within the hour on your registered mobile to complete "
        "your statement. The recall has been sent to the beneficiary bank and we will confirm "
        "the result within <b>five working days</b>.",
    "Phishing SMS reported":
        "No action is needed from you. We have referred the sending number for takedown and "
        "will add it to our blocklist within 24 hours.",
    "International transfer":
        "The SWIFT trace is with our correspondent bank. We will update you as soon as they "
        "respond, and in any event by <b>11 September</b>.",
    "Domestic transfer credited":
        "The recall is with the beneficiary bank. They have five working days to respond and we "
        "will call you with the outcome as soon as we hear.",
    "Cannot log in to online banking":
        "Please reinstall the app and register your new device. If the OTP still does not arrive, "
        "reply to this email and we will verify your registered number and re-issue it the same "
        "day.",
    "Mobile app crashes":
        "Our technology team is targeting a fix in the next app release. We will email you as "
        "soon as it is available in the store; web banking remains fully available.",
    "Credit card application":
        "Please return the signed application form with your Emirates ID and salary certificate. "
        "As a Premier customer your application will be assessed within <b>two working days</b> "
        "of receipt.",
    "Auto loan application":
        "Send us the dealer quotation, Emirates ID and three months of salary slips. We will "
        "instruct the independent valuation on receipt and issue a decision within "
        "<b>three working days</b>.",
    "Mortgage application":
        "Your pre-approval is valid for sixty days. Our panel valuer will contact you directly to "
        "arrange access and we expect their report within <b>five working days</b>.",
    "Personal loan application":
        "Once we have your statements, salary certificate and the two settlement letters we will "
        "assess affordability and come back to you within <b>three working days</b>.",
    "Credit card limit increase":
        "Your request is with our credit assessment team. We will confirm the decision by SMS and "
        "email within <b>two working days</b>, well ahead of your travel in October.",
    "Lost card in Bangkok":
        "Collection details for your emergency cash will arrive by SMS within the next hour. Your "
        "replacement cards will be ready at your home branch when you return.",
    "Complaint - branch service quality":
        "I will complete our review and write to you with a substantive response within "
        "<b>five working days</b>. In the meantime, reply to this email and I will arrange your "
        "Emirates ID update remotely so you do not need to travel again.",
    "Regulatory complaint":
        "Your case is with a senior case manager. You will receive our full written response "
        "within the regulatory timeframe and we will copy the outcome to the Central Bank.",
    "Update registered address":
        "Your address is updated with immediate effect. For the mobile number change, reply with "
        "a convenient time and we will complete a short verification call.",
    "Request to close current account":
        "Once the AED 430 card balance is settled and the standing instruction is cancelled we "
        "will issue your clearance letter and final statement within <b>two working days</b> and "
        "remit the balance to your nominated account.",
    "Set up standing instruction":
        "Reply with the beneficiary name, IBAN and bank and we will activate the instruction in "
        "time for the <b>1 October</b> payment.",
    "Dispute of late payment fee":
        "The AED 312 reversal will appear on your account within <b>two working days</b>. No "
        "adverse credit marker has been recorded and none will be reported.",
    "Missed instalments":
        "A collections specialist will call you within <b>two working days</b> to agree the "
        "arrangement. No recovery action will be taken while we assess your request.",
    "Periodic KYC refresh":
        "Please upload your renewed Emirates ID and passport through the app or reply to this "
        "email. Your account remains fully available while we complete the review.",
    "New account opening":
        "Start your application in the app and we will verify your documents digitally. Most "
        "accounts are open and ready for salary transfer within <b>one working day</b>.",
}

SIGN_OFF = re.compile(r"^(kind regards|regards|thank you|many thanks|yours)\b", re.I)


def key_for(title):
    for k in ADVISOR:
        if title.startswith(k):
            return k
    return None


def split_body(text):
    """Scenario prose -> paragraphs, with the hand-written sign-off removed.

    Source bodies close with either a bank team name or the customer's own name,
    sometimes preceded by "Kind regards" on the same paragraph. All of it is
    replaced by the rendered signature block.
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    while paras:
        last = paras[-1]
        if last.startswith("RAKBANK") or SIGN_OFF.match(last) or \
                last.splitlines()[-1].startswith("RAKBANK"):
            paras.pop()
            continue
        break
    return paras


def main():
    cases = {c["title"]: c for c in
             dv.get("incidents?$select=incidentid,title,ticketnumber,_customerid_value"
                    "&$top=500")["value"]}
    agent = dv.get("systemusers?$select=systemuserid&$filter=domainname ne null and "
                   "isdisabled eq false&$top=1")["value"][0]["systemuserid"]
    contacts = {c["contactid"]: c for c in
                dv.get("contacts?$select=contactid,fullname,mobilephone&$top=500")["value"]}

    now = dt.datetime.now(dt.timezone.utc)
    rebuilt = 0
    for (title, _subj, _cemail, _prio, days, _steps, _pref, _desc, thread) in src.CASES:
        case = cases.get(title)
        k = key_for(title)
        if not case or not k:
            print(f"  ! skipped {title[:56]}")
            continue
        cid = case["incidentid"]
        contact = contacts.get(case.get("_customerid_value"), {})

        for old in dv.get(f"emails?$select=activityid"
                          f"&$filter=_regardingobjectid_value eq {cid}")["value"]:
            dv.call("DELETE", f"emails({old['activityid']})")

        opened = now - dt.timedelta(days=days)
        for incoming, esub, ebody, hrs in thread:
            paras = split_body(ebody)
            if incoming:
                html = emailfmt.customer(paras, contact.get("fullname", ""),
                                         contact.get("mobilephone"),
                                         sent_from_phone=len(paras) == 1)
            else:
                has_greeting = bool(paras) and paras[0].startswith("Dear")
                greeting = paras[0] if has_greeting else "Dear Customer,"
                body = paras[1:] if has_greeting else paras
                html = emailfmt.bank(greeting, body, ADVISOR[k],
                                     case["ticketnumber"], NEXT_STEP.get(k))
            src.email_html(cid, case["_customerid_value"], agent, incoming, esub, html,
                           opened + dt.timedelta(hours=hrs))
            rebuilt += 1
        print(f"  ~ {title[:56]:<56} {len(thread)} email(s)")

    print(f"\n{rebuilt} email(s) rebuilt on letterhead")


if __name__ == "__main__":
    main()

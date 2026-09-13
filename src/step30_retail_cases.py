"""Seed twenty retail banking cases for the RAKBANK demo.

Each case carries a real subject (which is what the match engine now targets), a
customer whose segment lives on the contact record, an inbound customer email and
the bank's reply, and a partially walked process so the case panel widgets show
completed tasks, an active task, and live SLA state.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step30_retail_cases.py
"""
import datetime as dt
import json
import time

import dv

P = dv.PREFIX
LOW, NORMAL, HIGH = 3, 2, 1
EMAIL_ORIGIN = 1

# (title, subject, customer email, priority, days_ago, steps_to_walk, prefer,
#  description, [(incoming?, subject, body, hours_after_open)])
CASES = [
    ("Disputed card transaction - AED 4,320 at online merchant",
     "Card Disputes", "aisha.almarzouqi@contoso.ae", HIGH, 6, 3, "pos",
     "Cardholder disputes a card-not-present transaction she does not recognise. Card remains in her possession.",
     [(True, "I did not make this transaction",
       "Hello,\n\nI have just checked my statement and there is a charge of AED 4,320 on 30 August to an online merchant I have never heard of. My card has not left my handbag. Please block the card and reverse this charge.\n\nRegards,\nAisha Al Marzouqi", 0),
      (False, "RE: I did not make this transaction",
       "Dear Ms Al Marzouqi,\n\nThank you for reporting this. We have blocked the card immediately and raised dispute reference CD-4471. A provisional credit of AED 4,320 has been applied to your account while we investigate with the merchant's acquiring bank.\n\nYou will receive a replacement card within three working days.\n\nKind regards,\nRAKBANK Card Disputes Team", 2),
      (True, "RE: RE: I did not make this transaction",
       "Thank you, I can see the credit. Please confirm when the investigation closes.\n\nAisha", 20)]),

    ("Unauthorised transfer of AED 12,000 from savings account",
     "Unauthorised Transaction", "layla.mansour@contoso.ae", HIGH, 4, 3, "pos",
     "Customer reports funds moved out of her savings account overnight. Suspected account takeover following a phishing SMS.",
     [(True, "URGENT - money missing from my account",
       "I woke up to an SMS saying AED 12,000 was transferred from my savings account to an account I do not recognise. I did not authorise this. I received a text yesterday asking me to reconfirm my card details and I am worried I clicked it.\n\nPlease freeze everything.\n\nLayla Mansour", 0),
      (False, "RE: URGENT - money missing from my account",
       "Dear Ms Mansour,\n\nWe have frozen all outbound payments on your accounts and disabled digital banking access as a precaution. Our fraud team has recalled the transfer and has opened case reference FR-8823.\n\nPlease do not action any further SMS or email asking for your credentials. A fraud specialist will call you within the hour on your registered mobile.\n\nRAKBANK Fraud and Security", 1)]),

    ("International transfer to UK not received after 5 days",
     "International Transfer", "omar.haddad@contoso.ae", NORMAL, 9, 2, "neu",
     "Outbound SWIFT transfer to a UK beneficiary has not credited. Trace required with the correspondent bank.",
     [(True, "Transfer still not arrived",
       "I sent GBP 6,500 to my daughter's account in Manchester on 26 August. It has been five working days and nothing has arrived. The reference is TT-99213. Can you trace it please?\n\nOmar Haddad", 0),
      (False, "RE: Transfer still not arrived",
       "Dear Mr Haddad,\n\nWe have raised a SWIFT trace (MT199) with our correspondent bank for reference TT-99213. Traces of this type typically complete within three to five working days. We will update you as soon as the correspondent responds.\n\nRAKBANK Payments Investigation", 4)]),

    ("Domestic transfer credited to wrong beneficiary",
     "Domestic Transfer", "imran.qureshi@contoso.ae", NORMAL, 3, 2, "pos",
     "Customer selected a saved beneficiary in error. Requesting recall of AED 2,150.",
     [(True, "Sent money to the wrong person",
       "I picked the wrong saved beneficiary in the app and sent AED 2,150 to the wrong person this morning. Can you please recall it?\n\nImran Qureshi", 0),
      (False, "RE: Sent money to the wrong person",
       "Dear Mr Qureshi,\n\nWe have submitted a recall request to the beneficiary bank. Please note that under UAE Central Bank rules the receiving bank requires the beneficiary's consent to return the funds, so we cannot guarantee recovery. We will advise you of the outcome within five working days.\n\nRAKBANK Payments Investigation", 3)]),

    ("Cannot log in to online banking after device change",
     "Online Banking Login", "maryam.alzaabi@contoso.ae", NORMAL, 2, 2, "pos",
     "Customer changed phone and can no longer pass device binding. Needs digital access restored.",
     [(True, "Locked out of online banking",
       "I changed my phone last week and now the app will not let me in. It keeps saying device not recognised and the OTP never arrives. I need to pay my rent today.\n\nMaryam Al Zaabi", 0),
      (False, "RE: Locked out of online banking",
       "Dear Ms Al Zaabi,\n\nWe have reset your device binding and cleared the old registration. Please uninstall and reinstall the app, then log in with your username and password. You will be asked to register your new device and will receive a fresh OTP.\n\nIf the OTP still does not arrive, please confirm your registered mobile number so we can verify it against our records.\n\nRAKBANK Digital Banking Support", 1)]),

    ("Mobile app crashes on login after latest update",
     "Mobile App Access", "daniel.okafor@contoso.ae", NORMAL, 1, 1, "neu",
     "App closes immediately after splash screen on Android following the September release.",
     [(True, "App keeps closing",
       "Since the update on Monday the app closes as soon as I open it. I am on a Samsung S23. Web banking works fine.\n\nDaniel Okafor", 0),
      (False, "RE: App keeps closing",
       "Dear Mr Okafor,\n\nThank you for reporting this. We are aware of a compatibility issue affecting a small number of Android devices on the latest release and our technology team is working on a fix. In the meantime please continue to use web banking.\n\nWe will email you as soon as the update is available.\n\nRAKBANK Digital Banking Support", 5)]),

    ("Credit card application - Premier customer",
     "Card Application", "fatima.alsuwaidi@contoso.ae", NORMAL, 8, 3, "pos",
     "Existing Premier customer applying for a World Elite credit card. Salary certificate received.",
     [(True, "Credit card application",
       "I would like to apply for the World Elite credit card. I have banked with you for nine years and my salary is transferred to my account with you. Please let me know what you need from me.\n\nFatima Al Suwaidi", 0),
      (False, "RE: Credit card application",
       "Dear Ms Al Suwaidi,\n\nThank you for your interest. As an existing Premier customer with salary transfer we can process this on a fast track. We require a copy of your Emirates ID and a recent salary certificate.\n\nWe have attached the application form for signature.\n\nRAKBANK Premier Banking", 3)]),

    ("Auto loan application - AED 145,000 over 5 years",
     "Auto Loan", "khalid.alnuaimi@contoso.ae", NORMAL, 11, 3, "pos",
     "New auto finance application for a used vehicle. Awaiting valuation and dealer quotation.",
     [(True, "Car loan enquiry",
       "I am buying a 2022 Toyota Land Cruiser from a dealer in Sharjah for AED 145,000. I would like to finance it over five years. What is the rate and what documents do you need?\n\nKhalid Al Nuaimi", 0),
      (False, "RE: Car loan enquiry",
       "Dear Mr Al Nuaimi,\n\nThank you for your enquiry. Based on your profile we can offer a flat rate from 2.49% per annum over 60 months, subject to credit approval and vehicle valuation.\n\nPlease provide the dealer quotation, your Emirates ID, and three months of salary slips. As the vehicle is pre-owned we will also arrange an independent valuation.\n\nRAKBANK Auto Finance", 6)]),

    ("Mortgage application - villa purchase in Arabian Ranches",
     "Mortgage", "hessa.almuhairi@contoso.ae", NORMAL, 16, 4, "pos",
     "Home finance application for AED 3.2m villa purchase. Pre-approval issued, valuation instructed.",
     [(True, "Home loan application",
       "We have agreed a price of AED 3.2 million on a villa in Arabian Ranches and need a mortgage for AED 2.4 million. We would like to move quickly as the seller has given us six weeks.\n\nHessa Al Muhairi", 0),
      (False, "RE: Home loan application",
       "Dear Ms Al Muhairi,\n\nThank you. We have issued a pre-approval in principle for AED 2.4 million subject to valuation and final credit sign-off, valid for sixty days.\n\nWe have instructed our panel valuer and expect their report within five working days. Your relationship manager will contact you to walk through the offer letter.\n\nRAKBANK Home Finance", 8),
      (True, "RE: RE: Home loan application",
       "That is great news, thank you. When can we expect the valuation to take place?\n\nHessa", 30)]),

    ("Personal loan application - debt consolidation",
     "Personal Loan", "sami.chahine@contoso.ae", NORMAL, 7, 2, "neu",
     "Customer consolidating two existing card balances into a personal loan.",
     [(True, "Personal loan to consolidate my cards",
       "I have balances on two credit cards totalling about AED 68,000 and the interest is crushing me. Can I consolidate this into a personal loan with a lower rate?\n\nSami Chahine", 0),
      (False, "RE: Personal loan to consolidate my cards",
       "Dear Mr Chahine,\n\nYes, consolidation is possible. We will need three months of bank statements and your latest salary certificate to assess affordability, along with settlement letters for the two card balances.\n\nRAKBANK Personal Lending", 5)]),

    ("Credit card limit increase request - AED 30,000 to AED 60,000",
     "Card Limit Increase", "noura.alshamsi@contoso.ae", NORMAL, 5, 2, "pos",
     "Priority customer requesting a limit uplift ahead of travel. Salary increase evidenced.",
     [(True, "Request to increase my card limit",
       "I have recently been promoted and my salary has increased. I am travelling in October and would like my card limit raised from AED 30,000 to AED 60,000. I have attached my new salary certificate.\n\nNoura Al Shamsi", 0),
      (False, "RE: Request to increase my card limit",
       "Dear Ms Al Shamsi,\n\nThank you for the salary certificate. We have submitted the limit increase for credit assessment. Given your excellent repayment history we expect a decision within two working days and will confirm by SMS and email.\n\nRAKBANK Cards", 2)]),

    ("Lost card in Bangkok - urgent replacement and emergency cash",
     "Lost or Stolen Card", "anton.kovacs@contoso.ae", HIGH, 2, 2, "pos",
     "Customer travelling overseas, wallet stolen. Card blocked, emergency replacement requested.",
     [(True, "My wallet was stolen abroad",
       "My wallet was taken from my bag in Bangkok last night. Both my debit and credit cards are gone. Please block them right away and tell me how I can get cash.\n\nAnton Kovacs", 0),
      (False, "RE: My wallet was stolen abroad",
       "Dear Mr Kovacs,\n\nBoth cards are now blocked with immediate effect. No transactions have been attempted since your last confirmed purchase.\n\nWe have arranged emergency cash of USD 1,000 for collection at our partner bank in Bangkok - details will follow by SMS. Replacement cards will be ready for collection at your home branch on your return.\n\nRAKBANK Cards - 24/7 Support", 1)]),

    ("Complaint - branch service quality at Deira branch",
     "Service Quality Complaint", "yousef.alblooshi@contoso.ae", NORMAL, 10, 2, "neg",
     "Customer waited over ninety minutes and was then told the service could not be completed. Requesting acknowledgement and remediation.",
     [(True, "Complaint about service at your branch",
       "I visited the Deira branch on Tuesday to update my Emirates ID. I waited one hour and forty minutes and when my number was finally called I was told the system was down and I would have to come back. Nobody apologised. This is not acceptable.\n\nYousef Al Blooshi", 0),
      (False, "RE: Complaint about service at your branch",
       "Dear Mr Al Blooshi,\n\nI am sorry for the experience you had at our Deira branch. That falls well short of the standard we set, and I have raised this with the Branch Manager directly.\n\nYour complaint is logged under reference CMP-2291. We will complete our review and respond substantively within five working days. In the meantime I would be glad to complete your Emirates ID update remotely so you do not need to travel again.\n\nRAKBANK Customer Care", 4)]),

    ("Regulatory complaint - escalated to Central Bank",
     "Regulatory Complaint", "grace.mensah@contoso.ae", HIGH, 14, 3, "neg",
     "Customer has escalated an unresolved fee complaint to the UAE Central Bank. Regulatory response required within the mandated window.",
     [(True, "I have escalated this to the Central Bank",
       "I have been chasing this for two months with no resolution. I have now filed a complaint with the UAE Central Bank Sanadak unit. I expect a formal written response.\n\nGrace Mensah", 0),
      (False, "RE: I have escalated this to the Central Bank",
       "Dear Ms Mensah,\n\nWe acknowledge receipt of your correspondence and confirm we have been notified of the referral to Sanadak.\n\nYour case has been assigned to our Regulatory Complaints unit under reference REG-0442 and is being handled by a senior case manager. We will provide a full written response within the regulatory timeframe and will copy the outcome to the Central Bank.\n\nRAKBANK Regulatory Complaints", 3)]),

    ("Phishing SMS reported by customer - no loss incurred",
     "Phishing and Scam Report", "priya.nair@contoso.ae", NORMAL, 3, 2, "pos",
     "Customer received a smishing message impersonating the bank. Reported without financial loss. Awareness follow-up required.",
     [(True, "Suspicious message pretending to be you",
       "I got a text saying my account would be suspended unless I verified my details, with a link. I did not click it. The number was a normal mobile number. Thought you should know.\n\nPriya Nair", 0),
      (False, "RE: Suspicious message pretending to be you",
       "Dear Ms Nair,\n\nThank you for reporting this and for not clicking the link - that was exactly the right thing to do. We have passed the number to our fraud intelligence team for takedown action.\n\nAs a reminder, we will never ask you to confirm your PIN, password or full card number by SMS or email.\n\nRAKBANK Fraud and Security", 2)]),

    ("Update registered address and mobile number",
     "Address and Contact Update", "tariq.binsaleh@contoso.ae", LOW, 4, 2, "pos",
     "Customer relocated within the UAE. Address and mobile update with proof of residence.",
     [(True, "Change of address",
       "I have moved from Al Ain to a new address in Dubai. Please update my address and my mobile number. I have attached my new tenancy contract and DEWA bill.\n\nTariq Bin Saleh", 0),
      (False, "RE: Change of address",
       "Dear Mr Bin Saleh,\n\nThank you for the documents. We have verified the tenancy contract and DEWA bill and your address has been updated across all your accounts.\n\nFor the mobile number change we need to complete a short verification call for your security. Please let us know a convenient time.\n\nRAKBANK Customer Service", 2)]),

    ("Request to close current account and transfer balance",
     "Account Closure", "salma.bakr@contoso.ae", NORMAL, 6, 2, "neu",
     "Customer leaving the UAE and requesting account closure, final statement and clearance letter.",
     [(True, "Closing my account",
       "I am relocating back home at the end of the month and need to close my account. Please transfer the remaining balance to my overseas account and issue a clearance letter for my visa cancellation.\n\nSalma Bakr", 0),
      (False, "RE: Closing my account",
       "Dear Ms Bakr,\n\nWe are sorry to see you go. Before we can close the account we need to settle two items: an outstanding credit card balance of AED 430, and one standing instruction which must be cancelled.\n\nOnce those are cleared we will issue your clearance letter and final statement, and remit the balance to your nominated overseas account.\n\nRAKBANK Account Services", 5)]),

    ("Set up standing instruction for monthly rent payment",
     "Cheque Book and Standing Instructions", "vikram.shetty@contoso.ae", LOW, 3, 1, "pos",
     "Customer requesting a recurring monthly transfer to a landlord's account.",
     [(True, "Standing order for my rent",
       "Can you set up a standing instruction to pay AED 9,000 to my landlord on the 1st of every month starting October? I will send the account details separately.\n\nVikram Shetty", 0),
      (False, "RE: Standing order for my rent",
       "Dear Mr Shetty,\n\nCertainly. Please confirm the beneficiary name, IBAN and bank so we can set this up. We will also need confirmation of the end date, or we can set it as open-ended until you instruct otherwise.\n\nRAKBANK Account Services", 3)]),

    ("Dispute of late payment fee and interest charge",
     "Fee Reversal Request", "elena.petrova@contoso.com", NORMAL, 5, 2, "pos",
     "Customer charged a late fee following a direct debit failure caused by a bank-side processing delay.",
     [(True, "Please reverse this late fee",
       "I have been charged AED 250 late fee plus interest on my card. The payment failed because your own direct debit did not run on time - my account had plenty of funds. Please reverse both charges.\n\nElena Petrova", 0),
      (False, "RE: Please reverse this late fee",
       "Dear Ms Petrova,\n\nThank you for raising this. Our initial review confirms the direct debit collection did not run on the scheduled date due to a processing delay at our end.\n\nOn that basis we have reversed the AED 250 late fee and the associated interest charge of AED 62. Both will show on your account within two working days, and no adverse credit marker has been recorded.\n\nRAKBANK Customer Care", 3)]),

    ("Missed instalments on personal loan - repayment plan requested",
     "Arrears and Repayment Plan", "grace.mensah@contoso.ae", HIGH, 12, 3, "neu",
     "Customer two instalments in arrears following redundancy. Requesting restructured repayment plan.",
     [(True, "I need help with my loan repayments",
       "I was made redundant in July and I have missed my last two loan instalments. I have a new role starting in October but I cannot pay the full amount until then. Can we agree a plan? I do not want to default.\n\nGrace Mensah", 0),
      (False, "RE: I need help with my loan repayments",
       "Dear Ms Mensah,\n\nThank you for contacting us early - that makes a real difference to the options available.\n\nWe can look at a short-term payment holiday or a restructured schedule that reduces your instalment until your new salary starts. To assess this we need your termination letter and your new offer letter.\n\nA collections specialist will call you to talk through the options. No further recovery action will be taken while we assess your request.\n\nRAKBANK Collections", 6)]),

    ("Periodic KYC refresh - documents expired",
     "KYC Refresh", "rashid.alhosani@contoso.ae", NORMAL, 20, 2, "neu",
     "Scheduled KYC review. Emirates ID and passport on file have expired; refreshed documents required.",
     [(False, "Action needed - please refresh your documents",
       "Dear Mr Al Hosani,\n\nAs part of our regulatory obligations we periodically refresh the identification we hold on file. Our records show your Emirates ID and passport have now expired.\n\nPlease upload current copies through the app or reply to this email. If we do not receive them within thirty days we may need to restrict activity on the account.\n\nRAKBANK Compliance", 0),
      (True, "RE: Action needed - please refresh your documents",
       "I have renewed both. Attaching copies of my new Emirates ID and passport now.\n\nRashid Al Hosani", 48)]),

    ("New account opening - salary transfer package",
     "New Account Opening", "grace.mensah@contoso.ae", NORMAL, 1, 1, "pos",
     "New-to-bank customer opening a current account with salary transfer.",
     [(True, "I would like to open an account",
       "I am starting a new job in Dubai in October and my employer needs a bank account for salary transfer. What do I need to open one?\n\nGrace Mensah", 0),
      (False, "RE: I would like to open an account",
       "Dear Ms Mensah,\n\nWelcome. To open a current account with salary transfer we need your Emirates ID, passport with residence visa, and your employer's salary transfer letter.\n\nYou can start the application in the app and we will complete verification digitally - most accounts are open within one working day.\n\nRAKBANK Onboarding", 2)]),
]


def lookup(entity, key, cols, filt=None, top=500):
    q = f"{entity}?$select={cols}&$top={top}"
    if filt:
        q += "&$filter=" + filt
    return {r[key]: r for r in dv.get(q)["value"]}


def open_tasks(case_id):
    return dv.get(f"tasks?$select=activityid,subject,{P}_availableoutcomes,{P}_sequence"
                  f"&$filter=_regardingobjectid_value eq {case_id} and statecode eq 0"
                  f"&$orderby={P}_sequence")["value"]


def pick(outcomes, prefer, seen):
    """Choose an outcome, steering toward the branch the scenario calls for.

    An empty nextTask ends the process, and some negative outcomes deliberately
    loop back to an earlier task. Both are skipped so the demo cases finish
    mid-flight with an open task and a live SLA rather than closed or circling.
    """
    pool = [o for o in outcomes
            if o.get("nextTask") and o["nextTask"] not in seen] or outcomes
    want = {"pos": 1, "neu": 2, "neg": 3}.get(prefer, 2)
    for o in pool:
        if o.get("sentiment") == want:
            return o
    for o in pool:
        if o.get("isDefault"):
            return o
    return pool[0] if pool else None


def walk(case_id, steps, prefer, log):
    """Complete `steps` tasks the way an agent would, recording a real outcome."""
    seen = set()
    for _ in range(steps):
        tasks = open_tasks(case_id)
        if not tasks:
            return
        t = tasks[0]
        seen.add(t["subject"])
        try:
            outs = json.loads(t.get(f"{P}_availableoutcomes") or "[]")
        except ValueError:
            outs = []
        o = pick(outs, prefer, seen)
        if not o:
            return
        dv.patch(f"tasks({t['activityid']})", {
            f"{P}_outcomelabel": o["label"], "statecode": 1, "statuscode": 5,
            f"{P}_outcomecomment": "Handled and evidenced during the customer conversation.",
        })
        log.append(f"{t['subject']} -> {o['label']}")
        time.sleep(1.2)


def email_html(case_id, contact_id, agent_id, incoming, subject, html, when):
    """Create one email activity with already-rendered HTML body."""
    e = dv.post("emails", {
        "subject": subject,
        "description": html,
        "directioncode": not incoming,
        "regardingobjectid_incident@odata.bind": f"/incidents({case_id})",
        "actualend": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "email_activity_parties": [
            {("partyid_contact@odata.bind" if incoming else "partyid_systemuser@odata.bind"):
             (f"/contacts({contact_id})" if incoming else f"/systemusers({agent_id})"),
             "participationtypemask": 1},
            {("partyid_systemuser@odata.bind" if incoming else "partyid_contact@odata.bind"):
             (f"/systemusers({agent_id})" if incoming else f"/contacts({contact_id})"),
             "participationtypemask": 2},
        ],
    })
    eid = dv.new_id(e)
    # 3 = sent, 4 = received; both land the activity closed on the timeline.
    dv.patch(f"emails({eid})", {"statecode": 1, "statuscode": 4 if incoming else 3})
    return eid


def email(case_id, contact_id, agent_id, incoming, subject, body, when):
    return email_html(case_id, contact_id, agent_id, incoming, subject,
                      body.replace("\n", "<br/>"), when)


def main():
    contacts = {(c.get("emailaddress1") or "").lower(): c["contactid"]
                for c in dv.get("contacts?$select=contactid,emailaddress1&$top=500")["value"]}
    subjects = {s["title"]: s["subjectid"]
                for s in dv.get("subjects?$select=subjectid,title&$top=300")["value"]}
    agent = dv.get("systemusers?$select=systemuserid&$filter=domainname ne null and "
                   "isdisabled eq false&$top=1")["value"][0]["systemuserid"]

    existing = {c["title"] for c in
                dv.get("incidents?$select=title&$top=500")["value"]}

    now = dt.datetime.utcnow()
    made = 0
    for (title, subj, cemail, prio, days, steps, prefer, desc, thread) in CASES:
        if title in existing:
            print(f"  = exists: {title[:60]}")
            continue
        cid = contacts.get(cemail.lower())
        sid = subjects.get(subj)
        if not cid or not sid:
            print(f"  ! skip (contact={bool(cid)} subject={bool(sid)}): {title[:50]}")
            continue
        opened = now - dt.timedelta(days=days)
        case = dv.new_id(dv.post("incidents", {
            "title": title,
            "description": desc,
            "customerid_contact@odata.bind": f"/contacts({cid})",
            "subjectid@odata.bind": f"/subjects({sid})",
            "prioritycode": prio,
            "caseorigincode": EMAIL_ORIGIN,
            "casetypecode": 3,
        }))
        time.sleep(2.5)  # let ApplyCaseProcess land the template and spawn task one

        for incoming, esub, ebody, hrs in thread:
            email(case, cid, agent, incoming, esub, ebody, opened + dt.timedelta(hours=hrs))

        log = []
        walk(case, steps, prefer, log)

        applied = dv.get(f"incidents({case})?$select=_{P}_appliedtemplate_value")
        tpl = applied.get(f"_{P}_appliedtemplate_value")
        tname = "(none)"
        if tpl:
            tname = dv.get(f"{P}_caseprocesstemplates({tpl})?$select={P}_name")[f"{P}_name"]
        print(f"  + {title[:52]:<52} [{tname[:34]}]")
        for line in log:
            print(f"        done: {line}")
        made += 1

    print(f"\n{made} case(s) created.")


if __name__ == "__main__":
    print("Retail cases")
    main()

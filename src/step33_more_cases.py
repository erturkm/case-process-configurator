"""Seed twenty further retail banking cases for the RAKBANK demo.

Extends the original set with a second wave weighted toward the scenarios most
likely to be demonstrated live: account opening, transaction disputes and credit
card limit increases, plus supporting volume across cards, payments, lending and
servicing so queue and dashboard counts look like a real working day.

Threads are authored directly as paragraph lists and rendered through emailfmt,
so every message carries a named advisor, a commitment and the case reference.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step33_more_cases.py
"""
import datetime as dt
import time

import dv
import emailfmt
import step30_retail_cases as base

P = dv.PREFIX
LOW, NORMAL, HIGH = 3, 2, 1
EMAIL_ORIGIN = 1

# title, subject, customer email, priority, days ago, tasks to walk, branch bias,
# advisor, description, next-step commitment, thread
CASES = [
    # ---------------------------------------------------------------- account opening
    ("New account opening - expatriate professional relocating to Dubai",
     "New Account Opening", "priya.nair@contoso.ae", NORMAL, 2, 2, "pos", "onboarding",
     "New-to-bank applicant relocating from Bangalore. Residence visa issued, employment starts 15 September.",
     "We will verify your documents digitally and confirm your account number and IBAN within "
     "<b>one working day</b> of receiving them. Your debit card follows by courier within three days.",
     [(True, "Opening an account before I relocate",
       ["I am relocating to Dubai on 12 September to join a technology company in Internet City, and my employer needs an account number for salary transfer before my first payroll run on the 25th.",
        "My residence visa was stamped last week. Is it possible to start the process now so the account is ready when I land?"]),
      (False, "RE: Opening an account before I relocate",
       ["Dear Ms Nair,",
        "Thank you for choosing RAKBANK, and congratulations on the move.",
        "Yes, we can begin now. Please upload your passport with the residence visa page, your Emirates ID application receipt, and your employment offer letter through the link below. We can open the account on the visa receipt and update it once the Emirates ID card is issued.",
        "Your employer can be given the IBAN as soon as the account is opened, so your September payroll will not be affected."])]),

    ("New account opening - salary transfer account for new joiner",
     "New Account Opening", "daniel.okafor@contoso.ae", NORMAL, 4, 3, "pos", "onboarding",
     "Salary transfer account requested by employer HR on behalf of a new joiner. Corporate payroll agreement in place.",
     "Your account is open and the IBAN has been sent to your HR team. Your debit card and cheque book "
     "will reach your registered address within <b>three working days</b>.",
     [(True, "Salary account - new joiner at Emirates Steel",
       ["My HR department has asked me to open a salary transfer account with you as my employer has a payroll arrangement in place.",
        "I have attached my Emirates ID, passport copy and the salary transfer letter from HR. Please let me know if anything else is needed."]),
      (False, "RE: Salary account - new joiner at Emirates Steel",
       ["Dear Mr Okafor,",
        "Thank you for the documents. Your employer is on our corporate payroll panel, which means we can open your account on a fast track and waive the minimum balance requirement while your salary is credited to us.",
        "Your account has been opened and the IBAN has been shared directly with your HR team so your first salary lands without delay."])]),

    ("New account opening - joint savings account for married couple",
     "New Account Opening", "salma.bakr@contoso.ae", LOW, 6, 2, "neu", "onboarding",
     "Joint savings account application. Second applicant documents outstanding.",
     "We need your husband's Emirates ID and a signed second-applicant mandate. Once received we will "
     "open the joint account within <b>two working days</b>.",
     [(True, "Joint savings account",
       ["My husband and I would like to open a joint savings account to save for a property deposit. We both already hold individual current accounts with you.",
        "What is the process, and do we both need to visit a branch?"]),
      (False, "RE: Joint savings account",
       ["Dear Ms Bakr,",
        "Thank you for your enquiry. As you are both existing customers there is no need to visit a branch; the account can be opened digitally.",
        "We hold current identification for you, but our records show your husband's Emirates ID expired in June. We will need a renewed copy along with a signed joint mandate confirming the operating instructions, which we have attached."])]),

    ("New account opening - SME business current account",
     "New Account Opening", "vikram.shetty@contoso.ae", NORMAL, 8, 3, "neu", "onboarding",
     "SME business current account for a newly licensed trading company. Enhanced due diligence required on ownership structure.",
     "Our business banking team will complete due diligence on the ownership structure and come back to "
     "you within <b>five working days</b>. A relationship manager will call you to arrange the signatory visit.",
     [(True, "Business account for my new trading company",
       ["I have just received the trade licence for my import and distribution company in Jebel Ali Free Zone and need a business current account to begin trading.",
        "I have attached the trade licence, memorandum of association and my Emirates ID. The company has two shareholders, myself and a partner based in Singapore."]),
      (False, "RE: Business account for my new trading company",
       ["Dear Mr Shetty,",
        "Thank you for the documents and congratulations on the new licence.",
        "Because one shareholder is resident overseas we are required to complete enhanced due diligence on the ownership structure before the account can be opened. We will need your partner's passport copy, proof of address, and a completed ultimate beneficial ownership declaration.",
        "This is a standard requirement under UAE Central Bank rules and does not indicate any concern with your application."])]),

    # ---------------------------------------------------------- transaction disputes
    ("Disputed subscription charges - merchant continued billing after cancellation",
     "Card Disputes", "grace.mensah@contoso.ae", NORMAL, 5, 3, "pos", "disputes",
     "Recurring merchant billing continued for three months after the customer cancelled. Cancellation confirmation supplied.",
     "We have raised a chargeback for all three charges totalling AED 897 and applied a provisional credit "
     "today. A block is now in place to stop further billing. We will confirm the final outcome by "
     "<b>25 September</b>.",
     [(True, "Being charged for a subscription I cancelled",
       ["I cancelled a streaming subscription in June and received an email confirming the cancellation, but I have been charged AED 299 in July, August and September.",
        "I have contacted the merchant twice with no response. I have attached the cancellation confirmation email. Please stop these charges and refund the three payments."]),
      (False, "RE: Being charged for a subscription I cancelled",
       ["Dear Ms Mensah,",
        "Thank you for sending the cancellation confirmation, which gives us clear grounds to dispute the charges.",
        "We have raised a chargeback for all three transactions totalling AED 897 and credited the amount to your account today while the merchant's bank responds.",
        "We have also placed a merchant block so no further charges from this retailer can be processed against your card."])]),

    ("Disputed ATM withdrawal - cash not dispensed",
     "Card Disputes", "yousef.alblooshi@contoso.ae", HIGH, 3, 3, "pos", "disputes",
     "ATM debited AED 3,000 without dispensing cash. Third-party ATM, journal retrieval required.",
     "We have credited the AED 3,000 to your account today. We are retrieving the ATM journal and cash "
     "balancing report from the operating bank and will confirm the final position within "
     "<b>ten working days</b> as required under the domestic scheme rules.",
     [(True, "ATM took my money but gave no cash",
       ["I tried to withdraw AED 3,000 from an ATM at Mirdif City Centre yesterday evening. The machine made the counting noise then displayed an error and returned my card without any cash.",
        "My account has been debited the full amount. I waited fifteen minutes and no cash came out. There was no receipt either."]),
      (False, "RE: ATM took my money but gave no cash",
       ["Dear Mr Al Blooshi,",
        "I am sorry this happened. Failed dispense claims are one of the more common ATM faults and are usually resolved in the customer's favour.",
        "We have applied a credit of AED 3,000 to your account today so you are not left out of pocket while we investigate.",
        "As the machine belongs to another bank we are requesting their electronic journal and end-of-day cash balancing report, which will show whether the cash was actually dispensed."])]),

    ("Duplicate charge at restaurant - card charged twice for one bill",
     "Card Disputes", "sami.chahine@contoso.ae", NORMAL, 2, 2, "pos", "disputes",
     "Merchant processed the same transaction twice on the same evening. Customer holds a single receipt.",
     "We have credited the duplicate AED 640 and raised the dispute with the merchant's bank. Duplicate "
     "processing claims are typically resolved within <b>fifteen working days</b>.",
     [(True, "Charged twice at the same restaurant",
       ["I paid a restaurant bill of AED 640 on Saturday evening and the amount has come out of my account twice, two minutes apart.",
        "I only signed one receipt, which I have attached. The waiter did say the first attempt had failed."]),
      (False, "RE: Charged twice at the same restaurant",
       ["Dear Mr Chahine,",
        "Thank you for the receipt. What you describe is a classic duplicate processing error, where a terminal times out and the transaction is entered a second time even though the first has already been authorised.",
        "We have refunded the duplicate AED 640 to your account today and raised the claim with the merchant's acquiring bank."])]),

    ("Disputed hotel charge - amount higher than the rate confirmed at booking",
     "Card Disputes", "anton.kovacs@contoso.ae", NORMAL, 7, 2, "neu", "disputes",
     "Hotel charged materially above the confirmed booking rate. Booking confirmation provided; merchant response awaited.",
     "We have raised the dispute for the AED 1,850 difference and requested the merchant's supporting "
     "documentation. They have <b>thirty days</b> to respond and we will write to you as soon as they do.",
     [(True, "Hotel charged more than the confirmed rate",
       ["I stayed at a hotel in Fujairah last month with a booking confirmation for AED 2,400 for three nights, but I have been charged AED 4,250.",
        "The hotel says the difference is for extras I did not use. I have attached the booking confirmation and my final invoice, which do not match."]),
      (False, "RE: Hotel charged more than the confirmed rate",
       ["Dear Mr Kovacs,",
        "Thank you for the booking confirmation and the invoice. The discrepancy of AED 1,850 is clear from the documents you have sent.",
        "We have raised a dispute for the difference rather than the full amount, as the underlying stay is not in question. This is the appropriate route where a merchant has charged above an agreed rate.",
        "Please keep any correspondence with the hotel, as it may support the claim if they contest it."])]),

    # ------------------------------------------------------ credit card limit increase
    ("Credit card limit increase - AED 50,000 to AED 100,000 for business travel",
     "Card Limit Increase", "hessa.almuhairi@contoso.ae", NORMAL, 3, 3, "pos", "premier",
     "Premier customer requesting a limit uplift to support frequent corporate travel. Strong repayment history.",
     "Your request is with credit assessment. Given your Premier standing and unblemished repayment "
     "record we expect to confirm by SMS and email within <b>two working days</b>.",
     [(True, "Increase to my card limit for travel",
       ["My role now involves regular travel across the region and I am routinely booking flights and hotels for my team, which is pushing me close to my AED 50,000 limit each month.",
        "I would like to request an increase to AED 100,000. My salary is credited to my account with you and I settle the balance in full every month."]),
      (False, "RE: Increase to my card limit for travel",
       ["Dear Ms Al Muhairi,",
        "Thank you for getting in touch. Your account history supports this request; you have settled in full every month for the past four years and your salary continues to be credited to us.",
        "As we hold your salary records we do not need any further documentation from you. The request has gone straight to credit assessment."])]),

    ("Credit card limit increase declined - customer requesting review",
     "Card Limit Increase", "imran.qureshi@contoso.ae", NORMAL, 9, 3, "neg", "cards",
     "Automated limit increase declined on debt burden ratio. Customer disputing the decision and requesting manual review.",
     "A credit officer will manually review your file against the updated salary certificate and we will "
     "write to you with a final decision within <b>five working days</b>.",
     [(True, "Why was my limit increase refused?",
       ["I applied for an increase from AED 20,000 to AED 35,000 through the app and it was declined immediately with no explanation.",
        "I have never missed a payment in six years and my salary went up in July. I would like to understand the reason and have the decision reviewed."]),
      (False, "RE: Why was my limit increase refused?",
       ["Dear Mr Qureshi,",
        "Thank you for asking, and I am sorry the automated decline came without an explanation.",
        "The application was assessed against your debt burden ratio, which combines all your credit commitments across the banking system. Our records still held your previous salary, which put the calculation above the Central Bank threshold of 50%.",
        "As your salary has since increased, please send us your latest salary certificate and we will have a credit officer review the file manually rather than relying on the automated assessment."])]),

    ("Credit card limit decrease requested by customer",
     "Card Limit Increase", "tariq.binsaleh@contoso.ae", LOW, 4, 2, "pos", "cards",
     "Customer voluntarily requesting a lower limit to support personal budgeting. No adverse indicators.",
     "Your limit has been reduced to AED 15,000 with immediate effect. This is recorded as a customer "
     "request and will not affect your credit standing. You can ask us to restore it at any time.",
     [(True, "Please reduce my credit limit",
       ["I would like to reduce my credit card limit from AED 40,000 to AED 15,000. I am trying to manage my spending more carefully and a lower limit will help.",
        "Please confirm this will not be recorded as a problem on my credit file."]),
      (False, "RE: Please reduce my credit limit",
       ["Dear Mr Bin Saleh,",
        "Thank you for contacting us, and I am happy to confirm your limit has been reduced to AED 15,000 with immediate effect.",
        "To reassure you: a reduction made at the customer's own request is recorded as exactly that. It carries no negative implication on your credit file and is quite different from a limit cut imposed by a lender.",
        "If your circumstances change you can ask us to restore the previous limit and we will assess it in the normal way."])]),

    ("Temporary credit limit increase for medical expenses",
     "Card Limit Increase", "maryam.alzaabi@contoso.ae", HIGH, 1, 2, "pos", "cards",
     "Urgent temporary limit uplift requested to cover a hospital admission deposit. Time-critical.",
     "We have applied a temporary limit of AED 45,000 with immediate effect, valid for ninety days. Your "
     "card is ready to use now and the limit reverts automatically on <b>3 December</b>.",
     [(True, "Urgent - need a higher limit for hospital admission",
       ["My father has been admitted to hospital and they require a deposit of AED 35,000 before proceeding with surgery tomorrow morning.",
        "My current limit is AED 25,000. Is there any way to increase it today? I can settle the balance when my end-of-service payment clears next month."]),
      (False, "RE: Urgent - need a higher limit for hospital admission",
       ["Dear Ms Al Zaabi,",
        "I am sorry to hear about your father, and I hope the surgery goes well.",
        "I have applied a temporary limit of AED 45,000 to your card with immediate effect. You can use it straight away for the hospital deposit.",
        "The temporary limit runs for ninety days and then reverts to AED 25,000 automatically. If you would like to discuss a permanent increase or a payment plan once things have settled, please call me directly."])]),

    # ---------------------------------------------------------------- payments, cards
    ("Salary not credited - employer transfer not received",
     "Salary Transfer and Payroll", "grace.mensah@contoso.ae", HIGH, 2, 2, "neu", "payments",
     "Customer reports salary missing on the expected date. Investigation with the employer's remitting bank.",
     "We are tracing the payment with your employer's bank and will update you within "
     "<b>one working day</b>. We have waived the charges that were applied when the direct debits failed.",
     [(True, "My salary has not arrived",
       ["My salary is normally credited on the 28th and it is now the 2nd with nothing showing in my account. My employer says the transfer was released on the 27th through their bank.",
        "Two of my direct debits have already bounced and I have been charged for both. Please help urgently."]),
      (False, "RE: My salary has not arrived",
       ["Dear Ms Mensah,",
        "Thank you for letting us know, and I am sorry for the difficulty this has caused.",
        "I have checked our incoming payment records and no credit has been received against your account. We are raising a trace with your employer's remitting bank to establish where the funds are held.",
        "I have reversed both returned direct debit charges and instructed that no further fees be applied to your account until this is resolved."])]),

    ("Cheque returned unpaid - insufficient funds dispute",
     "Domestic Transfer", "khalid.alnuaimi@contoso.ae", HIGH, 6, 2, "neg", "payments",
     "Cheque returned unpaid despite the customer asserting sufficient cleared balance. Value-dating under review.",
     "We are reviewing the value-dating of the credit against the cheque presentation time and will come "
     "back to you within <b>two working days</b>. If the cheque was returned in error we will issue a "
     "correction letter to the beneficiary.",
     [(True, "My cheque was returned and it should not have been",
       ["A cheque I issued for AED 18,000 was returned unpaid yesterday marked insufficient funds. My account had AED 24,000 in it at the time.",
        "This is extremely damaging as the cheque was to my landlord. I need this corrected urgently and a letter confirming the error."]),
      (False, "RE: My cheque was returned and it should not have been",
       ["Dear Mr Al Nuaimi,",
        "Thank you for raising this, and I understand how serious a returned cheque is.",
        "I have reviewed the account. A credit of AED 22,000 was received on the same day but was value-dated to the following working day, which meant the cleared balance at the point the cheque was presented was below the cheque amount.",
        "I am having the value-dating reviewed to establish whether it was applied correctly. If the credit should have been available same-day, we will treat the return as our error and issue a correction letter to your landlord confirming the fault was ours."])]),

    ("Card declined abroad despite travel notification",
     "Card Delivery and PIN", "layla.mansour@contoso.ae", NORMAL, 3, 2, "pos", "cards",
     "Card blocked by fraud rules while the customer was overseas despite a registered travel notification.",
     "The block has been lifted and a travel exemption applied to your card until the end of your trip. "
     "We have credited AED 200 to cover the costs you incurred.",
     [(True, "My card was blocked even though I told you I was travelling",
       ["I registered my travel dates through the app before flying to Georgia, but my card was declined three times at a restaurant in Tbilisi and I was left unable to pay.",
        "It was embarrassing and I had to borrow cash from a colleague. Why did the travel notification not work?"]),
      (False, "RE: My card was blocked even though I told you I was travelling",
       ["Dear Ms Mansour,",
        "I am sorry, this should not have happened and I understand how uncomfortable that situation must have been.",
        "Your travel notification was correctly registered. The block was applied by a separate fraud rule triggered by a merchant category that had shown unusual activity that week, which unfortunately overrode the travel flag.",
        "I have removed the block, applied a specific exemption to your card for the remainder of your trip, and credited AED 200 to your account as an apology for the inconvenience and the cash you had to borrow."])]),

    ("Standing instruction failed - beneficiary account closed",
     "Cheque Book and Standing Instructions", "omar.haddad@contoso.ae", NORMAL, 5, 2, "neu", "servicing",
     "Recurring standing instruction failing because the beneficiary account has been closed. New details required.",
     "The instruction is suspended so no further attempts or charges are made. Send us the new IBAN and we "
     "will update it and process the missed payment within <b>one working day</b>.",
     [(True, "My monthly transfer keeps failing",
       ["My standing instruction to my son's account has failed twice this month and I have been charged a fee each time.",
        "He tells me he closed that account and opened a new one at a different bank. How do I update the details?"]),
      (False, "RE: My monthly transfer keeps failing",
       ["Dear Mr Haddad,",
        "Thank you for confirming, that explains the failures. When a beneficiary account is closed the receiving bank rejects the credit and it returns to us.",
        "I have suspended the instruction so no further attempts are made and no further charges are incurred, and I have reversed both fees already applied.",
        "Once you send your son's new IBAN and bank name we will update the instruction and release this month's payment straight away."])]),

    # ------------------------------------------------------------- lending, servicing
    ("Loan settlement quote requested for early payoff",
     "Loan Settlement and Early Payoff", "noura.alshamsi@contoso.ae", NORMAL, 4, 2, "pos", "lending",
     "Customer requesting a formal early settlement figure for a personal loan.",
     "Your formal settlement letter is attached and the figure is valid until <b>18 September</b>. Once "
     "payment is received we will issue your clearance letter and update the Al Etihad Credit Bureau "
     "within five working days.",
     [(True, "Early settlement figure for my personal loan",
       ["I have received a bonus and would like to settle my personal loan in full before the end of the month.",
        "Please send me a formal settlement quotation showing the outstanding principal and any early settlement charge, and confirm how long the figure is valid."]),
      (False, "RE: Early settlement figure for my personal loan",
       ["Dear Ms Al Shamsi,",
        "Thank you for your request. I have attached your formal settlement quotation.",
        "The outstanding principal is AED 84,320 and the early settlement fee is AED 843, being 1% of the outstanding balance and capped in line with UAE Central Bank regulations. The total settlement figure is AED 85,163.",
        "Settling early will save you AED 6,180 in interest over the remaining term."])]),

    ("Mortgage rate switch enquiry - variable to fixed",
     "Mortgage", "fatima.alsuwaidi@contoso.ae", NORMAL, 10, 3, "neu", "mortgage",
     "Existing mortgage customer enquiring about switching from a variable to a fixed rate.",
     "Our home finance team will prepare a formal switch illustration showing both options over the "
     "remaining term and send it to you within <b>three working days</b>.",
     [(True, "Switching my mortgage to a fixed rate",
       ["My mortgage is on a variable rate and my instalment has risen twice this year. I would like to understand what a fixed rate would cost.",
        "I have about eighteen years remaining and an outstanding balance of roughly AED 1.8 million. Is there a fee to switch?"]),
      (False, "RE: Switching my mortgage to a fixed rate",
       ["Dear Ms Al Suwaidi,",
        "Thank you for getting in touch, and this is a sensible question to ask given recent rate movements.",
        "We can offer a three-year fixed rate and a five-year fixed rate. Switching from variable to fixed within the same facility attracts a processing fee of AED 1,500 rather than the early settlement charge that would apply if you refinanced elsewhere.",
        "I am preparing an illustration showing your projected instalment under each option against the variable rate, so you can see the cost of certainty before deciding."])]),

    ("Complaint - repeated calls after account was settled",
     "Service Quality Complaint", "rashid.alhosani@contoso.ae", HIGH, 8, 3, "neg", "complaints",
     "Customer continued to receive collections contact after the account was settled in full. Service failure and data handling concern.",
     "All contact has been stopped and your settlement is confirmed on our records. I will complete my "
     "investigation and write to you with a full response and our findings within "
     "<b>five working days</b>.",
     [(True, "Stop calling me - I settled this account",
       ["I settled my card balance in full on 20 August and have the confirmation. Since then I have received eleven calls from your collections department demanding payment, including two before 8am.",
        "I have explained the situation each time. This is harassment and I want it stopped and investigated."]),
      (False, "RE: Stop calling me - I settled this account",
       ["Dear Mr Al Hosani,",
        "I am sorry. You settled your account and should not have received a single one of those calls, let alone eleven.",
        "I have confirmed the settlement was received and correctly applied on 20 August, and I have placed an immediate suppression on all outbound contact for your account.",
        "The calls continued because the settlement posted to a closed sub-account that did not update the collections queue. That is a failure in our process, not something you caused, and I am escalating it so it cannot recur.",
        "I am also reviewing the two calls made before 8am, which fall outside the permitted contact hours."])]),

    ("Statement request - two years of statements for visa application",
     "Statements", "elena.petrova@contoso.com", LOW, 3, 2, "pos", "servicing",
     "Customer requesting stamped historic statements and a balance certificate for a residency application.",
     "Your stamped statements and balance certificate will be ready for collection at your branch within "
     "<b>two working days</b>, or we can courier them to your registered address at no charge.",
     [(True, "Stamped statements for a visa application",
       ["I need bank statements covering the last twenty four months for a residency application, and the consulate requires them stamped and signed by the bank.",
        "I also need a balance certificate showing my current balance. How quickly can these be prepared?"]),
      (False, "RE: Stamped statements for a visa application",
       ["Dear Ms Petrova,",
        "Thank you for your request. Consulates are particular about this, so I want to make sure we get the format right first time.",
        "We will prepare twenty four months of statements to 31 August, stamped and signed on bank letterhead, together with a balance certificate confirming your current balance and the date the account was opened.",
        "If the consulate has specified a particular wording or requires the certificate addressed to a named authority, let me know and we will match it exactly."])]),
]


def main():
    contacts = {(c.get("emailaddress1") or "").lower(): c["contactid"]
                for c in dv.get("contacts?$select=contactid,emailaddress1&$top=500")["value"]}
    subjects = {s["title"]: s["subjectid"]
                for s in dv.get("subjects?$select=subjectid,title&$top=300")["value"]}
    agent = dv.get("systemusers?$select=systemuserid&$filter=domainname ne null and "
                   "isdisabled eq false&$top=1")["value"][0]["systemuserid"]
    existing = {c["title"] for c in dv.get("incidents?$select=title&$top=800")["value"]}

    now = dt.datetime.now(dt.timezone.utc)
    made = 0
    for (title, subj, cemail, prio, days, steps, prefer, advisor, desc, nxt, thread) in CASES:
        if title in existing:
            print(f"  = exists: {title[:62]}")
            continue
        cid = contacts.get(cemail.lower())
        sid = subjects.get(subj)
        if not cid or not sid:
            print(f"  ! skip (contact={bool(cid)} subject={bool(sid)}): {title[:50]}")
            continue

        opened = now - dt.timedelta(days=days)
        case_id = dv.new_id(dv.post("incidents", {
            "title": title,
            "description": desc,
            "customerid_contact@odata.bind": f"/contacts({cid})",
            "subjectid@odata.bind": f"/subjects({sid})",
            "prioritycode": prio,
            "caseorigincode": EMAIL_ORIGIN,
            "casetypecode": 3,
        }))
        time.sleep(2.5)  # let ApplyCaseProcess match a template and spawn task one

        ref = dv.get(f"incidents({case_id})?$select=ticketnumber")["ticketnumber"]
        contact = dv.get(f"contacts({cid})?$select=fullname,mobilephone")
        hours = 0
        for incoming, esub, paras in thread:
            if incoming:
                html = emailfmt.customer(paras, contact.get("fullname", ""),
                                         contact.get("mobilephone"),
                                         sent_from_phone=len(paras) == 1)
            else:
                html = emailfmt.bank(paras[0], paras[1:], advisor, ref, nxt)
            base.email_html(case_id, cid, agent, incoming, esub, html,
                            opened + dt.timedelta(hours=hours))
            hours += 3

        log = []
        base.walk(case_id, steps, prefer, log)

        applied = dv.get(f"incidents({case_id})?$select=_{P}_appliedtemplate_value")
        tpl = applied.get(f"_{P}_appliedtemplate_value")
        tname = dv.get(f"{P}_caseprocesstemplates({tpl})?$select={P}_name")[f"{P}_name"] \
            if tpl else "** NONE **"
        print(f"  + {title[:56]:<56} [{tname[:32]}]")
        for line in log:
            print(f"        done: {line}")
        made += 1

    print(f"\n{made} case(s) created.")


if __name__ == "__main__":
    print("Retail cases - second wave")
    main()

"""Place customer email into the RAKBANK care mailbox so it looks genuinely inbound.

Sending real mail from customer addresses is not an option - contoso.ae is not a
domain we own, so anything sent from it would be rejected or land in junk. Graph
sidesteps that entirely: creating a message directly inside a mail folder lets the
sender and the received timestamp be set to whatever the scenario calls for, and
Outlook renders it exactly like any other message.

Server-side sync then picks it up on its normal polling cycle, the
CreateCaseFromEmail plugin opens a case, TriageInboundCase derives the subject and
ApplyCaseProcess stamps the template, SLA, tasks and documents.

    python3 step39_inject_email.py            # queue every scenario not yet sent
    python3 step39_inject_email.py --one       # just the next unsent one, for a live demo
    python3 step39_inject_email.py --list      # show what is available
"""
import argparse
import datetime as dt
import sys

import emailfmt
import gr

MAILBOX = "customerservice@D365DemoTSCE13436844.onmicrosoft.com"

# (sender name, sender address, mobile, subject, [paragraphs], minutes_ago)
SCENARIOS = [
    ("Aisha Al Marzouqi", "aisha.almarzouqi@contoso.ae", "+971501112201",
     "Unauthorised transactions on my debit card", [
         "I checked my account this morning and found three transactions I did not authorise, "
         "totalling AED 8,450. They were all made yesterday evening at merchants I have never "
         "heard of.",
         "I still have my card with me, so I do not understand how this happened. I did not "
         "share my PIN or any codes with anyone.",
         "Please block the card immediately and refund these transactions. This is urgent as "
         "my salary is in that account.",
     ], 12),

    ("Grace Mensah", "grace.mensah@contoso.ae", "+971501112216",
     "Request to open a current account", [
         "I am relocating to Dubai next month to take up a position with a logistics company in "
         "Jebel Ali, and my employer requires a salary transfer account before my start date.",
         "I would like to open a current account with RAKBANK. I hold a UK passport and my "
         "residence visa is currently being processed.",
         "Could you let me know which documents you need from me and how long the process "
         "usually takes?",
     ], 34),

    ("Daniel Okafor", "daniel.okafor@contoso.ae", "+971501112213",
     "Charged twice for the same restaurant bill", [
         "I paid for dinner at a restaurant in Dubai Marina on Tuesday evening and the amount of "
         "AED 640 has been charged twice to my credit card.",
         "The restaurant confirmed they only processed one payment and suggested I raise a "
         "dispute with the bank. I have the receipt showing a single transaction.",
         "Please reverse the duplicate charge and confirm once this has been done.",
     ], 57),

    ("Vikram Shetty", "vikram.shetty@contoso.ae", "+971501112219",
     "Credit card limit increase request", [
         "I have held a credit card with RAKBANK for four years and have never missed a payment. "
         "My current limit is AED 45,000.",
         "I have recently been promoted and my monthly salary has increased to AED 38,000. I "
         "would like to request a limit increase to AED 90,000.",
         "I can provide an updated salary certificate and my most recent payslips. Please let me "
         "know what else is required.",
     ], 88),

    ("Noura Al Shamsi", "noura.alshamsi@contoso.ae", "+971501112208",
     "Locked out of online banking", [
         "I have been trying to log in to online banking since yesterday and the system tells me "
         "my account is locked after too many attempts.",
         "I am certain the password is correct. I need access urgently because I have a supplier "
         "payment due tomorrow morning.",
         "Please reset my access as soon as possible.",
     ], 121),

    ("Imran Qureshi", "imran.qureshi@contoso.ae", "+971501112211",
     "Salary has not been credited this month", [
         "My employer processed payroll on the 28th and has sent me the WPS confirmation, but "
         "nothing has been credited to my account.",
         "It is now the 3rd and my standing instructions for rent and school fees are due to run "
         "this week. If they fail I will be charged penalties by both providers.",
         "Please trace the payment and let me know where the funds are being held.",
     ], 165),

    ("Hessa Al Muhairi", "hessa.almuhairi@contoso.ae", "+971501112214",
     "Bank statements required for visa application", [
         "I am applying for a residence visa for my mother and the immigration office has asked "
         "for stamped bank statements covering the last two years.",
         "Could you please issue these for my current account? They must carry the bank stamp and "
         "signature to be accepted.",
         "I would be grateful if this could be arranged this week as the application deadline is "
         "approaching.",
     ], 210),

    ("Anton Kovacs", "anton.kovacs@contoso.ae", "+971501112217",
     "Card declined while travelling despite travel notification", [
         "I notified the bank through the mobile app before travelling to Germany last week, but "
         "my card was declined three times, including at my hotel when I tried to check out.",
         "I had to borrow money from a colleague to settle the bill, which was extremely "
         "embarrassing.",
         "Please explain why the travel notification was not applied and make sure my card works "
         "for the rest of my trip.",
     ], 260),

    ("Salma Bakr", "salma.bakr@contoso.ae", "+971501112218",
     "Suspicious message asking me to confirm my card details", [
         "I received an SMS this morning claiming to be from RAKBANK, saying my account would be "
         "suspended unless I confirmed my card details through a link.",
         "The link looked wrong so I did not click it, but I wanted to report it in case other "
         "customers receive the same message.",
         "Could you confirm whether this was genuine and what I should do if I receive more of "
         "these?",
     ], 305),

    ("Tariq Bin Saleh", "tariq.binsaleh@contoso.ae", "+971501112215",
     "Early settlement quote for my personal loan", [
         "I have received an annual bonus and would like to settle my personal loan in full "
         "before the end of this month.",
         "Please send me a settlement quote showing the outstanding principal, any early "
         "settlement fee, and the total amount payable.",
         "I would also need a liability clearance letter once the loan is closed.",
     ], 350),
]


def message(name, address, mobile, subject, paragraphs, minutes_ago):
    received = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    html = emailfmt.customer(paragraphs, name, mobile,
                             sent_from_phone=minutes_ago % 3 == 0)
    return {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "from": {"emailAddress": {"name": name, "address": address}},
        "sender": {"emailAddress": {"name": name, "address": address}},
        "toRecipients": [{"emailAddress": {"name": "RAKBANK Customer Care",
                                           "address": MAILBOX}}],
        "receivedDateTime": received.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentDateTime": received.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "isRead": False,
        # Without this the message is a draft and server-side sync ignores it.
        "singleValueExtendedProperties": [
            {"id": "Integer 0x0E07", "value": "1"},          # PR_MESSAGE_FLAGS = read/unsent
        ],
    }


def already_sent(token):
    subjects = set()
    for m in gr.paged(f"users/{MAILBOX}/mailFolders/inbox/messages?$select=subject&$top=100",
                      token=token):
        subjects.add((m.get("subject") or "").strip().lower())
    return subjects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", action="store_true", help="send only the next unsent scenario")
    ap.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = ap.parse_args()

    if args.list:
        for i, s in enumerate(SCENARIOS, 1):
            print(f"  {i:>2}. {s[0]:<22} {s[3]}")
        return

    token = gr.app_token()
    seen = already_sent(token)

    pending = [s for s in SCENARIOS if s[3].strip().lower() not in seen]
    if not pending:
        print("Every scenario is already in the mailbox.")
        return
    if args.one:
        pending = pending[:1]

    for name, address, mobile, subject, paragraphs, minutes in pending:
        gr.post(f"users/{MAILBOX}/mailFolders/inbox/messages",
                message(name, address, mobile, subject, paragraphs, minutes),
                token=token)
        print(f"  + {name:<22} {subject}")

    print(f"\n{len(pending)} message(s) delivered to {MAILBOX}")
    print("Server-side sync polls roughly every 5 minutes.")


if __name__ == "__main__":
    main()

"""Shared email rendering for the RAKBANK demo data.

Dataverse renders the email `description` field as HTML, so the demo threads are
built here rather than inline in the seeding scripts. Two voices are produced:

- `bank(...)`   an outbound reply on RAKBANK letterhead, with a named advisor,
                the case reference, a stated next step and a standard footer.
- `customer(...)` an inbound message with a normal personal sign-off.

Keeping both in one place means the twenty original cases and any later batch
render identically.
"""

FONT = "font-family:Segoe UI,Arial,sans-serif;font-size:10.5pt;color:#201f1e;"
MUTED = "font-family:Segoe UI,Arial,sans-serif;font-size:8.5pt;color:#605e5c;"

# (name, job title, team) keyed by the handling team so a case's correspondence
# comes from a plausible owner rather than a generic mailbox.
ADVISORS = {
    "cards":       ("Reem Al Falasi",    "Senior Cards Specialist",        "Card Operations"),
    "disputes":    ("Hussain Al Marri",  "Disputes and Chargebacks Officer", "Card Disputes"),
    "fraud":       ("Dana Al Kaabi",     "Fraud Investigations Officer",   "Fraud and Security"),
    "payments":    ("Ahmed Rahman",      "Payments Investigation Analyst", "Payments Investigations"),
    "digital":     ("Joseph Fernandes",  "Digital Banking Support Analyst", "Digital Banking Support"),
    "lending":     ("Mariam Al Hammadi", "Retail Lending Officer",         "Retail Lending Operations"),
    "mortgage":    ("Saeed Al Rashdi",   "Home Finance Consultant",        "Home Finance"),
    "premier":     ("Alia Al Mansoori",  "Premier Relationship Manager",   "Premier Banking"),
    "complaints":  ("Nadia Al Suwaidi",  "Customer Care Team Leader",      "Customer Care"),
    "regulatory":  ("Faisal Al Zeyoudi", "Senior Regulatory Complaints Manager", "Regulatory Complaints"),
    "onboarding":  ("Huda Al Balushi",   "Client Onboarding Specialist",   "Onboarding Operations"),
    "compliance":  ("Yasir Abdullah",    "KYC and Compliance Officer",     "Financial Crime Compliance"),
    "collections": ("Rania Haddad",      "Collections and Recoveries Specialist", "Collections"),
    "servicing":   ("Meera Iyer",        "Customer Service Officer",       "Account Services"),
    "branch":      ("Omar Al Zaabi",     "Branch Service Manager",         "Branch Operations"),
}

FOOTER = (
    "RAKBANK &middot; The National Bank of Ras Al Khaimah (P.S.C.)<br/>"
    "Contact centre 04 213 0000 &middot; rakbank.ae<br/><br/>"
    "This message and any attachments are confidential and intended solely for the "
    "addressee. If you have received it in error, please notify the sender and delete it. "
    "RAKBANK will never ask you to disclose your PIN, password, OTP or full card number "
    "by email or telephone."
)


def _paras(body, style=FONT):
    return "".join(f'<p style="{style}margin:0 0 10pt 0;">{p}</p>'
                   for p in body if p is not None)


def bank(greeting, body, advisor, case_ref, next_step=None):
    """Render an outbound bank reply.

    `body` is a list of paragraphs. `next_step` is called out separately because
    every real service email tells the customer what happens next and by when.
    """
    name, title, team = ADVISORS[advisor]
    html = [f'<div style="{FONT}">']
    html.append(f'<p style="{FONT}margin:0 0 10pt 0;">{greeting}</p>')
    html.append(_paras(body))
    if next_step:
        html.append(
            f'<table cellpadding="0" cellspacing="0" style="margin:0 0 12pt 0;">'
            f'<tr><td style="border-left:3px solid #0f6cbd;padding:6pt 0 6pt 10pt;{FONT}">'
            f'<b>What happens next</b><br/>{next_step}</td></tr></table>')
    html.append(f'<p style="{FONT}margin:0 0 10pt 0;">'
                f'If you have any questions in the meantime, please reply to this email '
                f'quoting reference <b>{case_ref}</b> and it will come straight back to me.</p>')
    html.append(f'<p style="{FONT}margin:0 0 2pt 0;">Kind regards,</p>')
    html.append(f'<p style="{FONT}margin:0 0 10pt 0;"><b>{name}</b><br/>{title}<br/>'
                f'{team}, RAKBANK</p>')
    html.append(f'<hr style="border:none;border-top:1px solid #edebe9;margin:12pt 0 8pt 0;"/>')
    html.append(f'<p style="{MUTED}margin:0;">Our reference: <b>{case_ref}</b></p>')
    html.append(f'<p style="{MUTED}margin:6pt 0 0 0;">{FOOTER}</p>')
    html.append("</div>")
    return "".join(html)


def customer(body, name, mobile=None, sent_from_phone=False):
    """Render an inbound customer message."""
    html = [f'<div style="{FONT}">', _paras(body)]
    html.append(f'<p style="{FONT}margin:0 0 2pt 0;">{name}</p>')
    if mobile:
        html.append(f'<p style="{MUTED}margin:0;">{mobile}</p>')
    if sent_from_phone:
        html.append(f'<p style="{MUTED}margin:8pt 0 0 0;">Sent from my iPhone</p>')
    html.append("</div>")
    return "".join(html)

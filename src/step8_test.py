"""Step 8: create test cases that should hit each template and verify what the engine applied."""
import time
import dv

P = dv.PREFIX

CONTACTS = [
    ("Aisha", "Al Marzouqi", "aisha.almarzouqi@contoso.ae"),
    ("John", "Smith", "john.smith@contoso.com"),
    ("Rashid", "Al Hosani", "rashid.alhosani@contoso.ae"),
    ("Elena", "Petrova", "elena.petrova@contoso.com"),
    ("Omar", "Haddad", "omar.haddad@contoso.ae"),
]

# title, category, priority, segment, origin, expected template
CASES = [
    ("Mis-sold travel insurance on premier account", 1, 1, 1, 1, "Premier Complaint (High Priority)"),
    ("Unauthorised card transaction in Istanbul", 2, 1, 3, 1, "Fraud Dispute - Card"),
    ("Payment gateway outage affecting checkout", 6, 1, 4, 3, "Corporate Escalation"),
    ("New SME account opening - documents pending", 3, 2, 5, 2, "Retail Onboarding - KYC"),
    ("Request duplicate statement for July", 4, 3, 3, 2, "Service Request - Standard"),
    ("Unexplained fee on monthly bill", 7, 2, 3, 2, "Service Request - Standard"),
]


def ensure_contacts():
    ids = []
    for first, last, email in CONTACTS:
        e = dv.find_one("contacts", f"emailaddress1 eq '{email}'", "contactid")
        if e:
            ids.append(e["contactid"])
        else:
            ids.append(dv.new_id(dv.post("contacts", {
                "firstname": first, "lastname": last, "emailaddress1": email})))
    return ids


def create_cases(contact_ids):
    made = []
    for i, (title, cat, pri, seg, origin, expected) in enumerate(CASES):
        existing = dv.find_one("incidents", f"title eq '{title}'", "incidentid")
        if existing:
            made.append((existing["incidentid"], title, expected))
            continue
        cid = dv.new_id(dv.post("incidents", {
            "title": title,
            "description": f"Seeded test case for the Case Process Configurator demo. {title}.",
            f"{P}_casecategory": cat,
            "prioritycode": pri,
            f"{P}_customersegment": seg,
            "caseorigincode": origin,
            "customerid_contact@odata.bind": f"/contacts({contact_ids[i % len(contact_ids)]})",
        }))
        made.append((cid, title, expected))
        print("  + case", title)
    return made


def verify(made):
    ok = True
    for cid, title, expected in made:
        c = dv.get(f"incidents({cid})?$select=title,{P}_processsummary,{P}_taskstotal,{P}_docstotal,"
                   f"{P}_firstresponsedue,{P}_resolutiondue,processid,stageid,prioritycode,"
                   f"_{P}_appliedtemplate_value")
        tmpl_id = c.get(f"_{P}_appliedtemplate_value")
        tmpl = dv.get(f"{P}_caseprocesstemplates({tmpl_id})?$select={P}_name")[f"{P}_name"] if tmpl_id else None
        tasks = dv.get(f"tasks?$select=subject,{P}_sequence,{P}_stagename,{P}_assignedteamname,"
                       f"{P}_sladue,scheduledend&$filter=_regardingobjectid_value eq {cid}"
                       f"&$orderby={P}_sequence asc")["value"]
        docs = dv.get(f"{P}_caserequireddocuments?$select={P}_name,{P}_mandatory,{P}_duedate"
                      f"&$filter=_{P}_case_value eq {cid}&$orderby={P}_sequence asc")["value"]
        applied = dv.get(f"{P}_appliedprocesses?$select={P}_result,{P}_durationms,{P}_bpfapplied,"
                         f"{P}_stageset,{P}_slaapplied,{P}_evaluationlog"
                         f"&$filter=_{P}_case_value eq {cid}")["value"]

        good = tmpl == expected
        ok = ok and good
        print("=" * 78)
        print(("PASS " if good else "FAIL ") + title)
        print("   template  :", tmpl, "(expected", expected + ")")
        if applied:
            a = applied[0]
            print("   bpf/stage :", a.get(f"{P}_bpfapplied"), "/", a.get(f"{P}_stageset"))
            print("   sla       :", a.get(f"{P}_slaapplied"))
            print("   apply ms  :", a.get(f"{P}_durationms"))
        print("   first resp:", c.get(f"{P}_firstresponsedue"), " resolution:", c.get(f"{P}_resolutiondue"))
        print("   processid :", c.get("processid"), "stageid:", c.get("stageid"))
        print("   tasks     :", len(tasks))
        for t in tasks:
            print("      ", t.get(f"{P}_sequence"), "|", t["subject"][:44].ljust(44),
                  "|", (t.get(f"{P}_stagename") or "").ljust(20),
                  "|", (t.get(f"{P}_assignedteamname") or "")[:34],
                  "| sla", (t.get(f"{P}_sladue") or "")[:16])
        print("   documents :", len(docs))
        for d in docs:
            print("      ", d[f"{P}_name"][:44].ljust(44),
                  "mandatory" if d.get(f"{P}_mandatory") else "optional",
                  "due", (d.get(f"{P}_duedate") or "")[:16])
    return ok


if __name__ == "__main__":
    print("Contacts")
    ids = ensure_contacts()
    print("Cases")
    made = create_cases(ids)
    time.sleep(4)
    print("Verification")
    good = verify(made)
    print("\nRESULT:", "ALL PASS" if good else "SOME FAILED")

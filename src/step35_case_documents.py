"""Mark required documents received on the second wave of cases and attach evidence.

The first 22 cases already carry received documents with PDF notes on the case
timeline; the 20 cases added by step33 were created bare. This walks each of them
and marks the documents that would realistically be in hand by now - everything
up to and including the last completed task's point in the process - leaving the
rest outstanding so the widget still shows work to do.

Attachments are notes on the case (objecttypecode 'incident'), matching how the
first wave was seeded.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step35_case_documents.py
"""
import base64
import datetime as dt
import re

import dv
import step33_more_cases as wave2

P = dv.PREFIX

# a tiny but genuinely valid one-page PDF, so the note opens rather than erroring
PDF = base64.b64encode(
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
    b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
    b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 66>>stream\n"
    b"BT /F1 14 Tf 72 760 Td (RAKBANK - customer supplied document) Tj ET\n"
    b"endstream endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
).decode()


def filename(doc_name):
    slug = re.sub(r"[^a-z0-9]+", "_", doc_name.lower()).strip("_")
    return f"{slug}.pdf"


def main():
    titles = {c[0] for c in wave2.CASES}
    cases = [c for c in dv.get("incidents?$select=incidentid,title,createdon&$top=800")["value"]
             if c["title"] in titles]
    print(f"second-wave cases: {len(cases)}")

    marked = notes = 0
    for case in cases:
        cid = case["incidentid"]
        docs = dv.get(f"{P}_caserequireddocuments?$select={P}_caserequireddocumentid,"
                      f"{P}_name,{P}_sequence,{P}_received,{P}_mandatory"
                      f"&$filter=_{P}_case_value eq {cid}&$orderby={P}_sequence asc")["value"]
        if not docs:
            continue

        # how far the case has progressed decides how much evidence is in hand
        tasks = dv.get(f"tasks?$select=statecode&$filter=_regardingobjectid_value eq {cid}")["value"]
        done = sum(1 for t in tasks if t["statecode"] == 1)
        share = (done / len(tasks)) if tasks else 0.5
        take = max(1, round(len(docs) * share))
        if take == len(docs) and any(not d[f"{P}_received"] for d in docs):
            take = len(docs) - 1 if len(docs) > 1 else 1

        opened = dt.datetime.fromisoformat(case["createdon"].replace("Z", "+00:00"))
        for i, doc in enumerate(docs[:take]):
            if doc[f"{P}_received"]:
                continue
            when = opened + dt.timedelta(hours=6 + i * 9)
            dv.patch(f"{P}_caserequireddocuments({doc[f'{P}_caserequireddocumentid']})", {
                f"{P}_received": True,
                f"{P}_receivedon": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            dv.post("annotations", {
                "subject": doc[f"{P}_name"],
                "notetext": f"Received from the customer and verified against the "
                            f"process requirement '{doc[f'{P}_name']}'.",
                "filename": filename(doc[f"{P}_name"]),
                "mimetype": "application/pdf",
                "documentbody": PDF,
                "objectid_incident@odata.bind": f"/incidents({cid})",
            })
            marked += 1
            notes += 1
        print(f"  {case['title'][:52]:<52} {take}/{len(docs)} received")

    print(f"\n{marked} document(s) marked received, {notes} attachment(s) added.")

    total = dv.get(f"{P}_caserequireddocuments?$select={P}_received&$top=1000")["value"]
    print(f"org-wide: {sum(1 for d in total if d[f'{P}_received'])}/{len(total)} received")


if __name__ == "__main__":
    main()

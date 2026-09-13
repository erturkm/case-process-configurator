"""Seed the RAKBANK demo customer base.

Twenty UAE retail contacts carrying the customer segment on the customer record
(not the case), plus a light spread of city, phone and account number so the
case forms and the customer 360 widgets have something real to show.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step29_retail_customers.py
"""
import dv

PREMIER, PRIORITY, RETAIL, CORPORATE, SME = 1, 2, 3, 4, 5

# (first, last, email, mobile, city, segment)
CUSTOMERS = [
    ("Aisha",   "Al Marzouqi",  "aisha.almarzouqi@contoso.ae",  "+971501112201", "Abu Dhabi", PREMIER),
    ("Rashid",  "Al Hosani",    "rashid.alhosani@contoso.ae",   "+971501112202", "Abu Dhabi", CORPORATE),
    ("Omar",    "Haddad",       "omar.haddad@contoso.ae",       "+971501112203", "Dubai",     RETAIL),
    ("Fatima",  "Al Suwaidi",   "fatima.alsuwaidi@contoso.ae",  "+971501112204", "Dubai",     PREMIER),
    ("Khalid",  "Al Nuaimi",    "khalid.alnuaimi@contoso.ae",   "+971501112205", "Sharjah",   PRIORITY),
    ("Maryam",  "Al Zaabi",     "maryam.alzaabi@contoso.ae",    "+971501112206", "Dubai",     RETAIL),
    ("Yousef",  "Al Blooshi",   "yousef.alblooshi@contoso.ae",  "+971501112207", "Ajman",     RETAIL),
    ("Noura",   "Al Shamsi",    "noura.alshamsi@contoso.ae",    "+971501112208", "Abu Dhabi", PRIORITY),
    ("Sami",    "Chahine",      "sami.chahine@contoso.ae",      "+971501112209", "Dubai",     RETAIL),
    ("Layla",   "Mansour",      "layla.mansour@contoso.ae",     "+971501112210", "Dubai",     PREMIER),
    ("Imran",   "Qureshi",      "imran.qureshi@contoso.ae",     "+971501112211", "Sharjah",   RETAIL),
    ("Priya",   "Nair",         "priya.nair@contoso.ae",        "+971501112212", "Dubai",     PRIORITY),
    ("Daniel",  "Okafor",       "daniel.okafor@contoso.ae",     "+971501112213", "Dubai",     RETAIL),
    ("Hessa",   "Al Muhairi",   "hessa.almuhairi@contoso.ae",   "+971501112214", "Abu Dhabi", PREMIER),
    ("Tariq",   "Bin Saleh",    "tariq.binsaleh@contoso.ae",    "+971501112215", "Al Ain",    RETAIL),
    ("Grace",   "Mensah",       "grace.mensah@contoso.ae",      "+971501112216", "Dubai",     RETAIL),
    ("Anton",   "Kovacs",       "anton.kovacs@contoso.ae",      "+971501112217", "Dubai",     PRIORITY),
    ("Salma",   "Bakr",         "salma.bakr@contoso.ae",        "+971501112218", "Ras Al Khaimah", RETAIL),
    ("Vikram",  "Shetty",       "vikram.shetty@contoso.ae",     "+971501112219", "Dubai",     SME),
    ("Elena",   "Petrova",      "elena.petrova@contoso.com",    "+971501112220", "Dubai",     SME),
]


def existing():
    rows = dv.get("contacts?$select=contactid,emailaddress1&$top=500")["value"]
    return {(r.get("emailaddress1") or "").lower(): r["contactid"] for r in rows if r.get("emailaddress1")}


def main():
    have = existing()
    made = updated = 0
    for first, last, email, mobile, city, seg in CUSTOMERS:
        body = {
            "firstname": first, "lastname": last, "emailaddress1": email,
            "mobilephone": mobile, "telephone1": mobile,
            "address1_city": city, "address1_country": "United Arab Emirates",
            "address1_line1": f"{city} Branch Catchment",
            "cpc_customersegment": seg,
            "preferredcontactmethodcode": 2,  # email
        }
        cid = have.get(email.lower())
        if cid:
            dv.call("PATCH", f"contacts({cid})", body)
            updated += 1
            print(f"  ~ {first} {last}")
        else:
            r = dv.call("POST", "contacts", body)
            made += 1
            print(f"  + {first} {last}")
    print(f"\n{made} created, {updated} updated.")


if __name__ == "__main__":
    print("Retail customers")
    main()

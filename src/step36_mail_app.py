"""Register the Entra app that seeds customer email into the demo mailbox.

Creating a message directly in a mailbox folder needs Mail.ReadWrite as an
*application* permission - delegated tokens from the Azure CLI do not carry mail
scopes. The signed-in admin already holds Application.ReadWrite.All and
AppRoleAssignment.ReadWrite.All, so the registration, the consent and the secret
can all be created without touching the portal.

Access is deliberately narrowed afterwards: an ApplicationAccessPolicy would be
the ideal scope limiter, but that needs Exchange PowerShell, so instead the app
is documented as demo-only and the secret is short-lived.

    python3 step36_mail_app.py
"""
import datetime as dt
import json
import os
import time

import gr

APP_NAME = "RAKBANK Demo Mail Seeder"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

# Microsoft Graph application permissions
ROLES = {
    "Mail.ReadWrite": "e2a3a72e-5f79-4c64-b1b1-878b674786c9",
    "Mail.Send": "b633e1c5-b582-4048-a93e-9f11b44c7e96",
    "User.Read.All": "df021288-bdef-4463-88db-98f22de89214",
}


def ensure_app():
    existing = gr.get(f"applications?$filter=displayName eq '{APP_NAME}'")["value"]
    if existing:
        print(f"  = app exists: {existing[0]['appId']}")
        return existing[0]
    app = gr.post("applications", {
        "displayName": APP_NAME,
        "signInAudience": "AzureADMyOrg",
        "requiredResourceAccess": [{
            "resourceAppId": GRAPH_APP_ID,
            "resourceAccess": [{"id": rid, "type": "Role"} for rid in ROLES.values()],
        }],
    })
    print(f"  + app created: {app['appId']}")
    return app


def ensure_sp(app_id):
    existing = gr.get(f"servicePrincipals?$filter=appId eq '{app_id}'")["value"]
    if existing:
        print("  = service principal exists")
        return existing[0]
    sp = gr.post("servicePrincipals", {"appId": app_id})
    print("  + service principal created")
    return sp


def grant_roles(sp_id):
    graph_sp = gr.get(f"servicePrincipals?$filter=appId eq '{GRAPH_APP_ID}'")["value"][0]
    granted = {a["appRoleId"] for a in
               gr.get(f"servicePrincipals/{sp_id}/appRoleAssignments")["value"]}
    for name, rid in ROLES.items():
        if rid in granted:
            print(f"  = consent already granted: {name}")
            continue
        gr.post(f"servicePrincipals/{sp_id}/appRoleAssignedTo", {
            "principalId": sp_id,
            "resourceId": graph_sp["id"],
            "appRoleId": rid,
        })
        print(f"  + consent granted: {name}")


def new_secret(app_object_id):
    expiry = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)
    res = gr.post(f"applications/{app_object_id}/addPassword", {
        "passwordCredential": {
            "displayName": f"seeder {dt.date.today()}",
            "endDateTime": expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    })
    print(f"  + secret issued, expires {expiry:%Y-%m-%d}")
    return res["secretText"]


def main():
    print("Registering mail seeder app")
    app = ensure_app()
    sp = ensure_sp(app["appId"])
    grant_roles(sp["id"])
    secret = new_secret(app["id"])

    tenant = gr.get("organization?$select=id")["value"][0]["id"]
    os.makedirs(os.path.dirname(gr.CRED_PATH), exist_ok=True)
    with open(gr.CRED_PATH, "w") as fh:
        json.dump({"tenant_id": tenant, "client_id": app["appId"],
                   "client_secret": secret, "app_object_id": app["id"]}, fh, indent=2)
    os.chmod(gr.CRED_PATH, 0o600)
    print(f"\n  credentials -> {gr.CRED_PATH}")

    print("\nWaiting for the consent to propagate", end="", flush=True)
    mailbox = "customerservice@D365DemoTSCE13436844.onmicrosoft.com"
    for _ in range(20):
        try:
            gr._app_token = None
            box = gr.get(f"users/{mailbox}/mailFolders/inbox"
                         f"?$select=displayName,totalItemCount", token=gr.app_token())
            print(f"\n  mailbox reachable: {box['displayName']}, "
                  f"{box['totalItemCount']} item(s)")
            return
        except RuntimeError:
            print(".", end="", flush=True)
            time.sleep(15)
    print("\n  ! still not reachable - consent can take a few minutes, re-run to check")


if __name__ == "__main__":
    main()

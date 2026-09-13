"""Wire the RAKBANK customer-care mailbox up to a Dataverse queue.

Creating a queue with an email address makes Dataverse auto-create a matching
mailbox record. That mailbox is what has to be approved and tested before
server-side sync will pull anything in, so this script creates the queue, finds
the mailbox it produced, points it at the Exchange Online server profile, sets it
to server-side sync for incoming and outgoing, and approves the address.

The final "Test & Enable" is a portal action - it kicks off an async mailbox test
against Exchange - so the script prints the deep link rather than pretending it
can be done over the Web API.

    export DATAVERSE_URL="https://org5806161a.crm4.dynamics.com"
    python3 step37_queue_mailbox.py
"""
import dv

MAILBOX = "customerservice@D365DemoTSCE13436844.onmicrosoft.com"
QUEUE_NAME = "RAKBANK Customer Care"
PROFILE_NAME = "Microsoft Exchange Online"

PUBLIC_QUEUE = 0
SERVER_SIDE_SYNC = 2          # incoming/outgoing email delivery method
FILTER_ALL_MESSAGES = 0       # incomingemailfilteringmethod


def ensure_queue():
    q = dv.find_one("queues", f"name eq '{QUEUE_NAME}'",
                    "queueid,name,emailaddress,_defaultmailbox_value")
    if q:
        print(f"  = queue exists: {q['name']}")
        if (q.get("emailaddress") or "").lower() != MAILBOX.lower():
            dv.patch(f"queues({q['queueid']})", {"emailaddress": MAILBOX})
            print("  ~ queue email address corrected")
        return q["queueid"]

    qid = dv.new_id(dv.post("queues", {
        "name": QUEUE_NAME,
        "description": "Inbound retail banking customer email. Cases are created "
                       "automatically and matched to a process template.",
        "emailaddress": MAILBOX,
        "queuetypecode": PUBLIC_QUEUE,
        "incomingemailfilteringmethod": FILTER_ALL_MESSAGES,
    }))
    print(f"  + queue created: {QUEUE_NAME}")
    return qid


def main():
    qid = ensure_queue()

    profile = dv.find_one("emailserverprofiles", f"name eq '{PROFILE_NAME}'",
                          "emailserverprofileid,name")
    if not profile:
        raise SystemExit(f"no email server profile named {PROFILE_NAME!r}")

    q = dv.get(f"queues({qid})?$select=name,emailaddress,_defaultmailbox_value")
    mb_id = q.get("_defaultmailbox_value")
    if not mb_id:
        mb = dv.find_one("mailboxes", f"emailaddress eq '{MAILBOX}'", "mailboxid,name")
        mb_id = mb["mailboxid"] if mb else None
    if not mb_id:
        raise SystemExit("Dataverse has not created the queue mailbox yet - re-run shortly")

    dv.patch(f"mailboxes({mb_id})", {
        "emailserverprofile@odata.bind":
            f"/emailserverprofiles({profile['emailserverprofileid']})",
        "incomingemaildeliverymethod": SERVER_SIDE_SYNC,
        "outgoingemaildeliverymethod": SERVER_SIDE_SYNC,
        "isemailaddressapprovedbyo365admin": True,
    })

    mb = dv.get(f"mailboxes({mb_id})?$select=name,emailaddress,"
                "incomingemaildeliverymethod,outgoingemaildeliverymethod,"
                "isemailaddressapprovedbyo365admin,processingstatecode,"
                "testemailconfigurationscheduled")

    print("\nQueue mailbox ready for testing")
    print(f"  mailbox name : {mb['name']}")
    print(f"  address      : {mb['emailaddress']}")
    print(f"  incoming     : {mb.get('incomingemaildeliverymethod@OData.Community.Display.V1.FormattedValue')}")
    print(f"  outgoing     : {mb.get('outgoingemaildeliverymethod@OData.Community.Display.V1.FormattedValue')}")
    print(f"  approved     : {mb.get('isemailaddressapprovedbyo365admin')}")
    print(f"  test status  : {mb.get('testemailconfigurationscheduled')}")
    print(f"\n  open it here:\n  {dv.ORG}/main.aspx?etn=mailbox&id={mb_id}&pagetype=entityrecord")
    print("\n  In that form choose 'Test & Enable Mailbox' on the command bar.")


if __name__ == "__main__":
    main()

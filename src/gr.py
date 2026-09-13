"""Microsoft Graph helper for the RAKBANK email-to-case demo.

Two different identities are used here:

  * the Azure CLI login (Marco Henry, tenant admin) - used to register the app
    and read directory data;
  * a dedicated app registration with Mail.ReadWrite application permission -
    used to write messages into the customer-care mailbox.

The app's client secret never lives in this repository (it is published
publicly). It is written to the session store instead, and read back from
GRAPH_CRED_PATH or the default location below.
"""
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"
GRAPH_RESOURCE = "https://graph.microsoft.com"

CRED_PATH = os.environ.get(
    "GRAPH_CRED_PATH",
    os.path.expanduser("~/.cpc/mailapp.json"),
)

_cli_token = None
_app_token = None


def cli_token():
    """Delegated token for the signed-in Azure CLI user (tenant admin)."""
    global _cli_token
    if _cli_token is None:
        _cli_token = subprocess.check_output(
            ["az", "account", "get-access-token", "--resource", GRAPH_RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            stderr=subprocess.DEVNULL).decode().strip()
    return _cli_token


def credentials():
    with open(CRED_PATH) as fh:
        return json.load(fh)


def app_token():
    """Client-credentials token for the mail app registration."""
    global _app_token
    if _app_token is None:
        c = credentials()
        body = urllib.parse.urlencode({
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "scope": f"{GRAPH_RESOURCE}/.default",
            "grant_type": "client_credentials",
        }).encode()
        url = f"https://login.microsoftonline.com/{c['tenant_id']}/oauth2/v2.0/token"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body)) as r:
                _app_token = json.load(r)["access_token"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"token request failed: {e.code}\n"
                f"{e.read().decode(errors='ignore')[:600]}") from None
    return _app_token


def _encode(path):
    """Percent-encode the query string; OData filters are full of spaces."""
    if "?" not in path:
        return urllib.parse.quote(path, safe="/$(),'@=")
    head, _, query = path.partition("?")
    head = urllib.parse.quote(head, safe="/$(),'@=")
    return f"{head}?{urllib.parse.quote(query, safe='$&=,()/:@' + chr(39))}"


def call(method, path, body=None, token=None, base=GRAPH):
    url = path if path.startswith("http") else f"{base}/{_encode(path)}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token or cli_token()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:1200]
        raise RuntimeError(f"{method} {url} -> {e.code}\n{detail}") from None


def get(path, token=None, base=GRAPH):
    return call("GET", path, None, token, base)


def post(path, body, token=None, base=GRAPH):
    return call("POST", path, body, token, base)


def patch(path, body, token=None, base=GRAPH):
    return call("PATCH", path, body, token, base)


def delete(path, token=None, base=GRAPH):
    return call("DELETE", path, None, token, base)


def paged(path, token=None, base=GRAPH):
    """Follow @odata.nextLink and yield every item."""
    page = get(path, token, base)
    while page:
        for item in page.get("value", []):
            yield item
        nxt = page.get("@odata.nextLink")
        page = call("GET", nxt, None, token) if nxt else None

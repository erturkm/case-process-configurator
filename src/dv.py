"""Shared Dataverse Web API helper for the Case Process Configurator build.

Set the target environment before running any step, for example:

    export DATAVERSE_URL="https://yourorg.crm.dynamics.com"

Authentication uses the Azure CLI, so sign in first with `az login`.
"""
import json, os, subprocess, time, urllib.parse, urllib.request, urllib.error

ORG = os.environ.get("DATAVERSE_URL", "").rstrip("/")
if not ORG:
    raise SystemExit(
        "DATAVERSE_URL is not set.\n"
        '  export DATAVERSE_URL="https://yourorg.crm.dynamics.com"'
    )
API = ORG + "/api/data/v9.2"
PREFIX = os.environ.get("CPC_PREFIX", "cpc")
SOLUTION = os.environ.get("CPC_SOLUTION", "CaseProcessConfigurator")
_tok = {"v": None, "t": 0}


def token():
    if _tok["v"] and time.time() - _tok["t"] < 2400:
        return _tok["v"]
    t = subprocess.check_output(
        ["az", "account", "get-access-token", "--resource", ORG, "--query", "accessToken", "-o", "tsv"],
        text=True).strip()
    _tok["v"], _tok["t"] = t, time.time()
    return t


def call(method, path, body=None, headers=None, solution=False):
    url = path if path.startswith("http") else API + "/" + path.lstrip("/")
    url = urllib.parse.quote(url, safe=":/?&$=,()'*+%@.-_~!;")
    data = json.dumps(body).encode() if body is not None else None
    h = {"Authorization": "Bearer " + token(), "Accept": "application/json",
         "OData-MaxVersion": "4.0", "OData-Version": "4.0"}
    if data:
        h["Content-Type"] = "application/json"
    if solution:
        h["MSCRM.SolutionUniqueName"] = SOLUTION
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
            loc = r.headers.get("OData-EntityId")
            if not raw:
                return {"_location": loc}
            out = json.loads(raw)
            if loc:
                out["_location"] = loc
            return out
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}\n{e.read().decode(errors='ignore')[:1500]}") from None


def get(path):
    return call("GET", path)


def post(path, body, solution=False):
    return call("POST", path, body, solution=solution)


def patch(path, body, solution=False):
    return call("PATCH", path, body, headers={"If-Match": "*"}, solution=solution)


def upsert(path, body):
    """PATCH with If-None-Match omitted so it creates or updates by alternate key."""
    return call("PATCH", path, body, headers={"If-Match": "*"})


def new_id(resp):
    loc = resp.get("_location", "")
    return loc.split("(")[-1].rstrip(")") if loc else None


def find_one(entityset, filt, select="*"):
    r = get(f"{entityset}?$select={select}&$filter={filt}&$top=1")
    v = r.get("value", [])
    return v[0] if v else None


def label(text, lcid=1033):
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label",
            "LocalizedLabels": [{"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                                 "Label": text, "LanguageCode": lcid}]}


def publish_all():
    call("POST", "PublishAllXml", {})

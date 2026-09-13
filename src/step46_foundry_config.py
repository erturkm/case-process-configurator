"""Create Dataverse environment variables holding the Foundry connection for cpc_DesignProcess."""
import dv, os

def need(var):
    """Nothing about the Foundry connection is hardcoded: this repository is public,
    and the tenant, app registration and secret are all deployment specific."""
    v = os.environ.get(var, "").strip()
    if not v:
        raise SystemExit(
            f"{var} is not set. Configure the Foundry connection first, for example:\n"
            '  export CPC_FOUNDRY_ENDPOINT="https://<your-resource>.openai.azure.com"\n'
            '  export CPC_FOUNDRY_DEPLOYMENT="gpt-4.1"\n'
            '  export CPC_FOUNDRY_API_VERSION="2024-12-01-preview"\n'
            '  export CPC_FOUNDRY_TENANT_ID="<tenant guid>"\n'
            '  export CPC_FOUNDRY_CLIENT_ID="<app registration id>"\n'
            '  export CPC_FOUNDRY_CLIENT_SECRET="<client secret>"')
    return v


VARS = [
    ("cpc_FoundryEndpoint",    "Foundry endpoint",    need("CPC_FOUNDRY_ENDPOINT")),
    ("cpc_FoundryDeployment",  "Foundry deployment",  need("CPC_FOUNDRY_DEPLOYMENT")),
    ("cpc_FoundryApiVersion",  "Foundry api-version", need("CPC_FOUNDRY_API_VERSION")),
    ("cpc_FoundryTenantId",    "Entra tenant id",     need("CPC_FOUNDRY_TENANT_ID")),
    ("cpc_FoundryClientId",    "Entra client id",     need("CPC_FOUNDRY_CLIENT_ID")),
    ("cpc_FoundryClientSecret", "Entra client secret", need("CPC_FOUNDRY_CLIENT_SECRET")),
]

for schema, label, value in VARS:
    existing = dv.get(f"environmentvariabledefinitions?$select=environmentvariabledefinitionid"
                      f"&$filter=schemaname eq '{schema}'")["value"]
    if existing:
        defid = existing[0]["environmentvariabledefinitionid"]
        print(f"  = {schema} (definition exists)")
    else:
        r = dv.post("environmentvariabledefinitions", {
            "schemaname": schema,
            "displayname": label,
            "type": 100000000,          # String
            "isrequired": False,
        }, solution=True)
        defid = dv.new_id(r)
        print(f"  + {schema}")

    vals = dv.get(f"environmentvariablevalues?$select=environmentvariablevalueid"
                  f"&$filter=_environmentvariabledefinitionid_value eq {defid}")["value"]
    if vals:
        dv.patch(f"environmentvariablevalues({vals[0]['environmentvariablevalueid']})",
                 {"value": value})
        print(f"      value updated")
    else:
        dv.post("environmentvariablevalues", {
            "value": value,
            "EnvironmentVariableDefinitionId@odata.bind":
                f"/environmentvariabledefinitions({defid})",
        })
        print(f"      value set")

print("\ndone. secret is stored in Dataverse, not in source,\n      and the value records are deliberately NOT solution components\n      so they can never be carried out in an exported zip.")

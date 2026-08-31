"""Step 7: register the plugin assembly, types and SDK message processing steps."""
import base64, hashlib, os, subprocess, sys
import dv

HERE = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(HERE, "plugin", "bin", "Release", "CpcPlugins.dll")
ASM_NAME = "CpcPlugins"

# public key token from the signing key
PUBLIC_KEY_TOKEN = None


def compute_identity():
    """Read the assembly identity with ildasm-free reflection using dotnet + a tiny helper."""
    global PUBLIC_KEY_TOKEN
    script = os.path.join(HERE, "plugin", "identity.csx")
    # simplest reliable route: ask Dataverse to parse it. We only need name/version/culture/token,
    # and Dataverse recomputes them server side when Content is supplied.
    return None


def register_assembly():
    content = base64.b64encode(open(DLL, "rb").read()).decode()
    existing = dv.find_one("pluginassemblies", f"name eq '{ASM_NAME}'", "pluginassemblyid,version")
    body = {
        "content": content,
        "name": ASM_NAME,
        "isolationmode": 2,          # sandbox
        "sourcetype": 0,             # database
        "description": "Case Process Configurator engine: applies process templates on case create.",
    }
    if existing:
        dv.patch(f"pluginassemblies({existing['pluginassemblyid']})", {"content": content}, solution=True)
        print("  ~ assembly updated")
        return existing["pluginassemblyid"]
    aid = dv.new_id(dv.post("pluginassemblies", body, solution=True))
    print("  + assembly registered", aid)
    return aid


def register_type(asm_id, typename, friendly):
    ex = dv.find_one("plugintypes", f"typename eq '{typename}'", "plugintypeid")
    if ex:
        print("  exists type", typename)
        return ex["plugintypeid"]
    tid = dv.new_id(dv.post("plugintypes", {
        "typename": typename,
        "friendlyname": friendly,
        "name": friendly,
        "pluginassemblyid@odata.bind": f"/pluginassemblies({asm_id})",
    }, solution=True))
    print("  + type", typename)
    return tid


def message_id(name):
    r = dv.find_one("sdkmessages", f"name eq '{name}'", "sdkmessageid")
    return r["sdkmessageid"]


def filter_id(msg_id, entity):
    r = dv.find_one("sdkmessagefilters",
                    f"_sdkmessageid_value eq {msg_id} and primaryobjecttypecode eq '{entity}'",
                    "sdkmessagefilterid")
    return r["sdkmessagefilterid"] if r else None


def register_step(plugin_type_id, message, entity, stage, mode, name, rank=1, filtering=None):
    """stage: 20 pre-operation, 40 post-operation. mode: 0 sync, 1 async."""
    ex = dv.find_one("sdkmessageprocessingsteps", f"name eq '{name}'", "sdkmessageprocessingstepid")
    if ex:
        print("  exists step", name)
        return ex["sdkmessageprocessingstepid"]
    mid = message_id(message)
    fid = filter_id(mid, entity)
    body = {
        "name": name,
        "description": name,
        "mode": mode,
        "rank": rank,
        "stage": stage,
        "supporteddeployment": 0,
        "invocationsource": 0,
        "plugintypeid@odata.bind": f"/plugintypes({plugin_type_id})",
        "sdkmessageid@odata.bind": f"/sdkmessages({mid})",
    }
    if fid:
        body["sdkmessagefilterid@odata.bind"] = f"/sdkmessagefilters({fid})"
    if filtering:
        body["filteringattributes"] = filtering
    sid = dv.new_id(dv.post("sdkmessageprocessingsteps", body, solution=True))
    dv.patch(f"sdkmessageprocessingsteps({sid})", {"statecode": 0, "statuscode": 1})
    print("  + step", name)
    return sid


if __name__ == "__main__":
    if not os.path.exists(DLL):
        sys.exit("Build the plugin first: dotnet build -c Release")
    print("Assembly")
    asm = register_assembly()

    print("Types")
    t_apply = register_type(asm, "Cpc.Plugins.ApplyCaseProcess", "Apply Case Process")
    t_roll = register_type(asm, "Cpc.Plugins.UpdateCaseRollups", "Update Case Rollups")

    print("Steps")
    register_step(t_apply, "Create", "incident", 40, 0,
                  "CPC: Apply case process on case create", rank=10)
    register_step(t_roll, "Update", "task", 40, 1,
                  "CPC: Roll up task progress to case", rank=20,
                  filtering="statecode,statuscode")
    register_step(t_roll, "Update", "cpc_caserequireddocument", 40, 1,
                  "CPC: Roll up document progress to case", rank=20,
                  filtering="cpc_received")
    dv.publish_all()
    print("done")

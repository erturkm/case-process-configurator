"""Step 1: create publisher cpc and unmanaged solution CaseProcessConfigurator."""
import dv

pub = dv.find_one("publishers", "uniquename eq 'cpcpublisher'", "publisherid,uniquename,customizationprefix")
if pub:
    print("publisher exists", pub["publisherid"], pub["customizationprefix"])
else:
    r = dv.post("publishers", {
        "uniquename": "cpcpublisher",
        "friendlyname": "Case Process Configurator",
        "description": "Publisher for the Case Process Configurator solution",
        "customizationprefix": "cpc",
        "customizationoptionvalueprefix": 74210,
    })
    pub = {"publisherid": dv.new_id(r)}
    print("publisher created", pub["publisherid"])

sol = dv.find_one("solutions", f"uniquename eq '{dv.SOLUTION}'", "solutionid,uniquename,version")
if sol:
    print("solution exists", sol["solutionid"])
else:
    r = dv.post("solutions", {
        "uniquename": dv.SOLUTION,
        "friendlyname": "Case Process Configurator",
        "description": "Declarative case process blueprints: match rules, BPF and stage-linked tasks with owners and task SLAs, document packages.",
        "version": "1.0.0.0",
        "publisherid@odata.bind": f"/publishers({pub['publisherid']})",
    })
    print("solution created", dv.new_id(r))

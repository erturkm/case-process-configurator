# Installation guide

> [!WARNING]
> **Deploy only to a disposable trial, developer or sandbox environment.** This accelerator is a
> demonstration, not a production system. It modifies shared artefacts in your environment,
> including the Case main forms and the model-driven app site map. Read the
> [DISCLAIMER](DISCLAIMER.md) first.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Dynamics 365 Customer Service** environment | A Dataverse environment with the Customer Service (Case / `incident`) tables. A [Power Apps Developer Plan](https://powerapps.microsoft.com/developerplan/) environment works. |
| **System Administrator** role | Required to import solutions, register plug-in assemblies and edit the site map. |
| **Enhanced SLAs enabled** | Service Management → Service Configuration Settings. Needed for SLA stamping. |
| **Plug-in registration allowed** | The engine is a sandbox-isolated assembly. |

Additional prerequisites **only if building from source** (Option B):

| Requirement | Notes |
|---|---|
| **Python 3.9+** | Standard library only — no `pip install` needed. |
| **Azure CLI** (`az`) | Used to acquire Dataverse access tokens. |
| **.NET SDK / MSBuild** | To compile the plug-in assembly targeting .NET Framework 4.6.2. |

---

## Option A — import the packaged solution (recommended)

### 1. Import

1. Go to the [Power Platform admin centre](https://admin.powerplatform.microsoft.com/) → your
   environment → **Solutions** → **Import solution**.
2. Choose `solution/CaseProcessConfigurator_1_0_0_0_managed.zip`.
   *(Use the unmanaged zip instead if you intend to modify and rebuild the solution.)*
3. Accept the plug-in assembly registration prompt when asked.
4. Wait for the import to complete, then **Publish all customizations**.

> **If the import fails with a lock error** (`0x80071151` or `0x80048543`), a Microsoft-managed
> solution is installing in the background. Wait for it to finish and retry — this can take up to
> 30 minutes.

### 2. Assign security roles

The process engine assigns tasks and cases to teams. Each team that will own work needs a security
role with create/read/write privileges on Case, Task and the `cpc_` tables.

Settings → Security → Teams → select each team → **Manage roles**.

> Teams created through the API start with **zero** privileges. A team with no role produces a
> misleading error such as `prvReadActivity on msfp_surveyresponse`. If you see that, the cause is a
> missing role, not a missing survey.

### 3. Verify

1. Open the **Case Process Configurator** app.
2. **Configuration → Case Process Templates** — confirm the sample templates are listed and active.
3. **Configuration → Process Designer** — open a template and confirm the task graph renders.
4. **Runtime → My work** — confirm the dashboard and charts load.
5. Create a Case whose category matches a template, save, then reopen it. The **Case process** panel
   on the Summary tab should show the applied tasks, and the business process flow header should
   show the configured starting stage.

---

## Option B — build from source

This rebuilds the whole solution against your environment, step by step. Every script is
**idempotent** — safe to re-run if a step fails partway.

### 1. Authenticate and set the target

```bash
az login
export DATAVERSE_URL="https://yourorg.crm.dynamics.com"    # no trailing slash
```

Optionally override the publisher prefix and solution name (defaults `cpc` /
`CaseProcessConfigurator`):

```bash
export CPC_PREFIX="cpc"
export CPC_SOLUTION="CaseProcessConfigurator"
```

### 2. Build the plug-in assembly

```bash
cd src/plugin

# Generate a strong-name key (not included in this repository)
openssl genrsa -out key.pem 2048
openssl rsa -in key.pem -outform MSBLOB -out key.snk    # or: sn -k key.snk

dotnet build -c Release
cd ..
```

### 3. Run the build steps in order

```bash
cd src

python3 step1_solution.py           # publisher + unmanaged solution
python3 step2_tables.py             # custom tables and columns
python3 step3_relationships.py      # lookups
python3 step4_slas_teams.py         # demo teams, queues, enhanced SLAs
python3 step4b_activate_slas.py     # activate SLAs
python3 step4c_team_roles.py        # grant the demo teams a security role
python3 step5_runtime_columns.py    # runtime SLA columns on incident and task
python3 step6_seed.py               # document packages and sample templates
python3 step7_register_plugin.py    # register assembly, types and steps
python3 step8_test.py               # verify the engine applies templates

python3 step9_forms_views.py        # forms and views for the cpc_ tables
python3 step10_case_form.py         # Case Process tab on the Case forms
python3 step11_app.py               # model-driven app and site map

python3 step12_outcome_schema.py    # outcome graph schema
python3 step13_register_apis.py     # outcome engine and custom APIs
python3 step14_seed_outcomes.py     # build outcome graphs and lay them out
python3 step15_test_outcomes.py     # verify outcome-driven branching

python3 step16_designer.py          # visual process designer
python3 step17_outcome_picker.py    # outcome picker on the Task form
python3 step18_case_widgets.py      # tabbed case panel on the Case form

python3 step19_banking_processes.py # corporate and retail banking samples
python3 step21_app_bpf.py           # add the BPFs to the apps
python3 step22_workload.py          # My work dashboard and charts

python3 step20_test_credit.py       # full corporate credit walkthrough test
```

> **Re-run `step13_register_apis.py` after every plug-in rebuild**, otherwise the environment keeps
> running the previously uploaded assembly.

> **Long-running steps.** Some steps exceed five minutes and the connection can time out mid-run.
> Because every step is idempotent, simply re-run it. To avoid interactive timeouts:
> `nohup python3 -u step19_banking_processes.py > out.log 2>&1 &`

### 4. Publish

```bash
python3 -c "import dv; dv.publish_all()"
```

---

## Post-installation notes

### Creating your first process

1. **Configuration → Case Process Templates → New.** Give it a name and set it active.
2. **Match rules** — define which cases it targets. Use **Test rules** to check it against existing
   cases before activating.
3. **Process Designer** — lay out the task graph. Each task gets an owner (team, user, case owner or
   case owner's manager), an SLA, and a set of outcomes. Connect outcomes to the tasks they trigger.
4. **Document package** — attach one, if the process requires documents.
5. **Business process flow** — optionally bind a BPF and starting stage, and map tasks to stages.
6. Save, then create a matching case to see it applied.

Or open **Copilot** in the designer and describe the process in plain language.

### If a business process flow header does not appear

A BPF only renders when it is a **component of the model-driven app**. If you create a new flow
manually, add it to the app (or re-run `step21_app_bpf.py`), then publish and hard-refresh.

### Sample data

`step6_seed.py` and `step19_banking_processes.py` create fictitious templates, document packages,
teams and banking scenarios for demonstration. Skip both if you want an empty configuration, but
note that `step8_test.py`, `step15_test_outcomes.py` and `step20_test_credit.py` depend on them.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `DATAVERSE_URL is not set` | Export the variable in the shell running the script. |
| `429` with `0x80071151` or `0x80048543` | A managed solution is installing in the background and holds a lock. Wait and retry; `step22_workload.py` retries automatically. |
| Business process flow header is blank | The flow is not a component of the app. Run `step21_app_bpf.py`, publish, hard-refresh. |
| `prvReadActivity on msfp_surveyresponse` | A team has no security role. Assign one (see step 2 above). |
| Tasks not created on case create | Check the plug-in steps are registered and the assembly is current — re-run `step7_register_plugin.py` and `step13_register_apis.py`. |
| Widgets show blank panes | Publish all customizations, then hard-refresh (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>). |
| SLA fields stay empty | Enhanced SLAs are not enabled, or the SLAs are not activated. Run `step4b_activate_slas.py`. |

---

## Uninstall

**Managed import:** Solutions → **Case Process Configurator** → **Delete**. Managed solutions remove
their own components. The Case form changes and site map entries are reverted with the solution.

**Unmanaged / built from source:** components are not removed automatically. You must manually
delete the `cpc_` tables, plug-in assembly and steps, custom APIs, web resources, model-driven app,
SLAs and teams — and remove the added sections from the Case main forms. **This is another reason to
use a disposable environment.**

Sample records (cases, tasks, document requirements) created during testing are **not** removed by
uninstalling; delete them separately if needed.

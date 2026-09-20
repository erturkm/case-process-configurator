# Installation guide

> [!WARNING]
> **Deploy only to a disposable trial, developer or sandbox environment.** This accelerator is a
> demonstration, not a production system. It adds a model-driven app and edits the site map. Read the
> [DISCLAIMER](DISCLAIMER.md) first.

> [!NOTE]
> **As of 1.2.0 this solution no longer touches Microsoft's forms.** It ships exactly two forms of
> its own — **Case (CPC)** and **Task (CPC)** — and leaves every stock Case and Task form byte for
> byte untouched. This was verified by fingerprinting all 26 Case and Task forms in a vanilla
> Customer Service environment before and after the import: 26 of 26 identical, 0 changed, 2 added.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Dynamics 365 Customer Service** environment | A Dataverse environment with the Customer Service (Case / `incident`) tables. A [Power Apps Developer Plan](https://powerapps.microsoft.com/developerplan/) environment works. |
| **Modern SLA Timer PCF** | **Install this first.** The Task form binds its countdown clock to this control, so the solution import fails without it. See below. |
| **System Administrator** role | Required to import solutions, register plug-in assemblies and edit the site map. |
| **Enhanced SLAs enabled** | Service Management → Service Configuration Settings. Needed for SLA stamping. |
| **Plug-in registration allowed** | The engine is a sandbox-isolated assembly. |

Everything else the solution depends on ships with Customer Service and is present by default:
`msdynce_ServiceLevelAgreement`, `msdynce_AppCommon`, `msdyn_AppFrameworkInfraExtensions`,
`msdyn_CSIntelligence` (the Copilot case summary control on the Case form) and `PowerVirtualAgents`
(the `bot` table, which the agent-task columns look up to). There are **no** other dependencies —
no Field Service, no Sales, and nothing from any sibling accelerator.

### Modern SLA Timer PCF

The countdown clock on each process task is not our control. It is the **Modern SLA Timer** PCF by
Marcelo Oliveira Pinto, used unmodified and under its own licence:

**https://github.com/moliveirapinto/modern-sla-timer-pcf**

It is deliberately *not* bundled into this solution, so that it stays on its own release cadence and
its licence is never restated by us. Install it first — download the solution zip from that
repository's [releases](https://github.com/moliveirapinto/modern-sla-timer-pcf/releases) and import
it before importing this one.

Skipping it produces an import failure naming
`mcsla_ModernSlaTimer.ModernSlaTimerControl` as a missing dependency.

Additional prerequisites **only if building from source** (Option B):

| Requirement | Notes |
|---|---|
| **Python 3.9+** | Standard library only — no `pip install` needed. |
| **Azure CLI** (`az`) | Used to acquire Dataverse access tokens. |
| **.NET SDK / MSBuild** | To compile the plug-in assembly targeting .NET Framework 4.6.2. |

---

## Option A — import the packaged solution (recommended)

### 1. Import

1. **Import the [Modern SLA Timer PCF](https://github.com/moliveirapinto/modern-sla-timer-pcf)
   first** if you have not already — see Prerequisites above. The import fails without it.
2. Go to the [Power Platform admin centre](https://admin.powerplatform.microsoft.com/) → your
   environment → **Solutions** → **Import solution**.
3. Choose `solution/CaseProcessConfigurator_1_2_1_0_managed.zip`.
   *(Use the unmanaged zip instead if you intend to modify and rebuild the solution.)*
4. Accept the plug-in assembly registration prompt when asked.
5. Wait for the import to complete, then **Publish all customizations**.

> **If the import fails with a lock error** (`0x80071151` or `0x80048543`), a Microsoft-managed
> solution is installing in the background. Wait for it to finish and retry — this can take up to
> 30 minutes.

### 2. Add the Customer Segment column

The packaged solution deliberately contains **no customisations of `account` or `contact`** — that
is what keeps its dependency surface limited to Customer Service and the Modern SLA Timer PCF. The
sample templates, however, target **Customer › Customer Segment**, so that column has to be created
in your environment separately:

```bash
az login
export DATAVERSE_URL="https://yourorg.crm.dynamics.com"
python3 src/step26_customer_segment.py
```

This creates the `cpc_customersegment` choice (Premier / Priority / Retail / Corporate / SME) on
both **Account** and **Contact**, in the default solution. Skip it and any template that filters on
customer segment shows a *column not found* entry on the targeting screen and will never match.

> Only needed if you plan to use the shipped sample templates, or to target the customer behind a
> case. Templates that target only the Subject tree work without it.

### 3. Assign security roles

The process engine assigns tasks and cases to teams. Each team that will own work needs a security
role with create/read/write privileges on Case, Task and the `cpc_` tables.

Settings → Security → Teams → select each team → **Manage roles**.

> Teams created through the API start with **zero** privileges. A team with no role produces a
> misleading error such as `prvReadActivity on msfp_surveyresponse`. If you see that, the cause is a
> missing role, not a missing survey.

### 4. Verify

1. Open the **Case Process Configurator** app.
2. **Configuration → Case Process Templates** — confirm the sample templates are listed and active.
3. **Configuration → Process Designer** — open a template and confirm the task graph renders. On the
   **Targeting** step, the *This case* group should list the Case columns of *your* environment, and
   the related-record paths should reflect the lookups your environment actually has. Nothing in that
   screen is hard-coded; it is read from live metadata each time it loads, so two environments will
   legitimately show different lists.
4. **Runtime → My work** — confirm the dashboard and charts load.
5. Create a Case whose **Subject** falls under one targeted by a template, save, then reopen it. It
   opens on the **Case (CPC)** form. The **Case process** panel on the Summary tab should show the
   applied tasks, and the business process flow header should show the configured starting stage.
   Opening one of those tasks shows the **Task (CPC)** form with its outcome picker and countdown
   clock. Recording an outcome closes that task and creates the next one on the chosen branch.

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
python3 step5_runtime_columns.py    # runtime SLA columns on incident and task
python3 step6_seed.py               # document packages and sample templates
python3 step7_register_plugin.py    # register assembly, types and steps
python3 step8_test.py               # verify the engine applies templates

python3 step9_forms_views.py        # forms and views for the cpc_ tables
python3 step10_case_form.py         # Case Process tab on the Case form
python3 step11_app.py               # model-driven app and site map

python3 step12_outcome_schema.py    # outcome graph schema
python3 step13_register_apis.py     # outcome engine and custom APIs
python3 step14_seed_outcomes.py     # build outcome graphs and lay them out
python3 step15_test_outcomes.py     # verify outcome-driven branching

python3 step16_designer.py          # visual process designer
python3 step17_outcome_picker.py    # outcome picker on the Task form
python3 step18_case_widgets.py      # case process panel on the Case form
python3 step51_task_sla_timer.py    # Modern SLA Timer PCF on the Task form

python3 step19_banking_processes.py # corporate and retail banking samples
python3 step4c_team_roles.py        # grant the demo teams a security role
python3 step21_app_bpf.py           # add the BPFs to the apps
python3 step22_workload.py          # My work dashboard and charts

python3 step26_customer_segment.py  # Customer Segment choice column on Account and Contact
python3 step28_retire_category.py   # migrate targeting onto the subject tree + customer segment
python3 step27_engine_test.py       # verify the migrated targeting still matches

python3 step57_cpc_forms.py         # fork Case (CPC) and Task (CPC) from the stock forms
python3 step58_release_oob_forms.py # register the forks, release Microsoft's forms

python3 step20_test_credit.py       # full corporate credit walkthrough test
```

> **`step26` and `step28` are not optional.** The seeds (`step6`, `step19`) write their targeting
> rules against the original `cpc_casecategory` column. `step28_retire_category.py` is the schema
> migration that re-points every rule onto the **Subject** tree (using the *is at or under*
> hierarchy operator) and onto **Customer › Customer Segment**, extends the subject tree, and then
> hides `cpc_casecategory` from Advanced Find. It **must run after the seeds**. Skip it and every
> template still targets a retired column, which the designer cannot resolve — the targeting screen
> then shows a *column not found* entry instead of the real condition.

> **`step26` must run before `step28`**, because the migration re-points the segment rules onto the
> `cpc_customersegment` column that `step26` creates on **Account** and **Contact**.

> **`step4c_team_roles.py` must run *after* `step19_banking_processes.py`**, because that step
> creates the banking teams. Run it earlier and those teams end up with zero privileges, and case
> creation then fails with a misleading `403 / 0x80040299 prvReadActivity` on
> `msdyn_ocoutboundmessage` — which surfaces only in Omnichannel-enabled environments.

> **`step57` and `step58` are what keep Microsoft's forms out of the solution.** Steps 10, 17, 18
> and 51 author onto the stock **Case** and **Task** forms. `step57` then copies those two forms
> into **Case (CPC)** and **Task (CPC)**, stripping anything that belongs to another publisher or to
> a solution the target environment may not have. `step58` registers the two forks in the app and
> removes Microsoft's forms from the solution, leaving it with exactly two form components. Skip
> these and you ship — and overwrite — six Microsoft system forms.

> **Re-run `step13_register_apis.py` after every plug-in rebuild**, otherwise the environment keeps
> running the previously uploaded assembly.

> **Long-running steps.** Some steps exceed five minutes and the connection can time out mid-run.
> Because every step is idempotent, simply re-run it. To avoid interactive timeouts:
> `nohup python3 -u step19_banking_processes.py > out.log 2>&1 &`

### 4. Publish

```bash
python3 -c "import dv; dv.publish_all()"
```

### 5. Package

```bash
python3 step60_package.py --version 1.2.0.0
```

Exports both the unmanaged and managed zips into `dist/`, strips any foreign section that survived
the fork, and cleans the stale `MissingDependencies` manifest. It aborts rather than writing a zip
if a foreign reference is still present.

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

### If the header shows "Phone to Case Process" instead of the mapped flow

Customer Service ships **Phone to Case Process** as an active, order-0 business process flow on
Case, so the platform applies it automatically to every new case. The engine still creates the
instance of the flow the template maps to — you can confirm it in the BPF instance table, and switch
to it from the **Process** menu on the form — but the out-of-the-box flow wins the header by
default. To make the mapped flow the one that shows, deactivate **Phone to Case Process** (Settings
→ Processes), or lower its order below your own flows.

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

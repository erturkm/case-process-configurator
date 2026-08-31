# Case Process Configurator

**A declarative, business-user-configurable case handling accelerator for Microsoft Dynamics 365 Customer Service and Dataverse.**

> [!WARNING]
> **This is a demonstration accelerator. It is not built, reviewed or tested for production use, and is provided "as is" with no warranty and no support. Use entirely at your own risk.** Deploy only to a disposable trial, developer or sandbox environment — never to production, and never to an environment holding real personal, regulated or business-critical data. Please read the full [DISCLAIMER](DISCLAIMER.md) before installing.

---

## The problem

In most case management implementations, "how we handle this type of case" is buried in code —
plug-ins, workflows, hard-coded task lists, branching logic in JavaScript. When the business wants
to change the order of two steps, add a required document, reassign a step to a different team, or
tighten an SLA, they raise a change request and wait weeks for a developer.

The process knowledge lives with the business. The ability to change it lives with IT.

## What this accelerator does

It moves the entire case handling process into **configuration data that a business user owns**.

A **Case Process Template** answers two questions:

1. **Which cases does this apply to?** — a set of match rules (category, priority, customer segment,
   channel, value thresholds, and so on) evaluated against the case.
2. **What happens to those cases?** — applied automatically the moment the case is created:
   - the **SLA** (first response and resolution targets),
   - the **Business Process Flow** to run, and which stage to start in,
   - an **outcome-driven task graph** — the tasks to create, in what order, owned by which team or user, each with its own SLA,
   - the **document packages** that must be collected, with mandatory flags and due dates.

The distinguishing idea is the **outcome-driven task graph**. A task is not just an item on a
checklist — it publishes a set of possible outcomes ("Approved", "Rejected", "More information
needed", "Escalate to credit committee"). When an agent records an outcome, the engine decides
what happens next: which task to create, who owns it, whether to advance the business process flow
stage, whether to request additional documents. The same starting case can follow completely
different paths depending on what actually happens — and every one of those paths is configuration,
not code.

Business users build these processes in a **drag-and-drop visual designer**, or simply **describe
the process to Copilot in natural language** and have it generated for them.

---

## Screenshots

### Visual process designer

Business users lay out the task graph directly. Tasks are circular nodes carrying their SLA in the
centre; connectors are labelled with the outcome that triggers them; swimlanes map tasks onto
business process flow stages and stretch to fit their contents.

![Visual process designer showing an outcome-driven task graph with swimlanes per business process flow stage](docs/images/designer.png)

### Authoring a process with Copilot

Describe the process in plain language and have the template, task graph, owners, SLAs and document
requirements generated — then refine them in the designer.

![Copilot authoring panel generating a case process from a natural language description](docs/images/copilot-authoring.png)

### Runtime — case process progress

On the case form, agents see the live task graph: current stage, what is open, what is overdue, and
the outcomes available on each task. Recording an outcome drives the next step.

![Case form showing the case process progress widget with tasks, stages and outcomes](docs/images/case-process.png)

### Runtime — required documents

The second tab of the same panel tracks the document package: what is mandatory, what has been
received, what is outstanding and when it is due.

![Case form showing the required documents tab with mandatory and received document tracking](docs/images/case-documents.png)

### My work dashboard

A combined personal and team workload view with interactive, cross-filtering charts. Click a
doughnut slice, an owner bar or a category bar to filter the task and case lists beneath.

![My work dashboard with urgency doughnut, workload by owner and cases by category charts above filtered task and case lists](docs/images/dashboard.png)

---

## Main capabilities

### Configuration — owned by the business

| Capability | What it gives you |
|---|---|
| **Case process templates** | A single record defining targeting plus everything applied at runtime. Versioned, activatable, and orderable by priority when several could match. |
| **Match rule builder** | Compose targeting conditions over case fields — category, priority, origin, customer segment, value thresholds — with AND/OR grouping. Test rules against real cases before activating. |
| **Visual task designer** | Drag-and-drop authoring of the outcome-driven task graph. Circular task nodes with inline SLA, labelled outcome connectors, and elastic swimlanes per business process flow stage. |
| **Copilot process authoring** | Describe a process in natural language and have the template, tasks, outcomes, owners, SLAs and document requirements generated for you. |
| **Task outcomes** | Each task publishes its own outcome set. Outcomes drive branching, so one template can express many real-world paths. |
| **Per-task assignment** | Route each task to a specific team, a named user, the case owner, or the case owner's manager. |
| **Per-task SLA** | Each task carries its own due target, independent of the case-level SLA. |
| **Document packages** | Reusable bundles of required documents with mandatory flags, sequence, due offsets and template links. |
| **Business process flow binding** | Bind a template to a BPF and a starting stage; stages advance automatically as outcomes are recorded. |

### Runtime — automatic on case creation

| Capability | What it gives you |
|---|---|
| **Automatic template matching** | On create, the engine evaluates active templates in priority order and applies the first match. No manual selection. |
| **SLA stamping** | First response and resolution targets written to the case from the template. |
| **BPF application** | The bound business process flow is instantiated and set to the configured starting stage. |
| **Outcome-driven task creation** | The initial tasks are created with owners and SLAs. Recording an outcome creates the next task in the graph. |
| **Document requirement generation** | Required document records created from the template's document packages. |
| **Case rollups** | Open/total task counts, received/total document counts and progress maintained on the case for views and dashboards. |

### Agent experience

| Capability | What it gives you |
|---|---|
| **Tabbed case panel** | One space-efficient panel on the case form with tabs for case process and required documents, each showing a live count badge, turning red on overdue or outstanding mandatory items. |
| **Outcome picker** | Record a task outcome from the case, driving the process forward. |
| **My work dashboard** | Personal and team workload in one view, with a team picker and a mine/team/everything scope switch. |
| **Interactive charts** | Task urgency doughnut, workload by owner, and cases by category — all clickable and cross-filtering, with removable filter chips. |
| **Click-through** | Open any task or case directly from the dashboard. |

### Technical

- **10 custom Dataverse tables** — templates, match rules, process tasks, task outcomes, document packages, document items, applied processes, case required documents, plus two generated business process flow entities.
- **6 custom APIs** — `GetCaseView`, `GetProcessGraph`, `SaveProcessGraph`, `GetProcessCatalog`, `TestMatchRules`, `AuthorProcess`.
- **Sandboxed C# plug-in assembly** — the process engine, running in the supported sandbox isolation mode.
- **Model-driven app** with configuration, runtime and setup areas.
- **Web resources** — visual designer, case process widget, required documents widget, tabbed case panel, outcome picker, workload dashboard.
- **Chart.js bundled as a web resource**, not loaded from a CDN, so the dashboard works in locked-down tenants with restricted script origins.
- **Idempotent Python build scripts** — every step can be re-run safely, so the whole solution can be rebuilt from source against a fresh environment.

---

## Installation

Two options — import the solution, or build it from source.

**See [INSTALL.md](INSTALL.md) for full step-by-step instructions**, including prerequisites,
post-import configuration, sample data, verification and uninstall.

Quick summary:

```bash
# Option A — import the packaged solution (fastest)
#   Power Platform admin centre -> Solutions -> Import
#   -> solution/CaseProcessConfigurator_managed.zip
#   Then run the post-import steps in INSTALL.md.

# Option B — build from source against your own environment
az login
export DATAVERSE_URL="https://yourorg.crm.dynamics.com"
cd src
python3 step1_solution.py && python3 step2_tables.py   # ... see INSTALL.md
```

> [!IMPORTANT]
> Installing modifies your environment. It creates tables, registers a plug-in assembly and custom
> APIs, and **edits shared artefacts** — the Case main forms (including all three Customer Service
> form variants), the model-driven app site map, and app components. Use a disposable environment.

---

## Repository layout

```
solution/                 Packaged solution (.zip) — managed and unmanaged
src/                      Build scripts, plug-in source and web resources
  dv.py                   Dataverse Web API helper (reads DATAVERSE_URL)
  step*.py                Idempotent build steps, in order
  plugin/                 C# plug-in and custom API source
  webresources/           Designer, runtime widgets and dashboard
docs/images/              Screenshots
INSTALL.md                Installation, verification and uninstall
DISCLAIMER.md             Full disclaimer — please read before installing
LICENSE                   MIT
```

---

## Licence and disclaimer

Released under the [MIT Licence](LICENSE).

This is an independent personal open-source project. It is **not** a Microsoft product and is not
affiliated with, endorsed by or supported by Microsoft Corporation. Microsoft, Dynamics 365,
Dataverse, Power Platform and Copilot are trademarks of the Microsoft group of companies.

All sample data, template names and scenario content are fictitious and illustrative only. The
banking-oriented examples do not constitute financial, legal, regulatory or compliance advice.

**Please read the full [DISCLAIMER](DISCLAIMER.md) before you install or use this software.**

"""Step 10: splice a 'Case Process' tab into the OOB Case main forms."""
import re
import dv
import step9_forms_views as s9

P = dv.PREFIX
TARGET_FORMS = ["Case for Interactive experience", "Case", "Case for Multisession experience"]
TAB_MARK = "cpc_processtab"


def view_id(entity, name):
    v = dv.find_one("savedqueries", f"returnedtypecode eq '{entity}' and name eq '{name}'", "savedqueryid")
    return "{" + v["savedqueryid"] + "}" if v else None


def rel_name(child, lookup):
    r = dv.get(f"EntityDefinitions(LogicalName='{child}')/ManyToOneRelationships"
               f"?$select=SchemaName,ReferencingAttribute,ReferencedEntity")["value"]
    for x in r:
        if x["ReferencingAttribute"] == lookup:
            return x["SchemaName"]
    return None


def build_tab(m):
    task_view = view_id("task", "Open Activity Associated View") or view_id("task", "My Tasks")
    doc_view = view_id(f"{P}_caserequireddocument", "Active Case Required Documents")
    rel_doc = rel_name(f"{P}_caserequireddocument", f"{P}_case")

    secs = []
    secs.append(s9.section("Applied Process", [
        s9.cell(m, f"{P}_appliedtemplate"),
        s9.cell(m, f"{P}_processappliedon"),
        s9.cell(m, f"{P}_casecategory"),
        s9.cell(m, f"{P}_customersegment"),
        s9.cell(m, f"{P}_processsummary"),
    ]))
    secs.append(s9.section("Service Levels", [
        s9.cell(m, f"{P}_firstresponsedue"),
        s9.cell(m, f"{P}_firstresponsestatus"),
        s9.cell(m, f"{P}_firstresponsewarn"),
        s9.cell(m, f"{P}_resolutiondue"),
        s9.cell(m, f"{P}_resolutionstatus"),
        s9.cell(m, f"{P}_resolutionwarn"),
    ]))
    secs.append(s9.section("Progress", [
        s9.cell(m, f"{P}_tasksopen"),
        s9.cell(m, f"{P}_taskstotal"),
        s9.cell(m, f"{P}_docsreceived"),
        s9.cell(m, f"{P}_docstotal"),
    ]))
    grids = []
    if task_view:
        grids.append(s9.grid_cell("cpc_processtasks", "Process Tasks",
                                  "Incident_Tasks", "task", task_view))
    if doc_view and rel_doc:
        grids.append(s9.grid_cell("cpc_requireddocs", "Required Documents",
                                  rel_doc, f"{P}_caserequireddocument", doc_view))
    if grids:
        secs.append(s9.section("Tasks & Documents", grids, columns=1))

    t = s9.tab("Case Process", secs)
    return t.replace('name="tab_', f'name="{TAB_MARK}_', 1)


def splice(formxml, tab):
    if TAB_MARK in formxml:
        formxml = re.sub(r'<tab name="' + TAB_MARK + r'_.*?</tab>', "", formxml, flags=re.S)
    i = formxml.rindex("</tabs>")
    return formxml[:i] + tab + formxml[i:]


def main():
    m = s9.meta("incident")
    tab = build_tab(m)
    forms = dv.get("systemforms?$select=formid,name,formxml"
                   "&$filter=objecttypecode eq 'incident' and type eq 2")["value"]
    for f in forms:
        if f["name"] not in TARGET_FORMS:
            continue
        xml = splice(f["formxml"], tab)
        dv.patch(f"systemforms({f['formid']})", {"formxml": xml}, solution=True)
        print("  + Case Process tab ->", f["name"])
    dv.publish_all()
    print("done")


if __name__ == "__main__":
    main()

"""Replace the two stacked SLA quick-view timer cards on the Case form with the
Modern SLA Timer PCF (mcsla_ModernSlaTimer.ModernSlaTimerControl) bound to a
single SLA KPI Instances subgrid.

Why: the OOB Case form renders SLA KPIs as two quick-view forms
(firstresponsebykpiid / resolvebykpiid), each a large bordered card stacked
vertically. There is no supported "compact" mode for them. The PCF renders all
KPI instances as compact donut cards in one grid, reclaiming most of the height.

A PCF dataset binding lives in the form-level <controlDescriptions> block keyed
by the cell control's uniqueid -- NOT inline on the <control> element.
"""
import re
import uuid

import dv

FORM_NAME = "Case for Interactive experience"
PCF = "mcsla_ModernSlaTimer.ModernSlaTimerControl"
SUBGRID_CLASSID = "{E7A81278-8635-4d9e-8D4D-59480B391C5B}"
VIEW_NAME = "Modern SLA Timer Source"

# Columns the PCF reads in _extractKpis(). The OOB "SLA KPI Instances List View"
# omits pausedon / terminalstatereached, so paused and closed KPIs would render
# incorrectly. applicablefromvalue is enriched by the control over the Web API
# but including it here avoids that extra round trip.
ATTRS = [
    "name", "status", "failuretime", "warningtime", "succeededon",
    "applicablefromvalue", "pausedon", "terminalstatereached",
    "createdon", "slakpiinstanceid", "regardingentityid",
]


def ensure_view() -> str:
    existing = dv.find_one("savedqueries",
                           f"name eq '{VIEW_NAME}' and returnedtypecode eq 'slakpiinstance'",
                           "savedqueryid,name")
    fetch = ("<fetch version='1.0' output-format='xml-platform' mapping='logical'>"
             "<entity name='slakpiinstance'>"
             + "".join(f"<attribute name='{a}' />" for a in ATTRS)
             + "<order attribute='name' descending='false' />"
             "</entity></fetch>")
    layout = ("<grid name='resultset' object='9752' jump='name' select='1' icon='1' preview='1'>"
              "<row name='result' id='slakpiinstanceid'>"
              "<cell name='name' width='150' /><cell name='status' width='120' />"
              "<cell name='failuretime' width='125' /><cell name='warningtime' width='125' />"
              "</row></grid>")
    body = {"name": VIEW_NAME, "fetchxml": fetch, "layoutxml": layout}
    if existing:
        vid = existing["savedqueryid"]
        dv.patch(f"savedqueries({vid})", body, solution=True)
        print("  ~ view", vid)
    else:
        body |= {"returnedtypecode": "slakpiinstance", "querytype": 0,
                 "description": "Feeds the Modern SLA Timer PCF on the case form."}
        vid = dv.new_id(dv.post("savedqueries", body, solution=True))
        print("  + view", vid)
    return vid


def subgrid_params(view_id: str) -> str:
    return (f"<ViewId>{{{view_id.upper()}}}</ViewId><IsUserView>false</IsUserView>"
            "<RelationshipName>slakpiinstance_incident</RelationshipName>"
            "<TargetEntityType>slakpiinstance</TargetEntityType>"
            "<AutoExpand>Fixed</AutoExpand><EnableQuickFind>false</EnableQuickFind>"
            "<EnableViewPicker>false</EnableViewPicker><EnableJumpBar>false</EnableJumpBar>"
            "<ChartGridMode>Grid</ChartGridMode><VisualizationId /><IsUserChart>false</IsUserChart>"
            "<EnableChartPicker>false</EnableChartPicker><RecordsPerPage>10</RecordsPerPage>"
            "<EnableContextualActions>false</EnableContextualActions>")


def main() -> None:
    form = dv.find_one("systemforms", f"name eq '{FORM_NAME}' and type eq 2",
                       "formid,name,formxml")
    if not form:
        raise SystemExit(f"form not found: {FORM_NAME}")
    x = form["formxml"]
    print(f"form {form['formid']}  {len(x)} chars")

    view_id = ensure_view()
    uid = "{" + str(uuid.uuid4()).upper() + "}"
    cell_id = "{" + str(uuid.uuid4()).lower() + "}"

    # 1. Swap the two quick-view rows for a single subgrid cell.
    i = x.find('<section name="SLAKPI_Timer_Section"')
    if i == -1:
        raise SystemExit("SLAKPI_Timer_Section not found")
    j = x.find("</section>", i) + len("</section>")
    section = x[i:j]
    if "FirstResponseByKPI" not in section:
        print("  ! already rewired, skipping section swap")
        new_section = section
    else:
        rows_start = section.find("<rows>")
        rows_end = section.find("</rows>") + len("</rows>")
        new_rows = (
            "<rows><row>"
            f'<cell id="{cell_id}" showlabel="false" colspan="1" auto="false" rowspan="6">'
            '<labels><label description="SLA" languagecode="1033" /></labels>'
            f'<control id="ModernSlaTimerGrid" classid="{SUBGRID_CLASSID}" '
            f'indicationOfSubgrid="true" uniqueid="{uid}">'
            f"<parameters>{subgrid_params(view_id)}</parameters>"
            "</control></cell></row>"
            "<row /><row /><row /><row /><row /></rows>"
        )
        new_section = section[:rows_start] + new_rows + section[rows_end:]
    x = x[:i] + new_section + x[j:]

    # 2. Register the PCF binding for every form factor (0=web, 1=tablet, 2=phone).
    ff = "".join(
        f'<customControl formFactor="{n}" name="{PCF}"><parameters>'
        f'<data-set name="dataSetGrid_1"><ViewId>{{{view_id.upper()}}}</ViewId>'
        "<IsUserView>false</IsUserView>"
        "<RelationshipName>slakpiinstance_incident</RelationshipName>"
        "<TargetEntityType>slakpiinstance</TargetEntityType></data-set>"
        '<Update_Frequency static="true" type="Enum">10</Update_Frequency>'
        '<EnableNegativeTimer static="true" type="Enum">1</EnableNegativeTimer>'
        "</parameters></customControl>"
        for n in (0, 1, 2)
    )
    desc = (f'<controlDescription forControl="{uid}">'
            f'<customControl id="{SUBGRID_CLASSID}">'
            f"<parameters>{subgrid_params(view_id)}</parameters></customControl>"
            f"{ff}</controlDescription>")

    x = re.sub(r"<controlDescriptions\s*/>", "<controlDescriptions></controlDescriptions>", x)
    if "<controlDescriptions>" in x:
        x = x.replace("<controlDescriptions>", "<controlDescriptions>" + desc, 1)
    else:
        x = x.replace("</form>", f"<controlDescriptions>{desc}</controlDescriptions></form>", 1)

    dv.patch(f"systemforms({form['formid']})", {"formxml": x}, solution=True)
    print("  ~ formxml written", len(x), "chars")

    dv.post("PublishXml", {"ParameterXml":
        f"<importexportxml><entities><entity>incident</entity></entities></importexportxml>"})
    print("published")


if __name__ == "__main__":
    main()

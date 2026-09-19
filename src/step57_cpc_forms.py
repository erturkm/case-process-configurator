"""Step 57: give CPC its own Case and Task main forms.

Why this exists
---------------
CPC used to splice its sections straight into Microsoft's own Case and Task forms. A system
form is an atomic solution component, so that meant CPC shipped whole copies of Microsoft's
forms -- six of them -- and stamped over whatever the customer already had there on import.
It also pulled every control on those forms in as a dependency.

That is not theoretical. Microsoft's Case form in the authoring org carries Field Service
and Connected Field Service content: the msdyn_/Case/Case.Library.js and
msdyn_/CFS/Case/CaseForm.js libraries, a work order navigation item, and the
msdyn_functionallocation / msdyn_incidenttype / msdyn_iotalert fields. None of those exist
in a plain Customer Service org, so shipping that form hands the customer a broken one.

This step forks each form into one CPC owns outright, under its own formid and name. The
Microsoft originals are left untouched, and step58 drops them from the solution so import
never goes near them again.

Two accelerators share this authoring org. The Sales Process Configurator adds its own
sections to the same Task form, so forking blind would ship spc_ content inside CPC. The
sweep below removes it, which is why CPC's package is clean of spc_ and SPC's is clean of
cpc_.

Run after step18 (case widgets), step17 (outcome picker) and step51 (task SLA timer): those
steps still build the CPC sections, this one copies the result onto a form CPC owns.
"""
import re
import uuid

import dv

P = dv.PREFIX

# Simple lookup control. Same classid Microsoft uses for parentcontactid/transactioncurrencyid.
LOOKUP_CLASSID = "{270BD3DB-D9AF-4782-9025-509E298DEC0A}"
# Fixed namespace so generated cell/control ids are reproducible across runs and orgs.
FORM_NS = uuid.UUID("6f0d3f2e-9b1a-4c77-9f53-2a6d4b8e0c11")

# One fork per entity, by design: source form name -> CPC-owned form name.
FORKS = [
    ("incident", "Case", f"Case ({P.upper()})"),
    ("task", "Task", f"Task ({P.upper()})"),
]

# Proof that the source form really carries SPC content before we bother cloning it.
MARKERS = {
    # step18 consolidated the process and documents widgets into one panel; SEC_PROCESS and
    # SEC_DOCS survive in that step only to clean up forms authored by older builds.
    "incident": (f"{P}_summary_panel",),
    "task": (f"{P}_tasksla_sec", f"{P}_outcome_sec"),
}

GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

# Other solutions add their own sections to the same Microsoft forms -- in this org the Sales
# Process Configurator puts its own on every Task form. Forking blind copies them onto CPC's
# form and ships them, which is the contamination this step exists to end.
#
# Which prefixes count as foreign is read from the org's publishers rather than guessed, so
# this works in any org. Two things are deliberately kept:
#   - Microsoft's own product prefixes. The form is built on Customer Service and is meant to
#     keep its fields; stripping them would hand the user a crippled form.
#   - the Modern SLA Timer PCF prefix, which CPC genuinely depends on.
KEEP_PREFIXES = {"msdyn", "msdynce", "msdynmkt", "msa", "msfp", "adx", "mcsla"}

# ...except these. They come from first-party apps SPC does not require -- Field Service in
# particular -- and a fork that carries them refuses to install anywhere that app is absent.
# Matched as whole schema names, and as the library/handler paths that reference them.
# Verified absent from a plain Customer Service org (cascadedemo1), which is what makes them
# import-blocking rather than merely untidy.
DROP_NAMES = {
    "msdyn_functionallocation",
    "msdyn_incidenttype",
    "msdyn_iotalert",
    "nav_msdyn_incident_msdyn_workorder_ServiceRequest",
}
DROP_LIBRARIES = (
    "msdyn_/Case/Case.Library.js",
    "msdyn_/CFS/Case/CaseForm.js",
    "msdyn_/CFS/Utils/RibbonUtils.js",
)

# Fields CPC wants on its own form that Microsoft's original does not place. Microsoft's Case
# form already carries customerid ("Customer") and subjectid, which are the two the match
# engine addresses most, so there is nothing to add here today. The machinery is kept because
# the targeting model is metadata-driven and may grow.
ADD_FIELDS = {}


def _stable_guid(seed):
    """Deterministic id so re-running the fork does not churn the form xml."""
    return "{%s}" % str(uuid.uuid5(FORM_NS, seed)).upper()


def add_fields(xml, entity):
    """Place CPC's required fields in a named section, after the section's first row."""
    added = []
    for section, field, caption, classid in ADD_FIELDS.get(entity, []):
        if f'datafieldname="{field}"' in xml:
            continue
        m = re.search(r'<section\b[^>]*name="%s".*?</section>' % re.escape(section), xml, re.S)
        if not m:
            print(f"    ! section {section} not found - cannot place {field}")
            continue
        block = m.group(0)
        rows = re.search(r"<rows>(.*)</rows>", block, re.S)
        if not rows:
            print(f"    ! section {section} has no rows - cannot place {field}")
            continue
        cell = _stable_guid(f"{entity}/{section}/{field}/cell")
        uid = _stable_guid(f"{entity}/{section}/{field}/control")
        row = (f'<row><cell id="{cell}" showlabel="true" locklevel="0">'
               f'<labels><label description="{caption}" languagecode="1033" /></labels>'
               f'<control id="{field}" classid="{classid}" datafieldname="{field}" '
               f'uniqueid="{uid}" disabled="false" /></cell></row>')
        # After the first row: the section leads with Topic, and these two identify the deal.
        first = re.search(r"<row\b.*?</row>", rows.group(1), re.S)
        inner = rows.group(1)
        inner = (inner[: first.end()] + row + inner[first.end():]) if first else (row + inner)
        xml = xml.replace(block, re.sub(r"<rows>.*</rows>", lambda _: f"<rows>{inner}</rows>",
                                        block, count=1, flags=re.S), 1)
        added.append(field)
    return xml, added


def foreign_prefixes():
    """Publisher prefixes belonging to somebody else's customizations."""
    rows = dv.get("publishers?$select=customizationprefix&$top=200")["value"]
    found = {(r.get("customizationprefix") or "").lower() for r in rows}
    return {p for p in found if p and p != P and p not in KEEP_PREFIXES}


def strip_foreign(xml, prefixes):
    """Remove another publisher's content from the fork, and nothing else.

    Granularity matters here. An earlier cut of this dropped any SECTION that contained a
    foreign field, which quietly deleted Microsoft's own opportunity_information section --
    account, contact, budget, currency, purchase timeframe -- because Field Service had
    added one field to it. So: foreign ROWS go, and a section only goes if the section
    itself belongs to another publisher or is left with nothing in it.
    """
    if not prefixes:
        return xml, []
    alt = "|".join(sorted(re.escape(p) for p in prefixes))
    named = "|".join(sorted(re.escape(n) for n in DROP_NAMES))
    foreign_field = re.compile(rf'\bdatafieldname="((?:(?:{alt})_\w+)|(?:{named}))"')
    foreign_name = re.compile(rf'\bname="((?:(?:{alt})_\w+)|(?:{named}))"')
    ours = re.compile(rf'\b(?:name|datafieldname)="{re.escape(P)}_\w+"')
    dropped = set()

    def drop_rows(text):
        out, pos = [], 0
        for m in re.finditer(r'<row>(?:(?!</row>).)*?</row>', text, re.S):
            names = foreign_field.findall(m.group(0)) or foreign_name.findall(m.group(0))
            if names and not ours.search(m.group(0)):
                dropped.update(names)
                out.append(text[pos:m.start()])
                pos = m.end()
        out.append(text[pos:])
        return "".join(out)

    def drop_sections(text):
        out, pos = [], 0
        for m in re.finditer(r'<section\b(?:(?!</section>).)*?</section>', text, re.S):
            block = m.group(0)
            if ours.search(block):
                continue
            own_name = re.search(r'<section\b[^>]*\bname="([^"]*)"', block)
            label = own_name.group(1) if own_name else "unnamed"
            is_foreign = bool(foreign_name.search(f'name="{label}"'))
            is_empty = "<control " not in block and "<control>" not in block
            if is_foreign or is_empty:
                if is_foreign:
                    dropped.add(label)
                out.append(text[pos:m.start()])
                pos = m.end()
        out.append(text[pos:])
        return "".join(out)

    xml = drop_rows(xml)
    xml = drop_sections(xml)
    xml, tabs = drop_empty_tabs(xml)
    xml, nav = drop_related_nav(xml)
    xml, libs = drop_libraries(xml)
    xml, events = drop_orphan_events(xml)
    xml, orphans = drop_orphan_descriptions(xml)
    return xml, sorted(dropped) + tabs + nav + libs + events + orphans


def drop_empty_tabs(xml):
    """Drop tabs left with no controls once another app's content has been stripped.

    Removing Field Service's fields empties its tab but leaves the labelled shell behind, so
    the form still shows a "Field Service" heading with nothing under it. A tab with no
    <control> is dead weight on a case form.
    """
    gone = []

    def keep(m):
        block = m.group(0)
        if "<control " in block or "<control>" in block:
            return block
        name = re.search(r'<tab name="([^"]*)"', block)
        gone.append(name.group(1) if name else "unnamed")
        return ""

    xml = re.sub(r'<tab\b(?:(?!</tab>).)*?</tab>', keep, xml, flags=re.S)
    return xml, [f"empty tab: {t}" for t in gone]


def drop_related_nav(xml):
    """Strip the legacy related-records navigation pane.

    Each <NavBarByRelationshipItem> is a hard dependency on that relationship, and the OOB
    Case form carries entries for every app installed in the authoring org -- Field Service
    work orders among them. The modern app navigates by the Related tab instead, so dropping
    the whole pane costs nothing and keeps CPC's form dependent on Customer Service alone.
    """
    n = len(re.findall(r'<NavBarByRelationshipItem\b', xml))
    if not n:
        return xml, []
    xml = re.sub(r'<NavBarByRelationshipItem\b.*?</NavBarByRelationshipItem>', "", xml, flags=re.S)
    xml = re.sub(r'<NavBarByRelationshipItem\b[^>]*/>', "", xml)
    return xml, [f"related-records nav x{n}"]


def drop_libraries(xml):
    """Unhook form libraries and their event handlers for apps CPC does not require.

    A <formLibrary> entry is a hard dependency on that web resource. Field Service and
    Connected Field Service libraries are referenced by the OOB Case form and would block
    install anywhere those apps are absent -- all three are missing from a plain Customer
    Service org -- so the libraries and every handler calling into them are removed.

    A library is named two ways on the same form: bare, and prefixed "$webresource:" when a
    handler resolves it dynamically. Matching only the bare form leaves the $webresource:
    reference behind, and that reference is itself the import dependency.
    """
    gone = []
    for lib in DROP_LIBRARIES:
        if lib not in xml:
            continue
        for name in (lib, f"$webresource:{lib}"):
            ids = set(re.findall(rf'<Library\b[^>]*\bname="{re.escape(name)}"[^>]*\blibraryUniqueId='
                                 rf'"\{{?({GUID})\}}?"', xml, re.I))
            ids |= set(re.findall(rf'<Library\b[^>]*\blibraryUniqueId="\{{?({GUID})\}}?"'
                                  rf'[^>]*\bname="{re.escape(name)}"', xml, re.I))
            xml = re.sub(rf'<Library\b[^>]*\bname="{re.escape(name)}"[^>]*/>', "", xml, flags=re.I)
            for uid in ids:
                xml = re.sub(rf'<Handler\b[^>]*\blibraryUniqueId="\{{?{re.escape(uid)}\}}?"[^>]*/>',
                             "", xml, flags=re.I)
            xml = re.sub(rf'<Handler\b[^>]*\blibraryName="{re.escape(name)}"[^>]*/>',
                         "", xml, flags=re.I)
            xml = re.sub(rf'<Handler\b[^>]*\bfunctionName="[^"]*"[^>]*\blibraryName='
                         rf'"{re.escape(name)}"[^>]*/>', "", xml, flags=re.I)
        gone.append(lib)
    xml = re.sub(r'<Handlers>\s*</Handlers>', "", xml)
    xml = re.sub(r'<Libraries>\s*</Libraries>', "", xml)
    xml = re.sub(r'<events>\s*</events>', "", xml)
    return xml, gone


def drop_orphan_events(xml):
    """Remove <event> bindings whose attribute is no longer on the form.

    An onchange event names the attribute it fires for, and that name is a dependency in its
    own right -- independent of whether the field is still placed. Dropping Field Service's
    fields leaves <event attribute="msdyn_incidenttype"> behind, which alone is enough to
    make the form claim Field Service. Any event whose attribute is not on the form is dead
    by definition, so this is safe in general rather than a special case.
    """
    live = set(re.findall(r'datafieldname="([^"]+)"', xml))
    gone = []

    def keep(m):
        attr = m.group(1)
        if attr in live:
            return m.group(0)
        gone.append(attr)
        return ""

    xml = re.sub(r'<event\b[^>]*\battribute="([^"]+)"[^>]*>'
                 r'(?:(?!</event>).)*?</event>', keep, xml, flags=re.S)
    xml = re.sub(r'<event\b[^>]*\battribute="([^"]+)"[^>]*/>', keep, xml)
    return xml, [f"orphan event: {a}" for a in sorted(set(gone))]


def drop_orphan_descriptions(xml):
    """Remove <controlDescription> blocks whose control is no longer on the form.

    controlDescriptions live in their own block at the end of the form and bind back to a
    control by uniqueid. Deleting a section leaves its descriptions behind, still naming the
    other publisher's view and PCF -- which then import as missing dependencies even though
    nothing visible references them. This is what made the first fork drag a foreign view in.
    """
    live = set(re.findall(rf'<control\b[^>]*\buniqueid="\{{?({GUID})\}}?"', xml, re.I))
    live = {g.lower() for g in live}
    orphans = []

    def keep(m):
        ref = m.group(1).lower()
        if ref in live:
            return m.group(0)
        orphans.append(ref)
        return ""

    xml = re.sub(rf'<controlDescription\b[^>]*\bforControl="\{{?({GUID})\}}?"'
                 r'(?:(?!</controlDescription>).)*?</controlDescription>',
                 keep, xml, flags=re.S | re.I)
    xml = re.sub(r'<controlDescriptions>\s*</controlDescriptions>', "", xml)
    return xml, [f"orphan controlDescription x{len(orphans)}"] if orphans else []


def main_forms(entity):
    return dv.get("systemforms?$select=formid,name,formxml,formactivationstate,"
                  f"formpresentation&$filter=objecttypecode eq '{entity}' and type eq 2")["value"]


def find(forms, name):
    for f in forms:
        if f["name"] == name:
            return f
    return None


# Attributes whose guids are internal to one form and safe to renumber. They cross-reference
# each other -- <controlDescription forControl=".."> has to keep matching its control's
# uniqueid -- so they all share one map. classid is deliberately absent: it names the control
# type. So are handlerUniqueId and libraryUniqueId, which tie form events to <formLibraries>.
RETAG_ATTRS = ("id", "uniqueid", "forControl", "labelid")

# ...and inside these elements even id= names a control type rather than a form node, so the
# whole element is left alone. Renaming <customControl id=".."> silently breaks the form.
RETAG_SKIP_TAGS = ("customControl",)


def retag(xml):
    """Renumber the form's internal guids, keeping every cross-reference consistent.

    Dataverse does accept a byte-for-byte clone, but then two forms claim the same control
    ids. Renumbering keeps the fork independent, the way the designer's own Save As does.
    """
    seen = {}
    attr_re = re.compile(rf'\b({"|".join(RETAG_ATTRS)})="(\{{)?({GUID})(\}})?"')

    def swap(m):
        attr, brace_l, guid, brace_r = m.group(1), m.group(2) or "", m.group(3), m.group(4) or ""
        new = seen.setdefault(guid.lower(), str(uuid.uuid4()))
        if brace_l:
            new = new.upper()
        return f'{attr}="{brace_l}{new}{brace_r}"'

    def per_tag(m):
        tag = m.group(0)
        if m.group(1) in RETAG_SKIP_TAGS:
            return tag
        return attr_re.sub(swap, tag)

    return re.sub(r'<([A-Za-z_][\w:.-]*)\b[^>]*>', per_tag, xml)


def fork(entity, source_name, target_name, prefixes):
    forms = main_forms(entity)
    src = find(forms, source_name)
    if not src:
        print(f"  ! source form not found: {entity}/{source_name}")
        return None

    missing = [m for m in MARKERS[entity] if m not in (src["formxml"] or "")]
    if missing:
        print(f"  ! {source_name} is missing {missing} - run step17/step18/step51 first")
        return None

    xml = retag(src["formxml"])
    xml, dropped = strip_foreign(xml, prefixes)
    if dropped:
        print(f"    dropped from the fork (another publisher's): {', '.join(dropped)}")
    # After the sweep, so CPC's own additions can never be caught by it.
    xml, added = add_fields(xml, entity)
    if added:
        print(f"    added to the fork: {', '.join(added)}")

    existing = find(forms, target_name)
    if existing:
        dv.patch(f"systemforms({existing['formid']})", {"formxml": xml}, solution=True)
        print(f"  ~ refreshed {target_name}  ({existing['formid']})")
        return existing["formid"]

    fid = dv.new_id(dv.post("systemforms", {
        "name": target_name,
        "description": ("Main form owned by the Case Process Configurator. Forked from "
                        f"'{source_name}' so installing CPC never overwrites it."),
        "objecttypecode": entity,
        "type": 2,
        "formxml": xml,
        "formpresentation": src.get("formpresentation") or 1,
        "formactivationstate": 1,
    }, solution=True))
    print(f"  + created {target_name}  ({fid})")
    return fid


def main():
    prefixes = foreign_prefixes()
    print("foreign publisher prefixes in this org:", ", ".join(sorted(prefixes)) or "none")
    made = {}
    for entity, source, target in FORKS:
        fid = fork(entity, source, target, prefixes)
        if fid:
            made[entity] = fid
    # Scoped publish: an org-wide publish here takes long enough to time out the client, and
    # only these two entities changed.
    dv.post("PublishXml", {"ParameterXml":
                           "<importexportxml><entities>"
                           + "".join(f"<entity>{e}</entity>" for e, _, _ in FORKS)
                           + "</entities></importexportxml>"})
    print("\nCPC-owned forms:")
    for entity, fid in made.items():
        print(f"  {entity:12} {fid}")
    print("done")
    return made


if __name__ == "__main__":
    main()

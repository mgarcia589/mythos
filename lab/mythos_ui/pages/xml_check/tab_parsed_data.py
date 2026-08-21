"""Parsed Data tab — Table View, Form View, and Raw XML View."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.parse_service import get_display_name, FORM_DISPLAY_NAMES


def render_parsed_data(t: dict, s):
    """Render the Parsed Data tab."""
    xc = s.xml_check

    if not s.parser:
        _render_no_data(t)
        return

    # Form/schedule selector + view mode toggle
    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        # Left: form selector
        with ui.row().classes("items-center gap-3"):
            available_forms = _get_available_forms(s)
            current_form = xc.selected_form or (available_forms[0] if available_forms else None)

            if available_forms:
                ui.select(
                    options={f: get_display_name(f) for f in available_forms},
                    value=current_form,
                    on_change=lambda e: _select_form(e.value),
                ).classes("w-80").props("dense outlined").style("font-size: 0.75rem;")

        # Right: view mode toggle
        with ui.row().classes("items-center gap-1"):
            for mode, icon, label in [
                ("table", "table_chart", "Table"),
                ("form", "list_alt", "Form"),
                ("raw", "code", "Raw XML"),
            ]:
                is_active = xc.view_mode == mode
                ui.button(label, icon=icon,
                          on_click=lambda _, m=mode: _switch_view(m)) \
                    .props("flat dense no-caps size=sm") \
                    .style(
                        f"color: {t['accent'] if is_active else t['text_muted']}; "
                        f"background: {t['nav_active_bg'] if is_active else 'transparent'}; "
                        f"font-size: 0.65rem; padding: 4px 10px; border-radius: 6px;"
                    )

    # Content based on view mode
    if not current_form:
        _render_no_data(t)
        return

    # Store selected form for future renders
    if xc.selected_form != current_form:
        xc.selected_form = current_form

    match xc.view_mode:
        case "table":
            _render_table_view(t, s, current_form)
        case "form":
            _render_form_view(t, s, current_form)
        case "raw":
            _render_raw_view(t, s, current_form)


def _get_available_forms(s) -> list[str]:
    """Get list of forms available in the parsed data."""
    if not s.parser:
        return []

    xc = s.xml_check
    if xc.parse_summary and xc.parse_summary.schedule_inventory:
        forms = []
        for top_node in xc.parse_summary.schedule_inventory:
            for child in top_node.children:
                forms.append(child.form_name)
        return forms

    # Fallback: detect from parser
    form_types = s.parser.detect_forms()
    forms = []
    if "5471" in form_types:
        for key in ["IRS5471ScheduleH", "IRS5471ScheduleI1", "IRS5471ScheduleC",
                    "IRS5471ScheduleF", "IRS5471ScheduleE", "IRS5471ScheduleJ",
                    "IRS5471ScheduleG", "IRS5471ScheduleM", "IRS5471ScheduleO"]:
            forms.append(key)
    if "8858" in form_types:
        for key in ["IRS8858ScheduleC", "IRS8858ScheduleF", "IRS8858ScheduleH"]:
            forms.append(key)
    return forms


# ─── TABLE VIEW ────────────────────────────────────────────────────────────

def _render_table_view(t: dict, s, form_name: str):
    """Flat table view of form data — one row per entity."""
    import pandas as pd

    try:
        if "8858" in form_name:
            df = s.parser.extract_form_8858(form_name)
        else:
            df = s.parser.extract_form(form_name)
    except Exception as ex:
        _render_error(t, f"Failed to extract {form_name}: {ex}")
        return

    if df is None or df.empty:
        _render_empty_form(t, form_name)
        return

    # Prepare columns — show entity identifier + data columns
    entity_col = "_reference_id" if "_reference_id" in df.columns else df.columns[0]
    name_col = "_entity_name" if "_entity_name" in df.columns else None


    # Stats
    with ui.row().classes("items-center gap-3 mb-3 animate-fade-up stagger-2"):
        ui.label(f"{len(df)} entities").classes("text-xs mythos-mono") \
            .style(f"color: {t['text_muted']};")
        ui.label(f"{len(df.columns)} columns").classes("text-xs mythos-mono") \
            .style(f"color: {t['text_muted']};")
        ui.label(get_display_name(form_name)).classes("text-xs font-semibold") \
            .style(f"color: {t['accent']};")

    # Build table data
    display_cols = [c for c in df.columns if not c.startswith("_")][:20]
    id_cols = [c for c in [entity_col, name_col] if c and c in df.columns]
    show_cols = id_cols + display_cols

    columns = []
    for col in show_cols:
        short_name = col.replace(form_name.replace("IRS", ""), "").replace("5471", "").replace("8858", "")
        if len(short_name) > 30:
            short_name = short_name[:28] + "…"
        columns.append({
            "name": col, "label": short_name, "field": col,
            "align": "left", "sortable": True,
        })

    rows = []
    for i, (_, row) in enumerate(df[show_cols].head(200).iterrows()):
        r = {"_id": i}
        for col in show_cols:
            val = row.get(col, "")
            if pd.isna(val):
                r[col] = "—"
            elif isinstance(val, float):
                r[col] = f"{val:,.2f}" if abs(val) >= 1 else str(val)
            else:
                r[col] = str(val)[:100]
        rows.append(r)

    display_rows = rows

    with ui.card().classes("w-full animate-fade-up stagger-3").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 0; overflow: hidden;"
    ):
        table = ui.table(
            columns=columns, rows=display_rows, row_key="_id",
            pagination={"rowsPerPage": 50},
        ).classes("w-full").props("dense flat bordered separator=cell virtual-scroll")

        table.style(
            f"background: {t['bg_card']}; max-height: 60vh; "
            f"font-size: 0.7rem;")


# ─── FORM VIEW ─────────────────────────────────────────────────────────────

def _render_form_view(t: dict, s, form_name: str):
    """Form-style view — grouped by entity, showing line-by-line fields."""
    import pandas as pd

    try:
        if "8858" in form_name:
            df = s.parser.extract_form_8858(form_name)
        else:
            df = s.parser.extract_form(form_name)
    except Exception:
        _render_empty_form(t, form_name)
        return

    if df is None or df.empty:
        _render_empty_form(t, form_name)
        return

    entity_col = "_reference_id" if "_reference_id" in df.columns else df.columns[0]
    name_col = "_entity_name" if "_entity_name" in df.columns else None

    # Show first 10 entities to avoid overwhelming
    entities_shown = df.head(10)

    for idx, (_, row) in enumerate(entities_shown.iterrows()):
        entity_id = row.get(entity_col, f"Entity {idx}")
        entity_name = row.get(name_col, "") if name_col else ""

        with ui.expansion(
            text=f"{entity_id} — {entity_name}" if entity_name else str(entity_id),
            icon="business",
            value=(idx == 0),
        ).classes("w-full mb-2 animate-fade-up").style(
            f"border: 1px solid {t['border']}30; border-radius: 8px; "
            f"font-size: 0.8rem;"
        ):
            # Field list for this entity
            data_cols = [c for c in df.columns if not c.startswith("_")]
            with ui.column().classes("w-full gap-0"):
                for col in data_cols:
                    val = row.get(col, "")
                    if pd.isna(val) or val == "" or val is None:
                        continue

                    field_display = col.replace(
                        form_name.replace("IRS", ""), ""
                    ).replace("5471", "").replace("8858", "")

                    with ui.row().classes("w-full items-center py-1 gap-2").style(
                        f"border-bottom: 1px solid {t['border']}10; padding: 4px 8px;"
                    ):
                        ui.label(field_display).classes("text-xs flex-1") \
                            .style(f"color: {t['text_secondary']}; max-width: 60%;")
                        val_str = f"{val:,.2f}" if isinstance(val, float) else str(val)
                        ui.label(val_str).classes("text-xs mythos-mono text-right") \
                            .style(f"color: {t['text_primary']};")

    if len(df) > 10:
        ui.label(f"Showing 10 of {len(df)} entities") \
            .classes("text-xs mt-2").style(f"color: {t['text_muted']};")


# ─── RAW XML VIEW ──────────────────────────────────────────────────────────

def _render_raw_view(t: dict, s, form_name: str):
    """Raw XML fragment view with basic highlighting."""
    from lxml import etree

    # Get first entity's XML fragment
    try:
        tree = s.parser._tree
        ns = {"irs": "http://www.irs.gov/efile"}

        # Find the form elements
        tag_name = form_name.replace("IRS", "")
        elements = tree.findall(f".//{{{ns['irs']}}}{tag_name}") or \
                   tree.findall(f".//{tag_name}")

        if not elements:
            # Try without namespace
            all_elements = tree.iter()
            elements = [el for el in all_elements if tag_name in (el.tag.split("}")[-1] if "}" in el.tag else el.tag)]

        if not elements:
            _render_empty_form(t, form_name)
            return

        target = elements[0]

        xml_text = etree.tostring(target, pretty_print=True, encoding="unicode")

        # Truncate if too long
        if len(xml_text) > 15000:
            xml_text = xml_text[:15000] + "\n\n<!-- ... truncated (showing first 15KB) -->"

    except Exception as ex:
        xml_text = f"<!-- Error extracting XML: {ex} -->"

    with ui.card().classes("w-full animate-fade-up stagger-2").style(
        f"background: {t['bg_main']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px; overflow: hidden;"
    ):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("code").style(f"color: {t['text_muted']}; font-size: 0.9rem;")
            ui.label(f"Raw XML — {get_display_name(form_name)}") \
                .classes("text-xs font-semibold") \
                .style(f"color: {t['text_muted']};")

            ui.button("Copy", icon="content_copy",
                      on_click=lambda: ui.run_javascript(
                          f'navigator.clipboard.writeText({repr(xml_text[:5000])})'
                      )).props("flat dense no-caps size=xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")

        ui.code(xml_text, language="xml").classes("w-full") \
            .style(f"max-height: 55vh; overflow-y: auto; font-size: 0.65rem; "
                   f"border-radius: 8px;")


# ─── EMPTY STATES ──────────────────────────────────────────────────────────

def _render_no_data(t: dict):
    """No parser available."""
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("grid_on").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No parsed data available").classes("text-sm") \
            .style(f"color: {t['text_muted']};")
        ui.label("Run a parse or review first").classes("text-xs") \
            .style(f"color: {t['text_muted']}; opacity: 0.6;")


def _render_empty_form(t: dict, form_name: str):
    """Form exists but has no data."""
    with ui.column().classes("w-full items-center py-8 gap-3"):
        ui.icon("inbox").classes("text-3xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label(f"{get_display_name(form_name)}").classes("text-sm font-semibold") \
            .style(f"color: {t['text_muted']};")
        ui.label("No records found for this form/schedule") \
            .classes("text-xs").style(f"color: {t['text_muted']}; opacity: 0.6;")


def _render_error(t: dict, msg: str):
    """Error extracting data."""
    with ui.column().classes("w-full items-center py-8 gap-3"):
        ui.icon("error_outline").classes("text-3xl") \
            .style(f"color: {t['sev_high']}; opacity: 0.6;")
        ui.label(msg).classes("text-xs") \
            .style(f"color: {t['sev_high']};")


# ─── HANDLERS ──────────────────────────────────────────────────────────────

def _select_form(form_name: str):
    """Change selected form."""
    s = get_state()
    s.xml_check.selected_form = form_name
    ui.navigate.to("/review")


def _switch_view(mode: str):
    """Switch between table/form/raw view."""
    s = get_state()
    s.xml_check.view_mode = mode
    ui.navigate.to("/review")

"""Export dialog — scope selector, format picker, content preview."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.theme import get_theme


EXPORT_FORMATS = [
    {"value": "excel", "label": "Excel (.xlsx)", "icon": "table_view"},
    {"value": "csv", "label": "CSV (.csv)", "icon": "view_list"},
    {"value": "json", "label": "JSON (.json)", "icon": "data_object"},
    {"value": "pdf", "label": "PDF Report (.pdf)", "icon": "picture_as_pdf"},
]

EXPORT_SCOPES = [
    {"value": "all", "label": "All Parsed Data", "desc": "Every form and schedule"},
    {"value": "current_view", "label": "Current View", "desc": "What's visible in Parsed Data tab"},
    {"value": "selected_forms", "label": "Selected Forms", "desc": "Choose specific forms"},
    {"value": "issues_only", "label": "Issues Only", "desc": "Review findings export"},
    {"value": "rollover_only", "label": "Rollover Results", "desc": "PY vs CY comparison"},
]


def show_export_dialog():
    """Show the export configuration dialog."""
    t = get_theme()
    s = get_state()
    xc = s.xml_check

    # Dialog state
    state = {
        "format": "excel",
        "scope": "all",
        "include_metadata": True,
        "include_summary": True,
        "include_raw": False,
        "selected_forms": set(),
    }

    with ui.dialog().props("persistent maximized=false") as dialog, \
         ui.card().classes("w-[520px] max-h-[80vh]").style(
             f"background: {t['bg_card']}; border: 1px solid {t['border']}60; "
             f"border-radius: 12px; padding: 0; overflow: hidden;"
         ):

        # Header
        with ui.row().classes("w-full items-center justify-between px-5 pt-4 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("download").style(f"color: {t['accent']}; font-size: 1.1rem;")
                ui.label("Export Data").classes("text-sm font-semibold") \
                    .style(f"color: {t['text_primary']};")
            ui.button(icon="close", on_click=dialog.close) \
                .props("flat dense round size=sm") \
                .style(f"color: {t['text_muted']};")

        ui.separator().style(f"background: {t['border']}30;")

        # Body (scrollable)
        with ui.scroll_area().classes("w-full px-5 py-3").style("max-height: 55vh;"):

            # Scope selection
            ui.label("EXPORT SCOPE").classes("text-xs font-semibold mb-2") \
                .style(f"color: {t['text_muted']}; letter-spacing: 0.05em; font-size: 0.6rem;")

            scope_group = ui.radio(
                options={s["value"]: s["label"] for s in EXPORT_SCOPES},
                value=state["scope"],
                on_change=lambda e: _update_state(state, "scope", e.value),
            ).props("dense").classes("mb-4")

            # Form selection (shown only when scope = selected_forms)
            form_container = ui.column().classes("w-full mb-3 pl-6")
            form_container.set_visibility(False)

            with form_container:
                if xc.parse_summary and xc.parse_summary.schedule_inventory:
                    for node in xc.parse_summary.schedule_inventory:
                        for child in node.children:
                            ui.checkbox(
                                child.display_name,
                                value=False,
                                on_change=lambda e, fn=child.form_name: _toggle_form(state, fn, e.value),
                            ).classes("text-xs").style(f"color: {t['text_secondary']};")

            ui.separator().classes("my-3").style(f"background: {t['border']}20;")

            # Format selection
            ui.label("FORMAT").classes("text-xs font-semibold mb-2") \
                .style(f"color: {t['text_muted']}; letter-spacing: 0.05em; font-size: 0.6rem;")

            with ui.row().classes("w-full gap-2 mb-4"):
                for fmt in EXPORT_FORMATS:
                    is_selected = state["format"] == fmt["value"]
                    with ui.card().classes("cursor-pointer flex-1").style(
                        f"background: {t['accent'] + '10' if is_selected else 'transparent'}; "
                        f"border: {'1.5px' if is_selected else '1px'} solid "
                        f"{t['accent'] + '80' if is_selected else t['border'] + '40'}; "
                        f"border-radius: 8px; padding: 10px; text-align: center; "
                        f"min-width: 80px;"
                    ).on("click", lambda _, fv=fmt["value"]: _update_state(state, "format", fv)):
                        ui.icon(fmt["icon"]).classes("text-base mb-1") \
                            .style(f"color: {t['accent'] if is_selected else t['text_muted']};")
                        ui.label(fmt["label"]).classes("text-xs") \
                            .style(f"color: {t['text_primary'] if is_selected else t['text_muted']}; "
                                   f"font-size: 0.6rem;")

            ui.separator().classes("my-3").style(f"background: {t['border']}20;")

            # Content options
            ui.label("INCLUDE").classes("text-xs font-semibold mb-2") \
                .style(f"color: {t['text_muted']}; letter-spacing: 0.05em; font-size: 0.6rem;")

            ui.checkbox("Metadata (client, FY, return type)",
                        value=state["include_metadata"],
                        on_change=lambda e: _update_state(state, "include_metadata", e.value)) \
                .classes("text-xs").style(f"color: {t['text_secondary']};")
            ui.checkbox("Summary sheet / section",
                        value=state["include_summary"],
                        on_change=lambda e: _update_state(state, "include_summary", e.value)) \
                .classes("text-xs").style(f"color: {t['text_secondary']};")
            ui.checkbox("Raw XML values (unformatted)",
                        value=state["include_raw"],
                        on_change=lambda e: _update_state(state, "include_raw", e.value)) \
                .classes("text-xs").style(f"color: {t['text_secondary']};")

            ui.separator().classes("my-3").style(f"background: {t['border']}20;")

            # Preview estimate
            _render_preview(t, s, state)

        # Footer actions
        ui.separator().style(f"background: {t['border']}30;")
        with ui.row().classes("w-full items-center justify-end gap-2 px-5 py-3"):
            ui.button("Cancel", on_click=dialog.close) \
                .props("flat no-caps size=sm") \
                .style(f"color: {t['text_muted']};")
            ui.button("Export", icon="download",
                      on_click=lambda: _execute_export(state, dialog)) \
                .props("no-caps size=sm unelevated") \
                .style(f"background: {t['accent']}; color: white; border-radius: 6px;")

    dialog.open()


def _render_preview(t: dict, s, state: dict):
    """Estimate what will be exported."""
    xc = s.xml_check
    ps = xc.parse_summary

    ui.label("PREVIEW").classes("text-xs font-semibold mb-2") \
        .style(f"color: {t['text_muted']}; letter-spacing: 0.05em; font-size: 0.6rem;")

    with ui.card().style(
        f"background: {t['bg_elevated']}; border: 1px solid {t['border']}30; "
        f"border-radius: 6px; padding: 10px;"
    ):
        items = []
        scope = state["scope"]

        if scope in ("all", "current_view", "selected_forms"):
            if ps:
                forms = len(ps.schedule_inventory) if ps.schedule_inventory else 0
                items.append(f"{ps.entity_count} entities")
                items.append(f"{forms} form groups")
                items.append(f"~{ps.total_records:,} records")
                items.append(f"{ps.total_fields:,} fields")

        if scope == "issues_only":
            if s.report:
                items.append(f"{len(s.report.findings)} findings")
            else:
                items.append("No review data")

        if scope == "rollover_only":
            if s.rollover_reports:
                total = sum(r.total_checks for r in s.rollover_reports.values())
                items.append(f"{total} comparison items")
                items.append(f"{len(s.rollover_reports)} reports")
            else:
                items.append("No rollover data")

        if not items:
            items.append("No data to export")

        for item in items:
            with ui.row().classes("items-center gap-2"):
                ui.icon("chevron_right").style(
                    f"color: {t['accent']}; font-size: 0.7rem;")
                ui.label(item).classes("text-xs") \
                    .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")


def _update_state(state: dict, key: str, value):
    """Update dialog state."""
    state[key] = value


def _toggle_form(state: dict, form_name: str, checked: bool):
    """Toggle form in selection."""
    if checked:
        state["selected_forms"].add(form_name)
    else:
        state["selected_forms"].discard(form_name)


async def _execute_export(state: dict, dialog):
    """Execute the export with current settings."""
    s = get_state()

    try:
        from lab.xml_parser.api.service import MythosService

        svc = MythosService()
        scope = state["scope"]
        fmt = state["format"]

        forms_filter = None
        if scope == "selected_forms" and state["selected_forms"]:
            forms_filter = list(state["selected_forms"])
        elif scope == "current_view" and s.xml_check.selected_form:
            forms_filter = [s.xml_check.selected_form]

        entity_filter = None
        if s.xml_check.selected_entity:
            entity_filter = s.xml_check.selected_entity

        result = None

        if scope == "issues_only":
            if s.report:
                result = svc.export_findings(
                    s.report, format=fmt,
                    include_metadata=state["include_metadata"],
                )
            else:
                ui.notify("No review findings to export", type="warning")
                return

        elif scope == "rollover_only":
            if s.rollover_reports:
                result = svc.export_rollover(
                    s.rollover_reports, format=fmt,
                )
            else:
                ui.notify("No rollover data to export", type="warning")
                return

        else:
            if s.parser:
                result = svc.export_parsed_data(
                    parser=s.parser,
                    format=fmt,
                    forms_filter=forms_filter,
                    entity_filter=entity_filter,
                    include_metadata=state["include_metadata"],
                    include_summary=state["include_summary"],
                    include_raw=state["include_raw"],
                )
            else:
                ui.notify("No parsed data to export", type="warning")
                return

        if result and result.success:
            ui.notify(f"Exported: {result.message}", type="positive")
        elif result:
            ui.notify(f"Export issue: {result.message}", type="warning")

        dialog.close()

    except Exception as exc:
        ui.notify(f"Export failed: {exc}", type="negative")

"""Schedules tab — schedule inventory with entity coverage matrix."""

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.parse_service import get_display_name


def render_schedules(t: dict, s):
    """Render the Schedules tab."""
    xc = s.xml_check
    ps = xc.parse_summary

    if not ps or not ps.schedule_inventory:
        _render_empty(t)
        return

    # Collect all schedule nodes (flatten)
    all_schedules = []
    for top_node in ps.schedule_inventory:
        for child in top_node.children:
            if "Schedule" in child.form_name:
                all_schedules.append(child)

    if not all_schedules:
        _render_empty(t)
        return

    # Header
    with ui.row().classes("items-center gap-2 mb-4 animate-fade-up stagger-1"):
        ui.icon("table_chart").style(f"color: {t['accent']}; font-size: 1rem;")
        ui.label("Schedule Coverage").classes("text-sm font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(f"{len(all_schedules)} schedules detected") \
            .classes("text-xs").style(f"color: {t['text_muted']};")

    # Table view of schedules
    columns = [
        {"name": "schedule", "label": "Schedule", "field": "schedule", "align": "left", "sortable": True},
        {"name": "form_type", "label": "Form", "field": "form_type", "align": "center"},
        {"name": "entities", "label": "Entities", "field": "entities", "align": "center", "sortable": True},
        {"name": "fields", "label": "Fields", "field": "fields", "align": "center", "sortable": True},
        {"name": "multi", "label": "Multi-Instance", "field": "multi", "align": "center"},
    ]

    rows = []
    for i, sch in enumerate(all_schedules):
        short = sch.display_name.split("—")[0].strip() if "—" in sch.display_name else sch.display_name
        rows.append({
            "_id": i,
            "schedule": short,
            "form_type": sch.form_type.upper(),
            "entities": sch.entity_count,
            "fields": sch.field_count,
            "multi": "Yes" if sch.has_multi_instance else "—",
            "_form_name": sch.form_name,
        })

    strip = TableFilterStrip(
        filterable_columns={"form_type": "Form Type"},
        all_rows=rows,
    )
    strip.render(t)

    with ui.card().classes("w-full animate-fade-up stagger-2").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 0; overflow: hidden;"
    ):
        table = ui.table(
            columns=columns, rows=strip.filtered_rows, row_key="_id",
            pagination={"rowsPerPage": 25},
        ).classes("w-full").props("dense flat bordered separator=cell")
        table.style(f"background: {t['bg_card']}; font-size: 0.75rem;")
        strip.bind(table)

        # Row click to navigate
        table.on("row-click", lambda e: _navigate_to_form(
            e.args[1].get("_form_name", "") if len(e.args) > 1 else ""
        ))

    # Coverage heatmap (visual)
    ui.separator().classes("w-full my-4").style(f"background: {t['border']}20;")

    with ui.column().classes("w-full animate-fade-up stagger-3"):
        ui.label("Entity Coverage").classes("text-xs font-semibold mb-2") \
            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                   f"letter-spacing: 0.05em; font-size: 0.6rem;")

        max_entities = max((sch.entity_count for sch in all_schedules), default=1)

        for sch in sorted(all_schedules, key=lambda x: x.entity_count, reverse=True):
            pct = sch.entity_count / max_entities * 100 if max_entities > 0 else 0
            short = sch.display_name.split("—")[0].strip() if "—" in sch.display_name else sch.form_name

            with ui.row().classes("items-center gap-2 w-full mb-1"):
                ui.label(short).classes("text-xs w-32") \
                    .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")
                with ui.row().classes("flex-1 items-center"):
                    ui.element("div").style(
                        f"height: 6px; width: {max(pct, 3)}%; "
                        f"background: {t['accent']}; border-radius: 3px; "
                        f"transition: width 0.4s ease;")
                ui.label(str(sch.entity_count)).classes("text-xs mythos-mono w-8 text-right") \
                    .style(f"color: {t['text_muted']};")


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("table_chart").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No schedules detected").classes("text-sm") \
            .style(f"color: {t['text_muted']};")


def _navigate_to_form(form_name: str):
    if not form_name:
        return
    s = get_state()
    s.xml_check.selected_form = form_name
    s.xml_check.active_tab = "parsed_data"
    ui.navigate.to("/review")

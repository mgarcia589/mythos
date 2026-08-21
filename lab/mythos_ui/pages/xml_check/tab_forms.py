"""Forms tab — form & schedule inventory split by form type (5471 / 8858)."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state


def render_forms(t: dict, s):
    """Render the Forms tab — tables grouped by form type."""
    xc = s.xml_check
    ps = xc.parse_summary

    if not ps or not ps.schedule_inventory:
        _render_empty(t)
        return

    # Flatten all children from schedule_inventory
    all_items = []
    for top_node in ps.schedule_inventory:
        for child in top_node.children:
            all_items.append(child)

    # Split by form type
    items_5471 = [f for f in all_items if "5471" in f.form_type or "5471" in f.form_name]
    items_8858 = [f for f in all_items if "8858" in f.form_type or "8858" in f.form_name]
    items_8990 = [f for f in all_items if "8990" in f.form_type or "8990" in f.form_name]
    items_other = [f for f in all_items if f not in items_5471 and f not in items_8858 and f not in items_8990]

    # Header
    with ui.row().classes("items-center gap-2 mb-4 animate-fade-up stagger-1"):
        ui.icon("description").style(f"color: {t['accent']}; font-size: 1rem;")
        ui.label("Forms & Schedules").classes("text-sm font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(f"{len(all_items)} items total") \
            .classes("text-xs").style(f"color: {t['text_muted']};")

    # 5471 table
    if items_5471:
        _render_form_table(t, "Form 5471", items_5471, stagger=2)

    # 8858 table
    if items_8858:
        _render_form_table(t, "Form 8858", items_8858, stagger=3)

    # 8990 table
    if items_8990:
        _render_form_table(t, "Form 8990", items_8990, stagger=4)

    # Other (if any)
    if items_other:
        _render_form_table(t, "Other Attachments & Statements", items_other, stagger=5)


def _render_form_table(t: dict, title: str, items: list, stagger: int = 2):
    """Render a single form type table."""
    with ui.column().classes(f"w-full mb-5 animate-fade-up stagger-{stagger}"):
        # Section header
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("folder").style(f"color: {t['accent']}; font-size: 0.9rem;")
            ui.label(title).classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.label(f"{len(items)} items").classes("text-xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")

        # Table
        columns = [
            {"name": "name", "label": "Form / Schedule", "field": "name", "align": "left", "sortable": True},
            {"name": "description", "label": "Description", "field": "description", "align": "left"},
            {"name": "entities", "label": "Entities", "field": "entities", "align": "center", "sortable": True},
            {"name": "fields", "label": "Fields", "field": "fields", "align": "center", "sortable": True},
            {"name": "multi", "label": "Multi", "field": "multi", "align": "center"},
        ]

        rows = []
        for i, node in enumerate(items):
            short = node.display_name.split("—")[0].strip() if "—" in node.display_name else node.display_name
            desc = node.display_name.split("—")[1].strip() if "—" in node.display_name else ""

            rows.append({
                "_id": i,
                "name": short,
                "description": desc,
                "entities": node.entity_count,
                "fields": node.field_count,
                "multi": "Yes" if node.has_multi_instance else "—",
                "_form_name": node.form_name,
            })

        with ui.card().classes("w-full").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 0; overflow: hidden;"
        ):
            table = ui.table(
                columns=columns, rows=rows, row_key="_id",
                pagination={"rowsPerPage": 25},
            ).classes("w-full mythos-sticky-table").props("dense flat bordered separator=cell")
            table.style(f"background: {t['bg_card']}; font-size: 0.75rem;")

            table.on("row-click", lambda e: _navigate_to_form(
                e.args[1].get("_form_name", "") if len(e.args) > 1 else ""
            ))


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("description").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No form data available").classes("text-sm") \
            .style(f"color: {t['text_muted']};")


def _navigate_to_form(form_name: str):
    if not form_name:
        return
    s = get_state()
    s.xml_check.selected_form = form_name
    s.xml_check.active_tab = "parsed_data"
    ui.navigate.to("/review")

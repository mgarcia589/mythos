"""Toolbar — entity/form filters and export (search moved to Issues tab)."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.parse_service import get_display_name


def render_toolbar(t: dict, s):
    """Render the persistent toolbar between tabs and content."""
    xc = s.xml_check

    with ui.row().classes("w-full items-center gap-3 mb-3 animate-fade-up stagger-2"):
        # Dynamic filters (entity + form type)
        _render_filter_chips(t, s)

        # Spacer
        ui.element("div").classes("flex-1")

        # Export button
        ui.button("Export", icon="download",
                  on_click=lambda: _open_export()) \
            .props("flat no-caps size=sm") \
            .style(f"color: {t['accent']}; font-size: 0.7rem;")

    # Active filter pills
    if xc.active_filters:
        with ui.row().classes("w-full items-center gap-2 mb-2"):
            ui.label("Filters:").classes("text-xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")

            for key, value in xc.active_filters.items():
                with ui.row().classes("items-center gap-1").style(
                    f"background: {t['accent']}15; border: 1px solid {t['accent']}30; "
                    f"border-radius: 12px; padding: 2px 8px;"
                ):
                    ui.label(f"{key}: {value}").classes("text-xs") \
                        .style(f"color: {t['accent']}; font-size: 0.6rem;")
                    ui.button(icon="close",
                              on_click=lambda _, k=key: _remove_filter(k)) \
                        .props("flat dense round size=xs") \
                        .style(f"color: {t['accent']}; font-size: 0.5rem;")

            ui.button("Clear all", icon="filter_list_off",
                      on_click=lambda: _clear_filters()) \
                .props("flat dense no-caps size=xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _render_filter_chips(t: dict, s):
    """Render dynamic filter dropdowns."""
    xc = s.xml_check
    ps = xc.parse_summary

    if not ps:
        return

    # Entity filter
    if ps.entity_count > 1:
        entities = _get_entity_options(s)
        if entities:
            current_entity = xc.active_filters.get("entity", "All")
            ui.select(
                options=["All"] + entities,
                value=current_entity,
                on_change=lambda e: _set_filter("entity", e.value),
                label="Entity",
            ).classes("w-36").props("dense outlined") \
                .style("font-size: 0.65rem;")

    # Form type filter
    if len(ps.form_types) > 1:
        form_opts = ["All"] + [f"Form {ft}" for ft in sorted(ps.form_types)]
        current_form = xc.active_filters.get("form_type", "All")
        ui.select(
            options=form_opts,
            value=current_form,
            on_change=lambda e: _set_filter("form_type", e.value),
            label="Form Type",
        ).classes("w-32").props("dense outlined") \
            .style("font-size: 0.65rem;")


def _get_entity_options(s) -> list[str]:
    """Get entity options for filter."""
    if not s.parser:
        return []
    try:
        subs = s.parser.list_subsidiaries()
        return [f"{e.get('reference_id', '')} — {e.get('name', '')[:25]}"
                for e in subs[:50]]
    except Exception:
        return []


# ─── HANDLERS ──────────────────────────────────────────────────────────────

def _set_filter(key: str, value: str):
    s = get_state()
    if value == "All":
        s.xml_check.active_filters.pop(key, None)
    else:
        s.xml_check.active_filters[key] = value

    if key == "entity" and value != "All":
        ref_id = value.split(" — ")[0] if " — " in value else value
        s.xml_check.selected_entity = ref_id
    elif key == "entity":
        s.xml_check.selected_entity = None

    _refresh()


def _remove_filter(key: str):
    s = get_state()
    s.xml_check.active_filters.pop(key, None)
    if key == "entity":
        s.xml_check.selected_entity = None
    _refresh()


def _clear_filters():
    s = get_state()
    s.xml_check.active_filters.clear()
    s.xml_check.selected_entity = None
    s.xml_check.search_query = ""
    _refresh()


def _open_export():
    """Open the export dialog."""
    from lab.mythos_ui.pages.xml_check.export_dialog import show_export_dialog
    show_export_dialog()

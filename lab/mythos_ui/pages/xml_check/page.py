"""XML Check — Page orchestrator (state machine + tab router).

Uses @ui.refreshable created per-page-visit so uploads/actions trigger re-render.
"""

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.xml_check_state import PagePhase, ProcessingMode


def render():
    """Main render entry point — called by the route handler."""

    @ui.refreshable
    def content():
        t = get_theme()
        s = get_state()
        xc = s.xml_check

        match xc.phase:
            case PagePhase.INITIAL | PagePhase.FILES_UPLOADED:
                _render_upload(t, s, content.refresh)
            case PagePhase.PROCESSING:
                _render_processing(t, s, content.refresh)
            case PagePhase.COMPLETED | PagePhase.COMPLETED_WITH_WARNINGS | PagePhase.PARTIAL_SUCCESS:
                _render_completed(t, s, content.refresh)
            case PagePhase.FAILED:
                _render_failed(t, s, content.refresh)

    content()


def _render_upload(t: dict, s, refresh_fn):
    """Upload state — two cards + mode + run button."""
    from lab.mythos_ui.pages.xml_check.upload_panel import render_upload
    render_upload(t, s, refresh_fn=refresh_fn)


def _render_processing(t: dict, s, refresh_fn):
    """Processing in progress."""
    from lab.mythos_ui.pages.xml_check.processing_panel import render_progress

    with ui.column().classes("w-full gap-1 mb-4 animate-fade-up"):
        ui.label("Review").classes("text-2xl font-bold") \
            .style(f"color: {t['text_primary']};")
        ui.label("Processing...").classes("text-sm") \
            .style(f"color: {t['text_secondary']};")

    render_progress(t, s, refresh_fn=refresh_fn)


def _render_completed(t: dict, s, refresh_fn):
    """Processing complete — show toolbar + tabs."""
    xc = s.xml_check

    # Header
    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Review").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            subtitle_parts = []
            if xc.parse_summary:
                ps = xc.parse_summary
                if ps.client_name:
                    subtitle_parts.append(ps.client_name)
                if ps.tax_year:
                    subtitle_parts.append(f"FY{ps.tax_year}")
                subtitle_parts.append(f"{ps.entity_count} entities")
            ui.label(" · ".join(subtitle_parts) if subtitle_parts else "Analysis complete") \
                .classes("text-sm").style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-2"):
            ui.button("New Analysis", icon="restart_alt",
                      on_click=lambda: _clear_session(refresh_fn)) \
                .props("flat no-caps size=sm") \
                .style(f"color: {t['text_muted']}; font-size: 0.7rem;")

    # Warning banner
    if xc.phase == PagePhase.COMPLETED_WITH_WARNINGS and xc.warnings:
        with ui.card().classes("w-full mb-3").style(
            f"background: {t['sev_medium_bg']}; border: 1px solid {t['sev_medium']}40; "
            f"border-radius: 8px; padding: 10px 14px;"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("warning").style(f"color: {t['sev_medium']}; font-size: 0.9rem;")
                ui.label(f"{len(xc.warnings)} warnings during processing") \
                    .classes("text-xs font-semibold") \
                    .style(f"color: {t['sev_medium']};")

    # Tabs
    _render_tabs(t, s, refresh_fn)

    # Separator
    ui.separator().classes("w-full my-2").style(f"background: {t['border']}20;")

    # Tab content
    _render_active_tab(t, s, refresh_fn)


def _render_failed(t: dict, s, refresh_fn):
    """Processing failed."""
    xc = s.xml_check

    with ui.column().classes("w-full items-center justify-center py-12 gap-4 animate-fade-up"):
        ui.icon("error_outline").classes("text-5xl") \
            .style(f"color: {t['sev_high']};")

        ui.label("Processing Failed").classes("text-lg font-bold") \
            .style(f"color: {t['text_primary']};")

        if xc.error_message:
            ui.label(xc.error_message).classes("text-sm text-center max-w-lg") \
                .style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-3 mt-4"):
            ui.button("Retry", icon="refresh",
                      on_click=lambda: _retry_processing(refresh_fn)) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 24px; border-radius: 6px; font-size: 0.8rem;")

            ui.button("Start Over", icon="restart_alt",
                      on_click=lambda: _clear_session(refresh_fn)) \
                .props("flat no-caps") \
                .style(f"color: {t['text_muted']}; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")


# ─── TABS ──────────────────────────────────────────────────────────────────

TAB_ITEMS = [
    {"key": "overview", "label": "Overview", "icon": "dashboard"},
    {"key": "forms", "label": "Forms & Schedules", "icon": "description"},
    {"key": "entities", "label": "Entities", "icon": "account_tree"},
    {"key": "parsed_data", "label": "Parsed Data", "icon": "grid_on"},
    {"key": "issues", "label": "Issues", "icon": "bug_report"},
    {"key": "rollover", "label": "Rollover", "icon": "swap_vert"},
]


def _render_tabs(t: dict, s, refresh_fn):
    """Render tab navigation bar."""
    xc = s.xml_check

    with ui.row().classes("w-full gap-1 animate-fade-up stagger-2"):
        for tab in TAB_ITEMS:
            is_active = xc.active_tab == tab["key"]

            if tab["key"] == "rollover" and not s.rollover_reports and \
               xc.mode not in (ProcessingMode.ROLLOVER_ONLY, ProcessingMode.FULL_REVIEW):
                continue

            if tab["key"] == "issues" and not s.report:
                continue

            btn_style = (
                f"background: {t['nav_active_bg']}; color: {t['accent']}; "
                f"font-weight: 600; border-bottom: 2px solid {t['accent']};"
            ) if is_active else (
                f"color: {t['text_muted']};"
            )

            ui.button(
                tab["label"], icon=tab["icon"],
                on_click=lambda _, k=tab["key"]: _switch_tab(k, refresh_fn)
            ).props("flat dense no-caps size=sm").style(
                f"{btn_style} padding: 6px 12px; border-radius: 6px 6px 0 0; "
                f"font-size: 0.7rem;"
            )


def _render_active_tab(t: dict, s, refresh_fn):
    """Render the content for the currently active tab."""
    xc = s.xml_check

    if xc.active_tab not in ("overview", "forms", "entities"):
        from lab.mythos_ui.pages.xml_check.toolbar import render_toolbar
        render_toolbar(t, s)

    match xc.active_tab:
        case "overview":
            from lab.mythos_ui.pages.xml_check.tab_overview import render_overview
            render_overview(t, s)
        case "forms":
            from lab.mythos_ui.pages.xml_check.tab_forms import render_forms
            render_forms(t, s)
        case "entities":
            from lab.mythos_ui.pages.xml_check.tab_entities import render_entities
            render_entities(t, s)
        case "parsed_data":
            from lab.mythos_ui.pages.xml_check.tab_parsed_data import render_parsed_data
            render_parsed_data(t, s)
        case "issues":
            from lab.mythos_ui.pages.xml_check.tab_issues import render_issues
            render_issues(t, s)
        case "rollover":
            from lab.mythos_ui.pages.xml_check.tab_rollover import render_rollover
            render_rollover(t, s)


# ─── HANDLERS ──────────────────────────────────────────────────────────────

def _switch_tab(key: str, refresh_fn):
    s = get_state()
    s.xml_check.active_tab = key
    refresh_fn()


def _clear_session(refresh_fn):
    s = get_state()
    s.xml_check.reset()
    s.report = None
    s.parser = None
    s.current_xml = None
    s.prior_xml = None
    s.rollover_reports = None
    s.reviewed_items = set()
    refresh_fn()


def _retry_processing(refresh_fn):
    s = get_state()
    s.xml_check.phase = PagePhase.FILES_UPLOADED
    s.xml_check.error_message = None
    refresh_fn()

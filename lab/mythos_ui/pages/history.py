"""History page — shows previous review executions in this session."""

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state


def render():
    """Render the history page."""
    t = get_theme()
    s = get_state()

    with ui.row().classes("w-full items-center justify-between mb-6 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Review History").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label("Previous review executions in this session") \
                .classes("text-sm").style(f"color: {t['text_secondary']};")

    if not s.history:
        _render_empty(t)
        return

    # Show history entries (most recent first)
    for i, entry in enumerate(reversed(s.history)):
        is_current = i == 0
        _history_card(t, entry, is_current, len(s.history) - i)

    # Summary
    with ui.row().classes("w-full mt-6 items-center gap-2 animate-fade-up"):
        ui.icon("timeline").classes("text-sm") \
            .style(f"color: {t['text_muted']};")
        ui.label(f"{len(s.history)} review{'s' if len(s.history) != 1 else ''} "
                 f"executed this session") \
            .classes("text-xs").style(f"color: {t['text_muted']};")


def _history_card(t: dict, entry, is_current: bool, run_num: int):
    """Single history entry card."""
    border_color = t["accent"] if is_current else t["glass_border"]
    badge_text = "Current" if is_current else f"Run #{run_num}"

    with ui.card().classes("w-full mb-3 animate-fade-up").style(
        f"background: {t['glass_bg']}; "
        f"border: 1px solid {border_color}; "
        f"border-left: 3px solid {border_color}; "
        f"border-radius: 12px; padding: 16px 20px;"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("history").classes("text-base") \
                    .style(f"color: {t['accent'] if is_current else t['text_muted']};")
                with ui.column().classes("gap-0"):
                    ui.label(f"{entry.client_name} · FY{entry.tax_year}") \
                        .classes("text-sm font-semibold") \
                        .style(f"color: {t['text_primary']};")
                    ui.label(entry.timestamp).classes("text-xs") \
                        .style(f"color: {t['text_muted']};")

            with ui.row().classes("items-center gap-3"):
                # Quick stats
                with ui.row().classes("gap-2"):
                    _stat_chip(t, f"{entry.entity_count} entities", t["info"])
                    _stat_chip(t, f"{entry.finding_count} findings",
                               t["sev_high"] if entry.high_count > 0 else t["text_muted"])
                    if entry.high_count > 0:
                        _stat_chip(t, f"{entry.high_count} critical", t["sev_high"])

                ui.badge(badge_text, color="primary" if is_current else "grey") \
                    .props("outline dense")

        # File info
        with ui.row().classes("mt-2 gap-2 items-center"):
            ui.icon("description").classes("text-xs") \
                .style(f"color: {t['text_muted']};")
            ui.label(entry.xml_name).classes("text-xs mythos-mono") \
                .style(f"color: {t['text_secondary']};")


def _stat_chip(t: dict, text: str, color: str):
    """Mini stat chip."""
    ui.label(text).classes("text-xs px-2 py-0.5 rounded") \
        .style(f"background: {color}12; color: {color}; font-weight: 500;")


def _render_empty(t: dict):
    """Empty state for history."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("history").classes("text-5xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label("No review history yet").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(
            "Each time you run a compliance review, it will appear here. "
            "History persists for the current session."
        ).classes("text-sm text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

        ui.button("Run your first review", icon="play_circle",
                  on_click=lambda: ui.navigate.to("/")) \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

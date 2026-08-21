"""XML Check — Upload zone + post-review summary. Detailed findings live in /findings."""

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.components import notify


def render():
    """Render the Home cockpit."""
    t = get_theme()
    s = get_state()

    if not s.report:
        _render_welcome(t)
        return

    # Post-review: show success summary + actions (not detailed findings)
    _render_review_complete(t, s)


# ─── REVIEW COMPLETE (POST-ANALYSIS STATE) ────────────────────────────────

def _render_review_complete(t: dict, s):
    """Post-review Home: success/error summary + actions to navigate or reset."""
    report = s.report
    summary = report.summary
    total = summary["total_findings"]
    high = summary["by_severity"]["HIGH"]
    entities = report.entity_count
    clean = summary["clean_entities"]

    # Determine status
    if high > 0:
        status_color = t["sev_high"]
        status_icon = "error"
        status_title = "Review complete — issues detected"
    elif total > 0:
        status_color = t["accent"]
        status_icon = "check_circle"
        status_title = "Review complete — minor findings"
    else:
        status_color = t["success"]
        status_icon = "check_circle"
        status_title = "Review complete — all clear"

    with ui.column().classes("w-full items-center justify-center py-8 gap-5 animate-fade-up"):
        # Status icon
        ui.icon(status_icon).classes("text-5xl") \
            .style(f"color: {status_color};")

        # Title
        ui.label(status_title).classes("text-lg font-bold") \
            .style(f"color: {t['text_primary']};")

        # Summary line
        ui.label(
            f"{report.client_name} · FY{report.tax_year} · "
            f"{entities} entities analyzed · {clean} passed all checks"
        ).classes("text-sm text-center") \
            .style(f"color: {t['text_muted']};")

        # Quick stats
        with ui.row().classes("gap-3 mt-2"):
            _mini_stat(t, str(entities), "Entities", t["info"])
            _mini_stat(t, str(total), "Findings", t["accent"])
            _mini_stat(t, str(high), "Critical", t["sev_high"] if high > 0 else t["success"])
            _mini_stat(t, f"{clean}/{entities}", "Clean", t["success"])

        # Action buttons
        with ui.row().classes("gap-3 mt-6"):
            ui.button("View Findings", icon="assignment",
                      on_click=lambda: ui.navigate.to("/findings")) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 24px; border-radius: 6px; font-size: 0.8rem;")

            ui.button("View Entities", icon="account_tree",
                      on_click=lambda: ui.navigate.to("/entities")) \
                .props("flat no-caps") \
                .style(f"color: {t['text_secondary']}; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

            ui.button("Export", icon="download",
                      on_click=lambda: _handle_export()) \
                .props("flat no-caps") \
                .style(f"color: {t['text_secondary']}; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

        # Separator
        ui.separator().classes("w-64 my-4").style(f"background: {t['border']}30;")

        # Reset / load another
        with ui.row().classes("gap-3"):
            ui.button("Load another XML", icon="upload_file",
                      on_click=lambda: _clear_and_restart()) \
                .props("flat no-caps") \
                .style(f"color: {t['accent']}; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

            ui.button("Clear analysis", icon="restart_alt",
                      on_click=lambda: _clear_and_restart()) \
                .props("flat no-caps") \
                .style(f"color: {t['text_muted']}; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")


def _mini_stat(t: dict, value: str, label: str, color: str):
    """Compact stat badge for post-review summary."""
    with ui.card().classes("text-center").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 8px; padding: 12px 20px; min-width: 80px;"
    ):
        ui.label(value).classes("text-base font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


# ─── WELCOME (EMPTY STATE) ────────────────────────────────────────────────

def _render_welcome(t: dict):
    """Let's start — upload zone with CY (required) and PY (optional)."""
    from lab.mythos_ui.services.bridge import get_state
    s = get_state()

    with ui.column().classes("w-full items-center justify-center py-8 gap-5 animate-fade-up"):
        # Logo + title
        from lab.mythos_ui.layout import LOGO_SVG
        ui.html(LOGO_SVG.replace('width="16"', 'width="40"')
                .replace('height="18"', 'height="45"')) \
            .style(f"color: {t['accent']};")

        ui.label("Let's start").classes("text-xl font-bold") \
            .style(f"color: {t['text_primary']};")

        ui.label(
            "Upload an IRS e-file XML to parse, review, or compare."
        ).classes("text-sm text-center") \
            .style(f"color: {t['text_muted']};")

        # ── Upload cards ──
        with ui.row().classes("gap-4 mt-4 items-stretch"):
            # Current Year (required)
            _upload_card(t, s, "current")

            # Prior Year (optional)
            _upload_card(t, s, "prior")

        # ── Action buttons ──
        with ui.row().classes("gap-3 mt-4"):
            ui.button("Run Review", icon="play_circle",
                      on_click=lambda: _run_from_home()) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 24px; border-radius: 6px; font-size: 0.8rem;")


        # ── Value props (compact) ──
        ui.separator().classes("w-48 my-4").style(f"background: {t['border']}30;")

        with ui.row().classes("gap-6"):
            _value_prop(t, "bolt", "< 3 sec", "Per entity")
            _value_prop(t, "checklist", "32 checks", "4 dimensions")
            _value_prop(t, "compare", "Rollover", "YoY analysis")
            _value_prop(t, "download", "4 formats", "Export ready")


def _value_prop(t: dict, icon: str, title: str, subtitle: str):
    """Mini value proposition."""
    with ui.column().classes("items-center gap-1"):
        ui.icon(icon).classes("text-lg") \
            .style(f"color: {t['accent']}; opacity: 0.7;")
        ui.label(title).classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(subtitle).classes("text-xs") \
            .style(f"color: {t['text_muted']};")


def _upload_card(t: dict, s, target: str):
    """Full upload card with header, description, and functional drop zone."""
    is_current = target == "current"
    current_file = s.current_xml if is_current else s.prior_xml
    has_file = current_file is not None

    card_border = f"1px solid {t['border']}60" if is_current else f"1px solid {t['border']}40"
    icon_name = "description" if is_current else "history"
    icon_color = t["success"] if is_current else t["text_muted"]
    title = "Current Year XML" if is_current else "Prior Year XML"
    badge_text = "Required" if is_current else "Optional"
    badge_style = (f"color: {t['error']}; border: 1px solid {t['error']}40; font-size: 0.55rem;"
                   if is_current else
                   f"color: {t['text_muted']}; border: 1px solid {t['border']}; font-size: 0.55rem;")
    desc = ("The return you want to review or parse."
            if is_current else "Enables rollover checks (YoY comparison).")
    handler = _handle_cy_upload if is_current else _handle_py_upload

    with ui.card().classes("glass-card").style(
        f"background: {t['bg_card']}; border: {card_border}; "
        f"border-radius: 10px; padding: 20px; width: 280px; "
        f"display: flex; flex-direction: column;"
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon(icon_name).style(f"color: {icon_color}; font-size: 1rem;")
            ui.label(title).classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.badge(badge_text, color="transparent").props("dense") \
                .style(badge_style)

        # Fixed-height description area so both cards align
        ui.label(desc).classes("text-xs") \
            .style(f"color: {t['text_muted']}; min-height: 32px;")

        # Spacer pushes drop zone to bottom
        ui.space()

        # Drop zone — uses standard ui.upload but styled
        upload = ui.upload(
            label="Drop your .xml file here or click to browse",
            auto_upload=True,
            on_upload=handler,
        ).classes("mythos-upload w-full").props("accept=.xml dense flat")
        upload.style(
            f"background: {t['bg_main']}; "
            f"border: 1.5px dashed {t['success'] if has_file else t['border']}; "
            f"border-radius: 8px; "
            f"min-height: 72px;"
        )

        # Status indicator
        if has_file:
            with ui.row().classes("items-center gap-1 mt-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.8rem;")
                ui.label(current_file.name).classes("text-xs") \
                    .style(f"color: {t['success']};")


# ─── HANDLERS ──────────────────────────────────────────────────────────────

async def _handle_cy_upload(e):
    """Handle current year XML upload."""
    import tempfile
    from pathlib import Path
    from lab.mythos_ui.services.bridge import get_state

    state = get_state()
    tmp = Path(tempfile.gettempdir()) / e.file.name
    await e.file.save(tmp)
    state.current_xml = tmp
    notify("Current Year loaded", level="success", caption=e.file.name)
    ui.navigate.to("/review")


async def _handle_py_upload(e):
    """Handle prior year XML upload."""
    import tempfile
    from pathlib import Path
    from lab.mythos_ui.services.bridge import get_state

    state = get_state()
    tmp = Path(tempfile.gettempdir()) / e.file.name
    await e.file.save(tmp)
    state.prior_xml = tmp
    notify("Prior Year loaded", level="success", caption=e.file.name)
    ui.navigate.to("/review")


async def _run_from_home():
    """Run review directly from the home page."""
    from lab.mythos_ui.services.bridge import get_state, run_review
    from lab.mythos_ui.components import ProgressOverlay

    s = get_state()
    if not s.current_xml:
        ui.notify("Upload a Current Year XML first", type="warning")
        return

    overlay = ProgressOverlay()
    overlay.show()

    result = await run_review(s.current_xml, s.prior_xml)
    overlay.hide()

    if result.success:
        ui.notify(
            f"Review complete: {result.finding_count} findings",
            type="positive",
        )
        ui.navigate.to("/")
    else:
        ui.notify(f"Review failed: {result.message}", type="negative")




async def _handle_export():
    """Export from Home cockpit."""
    from lab.mythos_ui.services.bridge import run_export

    result = await run_export(fmt="excel")
    if result and result.success:
        ui.notify(f"Exported: {result.path.name}", type="positive")
    else:
        ui.notify("Nothing to export", type="warning")


def _clear_and_restart():
    """Clear current analysis and return to upload state."""
    from lab.mythos_ui.services.bridge import get_state

    state = get_state()
    state.report = None
    state.current_xml = None
    state.prior_xml = None
    state.reviewed_items = set()
    state.rollover_reports = None
    ui.navigate.to("/review")

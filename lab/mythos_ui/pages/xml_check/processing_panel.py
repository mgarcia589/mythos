"""Processing panel — mode selector + run button + progress display."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.xml_check_state import PagePhase, ProcessingMode
from lab.mythos_ui.components import notify


def render_processing_options(t: dict, s, refresh_fn=None):
    """Render mode selection cards + run button."""
    xc = s.xml_check

    with ui.card().classes("w-full animate-fade-up stagger-3").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 12px; padding: 20px 24px;"
    ):
        with ui.row().classes("items-center gap-2 mb-4"):
            ui.icon("tune").style(f"color: {t['accent']}; font-size: 1.1rem;")
            ui.label("Processing Mode").classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary']};")

        has_prior = any(f.role == "prior" for f in xc.files)
        selected = xc.mode

        with ui.row().classes("w-full gap-3"):
            _mode_card(
                t, "Parse XML",
                "Extract all forms, schedules, entities, and fields",
                "grid_on", ProcessingMode.PARSE_ONLY, selected, refresh_fn,
            )
            _mode_card(
                t, "Rollover Check",
                "Compare CY vs PY — identify differences",
                "swap_vert", ProcessingMode.ROLLOVER_ONLY, selected, refresh_fn,
                disabled=not has_prior,
                disabled_msg="Requires Prior Year XML",
            )
            _mode_card(
                t, "Full Review",
                "Parse + 32 compliance checks + rollover",
                "verified", ProcessingMode.FULL_REVIEW, selected, refresh_fn,
            )

        # Run button
        with ui.row().classes("w-full justify-end mt-4 gap-3 items-center"):
            if not has_prior and selected == ProcessingMode.ROLLOVER_ONLY:
                ui.label("Rollover requires Prior Year XML") \
                    .classes("text-xs").style(f"color: {t['sev_medium']};")

            can_run = selected is not None
            ui.button(
                "Run" if can_run else "Select a mode",
                icon="play_circle" if can_run else "touch_app",
                on_click=lambda: _start_processing(refresh_fn),
            ).props("unelevated no-caps").style(
                f"background: {t['accent'] if can_run else t['border']}; "
                f"color: {'#000' if can_run else t['text_muted']}; "
                f"font-weight: 600; padding: 10px 28px; border-radius: 6px; "
                f"font-size: 0.85rem; opacity: {'1' if can_run else '0.5'};"
            ).set_enabled(can_run)


def _mode_card(t: dict, title: str, desc: str, icon: str,
               mode: ProcessingMode, selected: ProcessingMode | None,
               refresh_fn=None, disabled: bool = False, disabled_msg: str = ""):
    """Single mode selection card."""
    is_active = selected == mode
    border_color = t["accent"] if is_active else t["border"]
    opacity = "0.4" if disabled else "1"

    with ui.card().classes("flex-1 cursor-pointer hover-lift").style(
        f"background: {t['bg_card']}; "
        f"border: {'2px' if is_active else '1px'} solid {border_color}{'80' if not is_active else ''}; "
        f"border-radius: 10px; padding: 16px; opacity: {opacity}; "
        f"transition: all 0.2s ease;"
    ).on("click", lambda _, m=mode, d=disabled: None if d else _select_mode(m, refresh_fn)):

        with ui.row().classes("items-center gap-2 mb-2"):
            icon_color = t["accent"] if is_active else t["text_muted"]
            ui.icon(icon).style(f"color: {icon_color}; font-size: 1.2rem;")
            ui.label(title).classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary'] if not disabled else t['text_muted']};")
            if is_active:
                ui.icon("check_circle").style(f"color: {t['accent']}; font-size: 0.9rem;")

        ui.label(desc).classes("text-xs") \
            .style(f"color: {t['text_secondary'] if not disabled else t['text_muted']}; "
                   f"line-height: 1.4;")

        if disabled and disabled_msg:
            ui.label(disabled_msg).classes("text-xs mt-2 italic") \
                .style(f"color: {t['sev_medium']}; font-size: 0.6rem;")


def render_progress(t: dict, s, refresh_fn=None):
    """Render processing progress view with polling timer."""
    xc = s.xml_check

    with ui.card().classes("w-full animate-fade-up").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 12px; padding: 32px;"
    ):
        with ui.column().classes("w-full items-center gap-4"):
            ui.icon("autorenew").classes("text-4xl spin-slow") \
                .style(f"color: {t['accent']};")

            mode_labels = {
                ProcessingMode.PARSE_ONLY: "Parsing XML...",
                ProcessingMode.ROLLOVER_ONLY: "Running Rollover Check...",
                ProcessingMode.FULL_REVIEW: "Running Full Review...",
            }
            ui.label(mode_labels.get(xc.mode, "Processing...")) \
                .classes("text-base font-semibold") \
                .style(f"color: {t['text_primary']};")

            progress_bar = ui.linear_progress(
                value=xc.progress, show_value=False,
            ).classes("w-80").style("height: 6px;")

            msg_label = ui.label(xc.progress_msg or "Initializing...") \
                .classes("text-xs mythos-mono") \
                .style(f"color: {t['text_muted']};")

            pct_label = ui.label(f"{xc.progress * 100:.0f}%") \
                .classes("text-xs mythos-mono") \
                .style(f"color: {t['accent']};")

    def _poll():
        s2 = get_state()
        xc2 = s2.xml_check
        if xc2.phase == PagePhase.PROCESSING:
            progress_bar.set_value(xc2.progress)
            msg_label.set_text(xc2.progress_msg or "Processing...")
            pct_label.set_text(f"{xc2.progress * 100:.0f}%")
        else:
            # Processing finished — refresh page to show results
            timer.deactivate()
            try:
                from lab.mythos_ui.layout import refresh_session_badge
                refresh_session_badge()
            except Exception:
                pass
            if refresh_fn:
                refresh_fn()

    timer = ui.timer(0.4, _poll)


# ─── HANDLERS ──────────────────────────────────────────────────────────────

def _select_mode(mode: ProcessingMode, refresh_fn=None):
    """Set the processing mode."""
    s = get_state()
    s.xml_check.mode = mode
    if refresh_fn:
        refresh_fn()


async def _start_processing(refresh_fn=None):
    """Begin processing based on selected mode."""
    s = get_state()
    xc = s.xml_check

    if not xc.mode:
        notify("Select a processing mode first", level="warning")
        return

    current_file = xc.get_current_file()
    if not current_file:
        notify("No Current Year XML loaded", level="warning")
        return

    # Transition to processing
    xc.phase = PagePhase.PROCESSING
    xc.progress = 0.0
    xc.progress_msg = "Starting..."
    if refresh_fn:
        refresh_fn()

    try:
        if xc.mode == ProcessingMode.PARSE_ONLY:
            await _run_parse_only(s, current_file, refresh_fn)
        elif xc.mode == ProcessingMode.ROLLOVER_ONLY:
            await _run_rollover_only(s, current_file, refresh_fn)
        elif xc.mode == ProcessingMode.FULL_REVIEW:
            await _run_full_review(s, current_file, refresh_fn)
    except Exception as ex:
        xc.phase = PagePhase.FAILED
        xc.error_message = str(ex)
        if refresh_fn:
            refresh_fn()


async def _run_parse_only(s, current_file, refresh_fn):
    """Execute parse-only mode."""
    from lab.mythos_ui.services.parse_service import parse_xml_only, build_parse_summary

    xc = s.xml_check

    def on_progress(msg, pct):
        xc.progress = pct
        xc.progress_msg = msg

    parser, parsed = await parse_xml_only(current_file.path, on_progress)

    s.parser = parser
    s.current_xml = current_file.path

    summary = await build_parse_summary(parser, parsed)
    xc.parse_summary = summary
    xc.phase = PagePhase.COMPLETED
    xc.active_tab = "overview"


async def _run_rollover_only(s, current_file, refresh_fn):
    """Execute rollover-only mode."""
    import asyncio
    from lab.xml_parser.reports import run_all_reports_unified
    from lab.xml_parser.parser import EFileParser
    from lab.mythos_ui.services.parse_service import build_parse_summary

    xc = s.xml_check
    prior_file = xc.get_prior_file()

    if not prior_file:
        xc.phase = PagePhase.FAILED
        xc.error_message = "No Prior Year XML loaded — required for rollover"
        return

    def on_progress(msg, pct):
        xc.progress = pct
        xc.progress_msg = msg

    on_progress("Parsing XMLs...", 0.2)
    loop = asyncio.get_event_loop()

    def _run():
        on_progress("Parsing current year...", 0.3)
        parser = EFileParser(current_file.path)
        parsed = parser.parse()
        on_progress("Running rollover reports...", 0.5)
        reports = run_all_reports_unified(prior_file.path, current_file.path)
        on_progress("Complete", 1.0)
        return parser, parsed, reports

    parser, parsed, reports = await loop.run_in_executor(None, _run)

    s.parser = parser
    s.rollover_reports = reports
    summary = await build_parse_summary(parser, parsed)
    xc.parse_summary = summary
    xc.phase = PagePhase.COMPLETED
    xc.active_tab = "rollover"


async def _run_full_review(s, current_file, refresh_fn):
    """Execute full review mode."""
    from lab.mythos_ui.services.bridge import run_review
    from lab.mythos_ui.services.parse_service import build_parse_summary

    xc = s.xml_check
    prior_file = xc.get_prior_file()
    prior_path = prior_file.path if prior_file else None

    def on_progress(msg, pct):
        xc.progress = pct
        xc.progress_msg = msg

    result = await run_review(current_file.path, prior_path, on_progress)

    if result.success:
        if s.parser:
            parsed = s.parser.parse()
            summary = await build_parse_summary(s.parser, parsed)
            xc.parse_summary = summary

        # Rollover if prior available
        if prior_path:
            import asyncio
            from lab.xml_parser.reports import run_all_reports_unified
            loop = asyncio.get_event_loop()
            reports = await loop.run_in_executor(
                None,
                lambda: run_all_reports_unified(prior_path, current_file.path),
            )
            s.rollover_reports = reports

        xc.phase = PagePhase.COMPLETED
        if result.high_count > 0:
            xc.phase = PagePhase.COMPLETED_WITH_WARNINGS
            xc.warnings.append(f"{result.high_count} critical issues detected")
        xc.active_tab = "overview"
    else:
        xc.phase = PagePhase.FAILED
        xc.error_message = result.message or "Review failed — unknown error"

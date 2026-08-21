"""Rollover page — PY vs CY year-over-year balance continuity analysis."""

from pathlib import Path

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state


def render():
    """Render the rollover analysis page."""
    t = get_theme()
    s = get_state()

    if not s.report or not s.prior_xml:
        _render_empty(t, has_report=s.report is not None)
        return

    # Use cached reports or show generate button
    if not s.rollover_reports:
        _render_generate(t)
        return

    reports = s.rollover_reports

    # ── Header ──
    total_checks = sum(r.total_checks for r in reports.values())
    total_pass = sum(r.passed for r in reports.values())
    total_fail = sum(r.failed for r in reports.values())
    pass_rate = total_pass / total_checks * 100 if total_checks > 0 else 0

    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Rollover Analysis").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label(
                f"{s.report.client_name} · FY{s.report.tax_year} · "
                f"{total_checks} comparisons across {len(reports)} reports"
            ).classes("text-sm").style(f"color: {t['text_secondary']};")

        ui.button("Regenerate", icon="refresh",
                  on_click=lambda: _regenerate()) \
            .props("flat no-caps dense") \
            .style(f"color: {t['text_muted']};")

    # ── KPI Strip ──
    with ui.row().classes("w-full gap-4 mb-6 animate-fade-up stagger-2"):
        _kpi(t, str(total_checks), "Comparisons", t["info"])
        _kpi(t, f"{pass_rate:.0f}%", "Pass Rate",
             t["success"] if pass_rate >= 95 else t["accent"] if pass_rate >= 80 else t["sev_high"])
        _kpi(t, str(total_fail), "Failures",
             t["sev_high"] if total_fail > 0 else t["success"])
        _kpi(t, str(total_pass), "Passed", t["success"])

    # ── Report Cards ──
    with ui.column().classes("w-full gap-4"):
        for report_name, report in reports.items():
            _report_card(t, report_name, report)


def _render_generate(t: dict):
    """Prompt user to generate rollover reports (can be slow for large files)."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("swap_vert").classes("text-5xl") \
            .style(f"color: {t['accent']}; opacity: 0.7;")
        ui.label("Ready to analyze").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(
            "Both CY and PY XML are loaded. Click below to run the "
            "year-over-year rollover comparison (may take a moment for large returns)."
        ).classes("text-sm text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

        ui.button("Generate Rollover Reports", icon="play_circle",
                  on_click=lambda: _run_rollover()) \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"padding: 10px 28px; border-radius: 6px; font-size: 0.85rem;")


async def _run_rollover():
    """Run rollover reports with progress overlay."""
    import asyncio
    from lab.mythos_ui.services.bridge import get_state
    from lab.mythos_ui.components import ProgressOverlay
    from lab.xml_parser.reports import run_all_reports

    s = get_state()
    s.progress = 0.0
    s.progress_msg = "Generating rollover reports..."

    overlay = ProgressOverlay()
    overlay.show()

    try:
        s.progress_msg = "Parsing PY and CY XML..."
        s.progress = 0.2
        reports = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: run_all_reports(s.prior_xml, s.current_xml),
        )
        s.rollover_reports = reports
        s.progress = 1.0
        s.progress_msg = "Complete"
    except Exception as e:
        ui.notify(f"Rollover generation failed: {e}", type="negative")
    finally:
        overlay.hide()

    ui.navigate.to("/rollover")


async def _regenerate():
    """Clear cached reports and regenerate."""
    from lab.mythos_ui.services.bridge import get_state
    s = get_state()
    s.rollover_reports = None
    await _run_rollover()


def _kpi(t: dict, value: str, label: str, color: str):
    """KPI card."""
    with ui.card().classes("flex-1 min-w-[120px] hover-lift").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-top: 2px solid {color}; border-radius: 10px; padding: 16px 20px;"
    ):
        ui.label(value).classes("text-xl font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs mt-0.5") \
            .style(f"color: {t['text_muted']}; font-size: 0.65rem;")


def _report_card(t: dict, name: str, report):
    """Single report section with expandable failure table."""
    has_failures = report.failed > 0
    status_color = t["sev_high"] if has_failures else t["success"]
    status_icon = "error" if has_failures else "check_circle"
    border = f"border-left: 3px solid {status_color};"

    with ui.card().classes("w-full glass-card animate-fade-up").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px 20px; {border}"
    ):
        # Header row
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-3"):
                ui.icon(status_icon).style(f"color: {status_color}; font-size: 1.1rem;")
                with ui.column().classes("gap-0"):
                    ui.label(name).classes("text-sm font-semibold") \
                        .style(f"color: {t['text_primary']};")
                    ui.label(f"{report.passed}/{report.total_checks} passed") \
                        .classes("text-xs") \
                        .style(f"color: {t['text_muted']};")

            with ui.row().classes("items-center gap-2"):
                if has_failures:
                    ui.badge(f"{report.failed} failures", color="red").props("outline dense")
                else:
                    ui.badge("CLEAN", color="green").props("outline dense")

        # Failure table (expandable)
        if has_failures:
            failures = [item for item in report.items if not item.passes]
            with ui.expansion(f"View {len(failures)} difference{'s' if len(failures) != 1 else ''}") \
                    .classes("w-full mt-3") \
                    .style(f"color: {t['text_secondary']};"):
                _failures_table(t, failures)


def _failures_table(t: dict, failures: list):
    """Render a table of rollover failures."""
    columns = [
        {"name": "entity", "label": "Entity", "field": "entity", "align": "left", "sortable": True},
        {"name": "ref", "label": "Ref ID", "field": "ref", "align": "left", "sortable": True},
        {"name": "field", "label": "Field", "field": "field", "align": "left"},
        {"name": "line", "label": "Line", "field": "line", "align": "center"},
        {"name": "py_value", "label": "PY Value", "field": "py_value", "align": "right"},
        {"name": "cy_value", "label": "CY Value", "field": "cy_value", "align": "right"},
        {"name": "diff", "label": "Difference", "field": "diff", "align": "right", "sortable": True},
    ]

    rows = []
    for i, item in enumerate(failures[:100]):
        diff_str = ""
        if item.difference and abs(item.difference) >= 1:
            if abs(item.difference) >= 1e6:
                diff_str = f"${item.difference / 1e6:+,.2f}M"
            elif abs(item.difference) >= 1000:
                diff_str = f"${item.difference / 1e3:+,.1f}K"
            else:
                diff_str = f"${item.difference:+,.0f}"

        rows.append({
            "id": str(i),
            "entity": item.entity_name[:30] if item.entity_name else "—",
            "ref": item.reference_id or "—",
            "field": item.field_description[:35] if item.field_description else "—",
            "line": item.line or "—",
            "py_value": _format_value(item.py_value),
            "cy_value": _format_value(item.cy_value),
            "diff": diff_str,
            "diff_raw": item.difference or 0,
        })

    strip = TableFilterStrip(
        filterable_columns={"entity": "Entity", "field": "Field"},
        all_rows=rows,
    )
    strip.render(t)

    table = ui.table(
        columns=columns,
        rows=strip.filtered_rows,
        row_key="id",
        pagination={"rowsPerPage": 25, "sortBy": "diff", "descending": True},
    ).classes("w-full").props("dense flat bordered separator=cell")
    strip.bind(table)

    table.style(
        f"background: {t['bg_card']}; "
        f"border: 1px solid {t['border']}30; "
        f"border-radius: 8px;"
    )

    table.add_slot("body-cell-diff", """
        <q-td :props="props">
            <span :style="props.row.diff_raw > 0 ? 'color: #ef4444; font-weight: 600' :
                         props.row.diff_raw < 0 ? 'color: #22c55e; font-weight: 600' :
                         'color: inherit'">
                {{ props.row.diff }}
            </span>
        </q-td>
    """)

    if len(failures) > 100:
        ui.label(f"Showing first 100 of {len(failures)} differences.") \
            .classes("text-xs mt-2").style(f"color: {t['text_muted']};")


def _format_value(val: str) -> str:
    """Format a numeric value for display."""
    if not val:
        return "—"
    try:
        num = float(val.replace(",", ""))
        if abs(num) >= 1e6:
            return f"${num / 1e6:,.2f}M"
        elif abs(num) >= 1000:
            return f"${num:,.0f}"
        elif num == 0:
            return "$0"
        else:
            return f"${num:,.2f}"
    except (ValueError, TypeError):
        return val[:20] if len(val) > 20 else val


def _render_empty(t: dict, has_report: bool):
    """Empty state — no prior year loaded."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("compare_arrows").classes("text-5xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label("Rollover analysis requires two years").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")

        if has_report:
            msg = ("A review is loaded but no Prior Year XML was provided. "
                   "Go to Home, clear the analysis, and upload both CY and PY XML files "
                   "to enable year-over-year rollover comparison.")
        else:
            msg = ("Upload both a Current Year and Prior Year XML from the Home page "
                   "to compare PY ending balances against CY beginning balances.")

        ui.label(msg).classes("text-sm text-center max-w-lg") \
            .style(f"color: {t['text_secondary']};")

        ui.button("Go to Home", icon="home",
                  on_click=lambda: ui.navigate.to("/")) \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")


def _render_error(t: dict):
    """Error generating reports."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("error_outline").classes("text-5xl") \
            .style(f"color: {t['error']}; opacity: 0.5;")
        ui.label("Could not generate rollover reports").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(
            "The prior year XML may not be compatible with the current year, "
            "or one of the files may have parsing issues."
        ).classes("text-sm text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

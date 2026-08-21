"""Reconciliation page — workbook vs XML field-by-field comparison."""

import tempfile
from pathlib import Path

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state


def render():
    """Render the reconciliation page."""
    t = get_theme()
    s = get_state()

    # ── Header ──
    with ui.row().classes("w-full items-center justify-between mb-6 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Reconciliation").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label("Compare workbook data against XML return — field by field") \
                .classes("text-sm").style(f"color: {t['text_secondary']};")

    # ── Config Panel (glass) ──
    with ui.card().classes("w-full glass-card animate-fade-up stagger-2").style(
        f"background: {t['glass_bg']}; "
        f"border: 1px solid {t['glass_border']}; "
        f"border-radius: 16px; padding: 24px;"
    ):
        ui.label("Configuration").classes("mythos-label mb-4")

        with ui.row().classes("w-full gap-6 items-end"):
            # XML source (auto-detected from review)
            with ui.column().classes("flex-1 gap-2"):
                ui.label("XML Source").classes("text-xs font-semibold") \
                    .style(f"color: {t['text_secondary']};")
                if s.current_xml:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("check_circle").classes("text-sm") \
                            .style(f"color: {t['success']};")
                        ui.label(s.current_xml.name).classes("text-sm mythos-mono") \
                            .style(f"color: {t['success']};")
                    if s.report:
                        ui.label(
                            f"Auto-detected from review ({s.report.client_name} · "
                            f"FY{s.report.tax_year})"
                        ).classes("text-xs").style(f"color: {t['text_muted']};")
                else:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning").classes("text-sm") \
                            .style(f"color: {t['sev_medium']};")
                        ui.label("No XML loaded — run a review first") \
                            .classes("text-sm") \
                            .style(f"color: {t['text_muted']};")
                    ui.button("Go to XML Check", icon="upload_file",
                              on_click=lambda: ui.navigate.to("/review")) \
                        .props("flat dense size=sm") \
                        .style(f"color: {t['accent']};")

            # Workbook upload
            with ui.column().classes("flex-1 gap-2"):
                ui.label("Excel Workbook").classes("text-xs font-semibold") \
                    .style(f"color: {t['text_secondary']};")
                wb_upload = ui.upload(
                    label="Upload .xlsx",
                    auto_upload=True,
                    on_upload=lambda e: _handle_wb_upload(e),
                ).classes("w-full").props("accept=.xlsx,.xls dense flat bordered")

            # Tolerance
            with ui.column().classes("w-32 gap-2"):
                ui.label("Tolerance ($)").classes("text-xs font-semibold") \
                    .style(f"color: {t['text_secondary']};")
                tolerance_input = ui.number(value=1.0, min=0, step=0.5) \
                    .classes("w-full").props("dense outlined")

        # Schedule filter
        with ui.row().classes("w-full gap-3 mt-4 items-end"):
            ui.label("Schedules:").classes("text-xs") \
                .style(f"color: {t['text_muted']};")
            schedule_select = ui.select(
                options=["All", "Schedule H", "Schedule I-1", "Schedule J",
                         "Schedule E", "Schedule F"],
                value="All",
            ).classes("w-48").props("dense outlined")

            ui.element("div").classes("flex-1")

            # Run button
            ui.button("Run Reconciliation", icon="compare_arrows",
                      on_click=lambda: _handle_reconcile(tolerance_input.value, schedule_select.value)) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

    # ── Results Area ──
    results_container = ui.column().classes("w-full mt-6 animate-fade-up stagger-3")

    # Store refs in module-level for handler access
    _page_state["results_container"] = results_container
    _page_state["tolerance_input"] = tolerance_input


# ─── PAGE STATE ─────────────────────────────────────────────────────────────

_page_state: dict = {
    "workbook_path": None,
    "results_container": None,
    "tolerance_input": None,
}


def _handle_wb_upload(e):
    """Handle workbook upload."""
    tmp = Path(tempfile.gettempdir()) / e.name
    tmp.write_bytes(e.content.read())
    _page_state["workbook_path"] = tmp
    ui.notify(f"Workbook: {e.name}", type="info")


async def _handle_reconcile(tolerance: float, schedule_filter: str):
    """Run reconciliation via MythosService."""
    from lab.mythos_ui.services.bridge import get_state, run_reconcile
    from lab.mythos_ui.components import ProgressOverlay

    s = get_state()
    wb_path = _page_state.get("workbook_path")

    if not s.current_xml:
        ui.notify("Load an XML first (run a review)", type="warning")
        return
    if not wb_path:
        ui.notify("Upload a workbook first", type="warning")
        return

    schedules = None
    if schedule_filter != "All":
        sch_map = {
            "Schedule H": "IRS5471ScheduleH",
            "Schedule I-1": "IRS5471ScheduleI1",
            "Schedule J": "IRS5471ScheduleJ",
            "Schedule E": "IRS5471ScheduleE",
            "Schedule F": "IRS5471ScheduleF",
        }
        schedules = [sch_map.get(schedule_filter, schedule_filter)]

    overlay = ProgressOverlay()
    overlay.show()

    result = await run_reconcile(
        xml_path=s.current_xml,
        workbook_path=wb_path,
        tolerance=tolerance,
        schedules=schedules,
    )

    overlay.hide()

    container = _page_state.get("results_container")
    if container:
        container.clear()
        with container:
            _render_results(result)


def _render_results(result):
    """Render reconciliation results."""
    t = get_theme()

    if not result.success:
        ui.notify(f"Reconciliation failed: {result.message}", type="negative")
        return

    # ── KPI Cards ──
    with ui.row().classes("w-full gap-4 mb-6 animate-fade-up"):
        _result_kpi(t, str(result.total_comparisons), "Total Comparisons", t["info"])
        _result_kpi(t, str(result.pass_count), "Passed", t["success"])
        _result_kpi(t, str(result.fail_count), "Failed",
                    t["error"] if result.fail_count > 0 else t["success"])
        _result_kpi(t, f"{result.pass_rate:.0%}", "Pass Rate",
                    t["success"] if result.pass_rate >= 0.95 else t["error"])

    # ── Failures Table ──
    if result.failures is not None and not result.failures.empty:
        with ui.column().classes("w-full animate-fade-up"):
            ui.label(f"Failures ({result.fail_count})").classes("mythos-label mb-3")

            columns = [
                {"name": col, "label": col.replace("_", " ").title(),
                 "field": col, "align": "left", "sortable": True}
                for col in result.failures.columns[:8]
            ]

            rows = result.failures.head(100).to_dict("records")
            for i, row in enumerate(rows):
                row["_id"] = i
                for k, v in row.items():
                    if v != v:  # NaN check
                        row[k] = "—"

            # Pick first 2 text columns as filterable
            filter_cols = {}
            for col in columns[:3]:
                field = col["field"]
                sample_vals = {str(r.get(field, "")) for r in rows
                               if r.get(field) and r.get(field) != "—"}
                if len(sample_vals) <= 50:
                    filter_cols[field] = col["label"]
            if filter_cols:
                strip = TableFilterStrip(
                    filterable_columns=filter_cols,
                    all_rows=rows,
                )
                strip.render(t)
                display_rows = strip.filtered_rows
            else:
                strip = None
                display_rows = rows

            table = ui.table(
                columns=columns,
                rows=display_rows,
                row_key="_id",
                pagination={"rowsPerPage": 25},
            ).classes("w-full").props("dense flat bordered separator=cell virtual-scroll")
            if strip:
                strip.bind(table)

            table.style(
                f"background: {t['glass_bg']}; "
                f"backdrop-filter: blur(10px); "
                f"border: 1px solid {t['glass_border']}; "
                f"border-radius: 12px; max-height: 50vh;"
            )
    else:
        with ui.column().classes("w-full items-center py-8 animate-fade-up"):
            ui.icon("check_circle").classes("text-4xl") \
                .style(f"color: {t['success']};")
            ui.label("Perfect match — all fields reconciled") \
                .classes("text-sm mt-2") \
                .style(f"color: {t['success']};")

    # Export button
    with ui.row().classes("w-full justify-end mt-4"):
        ui.button("Export Results", icon="download",
                  on_click=lambda: _handle_export_reconcile()) \
            .props("flat dense") \
            .style(f"color: {t['text_secondary']};")


def _result_kpi(t: dict, value: str, label: str, color: str):
    """Compact KPI for reconciliation results."""
    with ui.card().classes("flex-1 hover-lift").style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(10px); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-top: 2px solid {color}; "
        f"border-radius: 12px; padding: 16px 20px;"
    ):
        ui.label(value).classes("text-2xl font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("mythos-label mt-0.5")


async def _handle_export_reconcile():
    """Export reconciliation results."""
    ui.notify("Export not yet implemented for reconciliation", type="info")

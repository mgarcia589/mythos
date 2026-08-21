"""PDF Check page — Cross-validate OIT PDFs against XML e-file data."""

import asyncio
import tempfile
from pathlib import Path

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.components import notify


SCHEDULES = ["J", "F", "H", "I", "I1", "P", "R", "A", "B", "C", "E", "G"]


def render():
    """Render the PDF check page."""
    t = get_theme()
    s = get_state()

    if s.pdf_result and s.pdf_result.success:
        _render_results(t, s)
        return

    _render_upload(t, s)


# ─── UPLOAD STATE ─────────────────────────────────────────────────────────────

def _render_upload(t: dict, s):
    """Upload state — PDF + XML + schedule selection."""
    with ui.column().classes("w-full items-center justify-center py-8 gap-5 animate-fade-up"):
        ui.icon("picture_as_pdf").classes("text-5xl") \
            .style(f"color: {t['accent']}; opacity: 0.7;")

        ui.label("PDF Cross-Validation").classes("text-lg font-bold") \
            .style(f"color: {t['text_primary']};")

        ui.label(
            "Upload an OIT-generated PDF and compare it against the XML e-file "
            "to detect phantoms, mismatches, and missing entries."
        ).classes("text-sm text-center max-w-lg") \
            .style(f"color: {t['text_secondary']};")

        # Upload cards row
        with ui.row().classes("gap-4 mt-4 items-stretch"):
            _pdf_upload_card(t, s)
            _xml_upload_card(t, s)

        # Schedule + tolerance row
        with ui.row().classes("gap-4 mt-4 items-end"):
            schedule_select = ui.select(
                options=SCHEDULES,
                value="J",
                label="Schedule",
            ).classes("w-32").props("dense outlined")
            schedule_select.bind_value_to(s, "_pdf_schedule", forward=lambda v: v)

            tolerance_input = ui.number(
                label="Tolerance ($)",
                value=10.0,
                min=0, max=1000, step=1,
            ).classes("w-32").props("dense outlined")

        # Run button
        ui.button("Run Validation", icon="play_circle",
                  on_click=lambda: _run_validation(
                      schedule_select.value, tolerance_input.value)) \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"padding: 10px 28px; border-radius: 6px; font-size: 0.85rem;") \
            .classes("mt-4")

        # Info strip
        ui.separator().classes("w-48 my-4").style(f"background: {t['border']}30;")
        with ui.row().classes("gap-6"):
            _value_prop(t, "find_in_page", "12 schedules", "A through R")
            _value_prop(t, "compare", "3 checks", "Phantom · Missing · Mismatch")
            _value_prop(t, "download", "Excel export", "One-click report")


def _pdf_upload_card(t: dict, s):
    """Upload card for PDF file."""
    has_file = hasattr(s, '_pdf_path') and s._pdf_path is not None

    with ui.card().classes("glass-card").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}60; "
        f"border-radius: 10px; padding: 20px; width: 280px; "
        f"display: flex; flex-direction: column;"
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("picture_as_pdf").style(f"color: {t['accent']}; font-size: 1rem;")
            ui.label("PDF File").classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.badge("Required", color="transparent").props("dense") \
                .style(f"color: {t['error']}; border: 1px solid {t['error']}40; font-size: 0.55rem;")

        ui.label("OIT-generated PDF export for the schedule to validate.") \
            .classes("text-xs") \
            .style(f"color: {t['text_muted']}; min-height: 32px;")

        ui.space()

        upload = ui.upload(
            label="Drop .pdf file here",
            auto_upload=True,
            on_upload=_handle_pdf_upload,
        ).classes("mythos-upload w-full").props("accept=.pdf dense flat")
        upload.style(
            f"background: {t['bg_main']}; "
            f"border: 1.5px dashed {t['success'] if has_file else t['border']}; "
            f"border-radius: 8px; min-height: 72px;"
        )

        if has_file:
            with ui.row().classes("items-center gap-1 mt-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.8rem;")
                ui.label(s._pdf_path.name).classes("text-xs") \
                    .style(f"color: {t['success']};")


def _xml_upload_card(t: dict, s):
    """Upload card for XML file — or show already-loaded XML."""
    has_xml = s.current_xml is not None
    has_dedicated = hasattr(s, '_pdf_xml_path') and s._pdf_xml_path is not None

    with ui.card().classes("glass-card").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 20px; width: 280px; "
        f"display: flex; flex-direction: column;"
    ):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.icon("description").style(f"color: {t['success']}; font-size: 1rem;")
            ui.label("XML File").classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.badge("Required", color="transparent").props("dense") \
                .style(f"color: {t['error']}; border: 1px solid {t['error']}40; font-size: 0.55rem;")

        if has_xml:
            ui.label(
                f"Using loaded XML: {s.current_xml.name}"
            ).classes("text-xs") \
                .style(f"color: {t['success']}; min-height: 32px;")
        else:
            ui.label("XML e-file to compare against.") \
                .classes("text-xs") \
                .style(f"color: {t['text_muted']}; min-height: 32px;")

        ui.space()

        upload = ui.upload(
            label="Drop .xml file here (or use loaded CY)",
            auto_upload=True,
            on_upload=_handle_xml_upload,
        ).classes("mythos-upload w-full").props("accept=.xml dense flat")
        upload.style(
            f"background: {t['bg_main']}; "
            f"border: 1.5px dashed {t['success'] if (has_xml or has_dedicated) else t['border']}; "
            f"border-radius: 8px; min-height: 72px;"
        )

        if has_dedicated:
            with ui.row().classes("items-center gap-1 mt-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.8rem;")
                ui.label(s._pdf_xml_path.name).classes("text-xs") \
                    .style(f"color: {t['success']};")


def _value_prop(t: dict, icon: str, title: str, subtitle: str):
    """Mini value proposition."""
    with ui.column().classes("items-center gap-1"):
        ui.icon(icon).classes("text-lg") \
            .style(f"color: {t['accent']}; opacity: 0.7;")
        ui.label(title).classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(subtitle).classes("text-xs") \
            .style(f"color: {t['text_muted']};")


# ─── RESULTS STATE ────────────────────────────────────────────────────────────

def _render_results(t: dict, s):
    """Results view with KPIs and discrepancy table."""
    result = s.pdf_result
    report = s.pdf_report
    metrics = result.metrics

    total = metrics.get("total_comparisons", 0)
    ok = metrics.get("ok_count", 0)
    phantoms = metrics.get("phantom_count", 0)
    missing = metrics.get("missing_count", 0)
    mismatches = metrics.get("mismatch_count", 0)
    entities = metrics.get("entities_checked", 0)
    pass_rate = ok / total * 100 if total > 0 else 0

    # Header
    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("PDF Cross-Validation").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label(
                f"Schedule {report.schedule} · {report.pdf_source} vs {report.xml_source} · "
                f"{entities} entities · {result.duration_display}"
            ).classes("text-sm").style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-2"):
            ui.button("Export Excel", icon="download",
                      on_click=lambda: _export_excel()) \
                .props("flat no-caps dense") \
                .style(f"color: {t['accent']};")
            ui.button("Clear", icon="restart_alt",
                      on_click=lambda: _clear_results()) \
                .props("flat no-caps dense") \
                .style(f"color: {t['text_muted']};")

    # KPI Strip
    with ui.row().classes("w-full gap-4 mb-6 animate-fade-up stagger-2"):
        _kpi(t, str(total), "Comparisons", t["info"])
        _kpi(t, f"{pass_rate:.0f}%", "Pass Rate",
             t["success"] if pass_rate >= 95 else t["accent"] if pass_rate >= 80 else t["sev_high"])
        _kpi(t, str(ok), "OK", t["success"])
        _kpi(t, str(phantoms), "Phantoms",
             t["sev_high"] if phantoms > 0 else t["success"])
        _kpi(t, str(missing), "Missing",
             t["accent"] if missing > 0 else t["success"])
        _kpi(t, str(mismatches), "Mismatches",
             t["accent"] if mismatches > 0 else t["success"])

    # Warnings
    if result.warnings:
        with ui.expansion(f"{len(result.warnings)} warnings").classes("w-full mb-4") \
                .style(f"color: {t['accent']};"):
            for w in result.warnings[:20]:
                ui.label(f"⚠ {w}").classes("text-xs") \
                    .style(f"color: {t['accent']};")

    # Discrepancy table
    discrepancies = report.discrepancies if report else []
    if discrepancies:
        _discrepancy_card(t, discrepancies)
    else:
        with ui.card().classes("w-full glass-card animate-fade-up").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-left: 3px solid {t['success']}; "
            f"border-radius: 10px; padding: 20px;"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 1.2rem;")
                ui.label("All comparisons passed — PDF matches XML within tolerance.") \
                    .classes("text-sm font-semibold") \
                    .style(f"color: {t['success']};")


def _kpi(t: dict, value: str, label: str, color: str):
    """KPI card."""
    with ui.card().classes("flex-1 min-w-[100px] hover-lift").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-top: 2px solid {color}; border-radius: 10px; padding: 14px 16px;"
    ):
        ui.label(value).classes("text-lg font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs mt-0.5") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _discrepancy_card(t: dict, discrepancies: list):
    """Discrepancy table card."""
    with ui.card().classes("w-full glass-card animate-fade-up").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-left: 3px solid {t['sev_high']}; "
        f"border-radius: 10px; padding: 16px 20px;"
    ):
        with ui.row().classes("items-center gap-3 mb-3"):
            ui.icon("error").style(f"color: {t['sev_high']}; font-size: 1.1rem;")
            ui.label(f"{len(discrepancies)} Discrepancies Found") \
                .classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary']};")

        _discrepancy_table(t, discrepancies)


def _discrepancy_table(t: dict, discrepancies: list):
    """Render discrepancy table."""
    columns = [
        {"name": "status", "label": "Status", "field": "status", "align": "center", "sortable": True},
        {"name": "severity", "label": "Sev", "field": "severity", "align": "center", "sortable": True},
        {"name": "entity", "label": "Entity", "field": "entity", "align": "left", "sortable": True},
        {"name": "ref", "label": "Ref ID", "field": "ref", "align": "left"},
        {"name": "basket", "label": "Pool/Basket", "field": "basket", "align": "left"},
        {"name": "pdf_val", "label": "PDF Value", "field": "pdf_val", "align": "right"},
        {"name": "xml_val", "label": "XML Value", "field": "xml_val", "align": "right"},
        {"name": "delta", "label": "Delta", "field": "delta", "align": "right", "sortable": True},
    ]

    rows = []
    for i, d in enumerate(discrepancies[:200]):
        rows.append({
            "id": str(i),
            "status": d.status,
            "severity": d.severity,
            "entity": (d.entity_name[:28] + "…") if len(d.entity_name) > 30 else d.entity_name,
            "ref": d.reference_id or "—",
            "basket": d.field_description[:30] if d.field_description else d.basket,
            "pdf_val": _fmt(d.pdf_value),
            "xml_val": _fmt(d.xml_value),
            "delta": _fmt(d.delta),
            "delta_raw": d.delta,
        })

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
        pagination={"rowsPerPage": 25, "sortBy": "delta", "descending": True},
    ).classes("w-full").props("dense flat bordered separator=cell")

    table.style(
        f"background: {t['bg_card']}; "
        f"border: 1px solid {t['border']}30; "
        f"border-radius: 8px;"
    )

    # Color-code status column
    table.add_slot("body-cell-status", """
        <q-td :props="props">
            <q-badge :color="props.row.status === 'PHANTOM' ? 'red' :
                            props.row.status === 'MISSING' ? 'amber' :
                            props.row.status === 'MISMATCH' ? 'orange' : 'green'"
                     :label="props.row.status" dense outline />
        </q-td>
    """)

    # Color-code delta
    table.add_slot("body-cell-delta", """
        <q-td :props="props">
            <span :style="props.row.delta_raw > 0 ? 'color: #ef4444; font-weight: 600' :
                         props.row.delta_raw < 0 ? 'color: #22c55e; font-weight: 600' :
                         'color: inherit'">
                {{ props.row.delta }}
            </span>
        </q-td>
    """)

    if len(discrepancies) > 200:
        ui.label(f"Showing first 200 of {len(discrepancies)} discrepancies.") \
            .classes("text-xs mt-2").style(f"color: {t['text_muted']};")


def _fmt(val: float) -> str:
    """Format numeric value for display."""
    if val == 0:
        return "$0"
    if abs(val) >= 1e6:
        return f"${val / 1e6:,.2f}M"
    if abs(val) >= 1000:
        return f"${val:,.0f}"
    return f"${val:,.2f}"


# ─── HANDLERS ─────────────────────────────────────────────────────────────────

async def _handle_pdf_upload(e):
    """Handle PDF file upload."""
    s = get_state()
    tmp = Path(tempfile.gettempdir()) / e.file.name
    await e.file.save(tmp)
    s._pdf_path = tmp
    notify("PDF loaded", level="success", caption=e.file.name)
    ui.navigate.to("/pdf-check")


async def _handle_xml_upload(e):
    """Handle XML file upload for PDF validation."""
    s = get_state()
    tmp = Path(tempfile.gettempdir()) / e.file.name
    await e.file.save(tmp)
    s._pdf_xml_path = tmp
    notify("XML loaded", level="success", caption=e.file.name)
    ui.navigate.to("/pdf-check")


async def _run_validation(schedule: str, tolerance: float):
    """Run PDF validation with progress overlay."""
    from lab.mythos_ui.components import ProgressOverlay
    from lab.pdf_validator import PDFValidator

    s = get_state()

    # Determine PDF path
    pdf_path = getattr(s, '_pdf_path', None)
    if not pdf_path:
        ui.notify("Upload a PDF file first", type="warning")
        return

    # Determine XML path (dedicated upload takes priority over global)
    xml_path = getattr(s, '_pdf_xml_path', None) or s.current_xml
    if not xml_path:
        ui.notify("Upload an XML file or load one from Home first", type="warning")
        return

    s.progress = 0.0
    s.progress_msg = "Starting PDF validation..."

    overlay = ProgressOverlay()
    overlay.show()

    try:
        def progress_callback(stage: str, progress: float, message: str):
            s.progress = progress
            s.progress_msg = message

        validator = PDFValidator(
            pdf_path=pdf_path,
            xml_path=xml_path,
            schedule=schedule,
            tolerance=tolerance,
        )

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: validator.run(progress=progress_callback),
        )

        s.pdf_result = result
        s.pdf_report = validator.report
        s._pdf_validator = validator
        s.progress = 1.0
        s.progress_msg = "Complete"

        if result.success:
            issues = (result.metrics.get("phantom_count", 0) +
                      result.metrics.get("missing_count", 0) +
                      result.metrics.get("mismatch_count", 0))
            if issues > 0:
                ui.notify(f"Validation complete: {issues} discrepancies found", type="warning")
            else:
                ui.notify("Validation complete: all checks passed", type="positive")
        else:
            ui.notify(f"Validation failed: {result.message}", type="negative")

    except Exception as e:
        ui.notify(f"Error: {e}", type="negative")
    finally:
        overlay.hide()

    ui.navigate.to("/pdf-check")


async def _export_excel():
    """Export validation results to Excel."""
    s = get_state()
    validator = getattr(s, '_pdf_validator', None)
    if not validator or not validator.report:
        ui.notify("No validation results to export", type="warning")
        return

    output_path = Path(tempfile.gettempdir()) / f"pdf-validation-sch{validator.schedule.lower()}.xlsx"

    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: validator.to_excel(output_path),
        )
        ui.notify(f"Exported: {output_path.name}", type="positive")
    except Exception as e:
        ui.notify(f"Export failed: {e}", type="negative")


def _clear_results():
    """Clear PDF validation state."""
    s = get_state()
    s.pdf_result = None
    s.pdf_report = None
    s._pdf_validator = None
    s._pdf_path = None
    s._pdf_xml_path = None
    ui.navigate.to("/pdf-check")

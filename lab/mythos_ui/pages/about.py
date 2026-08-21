"""About page — Tool capabilities, architecture, and competitive positioning."""

from nicegui import ui

from lab.mythos_ui import __version__
from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.layout import LOGO_SVG


def render():
    """Render the about page content."""
    t = get_theme()

    with ui.scroll_area().classes("w-full").style("height: calc(100vh - 120px);"):
        with ui.column().classes("w-full gap-4 max-w-5xl mx-auto pb-8"):

            # ── Hero ──
            with ui.row().classes("w-full items-center gap-4 animate-fade-up"):
                ui.html(LOGO_SVG.replace('width="16"', 'width="36"')
                        .replace('height="18"', 'height="40"')) \
                    .style(f"color: {t['accent']};")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label("Mythos").classes("text-xl font-bold") \
                            .style(f"color: {t['text_primary']};")
                        ui.badge(f"v{__version__}").props("outline dense") \
                            .style(f"color: {t['accent']}; border-color: {t['accent']}50; "
                                   f"font-size: 0.6rem;")
                    ui.label("Automated Compliance Engine for IRS Form 5471") \
                        .classes("text-xs") \
                        .style(f"color: {t['text_muted']};")

            # ── Description ──
            with ui.card().classes("w-full glass-card animate-fade-up stagger-1").style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-radius: 10px; padding: 20px;"
            ):
                ui.label(
                    "Automated compliance engine for US international tax returns. Parses IRS "
                    "e-file XML (Forms 5471, 8858, 8865), executes 32 multi-dimensional "
                    "validations, and detects flow-through inconsistencies, missing schedules, "
                    "outlier amounts, and year-over-year rollover breaks — all in under 3 seconds "
                    "per entity, without access to the preparer workbook."
                ).classes("text-sm leading-relaxed") \
                    .style(f"color: {t['text_secondary']};")

                ui.label(
                    "Supports end-to-end validation: XML review, workbook-to-XML reconciliation, "
                    "PDF-to-XML cross-check (detecting phantom data in OIT reports), and "
                    "independent formula audit of preparer workbooks. Processes any return "
                    "regardless of software origin (ONESOURCE, GoSystem, Corptax) with "
                    "severity-ranked findings exportable to Excel, PDF, HTML, and CSV."
                ).classes("text-sm leading-relaxed mt-2") \
                    .style(f"color: {t['text_secondary']};")

            # ── Stats row ──
            with ui.row().classes("w-full gap-3 animate-fade-up stagger-2"):
                _stat_card(t, "< 3s", "Per entity", t["accent"])
                _stat_card(t, "32", "Checks", t["info"])
                _stat_card(t, "103", "Fields parsed", t["success"])
                _stat_card(t, "4", "Export formats", t["text_primary"])
                _stat_card(t, "3", "Validation layers", t["error"])

            # ── PDF Validator ──
            with ui.card().classes("w-full glass-card animate-fade-up stagger-3").style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-left: 3px solid {t['accent']}; "
                f"border-radius: 10px; padding: 20px;"
            ):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.icon("picture_as_pdf").style(f"color: {t['accent']}; font-size: 1.2rem;")
                    ui.label("PDF Cross-Validation").classes("text-sm font-bold") \
                        .style(f"color: {t['text_primary']};")
                    ui.badge("Candado", color="transparent").props("dense") \
                        .style(f"color: {t['accent']}; border: 1px solid {t['accent']}40; "
                               f"font-size: 0.55rem;")

                ui.label(
                    "Independent second check that cross-validates OIT-generated PDFs against "
                    "the XML e-file. The XML is a point-in-time snapshot — if a value is modified "
                    "in OIT after export (or the export has a bug), the XML alone cannot detect "
                    "the discrepancy. The PDF reflects OIT's current state, so comparing both "
                    "creates a validation lock:"
                ).classes("text-sm leading-relaxed") \
                    .style(f"color: {t['text_secondary']};")

                ui.label(
                    "FULLY VALIDATED = XML Rollover PASS  +  PDF vs XML PASS"
                ).classes("text-xs font-semibold mythos-mono mt-2 px-3 py-2 rounded") \
                    .style(f"color: {t['accent']}; background: {t['bg_main']}; "
                           f"border: 1px solid {t['accent']}30;")

                ui.separator().classes("my-3").style(f"background: {t['border']}30;")

                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("flex-1 gap-2"):
                        ui.label("Detects").classes("text-xs font-semibold") \
                            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                                   f"letter-spacing: 0.05em; font-size: 0.6rem;")
                        _pdf_detect_row(t, "PHANTOM", "Value in PDF but absent in XML — most dangerous",
                                        t["error"])
                        _pdf_detect_row(t, "MISSING", "Value in XML but absent in PDF",
                                        t["accent"])
                        _pdf_detect_row(t, "MISMATCH", "Both have values but differ beyond tolerance",
                                        t["info"])

                    with ui.column().classes("flex-1 gap-2"):
                        ui.label("Capabilities").classes("text-xs font-semibold") \
                            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                                   f"letter-spacing: 0.05em; font-size: 0.6rem;")
                        _pdf_cap_row(t, "12 schedules supported (A through R)")
                        _pdf_cap_row(t, "Batch processing (~70 entities in <30s)")
                        _pdf_cap_row(t, "Configurable tolerance (default $10)")
                        _pdf_cap_row(t, "Excel report with 4 sheets (Summary, Phantoms, Mismatches, All)")
                        _pdf_cap_row(t, "pdfplumber extraction (text-based, no OCR)")

            # ── Two-column layout: Dimensions + Tech ──
            with ui.row().classes("w-full gap-4 animate-fade-up stagger-4"):
                # Dimensions
                with ui.card().classes("flex-1 glass-card").style(
                    f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                    f"border-radius: 10px; padding: 16px;"
                ):
                    ui.label("Review Dimensions").style(
                        f"color: {t['text_muted']}; font-size: 0.65rem; "
                        f"font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;")

                    _dim(t, "Flow-Through", "8", "Cross-schedule consistency", t["info"])
                    _dim(t, "Completeness", "6", "Required fields & schedules", t["accent"])
                    _dim(t, "Reasonableness", "7", "Outlier & anomaly detection", t["success"])
                    _dim(t, "Rollover", "11", "YoY balance continuity", t["error"])

                # Tech stack
                with ui.card().classes("flex-1 glass-card").style(
                    f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                    f"border-radius: 10px; padding: 16px;"
                ):
                    ui.label("Stack").style(
                        f"color: {t['text_muted']}; font-size: 0.65rem; "
                        f"font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;")

                    _tech_row(t, "language", "Python 3.11+", "Core engine")
                    _tech_row(t, "code", "lxml + pandas", "XML parsing & analysis")
                    _tech_row(t, "desktop_windows", "NiceGUI + pywebview", "Desktop UI")
                    _tech_row(t, "insert_chart", "Plotly", "Visualizations")
                    _tech_row(t, "table_chart", "openpyxl", "Excel export")

            # ── Comparison Section ──
            with ui.card().classes("w-full glass-card animate-fade-up stagger-5").style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-radius: 10px; padding: 16px;"
            ):
                ui.label("How It Compares").style(
                    f"color: {t['text_muted']}; font-size: 0.65rem; "
                    f"font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;")

                # Table header
                with ui.row().classes("w-full mt-3 pb-2").style(
                    f"border-bottom: 1px solid {t['border']}40;"
                ):
                    ui.label("Capability").classes("text-xs font-semibold flex-1") \
                        .style(f"color: {t['text_secondary']}; min-width: 160px;")
                    ui.label("Mythos").classes("text-xs font-semibold text-center") \
                        .style(f"color: {t['accent']}; width: 80px;")
                    ui.label("Bolt / Alteryx").classes("text-xs font-semibold text-center") \
                        .style(f"color: {t['text_muted']}; width: 100px;")
                    ui.label("OIT Diagnostics").classes("text-xs font-semibold text-center") \
                        .style(f"color: {t['text_muted']}; width: 100px;")

                _compare_row(t, "Execution speed", "< 3s", "2-5 min", "30-60s")
                _compare_row(t, "Checks per entity", "32", "~8", "~12")
                _compare_row(t, "Year-over-year rollover", "yes", "partial", "no")
                _compare_row(t, "Works without workbook", "yes", "no", "yes")
                _compare_row(t, "Multi-software XML support", "yes", "no", "yes")
                _compare_row(t, "Severity-ranked output", "yes", "no", "limited")
                _compare_row(t, "Exportable findings report", "yes", "manual", "limited")
                _compare_row(t, "Desktop GUI", "yes", "no", "browser")
                _compare_row(t, "License cost", "Internal", "Alteryx seat", "OIT license")

            # ── Architecture (layered diagram) ──
            with ui.card().classes("w-full glass-card animate-fade-up stagger-6").style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-radius: 10px; padding: 16px;"
            ):
                ui.label("Architecture").style(
                    f"color: {t['text_muted']}; font-size: 0.65rem; "
                    f"font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;")

                with ui.column().classes("w-full gap-2 mt-3"):
                    _arch_layer(t, "Presentation", "NiceGUI + Quasar + Tailwind",
                                "desktop_windows", t["accent"],
                                ["pages/", "theme.py", "shortcuts.py", "components.py"])
                    _arch_arrow(t)
                    _arch_layer(t, "Service Bridge", "Async orchestration + progress",
                                "sync_alt", t["info"], ["bridge.py", "state management"])
                    _arch_arrow(t)
                    _arch_layer(t, "Core Engine", "MythosService",
                                "hub", t["success"],
                                ["ReviewEngine (32 checks)", "EFileParser (lxml)",
                                 "Reconciler", "Exporter"])
                    _arch_arrow(t)
                    _arch_layer(t, "Data Layer", "IRS e-file XML → DataFrames",
                                "storage", t["text_muted"],
                                ["pandas", "openpyxl", "lxml"])

            # ── Keyboard Shortcuts ──
            with ui.card().classes("w-full glass-card animate-fade-up stagger-7").style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-radius: 10px; padding: 16px;"
            ):
                ui.label("Keyboard Shortcuts").style(
                    f"color: {t['text_muted']}; font-size: 0.65rem; "
                    f"font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;")

                with ui.row().classes("w-full gap-6 mt-3"):
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label("Navigation").classes("text-xs font-semibold mb-1") \
                            .style(f"color: {t['text_secondary']};")
                        _shortcut(t, "Ctrl+1", "Home")
                        _shortcut(t, "Ctrl+2", "XML Check")
                        _shortcut(t, "Ctrl+3", "PDF Check")
                        _shortcut(t, "Ctrl+4", "Findings")
                        _shortcut(t, "Ctrl+5", "Entities")
                        _shortcut(t, "Ctrl+6", "Rollover")
                        _shortcut(t, "Ctrl+7", "Reconcile")
                        _shortcut(t, "Ctrl+8", "History")
                        _shortcut(t, "Ctrl+9", "About")
                    with ui.column().classes("flex-1 gap-1"):
                        ui.label("Actions").classes("text-xs font-semibold mb-1") \
                            .style(f"color: {t['text_secondary']};")
                        _shortcut(t, "Ctrl+D", "Toggle theme")
                        _shortcut(t, "Ctrl+E", "Export XLSX")
                        _shortcut(t, "Ctrl+R", "Re-run review")
                        _shortcut(t, "Shift+?", "Help dialog")

            # Footer
            ui.label("Mythos · US International Tax Compliance Engine") \
                .classes("text-xs text-center w-full mt-2") \
                .style(f"color: {t['text_muted']}; opacity: 0.6;")


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _stat_card(t: dict, value: str, label: str, color: str):
    with ui.card().classes("flex-1 min-w-[100px] text-center hover-lift").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}30; "
        f"border-radius: 8px; padding: 12px 8px;"
    ):
        ui.label(value).classes("text-base font-bold") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs mt-0.5") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _dim(t: dict, title: str, count: str, desc: str, color: str):
    with ui.row().classes("w-full items-center gap-2 py-2") \
            .style(f"border-bottom: 1px solid {t['border']}20;"):
        ui.badge(count, color="transparent").props("dense") \
            .style(f"color: {color}; border: 1px solid {color}40; "
                   f"font-size: 0.6rem; min-width: 20px;")
        with ui.column().classes("gap-0 flex-1"):
            ui.label(title).classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.label(desc).classes("text-xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _tech_row(t: dict, icon: str, name: str, role: str):
    with ui.row().classes("w-full items-center gap-2 py-2") \
            .style(f"border-bottom: 1px solid {t['border']}20;"):
        ui.icon(icon).style(f"color: {t['text_muted']}; font-size: 0.85rem;")
        ui.label(name).classes("text-xs font-semibold flex-1") \
            .style(f"color: {t['text_primary']};")
        ui.label(role).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _compare_row(t: dict, capability: str, mythos: str, bolt: str, oit: str):
    is_yes_mythos = mythos.lower() == "yes"
    with ui.row().classes("w-full items-center py-2") \
            .style(f"border-bottom: 1px solid {t['border']}15;"):
        ui.label(capability).classes("text-xs flex-1") \
            .style(f"color: {t['text_secondary']}; min-width: 160px;")
        _compare_cell(t, mythos, is_mythos=True)
        _compare_cell(t, bolt, is_mythos=False)
        _compare_cell(t, oit, is_mythos=False)


def _compare_cell(t: dict, value: str, is_mythos: bool):
    width = "80px" if is_mythos else "100px"
    if value.lower() == "yes":
        color = t["success"] if is_mythos else t["text_muted"]
        icon = "check_circle"
    elif value.lower() == "no":
        color = t["error"] if not is_mythos else t["text_muted"]
        icon = "cancel"
    elif value.lower() in ("partial", "limited", "manual"):
        color = t["text_muted"]
        icon = "remove_circle_outline"
    else:
        color = t["accent"] if is_mythos else t["text_muted"]
        icon = None

    with ui.row().classes("items-center justify-center gap-1") \
            .style(f"width: {width};"):
        if icon:
            ui.icon(icon).style(f"color: {color}; font-size: 0.75rem;")
        ui.label(value).classes("text-xs") \
            .style(f"color: {color}; font-weight: {'600' if is_mythos else '400'};")


def _shortcut(t: dict, key: str, desc: str):
    with ui.row().classes("items-center gap-2"):
        ui.label(key).classes("text-xs mythos-mono px-1.5 py-0.5 rounded") \
            .style(f"background: {t['bg_main']}; color: {t['text_primary']}; "
                   f"border: 1px solid {t['border']}60; font-size: 0.6rem; "
                   f"min-width: 52px; text-align: center;")
        ui.label(desc).classes("text-xs") \
            .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")


def _arch_layer(t: dict, title: str, subtitle: str, icon: str, color: str, modules: list):
    """Render one layer of the architecture diagram."""
    with ui.row().classes("w-full items-center gap-3 p-3 rounded-lg") \
            .style(f"background: {color}08; border: 1px solid {color}25;"):
        ui.icon(icon).style(f"color: {color}; font-size: 1.1rem;")
        with ui.column().classes("gap-0 flex-1"):
            ui.label(title).classes("text-xs font-semibold") \
                .style(f"color: {t['text_primary']};")
            ui.label(subtitle).classes("text-xs") \
                .style(f"color: {t['text_muted']}; font-size: 0.6rem;")
        with ui.row().classes("gap-1 flex-wrap"):
            for mod in modules:
                ui.badge(mod, color="transparent").props("dense") \
                    .style(f"color: {t['text_secondary']}; "
                           f"background: {t['bg_main']}; "
                           f"border: 1px solid {t['border']}40; "
                           f"font-size: 0.55rem; padding: 1px 6px;")


def _arch_arrow(t: dict):
    """Render a connecting arrow between architecture layers."""
    with ui.row().classes("w-full justify-center"):
        ui.icon("arrow_downward") \
            .style(f"color: {t['border']}; font-size: 0.9rem; opacity: 0.6;")


def _pdf_detect_row(t: dict, status: str, desc: str, color: str):
    """Render a PDF detection type row."""
    with ui.row().classes("items-center gap-2"):
        ui.badge(status, color="transparent").props("dense") \
            .style(f"color: {color}; border: 1px solid {color}40; "
                   f"font-size: 0.55rem; min-width: 65px; text-align: center;")
        ui.label(desc).classes("text-xs") \
            .style(f"color: {t['text_secondary']};")


def _pdf_cap_row(t: dict, text: str):
    """Render a PDF capability bullet."""
    with ui.row().classes("items-start gap-2"):
        ui.icon("check").style(f"color: {t['success']}; font-size: 0.7rem; margin-top: 2px;")
        ui.label(text).classes("text-xs") \
            .style(f"color: {t['text_secondary']};")

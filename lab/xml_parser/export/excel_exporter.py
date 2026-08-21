"""Excel Exporter — Premium XlsxWriter-based corporate report generation.

Design principles applied:
- Canvas mode: gridlines hidden, content floats on white
- Typographic hierarchy via font weight and size, not color overload
- Hairline borders only where they aid data scanning
- Numeric columns use tabular alignment and executive formatting
- Auto-fit column widths based on content length
- Strategic color: accent for headers, semantic for severity/status only
"""

from pathlib import Path
from datetime import datetime
from collections import OrderedDict

from lab.xml_parser.core.models import Finding, ReviewReport, RolloverReport, RolloverItem
from lab.xml_parser.export.design_system import DesignSystem as DS


def _auto_fit_columns(worksheet, data_rows: list[list], col_offset: int = 0, min_width: float = 8.0, max_width: float = 45.0):
    """Set column widths based on content length."""
    if not data_rows:
        return
    num_cols = max(len(row) for row in data_rows) if data_rows else 0
    for col_idx in range(num_cols):
        max_len = min_width
        for row in data_rows:
            if col_idx < len(row):
                cell_len = len(str(row[col_idx])) * 1.15
                max_len = max(max_len, cell_len)
        width = min(max_len, max_width)
        worksheet.set_column(col_offset + col_idx, col_offset + col_idx, width)


def _create_formats(workbook) -> dict:
    """Create all reusable formats from the design system."""
    F = DS.FONT_EXCEL
    return {
        "title": workbook.add_format({
            "font_name": F, "font_size": 18, "bold": True,
            "font_color": DS.NAVY, "bottom": 3, "bottom_color": DS.COPPER,
        }),
        "subtitle": workbook.add_format({
            "font_name": F, "font_size": 11, "font_color": DS.SLATE,
        }),
        "section": workbook.add_format({
            "font_name": F, "font_size": 13, "bold": True,
            "font_color": DS.NAVY, "bottom": 2, "bottom_color": DS.COPPER,
        }),
        "meta_label": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.GRAPHITE,
            "bold": True,
        }),
        "meta_value": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
        }),
        "timestamp": workbook.add_format({
            "font_name": F, "font_size": 8, "italic": True,
            "font_color": DS.GRAPHITE,
        }),

        # Table headers
        "th": workbook.add_format({
            "font_name": F, "font_size": 9, "bold": True,
            "font_color": DS.WHITE, "bg_color": DS.NAVY,
            "border": 1, "border_color": DS.NAVY,
            "align": "center", "valign": "vcenter",
            "text_wrap": True,
        }),
        "th_left": workbook.add_format({
            "font_name": F, "font_size": 9, "bold": True,
            "font_color": DS.WHITE, "bg_color": DS.NAVY,
            "border": 1, "border_color": DS.NAVY,
            "align": "left", "valign": "vcenter",
            "text_wrap": True,
        }),
        "th_accent": workbook.add_format({
            "font_name": F, "font_size": 9, "bold": True,
            "font_color": DS.WHITE, "bg_color": DS.COPPER,
            "border": 1, "border_color": DS.COPPER,
            "align": "center", "valign": "vcenter",
        }),

        # Data cells
        "cell": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "cell_alt": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
            "bg_color": DS.CLOUD,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "cell_bold": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
            "bold": True, "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "cell_mono": workbook.add_format({
            "font_name": "Consolas", "font_size": 9, "font_color": DS.NAVY,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),

        # Numeric
        "num": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
            "num_format": "#,##0", "align": "right",
            "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "num_alt": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.NAVY,
            "num_format": "#,##0", "align": "right",
            "bg_color": DS.CLOUD,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "num_danger": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.DANGER,
            "num_format": "#,##0", "align": "right", "bold": True,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),
        "num_muted": workbook.add_format({
            "font_name": F, "font_size": 9, "font_color": DS.GRAPHITE,
            "num_format": "#,##0", "align": "right",
            "bottom": 1, "bottom_color": DS.PEARL,
        }),

        # Status / Severity
        "sev_high": workbook.add_format({
            "font_name": F, "font_size": 8, "bold": True,
            "font_color": DS.WHITE, "bg_color": DS.DANGER,
            "align": "center", "valign": "vcenter",
            "border": 1, "border_color": DS.DANGER,
        }),
        "sev_medium": workbook.add_format({
            "font_name": F, "font_size": 8, "bold": True,
            "font_color": DS.NAVY, "bg_color": DS.WARNING_BG,
            "align": "center", "valign": "vcenter",
            "border": 1, "border_color": DS.WARNING,
        }),
        "sev_low": workbook.add_format({
            "font_name": F, "font_size": 8,
            "font_color": DS.SLATE, "bg_color": DS.INFO_BG,
            "align": "center", "valign": "vcenter",
            "border": 1, "border_color": DS.INFO,
        }),
        "status_ok": workbook.add_format({
            "font_name": F, "font_size": 8, "bold": True,
            "font_color": DS.SUCCESS, "bg_color": DS.SUCCESS_BG,
            "align": "center",
            "border": 1, "border_color": DS.SUCCESS,
        }),
        "status_review": workbook.add_format({
            "font_name": F, "font_size": 8, "bold": True,
            "font_color": DS.DANGER, "bg_color": DS.DANGER_BG,
            "align": "center",
            "border": 1, "border_color": DS.DANGER,
        }),

        # Entity group separator
        "entity_group": workbook.add_format({
            "font_name": F, "font_size": 9, "bold": True,
            "font_color": DS.NAVY, "bg_color": DS.PEARL,
            "left": 3, "left_color": DS.COPPER,
            "bottom": 1, "bottom_color": DS.PEARL,
        }),

        # KPI card formats
        "kpi_value": workbook.add_format({
            "font_name": F, "font_size": 20, "bold": True,
            "font_color": DS.NAVY, "align": "center", "valign": "vcenter",
        }),
        "kpi_label": workbook.add_format({
            "font_name": F, "font_size": 8, "font_color": DS.GRAPHITE,
            "align": "center", "valign": "top",
        }),
        "kpi_danger": workbook.add_format({
            "font_name": F, "font_size": 20, "bold": True,
            "font_color": DS.DANGER, "align": "center", "valign": "vcenter",
        }),
        "kpi_success": workbook.add_format({
            "font_name": F, "font_size": 20, "bold": True,
            "font_color": DS.SUCCESS, "align": "center", "valign": "vcenter",
        }),
    }


def _write_cover_sheet(workbook, fmts: dict, report: ReviewReport, client_name: str, engagement: str, comparison: str):
    """Write the executive summary cover sheet."""
    ws = workbook.add_worksheet("Executive Summary")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 3)    # left gutter
    ws.set_column("B:B", 18)
    ws.set_column("C:C", 18)
    ws.set_column("D:D", 18)
    ws.set_column("E:E", 18)
    ws.set_column("F:F", 18)
    ws.set_column("G:H", 14)

    row = 1

    # Title block
    ws.set_row(row, 30)
    ws.write(row, 1, "Automated Compliance Review", fmts["title"])
    row += 1
    ws.write(row, 1, "Project Mythos — XML-First Review Engine", fmts["subtitle"])
    row += 2

    # Metadata
    from lab.xml_parser import __version__
    meta = [
        ("Client", client_name or "—"),
        ("Engagement", engagement or "—"),
        ("Comparison", comparison or "—"),
        ("Generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Engine", f"v{__version__} — 71 checks"),
    ]
    for label, value in meta:
        ws.write(row, 1, label, fmts["meta_label"])
        ws.write(row, 2, value, fmts["meta_value"])
        row += 1

    row += 2

    # KPI row
    high = sum(1 for f in report.findings if f.severity == "HIGH")
    medium = sum(1 for f in report.findings if f.severity == "MEDIUM")
    entities_hit = len(set(f.entity_code for f in report.findings))
    clean = report.entity_count - entities_hit

    kpis = [
        (str(len(report.findings)), "Total Findings", "kpi_value"),
        (str(high), "High Severity", "kpi_danger"),
        (str(medium), "Medium Severity", "kpi_value"),
        (f"{clean}/{report.entity_count}", "Clean Entities", "kpi_success"),
    ]

    ws.set_row(row, 35)
    ws.set_row(row + 1, 18)
    for i, (val, label, style) in enumerate(kpis):
        col = 1 + i
        ws.write(row, col, val, fmts[style])
        ws.write(row + 1, col, label, fmts["kpi_label"])

    row += 4

    # Findings by category
    ws.write(row, 1, "Findings by Category", fmts["section"])
    row += 1

    by_cat = {}
    for f in report.findings:
        by_cat.setdefault(f.category, {"HIGH": 0, "MEDIUM": 0, "LOW": 0})
        by_cat[f.category][f.severity] += 1

    headers = ["Category", "HIGH", "MEDIUM", "LOW", "Total"]
    for i, h in enumerate(headers):
        ws.write(row, 1 + i, h, fmts["th"] if i > 0 else fmts["th_left"])
    row += 1

    for cat, counts in sorted(by_cat.items()):
        total = sum(counts.values())
        ws.write(row, 1, cat, fmts["cell_bold"])
        ws.write(row, 2, counts["HIGH"], fmts["num_danger"] if counts["HIGH"] else fmts["num_muted"])
        ws.write(row, 3, counts["MEDIUM"], fmts["num"])
        ws.write(row, 4, counts["LOW"], fmts["num_muted"])
        ws.write(row, 5, total, fmts["num"])
        row += 1

    row += 2

    # Top findings
    ws.write(row, 1, "Top Findings (HIGH severity)", fmts["section"])
    row += 1

    top_headers = ["Check", "Entity", "Description", "Delta"]
    for i, h in enumerate(top_headers):
        ws.write(row, 1 + i, h, fmts["th_left"] if i < 3 else fmts["th"])
    row += 1

    for f in report.high_severity()[:15]:
        alt = (row % 2 == 0)
        cell_fmt = fmts["cell_alt"] if alt else fmts["cell"]
        num_fmt = fmts["num_alt"] if alt else fmts["num"]
        ws.write(row, 1, f.check_id, fmts["cell_mono"])
        ws.write(row, 2, f"{f.entity_name[:25]} ({f.entity_code})", cell_fmt)
        ws.write(row, 3, f.description[:55], cell_fmt)
        if f.delta:
            ws.write_number(row, 4, f.delta, fmts["num_danger"])
        else:
            ws.write(row, 4, "—", fmts["num_muted"])
        row += 1

    # Footer
    row += 2
    from lab.xml_parser.core.config import get_config
    _cfg = get_config()
    _footer_parts = ["Generated by Project Mythos"]
    if _cfg.firm_name:
        _footer_parts.append(_cfg.firm_name)
    if _cfg.confidentiality_label:
        _footer_parts.append(_cfg.confidentiality_label)
    ws.write(row, 1, " | ".join(_footer_parts), fmts["timestamp"])


def _write_findings_sheet(workbook, fmts: dict, report: ReviewReport):
    """Write the detailed findings sheet grouped by entity."""
    ws = workbook.add_worksheet("All Findings")
    ws.hide_gridlines(2)

    col_widths = [10, 8, 11, 50, 16, 16, 13, 40]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    ws.set_row(row, DS.EXCEL_HEADER_HEIGHT)
    headers = ["Check ID", "Severity", "Category", "Description", "Expected", "Actual", "Delta", "Context"]
    for i, h in enumerate(headers):
        ws.write(row, i, h, fmts["th_left"] if i in (0, 2, 3, 7) else fmts["th"])
    row += 1

    # Group by entity
    by_entity: dict[str, list[Finding]] = {}
    for f in report.findings:
        key = f"{f.entity_name} ({f.entity_code})"
        by_entity.setdefault(key, []).append(f)

    for entity_label, findings in by_entity.items():
        ws.merge_range(row, 0, row, 7, entity_label, fmts["entity_group"])
        row += 1

        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        findings.sort(key=lambda x: severity_order.get(x.severity, 3))

        for f in findings:
            alt = (row % 2 == 0)
            cell_fmt = fmts["cell_alt"] if alt else fmts["cell"]

            ws.write(row, 0, f.check_id, fmts["cell_mono"])

            sev_fmt = {"HIGH": fmts["sev_high"], "MEDIUM": fmts["sev_medium"], "LOW": fmts["sev_low"]}
            ws.write(row, 1, f.severity, sev_fmt.get(f.severity, fmts["cell"]))

            ws.write(row, 2, f.category, cell_fmt)
            ws.write(row, 3, f.description, cell_fmt)
            ws.write(row, 4, str(f.expected or "—"), cell_fmt)
            ws.write(row, 5, str(f.actual or "—"), cell_fmt)

            if f.delta is not None and f.delta != 0:
                ws.write_number(row, 6, f.delta, fmts["num_danger"] if f.severity == "HIGH" else fmts["num"])
            else:
                ws.write(row, 6, "—", fmts["num_muted"])

            ws.write(row, 7, f.context or "", cell_fmt)
            row += 1

        row += 1

    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, row - 1, 7)


def _write_rollover_sheet(workbook, fmts: dict, name: str, report: RolloverReport):
    """Write a rollover report as its own sheet."""
    tab_name = name[:31]
    ws = workbook.add_worksheet(tab_name)
    ws.hide_gridlines(2)

    headers = ["Entity", "Ref ID", "Line", "Field", "PY Value", "CY Value", "Difference", "Status"]
    col_widths = [30, 9, 6, 30, 15, 15, 13, 9]

    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    # Title row
    row = 0
    ws.set_row(row, DS.EXCEL_TITLE_HEIGHT)
    ws.write(row, 0, report.title, fmts["section"])
    row += 1
    ws.write(row, 0, f"{report.passed}/{report.total_checks} pass | {report.failed} differences", fmts["meta_value"])
    row += 2

    # Headers
    ws.set_row(row, DS.EXCEL_HEADER_HEIGHT)
    for i, h in enumerate(headers):
        fmt = fmts["th"] if i >= 4 else fmts["th_left"]
        ws.write(row, i, h, fmt)
    row += 1

    # Data rows (failures first, then passes)
    items_sorted = sorted(report.items, key=lambda x: (x.passes, x.entity_name))

    for item in items_sorted:
        alt = (row % 2 == 0)
        cell_fmt = fmts["cell_alt"] if alt else fmts["cell"]
        num_fmt = fmts["num_alt"] if alt else fmts["num"]

        ws.write(row, 0, item.entity_name[:35], cell_fmt)
        ws.write(row, 1, item.reference_id, fmts["cell_mono"])
        ws.write(row, 2, item.line, cell_fmt)
        ws.write(row, 3, item.field_description[:35], cell_fmt)

        # PY value
        try:
            py_num = float(item.py_value) if item.py_value else 0
            ws.write_number(row, 4, py_num, num_fmt)
        except (ValueError, TypeError):
            ws.write(row, 4, str(item.py_value or "—"), cell_fmt)

        # CY value
        try:
            cy_num = float(item.cy_value) if item.cy_value else 0
            ws.write_number(row, 5, cy_num, num_fmt)
        except (ValueError, TypeError):
            ws.write(row, 5, str(item.cy_value or "—"), cell_fmt)

        # Difference
        if item.difference and abs(item.difference) >= 1:
            ws.write_number(row, 6, item.difference, fmts["num_danger"] if not item.passes else fmts["num_muted"])
        else:
            ws.write(row, 6, 0, fmts["num_muted"])

        # Status
        if item.passes:
            ws.write(row, 7, "OK", fmts["status_ok"])
        else:
            ws.write(row, 7, "REVIEW", fmts["status_review"])

        row += 1

    ws.freeze_panes(4, 2)
    ws.autofilter(3, 0, row - 1, 7)


def _write_entity_summary_sheet(workbook, fmts: dict, report: ReviewReport):
    """Write an entity summary sheet — one row per entity with findings count and flags."""
    ws = workbook.add_worksheet("Entity Summary")
    ws.hide_gridlines(2)

    headers = ["Entity", "Ref ID", "Country", "Currency", "HIGH", "MEDIUM", "LOW", "Total", "Status"]
    col_widths = [30, 9, 8, 6, 7, 9, 7, 7, 10]

    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)

    row = 0
    ws.set_row(row, DS.EXCEL_TITLE_HEIGHT)
    ws.write(row, 0, "Entity Summary", fmts["section"])
    row += 1
    entities_hit = len(set(f.entity_code for f in report.findings))
    ws.write(row, 0, f"{report.entity_count} entities | {entities_hit} with findings | "
             f"{report.entity_count - entities_hit} clean", fmts["meta_value"])
    row += 2

    ws.set_row(row, DS.EXCEL_HEADER_HEIGHT)
    for i, h in enumerate(headers):
        fmt = fmts["th_left"] if i < 4 else fmts["th"]
        ws.write(row, i, h, fmt)
    row += 1

    by_entity: dict[str, dict] = {}
    for f in report.findings:
        key = f.entity_code
        if key not in by_entity:
            by_entity[key] = {"name": f.entity_name, "HIGH": 0, "MEDIUM": 0, "LOW": 0,
                             "country": "", "currency": ""}
        by_entity[key][f.severity] += 1

    for code, info in sorted(by_entity.items(), key=lambda x: x[1]["HIGH"], reverse=True):
        alt = (row % 2 == 0)
        cell_fmt = fmts["cell_alt"] if alt else fmts["cell"]
        total = info["HIGH"] + info["MEDIUM"] + info["LOW"]

        ws.write(row, 0, info["name"][:30], cell_fmt)
        ws.write(row, 1, code, fmts["cell_mono"])
        ws.write(row, 2, info["country"], cell_fmt)
        ws.write(row, 3, info["currency"], cell_fmt)
        ws.write(row, 4, info["HIGH"], fmts["num_danger"] if info["HIGH"] else fmts["num_muted"])
        ws.write(row, 5, info["MEDIUM"], fmts["num"] if info["MEDIUM"] else fmts["num_muted"])
        ws.write(row, 6, info["LOW"], fmts["num_muted"])
        ws.write(row, 7, total, fmts["num"])
        ws.write(row, 8, "REVIEW", fmts["status_review"] if info["HIGH"] else fmts["sev_medium"])
        row += 1

    ws.freeze_panes(4, 0)
    ws.autofilter(3, 0, row - 1, 8)


def export_excel(
    output_path: str | Path,
    review_report: ReviewReport | None = None,
    rollover_reports: dict[str, RolloverReport] | None = None,
    client_name: str = "",
    engagement: str = "",
    comparison: str = "",
):
    """Generate a premium corporate Excel workbook.

    Args:
        output_path: Where to save the .xlsx file
        review_report: ReviewReport from ReviewEngine (findings-based)
        rollover_reports: Dict of name -> RolloverReport from ReportEngine
        client_name: Client display name
        engagement: Engagement/year label
        comparison: Description of comparison
    """
    import xlsxwriter

    output_path = Path(output_path)

    workbook = xlsxwriter.Workbook(str(output_path), {"strings_to_numbers": False})
    fmts = _create_formats(workbook)

    # Executive Summary (if we have a ReviewReport)
    if review_report and review_report.findings:
        _write_cover_sheet(workbook, fmts, review_report, client_name, engagement, comparison)
        _write_findings_sheet(workbook, fmts, review_report)
        _write_entity_summary_sheet(workbook, fmts, review_report)

    # Rollover detail sheets
    if rollover_reports:
        for name, report in rollover_reports.items():
            if report.items:
                _write_rollover_sheet(workbook, fmts, name, report)

    workbook.close()
    return output_path

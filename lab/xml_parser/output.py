"""Output formatters — Generate Excel, CSV, and PDF reports.

Supports:
- Excel (.xlsx) — XlsxWriter: conditional formatting, freeze panes, auto-width
- CSV (.csv) — flat file per report
- PDF Simple — reportlab: clean tables, no branding
- PDF Branded — reportlab: PwC style (orange, professional layout)
- PDF (legacy) — fpdf2 fallback
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd

from lab.xml_parser.reports import RolloverReport


# PwC brand colors (RGB tuples and hex)
PWC_ORANGE = (208, 74, 2)
PWC_ORANGE_HEX = "#D04A02"
PWC_BLACK = (0, 0, 0)
PWC_WHITE = (255, 255, 255)
PWC_GREY_LIGHT = (245, 245, 245)
PWC_GREY_DARK = (100, 100, 100)
PWC_ROSE = (235, 100, 64)
PWC_YELLOW = (255, 184, 28)
PWC_GREEN = (34, 139, 34)
PWC_RED = (200, 30, 30)


def _sanitize_text(text: str) -> str:
    """Replace Unicode chars that cause issues in some PDF fonts."""
    replacements = {
        "—": "-", "–": "-", "→": "->",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "…": "...", "×": "x", "≤": "<=", "≥": ">=",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# DataFrame Conversion
# ─────────────────────────────────────────────────────────────────────────────

def report_to_dataframe(report: RolloverReport, include_pass: bool = False) -> pd.DataFrame:
    """Convert a RolloverReport to a DataFrame."""
    records = []
    for item in report.items:
        if not include_pass and item.passes:
            continue
        records.append({
            "Entity": item.entity_name,
            "Ref ID": item.reference_id,
            "Line": item.line,
            "Description": item.field_description,
            "PY Value": item.py_value,
            "CY Value": item.cy_value,
            "Difference": item.difference if item.difference != 0 else "",
            "Status": "PASS" if item.passes else "FAIL",
        })
    return pd.DataFrame(records) if records else pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(reports: dict, output_dir: str | Path, prefix: str = "review"):
    """Export each report as a separate CSV file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, report in reports.items():
        safe_name = name.replace(" ", "_").replace("/", "-").lower()
        df = report_to_dataframe(report, include_pass=True)
        if not df.empty:
            path = output_dir / f"{prefix}_{safe_name}.csv"
            df.to_csv(path, index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Excel Export (XlsxWriter — professional formatting)
# ─────────────────────────────────────────────────────────────────────────────

def export_excel(reports: dict, output_path: str | Path):
    """Export all reports to a professionally formatted Excel workbook."""
    output_path = Path(output_path)

    with pd.ExcelWriter(str(output_path), engine="xlsxwriter") as writer:
        workbook = writer.book

        # ── Define formats ──
        fmt_header = workbook.add_format({
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": PWC_ORANGE_HEX,
            "border": 1,
            "border_color": "#999999",
            "align": "center",
            "valign": "vcenter",
            "font_size": 10,
            "font_name": "Segoe UI",
        })
        fmt_pass = workbook.add_format({
            "font_color": "#1B7340",
            "bg_color": "#E8F5E9",
            "align": "center",
            "font_size": 9,
            "font_name": "Segoe UI",
        })
        fmt_fail = workbook.add_format({
            "font_color": "#C81E1E",
            "bg_color": "#FFEBEE",
            "bold": True,
            "align": "center",
            "font_size": 9,
            "font_name": "Segoe UI",
        })
        fmt_number = workbook.add_format({
            "num_format": "#,##0",
            "font_size": 9,
            "font_name": "Segoe UI",
        })
        fmt_diff_pos = workbook.add_format({
            "num_format": "+#,##0;-#,##0",
            "font_color": "#C81E1E",
            "bold": True,
            "font_size": 9,
            "font_name": "Segoe UI",
        })
        fmt_diff_zero = workbook.add_format({
            "num_format": "#,##0",
            "font_color": "#999999",
            "font_size": 9,
            "font_name": "Segoe UI",
        })
        fmt_text = workbook.add_format({
            "font_size": 9,
            "font_name": "Segoe UI",
            "text_wrap": True,
        })
        fmt_title = workbook.add_format({
            "bold": True,
            "font_size": 14,
            "font_color": PWC_ORANGE_HEX,
            "font_name": "Segoe UI",
        })
        fmt_subtitle = workbook.add_format({
            "font_size": 10,
            "font_color": "#666666",
            "font_name": "Segoe UI",
        })
        fmt_summary_header = workbook.add_format({
            "bold": True,
            "font_size": 10,
            "font_name": "Segoe UI",
            "bottom": 2,
            "bottom_color": PWC_ORANGE_HEX,
        })
        fmt_clean = workbook.add_format({
            "font_color": "#1B7340",
            "bold": True,
            "font_size": 10,
            "font_name": "Segoe UI",
        })
        fmt_issues = workbook.add_format({
            "font_color": "#C81E1E",
            "bold": True,
            "font_size": 10,
            "font_name": "Segoe UI",
        })

        # ── Summary tab ──
        ws_sum = workbook.add_worksheet("Summary")
        ws_sum.hide_gridlines(2)
        ws_sum.set_column("A:A", 28)
        ws_sum.set_column("B:D", 12)
        ws_sum.set_column("E:E", 18)

        ws_sum.write("A1", "XML Rollover Review", fmt_title)
        ws_sum.write("A2", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", fmt_subtitle)
        ws_sum.write("A4", "Report", fmt_summary_header)
        ws_sum.write("B4", "Checks", fmt_summary_header)
        ws_sum.write("C4", "Pass", fmt_summary_header)
        ws_sum.write("D4", "Fail", fmt_summary_header)
        ws_sum.write("E4", "Status", fmt_summary_header)

        row = 4
        for name, report in reports.items():
            ws_sum.write(row, 0, name, fmt_text)
            ws_sum.write(row, 1, report.total_checks, fmt_number)
            ws_sum.write(row, 2, report.passed, fmt_number)
            ws_sum.write(row, 3, report.failed, fmt_number)
            status = "CLEAN" if report.failed == 0 else f"{report.failed} issues"
            ws_sum.write(row, 4, status, fmt_clean if report.failed == 0 else fmt_issues)
            row += 1

        total_checks = sum(r.total_checks for r in reports.values())
        total_pass = sum(r.passed for r in reports.values())
        total_fail = sum(r.failed for r in reports.values())
        row += 1
        ws_sum.write(row, 0, "TOTAL", fmt_summary_header)
        ws_sum.write(row, 1, total_checks, fmt_number)
        ws_sum.write(row, 2, total_pass, fmt_number)
        ws_sum.write(row, 3, total_fail, fmt_number)

        # ── Detail tabs ──
        for name, report in reports.items():
            df = report_to_dataframe(report, include_pass=("Movement" in name or "Comparison" in name))
            if df.empty:
                continue

            tab_name = name[:31]
            df.to_excel(writer, sheet_name=tab_name, index=False, startrow=1)
            ws = writer.sheets[tab_name]

            # Header formatting
            for col_num, col_name in enumerate(df.columns):
                ws.write(1, col_num, col_name, fmt_header)

            # Column widths
            col_widths = {"Entity": 30, "Ref ID": 10, "Line": 8, "Description": 30,
                          "PY Value": 16, "CY Value": 16, "Difference": 14, "Status": 10}
            for col_num, col_name in enumerate(df.columns):
                ws.set_column(col_num, col_num, col_widths.get(col_name, 12))

            # Freeze panes (header row)
            ws.freeze_panes(2, 0)

            # Auto-filter
            ws.autofilter(1, 0, len(df) + 1, len(df.columns) - 1)

            # Conditional formatting on Status column
            status_col = list(df.columns).index("Status") if "Status" in df.columns else -1
            if status_col >= 0:
                ws.conditional_format(2, status_col, len(df) + 1, status_col, {
                    "type": "text",
                    "criteria": "containing",
                    "value": "PASS",
                    "format": fmt_pass,
                })
                ws.conditional_format(2, status_col, len(df) + 1, status_col, {
                    "type": "text",
                    "criteria": "containing",
                    "value": "FAIL",
                    "format": fmt_fail,
                })

            # Conditional formatting on Difference column
            diff_col = list(df.columns).index("Difference") if "Difference" in df.columns else -1
            if diff_col >= 0:
                ws.conditional_format(2, diff_col, len(df) + 1, diff_col, {
                    "type": "cell",
                    "criteria": "!=",
                    "value": 0,
                    "format": fmt_diff_pos,
                })


# ─────────────────────────────────────────────────────────────────────────────
# PDF Export — reportlab (Professional)
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf_branded(reports: dict, output_path: str | Path, client_name: str = "", tax_year: str = ""):
    """Generate a PwC-branded PDF report using reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    output_path = Path(output_path)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(letter),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.5 * inch,
    )

    # Colors
    pwc_orange = colors.Color(208/255, 74/255, 2/255)
    pwc_light_grey = colors.Color(245/255, 245/255, 245/255)
    pwc_green = colors.Color(27/255, 115/255, 64/255)
    pwc_red = colors.Color(200/255, 30/255, 30/255)
    pwc_dark_grey = colors.Color(100/255, 100/255, 100/255)

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=pwc_orange, spaceAfter=6,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle", parent=styles["Normal"],
        fontSize=14, textColor=pwc_dark_grey, spaceAfter=20,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionTitle", parent=styles["Heading1"],
        fontSize=16, textColor=pwc_orange, spaceBefore=12, spaceAfter=8,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        fontSize=9, textColor=pwc_dark_grey, spaceAfter=6,
        fontName="Helvetica-Oblique",
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, textColor=pwc_dark_grey, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "CellText", parent=styles["Normal"],
        fontSize=8, leading=10, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "CellBold", parent=styles["Normal"],
        fontSize=8, leading=10, fontName="Helvetica-Bold",
    ))

    elements = []

    # ── Cover section ──
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(HRFlowable(
        width="100%", thickness=4, color=pwc_orange,
        spaceBefore=0, spaceAfter=20
    ))
    elements.append(Paragraph("XML Rollover Review", styles["CoverTitle"]))
    subtitle_parts = []
    if client_name:
        subtitle_parts.append(client_name)
    if tax_year:
        subtitle_parts.append(f"Tax Year {tax_year}")
    subtitle_parts.append(f"Generated {datetime.now().strftime('%B %d, %Y')}")
    elements.append(Paragraph(" | ".join(subtitle_parts), styles["CoverSubtitle"]))
    elements.append(Spacer(1, 0.3 * inch))

    # ── Summary table ──
    elements.append(Paragraph("Review Summary", styles["SectionTitle"]))

    total_checks = sum(r.total_checks for r in reports.values())
    total_pass = sum(r.passed for r in reports.values())
    total_fail = sum(r.failed for r in reports.values())

    summary_data = [["Report", "Checks", "Pass", "Fail", "Status"]]
    for name, report in reports.items():
        status = "CLEAN" if report.failed == 0 else f"{report.failed} issues"
        summary_data.append([name, str(report.total_checks), str(report.passed), str(report.failed), status])
    summary_data.append(["TOTAL", str(total_checks), str(total_pass), str(total_fail), ""])

    summary_table = Table(summary_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
    summary_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), pwc_orange),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, pwc_light_grey]),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, pwc_orange),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(0.85, 0.85, 0.85)),
    ])

    # Color code the status column
    for i, (name, report) in enumerate(reports.items(), start=1):
        if report.failed == 0:
            summary_style.add("TEXTCOLOR", (4, i), (4, i), pwc_green)
        else:
            summary_style.add("TEXTCOLOR", (4, i), (4, i), pwc_red)
            summary_style.add("FONTNAME", (4, i), (4, i), "Helvetica-Bold")

    summary_table.setStyle(summary_style)
    elements.append(summary_table)

    # ── Detail pages for reports with issues ──
    for name, report in reports.items():
        if report.failed == 0:
            continue

        elements.append(PageBreak())
        elements.append(HRFlowable(
            width="100%", thickness=3, color=pwc_orange,
            spaceBefore=0, spaceAfter=8
        ))
        elements.append(Paragraph(name, styles["SectionTitle"]))
        elements.append(Paragraph(
            _sanitize_text(report.summary), styles["ReportSubtitle"]
        ))
        elements.append(Spacer(1, 0.15 * inch))

        # Detail table
        headers = ["Entity", "Ref ID", "Line", "Description", "PY Value", "CY Value", "Diff"]
        detail_data = [headers]

        for item in report.items:
            if item.passes:
                continue
            diff_str = f"{item.difference:+,.0f}" if item.difference and abs(item.difference) >= 1 else ""
            detail_data.append([
                _sanitize_text(item.entity_name[:35]),
                item.reference_id[:10],
                item.line[:8],
                _sanitize_text(item.field_description[:30]),
                str(item.py_value)[:18],
                str(item.cy_value)[:18],
                diff_str,
            ])

        col_widths = [2.5*inch, 0.7*inch, 0.6*inch, 2.2*inch, 1.3*inch, 1.3*inch, 0.9*inch]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)

        detail_style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), pwc_orange),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pwc_light_grey]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(0.85, 0.85, 0.85)),
        ])

        # Highlight diff column in red if non-zero
        for row_idx in range(1, len(detail_data)):
            if detail_data[row_idx][-1]:
                detail_style.add("TEXTCOLOR", (-1, row_idx), (-1, row_idx), pwc_red)
                detail_style.add("FONTNAME", (-1, row_idx), (-1, row_idx), "Helvetica-Bold")

        detail_table.setStyle(detail_style)
        elements.append(detail_table)

    # ── Footer ──
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=pwc_dark_grey, spaceAfter=6))
    elements.append(Paragraph(
        "Generated by Project Mythos | PwC US Tax LLP | Confidential - For internal use only",
        styles["Footer"]
    ))

    doc.build(elements)


def export_pdf_simple(reports: dict, output_path: str | Path, title: str = "XML Rollover Review"):
    """Generate a simple PDF report using reportlab (no branding)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER

    output_path = Path(output_path)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(letter),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))

    # Summary
    elements.append(Paragraph("Summary", styles["Heading2"]))
    for name, report in reports.items():
        status = "CLEAN" if report.failed == 0 else f"{report.failed} ISSUES"
        elements.append(Paragraph(
            f"&nbsp;&nbsp;{name}: {report.passed}/{report.total_checks} pass | {status}",
            styles["Normal"]
        ))

    # Detail pages
    for name, report in reports.items():
        if report.failed == 0:
            continue

        elements.append(PageBreak())
        elements.append(Paragraph(name, styles["Heading2"]))
        elements.append(Paragraph(_sanitize_text(report.summary), styles["Normal"]))
        elements.append(Spacer(1, 0.15 * inch))

        headers = ["Entity", "Ref", "Ln", "Description", "PY", "CY", "Diff"]
        data = [headers]
        for item in report.items:
            if item.passes:
                continue
            diff_str = f"{item.difference:+,.0f}" if item.difference and abs(item.difference) >= 1 else ""
            data.append([
                _sanitize_text(item.entity_name[:30]),
                item.reference_id[:8],
                item.line[:6],
                _sanitize_text(item.field_description[:25]),
                str(item.py_value)[:15],
                str(item.cy_value)[:15],
                diff_str,
            ])

        col_widths = [2.2*inch, 0.7*inch, 0.5*inch, 1.8*inch, 1.2*inch, 1.2*inch, 0.8*inch]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(table)

    doc.build(elements)

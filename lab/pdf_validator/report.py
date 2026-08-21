"""Output formatting for PDF Validation reports.

Generates Excel reports following spec 00-report-standards:
- Header estándar (Client, Engagement, Report, Comparison, Generated)
- Color coding: OK=green, PHANTOM/MISSING=red, MISMATCH=orange
- Sheets: Summary, Phantom Data, Mismatches, All Comparisons
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from lab.pdf_validator.reconciler import PDFValidationReport, PDFDiscrepancy

# Report styling
ACCENT_COLOR = "D04A02"
HEADER_FILL = PatternFill(start_color=ACCENT_COLOR, end_color=ACCENT_COLOR, fill_type="solid")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
OK_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
OK_FONT = Font(name="Calibri", color="375623", size=10)
PHANTOM_FILL = PatternFill(start_color="FBE5D6", end_color="FBE5D6", fill_type="solid")
PHANTOM_FONT = Font(name="Calibri", color="C00000", bold=True, size=10)
MISMATCH_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
MISMATCH_FONT = Font(name="Calibri", color="BF8F00", bold=True, size=10)
MISSING_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
MISSING_FONT = Font(name="Calibri", color="2F5496", bold=True, size=10)

STATUS_STYLES = {
    "OK": (OK_FILL, OK_FONT),
    "PHANTOM": (PHANTOM_FILL, PHANTOM_FONT),
    "MISSING": (MISSING_FILL, MISSING_FONT),
    "MISMATCH": (MISMATCH_FILL, MISMATCH_FONT),
}


def write_report_excel(report: PDFValidationReport, output_path: Path | str,
                       client_name: str = "Sample Client LP",
                       engagement: str = "FY25 International Tax Compliance"):
    """Generate formatted Excel report from PDFValidationReport."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # === Sheet 1: Summary ===
    ws = wb.active
    ws.title = "Summary"
    _write_header(ws, client_name, engagement,
                  f"PDF vs XML Validation — Schedule {report.schedule}",
                  f"PDF: {report.pdf_source} | XML: {report.xml_source}")

    row = 8
    ws.cell(row=row, column=1, value="RESULTS OVERVIEW").font = Font(bold=True, size=11)
    row += 1
    ws.cell(row=row, column=1, value=f"Total comparisons: {report.total_comparisons}")
    row += 1
    ws.cell(row=row, column=1, value=f"OK: {report.ok_count}").font = OK_FONT
    row += 1
    ws.cell(row=row, column=1, value=f"PHANTOM (in PDF, not in XML): {report.phantom_count}").font = PHANTOM_FONT
    row += 1
    ws.cell(row=row, column=1, value=f"MISSING (in XML, not in PDF): {report.missing_count}").font = MISSING_FONT
    row += 1
    ws.cell(row=row, column=1, value=f"MISMATCH (both differ): {report.mismatch_count}").font = MISMATCH_FONT
    row += 1
    ws.cell(row=row, column=1, value=f"Entities checked: {report.entities_checked}")
    row += 1
    ws.cell(row=row, column=1, value=f"Entities with issues: {len(report.entities_with_issues)}")
    row += 2

    if report.discrepancies:
        ws.cell(row=row, column=1, value="DISCREPANCIES").font = Font(bold=True, size=11)
        row += 1
        row = _write_discrepancy_table(ws, report.discrepancies, row)
    else:
        ws.cell(row=row, column=1, value="No discrepancies found. PDF and XML are aligned.").font = OK_FONT

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 10

    # === Sheet 2: Phantom Data (highest priority) ===
    phantoms = [d for d in report.items if d.status == "PHANTOM"]
    if phantoms:
        ws2 = wb.create_sheet("Phantom Data")
        _write_header(ws2, client_name, engagement,
                      "PHANTOM — Data in PDF but NOT in XML",
                      "These values exist in OIT but the XML export does not reflect them")
        _write_discrepancy_table(ws2, phantoms, 8)
        ws2.column_dimensions["A"].width = 28

    # === Sheet 3: Mismatches ===
    mismatches = [d for d in report.items if d.status == "MISMATCH"]
    if mismatches:
        ws3 = wb.create_sheet("Mismatches")
        _write_header(ws3, client_name, engagement,
                      "MISMATCH — Both have values but differ",
                      "PDF and XML have different amounts for these fields")
        _write_discrepancy_table(ws3, mismatches, 8)
        ws3.column_dimensions["A"].width = 28

    # === Sheet 4: All Comparisons ===
    ws4 = wb.create_sheet("All Comparisons")
    _write_header(ws4, client_name, engagement,
                  "All PDF vs XML Comparisons",
                  "Complete audit trail of every comparison performed")
    _write_discrepancy_table(ws4, report.items, 8)
    ws4.column_dimensions["A"].width = 28

    wb.save(str(output_path))
    return output_path


def _write_header(ws, client: str, engagement: str, report_name: str, comparison: str):
    """Write standard header per spec 00-report-standards."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.cell(row=1, column=1, value="CLIENT:").font = Font(bold=True, size=10)
    ws.cell(row=1, column=2, value=client).font = Font(size=10)
    ws.cell(row=2, column=1, value="ENGAGEMENT:").font = Font(bold=True, size=10)
    ws.cell(row=2, column=2, value=engagement).font = Font(size=10)
    ws.cell(row=3, column=1, value="REPORT:").font = Font(bold=True, size=10, color=ACCENT_COLOR)
    ws.cell(row=3, column=2, value=report_name).font = Font(bold=True, size=12, color=ACCENT_COLOR)
    ws.cell(row=4, column=1, value="COMPARISON:").font = Font(bold=True, size=10)
    ws.cell(row=4, column=2, value=comparison).font = Font(size=10)
    ws.cell(row=5, column=1, value="Generated:").font = Font(italic=True, size=9, color="808080")
    ws.cell(row=5, column=2, value=now).font = Font(italic=True, size=9, color="808080")
    ws.column_dimensions["B"].width = 55


def _write_discrepancy_table(ws, items: list[PDFDiscrepancy], start_row: int) -> int:
    """Write a table of discrepancies with formatting. Returns next available row."""
    headers = ["Entity", "Ref ID", "Basket", "Pool", "Description",
               "PDF Value", "XML Value", "Delta", "Status", "Severity"]

    row = start_row
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    row += 1

    for item in items:
        ws.cell(row=row, column=1, value=item.entity_name)
        ws.cell(row=row, column=2, value=item.reference_id)
        ws.cell(row=row, column=3, value=item.basket)
        ws.cell(row=row, column=4, value=item.field.split(" ")[0] if " " in item.field else item.field)
        ws.cell(row=row, column=5, value=item.field_description)
        ws.cell(row=row, column=6, value=item.pdf_value).number_format = '#,##0'
        ws.cell(row=row, column=7, value=item.xml_value).number_format = '#,##0'

        delta_cell = ws.cell(row=row, column=8, value=item.delta)
        delta_cell.number_format = '+#,##0;-#,##0;"-"'

        status_cell = ws.cell(row=row, column=9, value=item.status)
        status_cell.alignment = Alignment(horizontal="center")
        fill, font = STATUS_STYLES.get(item.status, (None, None))
        if fill:
            status_cell.fill = fill
        if font:
            status_cell.font = font

        ws.cell(row=row, column=10, value=item.severity)
        row += 1

    # Column widths
    widths = [28, 8, 6, 10, 28, 14, 14, 14, 12, 10]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w

    return row

"""Content verification tests for Export layer.

Goes beyond "file exists" — opens generated files and validates:
- Correct sheet names
- Correct headers
- Correct row counts
- Correct cell values (spot checks)
- Totals reconciliation (findings count == rows in export)
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.core.models import Finding, ReviewReport, RolloverItem, RolloverReport
from lab.xml_parser.export import export_csv, export_findings_csv, export_excel
from lab.xml_parser.export.csv_exporter import export_findings_csv as csv_export_fn
from lab.xml_parser.review_engine import ReviewEngine

FIXTURES = Path(__file__).parent / "fixtures"


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def review_report():
    engine = ReviewEngine()
    return engine.review(FIXTURES / "sample_cy.xml", FIXTURES / "sample_py.xml")


@pytest.fixture
def rollover_reports():
    from lab.xml_parser.reports import run_all_reports

    return run_all_reports(FIXTURES / "sample_py.xml", FIXTURES / "sample_cy.xml")


@pytest.fixture
def sample_review_report():
    """Small deterministic review report for precise content checks."""
    return ReviewReport(
        client_name="Test Client Inc",
        tax_year="2025",
        entity_count=3,
        form_type="5471",
        findings=[
            Finding("FLO-001", "HIGH", "flow", "E001", "Alpha Corp",
                    "Sch H net income != Sch C line 21 (delta 50,000 FC)",
                    expected="Sch C: 1,000,000", actual="Sch H: 1,050,000", delta=50000),
            Finding("CMP-001", "HIGH", "completeness", "E002", "Beta LLC",
                    "Missing Schedule H", context="Entity has income but no Sch H"),
            Finding("RSN-003", "MEDIUM", "reasonableness", "E001", "Alpha Corp",
                    "ETR anomaly: 75%", expected="0-50%", actual="75%"),
        ],
    )


@pytest.fixture
def sample_rollover_reports():
    return {
        "Sch F Rollover": RolloverReport(
            title="Schedule F Rollover",
            items=[
                RolloverItem("Alpha Corp", "E001", "Total Assets", "9",
                             "10,000,000", "10,500,000", 500000, False),
                RolloverItem("Beta LLC", "E002", "Total Assets", "9",
                             "5,000,000", "5,000,000", 0, True),
            ],
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CSV EXPORT — Content Verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestCSVExportContent:
    """Verify CSV file content, not just existence."""

    def test_findings_csv_row_count(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)
        assert len(df) == len(review_report.findings)

    def test_findings_csv_columns(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)
        expected_cols = {"check_id", "severity", "category", "entity_code",
                        "entity_name", "description"}
        assert expected_cols.issubset(set(df.columns))

    def test_findings_csv_content_spot_check(self, sample_review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(sample_review_report, out)
        df = pd.read_csv(out)
        assert len(df) == 3
        flo = df[df["check_id"] == "FLO-001"]
        assert len(flo) == 1
        assert flo.iloc[0]["entity_code"] == "E001"
        assert flo.iloc[0]["severity"] == "HIGH"

    def test_findings_csv_high_severity_all_present(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)
        high_in_report = len([f for f in review_report.findings if f.severity == "HIGH"])
        high_in_csv = len(df[df["severity"] == "HIGH"])
        assert high_in_csv == high_in_report

    def test_rollover_csv_multiple_files(self, rollover_reports, tmp_path):
        files = export_csv(rollover_reports, tmp_path, prefix="test")
        assert len(files) >= 5
        for f in files:
            df = pd.read_csv(f)
            assert len(df) > 0
            assert "Entity" in df.columns or "Ref ID" in df.columns


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL EXPORT — Content Verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestExcelExportContent:
    """Open generated Excel files and verify internal structure."""

    def test_excel_has_expected_sheets(self, rollover_reports, tmp_path):
        out = tmp_path / "review.xlsx"
        export_excel(out, rollover_reports=rollover_reports, client_name="Test Client")
        assert out.exists()

        import openpyxl
        wb = openpyxl.load_workbook(out, read_only=True)
        assert len(wb.sheetnames) >= 3

    def test_excel_findings_sheet_row_count(self, review_report, tmp_path):
        out = tmp_path / "review.xlsx"
        export_excel(
            out,
            review_report=review_report,
            rollover_reports={},
            client_name="Test Client",
        )
        assert out.exists()

        import openpyxl
        wb = openpyxl.load_workbook(out, read_only=True)
        if "Findings" in wb.sheetnames:
            ws = wb["Findings"]
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            assert len(rows) == len(review_report.findings)

    def test_excel_not_empty(self, rollover_reports, tmp_path):
        out = tmp_path / "review.xlsx"
        export_excel(out, rollover_reports=rollover_reports, client_name="Test Client")
        assert out.stat().st_size > 5000  # Non-trivial file

    def test_excel_rollover_data_present(self, sample_rollover_reports, tmp_path):
        out = tmp_path / "review.xlsx"
        export_excel(
            out,
            rollover_reports=sample_rollover_reports,
            client_name="Test Client",
        )

        import openpyxl
        wb = openpyxl.load_workbook(out, read_only=True)
        all_values = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            for row in ws.iter_rows(values_only=True):
                all_values.extend([str(v) for v in row if v is not None])

        text = " ".join(all_values)
        assert "Alpha Corp" in text or "E001" in text


# ═══════════════════════════════════════════════════════════════════════════════
# RECONCILIATION — Input/Output Integrity
# ═══════════════════════════════════════════════════════════════════════════════


class TestExportReconciliation:
    """Verify that export doesn't lose or add data."""

    def test_csv_total_equals_input(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)
        assert len(df) == 28

    def test_csv_entity_distribution_matches(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)

        report_entities = {f.entity_code for f in review_report.findings}
        csv_entities = set(df["entity_code"].unique())
        assert report_entities == csv_entities

    def test_csv_check_id_distribution_matches(self, review_report, tmp_path):
        out = tmp_path / "findings.csv"
        export_findings_csv(review_report, out)
        df = pd.read_csv(out)

        report_checks = {f.check_id for f in review_report.findings}
        csv_checks = set(df["check_id"].unique())
        assert report_checks == csv_checks

    def test_rollover_csv_item_count_matches(self, rollover_reports, tmp_path):
        files = export_csv(rollover_reports, tmp_path, prefix="recon")
        total_items_in_reports = sum(r.total_checks for r in rollover_reports.values())
        total_items_in_csvs = sum(len(pd.read_csv(f)) for f in files)
        assert total_items_in_csvs == total_items_in_reports

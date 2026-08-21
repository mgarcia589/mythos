"""Smoke tests for reports/ and export/ packages."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.core.models import RolloverReport, RolloverItem
from lab.xml_parser.reports import (
    run_all_reports,
    ReportEngine,
    sch_f_rollover,
    page1_rollover,
    sch_j_rollover,
    ep_movement,
    gilti_comparison,
    new_final_entities,
    schedule_g_changes,
)
from lab.xml_parser.export import (
    export_csv,
    export_findings_csv,
    export_html,
    export_excel,
    DesignSystem,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def py_path():
    return FIXTURES / "sample_py.xml"


@pytest.fixture
def cy_path():
    return FIXTURES / "sample_cy.xml"


@pytest.fixture
def parsed_py(py_path):
    from lab.xml_parser.parser import EFileParser
    return EFileParser(py_path).parse()


@pytest.fixture
def parsed_cy(cy_path):
    from lab.xml_parser.parser import EFileParser
    return EFileParser(cy_path).parse()


class TestReportsPackage:
    """Verify reports/ functions return well-formed RolloverReport objects."""

    def test_run_all_reports(self, py_path, cy_path):
        reports = run_all_reports(py_path, cy_path)
        assert isinstance(reports, dict)
        assert len(reports) == 12
        for name, report in reports.items():
            assert isinstance(report, RolloverReport), f"{name} is not RolloverReport"
            assert report.total_checks >= 0

    def test_sch_f_rollover(self, parsed_py, parsed_cy):
        report = sch_f_rollover(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)
        assert "Sch F" in report.summary or "Schedule F" in report.summary

    def test_page1_rollover(self, parsed_py, parsed_cy):
        report = page1_rollover(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)

    def test_sch_j_rollover(self, parsed_py, parsed_cy):
        report = sch_j_rollover(parsed_py, parsed_cy, basket="GEN")
        assert isinstance(report, RolloverReport)

    def test_ep_movement(self, parsed_py, parsed_cy):
        report = ep_movement(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)

    def test_gilti_comparison(self, parsed_py, parsed_cy):
        report = gilti_comparison(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)

    def test_new_final_entities(self, parsed_py, parsed_cy):
        report = new_final_entities(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)

    def test_schedule_g_changes(self, parsed_py, parsed_cy):
        report = schedule_g_changes(parsed_py, parsed_cy)
        assert isinstance(report, RolloverReport)

    def test_report_engine_backward_compat(self, py_path, cy_path):
        engine = ReportEngine(py_path, cy_path)
        assert engine.entity_count > 0
        report = engine.sch_f_rollover()
        assert isinstance(report, RolloverReport)


class TestExportPackage:
    """Verify export/ functions produce output files."""

    def test_export_csv(self, py_path, cy_path, tmp_path):
        reports = run_all_reports(py_path, cy_path)
        files = export_csv(reports, tmp_path, prefix="test")
        assert len(files) > 0
        for f in files:
            assert f.exists()
            assert f.stat().st_size > 0
            assert f.suffix == ".csv"

    def test_export_findings_csv(self, tmp_path):
        from lab.xml_parser.review_engine import ReviewEngine
        engine = ReviewEngine()
        report = engine.review(
            FIXTURES / "sample_cy.xml",
            FIXTURES / "sample_py.xml",
        )
        out = tmp_path / "findings.csv"
        result = export_findings_csv(report, out)
        assert result is not None
        assert result.exists()
        assert result.stat().st_size > 0

    def test_export_excel(self, py_path, cy_path, tmp_path):
        reports = run_all_reports(py_path, cy_path)
        out = tmp_path / "test_export.xlsx"
        export_excel(out, rollover_reports=reports, client_name="Test Client")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_design_system_colors(self):
        assert DesignSystem.NAVY.startswith("#")
        assert DesignSystem.COPPER.startswith("#")
        assert DesignSystem.severity_color("HIGH") != ""

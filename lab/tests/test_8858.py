"""Tests for Form 8858 support: parser, checks, and reports."""

import pytest
from pathlib import Path

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.review_engine import ReviewEngine
from lab.xml_parser.reports import run_all_reports_8858
from lab.xml_parser.core.models import RolloverReport, ReviewReport


FIXTURES = Path(__file__).parent / "fixtures"
CY_8858 = FIXTURES / "sample_8858_cy.xml"
PY_8858 = FIXTURES / "sample_8858_py.xml"


@pytest.fixture
def cy_parser():
    return EFileParser(CY_8858)


@pytest.fixture
def py_parser():
    return EFileParser(PY_8858)


# ─── Parser Tests ────────────────────────────────────────────────────────────

class TestParser8858:
    def test_list_8858_entities(self, cy_parser):
        entities = cy_parser.list_8858_entities()
        assert len(entities) == 5
        refs = {e["reference_id"] for e in entities}
        assert refs == {"FDE001", "FDE002", "FDE003", "FDE004", "FDE005"}

    def test_entity_details(self, cy_parser):
        entities = cy_parser.list_8858_entities()
        by_ref = {e["reference_id"]: e for e in entities}

        fde001 = by_ref["FDE001"]
        assert fde001["name"] == "CLEAN FDE LLC"
        assert fde001["country_code"] == "UK"
        assert fde001["functional_currency"] == "USD"
        assert fde001["tax_owner"] == "TEST HOLDINGS INC"
        assert fde001["category"] == "FDE"

        fde002 = by_ref["FDE002"]
        assert fde002["functional_currency"] == "EUR"
        assert fde002["category"] == "FB"
        assert fde002["tax_owner_ref_id"] == "CFC001"

    def test_extract_schedule_c(self, cy_parser):
        sch_c = cy_parser.extract_form_8858("IRS8858ScheduleC")
        assert len(sch_c) == 4  # FDE001, FDE002, FDE004, FDE005 (FDE003 has no Sch C)
        fde001 = sch_c[sch_c["_reference_id"] == "FDE001"].iloc[0]
        assert float(fde001["IRS8858ScheduleC_GrossReceiptsOrSalesIncmStmt_USDollarAmt"]) == 5000000

    def test_extract_schedule_f(self, cy_parser):
        sch_f = cy_parser.extract_form_8858("IRS8858ScheduleF")
        assert len(sch_f) == 4
        fde001 = sch_f[sch_f["_reference_id"] == "FDE001"].iloc[0]
        assert float(fde001["IRS8858ScheduleF_TotalAssetsBalanceSheet_EndingAmt"]) == 11500000

    def test_extract_schedule_h(self, cy_parser):
        sch_h = cy_parser.extract_form_8858("IRS8858ScheduleH")
        assert len(sch_h) == 4
        fde002 = sch_h[sch_h["_reference_id"] == "FDE002"].iloc[0]
        assert float(fde002["IRS8858ScheduleH_CurrentEarningsAndProfitsAmt"]) == 850000
        assert float(fde002["IRS8858ScheduleH_ExchangeRt"]) == pytest.approx(0.909091, abs=0.0001)

    def test_extract_main_form(self, cy_parser):
        main = cy_parser.extract_form_8858("IRS8858")
        assert len(main) == 5
        assert "_dormant" in main.columns
        assert "_tax_owner" in main.columns

    def test_fc_and_usd_amounts(self, cy_parser):
        sch_c = cy_parser.extract_form_8858("IRS8858ScheduleC")
        fde002 = sch_c[sch_c["_reference_id"] == "FDE002"].iloc[0]
        fc = float(fde002["IRS8858ScheduleC_GrossReceiptsOrSalesIncmStmt_FunctionalCurrencyAmt"])
        usd = float(fde002["IRS8858ScheduleC_GrossReceiptsOrSalesIncmStmt_USDollarAmt"])
        assert fc == 2000000
        assert usd == 2200000


# ─── Check Tests ─────────────────────────────────────────────────────────────

class TestChecks8858:
    @pytest.fixture
    def review_report(self):
        engine = ReviewEngine()
        return engine.review(CY_8858, PY_8858, form_type="8858")

    @pytest.fixture
    def review_report_cy_only(self):
        engine = ReviewEngine()
        return engine.review(CY_8858, form_type="8858")

    def test_total_findings(self, review_report):
        assert len(review_report.findings) >= 5

    def test_form_type(self, review_report):
        assert review_report.form_type == "8858"

    def test_entity_count(self, review_report):
        assert review_report.entity_count == 5

    def test_cmp_8858_001_missing_sch_c(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "CMP-8858-001"]
        assert len(matches) == 1
        assert matches[0].entity_code == "FDE003"

    def test_cmp_8858_002_missing_sch_h(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "CMP-8858-002"]
        assert len(matches) == 1
        assert matches[0].entity_code == "FDE003"
        assert matches[0].severity == "HIGH"

    def test_cmp_8858_003_missing_sch_f(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "CMP-8858-003"]
        assert len(matches) == 1
        assert matches[0].entity_code == "FDE003"

    def test_flo_8858_004_balance_sheet_imbalance(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "FLO-8858-004"]
        assert len(matches) >= 1
        entities = {f.entity_code for f in matches}
        assert "FDE004" in entities

    def test_rol_8858_001_dropped_entity(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "ROL-8858-001"]
        assert len(matches) == 1
        assert matches[0].entity_code == "FDEDROP"

    def test_rol_8858_002_new_entity(self, review_report):
        matches = [f for f in review_report.findings if f.check_id == "ROL-8858-002"]
        assert len(matches) == 1
        assert matches[0].entity_code == "FDE005"

    def test_cy_only_no_rollover(self, review_report_cy_only):
        rollover = [f for f in review_report_cy_only.findings if f.category == "rollover"]
        assert len(rollover) == 0

    def test_cy_only_still_has_findings(self, review_report_cy_only):
        assert len(review_report_cy_only.findings) > 0


# ─── Report Tests ────────────────────────────────────────────────────────────

class TestReports8858:
    def test_run_all_reports_8858(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        assert isinstance(reports, dict)
        assert len(reports) == 5
        for name, report in reports.items():
            assert isinstance(report, RolloverReport), f"{name} is not RolloverReport"

    def test_sch_f_rollover(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        r = reports["8858 Sch F Rollover"]
        assert r.total_checks > 0
        # FDE001 PY EOY total assets = 10,000,000, CY BOY = 10,000,000 => pass
        fde001_items = [i for i in r.items if i.reference_id == "FDE001"]
        assert len(fde001_items) > 0

    def test_ep_summary(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        r = reports["8858 E&P Summary"]
        assert r.total_checks > 0

    def test_income_statement(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        r = reports["8858 Income Statement"]
        assert r.total_checks > 0

    def test_entity_changes(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        r = reports["8858 Entity Changes"]
        # FDE005 new in CY, FDEDROP dropped
        new_items = [i for i in r.items if "NEW" in i.field_description]
        drop_items = [i for i in r.items if "DROPPED" in i.field_description]
        assert len(new_items) == 1
        assert new_items[0].reference_id == "FDE005"
        assert len(drop_items) == 1
        assert drop_items[0].reference_id == "FDEDROP"

    def test_tax_owner_map(self):
        reports = run_all_reports_8858(PY_8858, CY_8858)
        r = reports["8858 Tax Owner Map"]
        assert r.total_checks == 5
        fde002 = [i for i in r.items if i.reference_id == "FDE002"]
        assert len(fde002) == 1
        assert "CFC001" in fde002[0].field_description


# ─── Backward Compatibility ──────────────────────────────────────────────────

class TestBackwardCompat:
    def test_5471_still_works(self):
        engine = ReviewEngine()
        report = engine.review(
            FIXTURES / "sample_cy.xml",
            FIXTURES / "sample_py.xml",
        )
        assert report.form_type == "5471"
        assert len(report.findings) == 28

    def test_5471_default_form_type(self):
        engine = ReviewEngine()
        report = engine.review(
            FIXTURES / "sample_cy.xml",
            FIXTURES / "sample_py.xml",
            form_type="5471",
        )
        assert len(report.findings) == 28

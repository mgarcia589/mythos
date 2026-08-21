"""Unit tests for the PDF Validator module.

Tests cover:
- Number parsing (OIT PDF format quirks)
- Field identification (description -> XML field mapping)
- Pool identification (various formats -> canonical pool name)
- Discrepancy classification logic
- Reconciler behavior with mock data
- ExecutionResult model
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from lab.pdf_validator.extractor import parse_number, PDFExtractor, SchJEntity
from lab.pdf_validator.layouts.schedule_j import identify_pool, identify_column
from lab.pdf_validator.reconciler import PDFReconciler, PDFValidationReport, PDFDiscrepancy, POOL_LOOKUP
from lab.pdf_validator.models import ExecutionResult, ValidationSummary


# ============================================================================
# parse_number tests
# ============================================================================

class TestParseNumber:
    """Tests for OIT PDF number parsing."""

    def test_positive_integer(self):
        assert parse_number("1,234,567") == 1234567.0

    def test_negative_parentheses(self):
        assert parse_number("(15,272,537)") == -15272537.0

    def test_negative_leading_minus(self):
        assert parse_number("-6,243") == -6243.0

    def test_trailing_period(self):
        assert parse_number("15,272,537.") == 15272537.0

    def test_simple_number(self):
        assert parse_number("92") == 92.0

    def test_zero_string(self):
        assert parse_number("0") is None

    def test_dash_is_none(self):
        assert parse_number("-") is None
        assert parse_number("—") is None
        assert parse_number("–") is None

    def test_empty_string_is_none(self):
        assert parse_number("") is None
        assert parse_number("   ") is None

    def test_none_input(self):
        assert parse_number(None) is None

    def test_whitespace_stripped(self):
        assert parse_number("  1,234  ") == 1234.0

    def test_parentheses_with_decimal(self):
        assert parse_number("(1,234.56)") == -1234.56

    def test_plain_decimal(self):
        assert parse_number("123.45") == 123.45

    def test_double_dash_is_none(self):
        assert parse_number("--") is None

    def test_non_numeric_returns_none(self):
        assert parse_number("abc") is None
        assert parse_number("N/A") is None


# ============================================================================
# identify_pool tests
# ============================================================================

class TestIdentifyPool:
    """Tests for pool identification from PDF text."""

    def test_letter_match_a(self):
        assert identify_pool("(a)") == "Post2017EPNotPrevTaxedGrp"

    def test_letter_match_c(self):
        assert identify_pool("(c)") == "Section951APTEPGrp"

    def test_letter_match_e_i(self):
        assert identify_pool("(e)(i)") == "Section951a1APTEPGrp"

    def test_keyword_gilti(self):
        assert identify_pool("Section 951A PTEP (GILTI)") == "Section951APTEPGrp"

    def test_keyword_subpart_f(self):
        assert identify_pool("subpart f ptep") == "Section951a1APTEPGrp"

    def test_keyword_post_2017(self):
        assert identify_pool("Post-2017 Not Prev Taxed") == "Post2017EPNotPrevTaxedGrp"

    def test_keyword_hovering(self):
        assert identify_pool("Hovering Deficit") == "HoveringDeficitDedSspndTaxGrp"

    def test_roman_numeral_xviii(self):
        assert identify_pool("XVIII") == "Section951APTEPGrp"

    def test_roman_numeral_xx(self):
        assert identify_pool("XX") == "Section951a1APTEPGrp"

    def test_unrecognized_returns_none(self):
        assert identify_pool("random text") is None
        assert identify_pool("") is None


# ============================================================================
# identify_column tests
# ============================================================================

class TestIdentifyColumn:
    """Tests for column header -> field name mapping."""

    def test_beg_bal(self):
        assert identify_column("Beg Bal") == "BeginningYearBalanceAmt"

    def test_beginning(self):
        assert identify_column("Beginning") == "BeginningYearBalanceAmt"

    def test_adj_beg(self):
        assert identify_column("Adj Beg") == "AdjustedBeginningBalanceAmt"

    def test_cy_ep(self):
        assert identify_column("CY E&P") == "CurrentYearEPDeficitAmt"

    def test_end_bal(self):
        assert identify_column("End Bal") == "BalanceBeginningNextYearAmt"

    def test_eoy(self):
        assert identify_column("EOY") == "BalanceEndOfYearAmt"

    def test_unrecognized(self):
        assert identify_column("Something Else") is None


# ============================================================================
# PDFReconciler._classify tests
# ============================================================================

class TestClassification:
    """Tests for discrepancy classification logic."""

    def _make_reconciler(self):
        """Create reconciler with empty PDF data for testing _classify."""
        df = pd.DataFrame(columns=["entity_name", "reference_id", "basket", "pool_name", "field_name", "value"])
        return PDFReconciler(pdf_data=df, schedule="J", tolerance=10.0)

    def test_ok_within_tolerance(self):
        r = self._make_reconciler()
        status, severity = r._classify(1000.0, 1005.0, -5.0)
        assert status == "OK"
        assert severity == "NONE"

    def test_ok_both_zero(self):
        r = self._make_reconciler()
        status, severity = r._classify(0.0, 0.0, 0.0)
        assert status == "OK"

    def test_phantom_pdf_has_value_xml_zero(self):
        r = self._make_reconciler()
        status, severity = r._classify(92.0, 0.0, 92.0)
        assert status == "PHANTOM"
        assert severity == "HIGH"

    def test_missing_xml_has_value_pdf_zero(self):
        r = self._make_reconciler()
        status, severity = r._classify(0.0, 5000.0, -5000.0)
        assert status == "MISSING"
        assert severity == "HIGH"

    def test_mismatch_both_have_values(self):
        r = self._make_reconciler()
        status, severity = r._classify(1000.0, 2000.0, -1000.0)
        assert status == "MISMATCH"
        assert severity == "MEDIUM"

    def test_phantom_negative_pdf_value(self):
        r = self._make_reconciler()
        status, severity = r._classify(-500.0, 0.0, -500.0)
        assert status == "PHANTOM"
        assert severity == "HIGH"

    def test_custom_tolerance(self):
        df = pd.DataFrame(columns=["entity_name", "reference_id", "basket", "pool_name", "field_name", "value"])
        r = PDFReconciler(pdf_data=df, schedule="J", tolerance=100.0)
        # Delta 50 is within tolerance of 100
        status, _ = r._classify(1050.0, 1000.0, 50.0)
        assert status == "OK"


# ============================================================================
# PDFReconciler reconciliation tests
# ============================================================================

class TestReconciliation:
    """Tests for full reconciliation pipeline with mock data."""

    def _mock_pdf_data(self, records: list[dict]) -> pd.DataFrame:
        """Build DataFrame matching PDFExtractor output schema."""
        df = pd.DataFrame(records, columns=[
            "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
        ])
        df.attrs["source"] = "test.pdf"
        return df

    def test_perfect_match(self):
        """When PDF and XML have identical values, all should be OK."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Test Corp", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 1000000.0},
        ])
        xml_values = {("C0001", "GEN", "Post2017EPNotPrevTaxedGrp"): 1000000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 1
        assert report.ok_count == 1
        assert report.phantom_count == 0

    def test_phantom_detected(self):
        """Value in PDF but not in XML should be flagged as PHANTOM."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Test Corp", "reference_id": "C0002", "basket": "GEN",
             "pool_name": "Section951APTEPGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 92.0},
        ])
        xml_values = {}  # XML has nothing

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1
        assert report.discrepancies[0].status == "PHANTOM"
        assert report.discrepancies[0].pdf_value == 92.0
        assert report.discrepancies[0].xml_value == 0.0

    def test_missing_detected(self):
        """Value in XML but not in PDF should be flagged as MISSING."""
        pdf_df = self._mock_pdf_data([])
        xml_values = {("C0001", "GEN", "Post2017EPNotPrevTaxedGrp"): 500000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.missing_count == 1
        assert report.discrepancies[0].status == "MISSING"

    def test_mismatch_detected(self):
        """Both have values but differ beyond tolerance."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 1000.0},
        ])
        xml_values = {("C0001", "GEN", "Post2017EPNotPrevTaxedGrp"): 2000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        assert report.discrepancies[0].delta == -1000.0

    def test_skip_pools_excluded(self):
        """Pools in skip_pools should not appear in results."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "TotalSection964AEPGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 99999.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 0

    def test_multiple_entities(self):
        """Reconciliation handles multiple entities correctly."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 1000.0},
            {"entity_name": "Corp B", "reference_id": "C0002", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 2000.0},
        ])
        xml_values = {
            ("C0001", "GEN", "Post2017EPNotPrevTaxedGrp"): 1000.0,
            ("C0002", "GEN", "Post2017EPNotPrevTaxedGrp"): 2000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2
        assert report.entities_checked == 2

    def test_field_name_filter(self):
        """Only the target xml_field should be reconciled."""
        pdf_df = self._mock_pdf_data([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BeginningYearBalanceAmt",
             "value": 1000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Post2017EPNotPrevTaxedGrp", "field_name": "BalanceBeginningNextYearAmt",
             "value": 9999.0},  # Different field, should be ignored
        ])
        xml_values = {("C0001", "GEN", "Post2017EPNotPrevTaxedGrp"): 1000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="J", xml_field="BeginningYearBalanceAmt")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 1
        assert report.ok_count == 1


# ============================================================================
# PDFValidationReport tests
# ============================================================================

class TestPDFValidationReport:
    """Tests for report summary properties."""

    def test_empty_report(self):
        report = PDFValidationReport(schedule="J", pdf_source="test.pdf", xml_source="test.xml")
        assert report.total_comparisons == 0
        assert report.summary == "No comparisons performed."

    def test_all_ok_summary(self):
        report = PDFValidationReport(schedule="J", pdf_source="test.pdf", xml_source="test.xml")
        report.items = [
            PDFDiscrepancy("Corp", "C0001", "GEN", "J", "(a) Pool", "Desc",
                           1000.0, 1000.0, 0.0, "OK", "NONE"),
        ]
        assert "ALL OK" in report.summary

    def test_entities_with_issues(self):
        report = PDFValidationReport(schedule="J", pdf_source="test.pdf", xml_source="test.xml")
        report.items = [
            PDFDiscrepancy("Corp A", "C0001", "GEN", "J", "(a) Pool", "Desc",
                           92.0, 0.0, 92.0, "PHANTOM", "HIGH"),
            PDFDiscrepancy("Corp B", "C0002", "GEN", "J", "(a) Pool", "Desc",
                           1000.0, 1000.0, 0.0, "OK", "NONE"),
        ]
        assert report.entities_with_issues == ["C0001"]
        assert report.phantom_count == 1
        assert report.ok_count == 1


# ============================================================================
# ExecutionResult tests
# ============================================================================

class TestExecutionResult:
    """Tests for the UI-ready result model."""

    def test_duration_display_milliseconds(self):
        started = datetime(2025, 1, 1, 12, 0, 0)
        completed = started + timedelta(milliseconds=500)
        result = ExecutionResult(
            success=True, status="completed", message="Done",
            started_at=started, completed_at=completed,
        )
        assert result.duration_display == "500ms"

    def test_duration_display_seconds(self):
        started = datetime(2025, 1, 1, 12, 0, 0)
        completed = started + timedelta(seconds=3.5)
        result = ExecutionResult(
            success=True, status="completed", message="Done",
            started_at=started, completed_at=completed,
        )
        assert result.duration_display == "3.5s"

    def test_duration_display_no_times(self):
        result = ExecutionResult(success=True, status="completed", message="Done")
        assert result.duration_display == "N/A"


# ============================================================================
# SchJEntity tests
# ============================================================================

class TestSchJEntity:
    """Tests for the extraction entity dataclass."""

    def test_pool_count(self):
        entity = SchJEntity(entity_name="Test", reference_id="C0001", basket="GEN")
        entity.pools = {
            "Post2017EPNotPrevTaxedGrp": {"BeginningYearBalanceAmt": 1000},
            "Section951APTEPGrp": {"BeginningYearBalanceAmt": 92},
        }
        assert entity.pool_count == 2

    def test_value_count(self):
        entity = SchJEntity(entity_name="Test", reference_id="C0001", basket="GEN")
        entity.pools = {
            "Post2017EPNotPrevTaxedGrp": {"BeginningYearBalanceAmt": 1000, "AdjustedBeginningBalanceAmt": 1000},
            "Section951APTEPGrp": {"BeginningYearBalanceAmt": 92},
        }
        assert entity.value_count == 3

    def test_empty_entity(self):
        entity = SchJEntity(entity_name="Test", reference_id="C0001", basket="GEN")
        assert entity.pool_count == 0
        assert entity.value_count == 0


# ============================================================================
# Schedule F — Line identification tests
# ============================================================================

class TestScheduleFLineIdentification:
    """Tests for Schedule F line item identification from descriptions."""

    def setup_method(self):
        from lab.pdf_validator.layouts.schedule_f import identify_line_item
        self.identify = identify_line_item

    def test_cash(self):
        result = self.identify("Cash")
        assert result is not None
        boy_field, eoy_field, line, desc = result
        assert boy_field == "BegngAcctPrdCashAmt"
        assert eoy_field == "EndAcctPrdCashAmt"
        assert line == "1"

    def test_trade_notes(self):
        result = self.identify("Trade notes & accounts receivable")
        assert result is not None
        assert result[0] == "BegngAcctPrdTradeNotesAmt"

    def test_inventories(self):
        result = self.identify("Inventories")
        assert result is not None
        assert result[0] == "BegngAcctPrdInventoriesAmt"

    def test_investment_subsidiaries(self):
        result = self.identify("Investment in subsidiaries")
        assert result is not None
        assert result[0] == "BegngAcctPrdInvstSubsidiaryAmt"

    def test_buildings(self):
        result = self.identify("Buildings & other depreciable assets")
        assert result is not None
        assert result[0] == "BegngAcctPrdBldgAndOtherAstAmt"

    def test_land(self):
        result = self.identify("Land")
        assert result is not None
        assert result[0] == "BegngAcctPrdLandAmt"

    def test_intangible(self):
        result = self.identify("Patents and other intangible assets")
        assert result is not None
        assert result[0] == "BegngAcctPrdPatentsOthAstAmt"

    def test_total_assets(self):
        result = self.identify("Total assets")
        assert result is not None
        assert result[0] == "BegngAcctPrdTotalAssetsAmt"
        assert result[1] == "EndAcctPrdTotalAssetsAmt"

    def test_accounts_payable(self):
        result = self.identify("Accounts payable")
        assert result is not None
        assert result[0] == "BegngAcctPrdAccountsPayableAmt"

    def test_capital_stock(self):
        result = self.identify("Capital stock")
        assert result is not None
        assert result[0] == "BegngAcctPrdCommonStockAmt"

    def test_retained_earnings(self):
        result = self.identify("Retained earnings")
        assert result is not None
        assert result[0] == "BegngAcctPrdRtnEarningsAmt"

    def test_total_liabilities_equity(self):
        result = self.identify("Total liabilities and shareholders equity")
        assert result is not None
        assert result[0] == "BegngAcctPrdTotLiabShrEqtyAmt"

    def test_case_insensitive(self):
        result = self.identify("TOTAL ASSETS")
        assert result is not None
        assert result[0] == "BegngAcctPrdTotalAssetsAmt"

    def test_unrecognized(self):
        assert self.identify("") is None
        assert self.identify("random text") is None


# ============================================================================
# Schedule F — Reconciliation tests
# ============================================================================

class TestScheduleFReconciliation:
    """Tests for Schedule F reconciliation pipeline."""

    def _mock_schf_pdf(self, records: list[dict]) -> pd.DataFrame:
        """Build DataFrame matching Schedule F extractor output."""
        df = pd.DataFrame(records, columns=[
            "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
        ])
        df.attrs["source"] = "test-schf.pdf"
        return df

    def test_schf_perfect_match(self):
        """Schedule F: identical PDF and XML values should all be OK."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdCashAmt", "field_name": "EndAcctPrdCashAmt",
             "value": 1000000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdTotalAssetsAmt", "field_name": "EndAcctPrdTotalAssetsAmt",
             "value": 5000000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "EndAcctPrdCashAmt"): 1000000.0,
            ("C0001", "N/A", "EndAcctPrdTotalAssetsAmt"): 5000000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2
        assert report.phantom_count == 0

    def test_schf_phantom_detected(self):
        """Schedule F: value in PDF not in XML should be PHANTOM."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "EndAcctPrdOtherAssetsAmt", "field_name": "EndAcctPrdOtherAssetsAmt",
             "value": 150000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1
        assert report.discrepancies[0].status == "PHANTOM"
        assert report.discrepancies[0].pdf_value == 150000.0

    def test_schf_missing_detected(self):
        """Schedule F: value in XML not in PDF should be MISSING."""
        pdf_df = self._mock_schf_pdf([])
        xml_values = {
            ("C0001", "N/A", "EndAcctPrdTotalAssetsAmt"): 5000000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.missing_count == 1

    def test_schf_mismatch_detected(self):
        """Schedule F: both have values but differ beyond tolerance."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdCashAmt", "field_name": "EndAcctPrdCashAmt",
             "value": 1000000.0},
        ])
        xml_values = {("C0001", "N/A", "EndAcctPrdCashAmt"): 900000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        assert report.discrepancies[0].delta == 100000.0

    def test_schf_boy_and_eoy_independent(self):
        """BOY and EOY are reconciled as separate fields."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "BegngAcctPrdCashAmt", "field_name": "BegngAcctPrdCashAmt",
             "value": 500000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdCashAmt", "field_name": "EndAcctPrdCashAmt",
             "value": 600000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "BegngAcctPrdCashAmt"): 500000.0,
            ("C0001", "N/A", "EndAcctPrdCashAmt"): 600000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2

    def test_schf_no_skip_pools(self):
        """Schedule F should not filter by skip_pools (that's Sch J only)."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdCashAmt", "field_name": "EndAcctPrdCashAmt",
             "value": 100.0},
        ])
        # Even if we pass skip_pools containing the field, it should NOT filter for Sch F
        xml_values = {("C0001", "N/A", "EndAcctPrdCashAmt"): 100.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 1
        assert report.ok_count == 1

    def test_schf_field_description_lookup(self):
        """Schedule F discrepancies should have human-readable descriptions."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdCashAmt", "field_name": "EndAcctPrdCashAmt",
             "value": 100000.0},
        ])
        xml_values = {("C0001", "N/A", "EndAcctPrdCashAmt"): 0.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.discrepancies[0].field_description == "Cash"

    def test_schf_multiple_entities(self):
        """Schedule F handles multiple entities correctly."""
        pdf_df = self._mock_schf_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "EndAcctPrdTotalAssetsAmt", "field_name": "EndAcctPrdTotalAssetsAmt",
             "value": 1000000.0},
            {"entity_name": "Corp B", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "EndAcctPrdTotalAssetsAmt", "field_name": "EndAcctPrdTotalAssetsAmt",
             "value": 2000000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "EndAcctPrdTotalAssetsAmt"): 1000000.0,
            ("C0002", "N/A", "EndAcctPrdTotalAssetsAmt"): 2000000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="F")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.entities_checked == 2
        assert report.ok_count == 2


# ============================================================================
# Schedule H — Line identification tests
# ============================================================================

class TestScheduleHLineIdentification:
    """Tests for Schedule H line item identification from descriptions."""

    def setup_method(self):
        from lab.pdf_validator.layouts.schedule_h import identify_line_item
        self.identify = identify_line_item

    def test_net_income_per_books(self):
        result = self.identify("Current year net income per books")
        assert result is not None
        xml_field, line, desc = result
        assert xml_field == "ForeignCYNetIncomePerBooksAmt"
        assert line == "1"

    def test_capital_gains(self):
        result = self.identify("Capital gains or losses")
        assert result is not None
        assert result[0] == "CapitalGainsOrLossesAmt"

    def test_depreciation(self):
        result = self.identify("Depreciation and amortization")
        assert result is not None
        assert result[0] == "DepreciationAndAmortizationAmt"

    def test_depletion(self):
        result = self.identify("Depletion")
        assert result is not None
        assert result[0] == "DepletionAmt"

    def test_statutory_reserves(self):
        result = self.identify("Charges to statutory reserves")
        assert result is not None
        assert result[0] == "ChargesToStatutoryReservesAmt"

    def test_inventory_adjustments(self):
        result = self.identify("Inventory adjustments")
        assert result is not None
        assert result[0] == "InventoryAdjustmentsAmt"

    def test_taxes_net_addition(self):
        result = self.identify("Income taxes (net addition)")
        assert result is not None
        assert result[0] == "TaxesNetAddnAmt"

    def test_foreign_currency(self):
        result = self.identify("Foreign currency gains/losses")
        assert result is not None
        assert result[0] == "FrgnCurrencyGainLossAddnAmt"

    def test_other_adjustments_addition(self):
        result = self.identify("Other adjustments (net addition)")
        assert result is not None
        assert result[0] == "OtherAdjustmentsNetAddnAmt"

    def test_other_adjustments_subtraction(self):
        result = self.identify("Other adjustments (net subtraction)")
        assert result is not None
        assert result[0] == "OtherAdjustmentsNetSbtrctnAmt"

    def test_total_net_additions(self):
        result = self.identify("Total net additions")
        assert result is not None
        assert result[0] == "TotalNetAdditionsAmt"

    def test_total_net_subtractions(self):
        result = self.identify("Total net subtractions")
        assert result is not None
        assert result[0] == "TotalNetSubtractionsAmt"

    def test_current_ep(self):
        result = self.identify("Current earnings and profits")
        assert result is not None
        assert result[0] == "CurrentEarningsAndProfitsAmt"
        assert result[1] == "5a"

    def test_dastm(self):
        result = self.identify("DASTM gain or loss")
        assert result is not None
        assert result[0] == "DASTMGainOrLossAmt"

    def test_ep_in_usd(self):
        result = self.identify("Current E&P in US dollars")
        assert result is not None
        assert result[0] == "CurrEarnAndPrftInUSDollarsAmt"

    def test_exchange_rate(self):
        result = self.identify("Exchange rate")
        assert result is not None
        assert result[0] == "ExchangeRt"
        assert result[1] == "5d(rate)"

    def test_case_insensitive(self):
        result = self.identify("TOTAL NET ADDITIONS")
        assert result is not None
        assert result[0] == "TotalNetAdditionsAmt"

    def test_unrecognized(self):
        assert self.identify("") is None
        assert self.identify("random text") is None


# ============================================================================
# Schedule H — Reconciliation tests
# ============================================================================

class TestScheduleHReconciliation:
    """Tests for Schedule H reconciliation pipeline."""

    def _mock_schh_pdf(self, records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(records, columns=[
            "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
        ])
        df.attrs["source"] = "test-schh.pdf"
        return df

    def test_schh_perfect_match(self):
        """Schedule H: identical PDF and XML values should all be OK."""
        pdf_df = self._mock_schh_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "CurrentEarningsAndProfitsAmt", "field_name": "CurrentEarningsAndProfitsAmt",
             "value": -500000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "CurrEarnAndPrftInUSDollarsAmt", "field_name": "CurrEarnAndPrftInUSDollarsAmt",
             "value": -450000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "CurrentEarningsAndProfitsAmt"): -500000.0,
            ("C0001", "N/A", "CurrEarnAndPrftInUSDollarsAmt"): -450000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="H")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2

    def test_schh_phantom_detected(self):
        """Schedule H: value in PDF not in XML should be PHANTOM."""
        pdf_df = self._mock_schh_pdf([
            {"entity_name": "Corp A", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "OtherAdjustmentsNetAddnAmt", "field_name": "OtherAdjustmentsNetAddnAmt",
             "value": 5000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="H")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1
        assert report.discrepancies[0].status == "PHANTOM"

    def test_schh_missing_detected(self):
        """Schedule H: value in XML not in PDF should be MISSING."""
        pdf_df = self._mock_schh_pdf([])
        xml_values = {
            ("C0001", "N/A", "ForeignCYNetIncomePerBooksAmt"): 1000000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="H")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.missing_count == 1

    def test_schh_exchange_rate(self):
        """Schedule H: exchange rate is reconciled same as amounts."""
        pdf_df = self._mock_schh_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ExchangeRt", "field_name": "ExchangeRt",
             "value": 0.7856},
        ])
        xml_values = {("C0001", "N/A", "ExchangeRt"): 0.7856}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="H")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1

    def test_schh_field_description_lookup(self):
        """Schedule H discrepancies should have human-readable descriptions."""
        pdf_df = self._mock_schh_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "CurrentEarningsAndProfitsAmt", "field_name": "CurrentEarningsAndProfitsAmt",
             "value": 100000.0},
        ])
        xml_values = {("C0001", "N/A", "CurrentEarningsAndProfitsAmt"): 0.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="H")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.discrepancies[0].field_description == "Current E&P"


# ============================================================================
# Schedule I-1 — Line identification tests
# ============================================================================

class TestScheduleI1LineIdentification:
    """Tests for Schedule I-1 line item identification from descriptions."""

    def setup_method(self):
        from lab.pdf_validator.layouts.schedule_i1 import identify_line_item
        self.identify = identify_line_item

    def test_gross_income(self):
        result = self.identify("Gross income")
        assert result is not None
        xml_field, line, desc = result
        assert xml_field == "GrossIncomeAmt"
        assert line == "1"

    def test_exclusion_eci(self):
        result = self.identify("Exclusion: effectively connected income")
        assert result is not None
        assert result[0] == "ExclGrossIncmEffCntdFCCorpAmt"

    def test_exclusion_subpart_f(self):
        result = self.identify("Exclusion: Subpart F income")
        assert result is not None
        assert result[0] == "ExclGrossIncmSubpartFIncmAmt"

    def test_exclusion_high_taxed(self):
        result = self.identify("Exclusion: high-taxed income")
        assert result is not None
        assert result[0] == "ExclGrossIncmHghTxdIncmAmt"

    def test_exclusion_dividends(self):
        result = self.identify("Exclusion: dividends received")
        assert result is not None
        assert result[0] == "ExclGrossIncmDvdRcvdAmt"

    def test_total_exclusions(self):
        result = self.identify("Total exclusions")
        assert result is not None
        assert result[0] == "TotalExclusionsAmt"

    def test_gross_income_less_exclusions(self):
        result = self.identify("Gross income less exclusions")
        assert result is not None
        assert result[0] == "GrossIncmLessExclusionsAmt"

    def test_allocable_deductions(self):
        result = self.identify("Allocable deductions and expenses")
        assert result is not None
        assert result[0] == "AllocableDedExpnssAmt"

    def test_tested_income(self):
        result = self.identify("Tested income")
        assert result is not None
        assert result[0] == "TestedIncomeAmt"
        assert result[1] == "6(pos)"

    def test_tested_loss(self):
        result = self.identify("Tested loss")
        assert result is not None
        assert result[0] == "TestedLossAmt"
        assert result[1] == "6(neg)"

    def test_qbai(self):
        result = self.identify("QBAI")
        assert result is not None
        assert result[0] == "QBAIAmt"
        assert result[1] == "8"

    def test_tested_interest_expense(self):
        result = self.identify("Tested interest expense")
        assert result is not None
        assert result[0] == "TestedInterestExpenseAmt"

    def test_tested_interest_income(self):
        result = self.identify("Tested interest income")
        assert result is not None
        assert result[0] == "TestedInterestIncomeAmt"

    def test_case_insensitive(self):
        result = self.identify("TESTED INCOME")
        assert result is not None
        assert result[0] == "TestedIncomeAmt"

    def test_unrecognized(self):
        assert self.identify("") is None
        assert self.identify("random text") is None


# ============================================================================
# Schedule I-1 — Reconciliation tests
# ============================================================================

class TestScheduleI1Reconciliation:
    """Tests for Schedule I-1 reconciliation pipeline."""

    def _mock_schi1_pdf(self, records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(records, columns=[
            "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
        ])
        df.attrs["source"] = "test-schi1.pdf"
        return df

    def test_schi1_perfect_match(self):
        """Schedule I-1: identical PDF and XML values should all be OK."""
        pdf_df = self._mock_schi1_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "TestedIncomeAmt", "field_name": "TestedIncomeAmt",
             "value": 250000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "QBAIAmt", "field_name": "QBAIAmt",
             "value": 1500000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "TestedIncomeAmt"): 250000.0,
            ("C0001", "N/A", "QBAIAmt"): 1500000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I1")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2

    def test_schi1_phantom_detected(self):
        """Schedule I-1: value in PDF not in XML should be PHANTOM."""
        pdf_df = self._mock_schi1_pdf([
            {"entity_name": "Corp B", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "TestedIncomeAmt", "field_name": "TestedIncomeAmt",
             "value": 250000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I1")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1
        assert report.discrepancies[0].status == "PHANTOM"

    def test_schi1_tested_income_vs_loss(self):
        """Schedule I-1: tested income and tested loss are separate fields."""
        pdf_df = self._mock_schi1_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "TestedIncomeAmt", "field_name": "TestedIncomeAmt",
             "value": 0.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "TestedLossAmt", "field_name": "TestedLossAmt",
             "value": 100000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "TestedLossAmt"): 100000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I1")
        report = reconciler.reconcile_against_values(xml_values)

        # Both fields reconcile OK: TestedIncome=0 on both sides, TestedLoss matches
        assert report.ok_count == 2
        assert report.phantom_count == 0

    def test_schi1_field_description_lookup(self):
        """Schedule I-1 discrepancies should have human-readable descriptions."""
        pdf_df = self._mock_schi1_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "QBAIAmt", "field_name": "QBAIAmt",
             "value": 1500000.0},
        ])
        xml_values = {("C0001", "N/A", "QBAIAmt"): 0.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I1")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.discrepancies[0].field_description == "QBAI"

    def test_schi1_multiple_entities(self):
        """Schedule I-1 handles multiple entities correctly."""
        pdf_df = self._mock_schi1_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "GrossIncomeAmt", "field_name": "GrossIncomeAmt",
             "value": 500000.0},
            {"entity_name": "Corp B", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "GrossIncomeAmt", "field_name": "GrossIncomeAmt",
             "value": 750000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "GrossIncomeAmt"): 500000.0,
            ("C0002", "N/A", "GrossIncomeAmt"): 750000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I1")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.entities_checked == 2
        assert report.ok_count == 2


# ============================================================================
# Schedule G — Line identification tests
# ============================================================================

class TestScheduleGLineIdentification:
    """Tests for Schedule G line item identification from descriptions."""

    def setup_method(self):
        from lab.pdf_validator.layouts.schedule_g import identify_line_item
        self.identify = identify_line_item

    def test_expatriated_subsidiary(self):
        result = self.identify("Expatriated foreign subsidiary")
        assert result is not None
        xml_field, field_type, line, desc = result
        assert xml_field == "ExpatriatedFrgnSubsidiaryInd"
        assert field_type == "indicator"
        assert line == "4"

    def test_base_erosion(self):
        result = self.identify("Base erosion payments")
        assert result is not None
        assert result[0] == "BaseErosionPaymentBenefitInd"
        assert result[1] == "indicator"

    def test_section_909(self):
        result = self.identify("Section 909 splitter arrangement")
        assert result is not None
        assert result[0] == "ForeignTaxSection909Ind"

    def test_fdii(self):
        result = self.identify("FDII benefits claimed")
        assert result is not None
        assert result[0] == "FDIIBenefitsClaimInd"

    def test_reportable_transaction(self):
        result = self.identify("Reportable transaction participant")
        assert result is not None
        assert result[0] == "ReportableTransactionPrtcptInd"

    def test_disallowed_interest(self):
        result = self.identify("Disallowed interest expense under 163(j)")
        assert result is not None
        assert result[0] == "DisallowedInterestExpenseInd"
        assert result[1] == "indicator"

    def test_163j_carryforward(self):
        result = self.identify("163(j) carryforward amount")
        assert result is not None
        assert result[0] == "CfwdPrevDsallwIntExpenseAmt"
        assert result[1] == "amount"

    def test_pillar_two(self):
        result = self.identify("Top-up tax (Pillar Two)")
        assert result is not None
        assert result[0] == "PayOrAccrueTopUpTaxInd"
        assert result[1] == "indicator"

    def test_case_insensitive(self):
        result = self.identify("BASE EROSION PAYMENTS")
        assert result is not None
        assert result[0] == "BaseErosionPaymentBenefitInd"

    def test_unrecognized(self):
        assert self.identify("") is None
        assert self.identify("random text") is None


# ============================================================================
# Schedule G — Reconciliation tests
# ============================================================================

class TestScheduleGReconciliation:
    """Tests for Schedule G reconciliation pipeline."""

    def _mock_schg_pdf(self, records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(records, columns=[
            "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
        ])
        df.attrs["source"] = "test-schg.pdf"
        return df

    def test_schg_indicators_match(self):
        """Schedule G: matching indicator values should be OK."""
        pdf_df = self._mock_schg_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "DisallowedInterestExpenseInd", "field_name": "DisallowedInterestExpenseInd",
             "value": 1.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "BaseErosionPaymentBenefitInd", "field_name": "BaseErosionPaymentBenefitInd",
             "value": 0.0},
        ])
        xml_values = {
            ("C0001", "N/A", "DisallowedInterestExpenseInd"): 1.0,
            ("C0001", "N/A", "BaseErosionPaymentBenefitInd"): 0.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="G")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.total_comparisons == 2
        assert report.ok_count == 2

    def test_schg_phantom_indicator(self):
        """Schedule G: indicator in PDF not in XML should be PHANTOM."""
        pdf_df = self._mock_schg_pdf([
            {"entity_name": "Corp A", "reference_id": "C0002", "basket": "N/A",
             "pool_name": "DisallowedInterestExpenseInd", "field_name": "DisallowedInterestExpenseInd",
             "value": 1.0},
        ])
        xml_values = {}

        # tolerance=0.5 because indicators are binary (0/1), not dollar amounts
        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="G", tolerance=0.5)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1

    def test_schg_amount_field(self):
        """Schedule G: 163(j) carryforward amount reconciles as normal."""
        pdf_df = self._mock_schg_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "CfwdPrevDsallwIntExpenseAmt", "field_name": "CfwdPrevDsallwIntExpenseAmt",
             "value": 75000.0},
        ])
        xml_values = {("C0001", "N/A", "CfwdPrevDsallwIntExpenseAmt"): 75000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="G")
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1

    def test_schg_indicator_mismatch(self):
        """Schedule G: indicator flip (PDF=Yes, XML=No) detected as PHANTOM."""
        pdf_df = self._mock_schg_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "FDIIBenefitsClaimInd", "field_name": "FDIIBenefitsClaimInd",
             "value": 1.0},
        ])
        xml_values = {("C0001", "N/A", "FDIIBenefitsClaimInd"): 0.0}

        # tolerance=0.5 for binary indicators
        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="G", tolerance=0.5)
        report = reconciler.reconcile_against_values(xml_values)

        # PDF=1, XML=0 → PHANTOM (PDF has value, XML doesn't)
        assert report.phantom_count == 1

    def test_schg_field_description_lookup(self):
        """Schedule G discrepancies should have human-readable descriptions."""
        pdf_df = self._mock_schg_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "PayOrAccrueTopUpTaxInd", "field_name": "PayOrAccrueTopUpTaxInd",
             "value": 1.0},
        ])
        xml_values = {("C0001", "N/A", "PayOrAccrueTopUpTaxInd"): 0.0}

        # tolerance=0.5 for binary indicators
        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="G", tolerance=0.5)
        report = reconciler.reconcile_against_values(xml_values)

        assert "Pillar Two" in report.discrepancies[0].field_description


# ============================================================================
# Page 1 / Schedule A tests
# ============================================================================

class TestPage1ScheduleALayout:
    """Tests for Page 1 / Schedule A field identification."""

    def test_voting_stock_identified(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_page1_field
        result = identify_page1_field("Voting stock owned percentage")
        assert result is not None
        assert result[0] == "VotingStockOwnedPct"
        assert result[1] == "percentage"

    def test_voting_stock_percent_sign(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_page1_field
        result = identify_page1_field("% of voting stock")
        assert result is not None
        assert result[0] == "VotingStockOwnedPct"

    def test_direct_percent(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_page1_field
        result = identify_page1_field("Direct percentage of voting stock owned")
        assert result is not None
        assert result[0] == "VotingStockOwnedPct"

    def test_unrelated_text_returns_none(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_page1_field
        assert identify_page1_field("Form 5471") is None
        assert identify_page1_field("") is None
        assert identify_page1_field("Schedule A") is None

    def test_scha_begin_shares(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_scha_field
        result = identify_scha_field("Beginning of annual accounting period")
        assert result is not None
        assert result[0] == "AnnualAcctPeriodBeginShareCnt"

    def test_scha_end_shares(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_scha_field
        result = identify_scha_field("End of annual accounting period")
        assert result is not None
        assert result[0] == "AnnualAcctPeriodEndShareCnt"

    def test_scha_begin_alt(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_scha_field
        result = identify_scha_field("Shares at beginning of period")
        assert result is not None
        assert result[0] == "AnnualAcctPeriodBeginShareCnt"

    def test_scha_end_alt(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_scha_field
        result = identify_scha_field("Shares at end of period")
        assert result is not None
        assert result[0] == "AnnualAcctPeriodEndShareCnt"

    def test_scha_unrelated(self):
        from lab.pdf_validator.layouts.page1_schedule_a import identify_scha_field
        assert identify_scha_field("Stock class description") is None
        assert identify_scha_field("") is None

    def test_parse_percentage(self):
        from lab.pdf_validator.layouts.page1_schedule_a import parse_percentage
        assert parse_percentage("0.60800") == 0.608
        assert parse_percentage("60.8%") == 60.8
        assert parse_percentage("1.00000") == 1.0
        assert parse_percentage("") is None
        assert parse_percentage(None) is None

    def test_parse_share_count(self):
        from lab.pdf_validator.layouts.page1_schedule_a import parse_share_count
        assert parse_share_count("265,401") == 265401.0
        assert parse_share_count("8741303") == 8741303.0
        assert parse_share_count("25000") == 25000.0
        assert parse_share_count("") is None
        assert parse_share_count("-") is None
        assert parse_share_count("0") is None

    def test_field_description_simple(self):
        from lab.pdf_validator.layouts.page1_schedule_a import get_field_description
        desc = get_field_description("VotingStockOwnedPct")
        assert "Voting" in desc
        assert "Line 3" in desc

    def test_field_description_compound(self):
        from lab.pdf_validator.layouts.page1_schedule_a import get_field_description
        desc = get_field_description("COMMON A|AnnualAcctPeriodBeginShareCnt")
        assert "COMMON A" in desc
        assert "beginning" in desc.lower()


class TestPage1ScheduleAReconciliation:
    """Tests for Page 1 / Schedule A reconciliation against XML."""

    def _mock_page1a_pdf(self, records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-page1a.pdf"
        return df

    def test_voting_stock_exact_match(self):
        """Voting stock % in PDF matches XML → OK."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "VotingStockOwnedPct", "field_name": "VotingStockOwnedPct",
             "value": 0.608},
        ])
        xml_values = {("C0001", "N/A", "VotingStockOwnedPct"): 0.608}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=0.001)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1
        assert report.mismatch_count == 0

    def test_share_count_match(self):
        """Share counts in PDF match XML → OK."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt",
             "field_name": "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt",
             "value": 265401.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ORDINARY SHARES|AnnualAcctPeriodEndShareCnt",
             "field_name": "ORDINARY SHARES|AnnualAcctPeriodEndShareCnt",
             "value": 265401.0},
        ])
        xml_values = {
            ("C0001", "N/A", "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt"): 265401.0,
            ("C0001", "N/A", "ORDINARY SHARES|AnnualAcctPeriodEndShareCnt"): 265401.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 2
        assert report.mismatch_count == 0

    def test_share_count_mismatch(self):
        """Share count differs between PDF and XML → MISMATCH."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "PREFERRED|AnnualAcctPeriodEndShareCnt",
             "field_name": "PREFERRED|AnnualAcctPeriodEndShareCnt",
             "value": 9000000.0},
        ])
        xml_values = {("C0001", "N/A", "PREFERRED|AnnualAcctPeriodEndShareCnt"): 8741303.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        disc = report.discrepancies[0]
        assert disc.pdf_value == 9000000.0
        assert disc.xml_value == 8741303.0

    def test_phantom_stock_class(self):
        """PDF has stock class not in XML → PHANTOM."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "CLASS B|AnnualAcctPeriodBeginShareCnt",
             "field_name": "CLASS B|AnnualAcctPeriodBeginShareCnt",
             "value": 100.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1

    def test_missing_from_pdf(self):
        """XML has stock data not found in PDF → MISSING."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt",
             "field_name": "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt",
             "value": 265401.0},
        ])
        xml_values = {
            ("C0001", "N/A", "ORDINARY SHARES|AnnualAcctPeriodBeginShareCnt"): 265401.0,
            ("C0001", "N/A", "ORDINARY SHARES|AnnualAcctPeriodEndShareCnt"): 265401.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1
        assert report.missing_count == 1

    def test_field_display_compound_key(self):
        """Schedule A compound keys should display with stock class name."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "COMMON A|AnnualAcctPeriodBeginShareCnt",
             "field_name": "COMMON A|AnnualAcctPeriodBeginShareCnt",
             "value": 874130.0},
        ])
        xml_values = {("C0001", "N/A", "COMMON A|AnnualAcctPeriodBeginShareCnt"): 999999.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        assert "COMMON A" in report.discrepancies[0].field_description

    def test_multi_class_entity(self):
        """Entity with multiple stock classes reconciles each independently."""
        pdf_df = self._mock_page1a_pdf([
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "COMMON A|AnnualAcctPeriodBeginShareCnt",
             "field_name": "COMMON A|AnnualAcctPeriodBeginShareCnt",
             "value": 874130.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "COMMON A|AnnualAcctPeriodEndShareCnt",
             "field_name": "COMMON A|AnnualAcctPeriodEndShareCnt",
             "value": 874130.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "PREFERRED|AnnualAcctPeriodBeginShareCnt",
             "field_name": "PREFERRED|AnnualAcctPeriodBeginShareCnt",
             "value": 8741303.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "PREFERRED|AnnualAcctPeriodEndShareCnt",
             "field_name": "PREFERRED|AnnualAcctPeriodEndShareCnt",
             "value": 8741303.0},
        ])
        xml_values = {
            ("X0001", "N/A", "COMMON A|AnnualAcctPeriodBeginShareCnt"): 874130.0,
            ("X0001", "N/A", "COMMON A|AnnualAcctPeriodEndShareCnt"): 874130.0,
            ("X0001", "N/A", "PREFERRED|AnnualAcctPeriodBeginShareCnt"): 8741303.0,
            ("X0001", "N/A", "PREFERRED|AnnualAcctPeriodEndShareCnt"): 8741303.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="A", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 4
        assert report.mismatch_count == 0


# ============================================================================
# Schedule B (Shareholders) tests
# ============================================================================

class TestScheduleBLayout:
    """Tests for Schedule B layout module."""

    def test_normalize_shareholder_name(self):
        from lab.pdf_validator.layouts.schedule_b import normalize_shareholder_name
        assert normalize_shareholder_name("Acme Ohio Corp") == "ACME OHIO CORP"
        assert normalize_shareholder_name("  ALPHA GROUP LIMITED  ") == "ALPHA GROUP LIMITED"
        assert normalize_shareholder_name("Delta Family Holdings 1 Corp.") == "DELTA FAMILY HOLDINGS 1 CORP"

    def test_normalize_collapses_whitespace(self):
        from lab.pdf_validator.layouts.schedule_b import normalize_shareholder_name
        assert normalize_shareholder_name("SAMPLE   CORP   HOLDINGS") == "SAMPLE CORP HOLDINGS"

    def test_normalize_empty(self):
        from lab.pdf_validator.layouts.schedule_b import normalize_shareholder_name
        assert normalize_shareholder_name("") == ""
        assert normalize_shareholder_name(None) == ""

    def test_parse_ein(self):
        from lab.pdf_validator.layouts.schedule_b import parse_ein
        assert parse_ein("99-1234567") == "991234567"
        assert parse_ein("991234567") == "991234567"
        assert parse_ein("EIN: 99-7654321") == "997654321"
        assert parse_ein("") is None
        assert parse_ein("123") is None

    def test_field_description_part2(self):
        from lab.pdf_validator.layouts.schedule_b import get_field_description
        desc = get_field_description("SAMPLE CORP|ORDINARY|AnnualAcctPeriodBeginShareCnt")
        assert "SAMPLE CORP" in desc
        assert "ORDINARY" in desc
        assert "beginning" in desc.lower()

    def test_field_description_part1(self):
        from lab.pdf_validator.layouts.schedule_b import get_field_description
        desc = get_field_description("VENTRA OHIO CORP|ShareholderEIN")
        assert "VENTRA OHIO CORP" in desc
        assert "EIN" in desc

    def test_field_description_base(self):
        from lab.pdf_validator.layouts.schedule_b import get_field_description
        desc = get_field_description("ShareholderEIN")
        assert "EIN" in desc


class TestScheduleBReconciliation:
    """Tests for Schedule B reconciliation."""

    def _mock_schb_pdf(self, records: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-schb.pdf"
        return df

    def test_part2_share_count_match(self):
        """Part II share counts match → OK."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "SAMPLE CORP|ORDINARY|AnnualAcctPeriodBeginShareCnt",
             "field_name": "SAMPLE CORP|ORDINARY|AnnualAcctPeriodBeginShareCnt",
             "value": 801730174.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "SAMPLE CORP|ORDINARY|AnnualAcctPeriodEndShareCnt",
             "field_name": "SAMPLE CORP|ORDINARY|AnnualAcctPeriodEndShareCnt",
             "value": 801730174.0},
        ])
        xml_values = {
            ("C0001", "N/A", "SAMPLE CORP|ORDINARY|AnnualAcctPeriodBeginShareCnt"): 801730174.0,
            ("C0001", "N/A", "SAMPLE CORP|ORDINARY|AnnualAcctPeriodEndShareCnt"): 801730174.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 2
        assert report.mismatch_count == 0

    def test_part1_ein_match(self):
        """Part I EIN matches → OK (tolerance=1 for integer comparison)."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "VENTRA OHIO CORP|ShareholderEIN",
             "field_name": "VENTRA OHIO CORP|ShareholderEIN",
             "value": 320079365.0},
        ])
        xml_values = {("C0001", "N/A", "VENTRA OHIO CORP|ShareholderEIN"): 320079365.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=1.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1

    def test_part2_share_count_mismatch(self):
        """Part II share count differs → MISMATCH."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ALPHA GROUP LIMITED|ORDINARY|AnnualAcctPeriodEndShareCnt",
             "field_name": "ALPHA GROUP LIMITED|ORDINARY|AnnualAcctPeriodEndShareCnt",
             "value": 20000000.0},
        ])
        xml_values = {("C0001", "N/A", "ALPHA GROUP LIMITED|ORDINARY|AnnualAcctPeriodEndShareCnt"): 20000001.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=0.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        disc = report.discrepancies[0]
        assert disc.pdf_value == 20000000.0
        assert disc.xml_value == 20000001.0

    def test_phantom_shareholder(self):
        """PDF has shareholder not in XML → PHANTOM."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "GHOST CORP|COMMON|AnnualAcctPeriodBeginShareCnt",
             "field_name": "GHOST CORP|COMMON|AnnualAcctPeriodBeginShareCnt",
             "value": 1000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.phantom_count == 1

    def test_missing_shareholder(self):
        """XML has shareholder not in PDF → MISSING."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "HOLDER A|CLASS X|AnnualAcctPeriodBeginShareCnt",
             "field_name": "HOLDER A|CLASS X|AnnualAcctPeriodBeginShareCnt",
             "value": 500.0},
        ])
        xml_values = {
            ("C0001", "N/A", "HOLDER A|CLASS X|AnnualAcctPeriodBeginShareCnt"): 500.0,
            ("C0001", "N/A", "HOLDER A|CLASS X|AnnualAcctPeriodEndShareCnt"): 500.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 1
        assert report.missing_count == 1

    def test_field_display_part2(self):
        """Part II field display includes shareholder and class names."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "SAMPLE CORP|PREFERENCE|AnnualAcctPeriodEndShareCnt",
             "field_name": "SAMPLE CORP|PREFERENCE|AnnualAcctPeriodEndShareCnt",
             "value": 5000.0},
        ])
        xml_values = {("C0001", "N/A", "SAMPLE CORP|PREFERENCE|AnnualAcctPeriodEndShareCnt"): 100.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.mismatch_count == 1
        assert "SAMPLE CORP" in report.discrepancies[0].field_description
        assert "PREFERENCE" in report.discrepancies[0].field_description

    def test_multi_shareholder_entity(self):
        """Entity with multiple shareholders reconciles each independently."""
        pdf_df = self._mock_schb_pdf([
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "HOLDER A|COMMON|AnnualAcctPeriodBeginShareCnt",
             "field_name": "HOLDER A|COMMON|AnnualAcctPeriodBeginShareCnt",
             "value": 100.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "HOLDER A|COMMON|AnnualAcctPeriodEndShareCnt",
             "field_name": "HOLDER A|COMMON|AnnualAcctPeriodEndShareCnt",
             "value": 100.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "HOLDER B|PREFERRED|AnnualAcctPeriodBeginShareCnt",
             "field_name": "HOLDER B|PREFERRED|AnnualAcctPeriodBeginShareCnt",
             "value": 500.0},
            {"entity_name": "Corp X", "reference_id": "X0001", "basket": "N/A",
             "pool_name": "HOLDER B|PREFERRED|AnnualAcctPeriodEndShareCnt",
             "field_name": "HOLDER B|PREFERRED|AnnualAcctPeriodEndShareCnt",
             "value": 500.0},
        ])
        xml_values = {
            ("X0001", "N/A", "HOLDER A|COMMON|AnnualAcctPeriodBeginShareCnt"): 100.0,
            ("X0001", "N/A", "HOLDER A|COMMON|AnnualAcctPeriodEndShareCnt"): 100.0,
            ("X0001", "N/A", "HOLDER B|PREFERRED|AnnualAcctPeriodBeginShareCnt"): 500.0,
            ("X0001", "N/A", "HOLDER B|PREFERRED|AnnualAcctPeriodEndShareCnt"): 500.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="B", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)

        assert report.ok_count == 4
        assert report.mismatch_count == 0


# ============================================================================
# Schedule C (Income Statement) Tests
# ============================================================================

class TestScheduleCLayout:
    """Tests for Schedule C line identification."""

    def test_gross_receipts(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Gross receipts or sales")
        assert result is not None
        assert result[0] == "ForeignGrossReceiptsOrSalesAmt"

    def test_cost_of_goods_sold(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Cost of goods sold")
        assert result is not None
        assert result[0] == "ForeignCostOfGoodsSoldAmt"

    def test_gross_profit(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Gross profit")
        assert result is not None
        assert result[0] == "ForeignGrossProfitAmt"

    def test_dividends(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Dividends")
        assert result is not None
        assert result[0] == "ForeignDividendIncomeAmt"

    def test_interest_income(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Interest income")
        assert result is not None
        assert result[0] == "ForeignInterestIncomeAmt"

    def test_net_income(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Net income per books")
        assert result is not None
        assert result[0] == "ForeignCYNetIncomePerBookAmt"

    def test_total_deductions(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Total deductions")
        assert result is not None
        assert result[0] == "ForeignTotalDeductionsAmt"

    def test_other_deductions(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        result = identify_line_item("Other deductions")
        assert result is not None
        assert result[0] == "ForeignOtherDeductionsAmt"

    def test_field_description(self):
        from lab.pdf_validator.layouts.schedule_c import get_field_description
        desc = get_field_description("ForeignGrossProfitAmt")
        assert "Gross profit" in desc
        assert "3" in desc

    def test_no_match(self):
        from lab.pdf_validator.layouts.schedule_c import identify_line_item
        assert identify_line_item("Some random text") is None
        assert identify_line_item("") is None


class TestScheduleCReconciliation:
    """Tests for Schedule C reconciliation logic."""

    @staticmethod
    def _mock_schc_pdf(records):
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-schc.pdf"
        return df

    def test_exact_match(self):
        pdf_df = self._mock_schc_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ForeignGrossProfitAmt", "field_name": "ForeignGrossProfitAmt",
             "value": 500000.0},
        ])
        xml_values = {("C0001", "N/A", "ForeignGrossProfitAmt"): 500000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="C", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1
        assert report.mismatch_count == 0

    def test_mismatch(self):
        pdf_df = self._mock_schc_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ForeignTotalIncomeAmt", "field_name": "ForeignTotalIncomeAmt",
             "value": 1000000.0},
        ])
        xml_values = {("C0001", "N/A", "ForeignTotalIncomeAmt"): 900000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="C", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.mismatch_count == 1

    def test_phantom(self):
        pdf_df = self._mock_schc_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ForeignOtherIncomeAmt", "field_name": "ForeignOtherIncomeAmt",
             "value": 50000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="C", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.phantom_count == 1

    def test_missing(self):
        pdf_df = self._mock_schc_pdf([])
        xml_values = {("C0001", "N/A", "ForeignNetGainLossAmt"): 75000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="C", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.missing_count == 1

    def test_field_display(self):
        pdf_df = self._mock_schc_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "ForeignInterestExpenseAmt", "field_name": "ForeignInterestExpenseAmt",
             "value": 25000.0},
        ])
        xml_values = {("C0001", "N/A", "ForeignInterestExpenseAmt"): 25000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="C", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert "Interest expense" in report.items[0].field_description


# ============================================================================
# Schedule E (Foreign Taxes) Tests
# ============================================================================

class TestScheduleELayout:
    """Tests for Schedule E field identification."""

    def test_summary_total_fc(self):
        from lab.pdf_validator.layouts.schedule_e import identify_line_item
        result = identify_line_item("Total tax in functional currency")
        assert result is not None
        assert result[0] == "TotalTaxInFunctionalCurAmt"

    def test_group_field_with_context(self):
        from lab.pdf_validator.layouts.schedule_e import identify_line_item
        result = identify_line_item("Taxes deemed paid", group_context="Frm5471SchETestedIncomeGrp")
        assert result is not None
        assert result[0] == "Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt"

    def test_detect_group_context(self):
        from lab.pdf_validator.layouts.schedule_e import detect_group_context
        assert detect_group_context("Subpart F income") == "Frm5471SchESubpartFIncomeGrp"
        assert detect_group_context("Tested income (GILTI)") == "Frm5471SchETestedIncomeGrp"
        assert detect_group_context("Residual income") == "Frm5471SchEResidualIncomeGrp"
        assert detect_group_context("random text") is None

    def test_get_field_description_compound(self):
        from lab.pdf_validator.layouts.schedule_e import get_field_description
        desc = get_field_description("Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt")
        assert "Tested income" in desc
        assert "Taxes deemed paid" in desc

    def test_get_field_description_simple(self):
        from lab.pdf_validator.layouts.schedule_e import get_field_description
        desc = get_field_description("TotalTaxInFunctionalCurAmt")
        assert "functional currency" in desc.lower()


class TestScheduleEReconciliation:
    """Tests for Schedule E reconciliation logic."""

    @staticmethod
    def _mock_sche_pdf(records):
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-sche.pdf"
        return df

    def test_compound_key_match(self):
        pdf_df = self._mock_sche_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt",
             "field_name": "Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt",
             "value": 12000.0},
        ])
        xml_values = {("C0001", "GEN", "Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt"): 12000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="E", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1

    def test_multi_basket(self):
        pdf_df = self._mock_sche_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "TotalTaxInUSDollarsAmt",
             "field_name": "TotalTaxInUSDollarsAmt", "value": 5000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "PAS",
             "pool_name": "TotalTaxInUSDollarsAmt",
             "field_name": "TotalTaxInUSDollarsAmt", "value": 3000.0},
        ])
        xml_values = {
            ("C0001", "GEN", "TotalTaxInUSDollarsAmt"): 5000.0,
            ("C0001", "PAS", "TotalTaxInUSDollarsAmt"): 3000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="E", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 2


# ============================================================================
# Schedule I (Shareholder's Income) Tests
# ============================================================================

class TestScheduleILayout:
    """Tests for Schedule I line identification."""

    def test_subpart_f_fphci(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("Foreign personal holding company income (FPHCI)")
        assert result is not None
        assert result[0] == "SubpartFPHCIncomeAmt"
        assert result[1] == "amount"

    def test_subpart_f_sales(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("Subpart F sales income")
        assert result is not None
        assert result[0] == "SubpartFSalesIncomeAmt"

    def test_earnings_us_property(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("Earnings invested in US property")
        assert result is not None
        assert result[0] == "EarningsInvestedInUSPropAmt"

    def test_245a_dividends(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("Section 245A eligible dividends")
        assert result is not None
        assert result[0] == "Sect245AEligibleDividendsAmt"

    def test_income_blocked_indicator(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("Income blocked")
        assert result is not None
        assert result[0] == "IncomeBlockedInd"
        assert result[1] == "indicator"

    def test_ed_account_indicator(self):
        from lab.pdf_validator.layouts.schedule_i import identify_line_item
        result = identify_line_item("E&D account")
        assert result is not None
        assert result[0] == "EDAccountInd"
        assert result[1] == "indicator"

    def test_parse_indicator(self):
        from lab.pdf_validator.layouts.schedule_i import parse_indicator
        assert parse_indicator("X") == 1.0
        assert parse_indicator("Yes") == 1.0
        assert parse_indicator("") == 0.0
        assert parse_indicator("No") == 0.0


class TestScheduleIReconciliation:
    """Tests for Schedule I reconciliation logic."""

    @staticmethod
    def _mock_schi_pdf(records):
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-schi.pdf"
        return df

    def test_amount_match(self):
        pdf_df = self._mock_schi_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "SubpartFPHCIncomeAmt", "field_name": "SubpartFPHCIncomeAmt",
             "value": 250000.0},
        ])
        xml_values = {("C0001", "N/A", "SubpartFPHCIncomeAmt"): 250000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1

    def test_indicator_match(self):
        pdf_df = self._mock_schi_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "IncomeBlockedInd", "field_name": "IncomeBlockedInd",
             "value": 1.0},
        ])
        xml_values = {("C0001", "N/A", "IncomeBlockedInd"): 1.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1

    def test_field_display(self):
        pdf_df = self._mock_schi_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "Sect245AEligibleDividendsAmt",
             "field_name": "Sect245AEligibleDividendsAmt", "value": 100000.0},
        ])
        xml_values = {("C0001", "N/A", "Sect245AEligibleDividendsAmt"): 100000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="I", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert "245A" in report.items[0].field_description


# ============================================================================
# Schedule P (Previously Taxed E&P) Tests
# ============================================================================

class TestSchedulePLayout:
    """Tests for Schedule P pool identification."""

    def test_detect_fc_951a_pool(self):
        from lab.pdf_validator.layouts.schedule_p import detect_pool_context
        result = detect_pool_context("FC Section 951A PTEP")
        assert result == "FCSection951APTEPGrp"

    def test_detect_us_total(self):
        from lab.pdf_validator.layouts.schedule_p import detect_pool_context
        result = detect_pool_context("US Total PTEP")
        assert result == "USTotalPTEPGrp"

    def test_identify_with_context(self):
        from lab.pdf_validator.layouts.schedule_p import identify_line_item
        result = identify_line_item("Beginning year balance", pool_context="FCSection951APTEPGrp")
        assert result is not None
        assert result[0] == "FCSection951APTEPGrp|BeginningYearBalanceAmt"

    def test_get_field_description_compound(self):
        from lab.pdf_validator.layouts.schedule_p import get_field_description
        desc = get_field_description("FCSection951APTEPGrp|BeginningYearBalanceAmt")
        assert "951A" in desc
        assert "Beginning" in desc

    def test_no_pool_context(self):
        from lab.pdf_validator.layouts.schedule_p import identify_line_item
        result = identify_line_item("random text without pool context")
        assert result is None


class TestSchedulePReconciliation:
    """Tests for Schedule P reconciliation logic."""

    @staticmethod
    def _mock_schp_pdf(records):
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-schp.pdf"
        return df

    def test_compound_key_match(self):
        pdf_df = self._mock_schp_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "FCSection951APTEPGrp|BeginningYearBalanceAmt",
             "field_name": "FCSection951APTEPGrp|BeginningYearBalanceAmt",
             "value": 1000000.0},
        ])
        xml_values = {("C0001", "GEN", "FCSection951APTEPGrp|BeginningYearBalanceAmt"): 1000000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="P", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1

    def test_multi_pool_entity(self):
        pdf_df = self._mock_schp_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "FCSection951APTEPGrp|BeginningYearBalanceAmt",
             "field_name": "FCSection951APTEPGrp|BeginningYearBalanceAmt",
             "value": 500000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "FCSection245AdPTEPGrp|BalanceBeginningNextYearAmt",
             "field_name": "FCSection245AdPTEPGrp|BalanceBeginningNextYearAmt",
             "value": 200000.0},
        ])
        xml_values = {
            ("C0001", "GEN", "FCSection951APTEPGrp|BeginningYearBalanceAmt"): 500000.0,
            ("C0001", "GEN", "FCSection245AdPTEPGrp|BalanceBeginningNextYearAmt"): 200000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="P", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 2
        assert report.mismatch_count == 0

    def test_mismatch(self):
        pdf_df = self._mock_schp_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "GEN",
             "pool_name": "USTotalPTEPGrp|TotalPreviouslyTaxedEPAmt",
             "field_name": "USTotalPTEPGrp|TotalPreviouslyTaxedEPAmt",
             "value": 750000.0},
        ])
        xml_values = {("C0001", "GEN", "USTotalPTEPGrp|TotalPreviouslyTaxedEPAmt"): 600000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="P", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.mismatch_count == 1


# ============================================================================
# Schedule R (Distributions) Tests
# ============================================================================

class TestScheduleRLayout:
    """Tests for Schedule R field identification."""

    def test_identify_column_date(self):
        from lab.pdf_validator.layouts.schedule_r import identify_column
        assert identify_column("Date") == "DistributionDt"

    def test_identify_column_amount(self):
        from lab.pdf_validator.layouts.schedule_r import identify_column
        assert identify_column("Functional currency amount") == "DistributionFuncCurAmt"

    def test_identify_column_ep(self):
        from lab.pdf_validator.layouts.schedule_r import identify_column
        assert identify_column("From E&P amount") == "DistributionFromEPFuncCurAmt"

    def test_make_parse_compound_key(self):
        from lab.pdf_validator.layouts.schedule_r import make_compound_key, parse_compound_key
        key = make_compound_key("1", "DistributionFuncCurAmt")
        assert key == "1|DistributionFuncCurAmt"
        row_id, field = parse_compound_key(key)
        assert row_id == "1"
        assert field == "DistributionFuncCurAmt"

    def test_normalize_desc(self):
        from lab.pdf_validator.layouts.schedule_r import normalize_distribution_desc
        assert normalize_distribution_desc("  cash dividend  ") == "CASH DIVIDEND"
        assert normalize_distribution_desc("Stock  Distribution.") == "STOCK DISTRIBUTION"

    def test_parse_date(self):
        from lab.pdf_validator.layouts.schedule_r import parse_date
        assert parse_date("12/31/2024") == "2024-12-31"
        assert parse_date("3/15/24") == "2024-03-15"
        assert parse_date("") is None

    def test_get_field_description_compound(self):
        from lab.pdf_validator.layouts.schedule_r import get_field_description
        desc = get_field_description("1|DistributionFuncCurAmt")
        assert "Row 1" in desc
        assert "functional currency" in desc.lower()


class TestScheduleRReconciliation:
    """Tests for Schedule R reconciliation logic."""

    @staticmethod
    def _mock_schr_pdf(records):
        df = pd.DataFrame(records)
        df.attrs["source"] = "test-schr.pdf"
        return df

    def test_row_match(self):
        pdf_df = self._mock_schr_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "1|DistributionFuncCurAmt",
             "field_name": "1|DistributionFuncCurAmt",
             "value": 100000.0},
        ])
        xml_values = {("C0001", "N/A", "1|DistributionFuncCurAmt"): 100000.0}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="R", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 1

    def test_multi_row(self):
        pdf_df = self._mock_schr_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "1|DistributionFuncCurAmt",
             "field_name": "1|DistributionFuncCurAmt", "value": 50000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "1|DistributionFromEPFuncCurAmt",
             "field_name": "1|DistributionFromEPFuncCurAmt", "value": 30000.0},
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "2|DistributionFuncCurAmt",
             "field_name": "2|DistributionFuncCurAmt", "value": 75000.0},
        ])
        xml_values = {
            ("C0001", "N/A", "1|DistributionFuncCurAmt"): 50000.0,
            ("C0001", "N/A", "1|DistributionFromEPFuncCurAmt"): 30000.0,
            ("C0001", "N/A", "2|DistributionFuncCurAmt"): 75000.0,
        }

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="R", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.ok_count == 3
        assert report.mismatch_count == 0

    def test_phantom_distribution(self):
        pdf_df = self._mock_schr_pdf([
            {"entity_name": "Corp A", "reference_id": "C0001", "basket": "N/A",
             "pool_name": "1|DistributionFuncCurAmt",
             "field_name": "1|DistributionFuncCurAmt", "value": 200000.0},
        ])
        xml_values = {}

        reconciler = PDFReconciler(pdf_data=pdf_df, schedule="R", tolerance=10.0)
        report = reconciler.reconcile_against_values(xml_values)
        assert report.phantom_count == 1

"""Unit tests for core/filters.py — FilterSpec and application functions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.core.models import Finding, ReviewReport, RolloverItem, RolloverReport
from lab.xml_parser.core.filters import (
    FilterSpec,
    build_filter_spec,
    filter_review_report,
    filter_rollover_reports,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_findings():
    return [
        Finding("FLO-003", "HIGH", "flow", "E001", "Alpha Corp", "Sch I-1 mismatch"),
        Finding("FLO-005", "HIGH", "flow", "E002", "Beta LLC", "Tested loss with taxes"),
        Finding("ROL-002", "MEDIUM", "rollover", "EDROP", "Dropped Entity", "Entity dropped"),
        Finding("ROL-007", "HIGH", "rollover", "E001", "Alpha Corp", "Sch J rollover"),
        Finding("CMP-001", "HIGH", "completeness", "E003", "Gamma Inc", "Missing Sch H"),
        Finding("RSN-003", "MEDIUM", "reasonableness", "E002", "Beta LLC", "ETR anomaly"),
    ]


@pytest.fixture
def sample_review_report(sample_findings):
    report = ReviewReport(
        client_name="Test Client",
        tax_year="2025",
        entity_count=5,
        findings=sample_findings,
    )
    report.compute_summary()
    return report


@pytest.fixture
def sample_rollover_reports():
    return {
        "Sch F Rollover": RolloverReport(
            title="Schedule F Rollover",
            items=[
                RolloverItem("Alpha Corp", "E001", "Total Assets", "1a", "100", "110", 10, True),
                RolloverItem("Beta LLC", "E002", "Total Assets", "1a", "200", "250", 50, False),
                RolloverItem("Gamma Inc", "E003", "Total Assets", "1a", "300", "300", 0, True),
            ],
        ),
        "Sch J Rollover": RolloverReport(
            title="Schedule J Rollover",
            items=[
                RolloverItem("Alpha Corp", "E001", "Post-2017 E&P", "1", "500", "600", 100, False),
                RolloverItem("Beta LLC", "E002", "Post-2017 E&P", "1", "400", "400", 0, True),
            ],
        ),
        "GILTI Comparison": RolloverReport(
            title="GILTI Comparison",
            items=[
                RolloverItem("Alpha Corp", "E001", "Tested Income", "1", "1000", "1100", 100, True),
                RolloverItem("Gamma Inc", "E003", "Tested Income", "1", "800", "900", 100, True),
            ],
        ),
    }


# ─── FilterSpec Tests ────────────────────────────────────────────────────────


class TestFilterSpec:
    def test_empty_filter(self):
        spec = FilterSpec()
        assert spec.is_empty
        assert not spec.has_entity_filter
        assert not spec.has_check_filter
        assert not spec.has_report_filter

    def test_entity_filter_by_code(self):
        spec = FilterSpec(entity_codes=frozenset({"E001", "E002"}))
        assert spec.has_entity_filter
        assert spec.matches_entity("E001", "Alpha Corp")
        assert spec.matches_entity("E002", "Beta LLC")
        assert not spec.matches_entity("E003", "Gamma Inc")

    def test_entity_filter_by_name(self):
        spec = FilterSpec(entity_names=frozenset({"Alpha"}))
        assert spec.matches_entity("E999", "Alpha Corp")
        assert not spec.matches_entity("E001", "Beta LLC")

    def test_entity_filter_name_case_insensitive(self):
        spec = FilterSpec(entity_names=frozenset({"alpha"}))
        assert spec.matches_entity("E001", "Alpha Corp")

    def test_entity_filter_code_or_name(self):
        spec = FilterSpec(
            entity_codes=frozenset({"E001"}),
            entity_names=frozenset({"Gamma"}),
        )
        assert spec.matches_entity("E001", "Alpha Corp")
        assert spec.matches_entity("E003", "Gamma Inc")
        assert not spec.matches_entity("E002", "Beta LLC")

    def test_check_filter_by_id(self):
        spec = FilterSpec(check_ids=frozenset({"FLO-003", "ROL-007"}))
        assert spec.has_check_filter
        assert spec.matches_check("FLO-003", "flow")
        assert spec.matches_check("ROL-007", "rollover")
        assert not spec.matches_check("CMP-001", "completeness")

    def test_check_filter_by_category(self):
        spec = FilterSpec(check_categories=frozenset({"rollover"}))
        assert spec.matches_check("ROL-001", "rollover")
        assert spec.matches_check("ROL-007", "rollover")
        assert not spec.matches_check("FLO-003", "flow")

    def test_report_key_filter(self):
        spec = FilterSpec(report_keys=frozenset({"Sch F", "GILTI"}))
        assert spec.has_report_filter
        assert spec.matches_report_key("Sch F Rollover")
        assert spec.matches_report_key("GILTI Comparison")
        assert not spec.matches_report_key("Sch J Rollover")

    def test_no_filter_matches_everything(self):
        spec = FilterSpec()
        assert spec.matches_entity("E001", "Anything")
        assert spec.matches_check("FLO-999", "unknown")
        assert spec.matches_report_key("Anything")


# ─── filter_review_report Tests ──────────────────────────────────────────────


class TestFilterReviewReport:
    def test_empty_filter_returns_same(self, sample_review_report):
        result = filter_review_report(sample_review_report, FilterSpec())
        assert result is sample_review_report

    def test_filter_by_entity_code(self, sample_review_report):
        spec = FilterSpec(entity_codes=frozenset({"E001"}))
        result = filter_review_report(sample_review_report, spec)
        assert len(result.findings) == 2
        assert all(f.entity_code == "E001" for f in result.findings)

    def test_filter_by_check_id(self, sample_review_report):
        spec = FilterSpec(check_ids=frozenset({"FLO-003"}))
        result = filter_review_report(sample_review_report, spec)
        assert len(result.findings) == 1
        assert result.findings[0].check_id == "FLO-003"

    def test_filter_by_category(self, sample_review_report):
        spec = FilterSpec(check_categories=frozenset({"rollover"}))
        result = filter_review_report(sample_review_report, spec)
        assert len(result.findings) == 2
        assert all(f.category == "rollover" for f in result.findings)

    def test_filter_entity_and_check_combined(self, sample_review_report):
        spec = FilterSpec(
            entity_codes=frozenset({"E001"}),
            check_categories=frozenset({"rollover"}),
        )
        result = filter_review_report(sample_review_report, spec)
        assert len(result.findings) == 1
        assert result.findings[0].check_id == "ROL-007"
        assert result.findings[0].entity_code == "E001"

    def test_filtered_report_preserves_metadata(self, sample_review_report):
        spec = FilterSpec(entity_codes=frozenset({"E001"}))
        result = filter_review_report(sample_review_report, spec)
        assert result.client_name == "Test Client"
        assert result.tax_year == "2025"
        assert result.entity_count == 5

    def test_filtered_report_recomputes_summary(self, sample_review_report):
        spec = FilterSpec(entity_codes=frozenset({"E001"}))
        result = filter_review_report(sample_review_report, spec)
        assert result.summary["total_findings"] == 2


# ─── filter_rollover_reports Tests ───────────────────────────────────────────


class TestFilterRolloverReports:
    def test_empty_filter_returns_same(self, sample_rollover_reports):
        result = filter_rollover_reports(sample_rollover_reports, FilterSpec())
        assert result is sample_rollover_reports

    def test_filter_by_report_key(self, sample_rollover_reports):
        spec = FilterSpec(report_keys=frozenset({"Sch F"}))
        result = filter_rollover_reports(sample_rollover_reports, spec)
        assert len(result) == 1
        assert "Sch F Rollover" in result

    def test_filter_by_entity_within_reports(self, sample_rollover_reports):
        spec = FilterSpec(entity_codes=frozenset({"E001"}))
        result = filter_rollover_reports(sample_rollover_reports, spec)
        assert len(result) == 3
        for name, report in result.items():
            assert all(item.reference_id == "E001" for item in report.items)

    def test_filter_report_key_and_entity(self, sample_rollover_reports):
        spec = FilterSpec(
            entity_codes=frozenset({"E001"}),
            report_keys=frozenset({"Sch J"}),
        )
        result = filter_rollover_reports(sample_rollover_reports, spec)
        assert len(result) == 1
        assert "Sch J Rollover" in result
        assert len(result["Sch J Rollover"].items) == 1
        assert result["Sch J Rollover"].items[0].reference_id == "E001"

    def test_filter_produces_empty_items(self, sample_rollover_reports):
        spec = FilterSpec(entity_codes=frozenset({"E999"}))
        result = filter_rollover_reports(sample_rollover_reports, spec)
        assert len(result) == 3
        for report in result.values():
            assert len(report.items) == 0


# ─── build_filter_spec Tests ─────────────────────────────────────────────────


class TestBuildFilterSpec:
    def test_empty_args(self):
        spec = build_filter_spec()
        assert spec.is_empty

    def test_entity_codes_detected(self):
        spec = build_filter_spec(entities=["E001", "E005"])
        assert "E001" in spec.entity_codes
        assert "E005" in spec.entity_codes
        assert not spec.entity_names

    def test_entity_names_detected(self):
        spec = build_filter_spec(entities=["Alpha Reinsurance"])
        assert not spec.entity_codes
        assert "Alpha Reinsurance" in spec.entity_names

    def test_mixed_entities(self):
        spec = build_filter_spec(entities=["E001", "Alpha Holdings"])
        assert "E001" in spec.entity_codes
        assert "Alpha Holdings" in spec.entity_names

    def test_check_ids_detected(self):
        spec = build_filter_spec(checks=["FLO-003", "ROL-007"])
        assert "FLO-003" in spec.check_ids
        assert "ROL-007" in spec.check_ids

    def test_report_keys_from_checks(self):
        spec = build_filter_spec(checks=["sch_f", "gilti"])
        assert "sch_f" in spec.report_keys
        assert "gilti" in spec.report_keys

    def test_categories(self):
        spec = build_filter_spec(categories=["rollover", "flow"])
        assert "rollover" in spec.check_categories
        assert "flow" in spec.check_categories

    def test_categories_map_to_report_keys(self):
        spec = build_filter_spec(categories=["rollover"])
        assert "Sch F Rollover" in spec.report_keys
        assert "Sch J Rollover (GEN)" in spec.report_keys
        assert "Sch J Rollover (PAS)" in spec.report_keys
        assert "Page 1 Rollover" in spec.report_keys


# ─── Model Method Tests ──────────────────────────────────────────────────────


class TestModelMethods:
    def test_review_report_by_check_id(self, sample_review_report):
        results = sample_review_report.by_check_id("FLO-003")
        assert len(results) == 1
        assert results[0].entity_code == "E001"

    def test_review_report_by_check_ids(self, sample_review_report):
        results = sample_review_report.by_check_ids({"FLO-003", "ROL-007"})
        assert len(results) == 2

    def test_rollover_report_filter_entities(self, sample_rollover_reports):
        report = sample_rollover_reports["Sch F Rollover"]
        filtered = report.filter_entities(codes={"E001", "E003"})
        assert len(filtered.items) == 2
        assert filtered.title == report.title

    def test_rollover_report_filter_entities_by_name(self, sample_rollover_reports):
        report = sample_rollover_reports["Sch F Rollover"]
        filtered = report.filter_entities(names={"Beta"})
        assert len(filtered.items) == 1
        assert filtered.items[0].reference_id == "E002"

    def test_rollover_report_filter_no_args_returns_self(self, sample_rollover_reports):
        report = sample_rollover_reports["Sch F Rollover"]
        filtered = report.filter_entities()
        assert filtered is report

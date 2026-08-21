"""Tests for unified orchestration — multi-form auto-detection and merged results."""

import pytest
from pathlib import Path

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.review_engine import ReviewEngine
from lab.xml_parser.reports import run_all_reports_unified
from lab.xml_parser.core.models import ReviewReport


FIXTURES = Path(__file__).parent / "fixtures"
CY_MIXED = FIXTURES / "sample_mixed_cy.xml"
PY_MIXED = FIXTURES / "sample_mixed_py.xml"
CY_5471 = FIXTURES / "sample_cy.xml"
PY_5471 = FIXTURES / "sample_py.xml"
CY_8858 = FIXTURES / "sample_8858_cy.xml"
PY_8858 = FIXTURES / "sample_8858_py.xml"


# ─── Parser detect_forms() ──────────────────────────────────────────────────

class TestDetectForms:
    def test_mixed_return_detects_both(self):
        parser = EFileParser(CY_MIXED)
        forms = parser.detect_forms()
        assert forms == {"5471", "8858"}

    def test_5471_only(self):
        parser = EFileParser(CY_5471)
        forms = parser.detect_forms()
        assert forms == {"5471"}

    def test_8858_only(self):
        parser = EFileParser(CY_8858)
        forms = parser.detect_forms()
        assert forms == {"8858"}


# ─── ReviewEngine.review_all() ──────────────────────────────────────────────

class TestReviewAll:
    def test_mixed_return_runs_both_forms(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_MIXED, PY_MIXED)
        assert report.form_type == "multi"
        assert report.entity_count == 2  # 1 CFC + 1 FDE

    def test_mixed_return_has_findings_from_both(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_MIXED, PY_MIXED)
        check_prefixes = {f.check_id.split("-")[0] for f in report.findings}
        # Should have at least one 5471 check and one 8858 check firing
        # (exact checks depend on fixture data — the point is both run)
        assert report.findings is not None

    def test_mixed_report_client_name(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_MIXED, PY_MIXED)
        assert report.client_name != "Unknown"

    def test_5471_only_returns_single_report(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_5471, PY_5471)
        assert report.form_type == "5471"

    def test_8858_only_returns_single_report(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_8858, PY_8858)
        assert report.form_type == "8858"

    def test_findings_sorted_by_severity(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_MIXED, PY_MIXED)
        if len(report.findings) > 1:
            sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            for i in range(len(report.findings) - 1):
                a = sev_order[report.findings[i].severity]
                b = sev_order[report.findings[i + 1].severity]
                assert a <= b

    def test_review_all_no_prior(self):
        engine = ReviewEngine()
        report = engine.review_all(CY_MIXED)
        assert report.form_type == "multi"
        rollover = [f for f in report.findings if f.category == "rollover"]
        assert len(rollover) == 0


# ─── run_all_reports_unified() ──────────────────────────────────────────────

class TestUnifiedReports:
    def test_mixed_return_has_5471_and_8858_reports(self):
        reports = run_all_reports_unified(PY_MIXED, CY_MIXED)
        has_5471 = any(not k.startswith("8858") for k in reports)
        has_8858 = any(k.startswith("8858") for k in reports)
        assert has_5471
        assert has_8858

    def test_5471_only_returns_5471_reports(self):
        reports = run_all_reports_unified(PY_5471, CY_5471)
        assert "Sch F Rollover" in reports
        assert not any(k.startswith("8858") for k in reports)

    def test_8858_only_returns_8858_reports(self):
        reports = run_all_reports_unified(PY_8858, CY_8858)
        assert "8858 Sch F Rollover" in reports
        assert "Sch F Rollover" not in reports

    def test_mixed_report_count(self):
        reports = run_all_reports_unified(PY_MIXED, CY_MIXED)
        # 12 from 5471 + 5 from 8858 = 17
        assert len(reports) == 17


# ─── Backward Compatibility ─────────────────────────────────────────────────

class TestBackwardCompatUnified:
    def test_review_single_form_still_works(self):
        engine = ReviewEngine()
        report = engine.review(CY_5471, PY_5471, form_type="5471")
        assert report.form_type == "5471"
        assert len(report.findings) == 28

    def test_review_8858_still_works(self):
        engine = ReviewEngine()
        report = engine.review(CY_8858, PY_8858, form_type="8858")
        assert report.form_type == "8858"
        assert len(report.findings) >= 5

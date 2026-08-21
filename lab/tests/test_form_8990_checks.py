"""Tests for Form 8990 (Section 163(j)) check module.

Validates per-entity BIE limitation math, carryforward rollover,
CFC group consistency, and edge cases.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.engine.checks._helpers import CheckContext
from lab.xml_parser.engine.checks.form_8990 import run_form_8990_checks
from lab.xml_parser.parser import EFileParser
from lab.xml_parser.review_engine import ReviewEngine

FIXTURES = Path(__file__).parent / "fixtures"
CY_8990 = FIXTURES / "sample_8990_cy.xml"
PY_8990 = FIXTURES / "sample_8990_py.xml"


@pytest.fixture
def parser_cy():
    return EFileParser(CY_8990)


@pytest.fixture
def parser_py():
    return EFileParser(PY_8990)


@pytest.fixture
def ctx(parser_cy):
    df = parser_cy.to_dataframe()
    return CheckContext(parser_cy, df, _get_entity_name)


@pytest.fixture
def ctx_with_prior(parser_cy, parser_py):
    df = parser_cy.to_dataframe()
    return CheckContext(parser_cy, df, _get_entity_name, prior_parser=parser_py)


def _get_entity_name(df, code):
    rows = df[df["_reference_id"] == code]
    if rows.empty:
        return code
    return rows.iloc[0].get("_entity_name", code)


class TestForm8990ChecksFire:
    """Verify each check fires on the fixture data."""

    def test_bie_001_ati_math(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-001"]
        assert len(hits) == 1
        assert hits[0].entity_code == "D004"
        assert hits[0].severity == "HIGH"

    def test_bie_002_30_pct(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-002"]
        assert len(hits) == 2
        codes = {f.entity_code for f in hits}
        assert "D004" in codes
        assert "C003" in codes
        assert all(f.severity == "HIGH" for f in hits)

    def test_bie_003_limitation(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-003"]
        assert len(hits) == 1
        assert hits[0].entity_code == "D004"
        assert hits[0].severity == "HIGH"

    def test_bie_010_negative_ati(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-010"]
        assert len(hits) == 1
        assert hits[0].entity_code == "C003"
        assert hits[0].severity == "MEDIUM"

    def test_bie_012_net_creditor(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-012"]
        assert len(hits) == 1
        assert hits[0].entity_code == "E005"
        assert hits[0].severity == "LOW"

    def test_bie_013_rollover_mismatch(self, ctx_with_prior):
        run_form_8990_checks(ctx_with_prior)
        hits = [f for f in ctx_with_prior.findings if f.check_id == "BIE-013"]
        assert len(hits) >= 1
        d004_hit = [f for f in hits if f.entity_code == "D004"]
        assert len(d004_hit) == 1
        assert d004_hit[0].severity == "HIGH"


class TestForm8990Clean:
    """Verify clean entities don't produce false positives."""

    def test_alpha_clean_no_findings(self, ctx):
        run_form_8990_checks(ctx)
        a001_hits = [f for f in ctx.findings if f.entity_code == "A001"]
        assert len(a001_hits) == 0

    def test_beta_carryforward_no_math_errors(self, ctx):
        run_form_8990_checks(ctx)
        b002_hits = [f for f in ctx.findings if f.entity_code == "B002"]
        assert len(b002_hits) == 0

    def test_beta_rollover_clean(self, ctx_with_prior):
        run_form_8990_checks(ctx_with_prior)
        b002_hits = [f for f in ctx_with_prior.findings
                     if f.entity_code == "B002" and f.check_id == "BIE-013"]
        assert len(b002_hits) == 0


class TestForm8990EdgeCases:
    """Edge cases and boundary conditions."""

    def test_no_8990_data_returns_empty(self):
        parser = EFileParser(FIXTURES / "sample_8858_cy.xml")
        df = parser.to_dataframe()
        ctx = CheckContext(parser, df, _get_entity_name)
        run_form_8990_checks(ctx)
        bie_hits = [f for f in ctx.findings if f.check_id.startswith("BIE")]
        assert len(bie_hits) == 0

    def test_without_prior_no_bie013(self, ctx):
        run_form_8990_checks(ctx)
        hits = [f for f in ctx.findings if f.check_id == "BIE-013"]
        assert len(hits) == 0

    def test_total_finding_count(self, ctx_with_prior):
        run_form_8990_checks(ctx_with_prior)
        all_bie = [f for f in ctx_with_prior.findings if f.check_id.startswith("BIE")]
        assert len(all_bie) >= 5
        assert len(all_bie) <= 10


class TestForm8990ViaReviewEngine:
    """Integration: confirm ReviewEngine invokes 8990 checks."""

    def test_review_includes_bie_findings(self):
        engine = ReviewEngine()
        report = engine.review(CY_8990, PY_8990)
        bie_findings = [f for f in report.findings if f.check_id.startswith("BIE")]
        assert len(bie_findings) >= 4
        check_ids = {f.check_id for f in bie_findings}
        assert "BIE-001" in check_ids
        assert "BIE-010" in check_ids

    def test_review_bie_findings_sorted_by_severity(self):
        engine = ReviewEngine()
        report = engine.review(CY_8990, PY_8990)
        bie_findings = [f for f in report.findings if f.check_id.startswith("BIE")]
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        for i in range(len(bie_findings) - 1):
            assert severity_order[bie_findings[i].severity] <= severity_order[bie_findings[i + 1].severity]

    def test_review_without_prior_still_runs_math_checks(self):
        engine = ReviewEngine()
        report = engine.review(CY_8990)
        bie_findings = [f for f in report.findings if f.check_id.startswith("BIE")]
        assert len(bie_findings) >= 4
        assert not any(f.check_id == "BIE-013" for f in bie_findings)

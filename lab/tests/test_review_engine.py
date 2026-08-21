"""Regression tests for ReviewEngine baseline.

Asserts the exact 28 findings produced by sample_cy.xml + sample_py.xml.
Any refactoring that changes engine behavior must update these tests
deliberately, not accidentally.
"""

import pytest

from lab.xml_parser.review_engine import Finding, ReviewEngine, ReviewReport


class TestReviewReportBaseline:
    """Full CY+PY review produces exactly 28 findings."""

    def test_total_count(self, review_report: ReviewReport):
        assert len(review_report.findings) == 28

    def test_entity_count(self, review_report: ReviewReport):
        assert review_report.entity_count == 5

    def test_severity_counts(self, review_report: ReviewReport):
        high = [f for f in review_report.findings if f.severity == "HIGH"]
        medium = [f for f in review_report.findings if f.severity == "MEDIUM"]
        low = [f for f in review_report.findings if f.severity == "LOW"]
        assert len(high) == 10
        assert len(medium) == 15
        assert len(low) == 3

    def test_category_counts(self, review_report: ReviewReport):
        cats = {}
        for f in review_report.findings:
            cats[f.category] = cats.get(f.category, 0) + 1
        assert cats.get("flow", 0) >= 2
        assert cats.get("completeness", 0) >= 2
        assert cats.get("reasonableness", 0) >= 2
        assert cats.get("rollover", 0) >= 4


class TestFlowChecks:
    """FLO-xxx checks: internal consistency within a single return."""

    def test_flo_003_sch_i1_reconciliation(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "FLO-003"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E005"
        assert f.severity == "HIGH"
        assert "300,000,000" in f.description or f.delta == 300_000_000

    def test_flo_005_tested_loss_with_taxes(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "FLO-005"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E002"
        assert f.severity == "HIGH"

    def test_flo_008_balance_sheet_imbalance(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "FLO-008"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E004"
        assert f.severity == "HIGH"
        assert f.delta == 500_000 or "500,000" in f.description


class TestCompletenessChecks:
    """CMP-xxx checks: missing schedules or required data."""

    def test_cmp_001_missing_schedule_h(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "CMP-001"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E003"
        assert f.severity == "HIGH"

    def test_cmp_003_tested_income_no_sch_e(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "CMP-003"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E005"
        assert f.severity == "MEDIUM"

    def test_cmp_005_no_exchange_rate(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "CMP-005"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E005"
        assert f.severity == "MEDIUM"


class TestReasonablenessChecks:
    """RSN-xxx checks: values outside expected ranges."""

    def test_rsn_003_etr_anomaly(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "RSN-003"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E002"
        assert f.severity == "MEDIUM"
        assert "ETR" in f.description or "etr" in f.description.lower()

    def test_rsn_006_qbai_exceeds_assets(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "RSN-006"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E004"
        assert f.severity == "HIGH"


class TestRolloverChecks:
    """ROL-xxx checks: PY-to-CY continuity."""

    def test_rol_002_entity_dropped(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "ROL-002"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "EDROP"
        assert f.severity == "MEDIUM"

    def test_rol_003_new_entity(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "ROL-003"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E005"
        assert f.severity == "MEDIUM"

    def test_rol_004_ep_sign_flip(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "ROL-004"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E002"
        assert f.severity == "MEDIUM"

    def test_rol_007_sch_j_boy_vs_eoy(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "ROL-007"]
        assert len(matches) == 2
        entities = {f.entity_code for f in matches}
        assert "E001" in entities
        for f in matches:
            assert f.severity == "HIGH"

    def test_rol_010_gilti_classification_flip(self, review_report: ReviewReport):
        matches = [f for f in review_report.findings if f.check_id == "ROL-010"]
        assert len(matches) == 1
        f = matches[0]
        assert f.entity_code == "E002"
        assert f.severity == "MEDIUM"


class TestCYOnlyReview:
    """Without PY, rollover checks should not fire."""

    def test_no_rollover_findings(self, review_report_cy_only: ReviewReport):
        rollover = [f for f in review_report_cy_only.findings if f.category == "ROLLOVER"]
        assert len(rollover) == 0

    def test_non_rollover_findings_still_fire(self, review_report_cy_only: ReviewReport):
        assert len(review_report_cy_only.findings) > 0
        categories = {f.category for f in review_report_cy_only.findings}
        assert "flow" in categories or "completeness" in categories or "reasonableness" in categories


class TestReviewReportMethods:
    """Test ReviewReport helper methods."""

    def test_high_severity(self, review_report: ReviewReport):
        high = review_report.high_severity()
        assert len(high) == 10

    def test_by_entity(self, review_report: ReviewReport):
        e002 = review_report.by_entity("E002")
        assert len(e002) >= 3
        assert all(f.entity_code == "E002" for f in e002)

    def test_by_category(self, review_report: ReviewReport):
        flow = review_report.by_category("FLOW")
        assert all(f.category == "FLOW" for f in flow)

    def test_to_dataframe(self, review_report: ReviewReport):
        df = review_report.to_dataframe()
        assert len(df) == 28
        assert "check_id" in df.columns
        assert "severity" in df.columns
        assert "entity_code" in df.columns

    def test_compute_summary(self, review_report: ReviewReport):
        review_report.compute_summary()
        s = review_report.summary
        assert s["total_findings"] == 28
        assert s["by_severity"]["HIGH"] == 10
        assert s["by_severity"]["MEDIUM"] == 15
        assert s["by_severity"]["LOW"] == 3
        assert s["entities_with_findings"] == 7  # includes EDROP (PY-only) and ALL (cross-form aggregate)
        assert s["clean_entities"] == self._expected_clean(review_report)

    @staticmethod
    def _expected_clean(report: ReviewReport) -> int:
        return report.entity_count - len(set(f.entity_code for f in report.findings))


class TestFindingDataclass:
    """Verify Finding structure."""

    def test_finding_fields(self, review_report: ReviewReport):
        f = review_report.findings[0]
        assert isinstance(f, Finding)
        assert f.check_id
        assert f.severity in ("HIGH", "MEDIUM", "LOW")
        assert f.category in ("flow", "completeness", "reasonableness", "rollover")
        assert f.entity_code
        assert f.entity_name
        assert f.description

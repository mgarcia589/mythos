"""Tests for the MythosService API layer."""

import pytest
from pathlib import Path

from lab.xml_parser.api import MythosService
from lab.xml_parser.api.service import ReviewResult, EntitySummary

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def svc():
    return MythosService()


class TestServiceReview:
    def test_review_success(self, svc):
        result = svc.review(FIXTURES / "sample_cy.xml", prior=FIXTURES / "sample_py.xml")
        assert result.success is True
        assert result.finding_count == 28
        assert result.high_count == 10
        assert result.entity_count == 5
        assert result.duration_ms > 0
        assert result.report is not None

    def test_review_cy_only(self, svc):
        result = svc.review(FIXTURES / "sample_cy.xml")
        assert result.success is True
        assert result.finding_count > 0
        assert "rollover checks skipped" in result.warnings[0]

    def test_review_bad_path(self, svc):
        result = svc.review("nonexistent.xml")
        assert result.success is False
        assert result.message

    def test_review_with_progress(self):
        messages = []
        svc = MythosService(progress=lambda msg, pct: messages.append((msg, pct)))
        svc.review(FIXTURES / "sample_cy.xml", prior=FIXTURES / "sample_py.xml")
        assert len(messages) >= 2
        assert messages[-1][1] == 1.0


class TestServiceListEntities:
    def test_list_entities(self, svc):
        entities = svc.list_entities(FIXTURES / "sample_cy.xml")
        assert len(entities) == 5
        assert all(isinstance(e, EntitySummary) for e in entities)

    def test_entity_details(self, svc):
        entities = svc.list_entities(FIXTURES / "sample_cy.xml")
        by_ref = {e.reference_id: e for e in entities}

        e001 = by_ref["E001"]
        assert e001.name == "CLEAN SUBSIDIARY LTD"
        assert e001.country == "UK"
        assert e001.currency == "GBP"
        assert e001.has_sch_h is True
        assert e001.has_sch_f is True

        e003 = by_ref["E003"]
        assert e003.has_sch_h is False
        assert e003.has_sch_f is True


class TestServiceExport:
    def test_export_review_excel(self, svc, tmp_path):
        result = svc.review(FIXTURES / "sample_cy.xml", prior=FIXTURES / "sample_py.xml")
        export = svc.export_review(result.report, path=tmp_path / "test_export.xlsx")
        assert export.success is True
        assert export.path.exists()
        assert export.path.suffix == ".xlsx"

    def test_export_review_csv(self, svc, tmp_path):
        result = svc.review(FIXTURES / "sample_cy.xml", prior=FIXTURES / "sample_py.xml")
        export = svc.export_review(result.report, path=tmp_path / "test_export.csv", format="csv")
        assert export.success is True
        assert export.path.exists()

    def test_export_empty_report(self, svc):
        from lab.xml_parser.core.models import ReviewReport
        export = svc.export_review(ReviewReport())
        assert export.success is False

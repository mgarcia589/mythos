"""Tests for PDFComparator — PDF vs PDF comparison."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import pandas as pd

from lab.pdf_validator.comparator import (
    PDFComparator,
    PDFComparisonReport,
    ComparisonItem,
)


# ─── Helpers ───────────────────────────────────────────────────────────────

def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Create a DataFrame matching PDFExtractor output schema."""
    cols = ["entity_name", "reference_id", "basket", "pool_name", "field_name", "value"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


# ─── Model tests ───────────────────────────────────────────────────────────

class TestPDFComparisonReport:
    def test_counts(self):
        items = [
            ComparisonItem("A", "E001", "GEN", "J", "f1", "", 100, 100, 0, "UNCHANGED"),
            ComparisonItem("A", "E001", "GEN", "J", "f2", "", 100, 200, 100, "CHANGED"),
            ComparisonItem("A", "E001", "GEN", "J", "f3", "", 0, 50, 50, "NEW_IN_CY"),
            ComparisonItem("A", "E001", "GEN", "J", "f4", "", 50, 0, -50, "DROPPED_FROM_PY"),
        ]
        report = PDFComparisonReport(schedule="J", py_source="a.pdf", cy_source="b.pdf", items=items)

        assert report.total == 4
        assert report.unchanged_count == 1
        assert report.changed_count == 1
        assert report.new_count == 1
        assert report.dropped_count == 1

    def test_changes_property(self):
        items = [
            ComparisonItem("A", "E001", "GEN", "J", "f1", "", 100, 100, 0, "UNCHANGED"),
            ComparisonItem("A", "E001", "GEN", "J", "f2", "", 100, 200, 100, "CHANGED"),
        ]
        report = PDFComparisonReport(schedule="J", py_source="a.pdf", cy_source="b.pdf", items=items)

        assert len(report.changes) == 1
        assert report.changes[0].field_name == "f2"

    def test_summary_line(self):
        items = [
            ComparisonItem("A", "E001", "GEN", "J", "f1", "", 100, 100, 0, "UNCHANGED"),
        ]
        report = PDFComparisonReport(schedule="J", py_source="a.pdf", cy_source="b.pdf", items=items)
        line = report.summary_line()
        assert "1 fields compared" in line
        assert "1 unchanged" in line


# ─── Comparator logic tests (mock extractor) ──────────────────────────────

class TestPDFComparatorLogic:
    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_unchanged_fields(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 1000},
        ])
        cy_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 1000},
        ])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.unchanged_count == 1
        assert report.changed_count == 0

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_changed_fields(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 1000},
        ])
        cy_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 2000},
        ])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.changed_count == 1
        assert report.items[0].delta == 1000

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_new_in_cy(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([])
        cy_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 500},
        ])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.new_count == 1
        assert report.items[0].status == "NEW_IN_CY"

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_dropped_from_py(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 500},
        ])
        cy_df = _make_df([])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.dropped_count == 1
        assert report.items[0].status == "DROPPED_FROM_PY"

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_threshold_applies(self, MockExtractor, tmp_path):
        """Values within threshold should be UNCHANGED."""
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 1000},
        ])
        cy_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "Post2017", "field_name": "BeginBal", "value": 1000.50},
        ])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J", threshold=1.0)
        report = comparator.compare()

        assert report.unchanged_count == 1

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_multiple_entities(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        py_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "P1", "field_name": "F1", "value": 100},
            {"entity_name": "Corp B", "reference_id": "E002", "basket": "GEN",
             "pool_name": "P1", "field_name": "F1", "value": 200},
        ])
        cy_df = _make_df([
            {"entity_name": "Corp A", "reference_id": "E001", "basket": "GEN",
             "pool_name": "P1", "field_name": "F1", "value": 100},
            {"entity_name": "Corp B", "reference_id": "E002", "basket": "GEN",
             "pool_name": "P1", "field_name": "F1", "value": 300},
        ])

        instance_py = MagicMock()
        instance_py.extract.return_value = py_df
        instance_cy = MagicMock()
        instance_cy.extract.return_value = cy_df
        MockExtractor.side_effect = [instance_py, instance_cy]

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.total == 2
        assert report.unchanged_count == 1
        assert report.changed_count == 1

    @patch("lab.pdf_validator.comparator.PDFExtractor")
    def test_duration_recorded(self, MockExtractor, tmp_path):
        py_pdf = tmp_path / "py.pdf"
        cy_pdf = tmp_path / "cy.pdf"
        py_pdf.touch()
        cy_pdf.touch()

        instance = MagicMock()
        instance.extract.return_value = _make_df([])
        MockExtractor.return_value = instance

        comparator = PDFComparator(py_pdf, cy_pdf, schedule="J")
        report = comparator.compare()

        assert report.comparison_duration_ms >= 0

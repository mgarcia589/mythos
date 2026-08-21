"""Tests for PDFScanner — lightweight form/entity inventory."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from lab.pdf_validator.scanner import (
    PDFScanner,
    ScanResult,
    EntityInfo,
    FORM_5471_PATTERNS,
    FORM_8858_PATTERNS,
)


# ─── Fixtures: mock page text ──────────────────────────────────────────────

PAGE_5471_MAIN = """
Form 5471    Information Return of U.S. Persons With Respect to
Certain Foreign Corporations
Name of Foreign Corporation: OFFSHORE SUB LTD
Reference ID Number: CFC001
Country of Incorporation: UK
"""

PAGE_5471_SCHJ = """
SCHEDULE J (Form 5471)    Accumulated Earnings & Profits (E&P)
of Controlled Foreign Corporation
Name of person filing: PARENT CORP INC
Reference ID: CFC001
Category of income: General Category
"""

PAGE_5471_SCHF = """
SCHEDULE F (Form 5471)    Balance Sheet
Name of Foreign Corporation: OFFSHORE SUB LTD
Reference ID: CFC001
"""

PAGE_5471_SCHH = """
SCHEDULE H (Form 5471)    Current Earnings and Profits
Name of Foreign Corporation: OFFSHORE SUB LTD
Reference ID: CFC001
"""

PAGE_8858_MAIN = """
Form 8858    Information Return of U.S. Persons With Respect to
Foreign Disregarded Entities and Foreign Branches
Name of Foreign Disregarded Entity: BRANCH LLC
Reference ID Number: FDE001
Country of Organization: DE
"""

PAGE_8858_SCHC = """
Form 8858    Schedule C — Income Statement
Name of Foreign Entity: BRANCH LLC
Reference ID: FDE001
"""

PAGE_8858_SCHF = """
Form 8858    Schedule F — Balance Sheet
Name of Foreign Entity: BRANCH LLC
Reference ID: FDE001
"""

PAGE_ENTITY2 = """
SCHEDULE J (Form 5471)    Accumulated Earnings & Profits (E&P)
Name of Foreign Corporation: SECOND ENTITY INC
Reference ID: CFC002
Country of Incorporation: JP
"""


def _make_mock_pdf(page_texts: list[str]):
    """Create a mock pdfplumber context that returns given page texts."""
    mock_pdf = MagicMock()
    pages = []
    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)
    mock_pdf.pages = pages
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


# ─── Tests ─────────────────────────────────────────────────────────────────

class TestScanResult:
    def test_entity_count_property(self):
        r = ScanResult(file_path="test.pdf", total_pages=5)
        r.entities = [EntityInfo("A", "X"), EntityInfo("B", "Y")]
        assert r.entity_count == 2

    def test_empty_scan(self):
        r = ScanResult(file_path="test.pdf", total_pages=0)
        assert r.entity_count == 0
        assert r.form_types == set()


class TestPDFScannerFormDetection:
    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_5471(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([PAGE_5471_MAIN, PAGE_5471_SCHJ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert "5471" in result.form_types
        assert "8858" not in result.form_types

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_8858(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([PAGE_8858_MAIN, PAGE_8858_SCHC])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert "8858" in result.form_types
        assert "5471" not in result.form_types

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_mixed(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_5471_MAIN, PAGE_5471_SCHJ, PAGE_8858_MAIN, PAGE_8858_SCHC
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert result.form_types == {"5471", "8858"}


class TestPDFScannerScheduleDetection:
    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_5471_schedules(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_5471_MAIN, PAGE_5471_SCHJ, PAGE_5471_SCHF, PAGE_5471_SCHH
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert "J" in result.schedules_detected
        assert "F" in result.schedules_detected
        assert "H" in result.schedules_detected

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_8858_schedules(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_8858_MAIN, PAGE_8858_SCHC, PAGE_8858_SCHF
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert "8858_C" in result.schedules_detected
        assert "8858_F" in result.schedules_detected


class TestPDFScannerEntityDetection:
    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_entity_ref_id(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([PAGE_5471_MAIN, PAGE_5471_SCHJ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert result.entity_count >= 1
        ref_ids = {e.reference_id for e in result.entities}
        assert "CFC001" in ref_ids

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_detects_multiple_entities(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_5471_MAIN, PAGE_5471_SCHJ, PAGE_ENTITY2
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        ref_ids = {e.reference_id for e in result.entities}
        assert "CFC001" in ref_ids
        assert "CFC002" in ref_ids

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_entity_country_detected(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([PAGE_5471_MAIN])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        cfc001 = next((e for e in result.entities if e.reference_id == "CFC001"), None)
        assert cfc001 is not None
        assert cfc001.country == "UK"

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_entity_tracks_schedules(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_5471_MAIN, PAGE_5471_SCHJ, PAGE_5471_SCHF
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        cfc001 = next((e for e in result.entities if e.reference_id == "CFC001"), None)
        assert cfc001 is not None
        assert "J" in cfc001.schedules_present or "F" in cfc001.schedules_present

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_page_count(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([
            PAGE_5471_MAIN, PAGE_5471_SCHJ, PAGE_5471_SCHF
        ])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert result.total_pages == 3

    @patch("lab.pdf_validator.scanner.pdfplumber")
    def test_scan_duration_recorded(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        mock_plumber.open.return_value = _make_mock_pdf([PAGE_5471_MAIN])

        scanner = PDFScanner(pdf_file)
        result = scanner.scan()

        assert result.scan_duration_ms > 0


class TestPDFScannerErrors:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            PDFScanner("nonexistent.pdf")

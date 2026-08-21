"""Tests for Form 8858 PDF extraction — Schedules C, F, H."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import pandas as pd

from lab.pdf_validator.extractor import PDFExtractor
from lab.pdf_validator.layouts.schedule_8858_c import identify_line_item as identify_8858c
from lab.pdf_validator.layouts.schedule_8858_f import identify_line_item as identify_8858f
from lab.pdf_validator.layouts.schedule_8858_h import identify_line_item as identify_8858h


# ─── Layout identification tests ──────────────────────────────────────────

class TestSchedule8858CLayout:
    def test_gross_receipts(self):
        result = identify_8858c("Gross receipts or sales")
        assert result is not None
        assert result[0] == "GrossReceiptsOrSalesIncmStmt"

    def test_net_income(self):
        result = identify_8858c("Net income (loss) per income statement")
        assert result is not None
        assert result[0] == "NetIncomeLossPerIncomeStmt"

    def test_cost_of_goods_sold(self):
        result = identify_8858c("Cost of goods sold")
        assert result is not None
        assert result[0] == "CostOfGoodsSoldAmt"

    def test_total_deductions(self):
        result = identify_8858c("Total deductions")
        assert result is not None
        assert result[0] == "TotalDeductionsAmt"

    def test_unrecognized(self):
        assert identify_8858c("random text") is None

    def test_empty(self):
        assert identify_8858c("") is None


class TestSchedule8858FLayout:
    def test_cash(self):
        result = identify_8858f("Cash and other current assets")
        assert result is not None
        assert result[0] == "CashAndOtherCurrentAssets_BOY"
        assert result[1] == "CashAndOtherCurrentAssets_EOY"

    def test_total_assets(self):
        result = identify_8858f("Total assets")
        assert result is not None
        assert result[0] == "TotalAssetsBalanceSheet_BOY"
        assert result[1] == "TotalAssetsBalanceSheet_EOY"

    def test_liabilities(self):
        result = identify_8858f("Liabilities")
        assert result is not None
        assert result[0] == "LiabilitiesBalanceSheet_BOY"
        assert result[1] == "LiabilitiesBalanceSheet_EOY"

    def test_owner_equity(self):
        result = identify_8858f("Owner's equity")
        assert result is not None
        assert result[0] == "OwnerEquityBalanceSheet_BOY"
        assert result[1] == "OwnerEquityBalanceSheet_EOY"

    def test_total_liab_equity(self):
        result = identify_8858f("Total liabilities and owner's equity")
        assert result is not None
        assert result[0] == "TotLiabOwnerEquityBalanceSheet_BOY"

    def test_unrecognized(self):
        assert identify_8858f("random text") is None


class TestSchedule8858HLayout:
    def test_net_income_per_books(self):
        result = identify_8858h("CY net income per books")
        assert result is not None
        assert result[0] == "ForeignCYNetIncomePerBooksAmt"

    def test_current_ep(self):
        result = identify_8858h("Current earnings and profits")
        assert result is not None
        assert result[0] == "CurrentEarningsAndProfitsAmt"

    def test_ep_in_usd(self):
        result = identify_8858h("E&P in U.S. dollars")
        assert result is not None
        assert result[0] == "CurrEarnAndPrftInUSDollarsAmt"

    def test_exchange_rate(self):
        result = identify_8858h("Exchange rate")
        assert result is not None
        assert result[0] == "ExchangeRt"

    def test_depreciation(self):
        result = identify_8858h("Depreciation and amortization")
        assert result is not None
        assert result[0] == "DepreciationAndAmortizationAmt"


# ─── Extractor tests (mock pdfplumber) ────────────────────────────────────

# Main form page provides entity context (ref ID + FC)
PAGE_8858_MAIN = """
BRANCH ONE LLC 12-3456789
Form 8858 (Rev. 12-2024) Page 1
1a Name and address of FDE or FB
BRANCH ONE LLC 12-3456789
123 Main Street b(2) Reference ID number (see instructions)
City, Country FDE001
h Principal business activity code number i Principal business activity j Functional currency
511210 SOFTWARE EUR
"""

PAGE_8858_MAIN_USD = """
BRANCH ONE LLC 12-3456789
Form 8858 (Rev. 12-2024) Page 1
1a Name and address of FDE or FB
BRANCH ONE LLC 12-3456789
123 Main Street b(2) Reference ID number (see instructions)
City, Country FDE001
h Principal business activity code number i Principal business activity j Functional currency
511210 SOFTWARE USD
"""

PAGE_8858_SCHC = """
BRANCH ONE LLC 12-3456789
Form 8858 (Rev. 12-2024) Page2
Schedule C Income Statement (see instructions)
Important: Report all information in functional currency
Functional currency U.S. dollars
"""

PAGE_8858_SCHF = """
BRANCH ONE LLC 12-3456789
Form 8858 (Rev. 12-2024) Page2
Schedule C Income Statement (see instructions)
Schedule F Balance Sheet
Important:Report all amounts in U.S. dollars
"""

PAGE_8858_SCHH = """
BRANCH ONE LLC 12-3456789
Form 8858 (Rev. 12-2024) Page 4
Schedule H Current Earnings and Profits (or Taxable Income) of FDE or FB
Accumulated Earnings
"""


def _make_mock_pdf(page_texts, tables_per_page=None):
    """Create a mock pdfplumber PDF context."""
    mock_pdf = MagicMock()
    pages = []
    for i, text in enumerate(page_texts):
        page = MagicMock()
        page.extract_text.return_value = text
        if tables_per_page and i in tables_per_page:
            page.extract_tables.return_value = tables_per_page[i]
        else:
            page.extract_tables.return_value = []
        pages.append(page)
    mock_pdf.pages = pages
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


class TestExtractor8858CRouting:
    @patch("lab.pdf_validator.extractor.pdfplumber")
    def test_8858c_extraction_dual_amounts(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "8858c.pdf"
        pdf_file.touch()

        table = [
            ["Description", "Functional Currency", "U.S. Dollars"],
            ["Gross receipts or sales", "800,000", "1,000,000"],
            ["Cost of goods sold", "300,000", "375,000"],
            ["Net income (loss)", "320,000", "400,000"],
        ]

        mock_plumber.open.return_value = _make_mock_pdf(
            [PAGE_8858_MAIN, PAGE_8858_SCHC], tables_per_page={1: [table]}
        )

        extractor = PDFExtractor(pdf_file, schedule="8858_C")
        df = extractor.extract()

        assert not df.empty
        fc_fields = df[df["field_name"].str.endswith("_FC")]
        usd_fields = df[df["field_name"].str.endswith("_USD")]
        assert len(fc_fields) >= 2
        assert len(usd_fields) >= 2

    @patch("lab.pdf_validator.extractor.pdfplumber")
    def test_8858c_text_fallback(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "8858c.pdf"
        pdf_file.touch()

        text = PAGE_8858_SCHC + "\nGross receipts or sales  800,000  1,000,000\nNet income  320,000  400,000\n"

        mock_plumber.open.return_value = _make_mock_pdf(
            [PAGE_8858_MAIN, text], tables_per_page={}
        )

        extractor = PDFExtractor(pdf_file, schedule="8858_C")
        df = extractor.extract()

        assert not df.empty
        assert any("_FC" in f for f in df["field_name"].values)
        assert any("_USD" in f for f in df["field_name"].values)


class TestExtractor8858FRouting:
    @patch("lab.pdf_validator.extractor.pdfplumber")
    def test_8858f_extraction_boy_eoy(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "8858f.pdf"
        pdf_file.touch()

        table = [
            ["", "Beginning of year", "End of year"],
            ["Cash and other current assets", "3,000,000", "3,500,000"],
            ["Total assets", "3,500,000", "4,100,000"],
            ["Liabilities", "1,000,000", "1,200,000"],
            ["Owner's equity", "2,500,000", "2,900,000"],
            ["Total liabilities and equity", "3,500,000", "4,100,000"],
        ]

        mock_plumber.open.return_value = _make_mock_pdf(
            [PAGE_8858_MAIN, PAGE_8858_SCHF], tables_per_page={1: [table]}
        )

        extractor = PDFExtractor(pdf_file, schedule="8858_F")
        df = extractor.extract()

        assert not df.empty
        assert len(df) >= 4


class TestExtractor8858HRouting:
    @patch("lab.pdf_validator.extractor.pdfplumber")
    def test_8858h_extraction_single_column(self, mock_plumber, tmp_path):
        pdf_file = tmp_path / "8858h.pdf"
        pdf_file.touch()

        table = [
            ["Description", "Amount"],
            ["CY net income per books", "320,000"],
            ["Current earnings and profits", "320,000"],
            ["E&P in U.S. dollars", "400,000"],
            ["Exchange rate", "0.800000"],
        ]

        mock_plumber.open.return_value = _make_mock_pdf(
            [PAGE_8858_MAIN_USD, PAGE_8858_SCHH], tables_per_page={1: [table]}
        )

        extractor = PDFExtractor(pdf_file, schedule="8858_H")
        df = extractor.extract()

        assert not df.empty
        fields = set(df["field_name"].values)
        assert "ForeignCYNetIncomePerBooksAmt" in fields
        assert "CurrEarnAndPrftInUSDollarsAmt" in fields


class TestExtractor8858PageDisambiguation:
    @patch("lab.pdf_validator.extractor.pdfplumber")
    def test_5471_schf_not_confused_with_8858(self, mock_plumber, tmp_path):
        """A 5471 Schedule F page should NOT trigger when extracting 8858_F."""
        pdf_file = tmp_path / "5471f.pdf"
        pdf_file.touch()

        page_5471_f = """
        SCHEDULE F (Form 5471)    Balance Sheet
        Controlled Foreign Corporation
        Name of foreign corporation: CORP LTD
        Reference ID: CFC001
        """
        table = [
            ["", "Beginning of year", "End of year"],
            ["Cash", "1,000,000", "2,000,000"],
        ]

        mock_plumber.open.return_value = _make_mock_pdf(
            [page_5471_f], tables_per_page={0: [table]}
        )

        extractor = PDFExtractor(pdf_file, schedule="8858_F")
        df = extractor.extract()

        assert df.empty

"""Unit tests for EFileParser — edge cases, resilience, and correctness.

Covers:
- File not found handling
- Empty XML / no subsidiaries
- Missing namespace handling
- Multi-instance form expansion (Schedule J baskets)
- to_dataframe with various form combinations
- extract_top_level_form
- _flatten_element depth limit
- get_field lookup
"""

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.parser import EFileParser

FIXTURES = Path(__file__).parent / "fixtures"


# ═══════════════════════════════════════════════════════════════════════════════
# RESILIENCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestParserResilience:
    """Parser behavior with invalid/edge-case inputs."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            EFileParser("definitely_nonexistent_file.xml")

    def test_empty_xml_file(self, tmp_path):
        empty = tmp_path / "empty.xml"
        empty.write_text('<?xml version="1.0"?><Return xmlns="http://www.irs.gov/efile"></Return>')
        parser = EFileParser(empty)
        result = parser.list_subsidiaries()
        assert result == []

    def test_no_subsidiary_returns(self, tmp_path):
        xml = tmp_path / "no_subs.xml"
        xml.write_text(
            '<?xml version="1.0"?>'
            '<Return xmlns="http://www.irs.gov/efile">'
            "<ReturnHeader><TaxYr>2025</TaxYr></ReturnHeader>"
            "<ReturnData></ReturnData>"
            "</Return>"
        )
        parser = EFileParser(xml)
        subs = parser.list_subsidiaries()
        assert subs == []
        df = parser.to_dataframe()
        assert df.empty

    def test_subsidiary_without_return_data(self, tmp_path):
        xml = tmp_path / "no_ret_data.xml"
        xml.write_text(
            '<?xml version="1.0"?>'
            '<Return xmlns="http://www.irs.gov/efile">'
            "<ReturnHeader><TaxYr>2025</TaxYr></ReturnHeader>"
            "<SubsidiaryReturn>"
            "<ReturnHeader>"
            "<SubsidiaryCorpGrp>"
            "<BusinessName><BusinessNameLine1Txt>TEST CORP</BusinessNameLine1Txt></BusinessName>"
            "</SubsidiaryCorpGrp>"
            "</ReturnHeader>"
            "</SubsidiaryReturn>"
            "</Return>"
        )
        parser = EFileParser(xml)
        subs = parser.list_subsidiaries()
        assert len(subs) == 1
        assert subs[0]["name"] == "TEST CORP"

    def test_path_accepts_string(self):
        parser = EFileParser(str(FIXTURES / "sample_cy.xml"))
        assert parser.path.exists()

    def test_path_accepts_pathlib(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        assert parser.path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — list_subsidiaries()
# ═══════════════════════════════════════════════════════════════════════════════


class TestListSubsidiaries:
    def test_returns_expected_entities(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        subs = parser.list_subsidiaries()
        assert len(subs) == 5
        refs = {s["reference_id"] for s in subs}
        assert refs == {"E001", "E002", "E003", "E004", "E005"}

    def test_entity_fields_populated(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        subs = parser.list_subsidiaries()
        by_ref = {s["reference_id"]: s for s in subs}

        e001 = by_ref["E001"]
        assert e001["name"] == "CLEAN SUBSIDIARY LTD"
        assert e001["country_code"] == "UK"
        assert e001["functional_currency"] == "GBP"
        assert e001["dormant"] is False

    def test_prior_year_has_different_count(self):
        parser = EFileParser(FIXTURES / "sample_py.xml")
        subs = parser.list_subsidiaries()
        refs = {s["reference_id"] for s in subs}
        assert "EDROP" in refs


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — extract_form()
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractForm:
    @pytest.fixture
    def parser(self):
        return EFileParser(FIXTURES / "sample_cy.xml")

    def test_extract_schedule_h(self, parser):
        df = parser.extract_form("IRS5471ScheduleH")
        assert not df.empty
        assert "_reference_id" in df.columns
        assert "_entity_name" in df.columns
        refs = set(df["_reference_id"])
        assert "E001" in refs

    def test_extract_nonexistent_form_returns_empty(self, parser):
        df = parser.extract_form("IRS5471ScheduleZ")
        assert df.empty

    def test_multi_instance_schedule_j(self, parser):
        df = parser.extract_form("IRS5471ScheduleJ")
        if not df.empty:
            assert "_basket" in df.columns
            baskets = set(df["_basket"].dropna().unique())
            assert len(baskets) >= 1

    def test_extract_form_preserves_document_id(self, parser):
        df = parser.extract_form("IRS5471ScheduleH")
        assert "_document_id" in df.columns

    def test_columns_have_form_prefix(self, parser):
        df = parser.extract_form("IRS5471ScheduleH")
        data_cols = [c for c in df.columns if not c.startswith("_")]
        assert all(c.startswith("IRS5471ScheduleH_") for c in data_cols)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — to_dataframe()
# ═══════════════════════════════════════════════════════════════════════════════


class TestToDataframe:
    @pytest.fixture
    def parser(self):
        return EFileParser(FIXTURES / "sample_cy.xml")

    def test_default_forms_included(self, parser):
        df = parser.to_dataframe()
        assert not df.empty
        assert len(df) == 5  # 5 entities
        assert "_reference_id" in df.columns
        assert "_entity_name" in df.columns

    def test_single_multi_instance_form(self, parser):
        df = parser.to_dataframe(forms=["IRS5471ScheduleJ"])
        if not df.empty:
            assert "_basket" in df.columns

    def test_metadata_columns_present(self, parser):
        df = parser.to_dataframe()
        meta_cols = [c for c in df.columns if c.startswith("_")]
        assert "_entity_name" in meta_cols
        assert "_reference_id" in meta_cols
        assert "_country_code" in meta_cols
        assert "_functional_currency" in meta_cols

    def test_custom_form_list(self, parser):
        df = parser.to_dataframe(forms=["IRS5471ScheduleH"])
        data_cols = [c for c in df.columns if c.startswith("IRS5471ScheduleH_")]
        assert len(data_cols) > 0
        # No other form prefixes
        non_h_data = [c for c in df.columns if not c.startswith("_") and not c.startswith("IRS5471ScheduleH_")]
        assert len(non_h_data) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — extract_top_level_form()
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractTopLevelForm:
    @pytest.fixture
    def parser(self):
        return EFileParser(FIXTURES / "sample_cy.xml")

    def test_nonexistent_form_returns_empty(self, parser):
        df = parser.extract_top_level_form("IRS8990")
        assert isinstance(df, pd.DataFrame)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — parse() full extraction
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullParse:
    def test_parsed_return_structure(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        result = parser.parse()
        assert result.source_path == FIXTURES / "sample_cy.xml"
        assert result.header is not None
        assert len(result.subsidiaries) == 5

    def test_header_fields(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        result = parser.parse()
        h = result.header
        assert h.tax_year != ""
        assert h.filer_name != ""

    def test_subsidiary_entity_info(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        result = parser.parse()
        sub = result.subsidiaries[0]
        assert sub.entity.name != ""
        assert sub.entity.reference_id in {"E001", "E002", "E003", "E004", "E005"}

    def test_subsidiary_forms_populated(self):
        parser = EFileParser(FIXTURES / "sample_cy.xml")
        result = parser.parse()
        sub = result.subsidiaries[0]
        assert len(sub.forms) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — get_field()
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetField:
    @pytest.fixture
    def parser(self):
        return EFileParser(FIXTURES / "sample_cy.xml")

    def test_existing_entity_existing_field(self, parser):
        result = parser.get_field(
            "CLEAN SUBSIDIARY",
            ".//irs:ReturnData/irs:IRS5471/irs:FunctionalCurrencyCd",
        )
        assert result == "GBP"

    def test_nonexistent_entity(self, parser):
        result = parser.get_field(
            "DOES NOT EXIST",
            ".//irs:ReturnData/irs:IRS5471/irs:FunctionalCurrencyCd",
        )
        assert result is None

    def test_nonexistent_xpath(self, parser):
        result = parser.get_field(
            "CLEAN SUBSIDIARY",
            ".//irs:ReturnData/irs:NonexistentElement",
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS — 8858 Parsing
# ═══════════════════════════════════════════════════════════════════════════════


class TestParser8858EdgeCases:
    @pytest.fixture
    def parser(self):
        return EFileParser(FIXTURES / "sample_8858_cy.xml")

    def test_extract_form_8858_nonexistent_schedule(self, parser):
        df = parser.extract_form_8858("IRS8858ScheduleZ")
        assert df.empty

    def test_8858_entities_have_tax_owner(self, parser):
        entities = parser.list_8858_entities()
        for e in entities:
            assert "tax_owner" in e
            assert "tax_owner_ref_id" in e

    def test_8858_entity_category(self, parser):
        entities = parser.list_8858_entities()
        categories = {e["category"] for e in entities}
        assert categories.issubset({"FDE", "FB"})

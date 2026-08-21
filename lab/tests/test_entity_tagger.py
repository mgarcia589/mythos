"""Tests for Entity Tagger — rules, contradictions, tolerance, batch."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from lab.core.entity_tagger import EntityData, EntityTagger, TagResult, CONTRADICTIONS


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tagger():
    return EntityTagger()


@pytest.fixture
def empty_entity():
    return EntityData(reference_id="E001", entity_name="Empty Corp")


@pytest.fixture
def tested_income_entity():
    return EntityData(
        reference_id="E002",
        entity_name="Income Corp",
        sch_i1={"TestedIncomeAmt": 5_000_000, "QBAIAmt": 2_000_000},
        sch_h={"CurrentEarningsAndProfitsAmt": 3_000_000},
        voting_stock_pct=1.0,
    )


@pytest.fixture
def tested_loss_entity():
    return EntityData(
        reference_id="E003",
        entity_name="Loss Corp",
        sch_i1={"TestedLossAmt": 1_200_000},
        sch_h={"CurrentEarningsAndProfitsAmt": -500_000},
    )


@pytest.fixture
def subpart_f_entity():
    return EntityData(
        reference_id="E004",
        entity_name="SubF Corp",
        sch_i={
            "SubpartFPHCIncomeAmt": 800_000,
            "SubpartFSalesIncomeAmt": 200_000,
        },
        sch_c={"ForeignGrossIncomeAmt": 50_000_000},
        sch_h={"CurrentEarningsAndProfitsAmt": 4_000_000},
    )


@pytest.fixture
def dormant_entity():
    return EntityData(
        reference_id="E005",
        entity_name="Dormant LLC",
        is_dormant=True,
        sch_c={"GrossReceiptsOrSalesAmt": 0, "NetIncomeAmt": 0},
        sch_h={"CurrentEarningsAndProfitsAmt": 0},
    )


@pytest.fixture
def dre_entity():
    return EntityData(
        reference_id="E006",
        entity_name="DRE Subsidiary",
        is_dre=True,
    )


# ─── TEST: TESTED INCOME RULE ────────────────────────────────────────────────

class TestTestedIncomeRule:
    def test_positive_amount_tags(self, tagger, tested_income_entity):
        result = tagger.tag(tested_income_entity)
        assert "tested_income" in result.tags

    def test_zero_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "tested_income" not in result.tags

    def test_missing_schedule_does_not_tag(self, tagger):
        e = EntityData(reference_id="X", sch_i1={})
        result = tagger.tag(e)
        assert "tested_income" not in result.tags


# ─── TEST: TESTED LOSS RULE ──────────────────────────────────────────────────

class TestTestedLossRule:
    def test_positive_loss_amount_tags(self, tagger, tested_loss_entity):
        result = tagger.tag(tested_loss_entity)
        assert "tested_loss" in result.tags

    def test_zero_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "tested_loss" not in result.tags


# ─── TEST: HIGH TAX EXCLUSION ────────────────────────────────────────────────

class TestHighTaxExclusionRule:
    def test_positive_exclusion_tags(self, tagger):
        e = EntityData(reference_id="X", sch_i1={"ExclGrossIncmHghTxdIncmAmt": 100_000})
        result = tagger.tag(e)
        assert "high_tax_exclusion" in result.tags

    def test_zero_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "high_tax_exclusion" not in result.tags


# ─── TEST: SUBPART F ─────────────────────────────────────────────────────────

class TestSubpartFRule:
    def test_phc_income_tags(self, tagger, subpart_f_entity):
        result = tagger.tag(subpart_f_entity)
        assert "subpart_f" in result.tags

    def test_zero_subf_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "subpart_f" not in result.tags

    def test_single_field_sufficient(self, tagger):
        e = EntityData(reference_id="X", sch_i={"SubpartFIncomeAmt": 500})
        result = tagger.tag(e)
        assert "subpart_f" in result.tags


# ─── TEST: DE MINIMIS ────────────────────────────────────────────────────────

class TestDeMinimisRule:
    def test_below_1m_with_low_gross(self, tagger):
        """SubF = $900K, gross = $10M → threshold = min(1M, 500K) = 500K → NOT de minimis."""
        e = EntityData(
            reference_id="X",
            sch_i={"SubpartFIncomeAmt": 900_000},
            sch_c={"ForeignGrossIncomeAmt": 10_000_000},
        )
        result = tagger.tag(e)
        assert "de_minimis" not in result.tags

    def test_below_5pct_of_gross(self, tagger):
        """SubF = $400K, gross = $100M → threshold = min(1M, 5M) = 1M → IS de minimis."""
        e = EntityData(
            reference_id="X",
            sch_i={"SubpartFIncomeAmt": 400_000},
            sch_c={"ForeignGrossIncomeAmt": 100_000_000},
        )
        result = tagger.tag(e)
        assert "de_minimis" in result.tags

    def test_exactly_at_1m_boundary(self, tagger):
        """SubF = $999,999 < $1M threshold (gross very large)."""
        e = EntityData(
            reference_id="X",
            sch_i={"SubpartFIncomeAmt": 999_999},
            sch_c={"ForeignGrossIncomeAmt": 500_000_000},
        )
        result = tagger.tag(e)
        assert "de_minimis" in result.tags

    def test_no_subf_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "de_minimis" not in result.tags


# ─── TEST: NEGATIVE E&P ──────────────────────────────────────────────────────

class TestNegativeEPRule:
    def test_negative_ep_tags(self, tagger, tested_loss_entity):
        result = tagger.tag(tested_loss_entity)
        assert "negative_ep" in result.tags

    def test_positive_ep_does_not_tag(self, tagger, tested_income_entity):
        result = tagger.tag(tested_income_entity)
        assert "negative_ep" not in result.tags

    def test_zero_ep_does_not_tag(self, tagger):
        e = EntityData(reference_id="X", sch_h={"CurrentEarningsAndProfitsAmt": 0})
        result = tagger.tag(e)
        assert "negative_ep" not in result.tags


# ─── TEST: FULL INCLUSION ────────────────────────────────────────────────────

class TestFullInclusionRule:
    def test_100pct_with_tested_income_tags(self, tagger, tested_income_entity):
        result = tagger.tag(tested_income_entity)
        assert "full_inclusion" in result.tags

    def test_partial_ownership_does_not_tag(self, tagger):
        e = EntityData(reference_id="X", voting_stock_pct=0.8, sch_i1={"TestedIncomeAmt": 1_000_000})
        result = tagger.tag(e)
        assert "full_inclusion" not in result.tags

    def test_100pct_without_tested_income_does_not_tag(self, tagger):
        e = EntityData(reference_id="X", voting_stock_pct=1.0)
        result = tagger.tag(e)
        assert "full_inclusion" not in result.tags

    def test_none_ownership_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "full_inclusion" not in result.tags


# ─── TEST: INTEREST EXPENSE ─────────────────────────────────────────────────

class TestInterestExpenseRule:
    def test_interest_expense_tags(self, tagger):
        e = EntityData(reference_id="X", sch_i1={"TestedInterestExpenseAmt": 50_000})
        result = tagger.tag(e)
        assert "interest_expense" in result.tags

    def test_no_interest_expense_does_not_tag(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert "interest_expense" not in result.tags


# ─── TEST: CONTRADICTIONS ────────────────────────────────────────────────────

class TestContradictions:
    def test_income_and_loss_contradiction(self, tagger):
        """Injecting both tested income and loss should flag contradiction."""
        e = EntityData(
            reference_id="X",
            sch_i1={"TestedIncomeAmt": 100, "TestedLossAmt": 200},
        )
        result = tagger.tag(e)
        assert "tested_income" in result.tags
        assert "tested_loss" in result.tags
        assert any(c[0] == "tested_income" and c[1] == "tested_loss"
                   for c in result.contradictions)

    def test_no_contradictions_for_clean_entity(self, tagger, tested_income_entity):
        result = tagger.tag(tested_income_entity)
        assert result.contradictions == []


# ─── TEST: TOLERANCE (MISSING DATA) ─────────────────────────────────────────

class TestTolerance:
    def test_completely_empty_entity_no_crash(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert isinstance(result, TagResult)
        assert result.reference_id == "E001"

    def test_empty_dicts_produce_no_tags(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert len(result.tags) == 0

    def test_invalid_value_type_handled(self, tagger):
        e = EntityData(reference_id="X", sch_i1={"TestedIncomeAmt": "not_a_number"})
        result = tagger.tag(e)
        assert "tested_income" not in result.tags


# ─── TEST: BATCH MODE ────────────────────────────────────────────────────────

class TestBatchMode:
    def test_batch_returns_list(self, tagger, tested_income_entity, tested_loss_entity):
        results = tagger.tag_batch([tested_income_entity, tested_loss_entity])
        assert len(results) == 2
        assert results[0].reference_id == "E002"
        assert results[1].reference_id == "E003"

    def test_batch_empty_list(self, tagger):
        results = tagger.tag_batch([])
        assert results == []

    def test_summary_counts(self, tagger, tested_income_entity, tested_loss_entity):
        results = tagger.tag_batch([tested_income_entity, tested_loss_entity])
        summary = tagger.summary(results)
        assert summary.get("tested_income", 0) == 1
        assert summary.get("tested_loss", 0) == 1


# ─── TEST: ENTITYDATA ACCESSORS ──────────────────────────────────────────────

class TestEntityDataAccessors:
    def test_get_existing_field(self):
        e = EntityData(reference_id="X", sch_i1={"QBAIAmt": 1_500_000})
        assert e.get("i1", "QBAIAmt") == 1_500_000

    def test_get_missing_field_returns_default(self):
        e = EntityData(reference_id="X", sch_i1={})
        assert e.get("i1", "QBAIAmt") == 0.0

    def test_get_missing_schedule_returns_default(self):
        e = EntityData(reference_id="X")
        assert e.get("z99", "SomeField") == 0.0

    def test_has_schedule_true(self):
        e = EntityData(reference_id="X", sch_h={"CurrentEarningsAndProfitsAmt": 100})
        assert e.has_schedule("h") is True

    def test_has_schedule_false(self):
        e = EntityData(reference_id="X", sch_h={})
        assert e.has_schedule("h") is False


# ─── TEST: EVIDENCE (TAG → XML FIELD TRACEABILITY) ──────────────────────────

class TestEvidence:
    def test_tested_income_captures_evidence(self, tagger):
        e = EntityData(reference_id="X", sch_i1={"TestedIncomeAmt": 5_000_000})
        result = tagger.tag(e)
        assert "tested_income" in result.tags
        assert "tested_income" in result.evidence
        assert result.evidence["tested_income"]["i1.TestedIncomeAmt"] == 5_000_000

    def test_subpart_f_captures_multiple_fields(self, tagger):
        e = EntityData(
            reference_id="X",
            sch_i={"SubpartFPHCIncomeAmt": 300_000, "SubpartFSalesIncomeAmt": 100_000},
        )
        result = tagger.tag(e)
        assert "subpart_f" in result.tags
        ev = result.evidence["subpart_f"]
        assert ev["i.SubpartFPHCIncomeAmt"] == 300_000
        assert ev["i.SubpartFSalesIncomeAmt"] == 100_000

    def test_negative_ep_captures_evidence(self, tagger):
        e = EntityData(reference_id="X", sch_h={"CurrentEarningsAndProfitsAmt": -750_000})
        result = tagger.tag(e)
        assert "negative_ep" in result.tags
        assert result.evidence["negative_ep"]["h.CurrentEarningsAndProfitsAmt"] == -750_000

    def test_no_evidence_when_tag_not_fired(self, tagger, empty_entity):
        result = tagger.tag(empty_entity)
        assert result.evidence == {}

    def test_evidence_flows_to_classifier_tag_metadata(self):
        from lab.core.entity_classifier import ClassifiedEntity, EntityClassifier
        classifier = EntityClassifier()
        entity = ClassifiedEntity(
            reference_id="E1",
            entity_name="Test Corp",
            sch_i1={"TestedIncomeAmt": 2_000_000, "TestedInterestExpenseAmt": 50_000},
            voting_stock_pct=1.0,
        )
        classifier._apply_tags(entity)
        assert "tested_income" in entity.tag_metadata
        assert entity.tag_metadata["tested_income"]["i1.TestedIncomeAmt"] == 2_000_000
        assert "interest_expense" in entity.tag_metadata
        assert entity.tag_metadata["interest_expense"]["i1.TestedInterestExpenseAmt"] == 50_000

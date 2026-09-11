"""Tests for Entity Classifier — unified pipeline, summary, adapters, registry enrichment.

v2: Added tests for O(1) registry lookups, populate_from_parser, cache,
    completeness scoring, and avg_completeness in summary.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from lab.core.entity_classifier import (
    ClassifiedEntity,
    ClassificationResult,
    ClassificationSummary,
    EntityClassifier,
)
from lab.core.entity_tagger import EntityData
from lab.core.entity_registry import EntityRegistry, Entity


FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_CY = FIXTURES / "sample_cy.xml"


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


@pytest.fixture
def classifier():
    return EntityClassifier()


@pytest.fixture
def classifier_with_registry():
    registry = EntityRegistry.sample()
    return EntityClassifier(registry=registry)


@pytest.fixture
def sample_parser():
    from lab.xml_parser.parser import EFileParser
    return EFileParser(SAMPLE_CY)


@pytest.fixture
def custom_registry():
    entities = [
        Entity("T001", "Test Insurance Co", "USD", "BD", "TestDeal", is_insurance=True, ein_ref="REF001"),
        Entity("T002", "Test DRE Sub", "EUR", "DE", "TestDeal", is_dre=True, ein_ref="REF002"),
        Entity("T003", "Regular Corp", "GBP", "UK", "TestDeal"),
    ]
    return EntityRegistry(entities)


# ─── TEST: CLASSIFIED ENTITY PROPERTIES ─────────────────────────────────────


class TestClassifiedEntity:
    def test_has_schedule_properties(self):
        e = ClassifiedEntity(
            reference_id="X",
            entity_name="Test",
            sch_h={"CurrentEarningsAndProfitsAmt": 100},
            sch_c={},
        )
        assert e.has_sch_h is True
        assert e.has_sch_c is False
        assert e.has_sch_i is False

    def test_to_entity_data_preserves_fields(self):
        e = ClassifiedEntity(
            reference_id="REF1",
            entity_name="Corp A",
            voting_stock_pct=1.0,
            dormant=True,
            is_insurance=True,
            is_dre=False,
            sch_h={"CurrentEarningsAndProfitsAmt": 500},
            sch_i1={"TestedIncomeAmt": 1000},
        )
        ed = e.to_entity_data()
        assert isinstance(ed, EntityData)
        assert ed.reference_id == "REF1"
        assert ed.entity_name == "Corp A"
        assert ed.voting_stock_pct == 1.0
        assert ed.is_dormant is True
        assert ed.is_insurance is True
        assert ed.is_dre is False
        assert ed.sch_h == {"CurrentEarningsAndProfitsAmt": 500}
        assert ed.sch_i1 == {"TestedIncomeAmt": 1000}

    def test_to_entity_data_empty_schedules(self):
        e = ClassifiedEntity(reference_id="X", entity_name="Empty")
        ed = e.to_entity_data()
        assert ed.sch_c == {}
        assert ed.sch_h == {}

    def test_default_values(self):
        e = ClassifiedEntity(reference_id="X", entity_name="Test")
        assert e.country_code == ""
        assert e.functional_currency == ""
        assert e.voting_stock_pct is None
        assert e.dormant is False
        assert e.is_insurance is False
        assert e.is_dre is False
        assert e.tags == set()
        assert e.contradictions == []
        assert e.oit_locator == ""
        assert e.document_id == ""
        assert e.completeness_score == 0.0
        assert e.missing_schedules == []
        assert e.present_schedules == []


# ─── TEST: OIT LOCATOR EXTRACTION ───────────────────────────────────────────


class TestOitLocator:
    def test_valid_production_format(self):
        loc = EntityClassifier._extract_oit_locator("F5471EGEN000272I5")
        assert loc == "000272"

    def test_another_valid_id(self):
        loc = EntityClassifier._extract_oit_locator("F5471EGEN123456X9")
        assert loc == "123456"

    def test_short_document_id_returns_empty(self):
        loc = EntityClassifier._extract_oit_locator("SHORT")
        assert loc == ""

    def test_empty_string(self):
        loc = EntityClassifier._extract_oit_locator("")
        assert loc == ""

    def test_non_alnum_at_position_returns_empty(self):
        loc = EntityClassifier._extract_oit_locator("F5471EGENab!d#fX9")
        assert loc == ""

    def test_fixture_format_no_locator(self):
        loc = EntityClassifier._extract_oit_locator("IRS5471-E001")
        assert loc == ""


# ─── TEST: CLASSIFIER PIPELINE (with fixture XML) ───────────────────────────


@pytest.mark.skipif(not SAMPLE_CY.exists(), reason="Fixture not available")
class TestClassifierPipeline:
    def test_classify_returns_entities(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        assert isinstance(entities, list)
        assert len(entities) > 0
        assert all(isinstance(e, ClassifiedEntity) for e in entities)

    def test_entities_have_identity(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        for e in entities:
            assert e.reference_id
            assert e.entity_name

    def test_entities_have_tags(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        tagged = [e for e in entities if e.tags]
        assert len(tagged) > 0

    def test_classify_single(self, classifier, sample_parser):
        all_entities = classifier.classify(sample_parser)
        first_ref = all_entities[0].reference_id
        single = classifier.classify_single(sample_parser, first_ref)
        assert single is not None
        assert single.reference_id == first_ref
        assert single.tags == all_entities[0].tags

    def test_classify_single_not_found(self, classifier, sample_parser):
        result = classifier.classify_single(sample_parser, "NONEXISTENT_REF")
        assert result is None

    def test_schedule_data_populated(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        has_any_schedule = any(
            e.has_sch_h or e.has_sch_i or e.has_sch_i1 or e.has_sch_c
            for e in entities
        )
        assert has_any_schedule

    def test_country_and_currency_populated(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        has_country = any(e.country_code for e in entities)
        assert has_country

    def test_full_identity_from_page1(self, classifier, sample_parser):
        """Verify address, city, postal code flow from SubsidiaryEntity."""
        entities = classifier.classify(sample_parser)
        e001 = next(e for e in entities if e.reference_id == "E001")
        assert e001.entity_name == "CLEAN SUBSIDIARY LTD"
        assert e001.address_line1 == "123 Main Street"
        assert e001.city == "London"
        assert e001.postal_code == "EC1A 1BB"
        assert e001.country_code == "UK"
        assert e001.functional_currency == "GBP"

    def test_principal_place_of_business(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        e001 = next(e for e in entities if e.reference_id == "E001")
        assert e001.principal_place_of_business == "UK"

    def test_form_type_default_5471(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        for e in entities:
            assert e.form_type == "5471"

    def test_multiple_entities_have_distinct_addresses(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        cities = [e.city for e in entities if e.city]
        assert len(set(cities)) > 1

    def test_completeness_populated(self, classifier, sample_parser):
        entities = classifier.classify(sample_parser)
        for e in entities:
            assert 0.0 <= e.completeness_score <= 1.0
            assert isinstance(e.present_schedules, list)
            assert isinstance(e.missing_schedules, list)

    def test_cache_returns_same_list(self, classifier, sample_parser):
        first = classifier.classify(sample_parser)
        second = classifier.classify(sample_parser)
        assert first is second

    def test_invalidate_cache(self, classifier, sample_parser):
        first = classifier.classify(sample_parser)
        classifier.invalidate_cache(sample_parser)
        second = classifier.classify(sample_parser)
        assert first is not second
        assert len(first) == len(second)


# ─── TEST: CLASSIFICATION SUMMARY ───────────────────────────────────────────


class TestClassificationSummary:
    def test_summary_from_entities(self, classifier):
        entities = [
            ClassifiedEntity(
                reference_id="E1", entity_name="Corp A",
                country_code="UK", tags={"tested_income", "full_inclusion"},
            ),
            ClassifiedEntity(
                reference_id="E2", entity_name="Corp B",
                country_code="DE", tags={"tested_loss", "negative_ep"},
            ),
            ClassifiedEntity(
                reference_id="E3", entity_name="Corp C",
                country_code="UK", tags={"subpart_f"},
            ),
        ]
        summary = classifier.build_summary(entities)
        assert summary.total_entities == 3
        assert summary.tested_income_count == 1
        assert summary.tested_loss_count == 1
        assert summary.by_country["UK"] == 2
        assert summary.by_country["DE"] == 1
        assert summary.by_tag["tested_income"] == 1
        assert summary.by_tag["subpart_f"] == 1

    def test_summary_by_type(self, classifier):
        entities = [
            ClassifiedEntity(reference_id="E1", entity_name="Ins", is_insurance=True, tags=set()),
            ClassifiedEntity(reference_id="E2", entity_name="DRE", is_dre=True, tags=set()),
            ClassifiedEntity(reference_id="E3", entity_name="Norm", tags=set()),
            ClassifiedEntity(reference_id="E4", entity_name="Active", tags={"tested_income"}),
        ]
        summary = classifier.build_summary(entities)
        assert summary.by_type["insurance"] == 1
        assert summary.by_type["dre"] == 1
        assert summary.by_type["normal"] == 2

    def test_summary_contradictions(self, classifier):
        entities = [
            ClassifiedEntity(
                reference_id="E1", entity_name="Bad",
                tags={"tested_income", "tested_loss"},
                contradictions=[("tested_income", "tested_loss", "Cannot have both")],
            ),
        ]
        summary = classifier.build_summary(entities)
        assert len(summary.contradictions) == 1
        assert summary.contradictions[0][0] == "E1"

    def test_empty_entities_summary(self, classifier):
        summary = classifier.build_summary([])
        assert summary.total_entities == 0
        assert summary.by_tag == {}
        assert summary.by_country == {}
        assert summary.tested_income_count == 0
        assert summary.avg_completeness == 0.0

    def test_summary_avg_completeness(self, classifier):
        entities = [
            ClassifiedEntity(reference_id="E1", entity_name="A", completeness_score=1.0),
            ClassifiedEntity(reference_id="E2", entity_name="B", completeness_score=0.5),
        ]
        summary = classifier.build_summary(entities)
        assert summary.avg_completeness == 0.75


# ─── TEST: REGISTRY ENRICHMENT ──────────────────────────────────────────────


class TestRegistryEnrichment:
    def test_match_by_name_enriches_insurance(self):
        registry = EntityRegistry([
            Entity("E006", "Alpha Reinsurance Limited", "USD", "BD", "Portfolio-A", is_insurance=True),
        ])
        classifier = EntityClassifier(registry=registry)

        entity = ClassifiedEntity(
            reference_id="REF1",
            entity_name="Alpha Reinsurance Limited",
        )
        classifier._enrich_from_registry(entity)
        assert entity.is_insurance is True

    def test_match_by_name_enriches_dre(self):
        registry = EntityRegistry([
            Entity("E016", "Alpha Europe Limited (Zurich)", "USD", "SZ", "Portfolio-A", is_dre=True),
        ])
        classifier = EntityClassifier(registry=registry)

        entity = ClassifiedEntity(
            reference_id="REF2",
            entity_name="Alpha Europe Limited (Zurich)",
        )
        classifier._enrich_from_registry(entity)
        assert entity.is_dre is True

    def test_match_by_ref_id(self, custom_registry):
        classifier = EntityClassifier(registry=custom_registry)

        entity = ClassifiedEntity(
            reference_id="REF001",
            entity_name="Some Other Name",
        )
        classifier._enrich_from_registry(entity)
        assert entity.is_insurance is True

    def test_no_match_leaves_defaults(self):
        registry = EntityRegistry([
            Entity("C0001", "Specific Corp", "USD", "US", "Deal"),
        ])
        classifier = EntityClassifier(registry=registry)

        entity = ClassifiedEntity(
            reference_id="UNKNOWN",
            entity_name="Totally Different Corp",
        )
        classifier._enrich_from_registry(entity)
        assert entity.is_insurance is False
        assert entity.is_dre is False

    def test_no_registry_is_noop(self, classifier):
        entity = ClassifiedEntity(reference_id="X", entity_name="Test")
        classifier._enrich_from_registry(entity)
        assert entity.is_insurance is False


# ─── TEST: ENTITY REGISTRY v2 — O(1) LOOKUPS + POPULATE ───────────────────


class TestEntityRegistryV2:
    def test_o1_match_by_ref_id(self):
        registry = EntityRegistry([
            Entity("T001", "Test Corp", "USD", "US", "Deal", ein_ref="REF123"),
        ])
        result = registry.match_by_ref_id("REF123")
        assert result is not None
        assert result.name == "Test Corp"

    def test_o1_match_by_name_exact(self):
        registry = EntityRegistry([
            Entity("T001", "Test Corp", "USD", "US", "Deal"),
        ])
        result = registry.match_by_name("Test Corp")
        assert result is not None
        assert result.code == "T001"

    def test_match_by_name_case_insensitive(self):
        registry = EntityRegistry([
            Entity("T001", "Test Corp", "USD", "US", "Deal"),
        ])
        result = registry.match_by_name("TEST CORP")
        assert result is not None

    def test_match_by_name_substring_fallback(self):
        registry = EntityRegistry([
            Entity("T001", "Test Insurance Co", "USD", "BD", "Deal"),
        ])
        result = registry.match_by_name("Test Insurance Co Subsidiary")
        assert result is not None
        assert result.code == "T001"

    def test_match_by_name_empty(self):
        registry = EntityRegistry([Entity("T001", "Corp", "USD", "US", "Deal")])
        assert registry.match_by_name("") is None

    def test_match_by_ref_id_empty(self):
        registry = EntityRegistry([Entity("T001", "Corp", "USD", "US", "Deal")])
        assert registry.match_by_ref_id("") is None

    def test_match_not_found(self):
        registry = EntityRegistry([Entity("T001", "Corp A", "USD", "US", "Deal")])
        assert registry.match_by_name("Completely Different") is None
        assert registry.match_by_ref_id("NOPE") is None

    def test_register_updates_all_indexes(self):
        registry = EntityRegistry()
        registry.register(Entity("NEW1", "New Corp", "EUR", "DE", "DealX", ein_ref="REF_NEW"))
        assert registry.get("NEW1") is not None
        assert registry.match_by_name("New Corp") is not None
        assert registry.match_by_ref_id("REF_NEW") is not None
        assert registry.count == 1

    def test_register_upsert_last_wins(self):
        registry = EntityRegistry()
        registry.register(Entity("C1", "Alpha Corp", "USD", "US", "D1"))
        registry.register(Entity("C1", "Alpha Corp Updated", "EUR", "DE", "D2"))
        result = registry.get("C1")
        assert result.name == "Alpha Corp Updated"
        assert result.fc == "EUR"

    def test_count_and_len(self):
        registry = EntityRegistry([
            Entity("A", "A Corp", "USD", "US", "D"),
            Entity("B", "B Corp", "USD", "US", "D"),
        ])
        assert registry.count == 2
        assert len(registry) == 2

    def test_clear(self):
        registry = EntityRegistry.sample()
        assert registry.count > 0
        registry.clear()
        assert registry.count == 0
        assert registry.match_by_name("Alpha TopCo Ltd") is None

    def test_by_form_type(self):
        registry = EntityRegistry([
            Entity("A", "Corp 5471", "USD", "US", "D", form_type="5471"),
            Entity("B", "FDE 8858", "EUR", "DE", "D", form_type="8858"),
        ])
        assert len(registry.by_form_type("5471")) == 1
        assert len(registry.by_form_type("8858")) == 1

    def test_contains_and_getitem(self):
        registry = EntityRegistry([Entity("X1", "Test", "USD", "US", "D")])
        assert "X1" in registry
        assert "X2" not in registry
        assert registry["X1"].name == "Test"
        with pytest.raises(KeyError):
            _ = registry["X2"]

    def test_sample_factory(self):
        registry = EntityRegistry.sample()
        assert registry.count == 36
        assert registry.match_by_name("Alpha TopCo Ltd") is not None


@pytest.mark.skipif(not SAMPLE_CY.exists(), reason="Fixture not available")
class TestRegistryPopulateFromParser:
    def test_populate_returns_count(self):
        from lab.xml_parser.parser import EFileParser
        parser = EFileParser(SAMPLE_CY)
        registry = EntityRegistry()
        count = registry.populate_from_parser(parser)
        assert count > 0

    def test_populated_entities_are_findable(self):
        from lab.xml_parser.parser import EFileParser
        parser = EFileParser(SAMPLE_CY)
        registry = EntityRegistry()
        registry.populate_from_parser(parser)
        parsed = parser.parse()
        for sub in parsed.subsidiaries:
            ref = sub.entity.reference_id
            if ref:
                assert registry.match_by_ref_id(ref) is not None

    def test_populated_entity_has_metadata(self):
        from lab.xml_parser.parser import EFileParser
        parser = EFileParser(SAMPLE_CY)
        registry = EntityRegistry()
        registry.populate_from_parser(parser)
        e = registry.match_by_ref_id("E001")
        assert e is not None
        assert e.name
        assert e.country
        assert e.fc


# ─── TEST: ENTITY REGISTRY BRIDGE METHODS ───────────────────────────────────


class TestEntityRegistryBridge:
    def test_match_by_ref_id_found(self, custom_registry):
        result = custom_registry.match_by_ref_id("REF001")
        assert result is not None
        assert result.name == "Test Insurance Co"

    def test_match_by_ref_id_not_found(self, custom_registry):
        result = custom_registry.match_by_ref_id("NONEXISTENT")
        assert result is None

    def test_match_by_ref_id_empty_string(self, custom_registry):
        result = custom_registry.match_by_ref_id("")
        assert result is None

    def test_match_by_name_exact(self, custom_registry):
        result = custom_registry.match_by_name("Test Insurance Co")
        assert result is not None
        assert result.code == "T001"

    def test_match_by_name_case_insensitive(self, custom_registry):
        result = custom_registry.match_by_name("test insurance co")
        assert result is not None
        assert result.code == "T001"

    def test_match_by_name_not_found(self, custom_registry):
        result = custom_registry.match_by_name("Nonexistent Corp")
        assert result is None

    def test_match_by_name_empty(self, custom_registry):
        result = custom_registry.match_by_name("")
        assert result is None

    def test_match_by_name_substring(self, custom_registry):
        result = custom_registry.match_by_name("Test Insurance Co Subsidiary")
        assert result is not None
        assert result.code == "T001"


# ─── TEST: TAG CONSISTENCY ──────────────────────────────────────────────────


class TestTagConsistency:
    def test_tagger_produces_same_tags_as_classifier(self):
        """Verify that direct tagger and classifier produce identical tags."""
        from lab.core.entity_tagger import EntityTagger

        entity_data = EntityData(
            reference_id="E1",
            entity_name="Test Corp",
            sch_i1={"TestedIncomeAmt": 1_000_000, "QBAIAmt": 500_000},
            sch_h={"CurrentEarningsAndProfitsAmt": 2_000_000},
            voting_stock_pct=1.0,
        )

        tagger = EntityTagger()
        tag_result = tagger.tag(entity_data)

        classifier = EntityClassifier()
        classified = ClassifiedEntity(
            reference_id="E1",
            entity_name="Test Corp",
            voting_stock_pct=1.0,
            sch_i1={"TestedIncomeAmt": 1_000_000, "QBAIAmt": 500_000},
            sch_h={"CurrentEarningsAndProfitsAmt": 2_000_000},
        )
        classifier._apply_tags(classified)

        assert classified.tags == tag_result.tags
        assert classified.contradictions == tag_result.contradictions

    def test_full_inclusion_requires_tested_income_and_100pct(self):
        classifier = EntityClassifier()
        entity = ClassifiedEntity(
            reference_id="E1",
            entity_name="Full Inc Corp",
            voting_stock_pct=1.0,
            sch_i1={"TestedIncomeAmt": 1_000_000},
        )
        classifier._apply_tags(entity)
        assert "full_inclusion" in entity.tags
        assert "tested_income" in entity.tags

    def test_100pct_without_income_no_full_inclusion(self):
        classifier = EntityClassifier()
        entity = ClassifiedEntity(
            reference_id="E1",
            entity_name="No Income Corp",
            voting_stock_pct=1.0,
        )
        classifier._apply_tags(entity)
        assert "full_inclusion" not in entity.tags


# ─── TEST: COMPLETENESS SCORING ─────────────────────────────────────────────


class TestCompletenessScoring:
    def test_full_5471_all_schedules(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="Full Corp", form_type="5471",
            sch_c={"x": 1}, sch_e={"x": 1}, sch_h={"x": 1},
            sch_i={"x": 1}, sch_i1={"x": 1}, sch_j={"x": 1}, sch_p={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == 1.0
        assert entity.missing_schedules == []
        assert len(entity.present_schedules) == 7

    def test_5471_missing_some(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="Partial Corp", form_type="5471",
            sch_c={"x": 1}, sch_h={"x": 1}, sch_j={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert 0.0 < entity.completeness_score < 1.0
        assert "e" in entity.missing_schedules
        assert "i" in entity.missing_schedules
        assert "i1" in entity.missing_schedules
        assert "p" in entity.missing_schedules

    def test_5471_dormant_only_h_j_expected(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="Dormant Corp",
            form_type="5471", dormant=True,
            sch_h={"x": 1}, sch_j={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == 1.0
        assert entity.missing_schedules == []

    def test_dormant_missing_j(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="Dormant Corp",
            form_type="5471", dormant=True,
            sch_h={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == 0.5
        assert "j" in entity.missing_schedules

    def test_8858_expects_c_f_h(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="FDE",
            form_type="8858",
            sch_c={"x": 1}, sch_f={"x": 1}, sch_h={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == 1.0

    def test_8858_missing_f(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="FDE",
            form_type="8858",
            sch_c={"x": 1}, sch_h={"x": 1},
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == pytest.approx(0.667, abs=0.01)
        assert "f" in entity.missing_schedules

    def test_empty_entity_zero_score(self):
        entity = ClassifiedEntity(
            reference_id="E1", entity_name="Empty", form_type="5471",
        )
        EntityClassifier._compute_completeness(entity)
        assert entity.completeness_score == 0.0
        assert len(entity.missing_schedules) == 7


# ─── TEST: CLASSIFICATION CACHE ─────────────────────────────────────────────


class TestClassificationCache:
    def test_cache_invalidate_all(self, classifier):
        classifier._cache["fake_key"] = [ClassifiedEntity(reference_id="X", entity_name="X")]
        classifier.invalidate_cache()
        assert classifier._cache == {}

    def test_cache_invalidate_specific(self, classifier):
        classifier._cache["path_a"] = []
        classifier._cache["path_b"] = []
        classifier.invalidate_cache(type("P", (), {"path": "path_a"})())
        assert "path_a" not in classifier._cache
        assert "path_b" in classifier._cache


# ─── TEST: FULL INTEGRATION (SERVICE) ───────────────────────────────────────


@pytest.mark.skipif(not SAMPLE_CY.exists(), reason="Fixture not available")
class TestServiceIntegration:
    def test_classify_entities_returns_result(self):
        from lab.xml_parser.api.service import MythosService
        svc = MythosService()
        result = svc.classify_entities(str(SAMPLE_CY))
        assert result.success is True
        assert len(result.entities) > 0
        assert result.summary is not None
        assert result.duration_ms > 0

    def test_tag_entities_backward_compat(self):
        from lab.xml_parser.api.service import MythosService
        svc = MythosService()
        result = svc.tag_entities(str(SAMPLE_CY))
        assert result.success is True
        assert result.entity_count > 0
        assert isinstance(result.summary, dict)

    def test_classify_and_tag_same_entity_count(self):
        from lab.xml_parser.api.service import MythosService
        svc = MythosService()
        cr = svc.classify_entities(str(SAMPLE_CY))
        tr = svc.tag_entities(str(SAMPLE_CY))
        assert len(cr.entities) == tr.entity_count

    def test_classify_with_registry(self):
        from lab.xml_parser.api.service import MythosService
        registry = EntityRegistry.sample()
        svc = MythosService()
        result = svc.classify_entities(str(SAMPLE_CY), registry=registry)
        assert result.success is True

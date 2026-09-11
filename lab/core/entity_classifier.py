"""Entity Classifier — Unified post-parse entity pipeline.

Single parse → enrich → tag → expose ClassifiedEntity as the canonical profile.
Consolidates 6 fragmented representations into one authoritative object.

v2: O(n) indexing, classification cache, completeness scoring, auto-populate registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from lab.core.entity_tagger import EntityData, EntityTagger, TagResult


_EXPECTED_SCHEDULES_5471 = {"c", "e", "h", "i", "i1", "j", "p"}
_EXPECTED_SCHEDULES_5471_DORMANT = {"h", "j"}
_EXPECTED_SCHEDULES_8858 = {"c", "f", "h"}
_EXPECTED_SCHEDULES_8865 = set()


@dataclass
class ClassifiedEntity:
    """Canonical post-parse entity representation — full Page 1 identity + classification."""

    # Identity — core (always populated)
    reference_id: str
    entity_name: str
    country_code: str = ""
    functional_currency: str = ""
    voting_stock_pct: float | None = None
    dormant: bool = False
    category_filers: list[str] = field(default_factory=list)

    # Identity — extended (from SubsidiaryEntity / Page 1)
    ein: str = ""
    incorporation_date: str = ""
    address_line1: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""
    principal_place_of_business: str = ""
    form_type: str = "5471"
    document_id: str = ""
    oit_locator: str = ""

    # 8858-specific identity
    tax_owner_name: str = ""
    tax_owner_ref_id: str = ""
    tax_owner_ein: str = ""
    tax_owner_country: str = ""
    is_fde_us_person: bool = False
    is_fb_cfc: bool = False

    # Type flags (from Registry or inferred)
    is_insurance: bool = False
    is_dre: bool = False

    # Schedule data (prefix-stripped dicts)
    sch_c: dict[str, Any] = field(default_factory=dict)
    sch_e: dict[str, Any] = field(default_factory=dict)
    sch_f: dict[str, Any] = field(default_factory=dict)
    sch_g: dict[str, Any] = field(default_factory=dict)
    sch_h: dict[str, Any] = field(default_factory=dict)
    sch_i: dict[str, Any] = field(default_factory=dict)
    sch_i1: dict[str, Any] = field(default_factory=dict)
    sch_j: dict[str, Any] = field(default_factory=dict)
    sch_p: dict[str, Any] = field(default_factory=dict)

    # Classification output
    tags: set[str] = field(default_factory=set)
    contradictions: list[tuple[str, str, str]] = field(default_factory=list)
    tag_metadata: dict[str, Any] = field(default_factory=dict)

    # Completeness scoring
    completeness_score: float = 0.0
    missing_schedules: list[str] = field(default_factory=list)
    present_schedules: list[str] = field(default_factory=list)

    @property
    def has_sch_c(self) -> bool:
        return bool(self.sch_c)

    @property
    def has_sch_e(self) -> bool:
        return bool(self.sch_e)

    @property
    def has_sch_f(self) -> bool:
        return bool(self.sch_f)

    @property
    def has_sch_g(self) -> bool:
        return bool(self.sch_g)

    @property
    def has_sch_h(self) -> bool:
        return bool(self.sch_h)

    @property
    def has_sch_i(self) -> bool:
        return bool(self.sch_i)

    @property
    def has_sch_i1(self) -> bool:
        return bool(self.sch_i1)

    @property
    def has_sch_j(self) -> bool:
        return bool(self.sch_j)

    @property
    def has_sch_p(self) -> bool:
        return bool(self.sch_p)

    def to_entity_data(self) -> EntityData:
        """Convert to EntityData for the tagger (lean adapter)."""
        return EntityData(
            reference_id=self.reference_id,
            entity_name=self.entity_name,
            is_dormant=self.dormant,
            is_insurance=self.is_insurance,
            is_dre=self.is_dre,
            voting_stock_pct=self.voting_stock_pct,
            sch_c=self.sch_c,
            sch_h=self.sch_h,
            sch_i=self.sch_i,
            sch_i1=self.sch_i1,
            sch_j=self.sch_j,
            sch_g=self.sch_g,
            sch_e=self.sch_e,
            sch_p=self.sch_p,
        )


@dataclass
class ClassificationSummary:
    """Aggregate statistics from a classification run."""

    total_entities: int = 0
    by_tag: dict[str, int] = field(default_factory=dict)
    by_country: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    contradictions: list[tuple[str, str, str, str]] = field(default_factory=list)
    tested_income_count: int = 0
    tested_loss_count: int = 0
    dormant_count: int = 0
    avg_completeness: float = 0.0


@dataclass
class ClassificationResult:
    """Return type for the classify operation."""

    success: bool
    entities: list[ClassifiedEntity] = field(default_factory=list)
    summary: ClassificationSummary | None = None
    duration_ms: float = 0.0
    message: str = ""


class EntityClassifier:
    """Unified entity classification pipeline.

    Parses once, enriches with optional registry, applies tag rules,
    computes completeness, returns ClassifiedEntity list as canonical output.

    v2 improvements:
      - O(n) indexing via groupby().first() instead of O(n²) loop
      - Classification cache keyed by parser.path
      - Completeness scoring per entity
      - Auto-populate registry from parser when no external registry given
    """

    def __init__(self, registry=None):
        self._registry = registry
        self._tagger = EntityTagger()
        self._cache: dict[str, list[ClassifiedEntity]] = {}

    def classify(self, parser) -> list[ClassifiedEntity]:
        """One-shot: all schedules -> all entities classified. Cached by path."""
        cache_key = str(getattr(parser, "path", id(parser)))
        if cache_key in self._cache:
            return self._cache[cache_key]

        entities = self._classify_impl(parser)
        self._cache[cache_key] = entities
        return entities

    def _classify_impl(self, parser) -> list[ClassifiedEntity]:
        """Internal: full classification pipeline, no cache."""
        parsed = parser.parse()
        subsidiaries = parsed.subsidiaries

        sch_h = parser.extract_form("IRS5471ScheduleH")
        sch_i = parser.extract_form("IRS5471ScheduleI")
        sch_i1 = parser.extract_form("IRS5471ScheduleI1")
        sch_c = parser.extract_form("IRS5471ScheduleC")
        sch_e = parser.extract_form("IRS5471ScheduleE")
        sch_j = parser.extract_form("IRS5471ScheduleJ")
        sch_p = parser.extract_form("IRS5471ScheduleP")

        h_by_ref = self._index_by_ref(sch_h)
        i_by_ref = self._index_by_ref(sch_i)
        i1_by_ref = self._index_by_ref(sch_i1)
        c_by_ref = self._index_by_ref(sch_c)
        e_by_ref = self._index_by_ref(sch_e)
        j_by_ref = self._index_by_ref(sch_j)
        p_by_ref = self._index_by_ref(sch_p)

        entities: list[ClassifiedEntity] = []

        seen_ids: set[str] = set()
        fde_counter = 0

        for sub in subsidiaries:
            ref = sub.entity.reference_id

            if not ref:
                ref = self._synthesize_ref_id(sub)
                if not ref:
                    fde_counter += 1
                    ref = f"FDE-{fde_counter:04d}"

            if ref in seen_ids:
                continue
            seen_ids.add(ref)

            entity = self._build_entity_from_sub(
                sub, ref,
                h_by_ref, i_by_ref, i1_by_ref, c_by_ref,
                e_by_ref, j_by_ref, p_by_ref,
            )

            self._enrich_from_registry(entity)
            self._apply_tags(entity)
            self._compute_completeness(entity)
            entities.append(entity)

        return entities

    def classify_single(self, parser, ref_id: str) -> ClassifiedEntity | None:
        """Classify one entity by reference_id. Uses cache if available."""
        all_entities = self.classify(parser)
        for e in all_entities:
            if e.reference_id == ref_id:
                return e
        return None

    def invalidate_cache(self, parser=None) -> None:
        """Clear classification cache. If parser given, only that key."""
        if parser is None:
            self._cache.clear()
        else:
            key = str(getattr(parser, "path", id(parser)))
            self._cache.pop(key, None)

    def build_summary(self, entities: list[ClassifiedEntity]) -> ClassificationSummary:
        """Compute aggregate statistics from classified entities."""
        summary = ClassificationSummary(total_entities=len(entities))

        completeness_sum = 0.0

        for e in entities:
            for tag in e.tags:
                summary.by_tag[tag] = summary.by_tag.get(tag, 0) + 1

            country = e.country_code or "UNKNOWN"
            summary.by_country[country] = summary.by_country.get(country, 0) + 1

            if e.is_insurance:
                t = "insurance"
            elif e.is_dre:
                t = "dre"
            elif "dormant" in e.tags or e.dormant:
                t = "dormant"
            else:
                t = "normal"
            summary.by_type[t] = summary.by_type.get(t, 0) + 1

            for tag_a, tag_b, reason in e.contradictions:
                summary.contradictions.append((e.reference_id, tag_a, tag_b, reason))

            if "tested_income" in e.tags:
                summary.tested_income_count += 1
            if "tested_loss" in e.tags:
                summary.tested_loss_count += 1
            if "dormant" in e.tags or e.dormant:
                summary.dormant_count += 1

            completeness_sum += e.completeness_score

        summary.by_tag = dict(sorted(summary.by_tag.items(), key=lambda x: -x[1]))

        if entities:
            summary.avg_completeness = round(completeness_sum / len(entities), 3)

        return summary

    def _build_entity_from_sub(
        self,
        sub,
        ref: str,
        h_by_ref: dict,
        i_by_ref: dict,
        i1_by_ref: dict,
        c_by_ref: dict,
        e_by_ref: dict,
        j_by_ref: dict,
        p_by_ref: dict,
    ) -> ClassifiedEntity:
        """Assemble a ClassifiedEntity from a SubsidiaryReturn (full Page 1 identity)."""
        ent = sub.entity
        original_ref = ent.reference_id

        voting_pct = None
        if ent.voting_stock_pct:
            try:
                v = float(ent.voting_stock_pct)
                voting_pct = v / 100.0 if v > 1 else v
            except (TypeError, ValueError):
                pass

        ppob = ""
        doc_id = ""
        form_type = "5471"

        irs5471_form = sub.forms.get("IRS5471")
        if irs5471_form:
            ppob = str(irs5471_form.fields.get("IRS5471_PrincipalPlaceOfBusCountryCd", ""))
            doc_id = irs5471_form.document_id

        irs8858_form = sub.forms.get("IRS8858")
        if irs8858_form and not irs5471_form:
            doc_id = irs8858_form.document_id
            form_type = "8858"

        irs8865_form = sub.forms.get("IRS8865")
        if irs8865_form and not irs5471_form and not irs8858_form:
            doc_id = irs8865_form.document_id
            form_type = "8865"

        has_fde_markers = ent.tax_owner_name or ent.is_fde_us_person or ent.is_fb_cfc
        if has_fde_markers and form_type == "5471":
            form_type = "8858"

        is_dre = form_type in ("8858", "8865") and not irs5471_form

        entity = ClassifiedEntity(
            reference_id=ref,
            entity_name=ent.name,
            country_code=ent.country_code,
            functional_currency=ent.functional_currency,
            voting_stock_pct=voting_pct,
            dormant=ent.dormant,
            category_filers=list(ent.category_filers),
            ein=ent.ein,
            incorporation_date=ent.incorporation_date,
            address_line1=ent.address_line1,
            city=ent.city,
            province=ent.province,
            postal_code=ent.postal_code,
            principal_place_of_business=ppob,
            form_type=form_type,
            document_id=doc_id,
            oit_locator=self._extract_oit_locator(doc_id),
            tax_owner_name=ent.tax_owner_name,
            tax_owner_ref_id=ent.tax_owner_ref_id,
            tax_owner_ein=ent.tax_owner_ein,
            tax_owner_country=ent.tax_owner_country,
            is_fde_us_person=ent.is_fde_us_person,
            is_fb_cfc=ent.is_fb_cfc,
            is_dre=is_dre,
            sch_h=self._row_to_dict(h_by_ref.get(original_ref), "IRS5471ScheduleH_") if original_ref else {},
            sch_i=self._row_to_dict(i_by_ref.get(original_ref), "IRS5471ScheduleI_") if original_ref else {},
            sch_i1=self._row_to_dict(i1_by_ref.get(original_ref), "IRS5471ScheduleI1_") if original_ref else {},
            sch_c=self._row_to_dict(c_by_ref.get(original_ref), "IRS5471ScheduleC_") if original_ref else {},
            sch_e=self._row_to_dict(e_by_ref.get(original_ref), "IRS5471ScheduleE_") if original_ref else {},
            sch_j=self._row_to_dict(j_by_ref.get(original_ref), "IRS5471ScheduleJ_") if original_ref else {},
            sch_p=self._row_to_dict(p_by_ref.get(original_ref), "IRS5471ScheduleP_") if original_ref else {},
        )

        return entity

    def _enrich_from_registry(self, entity: ClassifiedEntity) -> None:
        """Enrich entity with metadata from the registry (if available)."""
        if self._registry is None:
            return

        match = self._registry.match_by_name(entity.entity_name)
        if match is None:
            match = self._registry.match_by_ref_id(entity.reference_id)
        if match is None:
            return

        entity.is_insurance = match.is_insurance
        entity.is_dre = match.is_dre
        if match.is_dormant:
            entity.dormant = True

    def _apply_tags(self, entity: ClassifiedEntity) -> None:
        """Run the tagger on this entity and store results."""
        entity_data = entity.to_entity_data()
        result: TagResult = self._tagger.tag(entity_data)
        entity.tags = result.tags
        entity.contradictions = result.contradictions
        entity.tag_metadata = result.evidence

    @staticmethod
    def _compute_completeness(entity: ClassifiedEntity) -> None:
        """Score how complete this entity's schedule data is (0.0–1.0)."""
        schedule_map = {
            "c": entity.sch_c,
            "e": entity.sch_e,
            "g": entity.sch_g,
            "h": entity.sch_h,
            "i": entity.sch_i,
            "i1": entity.sch_i1,
            "j": entity.sch_j,
            "p": entity.sch_p,
        }

        if entity.form_type == "8865":
            expected = _EXPECTED_SCHEDULES_8865
        elif entity.form_type == "8858":
            schedule_map["f"] = entity.sch_f
            expected = _EXPECTED_SCHEDULES_8858
        elif entity.dormant:
            expected = _EXPECTED_SCHEDULES_5471_DORMANT
        else:
            expected = _EXPECTED_SCHEDULES_5471

        present = {k for k, v in schedule_map.items() if v}
        entity.present_schedules = sorted(present)
        entity.missing_schedules = sorted(expected - present)

        if expected:
            entity.completeness_score = round(len(present & expected) / len(expected), 3)
        else:
            entity.completeness_score = 1.0

    @staticmethod
    def _synthesize_ref_id(sub) -> str:
        """Generate a stable ref ID for entities without one (8858/8865 FDEs).

        Extracts the OIT locator from the document_id as a compact, stable identifier.
        Falls back to '' if no document_id is available.
        """
        for form_key in ("IRS8858", "IRS8865", "IRS5471"):
            form = sub.forms.get(form_key)
            if form and form.document_id:
                doc_id = form.document_id
                prefix_len = len(form_key)
                locator = doc_id[prefix_len:] if len(doc_id) > prefix_len else ""
                if locator:
                    return locator
        return ""

    @staticmethod
    def _extract_oit_locator(document_id: str) -> str:
        """Extract 6-char OIT locator from documentId."""
        if not document_id or len(document_id) < 13:
            return ""
        if document_id.startswith(("IRS5471", "IRS8858", "IRS8865")):
            locator = document_id[7:13]
        elif document_id.startswith("F5471"):
            locator = document_id[9:15]
        else:
            return ""
        if locator.isalnum():
            return locator
        return ""

    @staticmethod
    def _index_by_ref(df: pd.DataFrame) -> dict[str, pd.Series]:
        """Index a schedule DataFrame by reference_id -> first row. O(n)."""
        if df.empty or "_reference_id" not in df.columns:
            return {}
        grouped = df.groupby("_reference_id", sort=False)
        return {ref: rows.iloc[0] for ref, rows in grouped if ref}

    def _row_to_dict(self, row: Optional[pd.Series], prefix: str) -> dict[str, Any]:
        """Convert a DataFrame row to a schedule dict, stripping the prefix."""
        if row is None:
            return {}
        d = {}
        for col, val in row.items():
            if isinstance(col, str) and col.startswith(prefix):
                field_name = col[len(prefix):]
                try:
                    d[field_name] = float(val)
                except (TypeError, ValueError):
                    if val is not None:
                        d[field_name] = val
        return d

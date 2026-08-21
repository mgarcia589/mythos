"""Entity Tagger — Classification engine for CFC entities.

Receives parsed entity data and returns a set of fiscal classification tags
(tested_loss, full_inclusion, subpart_f, etc.) based on deterministic rules.
Pure functions, no I/O, fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EntityData:
    """Consolidated input for the tagger — all schedule data for one entity."""

    reference_id: str
    entity_name: str = ""

    # Metadata (from EntityRegistry or Page 1)
    is_dormant: bool = False
    is_insurance: bool = False
    is_dre: bool = False
    voting_stock_pct: float | None = None

    # Schedule C (Income Statement) — field_name: amount
    sch_c: dict[str, float] = field(default_factory=dict)

    # Schedule H (Current E&P)
    sch_h: dict[str, float] = field(default_factory=dict)

    # Schedule I (Subpart F Summary)
    sch_i: dict[str, float] = field(default_factory=dict)

    # Schedule I-1 (GILTI)
    sch_i1: dict[str, float] = field(default_factory=dict)

    # Schedule J (E&P pools) — basket: {field: amount}
    sch_j: dict[str, dict[str, float]] = field(default_factory=dict)

    # Schedule G (Other Information — indicators)
    sch_g: dict[str, Any] = field(default_factory=dict)

    # Schedule E (Foreign Taxes)
    sch_e: dict[str, float] = field(default_factory=dict)

    # Schedule P (PTEP)
    sch_p: dict[str, float] = field(default_factory=dict)

    def get(self, schedule: str, field_name: str, default: float = 0.0) -> float:
        """Safe accessor — EntityData.get("i1", "TestedIncomeAmt") -> float."""
        source = getattr(self, f"sch_{schedule}", None)
        if source is None:
            return default
        if isinstance(source, dict):
            val = source.get(field_name, default)
            if isinstance(val, dict):
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default
        return default

    def has_schedule(self, schedule: str) -> bool:
        """Check if entity has any data for a given schedule."""
        source = getattr(self, f"sch_{schedule}", None)
        if source is None:
            return False
        return bool(source)


@dataclass
class TagRule:
    """A single tagging rule — evaluates one condition."""

    tag_name: str
    description: str
    evaluate: Callable[[EntityData], bool]
    category: str = "classification"
    priority: int = 0
    xml_fields: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class TagResult:
    """Output of the tagger for one entity."""

    reference_id: str
    entity_name: str
    tags: set[str] = field(default_factory=set)
    contradictions: list[tuple[str, str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, dict[str, float]] = field(default_factory=dict)


# Contradiction pairs — (tag_a, tag_b, reason)
CONTRADICTIONS: list[tuple[str, str, str]] = [
    ("tested_income", "tested_loss", "Cannot have both tested income and tested loss"),
]


class EntityTagger:
    """Applies all registered rules to classify entities."""

    def __init__(self, rules: list[TagRule] | None = None):
        from lab.core.tagging_rules import DEFAULT_RULES
        self.rules = rules if rules is not None else DEFAULT_RULES

    def tag(self, entity: EntityData) -> TagResult:
        """Tag a single entity — returns TagResult with tags + contradictions + evidence."""
        result = TagResult(
            reference_id=entity.reference_id,
            entity_name=entity.entity_name,
        )

        sorted_rules = sorted(self.rules, key=lambda r: -r.priority)

        for rule in sorted_rules:
            try:
                if rule.evaluate(entity):
                    result.tags.add(rule.tag_name)
                    if rule.xml_fields:
                        ev = {}
                        for schedule, field_name in rule.xml_fields:
                            val = entity.get(schedule, field_name)
                            if val != 0.0:
                                ev[f"{schedule}.{field_name}"] = val
                        if ev:
                            result.evidence[rule.tag_name] = ev
            except Exception:
                pass

        result.contradictions = self._detect_contradictions(result.tags)
        return result

    def tag_batch(self, entities: list[EntityData]) -> list[TagResult]:
        """Tag multiple entities — returns list of TagResult."""
        return [self.tag(e) for e in entities]

    def summary(self, results: list[TagResult]) -> dict[str, int]:
        """Count entities per tag — useful for dashboards."""
        counts: dict[str, int] = {}
        for r in results:
            for tag in r.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def _detect_contradictions(self, tags: set[str]) -> list[tuple[str, str, str]]:
        """Check for invalid tag combinations."""
        found = []
        for tag_a, tag_b, reason in CONTRADICTIONS:
            if tag_a in tags and tag_b in tags:
                found.append((tag_a, tag_b, reason))
        return found

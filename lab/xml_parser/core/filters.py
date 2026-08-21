"""Granular export filtering — pre-processing layer between engine and exporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lab.xml_parser.core.models import ReviewReport, RolloverReport


@dataclass(frozen=True)
class FilterSpec:
    """Immutable filter specification.

    Semantics:
    - None/empty = no constraint (include everything)
    - Within a dimension: OR (E001 or E005)
    - Between dimensions: AND (entity=E001 AND check=ROL-*)
    """

    entity_codes: frozenset[str] = field(default_factory=frozenset)
    entity_names: frozenset[str] = field(default_factory=frozenset)
    check_ids: frozenset[str] = field(default_factory=frozenset)
    check_categories: frozenset[str] = field(default_factory=frozenset)
    report_keys: frozenset[str] = field(default_factory=frozenset)

    @property
    def has_entity_filter(self) -> bool:
        return bool(self.entity_codes or self.entity_names)

    @property
    def has_check_filter(self) -> bool:
        return bool(self.check_ids or self.check_categories)

    @property
    def has_report_filter(self) -> bool:
        return bool(self.report_keys)

    @property
    def is_empty(self) -> bool:
        return not (self.has_entity_filter or self.has_check_filter or self.has_report_filter)

    def matches_entity(self, code: str, name: str) -> bool:
        if not self.has_entity_filter:
            return True
        if self.entity_codes and code in self.entity_codes:
            return True
        if self.entity_names:
            name_lower = name.lower()
            if any(n.lower() in name_lower for n in self.entity_names):
                return True
        return False

    def matches_check(self, check_id: str, category: str) -> bool:
        if not self.has_check_filter:
            return True
        if self.check_ids and check_id in self.check_ids:
            return True
        if self.check_categories and category.lower() in self.check_categories:
            return True
        return False

    def matches_report_key(self, key: str) -> bool:
        if not self.has_report_filter:
            return True
        key_lower = key.lower()
        return any(
            k.lower() in key_lower or key_lower in k.lower()
            for k in self.report_keys
        )


def filter_review_report(report: ReviewReport, spec: FilterSpec) -> ReviewReport:
    """Return a new ReviewReport containing only findings matching the spec."""
    from lab.xml_parser.core.models import ReviewReport as RR

    if spec.is_empty:
        return report

    filtered = [
        f for f in report.findings
        if spec.matches_entity(f.entity_code, f.entity_name)
        and spec.matches_check(f.check_id, f.category)
    ]

    new_report = RR(
        client_name=report.client_name,
        tax_year=report.tax_year,
        entity_count=report.entity_count,
        findings=filtered,
        run_timestamp=report.run_timestamp,
    )
    new_report.compute_summary()
    return new_report


def filter_rollover_reports(
    reports: dict[str, RolloverReport],
    spec: FilterSpec,
) -> dict[str, RolloverReport]:
    """Return a filtered dict of RolloverReports."""
    from lab.xml_parser.core.models import RolloverReport as RR

    if spec.is_empty:
        return reports

    result = {}
    for key, report in reports.items():
        if not spec.matches_report_key(key):
            continue

        if spec.has_entity_filter:
            filtered_items = [
                item for item in report.items
                if spec.matches_entity(item.reference_id, item.entity_name)
            ]
            result[key] = RR(title=report.title, items=filtered_items)
        else:
            result[key] = report

    return result


def build_filter_spec(
    entities: list[str] | None = None,
    checks: list[str] | None = None,
    categories: list[str] | None = None,
) -> FilterSpec:
    """Build FilterSpec from CLI-style arguments.

    Classifies entity args as codes vs names by format heuristic.
    Check args with "-" are treated as check IDs; others as report keys.
    """
    entity_codes: set[str] = set()
    entity_names: set[str] = set()

    if entities:
        for e in entities:
            if len(e) <= 8 and e[0].isalpha() and any(c.isdigit() for c in e):
                entity_codes.add(e)
            else:
                entity_names.add(e)

    check_ids: set[str] = set()
    report_keys: set[str] = set()

    CATEGORY_TO_REPORTS = {
        "rollover": {"Sch F Rollover", "Sch J Rollover (GEN)", "Sch J Rollover (PAS)", "Page 1 Rollover"},
        "flow": set(),
        "completeness": set(),
        "reasonableness": set(),
        "movement": {"E&P Movement"},
        "gilti": {"GILTI Comparison"},
        "entity": {"Entity Changes"},
        "schedule_g": {"Sch G Indicators"},
    }

    if checks:
        for c in checks:
            if "-" in c and len(c) <= 8 and c[:3].isalpha():
                check_ids.add(c.upper())
            else:
                report_keys.add(c)

    check_categories: set[str] = set()
    if categories:
        for cat in categories:
            cat_lower = cat.lower()
            check_categories.add(cat_lower)
            if cat_lower in CATEGORY_TO_REPORTS:
                report_keys.update(CATEGORY_TO_REPORTS[cat_lower])

    return FilterSpec(
        entity_codes=frozenset(entity_codes),
        entity_names=frozenset(entity_names),
        check_ids=frozenset(check_ids),
        check_categories=frozenset(check_categories),
        report_keys=frozenset(report_keys),
    )

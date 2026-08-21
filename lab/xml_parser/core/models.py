"""Core data models — zero heavy dependencies (no pandas/lxml/numpy)."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Finding:
    check_id: str
    severity: str
    category: str
    entity_code: str
    entity_name: str
    description: str
    expected: str | None = None
    actual: str | None = None
    delta: float | None = None
    context: str | None = None


@dataclass
class ReviewReport:
    client_name: str = ""
    tax_year: str = ""
    entity_count: int = 0
    form_type: str = "5471"
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    run_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def high_severity(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "HIGH"]

    def by_entity(self, code: str) -> list[Finding]:
        return [f for f in self.findings if f.entity_code == code]

    def by_category(self, cat: str) -> list[Finding]:
        return [f for f in self.findings if f.category == cat]

    def by_check_id(self, check_id: str) -> list[Finding]:
        return [f for f in self.findings if f.check_id == check_id]

    def by_check_ids(self, ids: set[str]) -> list[Finding]:
        return [f for f in self.findings if f.check_id in ids]

    def to_dataframe(self):
        import pandas as pd

        if not self.findings:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "check_id": f.check_id,
                "severity": f.severity,
                "category": f.category,
                "entity_code": f.entity_code,
                "entity_name": f.entity_name,
                "description": f.description,
                "expected": f.expected,
                "actual": f.actual,
                "delta": f.delta,
                "context": f.context,
            }
            for f in self.findings
        ])

    def compute_summary(self):
        self.summary = {
            "total_findings": len(self.findings),
            "by_severity": {
                "HIGH": sum(1 for f in self.findings if f.severity == "HIGH"),
                "MEDIUM": sum(1 for f in self.findings if f.severity == "MEDIUM"),
                "LOW": sum(1 for f in self.findings if f.severity == "LOW"),
            },
            "by_category": {},
            "entities_with_findings": len(set(f.entity_code for f in self.findings)),
            "clean_entities": self.entity_count - len(set(f.entity_code for f in self.findings)),
        }
        for f in self.findings:
            cat = f.category
            if cat not in self.summary["by_category"]:
                self.summary["by_category"][cat] = 0
            self.summary["by_category"][cat] += 1


@dataclass
class RolloverItem:
    entity_name: str
    reference_id: str
    field_description: str
    line: str
    py_value: str
    cy_value: str
    difference: float = 0.0
    passes: bool = True


@dataclass
class RolloverReport:
    title: str
    items: list[RolloverItem] = field(default_factory=list)

    @property
    def total_checks(self) -> int:
        return len(self.items)

    @property
    def passed(self) -> int:
        return sum(1 for i in self.items if i.passes)

    @property
    def failed(self) -> int:
        return self.total_checks - self.passed

    @property
    def entities_with_issues(self) -> set:
        return {i.entity_name for i in self.items if not i.passes}

    @property
    def summary(self) -> str:
        return f"{self.title}: {self.passed}/{self.total_checks} PASS, {self.failed} differences ({len(self.entities_with_issues)} entities)"

    def filter_entities(self, codes: set[str] | None = None, names: set[str] | None = None) -> "RolloverReport":
        """Return a new RolloverReport with items filtered to matching entities."""
        if not codes and not names:
            return self
        filtered = []
        for item in self.items:
            if codes and item.reference_id in codes:
                filtered.append(item)
            elif names:
                name_lower = item.entity_name.lower()
                if any(n.lower() in name_lower for n in names):
                    filtered.append(item)
        return RolloverReport(title=self.title, items=filtered)

"""Domain models for PDF Validator — UI-ready result types.

These models provide structured results that a UI layer can consume
without coupling to the internal implementation.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol


@dataclass
class ExecutionResult:
    """Structured result from a PDF validation run.

    Designed for consumption by CLI, API, or UI layers.
    """
    success: bool
    status: str  # "completed", "completed_with_warnings", "failed"
    message: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, int | float | str] = field(default_factory=dict)
    output_files: list[Path] = field(default_factory=list)
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def duration_display(self) -> str:
        d = self.duration_seconds
        if d is None:
            return "N/A"
        if d < 1:
            return f"{d * 1000:.0f}ms"
        return f"{d:.1f}s"


class ProgressCallback(Protocol):
    """Protocol for progress reporting.

    Implement this to receive progress updates in a UI:
      - stage: current pipeline stage name
      - progress: 0.0 to 1.0
      - message: human-readable status message
    """

    def __call__(self, stage: str, progress: float, message: str) -> None: ...


class NullProgress:
    """No-op progress callback for non-interactive use."""

    def __call__(self, stage: str, progress: float, message: str) -> None:
        pass


@dataclass
class ValidationSummary:
    """Lightweight summary for dashboard/list views."""
    execution_id: str
    schedule: str
    pdf_source: str
    xml_source: str
    total_comparisons: int
    ok_count: int
    phantom_count: int
    missing_count: int
    mismatch_count: int
    entities_checked: int
    duration_seconds: Optional[float]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_issues(self) -> bool:
        return (self.phantom_count + self.missing_count + self.mismatch_count) > 0

    @property
    def status_emoji(self) -> str:
        if self.phantom_count > 0:
            return "CRITICAL"
        if self.mismatch_count > 0:
            return "WARNING"
        return "OK"


# ─── Smart Router models ─────────────────────────────────────────────────────


@dataclass
class EntityBlock:
    """All pages belonging to one entity in a batch PDF."""
    reference_id: str
    entity_name: str
    form_type: str = "5471"
    country: str = ""
    schedules: dict[str, list[int]] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return sum(len(pages) for pages in self.schedules.values())

    @property
    def schedule_list(self) -> list[str]:
        return sorted(self.schedules.keys())


@dataclass
class PageMap:
    """Map of entities and their schedule pages within a batch PDF."""
    total_pages: int
    entities: dict[str, EntityBlock] = field(default_factory=dict)
    skipped_pages: list[int] = field(default_factory=list)
    unrecognized_pages: list[int] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def classified_pages(self) -> int:
        return self.total_pages - len(self.unrecognized_pages) - len(self.skipped_pages)


@dataclass
class EntityCompleteness:
    """Cross-check: XML entities vs PDF entities."""
    xml_entities: set[str] = field(default_factory=set)
    pdf_entities: set[str] = field(default_factory=set)

    @property
    def missing_from_pdf(self) -> set[str]:
        return self.xml_entities - self.pdf_entities

    @property
    def extra_in_pdf(self) -> set[str]:
        return self.pdf_entities - self.xml_entities

    @property
    def matched(self) -> set[str]:
        return self.xml_entities & self.pdf_entities

    @property
    def is_complete(self) -> bool:
        return len(self.missing_from_pdf) == 0


@dataclass
class BatchValidationResult:
    """Result of validating all schedules in a batch PDF."""
    pdf_source: str
    xml_source: str
    page_map: Optional[PageMap] = None
    schedule_reports: dict = field(default_factory=dict)
    entity_completeness: Optional[EntityCompleteness] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def total_discrepancies(self) -> int:
        return sum(
            len(r.discrepancies)
            for r in self.schedule_reports.values()
        )

    @property
    def total_phantoms(self) -> int:
        return sum(r.phantom_count for r in self.schedule_reports.values())

    @property
    def total_comparisons(self) -> int:
        return sum(r.total_comparisons for r in self.schedule_reports.values())

    @property
    def has_phantoms(self) -> bool:
        return self.total_phantoms > 0

    @property
    def summary(self) -> str:
        schedules = len(self.schedule_reports)
        entities = self.page_map.entity_count if self.page_map else 0
        comps = self.total_comparisons
        discreps = self.total_discrepancies
        phantoms = self.total_phantoms
        if discreps == 0:
            return (f"Batch validation: {schedules} schedules, {entities} entities, "
                    f"{comps} comparisons — ALL OK")
        return (f"Batch validation: {schedules} schedules, {entities} entities, "
                f"{comps} comparisons | {discreps} discrepancies "
                f"({phantoms} phantoms)")

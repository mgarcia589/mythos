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

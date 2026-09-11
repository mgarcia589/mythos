"""Mythos Error Hierarchy — single authoritative exception tree.

Design:
- Single inheritance tree rooted at MythosError
- Each error carries optional structured context (entity, schedule, field)
- Severity level enables downstream routing (log vs alert vs halt)
- User-facing message separated from technical detail
- .to_log_entry() produces structured dict for JSON logging

Consolidates the former dual hierarchy (CerebroError + MythosError) into one.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ErrorContext:
    """Structured context attached to errors for debugging and log correlation."""
    entity_ref: str = ""
    schedule: str = ""
    field_name: str = ""
    source_file: str = ""
    page_number: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in {
            "entity_ref": self.entity_ref,
            "schedule": self.schedule,
            "field_name": self.field_name,
            "source_file": self.source_file,
            "page_number": self.page_number,
        }.items() if v}
        if self.extra:
            d.update(self.extra)
        return d


class MythosError(Exception):
    """Base exception for all Mythos errors."""

    severity: Severity = Severity.MEDIUM
    user_message: str = "An error occurred during processing."

    def __init__(self, message: str = "", *,
                 path: Any = None,
                 reason: str = "",
                 context: Optional[ErrorContext] = None,
                 severity: Optional[Severity] = None,
                 user_message: Optional[str] = None):
        if path and reason:
            full = f"Failed to process {path}: {reason}"
        elif path:
            full = f"Failed to process {path}"
        elif message:
            full = message
        else:
            full = reason or self.user_message
        super().__init__(full)
        self.technical_message = full
        self.path = path
        self.reason = reason
        self.context = context or ErrorContext()
        if severity is not None:
            self.severity = severity
        if user_message is not None:
            self.user_message = user_message

    def to_log_entry(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "severity": self.severity.value,
            "message": self.technical_message,
            "user_message": self.user_message,
            "context": self.context.as_dict(),
        }


# ── PARSING ──────────────────────────────────────────────────────────────────

class ParseError(MythosError):
    """Raised when XML/PDF/workbook parsing fails."""
    severity = Severity.HIGH
    user_message = "Failed to parse the input file."

    def __init__(self, path=None, reason="", **kwargs):
        super().__init__(path=path, reason=reason, **kwargs)


class XMLParseError(ParseError):
    """XML-specific: missing element, bad namespace, malformed structure."""
    user_message = "The XML file has an unexpected structure."


class PDFExtractionError(ParseError):
    """PDF table detection failed, page not recognized, no data found."""
    user_message = "Could not extract data from the PDF."


class WorkbookParseError(ParseError):
    """Excel/workbook reading failure: missing sheet, bad column."""
    user_message = "The workbook has an unexpected format."


# ── VALIDATION ───────────────────────────────────────────────────────────────

class ValidationError(MythosError):
    """Raised when data fails a business rule or integrity constraint."""
    severity = Severity.MEDIUM
    user_message = "Data validation failed."

    def __init__(self, field_name=None, value=None, reason="", **kwargs):
        msg = ""
        if field_name is not None:
            msg = f"Validation failed for {field_name}={value}: {reason}"
        super().__init__(message=msg, reason=reason, **kwargs)
        self.field = field_name
        self.value = value


class MissingFieldError(ValidationError):
    user_message = "A required field is missing from the data."


class InconsistencyError(ValidationError):
    severity = Severity.HIGH
    user_message = "Inconsistent data detected between schedules."


# ── RECONCILIATION ───────────────────────────────────────────────────────────

class ReconciliationError(MythosError):
    """Discrepancy between two data sources exceeds tolerance."""
    severity = Severity.MEDIUM
    user_message = "A reconciliation discrepancy was found."


class PhantomValueError(ReconciliationError):
    user_message = "Value found in one source but missing in the other."


class MaterialMismatchError(ReconciliationError):
    severity = Severity.HIGH
    user_message = "Material difference detected between sources."


# ── EXPORT ───────────────────────────────────────────────────────────────────

class ExportError(MythosError):
    """Raised when report export fails."""
    severity = Severity.MEDIUM
    user_message = "Report export failed."

    def __init__(self, format=None, path=None, reason="", **kwargs):
        msg = ""
        if format and path:
            msg = f"Export to {format} failed at {path}: {reason}"
        super().__init__(message=msg, path=path, reason=reason, **kwargs)
        self.format = format


# ── CONFIG ───────────────────────────────────────────────────────────────────

class ConfigError(MythosError):
    """Missing dependency, bad config, environment issue."""
    severity = Severity.CRITICAL
    user_message = "A required dependency or configuration is missing."


class DependencyMissingError(ConfigError):
    user_message = "A required library is not installed."

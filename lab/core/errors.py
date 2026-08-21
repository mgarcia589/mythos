"""Cerebro Error Hierarchy — Structured exceptions for the data pipeline.

Design decisions:
- Single inheritance tree rooted at CerebroError (catch-all without catching stdlib errors)
- Each error carries structured context (entity, schedule, field) for log correlation
- Severity level enables downstream routing (log vs alert vs halt)
- User-facing message separated from technical detail (never leak internals)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(Enum):
    LOW = "low"          # Recoverable, logged, execution continues
    MEDIUM = "medium"    # Degraded result, flagged in report
    HIGH = "high"        # Halts current entity/schedule, continues batch
    CRITICAL = "critical"  # Halts entire pipeline


@dataclass(frozen=True)
class ErrorContext:
    """Structured context attached to every error for debugging."""
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


class CerebroError(Exception):
    """Base for all Cerebro pipeline errors.

    Never raise bare Exception — always use a subclass so callers can
    discriminate between "our" errors and unexpected stdlib failures.
    """

    severity: Severity = Severity.MEDIUM
    user_message: str = "An error occurred during processing."

    def __init__(self, message: str, *,
                 context: Optional[ErrorContext] = None,
                 severity: Optional[Severity] = None,
                 user_message: Optional[str] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message)
        self.technical_message = message
        self.context = context or ErrorContext()
        if severity is not None:
            self.severity = severity
        if user_message is not None:
            self.user_message = user_message
        self.__cause__ = cause

    def to_log_entry(self) -> dict[str, Any]:
        """Structured dict ready for JSON logging or monitoring ingest."""
        return {
            "error_type": type(self).__name__,
            "severity": self.severity.value,
            "message": self.technical_message,
            "user_message": self.user_message,
            "context": self.context.as_dict(),
            "cause": f"{type(self.__cause__).__name__}: {self.__cause__}" if self.__cause__ else None,
        }


# =========================================================================
# 1. DATA SOURCE ERRORS — problems reading input files
# =========================================================================

class DataSourceError(CerebroError):
    """File not found, unreadable, corrupt, or wrong format."""
    severity = Severity.HIGH
    user_message = "Could not read the input file."


class FileNotFoundError_(DataSourceError):
    """Specific file missing (avoids shadowing builtins in catch blocks)."""
    user_message = "The specified file does not exist."


class FileFormatError(DataSourceError):
    """File exists but content is not the expected format (bad XML, corrupt PDF)."""
    user_message = "The file format is invalid or corrupted."


# =========================================================================
# 2. PARSING ERRORS — problems extracting structured data
# =========================================================================

class ParseError(CerebroError):
    """Base for extraction/parsing failures."""
    severity = Severity.MEDIUM
    user_message = "Failed to extract data from the source."


class XMLParseError(ParseError):
    """XML-specific: missing element, bad namespace, malformed structure."""
    user_message = "The XML file has an unexpected structure."


class PDFExtractionError(ParseError):
    """PDF table detection failed, page not recognized, no data found."""
    user_message = "Could not extract data from the PDF."


class WorkbookParseError(ParseError):
    """Excel/workbook reading failure: missing sheet, bad column, type mismatch."""
    user_message = "The workbook has an unexpected format."


# =========================================================================
# 3. VALIDATION ERRORS — data exists but fails business rules
# =========================================================================

class ValidationError(CerebroError):
    """Data violates a business rule or integrity constraint."""
    severity = Severity.MEDIUM
    user_message = "Data validation failed."


class MissingFieldError(ValidationError):
    """Required field absent (e.g., entity without reference_id)."""
    user_message = "A required field is missing from the data."


class ValueOutOfRangeError(ValidationError):
    """Numeric value outside acceptable bounds (e.g., percentage > 100)."""
    user_message = "A value is outside the expected range."


class InconsistencyError(ValidationError):
    """Cross-field or cross-schedule contradiction detected."""
    severity = Severity.HIGH
    user_message = "Inconsistent data detected between schedules."


# =========================================================================
# 4. RECONCILIATION ERRORS — mismatches between sources
# =========================================================================

class ReconciliationError(CerebroError):
    """Discrepancy between two data sources exceeds tolerance."""
    severity = Severity.MEDIUM
    user_message = "A reconciliation discrepancy was found."


class PhantomValueError(ReconciliationError):
    """Value in source A but not in source B."""
    user_message = "Value found in one source but missing in the other."


class MaterialMismatchError(ReconciliationError):
    """Both sources have the value but delta exceeds materiality threshold."""
    severity = Severity.HIGH
    user_message = "Material difference detected between sources."


# =========================================================================
# 5. CONFIGURATION / ENVIRONMENT ERRORS
# =========================================================================

class ConfigError(CerebroError):
    """Missing dependency, bad config, environment issue."""
    severity = Severity.CRITICAL
    user_message = "A required dependency or configuration is missing."


class DependencyMissingError(ConfigError):
    """Optional dependency (pdfplumber, openpyxl) not installed."""
    user_message = "A required library is not installed."

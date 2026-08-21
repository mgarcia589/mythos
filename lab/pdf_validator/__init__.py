"""PDF Validator — Visual Candado de Reconciliación.

Extracts data from OIT-generated PDFs and reconciles against XML,
acting as an independent second check. Resolves the gap where XML
may not reflect OIT's current state.

VALIDATED = XML_Rollover PASS  +  PDF_vs_XML PASS
"""

from lab.pdf_validator.validator import PDFValidator
from lab.pdf_validator.reconciler import (
    PDFReconciler,
    PDFValidationReport,
    PDFDiscrepancy,
    ALL_POOLS,
    POOL_LOOKUP,
    SKIP_POOLS,
)
from lab.pdf_validator.models import ExecutionResult, ProgressCallback, ValidationSummary
from lab.pdf_validator.config import PDFValidatorConfig
from lab.pdf_validator.scanner import PDFScanner, ScanResult, EntityInfo
from lab.pdf_validator.comparator import PDFComparator, PDFComparisonReport, ComparisonItem

__all__ = [
    "PDFValidator",
    "PDFReconciler",
    "PDFValidationReport",
    "PDFDiscrepancy",
    "ExecutionResult",
    "ProgressCallback",
    "ValidationSummary",
    "PDFValidatorConfig",
    "PDFScanner",
    "ScanResult",
    "EntityInfo",
    "PDFComparator",
    "PDFComparisonReport",
    "ComparisonItem",
    "ALL_POOLS",
    "POOL_LOOKUP",
    "SKIP_POOLS",
]

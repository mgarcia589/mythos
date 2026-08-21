"""PDFValidator — High-level API for PDF vs XML validation.

Usage:
    from lab.pdf_validator import PDFValidator

    validator = PDFValidator(
        pdf_path="path/to/schedule-batch.pdf",
        xml_path="path/to/return.xml",
        schedule="J",
    )
    report = validator.validate()
    validator.to_excel("output/pdf-validation.xlsx")

    # With progress callback (for UI integration):
    result = validator.run(progress=my_callback)
    print(result.status, result.metrics)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from lab.pdf_validator.extractor import PDFExtractor
from lab.pdf_validator.models import ExecutionResult, NullProgress, ProgressCallback, ValidationSummary
from lab.pdf_validator.reconciler import PDFReconciler, PDFValidationReport
from lab.pdf_validator.report import write_report_excel

logger = logging.getLogger(__name__)


class PDFValidator:
    """Main entry point for PDF vs XML validation.

    Orchestrates: PDF extraction -> reconciliation -> report generation.
    """

    def __init__(self, pdf_path: str | Path, xml_path: str | Path,
                 schedule: str = "J", xml_field: str = "BeginningYearBalanceAmt",
                 tolerance: float = 10.0):
        """
        Args:
            pdf_path: Path to OIT-generated PDF
            xml_path: Path to XML e-file for comparison
            schedule: Which schedule to validate ("J", "F", "H", "I1")
            xml_field: XML field to compare against (for Sch J: BeginningYearBalanceAmt)
            tolerance: Materiality threshold in dollars (default: $10)
        """
        self.pdf_path = Path(pdf_path)
        self.xml_path = Path(xml_path)
        self.schedule = schedule.upper()
        self.xml_field = xml_field
        self.tolerance = tolerance
        self._report: Optional[PDFValidationReport] = None

    def validate(self) -> PDFValidationReport:
        """Run full validation pipeline: extract PDF -> reconcile against XML.

        Returns:
            PDFValidationReport with all comparisons and discrepancies.

        Raises:
            FileNotFoundError: If PDF or XML file doesn't exist.
            ImportError: If pdfplumber is not installed.
        """
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        if not self.xml_path.exists():
            raise FileNotFoundError(f"XML not found: {self.xml_path}")

        logger.info("Starting PDF validation: %s vs %s", self.pdf_path.name, self.xml_path.name)

        # Step 1: Extract structured data from PDF
        extractor = PDFExtractor(self.pdf_path, schedule=self.schedule)
        pdf_data = extractor.extract()
        pdf_data.attrs["source"] = self.pdf_path.name

        entity_count = pdf_data["reference_id"].nunique() if not pdf_data.empty else 0
        logger.info("Extracted %d records from %d entities", len(pdf_data), entity_count)

        # Step 2: Reconcile against XML
        reconciler = PDFReconciler(
            pdf_data=pdf_data,
            xml_path=self.xml_path,
            schedule=self.schedule,
            xml_field=self.xml_field,
            tolerance=self.tolerance,
        )
        self._report = reconciler.reconcile()

        logger.info("Reconciliation complete: %s", self._report.summary)
        return self._report

    def to_excel(self, output_path: str | Path, **kwargs) -> Path:
        """Generate Excel report from last validation run.

        Must call validate() first.

        Returns:
            Path to the generated Excel file.
        """
        if self._report is None:
            raise RuntimeError("Call validate() before to_excel()")
        return write_report_excel(self._report, output_path, **kwargs)

    def run(self, output_path: Optional[str | Path] = None,
            progress: Optional[ProgressCallback] = None,
            **excel_kwargs) -> ExecutionResult:
        """Execute the full validation pipeline with structured result.

        This is the UI-friendly entry point that returns an ExecutionResult
        with metrics, warnings, and output file paths.

        Args:
            output_path: If provided, automatically generates Excel report.
            progress: Callback for reporting progress to UI.
            **excel_kwargs: Passed to write_report_excel (client_name, engagement, etc.)

        Returns:
            ExecutionResult with success status, metrics, warnings, and output files.
        """
        cb = progress or NullProgress()
        started = datetime.now()
        warnings: list[str] = []
        errors: list[str] = []
        output_files: list[Path] = []

        try:
            # Step 1: Validate inputs
            cb("validation", 0.0, "Checking input files...")
            if not self.pdf_path.exists():
                return ExecutionResult(
                    success=False, status="failed",
                    message=f"PDF file not found: {self.pdf_path}",
                    errors=[f"FileNotFoundError: {self.pdf_path}"],
                    started_at=started, completed_at=datetime.now(),
                )
            if not self.xml_path.exists():
                return ExecutionResult(
                    success=False, status="failed",
                    message=f"XML file not found: {self.xml_path}",
                    errors=[f"FileNotFoundError: {self.xml_path}"],
                    started_at=started, completed_at=datetime.now(),
                )

            # Step 2: Extract PDF
            cb("extraction", 0.1, f"Extracting data from {self.pdf_path.name}...")
            extractor = PDFExtractor(self.pdf_path, schedule=self.schedule)
            pdf_data = extractor.extract()
            pdf_data.attrs["source"] = self.pdf_path.name

            extraction_metrics = extractor.metrics
            warnings.extend(extraction_metrics.warnings)

            entity_count = pdf_data["reference_id"].nunique() if not pdf_data.empty else 0
            cb("extraction", 0.4, f"Extracted {len(pdf_data)} records from {entity_count} entities")

            if pdf_data.empty:
                return ExecutionResult(
                    success=False, status="failed",
                    message="No data extracted from PDF. Check file format.",
                    warnings=warnings, errors=["Empty extraction result"],
                    started_at=started, completed_at=datetime.now(),
                )

            # Step 3: Reconcile
            cb("reconciliation", 0.5, "Reconciling PDF vs XML...")
            reconciler = PDFReconciler(
                pdf_data=pdf_data,
                xml_path=self.xml_path,
                schedule=self.schedule,
                xml_field=self.xml_field,
                tolerance=self.tolerance,
            )
            self._report = reconciler.reconcile()
            cb("reconciliation", 0.8, f"Found {len(self._report.discrepancies)} discrepancies")

            # Step 4: Export (optional)
            if output_path:
                cb("export", 0.85, "Generating Excel report...")
                out = write_report_excel(self._report, output_path, **excel_kwargs)
                output_files.append(out)
                cb("export", 0.95, f"Report saved: {out.name}")

            # Build result
            cb("complete", 1.0, "Validation complete")
            completed = datetime.now()

            has_issues = len(self._report.discrepancies) > 0
            status = "completed_with_warnings" if has_issues else "completed"
            message = self._report.summary

            return ExecutionResult(
                success=True,
                status=status,
                message=message,
                warnings=warnings,
                errors=errors,
                metrics={
                    "total_comparisons": self._report.total_comparisons,
                    "ok_count": self._report.ok_count,
                    "phantom_count": self._report.phantom_count,
                    "missing_count": self._report.missing_count,
                    "mismatch_count": self._report.mismatch_count,
                    "entities_checked": self._report.entities_checked,
                    "entities_with_issues": len(self._report.entities_with_issues),
                    "records_extracted": len(pdf_data),
                    "pages_processed": extraction_metrics.pages_processed,
                    "tolerance": self.tolerance,
                },
                output_files=output_files,
                started_at=started,
                completed_at=completed,
            )

        except Exception as e:
            logger.exception("Validation failed")
            return ExecutionResult(
                success=False, status="failed",
                message=f"Validation failed: {e}",
                warnings=warnings,
                errors=[f"{type(e).__name__}: {e}"],
                started_at=started, completed_at=datetime.now(),
            )

    def get_summary(self) -> Optional[ValidationSummary]:
        """Get lightweight summary from last validation (for dashboard views)."""
        if self._report is None:
            return None
        return ValidationSummary(
            execution_id="",
            schedule=self._report.schedule,
            pdf_source=self._report.pdf_source,
            xml_source=self._report.xml_source,
            total_comparisons=self._report.total_comparisons,
            ok_count=self._report.ok_count,
            phantom_count=self._report.phantom_count,
            missing_count=self._report.missing_count,
            mismatch_count=self._report.mismatch_count,
            entities_checked=self._report.entities_checked,
            duration_seconds=None,
        )

    @property
    def report(self) -> Optional[PDFValidationReport]:
        """Access the last validation report (None if validate() not called)."""
        return self._report

    @staticmethod
    def full_validation(pdf_dir: str | Path, xml_path: str | Path,
                        output_dir: Optional[str | Path] = None,
                        tolerance: float = 10.0) -> dict[str, PDFValidationReport]:
        """Validate all PDF exports in a directory against one XML.

        Looks for PDFs named like: schj-*.pdf, schf-*.pdf, etc.
        Returns dict of schedule -> report.
        """
        pdf_dir = Path(pdf_dir)
        xml_path = Path(xml_path)
        results = {}

        schedule_patterns = {
            "A": ["page1", "scha", "schedule-a", "schedule_a", "sch-a", "5471-page1"],
            "B": ["schb", "schedule-b", "schedule_b", "sch-b", "shareholders"],
            "C": ["schc", "schedule-c", "schedule_c", "sch-c", "income-stmt"],
            "E": ["sche", "schedule-e", "schedule_e", "sch-e", "foreign-tax"],
            "F": ["schf", "schedule-f", "schedule_f", "sch-f"],
            "G": ["schg", "schedule-g", "schedule_g", "sch-g"],
            "H": ["schh", "schedule-h", "schedule_h", "sch-h"],
            "I": ["schi-", "schedule-i-", "schedule_i_", "sch-i-", "shareholder-income"],
            "I1": ["schi1", "schedule-i1", "schedule_i1", "sch-i1", "gilti"],
            "J": ["schj", "schedule-j", "schedule_j", "sch-j"],
            "P": ["schp", "schedule-p", "schedule_p", "sch-p", "ptep"],
            "R": ["schr", "schedule-r", "schedule_r", "sch-r", "distribution"],
        }

        for schedule, patterns in schedule_patterns.items():
            for pdf_file in sorted(pdf_dir.glob("*.pdf")):
                name_lower = pdf_file.stem.lower()
                if any(p in name_lower for p in patterns):
                    validator = PDFValidator(
                        pdf_file, xml_path, schedule=schedule, tolerance=tolerance
                    )
                    try:
                        report = validator.validate()
                        results[schedule] = report
                        if output_dir:
                            out = Path(output_dir) / f"pdf-validation-sch{schedule.lower()}.xlsx"
                            validator.to_excel(out)
                    except Exception as e:
                        logger.warning("Failed to validate %s: %s", pdf_file.name, e)
                    break

        return results

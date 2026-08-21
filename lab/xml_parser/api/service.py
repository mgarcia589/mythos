"""Mythos Service Layer — single entry point for all operations.

This module provides a clean boundary between business logic and presentation.
CLI, dashboard, and scripts all consume this service rather than
instantiating engines directly.
"""

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Callable, Optional

import pandas as pd

from lab.xml_parser.core.config import MythosConfig, get_config
from lab.xml_parser.core.exceptions import ParseError
from lab.xml_parser.core.logging import get_logger
from lab.xml_parser.core.models import Finding, ReviewReport, RolloverReport


ProgressCallback = Callable[[str, float], None]


@dataclass
class TagSummary:
    """Typed result from a tag operation."""
    success: bool
    entity_count: int = 0
    results: list = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    contradictions_count: int = 0
    duration_ms: float = 0.0
    message: str = ""


@dataclass
class EntitySummary:
    reference_id: str
    name: str
    country: str
    currency: str
    has_sch_h: bool = False
    has_sch_i1: bool = False
    has_sch_e: bool = False
    has_sch_f: bool = False
    has_sch_j: bool = False


@dataclass
class ReviewResult:
    """Typed result from a review operation."""
    success: bool
    report: Optional[ReviewReport] = None
    duration_ms: float = 0.0
    entity_count: int = 0
    finding_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    export_path: Optional[Path] = None


@dataclass
class ReconcileResult:
    """Typed result from a reconciliation operation."""
    success: bool
    total_comparisons: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_rate: float = 0.0
    duration_ms: float = 0.0
    message: str = ""
    failures: Optional[pd.DataFrame] = None
    export_path: Optional[Path] = None


@dataclass
class ExportResult:
    """Typed result from an export operation."""
    success: bool
    path: Optional[Path] = None
    format: str = ""
    message: str = ""


class MythosService:
    """Unified service layer for Mythos operations.

    Usage:
        svc = MythosService()
        result = svc.review("current.xml", prior="prior.xml")
        if result.success:
            print(f"{result.finding_count} findings")
    """

    def __init__(self, config: Optional[MythosConfig] = None, progress: Optional[ProgressCallback] = None):
        self._config = config or get_config()
        self._progress = progress or (lambda msg, pct: None)
        self._log = get_logger("service")

    def review(
        self,
        current_xml: str | Path,
        prior: str | Path | None = None,
        export: bool = False,
        export_path: str | Path | None = None,
    ) -> ReviewResult:
        """Run automated compliance review on XML return(s).

        Args:
            current_xml: Path to current year e-file XML
            prior: Optional prior year XML (enables rollover checks)
            export: If True, auto-export findings to Excel
            export_path: Custom export path (default: next to XML)
        """
        from lab.xml_parser.review_engine import ReviewEngine

        t0 = perf_counter()

        try:
            engine = ReviewEngine(progress=self._progress)
            report = engine.review(current_xml, prior)
        except Exception as e:
            self._log.error(f"Review failed: {e}")
            return ReviewResult(success=False, message=str(e))

        duration = (perf_counter() - t0) * 1000
        self._progress("Complete", 1.0)

        result = ReviewResult(
            success=True,
            report=report,
            duration_ms=duration,
            entity_count=report.entity_count,
            finding_count=len(report.findings),
            high_count=len(report.high_severity()),
            medium_count=sum(1 for f in report.findings if f.severity == "MEDIUM"),
            low_count=sum(1 for f in report.findings if f.severity == "LOW"),
            message=f"{len(report.findings)} findings ({len(report.high_severity())} HIGH) in {duration:.0f}ms",
        )

        if not prior:
            result.warnings.append("No prior year XML — rollover checks skipped")

        if export:
            export_result = self.export_review(report, path=export_path or current_xml)
            result.export_path = export_result.path

        self._log.info(
            f"Review complete: {result.entity_count} entities, "
            f"{result.finding_count} findings, {duration:.0f}ms"
        )
        return result

    def list_entities(self, xml_path: str | Path) -> list[EntitySummary]:
        """List all entities in an XML return with schedule presence flags."""
        from lab.xml_parser.parser import EFileParser

        self._progress("Parsing entities...", 0.2)
        parser = EFileParser(Path(xml_path))
        df = parser.to_dataframe()

        entities = []
        refs = [r for r in df["_reference_id"].unique() if r]

        sch_h = parser.extract_form("IRS5471ScheduleH")
        sch_i1 = parser.extract_form("IRS5471ScheduleI1")
        sch_e = parser.extract_form("IRS5471ScheduleE")
        sch_f = parser.extract_form("IRS5471ScheduleF")
        sch_j = parser.extract_form("IRS5471ScheduleJ")

        h_refs = set(sch_h["_reference_id"].unique()) if not sch_h.empty else set()
        i1_refs = set(sch_i1["_reference_id"].unique()) if not sch_i1.empty else set()
        e_refs = set(sch_e["_reference_id"].unique()) if not sch_e.empty else set()
        f_refs = set(sch_f["_reference_id"].unique()) if not sch_f.empty else set()
        j_refs = set(sch_j["_reference_id"].unique()) if not sch_j.empty else set()

        for ref in sorted(refs):
            row = df[df["_reference_id"] == ref].iloc[0]
            name = str(row.get("_entity_name", ref))
            country = str(row.get("IRS5471_CountryUnderWhoseLawsIncCd", ""))
            currency = str(row.get("IRS5471_FunctionalCurrencyCd", ""))

            entities.append(EntitySummary(
                reference_id=ref,
                name=name,
                country=country,
                currency=currency,
                has_sch_h=ref in h_refs,
                has_sch_i1=ref in i1_refs,
                has_sch_e=ref in e_refs,
                has_sch_f=ref in f_refs,
                has_sch_j=ref in j_refs,
            ))

        self._progress("Done", 1.0)
        return entities

    def classify_entities(self, xml_path: str | Path, registry=None):
        """Unified entity classification — parse, enrich, tag, return profiles.

        Returns ClassificationResult with full ClassifiedEntity objects.
        """
        from lab.xml_parser.parser import EFileParser
        from lab.core.entity_classifier import EntityClassifier, ClassificationResult

        t0 = perf_counter()
        self._progress("Parsing XML for classification...", 0.1)

        try:
            parser = EFileParser(Path(xml_path))
        except Exception as e:
            return ClassificationResult(success=False, message=f"Parse error: {e}")

        self._progress("Classifying entities...", 0.4)
        classifier = EntityClassifier(registry=registry)

        try:
            entities = classifier.classify(parser)
        except Exception as e:
            return ClassificationResult(success=False, message=f"Classification error: {e}")

        self._progress("Building summary...", 0.8)
        summary = classifier.build_summary(entities)

        duration = (perf_counter() - t0) * 1000
        self._progress("Complete", 1.0)
        self._log.info(f"Classified {len(entities)} entities in {duration:.0f}ms")

        return ClassificationResult(
            success=True,
            entities=entities,
            summary=summary,
            duration_ms=duration,
            message=f"Classified {len(entities)} entities ({len(summary.contradictions)} contradictions)",
        )

    def tag_entities(self, xml_path: str | Path) -> TagSummary:
        """Classify entities by fiscal behavior using rule-based tagging.

        Delegates to classify_entities() and adapts the output to TagSummary
        for backward compatibility.
        """
        from lab.core.entity_tagger import TagResult

        t0 = perf_counter()
        cr = self.classify_entities(xml_path)

        if not cr.success:
            return TagSummary(success=False, message=cr.message)

        results = []
        for e in cr.entities:
            results.append(TagResult(
                reference_id=e.reference_id,
                entity_name=e.entity_name,
                tags=e.tags,
                contradictions=e.contradictions,
            ))

        duration = (perf_counter() - t0) * 1000
        contradictions_total = sum(len(r.contradictions) for r in results)

        tag_counts: dict[str, int] = {}
        for r in results:
            for tag in r.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tag_counts = dict(sorted(tag_counts.items(), key=lambda x: -x[1]))

        return TagSummary(
            success=True,
            entity_count=len(results),
            results=results,
            summary=tag_counts,
            contradictions_count=contradictions_total,
            duration_ms=duration,
            message=f"Tagged {len(results)} entities ({contradictions_total} contradictions)",
        )

    def reconcile(
        self,
        xml_path: str | Path,
        workbook_path: str | Path,
        tolerance: float = 1.0,
        schedules: list[str] | None = None,
        export: bool = False,
        export_path: str | Path | None = None,
    ) -> ReconcileResult:
        """Reconcile workbook data against XML — field-by-field comparison.

        Args:
            xml_path: Path to e-file XML
            workbook_path: Path to Excel workbook
            tolerance: Numeric tolerance for matching (default: $1)
            schedules: Specific schedules to reconcile (default: all)
            export: Auto-export results to Excel
            export_path: Custom export path
        """
        from lab.xml_parser.parser import EFileParser
        from lab.xml_parser.workbook_reader import WorkbookReader
        from lab.xml_parser.reconciler import Reconciler

        t0 = perf_counter()
        self._progress("Parsing XML...", 0.1)

        try:
            parser = EFileParser(xml_path)
            parser.parse()
        except Exception as e:
            return ReconcileResult(success=False, message=f"XML parse error: {e}")

        self._progress("Parsing workbook...", 0.3)
        try:
            with WorkbookReader(workbook_path) as reader:
                wb_data = reader.parse()
        except Exception as e:
            return ReconcileResult(success=False, message=f"Workbook parse error: {e}")

        self._progress("Reconciling...", 0.6)
        rec = Reconciler(tolerance=tolerance)
        report = rec.reconcile(wb_data, parser, schedules=schedules)

        duration = (perf_counter() - t0) * 1000
        self._progress("Complete", 1.0)

        s = report.summary
        result = ReconcileResult(
            success=True,
            total_comparisons=s["total"],
            pass_count=s["pass_count"],
            fail_count=s["fail_count"],
            pass_rate=s["pass_rate"],
            duration_ms=duration,
            message=f"{s['pass_rate']:.0%} pass rate ({s['fail_count']} failures)",
            failures=report.failures_only(),
        )

        if export:
            out = Path(export_path) if export_path else Path(workbook_path).parent / f"reconciliation_{Path(workbook_path).stem}.xlsx"
            report.to_excel(out)
            result.export_path = out

        self._log.info(
            f"Reconciliation complete: {result.total_comparisons} comparisons, "
            f"{result.pass_rate:.0%} pass, {duration:.0f}ms"
        )
        return result

    def export_review(
        self,
        report: ReviewReport,
        path: str | Path | None = None,
        format: str = "excel",
        filter_spec=None,
    ) -> ExportResult:
        """Export review findings to file.

        Deprecated: use export_findings() for premium output.
        Kept for backward compatibility — delegates to export_findings().
        """
        return self.export_findings(report, path=path, format=format, filter_spec=filter_spec)

    def export_findings(
        self,
        report: ReviewReport,
        path: str | Path | None = None,
        format: str = "excel",
        filter_spec=None,
        include_metadata: bool = True,
    ) -> ExportResult:
        """Export review findings with premium formatting via DesignSystem.

        Args:
            report: ReviewReport to export
            path: Output path (auto-named if None)
            format: "excel", "csv", "json", or "pdf"
            filter_spec: Optional FilterSpec to narrow findings
            include_metadata: Include client/engagement metadata in output
        """
        from lab.xml_parser.export import export_excel, export_pdf, export_findings_csv

        if filter_spec and not filter_spec.is_empty:
            from lab.xml_parser.core.filters import filter_review_report
            report = filter_review_report(report, filter_spec)

        if not report or not report.findings:
            return ExportResult(success=False, message="No findings to export")

        base = Path(path) if path else self._config.output_dir / "review"
        client = report.client_name if include_metadata else ""

        if format == "excel":
            out = base.with_suffix(".xlsx") if base.suffix != ".xlsx" else base
            out.parent.mkdir(parents=True, exist_ok=True)
            export_excel(out, review_report=report, client_name=client)
            return ExportResult(success=True, path=out, format="excel",
                              message=f"Saved {len(report.findings)} findings")

        elif format == "pdf":
            out = base.with_suffix(".pdf")
            out.parent.mkdir(parents=True, exist_ok=True)
            export_pdf(out, review_report=report, client_name=client,
                      tax_year=report.tax_year or "")
            return ExportResult(success=True, path=out, format="pdf",
                              message=f"Saved {len(report.findings)} findings")

        elif format == "csv":
            out = base.with_suffix(".csv")
            out.parent.mkdir(parents=True, exist_ok=True)
            export_findings_csv(report, out)
            return ExportResult(success=True, path=out, format="csv",
                              message=f"Saved {len(report.findings)} findings")

        elif format == "json":
            out = base.with_suffix(".json")
            out.parent.mkdir(parents=True, exist_ok=True)
            df = report.to_dataframe()
            df.to_json(out, orient="records", indent=2)
            return ExportResult(success=True, path=out, format="json",
                              message=f"Saved {len(report.findings)} findings")

        return ExportResult(success=False, message=f"Unknown format: {format}")

    def export_rollover(
        self,
        reports: dict[str, RolloverReport],
        path: str | Path | None = None,
        format: str = "excel",
        client_name: str = "",
        tax_year: str = "",
    ) -> ExportResult:
        """Export rollover reports with premium formatting.

        Args:
            reports: Dict of report name -> RolloverReport
            path: Output path or directory (auto-named if None)
            format: "excel", "csv", "html", or "pdf"
            client_name: Client name for headers
            tax_year: Tax year label
        """
        from lab.xml_parser.export import export_excel, export_pdf, export_html, export_csv

        if not reports:
            return ExportResult(success=False, message="No rollover reports to export")

        base = Path(path) if path else self._config.output_dir / "rollover"

        if format == "excel":
            out = base.with_suffix(".xlsx") if base.suffix != ".xlsx" else base
            out.parent.mkdir(parents=True, exist_ok=True)
            export_excel(out, rollover_reports=reports, client_name=client_name)
            return ExportResult(success=True, path=out, format="excel",
                              message=f"Saved {len(reports)} rollover reports")

        elif format == "pdf":
            out = base.with_suffix(".pdf")
            out.parent.mkdir(parents=True, exist_ok=True)
            export_pdf(out, rollover_reports=reports, client_name=client_name,
                      tax_year=tax_year)
            return ExportResult(success=True, path=out, format="pdf",
                              message=f"Saved {len(reports)} rollover reports")

        elif format == "html":
            out_dir = base if base.suffix == "" else base.parent / base.stem
            out_dir.mkdir(parents=True, exist_ok=True)
            files = export_html(reports, out_dir, client_name=client_name,
                              tax_year=tax_year)
            return ExportResult(success=True, path=out_dir, format="html",
                              message=f"Saved {len(files)} HTML files")

        elif format == "csv":
            out_dir = base if base.suffix == "" else base.parent / base.stem
            out_dir.mkdir(parents=True, exist_ok=True)
            files = export_csv(reports, out_dir, prefix="rollover")
            return ExportResult(success=True, path=out_dir, format="csv",
                              message=f"Saved {len(files)} CSV files")

        return ExportResult(success=False, message=f"Unknown format: {format}")

    def export_parsed_data(
        self,
        parser,
        path: str | Path | None = None,
        format: str = "excel",
        forms_filter: list[str] | None = None,
        entity_filter: str | None = None,
        include_metadata: bool = True,
        include_summary: bool = True,
        include_raw: bool = False,
    ) -> ExportResult:
        """Export raw parsed XML data (schedules) to file.

        Args:
            parser: EFileParser instance (already parsed)
            path: Output path (auto-named if None)
            format: "excel", "csv", or "json"
            forms_filter: List of form names to include (None = all)
            entity_filter: Single entity reference_id to filter
            include_metadata: Include header metadata sheet
            include_summary: Include summary sheet
            include_raw: Include raw field values (unformatted)
        """
        from lab.xml_parser.export.design_system import DesignSystem as DS

        if parser is None:
            return ExportResult(success=False, message="No parser provided")

        base = Path(path) if path else self._config.output_dir / "parsed_data"

        forms_to_extract = forms_filter or parser.available_forms()
        frames: dict[str, pd.DataFrame] = {}

        for form_name in forms_to_extract:
            df = parser.extract_form(form_name)
            if df.empty:
                continue
            if entity_filter:
                df = df[df["_reference_id"] == entity_filter]
                if df.empty:
                    continue
            tab_name = form_name.replace("IRS5471", "").replace("IRS8858", "8858_")
            if len(tab_name) > 31:
                tab_name = tab_name[:31]
            frames[tab_name] = df

        if not frames:
            return ExportResult(success=False, message="No data found for the selected filters")

        if format == "excel":
            out = base.with_suffix(".xlsx") if base.suffix != ".xlsx" else base
            out.parent.mkdir(parents=True, exist_ok=True)

            import xlsxwriter
            wb = xlsxwriter.Workbook(str(out), {"strings_to_numbers": False})

            header_fmt = wb.add_format({
                "font_name": DS.FONT_EXCEL, "font_size": 9, "bold": True,
                "font_color": DS.WHITE, "bg_color": DS.NAVY,
                "border": 1, "border_color": DS.NAVY,
            })
            cell_fmt = wb.add_format({
                "font_name": DS.FONT_EXCEL, "font_size": 9, "font_color": DS.NAVY,
            })

            if include_summary:
                ws = wb.add_worksheet("Summary")
                ws.hide_gridlines(2)
                ws.write(0, 0, "Form/Schedule", header_fmt)
                ws.write(0, 1, "Records", header_fmt)
                ws.write(0, 2, "Fields", header_fmt)
                for i, (name, df) in enumerate(frames.items(), 1):
                    ws.write(i, 0, name, cell_fmt)
                    ws.write(i, 1, len(df), cell_fmt)
                    ws.write(i, 2, len(df.columns), cell_fmt)
                ws.set_column(0, 0, 30)
                ws.set_column(1, 2, 12)

            for tab_name, df in frames.items():
                cols = [c for c in df.columns if include_raw or not c.startswith("_raw_")]
                write_df = df[cols] if cols != list(df.columns) else df
                ws = wb.add_worksheet(tab_name)
                ws.hide_gridlines(2)
                for col_idx, col_name in enumerate(write_df.columns):
                    ws.write(0, col_idx, col_name, header_fmt)
                for row_idx, row in enumerate(write_df.itertuples(index=False), 1):
                    for col_idx, value in enumerate(row):
                        ws.write(row_idx, col_idx, str(value) if value is not None else "", cell_fmt)
                ws.set_column(0, len(write_df.columns) - 1, 15)

            wb.close()
            return ExportResult(success=True, path=out, format="excel",
                              message=f"Saved {len(frames)} schedules ({sum(len(df) for df in frames.values())} records)")

        elif format == "csv":
            out_dir = base if base.suffix == "" else base.parent / base.stem
            out_dir.mkdir(parents=True, exist_ok=True)
            for tab_name, df in frames.items():
                safe = tab_name.replace("/", "-").replace(" ", "_")
                df.to_csv(out_dir / f"{safe}.csv", index=False)
            return ExportResult(success=True, path=out_dir, format="csv",
                              message=f"Saved {len(frames)} CSV files")

        elif format == "json":
            out = base.with_suffix(".json") if base.suffix != ".json" else base
            out.parent.mkdir(parents=True, exist_ok=True)
            import json
            payload = {name: df.to_dict(orient="records") for name, df in frames.items()}
            out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            return ExportResult(success=True, path=out, format="json",
                              message=f"Saved {len(frames)} schedules")

        return ExportResult(success=False, message=f"Unknown format: {format}")

    def export_full(
        self,
        review_report: ReviewReport | None = None,
        rollover_reports: dict[str, RolloverReport] | None = None,
        path: str | Path | None = None,
        format: str = "excel",
        client_name: str = "",
        tax_year: str = "",
    ) -> ExportResult:
        """Combined export — findings + rollover in one file/package.

        This is the premium orchestrator that produces the complete deliverable.

        Args:
            review_report: ReviewReport (findings)
            rollover_reports: Dict of rollover reports
            path: Output path (auto-named if None)
            format: "excel", "pdf", "html", or "csv"
            client_name: Client name for headers
            tax_year: Tax year label
        """
        from lab.xml_parser.export import export_excel, export_pdf, export_html, export_csv

        if not review_report and not rollover_reports:
            return ExportResult(success=False, message="No data to export")

        base = Path(path) if path else self._config.output_dir / "full_review"
        client = client_name or (review_report.client_name if review_report else "")

        if format == "excel":
            out = base.with_suffix(".xlsx") if base.suffix != ".xlsx" else base
            out.parent.mkdir(parents=True, exist_ok=True)
            export_excel(out, review_report=review_report,
                        rollover_reports=rollover_reports, client_name=client)
            return ExportResult(success=True, path=out, format="excel",
                              message="Full review exported")

        elif format == "pdf":
            out = base.with_suffix(".pdf")
            out.parent.mkdir(parents=True, exist_ok=True)
            export_pdf(out, review_report=review_report,
                      rollover_reports=rollover_reports,
                      client_name=client, tax_year=tax_year)
            return ExportResult(success=True, path=out, format="pdf",
                              message="Full review exported")

        elif format == "html":
            out_dir = base if base.suffix == "" else base.parent / base.stem
            out_dir.mkdir(parents=True, exist_ok=True)
            files = []
            if rollover_reports:
                files = export_html(rollover_reports, out_dir,
                                   client_name=client, tax_year=tax_year)
            return ExportResult(success=True, path=out_dir, format="html",
                              message=f"Saved {len(files)} HTML files")

        elif format == "csv":
            out_dir = base if base.suffix == "" else base.parent / base.stem
            out_dir.mkdir(parents=True, exist_ok=True)
            files = []
            if rollover_reports:
                files += export_csv(rollover_reports, out_dir, prefix="rollover")
            if review_report:
                from lab.xml_parser.export import export_findings_csv
                findings_path = out_dir / "findings.csv"
                export_findings_csv(review_report, findings_path)
                files.append(findings_path)
            return ExportResult(success=True, path=out_dir, format="csv",
                              message=f"Saved {len(files)} files")

        return ExportResult(success=False, message=f"Unknown format: {format}")

    def full_review(
        self,
        current_xml: str | Path,
        prior_xml: str | Path,
        output_path: str | Path | None = None,
        export_format: str = "excel",
        filter_spec=None,
        form_type: str = "5471",
    ) -> dict:
        """Run the full review pipeline (tabular rollover + automated checks).

        Returns dict of RolloverReport objects keyed by report name.
        Uses the new reports/ and export/ packages directly.

        Args:
            filter_spec: Optional FilterSpec to narrow output by entity/check.
            form_type: "5471" (default), "8858", or "auto" for unified.
        """
        from lab.xml_parser.reports import run_all_reports
        from lab.xml_parser.review_engine import ReviewEngine
        from lab.xml_parser.export import export_excel

        if form_type == "auto":
            return self.full_review_all(current_xml, prior_xml, output_path, filter_spec)

        self._progress("Generating rollover reports...", 0.2)

        if form_type == "8858":
            from lab.xml_parser.reports import run_all_reports_8858
            reports = run_all_reports_8858(prior_xml, current_xml)
        else:
            reports = run_all_reports(prior_xml, current_xml)

        self._progress("Running automated checks...", 0.6)
        engine = ReviewEngine(progress=self._progress)
        review_report = engine.review(current_xml, prior_xml, form_type=form_type)

        if filter_spec and not filter_spec.is_empty:
            from lab.xml_parser.core.filters import filter_review_report, filter_rollover_reports
            reports = filter_rollover_reports(reports, filter_spec)
            review_report = filter_review_report(review_report, filter_spec)

        self._progress("Exporting...", 0.8)
        if output_path:
            out = Path(output_path)
        else:
            out = Path(current_xml).parent / f"Review_{Path(current_xml).stem}.xlsx"

        export_excel(
            out,
            review_report=review_report,
            rollover_reports=reports,
            client_name=review_report.client_name,
        )

        reports["_review_report"] = review_report
        reports["_export_path"] = out
        self._progress("Complete", 1.0)
        return reports

    def full_review_all(
        self,
        current_xml: str | Path,
        prior_xml: str | Path,
        output_path: str | Path | None = None,
        filter_spec=None,
    ) -> dict:
        """Unified review — auto-detect forms and run all applicable checks + reports.

        Scans the XML for Form 5471 and 8858 entities. Runs checks and reports
        for each form type found. Returns merged dict with all reports and a
        composite ReviewReport.

        Args:
            current_xml: Path to current year XML
            prior_xml: Path to prior year XML
            output_path: Custom export path (default: next to XML)
            filter_spec: Optional FilterSpec to narrow output
        """
        from lab.xml_parser.reports import run_all_reports_unified
        from lab.xml_parser.review_engine import ReviewEngine
        from lab.xml_parser.export import export_excel

        self._progress("Detecting form types...", 0.05)
        reports = run_all_reports_unified(prior_xml, current_xml)

        self._progress("Running automated checks...", 0.50)
        engine = ReviewEngine(progress=self._progress)
        review_report = engine.review_all(current_xml, prior_xml)

        if filter_spec and not filter_spec.is_empty:
            from lab.xml_parser.core.filters import filter_review_report, filter_rollover_reports
            reports = filter_rollover_reports(reports, filter_spec)
            review_report = filter_review_report(review_report, filter_spec)

        self._progress("Exporting...", 0.85)
        if output_path:
            out = Path(output_path)
        else:
            out = Path(current_xml).parent / f"Review_{Path(current_xml).stem}.xlsx"

        export_excel(
            out,
            review_report=review_report,
            rollover_reports=reports,
            client_name=review_report.client_name,
        )

        reports["_review_report"] = review_report
        reports["_export_path"] = out
        self._progress("Complete", 1.0)
        return reports

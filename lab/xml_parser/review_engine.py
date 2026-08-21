"""Review Engine — XML-First Automated Compliance Review.

Performs multi-dimensional quality checks against IRS e-file XML returns
without requiring workbook access. Surfaces anomalies, inconsistencies,
and review points ranked by severity.

This module is now a thin orchestrator. Check logic lives in
lab.xml_parser.engine.checks.{flow, completeness, reasonableness, rollover}.
"""

from pathlib import Path

import pandas as pd

from lab.xml_parser.core.models import Finding, ReviewReport
from lab.xml_parser.engine.checks._helpers import CheckContext
from lab.xml_parser.engine.checks.flow import run_flow_checks
from lab.xml_parser.engine.checks.completeness import run_completeness_checks
from lab.xml_parser.engine.checks.reasonableness import run_reasonableness_checks
from lab.xml_parser.engine.checks.rollover import run_rollover_checks
from lab.xml_parser.engine.checks.cross_schedule import run_cross_schedule_checks
from lab.xml_parser.engine.checks.cross_form import run_cross_form_checks
from lab.xml_parser.engine.checks.form_8990 import run_form_8990_checks
from lab.xml_parser.engine.checks.completeness_8858 import run_completeness_checks_8858
from lab.xml_parser.engine.checks.flow_8858 import run_flow_checks_8858
from lab.xml_parser.engine.checks.reasonableness_8858 import run_reasonableness_checks_8858
from lab.xml_parser.engine.checks.rollover_8858 import run_rollover_checks_8858
from lab.xml_parser.parser import EFileParser


class ReviewEngine:
    """Automated compliance review engine for IRS e-file XML returns."""

    def __init__(self, progress=None):
        self._findings: list[Finding] = []
        self._progress = progress or (lambda msg, pct: None)

    def review(
        self,
        current_xml: str | Path,
        prior_xml: str | Path | None = None,
        form_type: str = "5471",
    ) -> ReviewReport:
        """Run full review on one or two XML returns.

        Args:
            current_xml: Path to current year XML
            prior_xml: Optional path to prior year XML (enables rollover checks)
            form_type: "5471" (default) or "8858"
        """
        if form_type == "8858":
            return self._review_8858(current_xml, prior_xml)
        return self._review_5471(current_xml, prior_xml)

    def _review_5471(
        self,
        current_xml: str | Path,
        prior_xml: str | Path | None = None,
    ) -> ReviewReport:
        """Run Form 5471 checks."""
        self._findings = []

        self._progress("Parsing XML...", 0.10)
        parser_cy = EFileParser(Path(current_xml))
        df_cy = parser_cy.to_dataframe()

        report = ReviewReport()
        report.client_name = self._get_client_name(df_cy)
        report.tax_year = self._get_tax_year(df_cy)
        report.entity_count = len(df_cy["_reference_id"].unique()) - (1 if "" in df_cy["_reference_id"].values else 0)

        self._progress("Flow-through checks...", 0.20)
        ctx_flow = CheckContext(parser_cy, df_cy, self._get_entity_name)
        run_flow_checks(ctx_flow)
        self._findings.extend(ctx_flow.findings)

        self._progress("Completeness checks...", 0.35)
        ctx_cmp = CheckContext(parser_cy, df_cy, self._get_entity_name)
        run_completeness_checks(ctx_cmp)
        self._findings.extend(ctx_cmp.findings)

        self._progress("Reasonableness checks...", 0.50)
        ctx_rsn = CheckContext(parser_cy, df_cy, self._get_entity_name)
        run_reasonableness_checks(ctx_rsn)
        self._findings.extend(ctx_rsn.findings)

        self._progress("Cross-schedule checks...", 0.60)
        ctx_xsc = CheckContext(parser_cy, df_cy, self._get_entity_name)
        run_cross_schedule_checks(ctx_xsc)
        self._findings.extend(ctx_xsc.findings)

        self._progress("Cross-form checks...", 0.65)
        ctx_xfm = CheckContext(parser_cy, df_cy, self._get_entity_name)
        run_cross_form_checks(ctx_xfm)
        self._findings.extend(ctx_xfm.findings)

        # Section 163(j) / Form 8990 checks
        parser_py = None
        if prior_xml:
            parser_py = EFileParser(Path(prior_xml))

        self._progress("Section 163(j) checks...", 0.72)
        ctx_bie = CheckContext(parser_cy, df_cy, self._get_entity_name, prior_parser=parser_py)
        run_form_8990_checks(ctx_bie)
        self._findings.extend(ctx_bie.findings)

        # Rollover checks (if prior year available)
        if parser_py:
            self._progress("Rollover checks...", 0.82)
            df_py = parser_py.to_dataframe()
            ctx_rol = CheckContext(parser_cy, df_cy, self._get_entity_name)
            run_rollover_checks(ctx_rol, parser_py=parser_py, df_py=df_py)
            self._findings.extend(ctx_rol.findings)

        self._progress("Finalizing...", 0.92)

        report.findings = sorted(
            self._findings,
            key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity], f.check_id),
        )
        report.compute_summary()
        return report

    def _review_8858(
        self,
        current_xml: str | Path,
        prior_xml: str | Path | None = None,
    ) -> ReviewReport:
        """Run Form 8858 checks on FDE/FB entities."""
        self._findings = []

        self._progress("Parsing 8858 XML...", 0.10)
        parser_cy = EFileParser(Path(current_xml))
        main_df = parser_cy.extract_form_8858("IRS8858")

        report = ReviewReport()
        report.form_type = "8858"

        if main_df.empty:
            report.entity_count = 0
            report.findings = []
            report.compute_summary()
            return report

        report.client_name = self._get_client_name_8858(main_df)
        report.entity_count = len(main_df["_reference_id"].unique()) - (1 if "" in main_df["_reference_id"].values else 0)

        def get_name(df, code):
            m = main_df[main_df["_reference_id"] == code]
            return str(m.iloc[0]["_entity_name"]) if not m.empty else code

        self._progress("Completeness checks...", 0.25)
        ctx_cmp = CheckContext(parser_cy, main_df, get_name)
        run_completeness_checks_8858(ctx_cmp)
        self._findings.extend(ctx_cmp.findings)

        self._progress("Flow-through checks...", 0.45)
        ctx_flow = CheckContext(parser_cy, main_df, get_name)
        run_flow_checks_8858(ctx_flow)
        self._findings.extend(ctx_flow.findings)

        self._progress("Reasonableness checks...", 0.60)
        ctx_rsn = CheckContext(parser_cy, main_df, get_name)
        run_reasonableness_checks_8858(ctx_rsn)
        self._findings.extend(ctx_rsn.findings)

        # Rollover checks
        if prior_xml:
            self._progress("Rollover checks...", 0.75)
            parser_py = EFileParser(Path(prior_xml))
            ctx_rol = CheckContext(parser_cy, main_df, get_name)
            run_rollover_checks_8858(ctx_rol, parser_py)
            self._findings.extend(ctx_rol.findings)

        self._progress("Finalizing...", 0.92)

        report.findings = sorted(
            self._findings,
            key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity], f.check_id),
        )
        report.compute_summary()
        return report

    def _get_client_name(self, df: pd.DataFrame) -> str:
        name_cols = [c for c in df.columns if "BusinessNameLine1" in c and "Foreign" not in c]
        if name_cols:
            vals = df[name_cols[0]].dropna().unique()
            if len(vals) > 0:
                return str(vals[0])
        return "Unknown"

    def _get_tax_year(self, df: pd.DataFrame) -> str:
        if "_tax_year" in df.columns:
            vals = df["_tax_year"].dropna().unique()
            if len(vals) > 0:
                return str(vals[0])
        return ""

    def _get_entity_name(self, df: pd.DataFrame, code: str) -> str:
        if "_entity_name" in df.columns:
            match = df[df["_reference_id"] == code]["_entity_name"]
            if not match.empty:
                return str(match.iloc[0])
        return code

    def review_all(
        self,
        current_xml: str | Path,
        prior_xml: str | Path | None = None,
    ) -> ReviewReport:
        """Auto-detect form types and run all applicable checks.

        Scans the XML for both Form 5471 and Form 8858 entities.
        Runs checks for each form type found, merges findings into
        a single composite ReviewReport.
        """
        self._findings = []
        parser = EFileParser(Path(current_xml))
        forms_present = parser.detect_forms()

        if not forms_present:
            report = ReviewReport()
            report.compute_summary()
            return report

        reports: list[ReviewReport] = []

        if "5471" in forms_present:
            self._progress("Reviewing Form 5471...", 0.05)
            r5471 = self._review_5471(current_xml, prior_xml)
            reports.append(r5471)

        if "8858" in forms_present:
            pct = 0.50 if "5471" in forms_present else 0.05
            self._progress("Reviewing Form 8858...", pct)
            r8858 = self._review_8858(current_xml, prior_xml)
            reports.append(r8858)

        if len(reports) == 1:
            return reports[0]

        return self._merge_reports(reports)

    def _merge_reports(self, reports: list[ReviewReport]) -> ReviewReport:
        """Merge multiple form-type ReviewReports into a composite report."""
        merged = ReviewReport()
        merged.form_type = "multi"

        all_findings = []
        entity_count = 0
        for r in reports:
            all_findings.extend(r.findings)
            entity_count += r.entity_count
            if not merged.client_name and r.client_name != "Unknown":
                merged.client_name = r.client_name
            if not merged.tax_year and r.tax_year:
                merged.tax_year = r.tax_year

        merged.entity_count = entity_count
        merged.findings = sorted(
            all_findings,
            key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity], f.check_id),
        )
        merged.compute_summary()
        return merged

    def _get_client_name_8858(self, df: pd.DataFrame) -> str:
        if "_tax_owner" in df.columns:
            vals = df["_tax_owner"].dropna().unique()
            owners = [v for v in vals if v]
            if owners:
                return str(owners[0])
        return "Unknown"

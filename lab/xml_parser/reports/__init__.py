"""Reports package — data generation + backward-compat ReportEngine.

Pure functions (preferred for new code):
    from lab.xml_parser.reports import run_all_reports, sch_f_rollover, ...

Legacy class (still supported):
    from lab.xml_parser.reports import ReportEngine
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from lab.xml_parser.core.models import Finding, ReviewReport, RolloverItem, RolloverReport
from lab.xml_parser.parser import EFileParser
from lab.xml_parser.models import ParsedReturn
from lab.xml_parser.reports.rollover import sch_f_rollover, page1_rollover, sch_j_rollover
from lab.xml_parser.reports.movement import (
    ep_movement, gilti_comparison, sch_h_detail, gilti_detail, sch_e_tax_summary,
)
from lab.xml_parser.reports.entity_changes import new_final_entities, schedule_g_changes
from lab.xml_parser.reports.cross_schedule import cross_schedule_tie
from lab.xml_parser.reports.reports_8858 import (
    sch_f_8858_rollover,
    ep_summary_8858,
    income_statement_8858,
    entity_changes_8858,
    tax_owner_map_8858,
)

__all__ = [
    "sch_f_rollover",
    "page1_rollover",
    "sch_j_rollover",
    "ep_movement",
    "gilti_comparison",
    "sch_h_detail",
    "gilti_detail",
    "sch_e_tax_summary",
    "cross_schedule_tie",
    "new_final_entities",
    "schedule_g_changes",
    "run_all_reports",
    "run_all_reports_8858",
    "run_all_reports_unified",
    "sch_f_8858_rollover",
    "ep_summary_8858",
    "income_statement_8858",
    "entity_changes_8858",
    "tax_owner_map_8858",
    "ReportEngine",
]


def run_all_reports(
    py_xml: str | Path,
    cy_xml: str | Path,
) -> dict[str, RolloverReport]:
    """Run all tabular reports and return as a dict.

    This is the primary orchestrator for data generation
    without any rendering or file output.
    """
    py = EFileParser(py_xml).parse()
    cy = EFileParser(cy_xml).parse()

    return {
        "Sch F Rollover": sch_f_rollover(py, cy),
        "Sch J Rollover (GEN)": sch_j_rollover(py, cy, basket="GEN"),
        "Sch J Rollover (PAS)": sch_j_rollover(py, cy, basket="PAS"),
        "Page 1 Rollover": page1_rollover(py, cy),
        "E&P Movement": ep_movement(py, cy),
        "Sch H Detail": sch_h_detail(py, cy),
        "GILTI Comparison": gilti_comparison(py, cy),
        "GILTI Detail": gilti_detail(py, cy),
        "Sch E Tax Summary": sch_e_tax_summary(py, cy),
        "Cross-Schedule Tie": cross_schedule_tie(py, cy),
        "Entity Changes": new_final_entities(py, cy),
        "Sch G Indicators": schedule_g_changes(py, cy),
    }


def run_all_reports_8858(
    py_xml: str | Path,
    cy_xml: str | Path,
) -> dict[str, RolloverReport]:
    """Run all Form 8858 tabular reports."""
    py = EFileParser(py_xml)
    cy = EFileParser(cy_xml)

    return {
        "8858 Sch F Rollover": sch_f_8858_rollover(py, cy),
        "8858 E&P Summary": ep_summary_8858(py, cy),
        "8858 Income Statement": income_statement_8858(py, cy),
        "8858 Entity Changes": entity_changes_8858(py, cy),
        "8858 Tax Owner Map": tax_owner_map_8858(py, cy),
    }


def run_all_reports_unified(
    py_xml: str | Path,
    cy_xml: str | Path,
) -> dict[str, RolloverReport]:
    """Auto-detect form types and run all applicable reports.

    Scans the current-year XML for Form 5471 and Form 8858 entities.
    Runs reports for each form type found, returning a merged dict.
    """
    cy_parser = EFileParser(cy_xml)
    forms = cy_parser.detect_forms()

    reports: dict[str, RolloverReport] = {}

    if "5471" in forms:
        reports.update(run_all_reports(py_xml, cy_xml))

    if "8858" in forms:
        reports.update(run_all_reports_8858(py_xml, cy_xml))

    return reports


class ReportEngine:
    """Generate predefined analytical reports from PY vs CY XML comparison.

    Delegates data generation to reports.rollover, reports.movement,
    reports.entity_changes. Retains terminal display for backward compat.
    """

    def __init__(self, prior_xml: str | Path, current_xml: str | Path):
        self.py_path = Path(prior_xml)
        self.cy_path = Path(current_xml)
        self._py = EFileParser(prior_xml).parse()
        self._cy = EFileParser(current_xml).parse()
        self.console = Console()

    @property
    def entity_count(self) -> int:
        return len(self._cy.subsidiaries)

    def get_all_entities(self) -> list[tuple[str, str]]:
        """Return (reference_id, name) for all CY entities."""
        entities = []
        for s in self._cy.subsidiaries:
            entities.append((s.entity.reference_id, s.entity.name))
        return sorted(entities, key=lambda x: x[0] or x[1])

    # ─── Delegated report methods ────────────────────────────────────────

    def sch_f_rollover(self) -> RolloverReport:
        return sch_f_rollover(self._py, self._cy)

    def page1_rollover(self) -> RolloverReport:
        return page1_rollover(self._py, self._cy)

    def sch_j_rollover(self, basket: str = "GEN") -> RolloverReport:
        return sch_j_rollover(self._py, self._cy, basket=basket)

    def sch_j_gen_rollover(self) -> RolloverReport:
        return sch_j_rollover(self._py, self._cy, basket="GEN")

    def sch_j_pas_rollover(self) -> RolloverReport:
        return sch_j_rollover(self._py, self._cy, basket="PAS")

    def ep_movement(self) -> RolloverReport:
        return ep_movement(self._py, self._cy)

    def gilti_comparison(self) -> RolloverReport:
        return gilti_comparison(self._py, self._cy)

    def new_final_entities(self) -> RolloverReport:
        return new_final_entities(self._py, self._cy)

    def schedule_g_changes(self) -> RolloverReport:
        return schedule_g_changes(self._py, self._cy)

    # ─── Integration with ReviewEngine ───────────────────────────────────

    def automated_review(self) -> ReviewReport:
        """Run the automated compliance checks via ReviewEngine."""
        from lab.xml_parser.review_engine import ReviewEngine
        engine = ReviewEngine()
        return engine.review(self.cy_path, self.py_path)

    # ─── Full Review (orchestrator) ──────────────────────────────────────

    def full_review(self, output_path: Optional[str | Path] = None, include_findings: bool = True) -> dict:
        """Run all reports and generate combined output."""
        reports = {
            "Sch F Rollover": self.sch_f_rollover(),
            "Sch J Rollover": self.sch_j_rollover(),
            "Page 1 Rollover": self.page1_rollover(),
            "E&P Movement": self.ep_movement(),
            "GILTI Comparison": self.gilti_comparison(),
            "Entity Changes": self.new_final_entities(),
            "Sch G Indicators": self.schedule_g_changes(),
        }

        review_report = None
        if include_findings:
            review_report = self.automated_review()
            reports["_review_report"] = review_report

        # Terminal summary
        self.console.print(Panel.fit(
            "[bold]Project Mythos — Full Review Package[/bold]",
            style="orange1"
        ))
        self.console.print(f"\n[bold]Prior Year:[/bold] {self.py_path.name} (TY{self._py.header.tax_year})")
        self.console.print(f"[bold]Current Year:[/bold] {self.cy_path.name} (TY{self._cy.header.tax_year})")
        self.console.print(f"[bold]Entities:[/bold] PY={self._py.entity_count} | CY={self._cy.entity_count}\n")

        summary_table = Table(title="Review Summary", show_lines=True)
        summary_table.add_column("Report", style="bold", width=25)
        summary_table.add_column("Checks", justify="center", width=8)
        summary_table.add_column("Pass", justify="center", width=8, style="green")
        summary_table.add_column("Fail", justify="center", width=8, style="red")
        summary_table.add_column("Status", justify="center", width=12)

        for name, report in reports.items():
            if name.startswith("_"):
                continue
            status = "[green]CLEAN[/green]" if report.failed == 0 else f"[red]{report.failed} ISSUES[/red]"
            summary_table.add_row(
                name, str(report.total_checks), str(report.passed),
                str(report.failed), status
            )

        self.console.print(summary_table)

        if review_report and review_report.findings:
            self.console.print(f"\n[bold orange1]Automated Checks:[/bold orange1] {len(review_report.findings)} findings "
                             f"({len(review_report.high_severity())} HIGH)")
            for f in review_report.high_severity()[:10]:
                self.console.print(f"  [red]HIGH[/red]  {f.check_id}  {f.entity_code:<6}  {f.description[:60]}")

        # Excel output
        if output_path is None:
            output_path = self.cy_path.parent / f"Review_{self.cy_path.stem}.xlsx"

        self._to_excel(reports, output_path)
        self.console.print(f"\n[bold green]Excel saved:[/bold green] {output_path}")

        return reports

    def _to_excel(self, reports: dict, output_path: str | Path):
        """Export all reports to Excel via the export/ package."""
        from lab.xml_parser.export import export_excel
        review_report = reports.pop("_review_report", None)
        rollover_reports = {k: v for k, v in reports.items() if not k.startswith("_")}
        export_excel(
            output_path,
            review_report=review_report,
            rollover_reports=rollover_reports,
        )
        if review_report:
            reports["_review_report"] = review_report

    # ─── Display helpers ─────────────────────────────────────────────────

    def display_report(self, report: RolloverReport, show_pass: bool = False):
        """Display a single report in the terminal."""
        self.console.print(f"\n[bold]{report.summary}[/bold]\n")

        if report.failed == 0 and not show_pass:
            self.console.print("[green]  All checks passed — no differences found.[/green]")
            return

        table = Table(show_lines=False)
        table.add_column("Entity", style="bold", min_width=25)
        table.add_column("Ref", width=7)
        table.add_column("Line", width=6)
        table.add_column("Field", min_width=25)
        table.add_column("PY", justify="right", width=15)
        table.add_column("CY", justify="right", width=15)
        table.add_column("Diff", justify="right", width=12)
        table.add_column("", width=5)

        for item in report.items:
            if item.passes and not show_pass:
                continue

            status = "[green]✓[/green]" if item.passes else "[red]✗[/red]"

            diff_str = ""
            if item.difference and abs(item.difference) >= 1:
                if abs(item.difference) >= 1e6:
                    diff_str = f"{item.difference/1e6:+,.2f}M"
                elif abs(item.difference) >= 1000:
                    diff_str = f"{item.difference/1e3:+,.1f}K"
                else:
                    diff_str = f"{item.difference:+,.0f}"

            table.add_row(
                item.entity_name[:25],
                item.reference_id,
                item.line,
                item.field_description[:25],
                item.py_value[:15] if item.py_value else "—",
                item.cy_value[:15] if item.cy_value else "—",
                diff_str,
                status,
            )

        self.console.print(table)

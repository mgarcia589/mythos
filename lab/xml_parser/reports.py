"""Analytical Reports — Predefined checks for XML rollover review.

Business-logic reports that know WHAT should match between PY and CY,
and flag specifically when it doesn't.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.models import ParsedReturn, SubsidiaryReturn
from lab.xml_parser.field_maps import (
    SCHEDULE_F_ROLLOVER_PAIRS,
    SCHEDULE_H_FIELDS,
    SCHEDULE_I1_FIELDS,
    SCHEDULE_G_FIELDS,
    FORM_5471_FIELDS,
    format_value,
)


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
    items: list = field(default_factory=list)

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


class ReportEngine:
    """Generate predefined analytical reports from PY vs CY XML comparison."""

    def __init__(self, prior_xml: str | Path, current_xml: str | Path):
        self.py_path = Path(prior_xml)
        self.cy_path = Path(current_xml)
        self._py = EFileParser(prior_xml).parse()
        self._cy = EFileParser(current_xml).parse()
        self.console = Console()

    def _match_entities(self) -> list[tuple[SubsidiaryReturn, SubsidiaryReturn]]:
        """Match PY entities to CY entities by reference ID or name."""
        matched = []
        cy_by_ref = {s.entity.reference_id: s for s in self._cy.subsidiaries if s.entity.reference_id}
        cy_by_name = {s.entity.name.lower(): s for s in self._cy.subsidiaries}

        for py_sub in self._py.subsidiaries:
            cy_sub = cy_by_ref.get(py_sub.entity.reference_id)
            if not cy_sub:
                cy_sub = cy_by_name.get(py_sub.entity.name.lower())
            if cy_sub:
                matched.append((py_sub, cy_sub))
        return matched

    def _get_field(self, sub: SubsidiaryReturn, form: str, field_name: str) -> str:
        """Get a field value from a subsidiary's form data."""
        form_data = sub.forms.get(form)
        if not form_data:
            return ""
        # Try with prefix
        prefixed = f"{form}_{field_name}"
        val = form_data.fields.get(prefixed, "")
        if not val:
            val = form_data.fields.get(field_name, "")
        return str(val) if val else ""

    # ─────────────────────────────────────────────────────────────────
    # REPORT: Schedule F Rollover (PY End = CY Begin)
    # ─────────────────────────────────────────────────────────────────

    def sch_f_rollover(self) -> RolloverReport:
        """Check that PY ending balances equal CY beginning balances."""
        report = RolloverReport(title="Schedule F — Balance Sheet Rollover")
        matched = self._match_entities()

        for py_sub, cy_sub in matched:
            for pair in SCHEDULE_F_ROLLOVER_PAIRS:
                py_end_field, cy_begin_field, description = pair[0], pair[1], pair[2]
                line = pair[3] if len(pair) > 3 else ""
                py_val = self._get_field(py_sub, "IRS5471ScheduleF", py_end_field)
                cy_val = self._get_field(cy_sub, "IRS5471ScheduleF", cy_begin_field)

                # Also try from IRS5471 (Sch F is often inline)
                if not py_val:
                    py_val = self._get_field(py_sub, "IRS5471", f"IRS5471ScheduleF_{py_end_field}")
                if not cy_val:
                    cy_val = self._get_field(cy_sub, "IRS5471", f"IRS5471ScheduleF_{cy_begin_field}")

                try:
                    py_num = float(py_val) if py_val else 0.0
                    cy_num = float(cy_val) if cy_val else 0.0
                    diff = cy_num - py_num
                    passes = abs(diff) < 1.0
                except (ValueError, TypeError):
                    diff = 0.0
                    passes = py_val == cy_val

                # Only add if at least one value exists
                if py_val or cy_val:
                    report.items.append(RolloverItem(
                        entity_name=py_sub.entity.name,
                        reference_id=py_sub.entity.reference_id,
                        field_description=description,
                        line=line,
                        py_value=py_val,
                        cy_value=cy_val,
                        difference=diff,
                        passes=passes,
                    ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: Page 1 Rollover (Entity Info Unchanged)
    # ─────────────────────────────────────────────────────────────────

    def page1_rollover(self) -> RolloverReport:
        """Check that entity identification data rolled correctly PY→CY."""
        report = RolloverReport(title="Page 1 — Entity Information Rollover")

        # Fields that should NOT change
        static_fields = [
            ("ForeignCorporation_BusinessName_BusinessNameLine1Txt", "Entity name", "1a"),
            ("ForeignCorporation_ForeignAddress_AddressLine1Txt", "Address line 1", "1a(addr)"),
            ("ForeignCorporation_ForeignAddress_CityNm", "City", "1a(city)"),
            ("ForeignCorporation_ForeignAddress_CountryCd", "Country code", "1a(country)"),
            ("ForeignEntityIdentificationGrp_ForeignEntityReferenceIdNum", "Reference ID", "1d"),
            ("CountryUnderWhoseLawsIncCd", "Country of incorporation", "1b"),
            ("FunctionalCurrencyCd", "Functional currency", "1c"),
            ("IncorporationDt", "Incorporation date", "2b"),
            ("PrincipalPlaceOfBusCountryCd", "Principal place of business", "2a"),
            ("EIN", "EIN", "1d"),
        ]

        matched = self._match_entities()
        for py_sub, cy_sub in matched:
            for field_name, description, line in static_fields:
                py_val = self._get_field(py_sub, "IRS5471", field_name)
                cy_val = self._get_field(cy_sub, "IRS5471", field_name)

                if not py_val and not cy_val:
                    continue

                passes = py_val.strip().upper() == cy_val.strip().upper()

                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line=line,
                    py_value=py_val,
                    cy_value=cy_val,
                    passes=passes,
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: Schedule J Rollover (Accumulated E&P — totals only)
    # ─────────────────────────────────────────────────────────────────

    def sch_j_rollover(self) -> RolloverReport:
        """Check that PY ending accumulated E&P balances roll to CY beginning.

        Checks total-level groups only:
        - Post2017EPNotPrevTaxedGrp (post-2017 untaxed E&P)
        - TotalSection964AEPGrp (total Section 964(a) E&P)
        - Post1986UndistributedEarnGrp (post-1986 undistributed earnings)
        - HoveringDeficitDedSspndTaxGrp (hovering deficit)

        Logic: PY 'BalanceBeginningNextYearAmt' should = CY 'BeginningYearBalanceAmt'
        """
        report = RolloverReport(title="Schedule J — Accumulated E&P Rollover (Totals)")

        j_groups = [
            ("Post2017EPNotPrevTaxedGrp", "Post-2017 E&P Not Previously Taxed"),
            ("TotalSection964AEPGrp", "Total Section 964(a) E&P"),
            ("Post1986UndistributedEarnGrp", "Post-1986 Undistributed Earnings"),
            ("HoveringDeficitDedSspndTaxGrp", "Hovering Deficit"),
            ("Section951APTEPGrp", "Section 951A PTEP (GILTI)"),
        ]

        matched = self._match_entities()
        for py_sub, cy_sub in matched:
            for group_name, description in j_groups:
                # PY ending = BalanceBeginningNextYearAmt
                py_field = f"{group_name}_BalanceBeginningNextYearAmt"
                py_val = self._get_field(py_sub, "IRS5471ScheduleJ", py_field)

                # CY beginning = BeginningYearBalanceAmt
                cy_field = f"{group_name}_BeginningYearBalanceAmt"
                cy_val = self._get_field(cy_sub, "IRS5471ScheduleJ", cy_field)

                if not py_val and not cy_val:
                    continue

                try:
                    py_num = float(py_val) if py_val else 0.0
                    cy_num = float(cy_val) if cy_val else 0.0
                    diff = cy_num - py_num
                    passes = abs(diff) < 1.0
                except (ValueError, TypeError):
                    diff = 0.0
                    passes = py_val == cy_val

                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line="J",
                    py_value=py_val,
                    cy_value=cy_val,
                    difference=diff,
                    passes=passes,
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: E&P Movement (Sch H YoY)
    # ─────────────────────────────────────────────────────────────────

    def ep_movement(self) -> RolloverReport:
        """Compare E&P amounts PY vs CY to show year-over-year movement."""
        report = RolloverReport(title="Schedule H — E&P Year-over-Year Movement")

        ep_fields = [
            ("ForeignCYNetIncomePerBooksAmt", "Net income per books", "1"),
            ("TotalNetAdditionsAmt", "Total additions", "3"),
            ("TotalNetSubtractionsAmt", "Total subtractions", "4"),
            ("CurrentEarningsAndProfitsAmt", "Current E&P", "5a"),
            ("CurrEarnAndPrftInUSDollarsAmt", "Current E&P (USD)", "5d"),
        ]

        matched = self._match_entities()
        for py_sub, cy_sub in matched:
            for field_name, description, line in ep_fields:
                py_val = self._get_field(py_sub, "IRS5471ScheduleH", field_name)
                cy_val = self._get_field(cy_sub, "IRS5471ScheduleH", field_name)

                if not py_val and not cy_val:
                    continue

                try:
                    py_num = float(py_val) if py_val else 0.0
                    cy_num = float(cy_val) if cy_val else 0.0
                    diff = cy_num - py_num
                except (ValueError, TypeError):
                    diff = 0.0

                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line=line,
                    py_value=py_val,
                    cy_value=cy_val,
                    difference=diff,
                    passes=True,  # Movement report — no pass/fail, just shows delta
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: GILTI Comparison (Sch I-1)
    # ─────────────────────────────────────────────────────────────────

    def gilti_comparison(self) -> RolloverReport:
        """Compare GILTI tested income/QBAI PY vs CY."""
        report = RolloverReport(title="Schedule I-1 — GILTI Comparison")

        gilti_fields = [
            ("GrossIncomeAmt", "Gross income", "1"),
            ("SubpartFIncomeAmt", "Subpart F exclusion", "2b"),
            ("GrossIncomeLessTotIncmExclAmt", "Gross income less exclusions", "4"),
            ("AllocableDeductionAmt", "Allocable deductions", "5"),
            ("TestedIncomeLossGrp_USDollarAmt", "Tested income/loss (USD)", "6"),
            ("InterestExpenseAmt", "Interest expense", "9a"),
        ]

        matched = self._match_entities()
        for py_sub, cy_sub in matched:
            for field_name, description, line in gilti_fields:
                py_val = self._get_field(py_sub, "IRS5471ScheduleI1", field_name)
                cy_val = self._get_field(cy_sub, "IRS5471ScheduleI1", field_name)

                if not py_val and not cy_val:
                    continue

                try:
                    diff = float(cy_val or 0) - float(py_val or 0)
                except (ValueError, TypeError):
                    diff = 0.0

                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line=line,
                    py_value=py_val,
                    cy_value=cy_val,
                    difference=diff,
                    passes=True,
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: New/Final Entities
    # ─────────────────────────────────────────────────────────────────

    def new_final_entities(self) -> RolloverReport:
        """Identify entities added or removed between PY and CY."""
        report = RolloverReport(title="Entity Changes — New & Final Returns")

        py_refs = {s.entity.reference_id or s.entity.name: s for s in self._py.subsidiaries}
        cy_refs = {s.entity.reference_id or s.entity.name: s for s in self._cy.subsidiaries}

        # New in CY (not in PY)
        for key, cy_sub in cy_refs.items():
            if key not in py_refs:
                report.items.append(RolloverItem(
                    entity_name=cy_sub.entity.name,
                    reference_id=cy_sub.entity.reference_id,
                    field_description="NEW ENTITY (not in prior year)",
                    line="—",
                    py_value="",
                    cy_value=f"{cy_sub.entity.country_code} | {cy_sub.entity.functional_currency}",
                    passes=False,
                ))

        # Removed (in PY not in CY)
        for key, py_sub in py_refs.items():
            if key not in cy_refs:
                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description="REMOVED (final return or liquidated)",
                    line="—",
                    py_value=f"{py_sub.entity.country_code} | {py_sub.entity.functional_currency}",
                    cy_value="",
                    passes=False,
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # REPORT: Schedule G Changes (Indicator Flips)
    # ─────────────────────────────────────────────────────────────────

    def schedule_g_changes(self) -> RolloverReport:
        """Flag any Yes/No indicators that changed PY→CY."""
        report = RolloverReport(title="Schedule G — Indicator Changes")

        indicator_fields = [
            ("DisallowedInterestExpenseInd", "163(j) disallowed interest?", "15a"),
            ("BaseErosionPaymentBenefitInd", "Base erosion payments?", "6"),
            ("FDIIBenefitsClaimInd", "FDII benefits claimed?", "8"),
            ("PayOrAccrueTopUpTaxInd", "Top-up tax (Pillar Two)?", "new"),
            ("ExpatriatedFrgnSubsidiaryInd", "Expatriated subsidiary?", "4"),
            ("ForeignTaxSection909Ind", "Section 909 splitter?", "7"),
            ("ReportableTransactionPrtcptInd", "Reportable transaction?", "11"),
        ]

        matched = self._match_entities()
        for py_sub, cy_sub in matched:
            for field_name, description, line in indicator_fields:
                py_val = self._get_field(py_sub, "IRS5471", f"IRS5471ScheduleG_{field_name}")
                cy_val = self._get_field(cy_sub, "IRS5471", f"IRS5471ScheduleG_{field_name}")

                if py_val == cy_val:
                    continue
                if not py_val and not cy_val:
                    continue

                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line=line,
                    py_value=py_val or "—",
                    cy_value=cy_val or "—",
                    passes=False,
                ))

        return report

    # ─────────────────────────────────────────────────────────────────
    # FULL REVIEW (all reports combined)
    # ─────────────────────────────────────────────────────────────────

    def full_review(self, output_path: Optional[str | Path] = None) -> dict:
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
            status = "[green]CLEAN[/green]" if report.failed == 0 else f"[red]{report.failed} ISSUES[/red]"
            summary_table.add_row(
                name, str(report.total_checks), str(report.passed),
                str(report.failed), status
            )

        self.console.print(summary_table)

        # Excel output
        if output_path is None:
            output_path = self.cy_path.parent / f"Review_{self.cy_path.stem}.xlsx"

        self._to_excel(reports, output_path)
        self.console.print(f"\n[bold green]Excel saved:[/bold green] {output_path}")

        return reports

    def _to_excel(self, reports: dict, output_path: str | Path):
        """Export all reports to a professionally formatted Excel workbook."""
        from lab.xml_parser.output import export_excel
        export_excel(reports, output_path)

    # ─────────────────────────────────────────────────────────────────
    # Display helpers
    # ─────────────────────────────────────────────────────────────────

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

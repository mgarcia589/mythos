"""Form View — renders parsed XML data in IRS form layout using rich tables.

Displays data organized like the printed IRS Form 5471 schedules:
- Section headers (Part I, Part II, etc.)
- Line numbers on the left
- Descriptions in the middle
- Amounts on the right
- Comparison mode: PY | CY | Diff columns
"""

from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.style import Style

from lab.xml_parser.field_maps import (
    SCHEDULE_H_FIELDS,
    SCHEDULE_C_FIELDS,
    SCHEDULE_F_BEGIN_FIELDS,
    SCHEDULE_F_END_FIELDS,
    SCHEDULE_F_ROLLOVER_PAIRS,
    SCHEDULE_I1_FIELDS,
    SCHEDULE_E_FIELDS,
    SCHEDULE_G_FIELDS,
    SCHEDULE_I_FIELDS,
    format_value,
)


def _safe_float(value) -> float:
    """Convert value to float safely, returning 0.0 on failure."""
    if not value or value in ("", "—", "nan", "None"):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _get_raw(entity_data: dict, field_name: str, form_prefix: str = "") -> str:
    """Extract a raw field value from entity_data dict.

    Tries both direct field name and prefixed form name variants.
    """
    # Try direct field name
    if field_name in entity_data:
        return str(entity_data[field_name])
    # Try with form prefix
    prefixed = f"{form_prefix}_{field_name}" if form_prefix else ""
    if prefixed and prefixed in entity_data:
        return str(entity_data[prefixed])
    return ""


def _format_diff(py_val: float, cy_val: float) -> Text:
    """Format the difference between PY and CY with color coding."""
    diff = cy_val - py_val
    if diff == 0:
        return Text("—", style="dim")
    sign = "+" if diff > 0 else ""
    if abs(diff) >= 1e6:
        txt = f"{sign}{diff/1e6:,.2f}M"
    elif abs(diff) >= 1000:
        txt = f"{sign}{diff/1e3:,.1f}K"
    else:
        txt = f"{sign}{diff:,.0f}"
    style = "red" if diff < 0 else "green"
    return Text(txt, style=style)


class FormView:
    """Renders parsed IRS form data in formatted terminal output.

    Usage:
        view = FormView()
        # entity_data is the .fields dict from a SubsidiaryReturn's FormData
        print(view.render_schedule_h(entity_data))
    """

    def __init__(self, console: Optional[Console] = None):
        if console is not None:
            self.console = console
        else:
            # Use a file=StringIO to suppress live terminal output;
            # we only want the recorded text returned from render methods.
            import io
            self.console = Console(record=True, width=120, file=io.StringIO())

    def _render_to_string(self) -> str:
        """Export recorded console output as a string."""
        result = self.console.export_text()
        # Clear the recording buffer for next render
        self.console._record_buffer.clear()
        return result

    def render_schedule_h(self, entity_data: dict) -> str:
        """Render Schedule H — Current Earnings and Profits.

        Args:
            entity_data: Dict of field_name -> value (from FormData.fields
                         or a flattened DataFrame row).
        """
        table = Table(
            title="Schedule H — Current Earnings and Profits",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Line", style="dim", width=8, justify="right")
        table.add_column("Description", width=50)
        table.add_column("Amount", justify="right", width=20)

        # Ordered line items as they appear on the printed form
        line_order = [
            "ForeignCYNetIncomePerBooksAmt",
            "CapitalGainsOrLossesAmt",
            "DepreciationAndAmortizationAmt",
            "DepletionAmt",
            "InvestmentOrIncentiveAllwncAmt",
            "ChargesToStatutoryReservesAmt",
            "InventoryAdjustmentsAmt",
            "TaxesNetAddnAmt",
            "FrgnCurrencyGainLossAddnAmt",
            "OtherAdjustmentsNetAddnAmt",
            "OtherAdjustmentsNetSbtrctnAmt",
            "TotalNetAdditionsAmt",
            "TotalNetSubtractionsAmt",
            "CurrentEarningsAndProfitsAmt",
            "DASTMGainOrLossAmt",
            "EarningAndPrftPlusDASTMGainAmt",
            "CurrEarnAndPrftInUSDollarsAmt",
            "ExchangeRt",
            "EPDASTMPassiveCatIncmAmt",
            "EPDASTMGeneralCatIncmAmt",
        ]

        for field_name in line_order:
            info = SCHEDULE_H_FIELDS.get(field_name, {})
            raw = _get_raw(entity_data, field_name, "IRS5471ScheduleH")
            formatted = format_value(raw, info)
            table.add_row(
                info.get("line", "?"),
                info.get("description", field_name),
                formatted,
            )

        self.console.print(table)
        return self._render_to_string()

    def render_schedule_c(self, entity_data: dict) -> str:
        """Render Schedule C — Income Statement.

        Args:
            entity_data: Dict of field_name -> value.
        """
        table = Table(
            title="Schedule C — Income Statement",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Line", style="dim", width=8, justify="right")
        table.add_column("Description", width=50)
        table.add_column("Amount", justify="right", width=20)

        # Part I — Income
        table.add_row("", Text("Part I — Income", style="bold underline"), "")

        income_fields = [
            "ForeignGrossReceiptsOrSalesAmt",
            "ForeignReturnsAndAllowancesAmt",
            "ForeignCostOfGoodsSoldAmt",
            "ForeignGrossProfitAmt",
            "ForeignDividendIncomeAmt",
            "ForeignInterestIncomeAmt",
            "ForeignNetRentRoyaltyIncomeAmt",
            "ForeignNetGainLossAmt",
            "ForeignOtherIncomeAmt",
            "ForeignTotalIncomeAmt",
        ]

        for field_name in income_fields:
            info = SCHEDULE_C_FIELDS.get(field_name, {})
            raw = _get_raw(entity_data, field_name, "IRS5471ScheduleC")
            formatted = format_value(raw, info)
            table.add_row(
                info.get("line", "?"),
                info.get("description", field_name),
                formatted,
            )

        # Part II — Deductions
        table.add_row("", "", "")
        table.add_row("", Text("Part II — Deductions", style="bold underline"), "")

        deduction_fields = [
            "ForeignCompensationNotDeductedAmt",
            "ForeignInterestExpenseAmt",
            "ForeignTaxesAmt",
            "ForeignDepreciationNotDeductedAmt",
            "ForeignOtherDeductionsAmt",
            "ForeignTotalDeductionsAmt",
        ]

        for field_name in deduction_fields:
            info = SCHEDULE_C_FIELDS.get(field_name, {})
            raw = _get_raw(entity_data, field_name, "IRS5471ScheduleC")
            formatted = format_value(raw, info)
            table.add_row(
                info.get("line", "?"),
                info.get("description", field_name),
                formatted,
            )

        # Net income
        table.add_row("", "", "")
        table.add_row("", Text("Net Income", style="bold underline"), "")
        ni_info = SCHEDULE_C_FIELDS.get("ForeignCYNetIncomePerBookAmt", {})
        ni_raw = _get_raw(entity_data, "ForeignCYNetIncomePerBookAmt", "IRS5471ScheduleC")
        table.add_row(
            ni_info.get("line", "21"),
            ni_info.get("description", "Net income per books"),
            format_value(ni_raw, ni_info),
        )

        self.console.print(table)
        return self._render_to_string()

    def render_schedule_f(self, entity_data: dict) -> str:
        """Render Schedule F — Balance Sheet (Beginning and End of period).

        Args:
            entity_data: Dict of field_name -> value.
        """
        table = Table(
            title="Schedule F — Balance Sheet",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Line", style="dim", width=6, justify="right")
        table.add_column("Description", width=42)
        table.add_column("Beginning", justify="right", width=18)
        table.add_column("End", justify="right", width=18)

        # Assets section
        table.add_row("", Text("ASSETS", style="bold underline"), "", "")

        asset_lines = [
            ("1", "Cash", "BegngAcctPrdCashAmt", "EndAcctPrdCashAmt"),
            ("2", "Trade notes & accounts receivable", "BegngAcctPrdTradeNotesAmt", "EndAcctPrdTradeNotesAmt"),
            ("3", "Inventories", "BegngAcctPrdInventoriesAmt", "EndAcctPrdInventoriesAmt"),
            ("4", "Investment in subsidiaries", "BegngAcctPrdInvstSubsidiaryAmt", "EndAcctPrdInvstSubsidiaryAmt"),
            ("5", "Buildings & other depreciable assets", "BegngAcctPrdBldgAndOtherAstAmt", "EndAcctPrdBldgAndOtherAstAmt"),
            ("6", "Land", "BegngAcctPrdLandAmt", "EndAcctPrdLandAmt"),
            ("7", "Intangible assets", "BegngAcctPrdPatentsOthAstAmt", "EndAcctPrdPatentsOthAstAmt"),
            ("8", "Other assets", "BegngAcctPrdOtherAssetsAmt", "EndAcctPrdOtherAssetsAmt"),
            ("9", "Total assets", "BegngAcctPrdTotalAssetsAmt", "EndAcctPrdTotalAssetsAmt"),
        ]

        for line_num, desc, beg_field, end_field in asset_lines:
            beg_raw = _get_raw(entity_data, beg_field, "IRS5471ScheduleF")
            end_raw = _get_raw(entity_data, end_field, "IRS5471ScheduleF")
            beg_info = SCHEDULE_F_BEGIN_FIELDS.get(beg_field, {"type": "amount"})
            end_info = SCHEDULE_F_END_FIELDS.get(end_field, {"type": "amount"})
            style = "bold" if line_num == "9" else ""
            table.add_row(
                line_num,
                Text(desc, style=style),
                format_value(beg_raw, beg_info),
                format_value(end_raw, end_info),
            )

        # Liabilities & Equity section
        table.add_row("", "", "", "")
        table.add_row("", Text("LIABILITIES & SHAREHOLDERS EQUITY", style="bold underline"), "", "")

        liab_lines = [
            ("10", "Accounts payable", "BegngAcctPrdAccountsPayableAmt", "EndAcctPrdAccountsPayableAmt"),
            ("11", "Other current liabilities", "BegngAcctPrdOtherCurrLiabAmt", "EndAcctPrdOtherCurrLiabAmt"),
            ("12", "Other liabilities", "BegngAcctPrdOthLiabilitiesAmt", "EndAcctPrdOthLiabilitiesAmt"),
            ("13", "Capital stock", "BegngAcctPrdCommonStockAmt", "EndAcctPrdCommonStockAmt"),
            ("14", "Paid-in or capital surplus", "BegngAcctPrdPaidInOrSurplusAmt", "EndAcctPrdPaidInOrSurplusAmt"),
            ("15", "Retained earnings", "BegngAcctPrdRtnEarningsAmt", "EndAcctPrdRtnEarningsAmt"),
            ("16", "Total liabilities & shareholders equity", "BegngAcctPrdTotLiabShrEqtyAmt", "EndAcctPrdTotLiabShrEqtyAmt"),
        ]

        for line_num, desc, beg_field, end_field in liab_lines:
            beg_raw = _get_raw(entity_data, beg_field, "IRS5471ScheduleF")
            end_raw = _get_raw(entity_data, end_field, "IRS5471ScheduleF")
            beg_info = SCHEDULE_F_BEGIN_FIELDS.get(beg_field, {"type": "amount"})
            end_info = SCHEDULE_F_END_FIELDS.get(end_field, {"type": "amount"})
            style = "bold" if line_num == "16" else ""
            table.add_row(
                line_num,
                Text(desc, style=style),
                format_value(beg_raw, beg_info),
                format_value(end_raw, end_info),
            )

        self.console.print(table)
        return self._render_to_string()

    def render_comparison(self, py_data: dict, cy_data: dict, form: str) -> str:
        """Render PY vs CY comparison for a given schedule.

        Args:
            py_data: Prior year entity field data.
            cy_data: Current year entity field data.
            form: One of "H", "C", "F", "I1", "E", "G", "I".

        Returns:
            Formatted string with PY | CY | Diff columns.
        """
        form_map = {
            "H": ("Schedule H — E&P Comparison", SCHEDULE_H_FIELDS, "IRS5471ScheduleH"),
            "C": ("Schedule C — Income Statement Comparison", SCHEDULE_C_FIELDS, "IRS5471ScheduleC"),
            "F": ("Schedule F — Balance Sheet Comparison", {**SCHEDULE_F_BEGIN_FIELDS, **SCHEDULE_F_END_FIELDS}, "IRS5471ScheduleF"),
            "I1": ("Schedule I-1 — GILTI Comparison", SCHEDULE_I1_FIELDS, "IRS5471ScheduleI1"),
            "E": ("Schedule E — Foreign Taxes Comparison", SCHEDULE_E_FIELDS, "IRS5471ScheduleE"),
            "G": ("Schedule G — Other Information Comparison", SCHEDULE_G_FIELDS, "IRS5471ScheduleG"),
            "I": ("Schedule I — Subpart F Comparison", SCHEDULE_I_FIELDS, "IRS5471ScheduleI"),
        }

        if form not in form_map:
            return f"[ERROR] Unknown form: {form}. Valid: {', '.join(form_map.keys())}"

        title, fields, prefix = form_map[form]

        table = Table(
            title=title,
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Line", style="dim", width=8, justify="right")
        table.add_column("Description", width=40)
        table.add_column("PY", justify="right", width=16)
        table.add_column("CY", justify="right", width=16)
        table.add_column("Diff", justify="right", width=14)

        for field_name, info in fields.items():
            py_raw = _get_raw(py_data, field_name, prefix)
            cy_raw = _get_raw(cy_data, field_name, prefix)

            if info.get("type") == "amount":
                py_formatted = format_value(py_raw, info)
                cy_formatted = format_value(cy_raw, info)
                py_num = _safe_float(py_raw)
                cy_num = _safe_float(cy_raw)
                # Flip sign if convention requires it
                if info.get("sign") == "negative_is_income":
                    py_num = -py_num
                    cy_num = -cy_num
                diff_text = _format_diff(py_num, cy_num)
            elif info.get("type") == "indicator":
                py_formatted = format_value(py_raw, info)
                cy_formatted = format_value(cy_raw, info)
                if py_formatted != cy_formatted:
                    diff_text = Text("CHANGED", style="yellow bold")
                else:
                    diff_text = Text("—", style="dim")
            else:
                py_formatted = format_value(py_raw, info)
                cy_formatted = format_value(cy_raw, info)
                diff_text = Text("—", style="dim")

            table.add_row(
                info.get("line", "?"),
                info.get("description", field_name),
                py_formatted,
                cy_formatted,
                diff_text,
            )

        self.console.print(table)
        return self._render_to_string()

    def render_rollover_check(self, py_data: dict, cy_data: dict) -> str:
        """Check that PY End balances equal CY Beginning balances (Schedule F).

        This is a critical compliance check — the ending balance sheet of the
        prior year must roll into the beginning balance sheet of the current year.

        Args:
            py_data: Prior year entity field data (needs EndAcctPrd* fields).
            cy_data: Current year entity field data (needs BegngAcctPrd* fields).

        Returns:
            Formatted string with pass/fail for each balance sheet line.
        """
        table = Table(
            title="Schedule F — Rollover Check (PY End = CY Begin)",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
            show_lines=False,
        )
        table.add_column("Line", style="dim", width=6, justify="right")
        table.add_column("Description", width=42)
        table.add_column("PY End", justify="right", width=16)
        table.add_column("CY Begin", justify="right", width=16)
        table.add_column("Status", justify="center", width=10)

        mismatches = 0
        amt_info = {"type": "amount"}

        for py_end_field, cy_beg_field, description in SCHEDULE_F_ROLLOVER_PAIRS:
            py_raw = _get_raw(py_data, py_end_field, "IRS5471ScheduleF")
            cy_raw = _get_raw(cy_data, cy_beg_field, "IRS5471ScheduleF")

            py_val = _safe_float(py_raw)
            cy_val = _safe_float(cy_raw)

            py_formatted = format_value(py_raw, amt_info) if py_raw else "—"
            cy_formatted = format_value(cy_raw, amt_info) if cy_raw else "—"

            # Check if values match (within floating-point tolerance)
            if abs(py_val - cy_val) < 0.01:
                status = Text("PASS", style="green bold")
            else:
                status = Text("FAIL", style="red bold")
                mismatches += 1

            # Extract line number from the end field info
            end_info = SCHEDULE_F_END_FIELDS.get(py_end_field, {})
            line_num = end_info.get("line", "?").replace("(b)", "")

            table.add_row(line_num, description, py_formatted, cy_formatted, status)

        # Summary row
        table.add_row("", "", "", "", "")
        if mismatches == 0:
            summary = Text("ALL LINES MATCH", style="green bold")
        else:
            summary = Text(f"{mismatches} MISMATCH(ES)", style="red bold")
        table.add_row("", Text("RESULT", style="bold"), "", "", summary)

        self.console.print(table)
        return self._render_to_string()

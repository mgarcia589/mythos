"""Movement reports — Year-over-year comparison (no pass/fail, shows deltas).

Generates RolloverReport objects for:
- E&P Movement (Sch H fields YoY)
- Sch H Detail (additions/subtractions line items)
- GILTI Comparison (Sch I-1 fields YoY)
- GILTI Detail (QBAI, tested taxes, HTE)
- Sch E Tax Summary (foreign taxes by entity)
"""

from __future__ import annotations

from lab.xml_parser.core.models import RolloverItem, RolloverReport
from lab.xml_parser.models import ParsedReturn, SubsidiaryReturn
from lab.xml_parser.reports.rollover import _match_entities, _get_field


# ─────────────────────────────────────────────────────────────────
# E&P Movement (Sch H YoY)
# ─────────────────────────────────────────────────────────────────

_EP_FIELDS = [
    ("ForeignCYNetIncomePerBooksAmt", "Net income per books", "1"),
    ("TotalNetAdditionsAmt", "Total additions", "3"),
    ("TotalNetSubtractionsAmt", "Total subtractions", "4"),
    ("CurrentEarningsAndProfitsAmt", "Current E&P", "5a"),
    ("CurrEarnAndPrftInUSDollarsAmt", "Current E&P (USD)", "5d"),
]


def ep_movement(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Compare E&P amounts PY vs CY to show year-over-year movement."""
    report = RolloverReport(title="Schedule H — E&P Year-over-Year Movement")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _EP_FIELDS:
            py_val = _get_field(py_sub, "IRS5471ScheduleH", field_name)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleH", field_name)

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
# GILTI Comparison (Sch I-1 YoY)
# ─────────────────────────────────────────────────────────────────

_GILTI_FIELDS = [
    ("GrossIncomeAmt", "Gross income", "1"),
    ("SubpartFIncomeAmt", "Subpart F exclusion", "2b"),
    ("GrossIncomeLessTotIncmExclAmt", "Gross income less exclusions", "4"),
    ("AllocableDeductionAmt", "Allocable deductions", "5"),
    ("TestedIncomeLossGrp_USDollarAmt", "Tested income/loss (USD)", "6"),
    ("InterestExpenseAmt", "Interest expense", "9a"),
]


def gilti_comparison(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Compare GILTI tested income/QBAI PY vs CY."""
    report = RolloverReport(title="Schedule I-1 — GILTI Comparison")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _GILTI_FIELDS:
            py_val = _get_field(py_sub, "IRS5471ScheduleI1", field_name)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleI1", field_name)

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
# Sch H Detail — Additions & Subtractions (line items YoY)
# ─────────────────────────────────────────────────────────────────

_SCH_H_DETAIL_FIELDS = [
    ("ForeignCYNetIncomePerBooksAmt", "Net income per books", "1"),
    ("CapitalGainsOrLossesAmt", "Capital gains/losses (add)", "2a"),
    ("DepreciationAndAmortizationAmt", "Depreciation & amortization (add)", "2b"),
    ("DepletionAmt", "Depletion (add)", "2c"),
    ("InvestmentOrIncentiveAllwncAmt", "Investment/incentive allowance (add)", "2d"),
    ("ChargesToStatutoryReservesAmt", "Charges to statutory reserves (add)", "2e"),
    ("InventoryAdjustmentsAmt", "Inventory adjustments (add)", "2f"),
    ("TaxesNetAddnAmt", "Taxes - net addition (add)", "2g"),
    ("FrgnCurrencyGainLossAddnAmt", "Foreign currency gain/loss (add)", "2h"),
    ("OtherAdjustmentsNetAddnAmt", "Other adjustments (add)", "2i"),
    ("TotalNetAdditionsAmt", "Total additions", "3"),
    ("TotalNetSubtractionsAmt", "Total subtractions", "4"),
    ("CurrentEarningsAndProfitsAmt", "Current E&P (FC)", "5a"),
    ("DASTMGainOrLossAmt", "DASTM gain/loss", "5b"),
    ("EarningAndPrftPlusDASTMGainAmt", "E&P + DASTM", "5c"),
    ("CurrEarnAndPrftInUSDollarsAmt", "Current E&P (USD)", "5d"),
    ("ExchangeRt", "Exchange rate", "5d(fx)"),
]


def sch_h_detail(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Sch H line-item detail YoY — additions, subtractions, DASTM."""
    report = RolloverReport(title="Schedule H — E&P Detail (Additions/Subtractions)")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _SCH_H_DETAIL_FIELDS:
            py_val = _get_field(py_sub, "IRS5471ScheduleH", field_name)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleH", field_name)

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
# GILTI Detail — QBAI, Tested Taxes, HTE
# ─────────────────────────────────────────────────────────────────

_GILTI_DETAIL_FIELDS = [
    ("GrossIncomeAmt", "Gross income", "1"),
    ("ExclGrossIncmEffCntdFCCorpAmt", "ECI exclusion", "2a"),
    ("ExclGrossIncmSubpartFIncmAmt", "Subpart F exclusion", "2b"),
    ("ExclGrossIncmHghTxdIncmAmt", "High-taxed exclusion (HTE)", "2c"),
    ("ExclGrossIncmDvdRcvdAmt", "Dividend exclusion", "2d"),
    ("TotalExclusionsAmt", "Total exclusions", "3"),
    ("GrossIncmLessExclusionsAmt", "Gross less exclusions", "4"),
    ("AllocableDedExpnssAmt", "Allocable deductions", "5"),
    ("TestedIncomeAmt", "Tested income", "6a"),
    ("TestedLossAmt", "Tested loss", "6b"),
    ("QBAIAmt", "QBAI", "7"),
    ("TestedInterestExpenseAmt", "Tested interest expense", "8"),
    ("TestedInterestIncomeAmt", "Tested interest income", "9"),
]


def gilti_detail(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Full GILTI detail with QBAI, tested taxes, HTE — all I-1 lines YoY."""
    report = RolloverReport(title="Schedule I-1 — GILTI Detail (QBAI/HTE/Taxes)")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _GILTI_DETAIL_FIELDS:
            py_val = _get_field(py_sub, "IRS5471ScheduleI1", field_name)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleI1", field_name)

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
# Sch E — Foreign Tax Summary (by entity)
# ─────────────────────────────────────────────────────────────────

_SCH_E_FIELDS = [
    ("Frm5471SchETestedIncomeGrp_TotalTaxInFuncCurrencyAmt", "Tested taxes (FC)", "E-tested"),
    ("Frm5471SchETestedIncomeGrp_TotalTaxInUSDollarsAmt", "Tested taxes (USD)", "E-tested$"),
    ("Frm5471SchESubpartFIncomeGrp_TotalTaxInFuncCurrencyAmt", "SubF taxes (FC)", "E-subf"),
    ("Frm5471SchESubpartFIncomeGrp_TotalTaxInUSDollarsAmt", "SubF taxes (USD)", "E-subf$"),
    ("Frm5471SchEGeneralCatIncmGrp_TotalTaxInFuncCurrencyAmt", "General cat taxes (FC)", "E-gen"),
    ("Frm5471SchEGeneralCatIncmGrp_TotalTaxInUSDollarsAmt", "General cat taxes (USD)", "E-gen$"),
    ("Frm5471SchEPassiveCatIncmGrp_TotalTaxInFuncCurrencyAmt", "Passive cat taxes (FC)", "E-pas"),
    ("Frm5471SchEPassiveCatIncmGrp_TotalTaxInUSDollarsAmt", "Passive cat taxes (USD)", "E-pas$"),
]


def sch_e_tax_summary(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Foreign tax summary from Sch E — taxes by category, YoY."""
    report = RolloverReport(title="Schedule E — Foreign Tax Summary")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _SCH_E_FIELDS:
            py_val = _get_field(py_sub, "IRS5471ScheduleE", field_name)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleE", field_name)

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

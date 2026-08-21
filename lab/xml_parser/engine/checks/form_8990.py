"""Form 8990 checks (BIE-001 to BIE-013): Section 163(j) limitation validation.

Per-entity validation of business interest expense limitation calculations.
Each CFC with BIE gets its own Form 8990 — this module validates the math
on every instance in the return.
"""

from __future__ import annotations

import math

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_form_8990_checks(ctx: CheckContext) -> list[Finding]:
    """Run all Section 163(j) / Form 8990 checks."""
    parser = ctx.parser

    df_8990 = parser.extract_form("IRS8990")
    if df_8990.empty:
        return ctx.findings

    df_8990 = df_8990.set_index("_reference_id")

    cfc_group_flags = set()
    for code in df_8990.index:
        if code == "":
            continue
        row = df_8990.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        cfc_group_flags.add(_str_flag(row, "IRS8990_CFCGroupElectionInd"))

    has_mixed_group = len(cfc_group_flags - {None}) > 1

    for code in df_8990.index:
        if code == "":
            continue
        row = df_8990.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        if _str_flag(row, "IRS8990_FrmFldBySpcfdGrpParentInd"):
            continue

        name = _entity_name(row) or ctx.entity_name(code)
        is_cfc_group = _str_flag(row, "IRS8990_CFCGroupElectionInd")

        _check_ati_math(ctx, code, name, row)
        _check_30_pct(ctx, code, name, row, is_cfc_group)
        _check_limitation_total(ctx, code, name, row, is_cfc_group)
        _check_disallowed_math(ctx, code, name, row)
        _check_deduction_within_limit(ctx, code, name, row)
        _check_bie_consistency(ctx, code, name, row)
        _check_carryforward_nonneg(ctx, code, name, row)
        _check_allowable_total(ctx, code, name, row)
        _check_additions_gte_bie(ctx, code, name, row)
        _check_negative_ati(ctx, code, name, row)
        _check_net_creditor(ctx, code, name, row)

    if has_mixed_group:
        _check_group_consistency(ctx, cfc_group_flags)

    _check_rollover(ctx, df_8990)

    return ctx.findings


def _entity_name(row: pd.Series) -> str:
    name = row.get("IRS8990_ForeignEntityName_BusinessNameLine1Txt", "")
    if isinstance(name, str) and name.strip():
        return name.strip()
    name = row.get("_entity_name", "")
    return name if isinstance(name, str) else ""


def _str_flag(row: pd.Series, col: str) -> bool | None:
    val = row.get(col, "")
    if not isinstance(val, str):
        if pd.isna(val):
            return None
        val = str(val)
    val = val.strip().upper()
    if val in ("X", "TRUE", "1", "YES", "Y"):
        return True
    if val in ("", "FALSE", "0", "NO", "N"):
        return False
    return None


def _val(row: pd.Series, col: str) -> float:
    v = safe_float(row, col)
    return v if v is not None else 0.0


def _has(row: pd.Series, col: str) -> bool:
    v = safe_float(row, col)
    return v is not None


def _check_ati_math(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-001: ATI = Taxable Income + Additions - Reductions."""
    ti = _val(row, "IRS8990_TaxableIncomeAmt")
    additions = _val(row, "IRS8990_TotalAdditionsAmt")
    reductions = _val(row, "IRS8990_TotalReductionsAmt")
    ati = _val(row, "IRS8990_AdjustedTaxableIncomeAmt")

    if not _has(row, "IRS8990_AdjustedTaxableIncomeAmt"):
        return
    if ti == 0 and additions == 0 and reductions == 0 and ati == 0:
        return

    expected = ti + additions - reductions
    delta = abs(ati - expected)

    if delta > 1:
        ctx.add(
            check_id="BIE-001", severity="HIGH", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"ATI calculation mismatch: reported ${ati:,.0f} vs expected ${expected:,.0f}",
            expected=f"TI({ti:,.0f}) + Additions({additions:,.0f}) - Reductions({reductions:,.0f}) = {expected:,.0f}",
            actual=f"AdjustedTaxableIncomeAmt = {ati:,.0f}",
            delta=delta,
            context="Form 8990 Line 15: ATI = Line 1 + Line 8 - Line 14",
        )


def _check_30_pct(ctx: CheckContext, code: str, name: str, row: pd.Series, is_cfc_group: bool | None):
    """BIE-002: Applicable % = ATI × 30%."""
    if is_cfc_group:
        return

    ati = _val(row, "IRS8990_AdjustedTaxableIncomeAmt")
    pct_amt = _val(row, "IRS8990_AdjTaxableIncomeApplcblPctAmt")

    if not _has(row, "IRS8990_AdjTaxableIncomeApplcblPctAmt"):
        return

    expected = max(ati * 0.30, 0)
    delta = abs(pct_amt - expected)

    if delta > 1:
        ctx.add(
            check_id="BIE-002", severity="HIGH", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"30% ATI calculation: reported ${pct_amt:,.0f} vs expected ${expected:,.0f}",
            expected=f"ATI({ati:,.0f}) × 30% = {expected:,.0f}",
            actual=f"AdjTaxableIncomeApplcblPctAmt = {pct_amt:,.0f}",
            delta=delta,
            context="Form 8990 Line 23: ATI × applicable percentage (30% for most filers)",
        )


def _check_limitation_total(ctx: CheckContext, code: str, name: str, row: pd.Series, is_cfc_group: bool | None):
    """BIE-003: Limitation = BII + 30% ATI."""
    if is_cfc_group:
        return

    bii = _val(row, "IRS8990_TotalBusinessInterestIncomeAmt")
    pct_amt = _val(row, "IRS8990_AdjTaxableIncomeApplcblPctAmt")
    limitation = _val(row, "IRS8990_TotalBusIntExpnsLimitationAmt")

    if not _has(row, "IRS8990_TotalBusIntExpnsLimitationAmt"):
        return

    expected = bii + pct_amt
    delta = abs(limitation - expected)

    if delta > 1:
        ctx.add(
            check_id="BIE-003", severity="HIGH", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Limitation total: reported ${limitation:,.0f} vs expected ${expected:,.0f}",
            expected=f"BII({bii:,.0f}) + 30% ATI({pct_amt:,.0f}) = {expected:,.0f}",
            actual=f"TotalBusIntExpnsLimitationAmt = {limitation:,.0f}",
            delta=delta,
            context="Form 8990 Line 25: Total limitation = Line 21 + Line 23",
        )


def _check_disallowed_math(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-004: Disallowed = Total Allowable - Deducted."""
    allowable = _val(row, "IRS8990_TotalAllowableBusIntExpnsAmt")
    deducted = _val(row, "IRS8990_TotCYBusinessIntExpnsDedAmt")
    disallowed = _val(row, "IRS8990_DisallowedBusInterestExpnsAmt")

    if not _has(row, "IRS8990_DisallowedBusInterestExpnsAmt"):
        return
    if allowable == 0 and deducted == 0 and disallowed == 0:
        return
    # When both deducted and disallowed are 0, the calculation either
    # happens at the CFC group consolidation level or entity has no activity.
    if deducted == 0 and disallowed == 0:
        return

    expected = allowable - deducted
    delta = abs(disallowed - expected)

    if delta > 1:
        ctx.add(
            check_id="BIE-004", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Disallowed BIE math: reported ${disallowed:,.0f} vs expected ${expected:,.0f}",
            expected=f"Allowable({allowable:,.0f}) - Deducted({deducted:,.0f}) = {expected:,.0f}",
            actual=f"DisallowedBusInterestExpnsAmt = {disallowed:,.0f}",
            delta=delta,
            context="Form 8990 Line 33: Disallowed = Line 29 - Line 31",
        )


def _check_deduction_within_limit(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-005: Deduction ≤ Limitation."""
    deducted = _val(row, "IRS8990_TotCYBusinessIntExpnsDedAmt")
    limitation = _val(row, "IRS8990_TotalBusIntExpnsLimitationAmt")

    if deducted == 0 or not _has(row, "IRS8990_TotalBusIntExpnsLimitationAmt"):
        return

    if deducted > limitation + 1:
        ctx.add(
            check_id="BIE-005", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"BIE deduction (${deducted:,.0f}) exceeds limitation (${limitation:,.0f})",
            expected=f"Deduction ≤ Limitation ({limitation:,.0f})",
            actual=f"TotCYBusinessIntExpnsDedAmt = {deducted:,.0f}",
            delta=deducted - limitation,
            context="Form 8990: CY deduction cannot exceed the 163(j) limitation",
        )


def _check_bie_consistency(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-006: Line 4 BIE == Line 27 BIE (internal form consistency)."""
    line4 = _val(row, "IRS8990_BusInterestExpnsNotPassThruAmt")
    line27 = _val(row, "IRS8990_CYBusIntExpnsBfr163jLmtAmt")

    if not _has(row, "IRS8990_BusInterestExpnsNotPassThruAmt"):
        return
    if not _has(row, "IRS8990_CYBusIntExpnsBfr163jLmtAmt"):
        return
    if line4 == 0 and line27 == 0:
        return

    delta = abs(line4 - line27)
    if delta > 1:
        ctx.add(
            check_id="BIE-006", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"BIE inconsistency: Line 4 (${line4:,.0f}) ≠ Line 27 (${line27:,.0f})",
            expected=f"Line 4 ({line4:,.0f}) = Line 27 ({line27:,.0f})",
            actual=f"Δ = {delta:,.0f}",
            delta=delta,
            context="Form 8990: Business interest expense on Line 4 should match Line 27",
        )


def _check_carryforward_nonneg(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-007: Carryforward must be ≥ 0."""
    cfwd = _val(row, "IRS8990_CfwdPrevDsallwIntExpenseAmt")

    if not _has(row, "IRS8990_CfwdPrevDsallwIntExpenseAmt"):
        return

    if cfwd < 0:
        ctx.add(
            check_id="BIE-007", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Negative carryforward: ${cfwd:,.0f}",
            expected="CfwdPrevDsallwIntExpenseAmt ≥ 0",
            actual=f"{cfwd:,.0f}",
            delta=abs(cfwd),
            context="Carryforward of previously disallowed interest cannot be negative — sign convention error",
        )


def _check_allowable_total(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-008: Total allowable = CY BIE + Carryforward."""
    cy_bie = _val(row, "IRS8990_CYBusIntExpnsBfr163jLmtAmt")
    cfwd = _val(row, "IRS8990_CfwdPrevDsallwIntExpenseAmt")
    total = _val(row, "IRS8990_TotalAllowableBusIntExpnsAmt")

    if not _has(row, "IRS8990_TotalAllowableBusIntExpnsAmt"):
        return
    if cy_bie == 0 and cfwd == 0 and total == 0:
        return

    expected = cy_bie + cfwd
    delta = abs(total - expected)

    if delta > 1:
        ctx.add(
            check_id="BIE-008", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Total allowable BIE: reported ${total:,.0f} vs expected ${expected:,.0f}",
            expected=f"CY BIE({cy_bie:,.0f}) + Cfwd({cfwd:,.0f}) = {expected:,.0f}",
            actual=f"TotalAllowableBusIntExpnsAmt = {total:,.0f}",
            delta=delta,
            context="Form 8990 Line 29: Total allowable = Line 27 + Line 28",
        )


def _check_additions_gte_bie(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-009: Total additions ≥ BIE add-back."""
    bie = _val(row, "IRS8990_BusInterestExpnsNotPassThruAmt")
    additions = _val(row, "IRS8990_TotalAdditionsAmt")

    if bie == 0 or not _has(row, "IRS8990_TotalAdditionsAmt"):
        return

    if additions < bie - 1:
        ctx.add(
            check_id="BIE-009", severity="LOW", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Total additions (${additions:,.0f}) < BIE add-back (${bie:,.0f})",
            expected=f"TotalAdditionsAmt ≥ BusInterestExpnsNotPassThruAmt ({bie:,.0f})",
            actual=f"TotalAdditionsAmt = {additions:,.0f}",
            delta=bie - additions,
            context="Form 8990 Line 8 should include at minimum the Line 4 BIE add-back",
        )


def _check_negative_ati(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-010: Negative ATI → 30% amount should be 0."""
    ati = _val(row, "IRS8990_AdjustedTaxableIncomeAmt")
    pct_amt = _val(row, "IRS8990_AdjTaxableIncomeApplcblPctAmt")

    if not _has(row, "IRS8990_AdjTaxableIncomeApplcblPctAmt"):
        return
    if ati >= 0:
        return

    if pct_amt > 1:
        ctx.add(
            check_id="BIE-010", severity="MEDIUM", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Negative ATI (${ati:,.0f}) but 30% amount is ${pct_amt:,.0f} (should be $0)",
            expected="AdjTaxableIncomeApplcblPctAmt = 0 when ATI < 0",
            actual=f"{pct_amt:,.0f}",
            delta=pct_amt,
            context="When ATI is negative, the applicable percentage is floored at zero",
        )


def _check_group_consistency(ctx: CheckContext, flags: set):
    """BIE-011: CFC Group election should be uniform across all entities."""
    if True in flags and False in flags:
        ctx.add(
            check_id="BIE-011", severity="LOW", category="section_163j",
            entity_code="ALL", entity_name="All Entities (CFC Group Election)",
            description="CFC Group Election indicator is inconsistent across entities",
            expected="All entities should have the same CFCGroupElectionInd value",
            actual="Mixed true/false values in the return",
            context="CFC Group Election under 163(j) is a group-wide election — mixed flags indicate a data error",
        )


def _check_net_creditor(ctx: CheckContext, code: str, name: str, row: pd.Series):
    """BIE-012: Net creditor (no carryforward) should not have disallowed BIE."""
    bii = _val(row, "IRS8990_TotalBusinessInterestIncomeAmt")
    bie = _val(row, "IRS8990_CYBusIntExpnsBfr163jLmtAmt")
    allowable = _val(row, "IRS8990_TotalAllowableBusIntExpnsAmt")
    limitation = _val(row, "IRS8990_TotalBusIntExpnsLimitationAmt")
    disallowed = _val(row, "IRS8990_DisallowedBusInterestExpnsAmt")

    if bie == 0 or bii == 0:
        return
    # Only flag when limitation exceeds total allowable (meaning math should allow full deduction)
    if limitation == 0 or allowable == 0:
        return

    if limitation >= allowable and disallowed > 1:
        ctx.add(
            check_id="BIE-012", severity="LOW", category="section_163j",
            entity_code=code, entity_name=name,
            description=f"Limitation (${limitation:,.0f}) >= Allowable (${allowable:,.0f}) but disallowed = ${disallowed:,.0f}",
            expected="DisallowedBusInterestExpnsAmt = 0 when limitation covers total allowable",
            actual=f"Disallowed = {disallowed:,.0f}",
            delta=disallowed,
            context="When the 163(j) limitation exceeds total allowable BIE, nothing should be disallowed",
        )


def _check_rollover(ctx: CheckContext, df_8990: pd.DataFrame):
    """BIE-013: PY disallowed should equal CY carryforward."""
    if not hasattr(ctx, "prior_parser") or ctx.prior_parser is None:
        return

    prior_8990 = ctx.prior_parser.extract_form("IRS8990")
    if prior_8990.empty:
        return

    prior_8990 = prior_8990.set_index("_reference_id")

    common_codes = set(df_8990.index) & set(prior_8990.index)
    for code in common_codes:
        if code == "":
            continue

        cy_row = df_8990.loc[code]
        py_row = prior_8990.loc[code]
        if isinstance(cy_row, pd.DataFrame):
            cy_row = cy_row.iloc[0]
        if isinstance(py_row, pd.DataFrame):
            py_row = py_row.iloc[0]

        py_disallowed = _val(py_row, "IRS8990_DisallowedBusInterestExpnsAmt")
        cy_cfwd = _val(cy_row, "IRS8990_CfwdPrevDsallwIntExpenseAmt")

        if py_disallowed == 0 and cy_cfwd == 0:
            continue

        delta = abs(cy_cfwd - py_disallowed)
        if delta > 1:
            name = _entity_name(cy_row) or ctx.entity_name(code)
            ctx.add(
                check_id="BIE-013", severity="HIGH", category="section_163j",
                entity_code=code, entity_name=name,
                description=f"Carryforward mismatch: CY cfwd ${cy_cfwd:,.0f} vs PY disallowed ${py_disallowed:,.0f}",
                expected=f"PY Disallowed ({py_disallowed:,.0f}) should roll to CY Carryforward",
                actual=f"CY CfwdPrevDsallwIntExpenseAmt = {cy_cfwd:,.0f}",
                delta=delta,
                context="Form 8990: Prior year disallowed BIE should carry forward to current year Line 28",
            )

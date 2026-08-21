"""Rollover checks (ROL-001 to ROL-012): PY-to-CY continuity."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float

if TYPE_CHECKING:
    from lab.xml_parser.parser import EFileParser


_SCH_F_ROLLOVER_LINES = [
    ("EndAcctPrdCashAmt", "BegngAcctPrdCashAmt", "Cash"),
    ("EndAcctPrdTradeNotesAmt", "BegngAcctPrdTradeNotesAmt", "Trade notes & AR"),
    ("EndAcctPrdInventoriesAmt", "BegngAcctPrdInventoriesAmt", "Inventories"),
    ("EndAcctPrdInvstSubsidiaryAmt", "BegngAcctPrdInvstSubsidiaryAmt", "Investment in subs"),
    ("EndAcctPrdBldgAndOtherAstAmt", "BegngAcctPrdBldgAndOtherAstAmt", "Buildings & depreciable"),
    ("EndAcctPrdLandAmt", "BegngAcctPrdLandAmt", "Land"),
    ("EndAcctPrdPatentsOthAstAmt", "BegngAcctPrdPatentsOthAstAmt", "Intangibles"),
    ("EndAcctPrdOtherAssetsAmt", "BegngAcctPrdOtherAssetsAmt", "Other assets"),
    ("EndAcctPrdTotalAssetsAmt", "BegngAcctPrdTotalAssetsAmt", "Total assets"),
    ("EndAcctPrdAccountsPayableAmt", "BegngAcctPrdAccountsPayableAmt", "Accounts payable"),
    ("EndAcctPrdOtherCurrLiabAmt", "BegngAcctPrdOtherCurrLiabAmt", "Other current liabilities"),
    ("EndAcctPrdOthLiabilitiesAmt", "BegngAcctPrdOthLiabilitiesAmt", "Other liabilities"),
    ("EndAcctPrdCommonStockAmt", "BegngAcctPrdCommonStockAmt", "Capital stock"),
    ("EndAcctPrdPaidInOrSurplusAmt", "BegngAcctPrdPaidInOrSurplusAmt", "Paid-in surplus"),
    ("EndAcctPrdRtnEarningsAmt", "BegngAcctPrdRtnEarningsAmt", "Retained earnings"),
    ("EndAcctPrdTotLiabShrEqtyAmt", "BegngAcctPrdTotLiabShrEqtyAmt", "Total L+E"),
]

_SCH_J_POOLS = [
    ("Post2017EPNotPrevTaxedGrp", "Post-2017 E&P Not Previously Taxed"),
    ("TotalSection964AEPGrp", "Total Section 964(a) E&P"),
    ("Post1986UndistributedEarnGrp", "Post-1986 Undistributed Earnings"),
    ("HoveringDeficitDedSspndTaxGrp", "Hovering Deficit"),
    ("Section951APTEPGrp", "Section 951A PTEP (GILTI)"),
]


def run_rollover_checks(ctx: CheckContext, parser_py: EFileParser = None, df_py: pd.DataFrame = None) -> list[Finding]:
    """Run all rollover checks. Requires prior year data."""
    if parser_py is None or df_py is None:
        return ctx.findings

    parser_cy = ctx.parser
    df_cy = ctx.df

    cy_entities = set(df_cy["_reference_id"].unique()) - {""}
    py_entities = set(df_py["_reference_id"].unique()) - {""}

    # ROL-002
    for code in py_entities - cy_entities:
        name = _get_entity_name_py(df_py, code)
        ctx.add(
            check_id="ROL-002", severity="MEDIUM", category="rollover",
            entity_code=code, entity_name=name,
            description="Entity present in prior year but absent in current year",
            context="Verify: was this entity liquidated, sold, or merged? Check Sch O.",
        )

    # ROL-003
    for code in cy_entities - py_entities:
        name = ctx.entity_name(code)
        ctx.add(
            check_id="ROL-003", severity="MEDIUM", category="rollover",
            entity_code=code, entity_name=name,
            description="Entity present in current year but not in prior year (new)",
            context="Verify: was this entity acquired, incorporated, or reclassified? Check Sch O.",
        )

    # ROL-001
    _check_balance_sheet_rollover(ctx, parser_cy, df_cy, parser_py, df_py)

    # ROL-004, ROL-005, ROL-006
    sch_h_cy = parser_cy.extract_form("IRS5471ScheduleH")
    sch_h_py = parser_py.extract_form("IRS5471ScheduleH")
    if not sch_h_cy.empty and not sch_h_py.empty:
        _check_ep_sign_flip(ctx, sch_h_cy, sch_h_py, df_cy)
        _check_fx_rate_change(ctx, sch_h_cy, sch_h_py, df_cy)
        _check_material_disappearance(ctx, sch_h_cy, sch_h_py, df_cy)

    # ROL-007
    sch_j_cy = parser_cy.extract_form("IRS5471ScheduleJ")
    sch_j_py = parser_py.extract_form("IRS5471ScheduleJ")
    if not sch_j_cy.empty and not sch_j_py.empty:
        _check_accumulated_ep_rollover(ctx, sch_j_cy, sch_j_py, df_cy)

    # ROL-008
    _check_page1_rollover(ctx, parser_cy, df_cy, parser_py, df_py)

    # ROL-009
    _check_schg_indicator_flips(ctx, parser_cy, df_cy, parser_py, df_py)

    # ROL-010
    sch_i1_cy = parser_cy.extract_form("IRS5471ScheduleI1")
    sch_i1_py = parser_py.extract_form("IRS5471ScheduleI1")
    if not sch_i1_cy.empty and not sch_i1_py.empty:
        _check_gilti_classification_change(ctx, sch_i1_cy, sch_i1_py, df_cy)

    # ROL-011
    if not sch_h_cy.empty:
        _check_ep_accumulation_math(ctx, sch_h_cy, sch_j_cy, df_cy)

    # ROL-012
    sch_f_cy = parser_cy.extract_form("IRS5471ScheduleF")
    if not sch_h_cy.empty and not sch_f_cy.empty:
        _check_retained_earnings_vs_ep(ctx, sch_h_cy, sch_f_cy, df_cy)

    return ctx.findings


def _get_entity_name_py(df_py: pd.DataFrame, code: str) -> str:
    if "_entity_name" in df_py.columns:
        match = df_py[df_py["_reference_id"] == code]["_entity_name"]
        if not match.empty:
            return str(match.iloc[0])
    return code


def _check_balance_sheet_rollover(ctx, parser_cy, df_cy, parser_py, df_py):
    sch_f_cy = parser_cy.extract_form("IRS5471ScheduleF")
    sch_f_py = parser_py.extract_form("IRS5471ScheduleF")

    if sch_f_cy.empty or sch_f_py.empty:
        return

    f_cy = sch_f_cy.set_index("_reference_id")
    f_py = sch_f_py.set_index("_reference_id")
    common = set(f_cy.index) & set(f_py.index) - {""}

    for code in common:
        name = ctx.entity_name(code)
        cy_row = f_cy.loc[code]
        py_row = f_py.loc[code]

        for py_eoy_suffix, cy_boy_suffix, desc in _SCH_F_ROLLOVER_LINES:
            py_col = f"IRS5471ScheduleF_{py_eoy_suffix}"
            cy_col = f"IRS5471ScheduleF_{cy_boy_suffix}"

            py_eoy = safe_float(py_row, py_col)
            cy_boy = safe_float(cy_row, cy_col)

            if py_eoy is None and cy_boy is None:
                continue
            py_eoy = py_eoy or 0
            cy_boy = cy_boy or 0

            delta = abs(cy_boy - py_eoy)
            if delta > 10000 and delta > max(1, abs(py_eoy) * 0.001):
                severity = "HIGH" if "Total" in desc else "MEDIUM"
                ctx.add(
                    check_id="ROL-001", severity=severity, category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Sch F {desc}: CY BOY ({cy_boy:,.0f}) != PY EOY ({py_eoy:,.0f})",
                    expected=f"CY BOY = PY EOY ({py_eoy:,.0f})",
                    actual=f"CY BOY = {cy_boy:,.0f} (delta {delta:,.0f})",
                    delta=delta,
                    context="Balance sheet must roll forward. FX retranslation may explain small diffs.",
                )


def _check_ep_sign_flip(ctx, sch_h_cy, sch_h_py, df_cy):
    ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
    h_cy = sch_h_cy.set_index("_reference_id")
    h_py = sch_h_py.set_index("_reference_id")

    if ep_col not in h_cy.columns or ep_col not in h_py.columns:
        return

    common = set(h_cy.index) & set(h_py.index) - {""}
    for code in common:
        cy_ep = safe_float(h_cy.loc[code], ep_col)
        py_ep = safe_float(h_py.loc[code], ep_col)

        if cy_ep is not None and py_ep is not None:
            if (cy_ep > 50000 and py_ep < -50000) or (cy_ep < -50000 and py_ep > 50000):
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="ROL-004", severity="MEDIUM", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"E&P sign flip: PY ${py_ep:,.0f} to CY ${cy_ep:,.0f}",
                    expected="Sign consistency unless material transaction occurred",
                    actual=f"PY: ${py_ep:,.0f}, CY: ${cy_ep:,.0f}",
                    context="Verify: acquisition, disposition, or large one-time item?",
                )


def _check_material_disappearance(ctx, sch_h_cy, sch_h_py, df_cy):
    ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
    h_cy = sch_h_cy.set_index("_reference_id") if "_reference_id" in sch_h_cy.columns else sch_h_cy
    h_py = sch_h_py.set_index("_reference_id") if "_reference_id" in sch_h_py.columns else sch_h_py

    if ep_col not in h_cy.columns or ep_col not in h_py.columns:
        return

    common = set(h_cy.index) & set(h_py.index) - {""}
    for code in common:
        py_ep = safe_float(h_py.loc[code], ep_col)
        cy_ep = safe_float(h_cy.loc[code], ep_col)

        if py_ep is not None and abs(py_ep) > 100000 and (cy_ep is None or cy_ep == 0):
            name = ctx.entity_name(code)
            ctx.add(
                check_id="ROL-006", severity="HIGH", category="rollover",
                entity_code=code, entity_name=name,
                description=f"Material E&P (${py_ep:,.0f}) in PY dropped to zero in CY",
                expected="Non-zero E&P unless entity disposed/liquidated",
                actual="$0 in current year",
                delta=abs(py_ep),
                context="Check for liquidation, disposition, or data omission",
            )


def _check_fx_rate_change(ctx, sch_h_cy, sch_h_py, df_cy):
    fx_col = "IRS5471ScheduleH_ExchangeRt"
    h_cy = sch_h_cy.set_index("_reference_id")
    h_py = sch_h_py.set_index("_reference_id")

    if fx_col not in h_cy.columns or fx_col not in h_py.columns:
        return

    common = set(h_cy.index) & set(h_py.index) - {""}
    for code in common:
        cy_fx = safe_float(h_cy.loc[code], fx_col)
        py_fx = safe_float(h_py.loc[code], fx_col)

        if cy_fx is not None and py_fx is not None and py_fx > 0 and cy_fx > 0:
            pct_change = abs(cy_fx - py_fx) / py_fx
            if pct_change > 0.25:
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="ROL-005", severity="LOW", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"FX rate changed {pct_change:.0%} YoY (PY: {py_fx:.4f}, CY: {cy_fx:.4f})",
                    expected="Change < 25% unless currency devaluation occurred",
                    actual=f"PY: {py_fx:.4f}, CY: {cy_fx:.4f} ({pct_change:.0%} change)",
                    context="Large FX swings may be correct (e.g. ARS, TRY) or indicate wrong rate entry",
                )


def _check_accumulated_ep_rollover(ctx, sch_j_cy, sch_j_py, df_cy):
    j_cy = sch_j_cy.set_index("_reference_id")
    j_py = sch_j_py.set_index("_reference_id")
    common = set(j_cy.index) & set(j_py.index) - {""}

    for pool_name, pool_desc in _SCH_J_POOLS:
        boy_col = f"IRS5471ScheduleJ_{pool_name}_BeginningYearBalanceAmt"
        eoy_col = f"IRS5471ScheduleJ_{pool_name}_BalanceBeginningNextYearAmt"

        if boy_col not in j_cy.columns or eoy_col not in j_py.columns:
            continue

        for code in common:
            cy_boy = safe_float(j_cy.loc[code], boy_col)
            py_eoy = safe_float(j_py.loc[code], eoy_col)

            if cy_boy is None and py_eoy is None:
                continue
            cy_boy = cy_boy or 0
            py_eoy = py_eoy or 0

            delta = abs(cy_boy - py_eoy)
            if delta > max(1, abs(py_eoy) * 0.001) and delta > 100:
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="ROL-007", severity="HIGH", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Sch J {pool_desc}: CY BOY (${cy_boy:,.0f}) != PY EOY (${py_eoy:,.0f})",
                    expected=f"CY beginning = PY ending (${py_eoy:,.0f})",
                    actual=f"CY BOY = ${cy_boy:,.0f} (delta ${delta:,.0f})",
                    delta=delta,
                    context="E&P pool must roll forward. Gap = missed distribution, inclusion, reclassification, or data error.",
                )


def _check_page1_rollover(ctx, parser_cy, df_cy, parser_py, df_py):
    cy_main = parser_cy.to_dataframe().set_index("_reference_id")
    py_main = parser_py.to_dataframe().set_index("_reference_id")
    common = set(cy_main.index) & set(py_main.index) - {""}

    static_fields = [
        ("_entity_name", "Entity name"),
        ("IRS5471_CountryUnderWhoseLawsIncCd", "Country of incorporation"),
        ("IRS5471_FunctionalCurrencyCd", "Functional currency"),
        ("IRS5471_PrincipalPlaceOfBusCountryCd", "Principal place of business"),
    ]

    for code in common:
        name = ctx.entity_name(code)
        for col, desc in static_fields:
            if col not in cy_main.columns or col not in py_main.columns:
                continue
            try:
                cy_val = str(cy_main.loc[code, col] or "").strip().upper()
                py_val = str(py_main.loc[code, col] or "").strip().upper()
            except (KeyError, TypeError):
                continue

            if not py_val or not cy_val:
                continue
            if py_val == "NAN" or cy_val == "NAN":
                continue

            if py_val != cy_val:
                severity = "HIGH" if "currency" in desc.lower() else "MEDIUM"
                ctx.add(
                    check_id="ROL-008", severity=severity, category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"{desc} changed: '{py_val}' -> '{cy_val}'",
                    expected=f"Unchanged (PY: {py_val})",
                    actual=f"CY: {cy_val}",
                    context="Static entity info should not change unless reclassification, re-domiciliation, or error.",
                )


def _check_schg_indicator_flips(ctx, parser_cy, df_cy, parser_py, df_py):
    cy_main = parser_cy.to_dataframe().set_index("_reference_id")
    py_main = parser_py.to_dataframe().set_index("_reference_id")
    common = set(cy_main.index) & set(py_main.index) - {""}

    indicators = [
        ("IRS5471_IRS5471ScheduleG_DisallowedInterestExpenseInd", "163(j) disallowed interest"),
        ("IRS5471_IRS5471ScheduleG_BaseErosionPaymentBenefitInd", "Base erosion payments (BEAT)"),
        ("IRS5471_IRS5471ScheduleG_FDIIBenefitsClaimInd", "FDII benefits claimed"),
        ("IRS5471_IRS5471ScheduleG_PayOrAccrueTopUpTaxInd", "Top-up tax (Pillar Two)"),
    ]

    for code in common:
        name = ctx.entity_name(code)
        for col, desc in indicators:
            if col not in cy_main.columns or col not in py_main.columns:
                continue
            try:
                cy_val = str(cy_main.loc[code, col] or "").strip().upper()
                py_val = str(py_main.loc[code, col] or "").strip().upper()
            except (KeyError, TypeError):
                continue

            if py_val == cy_val:
                continue
            if py_val in ("", "NAN") and cy_val in ("", "NAN"):
                continue

            direction = f"{'Yes' if py_val in ('1','TRUE','Y','YES') else 'No'} -> {'Yes' if cy_val in ('1','TRUE','Y','YES') else 'No'}"
            ctx.add(
                check_id="ROL-009", severity="MEDIUM", category="rollover",
                entity_code=code, entity_name=name,
                description=f"Sch G indicator flip: {desc} ({direction})",
                expected=f"PY: {py_val or 'blank'}",
                actual=f"CY: {cy_val or 'blank'}",
                context="Indicator changes may trigger new compliance requirements or affect calculations.",
            )


def _check_gilti_classification_change(ctx, sch_i1_cy, sch_i1_py, df_cy):
    tested_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt"
    i1_cy = sch_i1_cy.set_index("_reference_id")
    i1_py = sch_i1_py.set_index("_reference_id")

    if tested_col not in i1_cy.columns or tested_col not in i1_py.columns:
        return

    common = set(i1_cy.index) & set(i1_py.index) - {""}
    for code in common:
        cy_tested = safe_float(i1_cy.loc[code], tested_col)
        py_tested = safe_float(i1_py.loc[code], tested_col)

        if cy_tested is None or py_tested is None:
            continue

        if py_tested > 10000 and cy_tested < -10000:
            name = ctx.entity_name(code)
            ctx.add(
                check_id="ROL-010", severity="MEDIUM", category="rollover",
                entity_code=code, entity_name=name,
                description=f"GILTI classification flip: tested income (${py_tested:,.0f}) -> tested loss (${cy_tested:,.0f})",
                expected="Consistent classification unless material business change",
                actual=f"PY: ${py_tested:,.0f}, CY: ${cy_tested:,.0f}",
                context="Entity moved from GILTI inclusion contributor to loss entity. Verify business deterioration or restructuring.",
            )
        elif py_tested < -10000 and cy_tested > 10000:
            name = ctx.entity_name(code)
            ctx.add(
                check_id="ROL-010", severity="LOW", category="rollover",
                entity_code=code, entity_name=name,
                description=f"GILTI classification flip: tested loss (${py_tested:,.0f}) -> tested income (${cy_tested:,.0f})",
                expected="Consistent classification unless recovery",
                actual=f"PY: ${py_tested:,.0f}, CY: ${cy_tested:,.0f}",
                context="Entity recovered from loss to income. Verify turnaround or one-time item.",
            )


def _check_ep_accumulation_math(ctx, sch_h_cy, sch_j_cy, df_cy):
    if sch_j_cy.empty:
        return

    h_cy = sch_h_cy.set_index("_reference_id")
    j_cy = sch_j_cy.set_index("_reference_id")

    ep_usd_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
    boy_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_BeginningYearBalanceAmt"
    cy_ep_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_CurrentYearEPAmt"
    eoy_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_BalanceBeginningNextYearAmt"

    if ep_usd_col not in h_cy.columns:
        return
    if boy_col not in j_cy.columns or eoy_col not in j_cy.columns:
        return

    common = set(h_cy.index) & set(j_cy.index) - {""}
    for code in common:
        boy = safe_float(j_cy.loc[code], boy_col)
        cy_ep_j = safe_float(j_cy.loc[code], cy_ep_col)
        eoy = safe_float(j_cy.loc[code], eoy_col)
        cy_ep_h = safe_float(h_cy.loc[code], ep_usd_col)

        if cy_ep_j is not None and cy_ep_h is not None:
            delta = abs(cy_ep_j - cy_ep_h)
            if delta > max(100, abs(cy_ep_h) * 0.01) and delta > 1000:
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="ROL-011", severity="HIGH", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Sch J CY E&P (${cy_ep_j:,.0f}) != Sch H current E&P USD (${cy_ep_h:,.0f})",
                    expected=f"Sch J col ii = Sch H line 5d (${cy_ep_h:,.0f})",
                    actual=f"Sch J = ${cy_ep_j:,.0f} (delta ${delta:,.0f})",
                    delta=delta,
                    context="Current year E&P on Sch J must tie to Sch H. Mismatch = Sch J not updated or wrong pool.",
                )

        if boy is not None and eoy is not None and cy_ep_j is not None:
            expected_min = boy + cy_ep_j
            if eoy > expected_min + max(1000, abs(expected_min) * 0.05):
                overage = eoy - expected_min
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="ROL-011", severity="MEDIUM", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Sch J EOY (${eoy:,.0f}) > BOY + CY E&P (${expected_min:,.0f}) by ${overage:,.0f}",
                    expected=f"EOY <= BOY ({boy:,.0f}) + CY E&P ({cy_ep_j:,.0f}) unless reclassification in",
                    actual=f"EOY = ${eoy:,.0f} (overage ${overage:,.0f})",
                    delta=overage,
                    context="E&P pool grew more than current year earnings explain. Check reclassifications or data entry.",
                )


def _check_retained_earnings_vs_ep(ctx, sch_h_cy, sch_f_cy, df_cy):
    """ROL-012: Sch F retained earnings movement should approximate Sch H current E&P."""
    h_cy = sch_h_cy.set_index("_reference_id")
    f_cy = sch_f_cy.set_index("_reference_id")

    ep_col = "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt"
    re_boy_col = "IRS5471ScheduleF_BegngAcctPrdRtnEarningsAmt"
    re_eoy_col = "IRS5471ScheduleF_EndAcctPrdRtnEarningsAmt"

    if ep_col not in h_cy.columns:
        return

    common = set(h_cy.index) & set(f_cy.index) - {""}
    for code in common:
        ep_fc = safe_float(h_cy.loc[code], ep_col)
        re_boy = safe_float(f_cy.loc[code], re_boy_col)
        re_eoy = safe_float(f_cy.loc[code], re_eoy_col)

        if ep_fc is None or re_boy is None or re_eoy is None:
            continue

        re_delta = re_eoy - re_boy
        diff = abs(re_delta - ep_fc)

        if diff > max(500000, abs(ep_fc) * 0.50) and abs(ep_fc) > 10000:
            name = ctx.entity_name(code)
            ctx.add(
                check_id="ROL-012", severity="LOW", category="rollover",
                entity_code=code, entity_name=name,
                description=f"Sch F retained earnings change ({re_delta:,.0f}) vs Sch H E&P ({ep_fc:,.0f}) differ by {diff:,.0f}",
                expected=f"RE delta approx = E&P ({ep_fc:,.0f} FC)",
                actual=f"RE delta = {re_delta:,.0f} (diff {diff:,.0f})",
                delta=diff,
                context="Retained earnings should move by ~E&P unless dividends, prior period adj, or Sch O transactions",
            )

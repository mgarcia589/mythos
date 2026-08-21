"""Flow checks (FLO-001 to FLO-020): internal consistency within a single year.

Cross-schedule arithmetic validation for IRS Form 5471:
- FLO-001 to FLO-008: Original checks (Sch H/C/I-1/E/F per-field)
- FLO-009 to FLO-015: Internal sum validation (line items = totals)
- FLO-016 to FLO-018: Cross-schedule ties (E taxes, J vs H, basket allocation)
- FLO-019 to FLO-020: Logical consistency (dormant, gross decomposition)
"""

from __future__ import annotations

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_flow_checks(ctx: CheckContext) -> list[Finding]:
    """Run all flow checks and return findings."""
    parser = ctx.parser
    df = ctx.df

    sch_h = parser.extract_form("IRS5471ScheduleH")
    sch_i1 = parser.extract_form("IRS5471ScheduleI1")
    sch_e = parser.extract_form("IRS5471ScheduleE")
    sch_c = parser.extract_form("IRS5471ScheduleC")
    sch_f = parser.extract_form("IRS5471ScheduleF")
    sch_j = parser.extract_form("IRS5471ScheduleJ")

    if sch_h.empty:
        return ctx.findings

    sch_h = sch_h.set_index("_reference_id")
    if not sch_i1.empty:
        sch_i1 = sch_i1.set_index("_reference_id")
    if not sch_e.empty:
        sch_e = sch_e.set_index("_reference_id")
    if not sch_c.empty:
        sch_c = sch_c.set_index("_reference_id")
    if not sch_f.empty:
        sch_f = sch_f.set_index("_reference_id")
    if not sch_j.empty:
        sch_j = sch_j.set_index("_reference_id")

    for code in sch_h.index:
        if code == "":
            continue
        name = ctx.entity_name(code)
        _check_flow_entity(ctx, code, name, sch_h, sch_i1, sch_e, sch_c, sch_f)
        _check_flow_cross_schedule(ctx, code, name, sch_h, sch_i1, sch_e, sch_c, sch_f, sch_j)

    return ctx.findings


def _check_flow_entity(ctx, code, name, sch_h, sch_i1, sch_e, sch_c, sch_f):
    h = sch_h.loc[code] if code in sch_h.index else None
    if h is None:
        return

    net_income_h = safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")

    # FLO-001
    if not sch_c.empty and code in sch_c.index:
        c = sch_c.loc[code]
        net_income_c = safe_float(c, "IRS5471ScheduleC_ForeignCYNetIncomePerBookAmt")
        if net_income_h is not None and net_income_c is not None:
            delta = abs(net_income_h - net_income_c)
            if delta > max(1, abs(net_income_h) * 0.001):
                ctx.add(
                    check_id="FLO-001", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch H net income != Sch C line 21 (delta {delta:,.0f} FC)",
                    expected=f"Sch C: {net_income_c:,.0f}",
                    actual=f"Sch H: {net_income_h:,.0f}",
                    delta=delta,
                    context="Sch H line 1 should equal Sch C line 21 (net income per books)",
                )

    # FLO-002
    ep_fc = safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")
    ep_usd = safe_float(h, "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt")
    fx_rate = safe_float(h, "IRS5471ScheduleH_ExchangeRt")

    if ep_fc is not None and fx_rate is not None and fx_rate > 0 and ep_usd is not None:
        expected_usd = ep_fc / fx_rate
        delta = abs(expected_usd - ep_usd)
        if delta > max(10, abs(ep_usd) * 0.01):
            ctx.add(
                check_id="FLO-002", severity="MEDIUM", category="flow",
                entity_code=code, entity_name=name,
                description=f"E&P FC/FX rate != USD amount (delta ${delta:,.0f})",
                expected=f"${expected_usd:,.0f} (FC {ep_fc:,.0f} / {fx_rate:.4f})",
                actual=f"${ep_usd:,.0f}",
                delta=delta,
            )

    # FLO-004
    if not sch_e.empty and code in sch_e.index:
        e = sch_e.loc[code]
        total_tax = safe_float(e, "IRS5471ScheduleE_TotalTaxInFunctionalCurAmt")
        if total_tax is not None and net_income_h is not None and net_income_h > 0:
            max_reasonable_tax = net_income_h * 0.45
            if total_tax > max_reasonable_tax and total_tax > 10000:
                ctx.add(
                    check_id="FLO-004", severity="MEDIUM", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch E taxes ({total_tax:,.0f} FC) exceed 45% of pre-tax income ({net_income_h:,.0f} FC)",
                    expected=f"Tax <= {max_reasonable_tax:,.0f} FC (45% cap)",
                    actual=f"Tax = {total_tax:,.0f} FC ({total_tax/net_income_h:.0%})",
                    delta=total_tax - max_reasonable_tax,
                    context="Taxes exceeding maximum statutory rate suggest data error or prior-year adjustments included",
                )

    # FLO-005 and FLO-003
    if not sch_i1.empty and code in sch_i1.index:
        i1 = sch_i1.loc[code]
        tested_usd_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt"
        tested_fc_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_FunctionalCurrencyAmt"
        tax_col = "IRS5471ScheduleI1_TestedForeignIncomeTaxesGrp_USDollarAmt"

        tested = safe_float(i1, tested_usd_col) or safe_float(i1, tested_fc_col)
        taxes = safe_float(i1, tax_col)

        if tested is not None and tested < 0 and taxes is not None and taxes > 0:
            ctx.add(
                check_id="FLO-005", severity="HIGH", category="flow",
                entity_code=code, entity_name=name,
                description="Tested loss entity has positive tested foreign taxes",
                expected="No taxes for tested loss entity",
                actual=f"Tested income: ${tested:,.0f}, Taxes: ${taxes:,.0f}",
                context="Tested foreign taxes should only be claimed by tested income entities",
            )

        # FLO-003
        gross_col = "IRS5471ScheduleI1_GrossIncomeAmt"
        hte_col = "IRS5471ScheduleI1_HighTaxExceptionIncomeAmt"
        subf_col = "IRS5471ScheduleI1_SubpartFIncomeAmt"

        gross = safe_float(i1, gross_col)
        hte = safe_float(i1, hte_col) or 0
        subf = safe_float(i1, subf_col) or 0
        tested_val = tested or 0

        if gross is not None and gross != 0:
            allocable_col = "IRS5471ScheduleI1_AllocableDeductionAmt"
            allocable = safe_float(i1, allocable_col) or 0
            reconstructed = tested_val + hte + subf + allocable
            flow_delta = abs(gross - reconstructed)
            if flow_delta > max(1000, abs(gross) * 0.05):
                ctx.add(
                    check_id="FLO-003", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch I-1 income components don't reconcile to gross (delta ${flow_delta:,.0f})",
                    expected=f"Gross ${gross:,.0f} ~= Tested {tested_val:,.0f} + HTE {hte:,.0f} + SubF {subf:,.0f} + Deductions {allocable:,.0f}",
                    actual=f"Sum = ${reconstructed:,.0f}",
                    delta=flow_delta,
                )

    # FLO-006
    if not sch_c.empty and code in sch_c.index:
        c = sch_c.loc[code]
        total_income = safe_float(c, "IRS5471ScheduleC_ForeignTotalIncomeAmt")
        total_deductions = safe_float(c, "IRS5471ScheduleC_ForeignTotalDeductionsAmt")
        net_income_c = safe_float(c, "IRS5471ScheduleC_ForeignCYNetIncomePerBookAmt")
        if total_income is not None and total_deductions is not None and net_income_c is not None:
            expected_net = total_income - total_deductions
            d = abs(expected_net - net_income_c)
            if d > 1:
                ctx.add(
                    check_id="FLO-006", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch C: income ({total_income:,.0f}) - deductions ({total_deductions:,.0f}) != net ({net_income_c:,.0f})",
                    expected=f"Net = {expected_net:,.0f}",
                    actual=f"Net = {net_income_c:,.0f}",
                    delta=d,
                    context="Sch C line 12 - line 20 should equal line 21",
                )

    # FLO-007 and FLO-008
    if not sch_f.empty and code in sch_f.index:
        f = sch_f.loc[code]
        eoy_assets = safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
        boy_assets = safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt")

        if eoy_assets is not None and eoy_assets < 0:
            ctx.add(
                check_id="FLO-007", severity="HIGH", category="flow",
                entity_code=code, entity_name=name,
                description=f"Sch F EOY total assets is negative ({eoy_assets:,.0f})",
                expected="Total assets >= 0",
                actual=f"{eoy_assets:,.0f}",
                context="Negative total assets on balance sheet is impossible — likely data entry error",
            )

        if boy_assets is not None and boy_assets < 0:
            ctx.add(
                check_id="FLO-007", severity="HIGH", category="flow",
                entity_code=code, entity_name=name,
                description=f"Sch F BOY total assets is negative ({boy_assets:,.0f})",
                expected="Total assets >= 0",
                actual=f"{boy_assets:,.0f}",
                context="Negative total assets on balance sheet is impossible — likely data entry error",
            )

        # FLO-008
        eoy_liab_eq = safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotLiabShrEqtyAmt")
        if eoy_assets is not None and eoy_liab_eq is not None:
            bs_delta = abs(eoy_assets - eoy_liab_eq)
            if bs_delta > 1:
                ctx.add(
                    check_id="FLO-008", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F balance sheet does not balance (delta {bs_delta:,.0f})",
                    expected=f"Assets ({eoy_assets:,.0f}) = L+E ({eoy_liab_eq:,.0f})",
                    actual=f"Difference: {bs_delta:,.0f}",
                    delta=bs_delta,
                    context="Total assets must equal total liabilities + shareholders equity",
                )


def _check_flow_cross_schedule(ctx, code, name, sch_h, sch_i1, sch_e, sch_c, sch_f, sch_j):
    """FLO-009 to FLO-020: cross-schedule arithmetic and logical consistency."""
    h = sch_h.loc[code] if code in sch_h.index else None
    if h is None:
        return

    # ─── FLO-009: Sch H E&P computation (line 1 + line 3 - line 4 = line 5a) ─────
    net_income = safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
    total_add = safe_float(h, "IRS5471ScheduleH_TotalNetAdditionsAmt")
    total_sub = safe_float(h, "IRS5471ScheduleH_TotalNetSubtractionsAmt")
    ep_fc = safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")

    if all(v is not None for v in [net_income, total_add, total_sub, ep_fc]):
        expected_ep = net_income + total_add - total_sub
        delta = abs(expected_ep - ep_fc)
        if delta > max(1, abs(ep_fc) * 0.001) and delta > 1:
            ctx.add(
                check_id="FLO-009", severity="HIGH", category="flow",
                entity_code=code, entity_name=name,
                description=f"Sch H E&P math: line 1 + line 3 - line 4 != line 5a (delta {delta:,.0f})",
                expected=f"{net_income:,.0f} + {total_add:,.0f} - {total_sub:,.0f} = {expected_ep:,.0f}",
                actual=f"Line 5a = {ep_fc:,.0f}",
                delta=delta,
                context="Current E&P must equal net income plus additions minus subtractions",
            )

    # ─── FLO-010: Sch F asset components = total assets (EOY and BOY) ─────────────
    if not sch_f.empty and code in sch_f.index:
        f = sch_f.loc[code]

        for period, prefix, total_col in [
            ("EOY", "EndAcctPrd", "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt"),
            ("BOY", "BegngAcctPrd", "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt"),
        ]:
            total = safe_float(f, total_col)
            if total is None:
                continue

            components = [
                safe_float(f, f"IRS5471ScheduleF_{prefix}CashAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}TradeNotesAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}InventoriesAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}InvstSubsidiaryAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}BldgAndOtherAstAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}LandAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}PatentsOthAstAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}OtherAssetsAmt") or 0,
            ]
            comp_sum = sum(components)
            delta = abs(comp_sum - total)
            if delta > 1 and comp_sum != 0:
                ctx.add(
                    check_id="FLO-010", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F {period} asset line items ({comp_sum:,.0f}) != total assets ({total:,.0f})",
                    expected=f"Sum of lines 1-8 = {comp_sum:,.0f}",
                    actual=f"Line 9 = {total:,.0f}",
                    delta=delta,
                    context=f"Sch F {period} asset components must sum to total assets (line 9)",
                )

    # ─── FLO-011: Sch F L+E components = total L+E (EOY and BOY) ──────────────────
    if not sch_f.empty and code in sch_f.index:
        f = sch_f.loc[code]

        for period, prefix, total_col in [
            ("EOY", "EndAcctPrd", "IRS5471ScheduleF_EndAcctPrdTotLiabShrEqtyAmt"),
            ("BOY", "BegngAcctPrd", "IRS5471ScheduleF_BegngAcctPrdTotLiabShrEqtyAmt"),
        ]:
            total = safe_float(f, total_col)
            if total is None:
                continue

            components = [
                safe_float(f, f"IRS5471ScheduleF_{prefix}AccountsPayableAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}OtherCurrLiabAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}OthLiabilitiesAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}CommonStockAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}PaidInOrSurplusAmt") or 0,
                safe_float(f, f"IRS5471ScheduleF_{prefix}RtnEarningsAmt") or 0,
            ]
            comp_sum = sum(components)
            delta = abs(comp_sum - total)
            if delta > 1 and comp_sum != 0:
                ctx.add(
                    check_id="FLO-011", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F {period} L+E line items ({comp_sum:,.0f}) != total L+E ({total:,.0f})",
                    expected=f"Sum of lines 10-15 = {comp_sum:,.0f}",
                    actual=f"Line 16 = {total:,.0f}",
                    delta=delta,
                    context=f"Sch F {period} liability + equity components must sum to total (line 16)",
                )

    # ─── FLO-012: Sch C gross profit = Receipts - Returns - COGS ──────────────────
    if not sch_c.empty and code in sch_c.index:
        c = sch_c.loc[code]
        receipts = safe_float(c, "IRS5471ScheduleC_ForeignGrossReceiptsOrSalesAmt")
        returns = safe_float(c, "IRS5471ScheduleC_ForeignReturnsAndAllowancesAmt") or 0
        cogs = safe_float(c, "IRS5471ScheduleC_ForeignCostOfGoodsSoldAmt") or 0
        gross_profit = safe_float(c, "IRS5471ScheduleC_ForeignGrossProfitAmt")

        if receipts is not None and gross_profit is not None:
            expected_gp = receipts - returns - cogs
            delta = abs(expected_gp - gross_profit)
            if delta > 1:
                ctx.add(
                    check_id="FLO-012", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch C gross profit math: 1a - 1b - 2 != line 3 (delta {delta:,.0f})",
                    expected=f"{receipts:,.0f} - {returns:,.0f} - {cogs:,.0f} = {expected_gp:,.0f}",
                    actual=f"Line 3 = {gross_profit:,.0f}",
                    delta=delta,
                    context="Gross profit = gross receipts minus returns minus COGS",
                )

    # ─── FLO-013: Sch I-1 exclusions sum (lines 2a-2d = line 3) ──────────────────
    if not sch_i1.empty and code in sch_i1.index:
        i1 = sch_i1.loc[code]
        total_excl = safe_float(i1, "IRS5471ScheduleI1_TotalExclusionsAmt")

        if total_excl is not None:
            excl_eci = safe_float(i1, "IRS5471ScheduleI1_ExclGrossIncmEffCntdFCCorpAmt") or 0
            excl_subf = safe_float(i1, "IRS5471ScheduleI1_ExclGrossIncmSubpartFIncmAmt") or 0
            excl_hte = safe_float(i1, "IRS5471ScheduleI1_ExclGrossIncmHghTxdIncmAmt") or 0
            excl_div = safe_float(i1, "IRS5471ScheduleI1_ExclGrossIncmDvdRcvdAmt") or 0
            excl_sum = excl_eci + excl_subf + excl_hte + excl_div
            delta = abs(excl_sum - total_excl)
            if delta > 1 and (excl_sum != 0 or total_excl != 0):
                ctx.add(
                    check_id="FLO-013", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch I-1 exclusions sum ({excl_sum:,.0f}) != total exclusions ({total_excl:,.0f})",
                    expected=f"Lines 2a-2d sum = {excl_sum:,.0f}",
                    actual=f"Line 3 = {total_excl:,.0f}",
                    delta=delta,
                    context="Sum of ECI + SubF + HTE + Dividends exclusions must equal line 3",
                )

    # ─── FLO-014: Sch I-1 tested income = gross less exclusions - deductions ──────
    if not sch_i1.empty and code in sch_i1.index:
        i1 = sch_i1.loc[code]
        gross_less = safe_float(i1, "IRS5471ScheduleI1_GrossIncmLessExclusionsAmt")
        allocable = safe_float(i1, "IRS5471ScheduleI1_AllocableDedExpnssAmt") or 0
        tested_income = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeAmt")
        tested_loss = safe_float(i1, "IRS5471ScheduleI1_TestedLossAmt")

        if gross_less is not None:
            expected_tested = gross_less - allocable
            actual_tested = None
            if tested_income is not None and tested_income > 0:
                actual_tested = tested_income
            elif tested_loss is not None and tested_loss > 0:
                actual_tested = -tested_loss
            elif tested_income is not None:
                actual_tested = tested_income

            if actual_tested is not None:
                delta = abs(expected_tested - actual_tested)
                if delta > max(1, abs(expected_tested) * 0.001) and delta > 1:
                    ctx.add(
                        check_id="FLO-014", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch I-1 line 4 - line 5 != line 6 (delta {delta:,.0f})",
                        expected=f"{gross_less:,.0f} - {allocable:,.0f} = {expected_tested:,.0f}",
                        actual=f"Tested income/loss = {actual_tested:,.0f}",
                        delta=delta,
                        context="Tested income/loss = gross income less exclusions minus allocable deductions",
                    )

    # ─── FLO-015: Sch F BOY balance sheet equation (A = L+E) ─────────────────────
    if not sch_f.empty and code in sch_f.index:
        f = sch_f.loc[code]
        boy_assets = safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt")
        boy_liab_eq = safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotLiabShrEqtyAmt")
        if boy_assets is not None and boy_liab_eq is not None:
            bs_delta = abs(boy_assets - boy_liab_eq)
            if bs_delta > 1:
                ctx.add(
                    check_id="FLO-015", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F BOY balance sheet does not balance (delta {bs_delta:,.0f})",
                    expected=f"BOY Assets ({boy_assets:,.0f}) = BOY L+E ({boy_liab_eq:,.0f})",
                    actual=f"Difference: {bs_delta:,.0f}",
                    delta=bs_delta,
                    context="Beginning-of-year total assets must equal total liabilities + equity",
                )

    # ─── FLO-016: Sch E tested tax vs Sch I-1 tested foreign taxes ────────────────
    if not sch_e.empty and code in sch_e.index and not sch_i1.empty and code in sch_i1.index:
        e = sch_e.loc[code]
        i1 = sch_i1.loc[code]
        e_tested_tax = safe_float(e, "IRS5471ScheduleE_Frm5471SchETestedIncomeGrp_TotalTaxInUSDollarsAmt")
        i1_tested_tax = safe_float(i1, "IRS5471ScheduleI1_TestedForeignIncomeTaxesGrp_USDollarAmt")

        if e_tested_tax is not None and i1_tested_tax is not None:
            delta = abs(e_tested_tax - i1_tested_tax)
            if delta > max(1, abs(e_tested_tax) * 0.01):
                ctx.add(
                    check_id="FLO-016", severity="MEDIUM", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch E tested tax (${e_tested_tax:,.0f}) != Sch I-1 tested tax (${i1_tested_tax:,.0f})",
                    expected=f"Sch E: ${e_tested_tax:,.0f}",
                    actual=f"Sch I-1: ${i1_tested_tax:,.0f}",
                    delta=delta,
                    context="Both schedules report the same tested foreign income taxes — must be equal",
                )

    # ─── FLO-017: Sch J CY E&P vs Sch H current E&P in USD (per basket) ──────────
    if not sch_j.empty and code in sch_j.index:
        j_data = sch_j.loc[code]
        ep_usd = safe_float(h, "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt")
        ep_pas = safe_float(h, "IRS5471ScheduleH_EPDASTMPassiveCatIncmAmt")
        ep_gen = safe_float(h, "IRS5471ScheduleH_EPDASTMGeneralCatIncmAmt")

        # Normalize to DataFrame for uniform iteration
        if isinstance(j_data, pd.Series):
            j_rows = [j_data]
        else:
            j_rows = [row for _, row in j_data.iterrows()]

        for j in j_rows:
            basket = j.get("_basket", "") if hasattr(j, "get") else ""
            j_cy_ep = safe_float(j, "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_CurrentYearEPDeficitAmt")

            # Determine H-side comparator based on basket
            if basket == "PAS":
                h_ep = ep_pas
            elif basket == "GEN":
                h_ep = ep_gen
            else:
                h_ep = ep_usd

            if h_ep is not None and j_cy_ep is not None:
                delta = abs(h_ep - j_cy_ep)
                if delta > max(10, abs(h_ep) * 0.01) and delta > 1:
                    basket_label = f" ({basket})" if basket else ""
                    ctx.add(
                        check_id="FLO-017", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch J CY E&P{basket_label} (${j_cy_ep:,.0f}) != Sch H (${h_ep:,.0f})",
                        expected=f"Sch H{basket_label}: ${h_ep:,.0f}",
                        actual=f"Sch J Post-2017 CY{basket_label}: ${j_cy_ep:,.0f}",
                        delta=delta,
                        context=f"Sch J current year E&P{basket_label} should equal Sch H E&P allocation",
                    )

    # ─── FLO-018: Sch H basket allocation (PAS + GEN = line 5c) ───────────────────
    ep_pas = safe_float(h, "IRS5471ScheduleH_EPDASTMPassiveCatIncmAmt")
    ep_gen = safe_float(h, "IRS5471ScheduleH_EPDASTMGeneralCatIncmAmt")
    ep_5c = safe_float(h, "IRS5471ScheduleH_EarningAndPrftPlusDASTMGainAmt")

    if ep_pas is not None and ep_gen is not None and ep_5c is not None:
        basket_sum = ep_pas + ep_gen
        delta = abs(basket_sum - ep_5c)
        if delta > max(1, abs(ep_5c) * 0.001) and delta > 1:
            ctx.add(
                check_id="FLO-018", severity="MEDIUM", category="flow",
                entity_code=code, entity_name=name,
                description=f"Sch H basket allocation: PAS ({ep_pas:,.0f}) + GEN ({ep_gen:,.0f}) != line 5c ({ep_5c:,.0f})",
                expected=f"PAS + GEN = {basket_sum:,.0f}",
                actual=f"Line 5c = {ep_5c:,.0f}",
                delta=delta,
                context="Passive + General category E&P must equal total E&P after DASTM",
            )

    # ─── FLO-019: Dormant entity with non-zero income ─────────────────────────────
    entity_dormant = False
    if "_dormant" in ctx.df.columns:
        mask = ctx.df["_reference_id"] == code
        if mask.any():
            row = ctx.df[mask].iloc[0]
            entity_dormant = bool(row.get("_dormant", False))

    if entity_dormant:
        net_inc = safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
        if net_inc is not None and abs(net_inc) > 1:
            ctx.add(
                check_id="FLO-019", severity="MEDIUM", category="flow",
                entity_code=code, entity_name=name,
                description=f"Dormant entity has non-zero income ({net_inc:,.0f})",
                expected="Income = 0 for dormant entity",
                actual=f"Sch H net income = {net_inc:,.0f}",
                context="A dormant entity should have no financial activity",
            )

    # ─── FLO-020: Sch I-1 gross = exclusions + gross less exclusions ──────────────
    if not sch_i1.empty and code in sch_i1.index:
        i1 = sch_i1.loc[code]
        gross = safe_float(i1, "IRS5471ScheduleI1_GrossIncomeAmt")
        total_excl = safe_float(i1, "IRS5471ScheduleI1_TotalExclusionsAmt") or 0
        gross_less = safe_float(i1, "IRS5471ScheduleI1_GrossIncmLessExclusionsAmt")

        if gross is not None and gross_less is not None:
            expected_gross = total_excl + gross_less
            delta = abs(gross - expected_gross)
            if delta > 1:
                ctx.add(
                    check_id="FLO-020", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch I-1 line 1 ({gross:,.0f}) != line 3 ({total_excl:,.0f}) + line 4 ({gross_less:,.0f})",
                    expected=f"Line 3 + Line 4 = {expected_gross:,.0f}",
                    actual=f"Line 1 = {gross:,.0f}",
                    delta=delta,
                    context="Gross income must equal total exclusions plus gross income less exclusions",
                )

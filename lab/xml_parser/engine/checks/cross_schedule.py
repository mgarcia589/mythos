"""Cross-schedule consistency checks (XSC-001 to XSC-009).

Validates data ties across Schedules Q, I-1, E, J, P, and I that are not
covered by existing flow or rollover checks. Derived from competitive
analysis of peer-developed IRS XML review tools (Phase 9.5).
"""

from __future__ import annotations

import math

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_cross_schedule_checks(ctx: CheckContext) -> list[Finding]:
    """Run all cross-schedule consistency checks."""
    parser = ctx.parser

    sch_i1 = parser.extract_form("IRS5471ScheduleI1")
    sch_q = parser.extract_form("IRS5471ScheduleQ")
    sch_e = parser.extract_form("IRS5471ScheduleE")
    sch_j = parser.extract_form("IRS5471ScheduleJ")
    sch_p = parser.extract_form("IRS5471ScheduleP")

    if not sch_i1.empty:
        sch_i1 = sch_i1.set_index("_reference_id")
    if not sch_e.empty:
        sch_e = sch_e.set_index("_reference_id")

    _check_sch_q_ties(ctx, sch_i1, sch_q, sch_e)
    _check_jp_consistency(ctx, sch_j, sch_p)
    _check_sch_i_indicators(ctx)
    _check_sch_e_local_vs_fc(ctx, sch_e)

    return ctx.findings


def _check_sch_q_ties(ctx: CheckContext, sch_i1: pd.DataFrame, sch_q: pd.DataFrame, sch_e: pd.DataFrame):
    """XSC-001 to XSC-005: Schedule I-1 vs Schedule Q cross-ties."""
    if sch_q.empty or sch_i1.empty:
        return

    q_by_entity = {}
    for _, row in sch_q.iterrows():
        ref_id = row.get("_reference_id", "")
        basket = row.get("_basket", "")
        if ref_id:
            q_by_entity.setdefault(ref_id, {})[basket] = row

    for code in sch_i1.index:
        if code == "" or code not in q_by_entity:
            continue
        name = ctx.entity_name(code)
        i1 = sch_i1.loc[code]
        q_baskets = q_by_entity[code]

        # XSC-001: I-1 Gross Income Less Exclusions = Sch Q Total Tested Gross (GEN)
        q_gen = q_baskets.get("GEN")
        if q_gen is not None:
            i1_gross = safe_float(i1, "IRS5471ScheduleI1_GrossIncomeLessTotIncmExclAmt")
            q_gross = safe_float(q_gen, "IRS5471ScheduleQ_TotalTestedIncomeGrp_TotalGrossIncomeAmt")
            if i1_gross is not None and q_gross is not None:
                delta = abs(i1_gross - q_gross)
                if delta > max(1, abs(i1_gross) * 0.001):
                    ctx.add(
                        check_id="XSC-001", severity="HIGH", category="cross_schedule",
                        entity_code=code, entity_name=name,
                        description=f"Sch I-1 Gross Income Less Excl != Sch Q Tested Gross (GEN) (delta {delta:,.0f})",
                        expected=f"Sch Q GEN: {q_gross:,.0f}",
                        actual=f"Sch I-1: {i1_gross:,.0f}",
                        delta=delta,
                        context="Sch I-1 line 4 should tie to Sch Q tested income gross (GEN basket)",
                    )

        # XSC-002: I-1 SubF Income = Sch Q CFC Total Gross (PAS)
        q_pas = q_baskets.get("PAS")
        if q_pas is not None:
            i1_subf = safe_float(i1, "IRS5471ScheduleI1_SubpartFIncomeAmt")
            q_cfc_gross = safe_float(q_pas, "IRS5471ScheduleQ_CFCTotalIncomeGrp_TotalGrossIncomeAmt")
            if i1_subf is not None and q_cfc_gross is not None:
                delta = abs(i1_subf - q_cfc_gross)
                if delta > max(1, abs(i1_subf) * 0.001) if i1_subf else delta > 1:
                    ctx.add(
                        check_id="XSC-002", severity="HIGH", category="cross_schedule",
                        entity_code=code, entity_name=name,
                        description=f"Sch I-1 SubF Income != Sch Q CFC Gross (PAS) (delta {delta:,.0f})",
                        expected=f"Sch Q PAS: {q_cfc_gross:,.0f}",
                        actual=f"Sch I-1 SubF: {i1_subf:,.0f}",
                        delta=delta,
                        context="Sch I-1 Subpart F income should tie to Sch Q CFC total gross (PAS basket)",
                    )

        # XSC-003: I-1 Tested Income/Loss = Sch Q Tested Net Income (GEN)
        if q_gen is not None:
            i1_tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_FunctionalCurrencyAmt")
            q_net = safe_float(q_gen, "IRS5471ScheduleQ_TotalTestedIncomeGrp_NetIncomeAmt")
            if q_net is None:
                q_net = safe_float(q_gen, "IRS5471ScheduleQ_TestedIncomeGrp_NetIncomeAmt")
            if i1_tested is not None and q_net is not None:
                delta = abs(i1_tested - q_net)
                if delta > max(1, abs(i1_tested) * 0.001) if i1_tested else delta > 1:
                    ctx.add(
                        check_id="XSC-003", severity="HIGH", category="cross_schedule",
                        entity_code=code, entity_name=name,
                        description=f"Sch I-1 Tested Income != Sch Q Tested Net (GEN) (delta {delta:,.0f})",
                        expected=f"Sch Q GEN: {q_net:,.0f}",
                        actual=f"Sch I-1: {i1_tested:,.0f}",
                        delta=delta,
                        context="Sch I-1 tested income (FC) should tie to Sch Q tested net income (GEN basket)",
                    )

        # XSC-004: Sch E1 Tested Taxes USD = Sch Q Allowed FTC (GEN)
        if q_gen is not None and not sch_e.empty and code in sch_e.index:
            e = sch_e.loc[code]
            e_tax = safe_float(e, "IRS5471ScheduleE_Frm5471SchETestedIncomeGrp_TotalTaxInUSDollarsAmt")
            q_ftc = safe_float(q_gen, "IRS5471ScheduleQ_CFCTotalIncomeGrp_TotalAllowedFrgnTaxCreditAmt")
            if q_ftc is None:
                q_ftc = safe_float(q_gen, "IRS5471ScheduleQ_TotalTestedIncomeGrp_TotalAllowedFrgnTaxCreditAmt")
            if e_tax is not None and q_ftc is not None:
                delta = abs(e_tax - q_ftc)
                if delta > max(1, abs(e_tax) * 0.01):
                    ctx.add(
                        check_id="XSC-004", severity="MEDIUM", category="cross_schedule",
                        entity_code=code, entity_name=name,
                        description=f"Sch E1 Tested Taxes != Sch Q Allowed FTC (GEN) (delta ${delta:,.0f})",
                        expected=f"Sch Q GEN FTC: ${q_ftc:,.0f}",
                        actual=f"Sch E1 taxes: ${e_tax:,.0f}",
                        delta=delta,
                        context="Sch E Part I tested income taxes (USD) should tie to Sch Q allowed FTC (GEN)",
                    )

        # XSC-005: Sch Q Other Expenses != 0 (unexpected)
        for basket_key, q_row in q_baskets.items():
            other_exp = safe_float(q_row, "IRS5471ScheduleQ_CFCTotalIncomeGrp_TotalOtherExpensesAmt")
            if other_exp is not None and abs(other_exp) > 1:
                ctx.add(
                    check_id="XSC-005", severity="LOW", category="cross_schedule",
                    entity_code=code, entity_name=name,
                    description=f"Sch Q Other Expenses != 0 ({basket_key} basket: {other_exp:,.0f})",
                    expected="0",
                    actual=f"{other_exp:,.0f}",
                    delta=abs(other_exp),
                    context=f"Sch Q other expenses ({basket_key}) are typically zero; non-zero may indicate misallocation",
                )


def _check_jp_consistency(ctx: CheckContext, sch_j: pd.DataFrame, sch_p: pd.DataFrame):
    """XSC-006 and XSC-007: Category 1 filer / J-P basket consistency."""
    df = ctx.df
    if df.empty:
        return

    # Build set of entities with Sch P by basket
    p_entities = set()
    p_by_entity_basket = set()
    if not sch_p.empty:
        for _, row in sch_p.iterrows():
            ref_id = row.get("_reference_id", "")
            basket = row.get("_basket", "")
            if ref_id:
                p_entities.add(ref_id)
                p_by_entity_basket.add((ref_id, basket))

    # Build set of entities with Sch J by basket
    j_by_entity_basket = {}
    if not sch_j.empty:
        for _, row in sch_j.iterrows():
            ref_id = row.get("_reference_id", "")
            basket = row.get("_basket", "")
            if ref_id:
                j_by_entity_basket.setdefault(ref_id, set()).add(basket)

    # XSC-006: Category 1 filer must have Schedule P
    for _, ent_row in df.iterrows():
        code = ent_row.get("_reference_id", "")
        if not code:
            continue
        cats = ent_row.get("_category_filers", [])
        if not isinstance(cats, list):
            continue
        is_cat1 = any(c.startswith("1") for c in cats)
        if is_cat1 and code not in p_entities:
            name = ctx.entity_name(code)
            ctx.add(
                check_id="XSC-006", severity="HIGH", category="cross_schedule",
                entity_code=code, entity_name=name,
                description="Category 1 filer without Schedule P",
                expected="Schedule P populated",
                actual="Schedule P missing",
                context="Category 1 filers must report previously taxed E&P on Schedule P",
            )

    # XSC-007: If Sch J exists by basket, corresponding Sch P should exist
    for code, j_baskets in j_by_entity_basket.items():
        for basket in j_baskets:
            if basket and (code, basket) not in p_by_entity_basket:
                if code in p_entities:
                    continue
                name = ctx.entity_name(code)
                ctx.add(
                    check_id="XSC-007", severity="MEDIUM", category="cross_schedule",
                    entity_code=code, entity_name=name,
                    description=f"Sch J ({basket}) exists but no corresponding Sch P",
                    expected=f"Sch P ({basket}) populated",
                    actual="Sch P missing for this basket",
                    context="Schedule J and P should both exist per basket for PTEP tracking",
                )


def _check_sch_i_indicators(ctx: CheckContext):
    """XSC-008: Schedule I indicators unexpectedly set to Yes."""
    parser = ctx.parser
    sch_i = parser.extract_form("IRS5471ScheduleI")
    if sch_i.empty:
        return

    indicators = [
        ("IRS5471ScheduleI_IncomeBlockedInd", "Blocked Income (7a)"),
        ("IRS5471ScheduleI_IncomeUnblockedInd", "Unblocked Income (7b)"),
        ("IRS5471ScheduleI_EDAccountInd", "E&D Account (8a)"),
    ]

    for _, row in sch_i.iterrows():
        code = row.get("_reference_id", "")
        if not code:
            continue
        name = ctx.entity_name(code)

        for col, label in indicators:
            val = row.get(col, "")
            if isinstance(val, str) and val.strip().upper() in ("X", "YES", "TRUE", "Y", "1"):
                ctx.add(
                    check_id="XSC-008", severity="MEDIUM", category="cross_schedule",
                    entity_code=code, entity_name=name,
                    description=f"Sch I indicator '{label}' unexpectedly marked Yes",
                    expected="No / blank (standard for most CFCs)",
                    actual=f"{val}",
                    context=f"Sch I {label} is Yes — verify this is intentional; most CFCs should be No",
                )


def _check_sch_e_local_vs_fc(ctx: CheckContext, sch_e: pd.DataFrame):
    """XSC-009: Schedule E local currency tax vs functional currency tax mismatch."""
    if sch_e.empty:
        return

    local_col = "IRS5471ScheduleE_TxsForeignTaxCrAllowedGrp_TaxInForeignCurrencyAmt"
    fc_col = "IRS5471ScheduleE_TxsForeignTaxCrAllowedGrp_TaxInFunctionalCurrencyAmt"

    for code in sch_e.index:
        if code == "":
            continue
        e = sch_e.loc[code]
        local_tax = safe_float(e, local_col)
        fc_tax = safe_float(e, fc_col)

        if local_tax is None or fc_tax is None:
            continue
        if local_tax == 0 and fc_tax == 0:
            continue

        fc_currency = e.get("_functional_currency", "")
        country = e.get("_country_code", "")
        if not fc_currency and not country:
            continue

        delta = abs(local_tax - fc_tax)
        if delta > max(1, abs(fc_tax) * 0.001):
            name = ctx.entity_name(code)
            ctx.add(
                check_id="XSC-009", severity="LOW", category="cross_schedule",
                entity_code=code, entity_name=name,
                description=f"Sch E local currency tax != FC tax (delta {delta:,.0f})",
                expected=f"FC tax: {fc_tax:,.0f}",
                actual=f"Local tax: {local_tax:,.0f}",
                delta=delta,
                context="When functional currency = local currency, these amounts should match",
            )

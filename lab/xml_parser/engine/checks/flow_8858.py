"""Flow checks for Form 8858 (FLO-8858-001 to FLO-8858-008): arithmetic ties."""

from __future__ import annotations

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_flow_checks_8858(ctx: CheckContext) -> list[Finding]:
    """Run flow/arithmetic checks on Form 8858 schedules."""
    parser = ctx.parser

    sch_c = parser.extract_form_8858("IRS8858ScheduleC")
    sch_f = parser.extract_form_8858("IRS8858ScheduleF")
    sch_h = parser.extract_form_8858("IRS8858ScheduleH")
    main = parser.extract_form_8858("IRS8858")

    dormant_entities = set()
    if not main.empty:
        dormant_entities = set(
            main.loc[main["_dormant"] == True, "_reference_id"].unique()
        ) - {""}

    if not sch_c.empty:
        sch_c_idx = sch_c.set_index("_reference_id")
        _check_sch_c_flow(ctx, sch_c_idx, dormant_entities)

    if not sch_f.empty:
        sch_f_idx = sch_f.set_index("_reference_id")
        _check_sch_f_flow(ctx, sch_f_idx, dormant_entities)

    if not sch_h.empty:
        sch_h_idx = sch_h.set_index("_reference_id")
        _check_sch_h_flow(ctx, sch_h_idx, dormant_entities)

    # Cross-schedule: Sch C net income vs Sch H line 1
    if not sch_c.empty and not sch_h.empty:
        _check_c_vs_h(ctx, sch_c_idx, sch_h_idx, dormant_entities)

    return ctx.findings


def _check_sch_c_flow(ctx: CheckContext, sch_c_idx, dormant: set):
    """FLO-8858-005: Total income = sum of lines; FLO-8858-008: Gross profit = receipts - COGS."""
    prefix = "IRS8858ScheduleC_"

    for code in sch_c_idx.index.unique():
        if code in dormant or not code:
            continue
        row = sch_c_idx.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        name = row.get("_entity_name", code)

        # FLO-8858-008: Gross profit = receipts - COGS
        receipts = safe_float(row, f"{prefix}GrossReceiptsOrSalesIncmStmt_USDollarAmt")
        cogs = safe_float(row, f"{prefix}CostOfGoodsSoldIncmStmt_USDollarAmt")
        gross_profit = safe_float(row, f"{prefix}GrossProfitIncmStmt_USDollarAmt")

        if receipts is not None and gross_profit is not None:
            expected_gp = receipts - (cogs or 0)
            diff = abs(gross_profit - expected_gp)
            if diff > max(100, abs(expected_gp) * 0.01):
                ctx.add(
                    check_id="FLO-8858-008", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch C gross profit ({gross_profit:,.0f}) ≠ receipts ({receipts:,.0f}) - COGS ({cogs or 0:,.0f})",
                    expected=f"{expected_gp:,.0f}", actual=f"{gross_profit:,.0f}",
                    delta=gross_profit - expected_gp,
                )

        # FLO-8858-005: Total income = sum of income lines
        income_fields = [
            f"{prefix}GrossProfitIncmStmt_USDollarAmt",
            f"{prefix}DividendsIncmStmt_USDollarAmt",
            f"{prefix}InterestIncmStmt_USDollarAmt",
            f"{prefix}GrossRentRyltyLcnsFeeIncmStmt_USDollarAmt",
            f"{prefix}GrossIncmPerfSrvcIncmStmt_USDollarAmt",
            f"{prefix}FrgnCurrencyGainLossIncmStmt_USDollarAmt",
            f"{prefix}OtherIncmStmt_USDollarAmt",
        ]
        total_income = safe_float(row, f"{prefix}TotalIncmStmt_USDollarAmt")
        if total_income is not None:
            computed_sum = sum(safe_float(row, f) or 0 for f in income_fields)
            diff = abs(total_income - computed_sum)
            if diff > max(100, abs(total_income) * 0.01):
                ctx.add(
                    check_id="FLO-8858-005", severity="MEDIUM", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch C total income ({total_income:,.0f}) ≠ sum of lines ({computed_sum:,.0f})",
                    expected=f"{computed_sum:,.0f}", actual=f"{total_income:,.0f}",
                    delta=total_income - computed_sum,
                )


def _check_sch_f_flow(ctx: CheckContext, sch_f_idx, dormant: set):
    """FLO-8858-002/003/004: Balance sheet ties."""
    prefix = "IRS8858ScheduleF_"

    for code in sch_f_idx.index.unique():
        if code in dormant or not code:
            continue
        row = sch_f_idx.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        name = row.get("_entity_name", code)

        for period, suffix in [("BOY", "BeginningAmt"), ("EOY", "EndingAmt")]:
            cash = safe_float(row, f"{prefix}CashAndOtherCurrentAssets_{suffix}")
            other = safe_float(row, f"{prefix}OtherAssetsBalanceSheet_{suffix}")
            total_assets = safe_float(row, f"{prefix}TotalAssetsBalanceSheet_{suffix}")
            liab = safe_float(row, f"{prefix}LiabilitiesBalanceSheet_{suffix}")
            equity = safe_float(row, f"{prefix}OwnerEquityBalanceSheet_{suffix}")
            total_le = safe_float(row, f"{prefix}TotLiabOwnerEquityBalanceSheet_{suffix}")

            # FLO-8858-002: Total assets = cash + other
            if total_assets is not None and cash is not None and other is not None:
                computed = cash + other
                diff = abs(total_assets - computed)
                if diff > max(100, abs(total_assets) * 0.001):
                    ctx.add(
                        check_id="FLO-8858-002", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch F {period}: total assets ({total_assets:,.0f}) ≠ cash ({cash:,.0f}) + other ({other:,.0f})",
                        expected=f"{computed:,.0f}", actual=f"{total_assets:,.0f}",
                        delta=total_assets - computed,
                    )

            # FLO-8858-003: Total L+E = liabilities + equity
            if total_le is not None and liab is not None and equity is not None:
                computed = liab + equity
                diff = abs(total_le - computed)
                if diff > max(100, abs(total_le) * 0.001):
                    ctx.add(
                        check_id="FLO-8858-003", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch F {period}: total L+E ({total_le:,.0f}) ≠ liab ({liab:,.0f}) + equity ({equity:,.0f})",
                        expected=f"{computed:,.0f}", actual=f"{total_le:,.0f}",
                        delta=total_le - computed,
                    )

            # FLO-8858-004: A = L + E
            if total_assets is not None and total_le is not None:
                diff = abs(total_assets - total_le)
                if diff > max(100, abs(total_assets) * 0.001):
                    ctx.add(
                        check_id="FLO-8858-004", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch F {period}: assets ({total_assets:,.0f}) ≠ liab+equity ({total_le:,.0f})",
                        expected=f"{total_le:,.0f}", actual=f"{total_assets:,.0f}",
                        delta=total_assets - total_le,
                    )


def _check_sch_h_flow(ctx: CheckContext, sch_h_idx, dormant: set):
    """FLO-8858-006/007: E&P arithmetic ties."""
    prefix = "IRS8858ScheduleH_"

    for code in sch_h_idx.index.unique():
        if code in dormant or not code:
            continue
        row = sch_h_idx.loc[code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        name = row.get("_entity_name", code)

        net_income = safe_float(row, f"{prefix}ForeignCYNetIncomePerBooksAmt")
        additions = safe_float(row, f"{prefix}TotalNetAdditionsAmt")
        subtractions = safe_float(row, f"{prefix}TotalNetSubtractionsAmt")
        current_ep = safe_float(row, f"{prefix}CurrentEarningsAndProfitsAmt")
        ep_usd = safe_float(row, f"{prefix}CurrEarnAndPrftInUSDollarsAmt")
        fx = safe_float(row, f"{prefix}ExchangeRt")

        # FLO-8858-006: E&P = net income + additions - subtractions
        if net_income is not None and current_ep is not None:
            computed = net_income + (additions or 0) - (subtractions or 0)
            diff = abs(current_ep - computed)
            if diff > max(100, abs(computed) * 0.01):
                ctx.add(
                    check_id="FLO-8858-006", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch H E&P ({current_ep:,.0f}) ≠ net income ({net_income:,.0f}) + adj ({(additions or 0) - (subtractions or 0):,.0f})",
                    expected=f"{computed:,.0f}", actual=f"{current_ep:,.0f}",
                    delta=current_ep - computed,
                )

        # FLO-8858-007: USD E&P ≈ FC E&P × exchange rate
        if current_ep is not None and ep_usd is not None and fx is not None and fx > 0:
            computed_usd = current_ep / fx
            diff = abs(ep_usd - computed_usd)
            tolerance = max(100, abs(computed_usd) * 0.01)
            if diff > tolerance:
                ctx.add(
                    check_id="FLO-8858-007", severity="MEDIUM", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch H USD E&P ({ep_usd:,.0f}) ≠ FC E&P ({current_ep:,.0f}) ÷ FX ({fx:.6f}) = {computed_usd:,.0f}",
                    expected=f"{computed_usd:,.0f}", actual=f"{ep_usd:,.0f}",
                    delta=ep_usd - computed_usd,
                )


def _check_c_vs_h(ctx: CheckContext, sch_c_idx, sch_h_idx, dormant: set):
    """FLO-8858-001: Sch C net income vs Sch H line 1 (net income per books)."""
    prefix_c = "IRS8858ScheduleC_"
    prefix_h = "IRS8858ScheduleH_"

    common = set(sch_c_idx.index.unique()) & set(sch_h_idx.index.unique()) - dormant - {""}

    for code in common:
        c_row = sch_c_idx.loc[code]
        h_row = sch_h_idx.loc[code]
        if isinstance(c_row, pd.DataFrame):
            c_row = c_row.iloc[0]
        if isinstance(h_row, pd.DataFrame):
            h_row = h_row.iloc[0]
        name = c_row.get("_entity_name", code)

        # Use FC amount from Sch C if available, else USD
        net_c_fc = safe_float(c_row, f"{prefix_c}NetIncomeLossPerBooksIncmStmt_FunctionalCurrencyAmt")
        net_c_usd = safe_float(c_row, f"{prefix_c}NetIncomeLossPerBooksIncmStmt_USDollarAmt")
        net_h = safe_float(h_row, f"{prefix_h}ForeignCYNetIncomePerBooksAmt")

        if net_h is None:
            continue

        # Sch H is in FC, so compare to FC if available
        net_c = net_c_fc if net_c_fc is not None else net_c_usd
        if net_c is None:
            continue

        diff = abs(net_c - net_h)
        tolerance = max(100, abs(net_h) * 0.01)
        if diff > tolerance:
            ctx.add(
                check_id="FLO-8858-001", severity="HIGH", category="flow",
                entity_code=code, entity_name=name,
                description=f"Sch C net income ({net_c:,.0f}) ≠ Sch H line 1 ({net_h:,.0f})",
                expected=f"{net_h:,.0f}", actual=f"{net_c:,.0f}",
                delta=net_c - net_h,
                context="Sch C net income should tie to Sch H line 1 (net income per books in FC)",
            )

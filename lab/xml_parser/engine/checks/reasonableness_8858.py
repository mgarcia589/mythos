"""Reasonableness checks for Form 8858 (RSN-8858-001 to RSN-8858-004)."""

from __future__ import annotations

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_reasonableness_checks_8858(ctx: CheckContext) -> list[Finding]:
    """Run reasonableness checks on Form 8858 data."""
    parser = ctx.parser

    main = parser.extract_form_8858("IRS8858")
    sch_c = parser.extract_form_8858("IRS8858ScheduleC")
    sch_f = parser.extract_form_8858("IRS8858ScheduleF")
    sch_h = parser.extract_form_8858("IRS8858ScheduleH")

    dormant_entities = set()
    if not main.empty:
        dormant_entities = set(
            main.loc[main["_dormant"] == True, "_reference_id"].unique()
        ) - {""}

    if not sch_h.empty:
        _check_exchange_rate(ctx, sch_h, dormant_entities)

    if not sch_f.empty:
        _check_zero_assets(ctx, sch_f, main, dormant_entities)

    if not sch_c.empty:
        _check_extreme_loss(ctx, sch_c, dormant_entities)

    if not sch_h.empty:
        _check_ep_usd_no_fx(ctx, sch_h, dormant_entities)

    return ctx.findings


def _check_exchange_rate(ctx: CheckContext, sch_h, dormant: set):
    """RSN-8858-001: Exchange rate outside reasonable range (0.01–100)."""
    prefix = "IRS8858ScheduleH_"

    for _, row in sch_h.iterrows():
        code = row.get("_reference_id", "")
        if not code or code in dormant:
            continue
        fc = row.get("_functional_currency", "")
        if fc == "USD":
            continue

        fx = safe_float(row, f"{prefix}ExchangeRt")
        if fx is not None and fx > 0:
            if fx < 0.01 or fx > 100:
                name = row.get("_entity_name", code)
                ctx.add(
                    check_id="RSN-8858-001", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Exchange rate {fx:.6f} is outside reasonable range (0.01–100) for {fc}",
                    context="Extreme exchange rates may indicate data entry error or wrong currency code",
                )


def _check_zero_assets(ctx: CheckContext, sch_f, main, dormant: set):
    """RSN-8858-002: Total assets = 0 for non-dormant FDE."""
    prefix = "IRS8858ScheduleF_"

    for _, row in sch_f.iterrows():
        code = row.get("_reference_id", "")
        if not code or code in dormant:
            continue

        eoy_assets = safe_float(row, f"{prefix}TotalAssetsBalanceSheet_EndingAmt")
        if eoy_assets is not None and eoy_assets == 0:
            name = row.get("_entity_name", code)
            ctx.add(
                check_id="RSN-8858-002", severity="LOW", category="reasonableness",
                entity_code=code, entity_name=name,
                description="Total assets = 0 at EOY for non-dormant FDE",
                context="Non-dormant FDEs typically have assets; may indicate incomplete data or should be marked dormant",
            )


def _check_extreme_loss(ctx: CheckContext, sch_c, dormant: set):
    """RSN-8858-003: Net loss > 200% of revenue."""
    prefix = "IRS8858ScheduleC_"

    for _, row in sch_c.iterrows():
        code = row.get("_reference_id", "")
        if not code or code in dormant:
            continue

        revenue = safe_float(row, f"{prefix}GrossReceiptsOrSalesIncmStmt_USDollarAmt")
        net_income = safe_float(row, f"{prefix}NetIncomeLossPerBooksIncmStmt_USDollarAmt")

        if revenue is not None and revenue > 0 and net_income is not None:
            if net_income < 0 and abs(net_income) > 2 * revenue:
                name = row.get("_entity_name", code)
                ctx.add(
                    check_id="RSN-8858-003", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Net loss (${abs(net_income):,.0f}) exceeds 200% of revenue (${revenue:,.0f})",
                    context="Extreme loss relative to revenue may indicate misclassification or one-time write-off",
                )


def _check_ep_usd_no_fx(ctx: CheckContext, sch_h, dormant: set):
    """RSN-8858-004: E&P in USD populated but no exchange rate."""
    prefix = "IRS8858ScheduleH_"

    for _, row in sch_h.iterrows():
        code = row.get("_reference_id", "")
        if not code or code in dormant:
            continue

        fc = row.get("_functional_currency", "")
        if fc == "USD":
            continue

        ep_usd = safe_float(row, f"{prefix}CurrEarnAndPrftInUSDollarsAmt")
        fx = safe_float(row, f"{prefix}ExchangeRt")

        if ep_usd is not None and ep_usd != 0 and (fx is None or fx == 0):
            name = row.get("_entity_name", code)
            ctx.add(
                check_id="RSN-8858-004", severity="LOW", category="reasonableness",
                entity_code=code, entity_name=name,
                description=f"E&P in USD (${ep_usd:,.0f}) populated but exchange rate is missing",
                context="Non-USD entity should show exchange rate used for translation",
            )

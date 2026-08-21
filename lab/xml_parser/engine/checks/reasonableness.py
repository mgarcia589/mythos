"""Reasonableness checks (RSN-001 to RSN-010): values outside expected ranges."""

from __future__ import annotations

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.core.constants import EXPECTED_FX_RANGES
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_reasonableness_checks(ctx: CheckContext) -> list[Finding]:
    """Run all reasonableness checks and return findings."""
    parser = ctx.parser
    df = ctx.df

    sch_h = parser.extract_form("IRS5471ScheduleH")
    sch_i1 = parser.extract_form("IRS5471ScheduleI1")
    sch_f = parser.extract_form("IRS5471ScheduleF")

    if sch_h.empty:
        return ctx.findings
    sch_h = sch_h.set_index("_reference_id")
    if not sch_i1.empty:
        sch_i1 = sch_i1.set_index("_reference_id")
    if not sch_f.empty:
        sch_f = sch_f.set_index("_reference_id")

    for code in sch_h.index:
        if code == "":
            continue
        name = ctx.entity_name(code)
        h = sch_h.loc[code]

        # RSN-001
        ep_usd = safe_float(h, "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt")
        if ep_usd is not None and abs(ep_usd) > 1_000_000_000:
            ctx.add(
                check_id="RSN-001", severity="LOW", category="reasonableness",
                entity_code=code, entity_name=name,
                description=f"E&P exceeds $1B (${ep_usd:,.0f}) — verify this is correct",
                actual=f"${ep_usd:,.0f}",
            )

        # RSN-002
        fx_rate = safe_float(h, "IRS5471ScheduleH_ExchangeRt")
        if fx_rate is not None and fx_rate > 0:
            _check_fx_reasonableness(ctx, code, name, fx_rate)

        # RSN-003
        ep_fc = safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")
        net_income = safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
        if ep_fc is not None and net_income is not None and net_income != 0:
            implied_tax = net_income - ep_fc
            etr = implied_tax / net_income if net_income != 0 else 0
            if etr > 0.50 or etr < -0.10:
                ctx.add(
                    check_id="RSN-003", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Implied ETR of {etr:.0%} is outside normal range (0-50%)",
                    expected="0% to 50%",
                    actual=f"{etr:.1%} (income {net_income:,.0f}, E&P {ep_fc:,.0f})",
                    context="High ETR may indicate adjustments; negative may indicate refunds or errors",
                )

        # RSN-004
        if not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
            subf = safe_float(i1, "IRS5471ScheduleI1_SubpartFIncomeAmt")
            if (tested is not None and subf is not None
                    and tested > 0 and subf > 0
                    and abs(tested - subf) < 1):
                ctx.add(
                    check_id="RSN-004", severity="LOW", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Tested income (${tested:,.0f}) exactly equals SubF income — possible misclassification",
                    expected="Different amounts unless coincidence",
                    actual=f"Tested = SubF = ${tested:,.0f}",
                    context="Same amount in both categories may indicate double-counting or misallocation",
                )

        # RSN-006
        if not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            qbai = safe_float(i1, "IRS5471ScheduleI1_QBAIAmt")
            if not sch_f.empty and code in sch_f.index:
                f_row = sch_f.loc[code]
                total_assets = safe_float(f_row, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
                if qbai is not None and total_assets is not None and qbai > total_assets and qbai > 0:
                    ctx.add(
                        check_id="RSN-006", severity="HIGH", category="reasonableness",
                        entity_code=code, entity_name=name,
                        description=f"QBAI (${qbai:,.0f}) exceeds total assets (${total_assets:,.0f}) — impossible",
                        expected=f"QBAI <= Total assets (${total_assets:,.0f})",
                        actual=f"QBAI = ${qbai:,.0f}",
                        delta=qbai - total_assets,
                        context="QBAI is a subset of tangible assets; it cannot exceed total assets on Sch F",
                    )

        # RSN-007
        if not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            gross = safe_float(i1, "IRS5471ScheduleI1_GrossIncomeAmt")
            interest = safe_float(i1, "IRS5471ScheduleI1_InterestExpenseAmt")
            if (gross is not None and interest is not None
                    and interest > 0 and gross > 0
                    and interest > gross):
                ctx.add(
                    check_id="RSN-007", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Interest expense (${interest:,.0f}) exceeds gross income (${gross:,.0f})",
                    expected="Interest < gross income for operating entities",
                    actual=f"Interest/Income = {interest/gross:.0%}",
                    context="Extremely high leverage — verify holding company or inter-company debt structure",
                )

        # RSN-008: Tested income entity with QBAI = 0
        if not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
            qbai = safe_float(i1, "IRS5471ScheduleI1_QBAIAmt")
            if (tested is not None and tested > 100000
                    and (qbai is None or qbai == 0)):
                ctx.add(
                    check_id="RSN-008", severity="LOW", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Tested income (${tested:,.0f}) but QBAI = $0 — no deemed tangible return offset",
                    expected="QBAI > 0 for operating entities with tangible assets",
                    actual=f"Tested income ${tested:,.0f}, QBAI $0",
                    context="QBAI reduces GILTI inclusion (10% DTIR). Zero QBAI means full inclusion unless pure services entity.",
                )

        # RSN-009: E&P additions > 200% of net income
        net_income_rsn = safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
        total_add = safe_float(h, "IRS5471ScheduleH_TotalNetAdditionsAmt")
        if (net_income_rsn is not None and total_add is not None
                and net_income_rsn > 0 and total_add > net_income_rsn * 2
                and total_add > 500000):
            ratio = total_add / net_income_rsn
            ctx.add(
                check_id="RSN-009", severity="MEDIUM", category="reasonableness",
                entity_code=code, entity_name=name,
                description=f"E&P additions ({total_add:,.0f}) = {ratio:.0f}x net income ({net_income_rsn:,.0f})",
                expected="Additions typically < 2x net income",
                actual=f"Additions/Income = {ratio:.1f}x",
                context="Large additions relative to income may indicate unusual book-tax differences or errors",
            )

        # RSN-010: Negative E&P but entity is NOT tested loss
        ep_fc = safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")
        if ep_fc is not None and ep_fc < -10000 and not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
            if tested is not None and tested > 0:
                ctx.add(
                    check_id="RSN-010", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"Negative E&P ({ep_fc:,.0f} FC) but positive tested income (${tested:,.0f})",
                    expected="Negative E&P should generally result in tested loss, not income",
                    actual=f"E&P: {ep_fc:,.0f}, Tested: ${tested:,.0f}",
                    context="Book-tax differences can cause divergence, but large gap warrants review of adjustments",
                )

    # RSN-005
    ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
    if ep_col in sch_h.columns:
        ep_values = pd.to_numeric(sch_h[ep_col], errors="coerce").dropna()
        if len(ep_values) >= 5:
            positive = (ep_values > 0).sum()
            negative = (ep_values < 0).sum()
            if positive == 0 or negative == 0:
                sign = "positive" if positive > 0 else "negative"
                ctx.add(
                    check_id="RSN-005", severity="LOW", category="reasonableness",
                    entity_code="ALL", entity_name="(all entities)",
                    description=f"All {len(ep_values)} entities have {sign} E&P — unusual for diversified group",
                    context="Most multinational groups have a mix of profitable and loss-making entities",
                )

    return ctx.findings


def _check_fx_reasonableness(ctx: CheckContext, code: str, name: str, fx_rate: float):
    for currency, (low, high) in EXPECTED_FX_RANGES.items():
        if low * 0.7 <= fx_rate <= high * 1.3:
            if fx_rate < low * 0.85 or fx_rate > high * 1.15:
                ctx.add(
                    check_id="RSN-002", severity="MEDIUM", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"FX rate {fx_rate:.4f} near boundary of expected range for {currency} ({low}-{high})",
                    expected=f"{low} to {high}",
                    actual=f"{fx_rate:.4f}",
                    context="Verify rate is correct — may be stale or incorrectly entered",
                )
            return

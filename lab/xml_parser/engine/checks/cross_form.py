"""Cross-form checks (XFM-001 to XFM-003): Form 5471 vs Form 8990 ties.

Validates data consistency between per-entity Schedule C data and the
parent-level Form 8990 (Section 163(j) limitation). Only fires when
IRS8990 is present in the return.
"""

from __future__ import annotations

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_cross_form_checks(ctx: CheckContext) -> list[Finding]:
    """Run cross-form consistency checks (5471 vs 8990)."""
    parser = ctx.parser

    # Extract top-level IRS8990 — only present if 163(j) applies
    irs8990 = parser.extract_top_level_form("IRS8990")
    if irs8990.empty:
        return ctx.findings

    f8990 = irs8990.iloc[0]

    # Extract Schedule C for per-entity interest data
    sch_c = parser.extract_form("IRS5471ScheduleC")
    if sch_c.empty:
        return ctx.findings
    sch_c = sch_c.set_index("_reference_id")

    _check_interest_ties(ctx, sch_c, f8990)
    _check_safe_harbor(ctx, f8990)

    return ctx.findings


def _check_interest_ties(ctx: CheckContext, sch_c: pd.DataFrame, f8990: pd.Series):
    """XFM-001 and XFM-002: Sch C interest vs 8990 BII/BIE."""

    # 8990 reports aggregate amounts across all entities
    bii_8990 = safe_float(f8990, "IRS8990_CYBusinessInterestIncomeAmt")
    bie_8990 = safe_float(f8990, "IRS8990_BusInterestExpnsNotPassThruAmt")

    # Sum all entity-level interest from Schedule C
    total_interest_income = 0.0
    total_interest_expense = 0.0
    has_c_data = False

    for code in sch_c.index:
        if code == "":
            continue
        c = sch_c.loc[code]
        inc = safe_float(c, "IRS5471ScheduleC_USInterestIncomeAmt")
        exp = safe_float(c, "IRS5471ScheduleC_USInterestDeductionAmt")
        if inc is not None:
            total_interest_income += inc
            has_c_data = True
        if exp is not None:
            total_interest_expense += exp
            has_c_data = True

    if not has_c_data:
        return

    # XFM-001: Total Sch C interest income vs 8990 BII
    if bii_8990 is not None and total_interest_income > 0:
        delta = abs(total_interest_income - bii_8990)
        if delta > max(10, abs(bii_8990) * 0.01) and delta > 1:
            ctx.add(
                check_id="XFM-001", severity="MEDIUM", category="cross_form",
                entity_code="ALL", entity_name="All Entities (aggregate)",
                description=f"Total Sch C interest income (${total_interest_income:,.0f}) != 8990 BII (${bii_8990:,.0f})",
                expected=f"8990 BII: ${bii_8990:,.0f}",
                actual=f"Sum Sch C: ${total_interest_income:,.0f}",
                delta=delta,
                context="Aggregate interest income from all 5471 Sch C should tie to Form 8990 business interest income",
            )

    # XFM-002: Total Sch C interest expense vs 8990 BIE
    if bie_8990 is not None and total_interest_expense > 0:
        delta = abs(total_interest_expense - bie_8990)
        if delta > max(10, abs(bie_8990) * 0.01) and delta > 1:
            ctx.add(
                check_id="XFM-002", severity="MEDIUM", category="cross_form",
                entity_code="ALL", entity_name="All Entities (aggregate)",
                description=f"Total Sch C interest expense (${total_interest_expense:,.0f}) != 8990 BIE (${bie_8990:,.0f})",
                expected=f"8990 BIE: ${bie_8990:,.0f}",
                actual=f"Sum Sch C: ${total_interest_expense:,.0f}",
                delta=delta,
                context="Aggregate interest expense from all 5471 Sch C should tie to Form 8990 business interest expense",
            )


def _check_safe_harbor(ctx: CheckContext, f8990: pd.Series):
    """XFM-003: Form 8990 safe harbor election indicator should be No."""
    safe_harbor = f8990.get("IRS8990_SafeHarborElectionInd", "")

    if isinstance(safe_harbor, str) and safe_harbor.strip().upper() in ("X", "YES", "TRUE", "Y", "1"):
        ctx.add(
            check_id="XFM-003", severity="MEDIUM", category="cross_form",
            entity_code="ALL", entity_name="Form 8990 (Parent Return)",
            description="Form 8990 Safe Harbor election is checked",
            expected="No / blank (standard for most filers)",
            actual=f"{safe_harbor}",
            context="Safe harbor election on Form 8990 is unusual — verify this is intentional for 163(j)",
        )

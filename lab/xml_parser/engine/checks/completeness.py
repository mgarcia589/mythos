"""Completeness checks (CMP-001 to CMP-009): missing schedules or required data."""

from __future__ import annotations

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_completeness_checks(ctx: CheckContext) -> list[Finding]:
    """Run all completeness checks and return findings."""
    parser = ctx.parser
    df = ctx.df

    sch_h = parser.extract_form("IRS5471ScheduleH")
    sch_i1 = parser.extract_form("IRS5471ScheduleI1")
    sch_e = parser.extract_form("IRS5471ScheduleE")
    sch_f = parser.extract_form("IRS5471ScheduleF")
    sch_j = parser.extract_form("IRS5471ScheduleJ")
    sch_c = parser.extract_form("IRS5471ScheduleC")

    entities_in_return = set(df["_reference_id"].unique()) - {""}
    h_entities = set(sch_h["_reference_id"].unique()) - {""} if not sch_h.empty else set()
    i1_entities = set(sch_i1["_reference_id"].unique()) - {""} if not sch_i1.empty else set()
    e_entities = set(sch_e["_reference_id"].unique()) - {""} if not sch_e.empty else set()
    f_entities = set(sch_f["_reference_id"].unique()) - {""} if not sch_f.empty else set()
    j_entities = set(sch_j["_reference_id"].unique()) - {""} if not sch_j.empty else set()
    c_entities = set(sch_c["_reference_id"].unique()) - {""} if not sch_c.empty else set()

    if not sch_h.empty:
        sch_h_idx = sch_h.set_index("_reference_id")
    if not sch_i1.empty:
        sch_i1_idx = sch_i1.set_index("_reference_id")
    if not sch_f.empty:
        sch_f_idx = sch_f.set_index("_reference_id")

    for code in entities_in_return:
        name = ctx.entity_name(code)

        # CMP-001
        if code not in h_entities:
            ctx.add(
                check_id="CMP-001", severity="HIGH", category="completeness",
                entity_code=code, entity_name=name,
                description="Entity in return but missing Schedule H (E&P computation)",
                context="Every 5471 entity should have current year E&P computed",
            )

        # CMP-002
        if code in h_entities and code not in i1_entities:
            ctx.add(
                check_id="CMP-002", severity="MEDIUM", category="completeness",
                entity_code=code, entity_name=name,
                description="Entity has Sch H but no Sch I-1 (GILTI classification missing)",
                context="GILTI requires classification of income as tested/HTE/SubF for all CFCs",
            )

        # CMP-003
        if code in i1_entities and code not in e_entities:
            i1 = sch_i1_idx.loc[code]
            tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
            if tested is not None and tested > 0:
                ctx.add(
                    check_id="CMP-003", severity="MEDIUM", category="completeness",
                    entity_code=code, entity_name=name,
                    description=f"Entity has tested income (${tested:,.0f}) but no Sch E (foreign taxes)",
                    context="Tested income entities typically have foreign taxes to report on Sch E",
                )

        # CMP-004
        if code in f_entities:
            f = sch_f_idx.loc[code]
            boy_assets = safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt")
            eoy_assets = safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
            if boy_assets is not None and boy_assets != 0 and (eoy_assets is None or eoy_assets == 0):
                ctx.add(
                    check_id="CMP-004", severity="HIGH", category="completeness",
                    entity_code=code, entity_name=name,
                    description=f"Sch F has BOY assets ({boy_assets:,.0f}) but EOY is zero/missing",
                    expected="EOY amounts should be populated",
                    actual="EOY total assets = 0 or missing",
                    context="Incomplete balance sheet — entity likely still active if it has BOY",
                )

        # CMP-005
        if code in h_entities:
            h_row = sch_h_idx.loc[code]
            fx = safe_float(h_row, "IRS5471ScheduleH_ExchangeRt")
            if fx is None or fx == 0:
                ctx.add(
                    check_id="CMP-005", severity="MEDIUM", category="completeness",
                    entity_code=code, entity_name=name,
                    description="No exchange rate on Sch H (cannot convert FC to USD)",
                    context="Exchange rate is required for FC-to-USD translation of E&P",
                )

        # CMP-006
        if not code or len(code.strip()) < 3:
            ctx.add(
                check_id="CMP-006", severity="HIGH", category="completeness",
                entity_code=code, entity_name=name,
                description="Invalid or missing reference ID",
            )

        # CMP-007: Sch H present but no Sch J (E&P pool tracking missing)
        if code in h_entities and code not in j_entities:
            ctx.add(
                check_id="CMP-007", severity="MEDIUM", category="completeness",
                entity_code=code, entity_name=name,
                description="Entity has Sch H (E&P) but no Sch J (accumulated E&P pools)",
                context="Sch J tracks previously taxed and untaxed E&P pools — required for PTEP/distribution ordering",
            )

        # CMP-008: Tested income entity without QBAI
        if code in i1_entities and not sch_i1.empty:
            i1 = sch_i1_idx.loc[code] if code in sch_i1_idx.index else None
            if i1 is not None:
                tested = safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
                qbai = safe_float(i1, "IRS5471ScheduleI1_QBAIAmt")
                if tested is not None and tested > 0 and (qbai is None or qbai == 0):
                    ctx.add(
                        check_id="CMP-008", severity="MEDIUM", category="completeness",
                        entity_code=code, entity_name=name,
                        description=f"Tested income (${tested:,.0f}) but QBAI is zero/missing",
                        context="Tested income entities generally have tangible assets (QBAI) unless pure services/IP",
                    )

        # CMP-009: Income on Sch H but no Sch C (income statement)
        if code in h_entities and code not in c_entities:
            if not sch_h.empty:
                h_row = sch_h_idx.loc[code] if code in sch_h_idx.index else None
                if h_row is not None:
                    net_inc = safe_float(h_row, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
                    if net_inc is not None and net_inc > 100000:
                        ctx.add(
                            check_id="CMP-009", severity="LOW", category="completeness",
                            entity_code=code, entity_name=name,
                            description=f"Net income ${net_inc:,.0f} on Sch H but no Sch C (income statement)",
                            context="Sch C details revenue/COGS — omission may be acceptable for holding companies",
                        )

    return ctx.findings

"""Completeness checks for Form 8858 (CMP-8858-001 to CMP-8858-005)."""

from __future__ import annotations

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_completeness_checks_8858(ctx: CheckContext) -> list[Finding]:
    """Run completeness checks on Form 8858 FDE/FB entities."""
    parser = ctx.parser

    main = parser.extract_form_8858("IRS8858")
    sch_c = parser.extract_form_8858("IRS8858ScheduleC")
    sch_f = parser.extract_form_8858("IRS8858ScheduleF")
    sch_h = parser.extract_form_8858("IRS8858ScheduleH")

    entities = set(main["_reference_id"].unique()) - {""} if not main.empty else set()
    c_entities = set(sch_c["_reference_id"].unique()) - {""} if not sch_c.empty else set()
    f_entities = set(sch_f["_reference_id"].unique()) - {""} if not sch_f.empty else set()
    h_entities = set(sch_h["_reference_id"].unique()) - {""} if not sch_h.empty else set()

    dormant_entities = set()
    if not main.empty:
        dormant_entities = set(
            main.loc[main["_dormant"] == True, "_reference_id"].unique()
        ) - {""}

    if not sch_h.empty:
        sch_h_idx = sch_h.set_index("_reference_id")

    if not main.empty:
        main_idx = main.set_index("_reference_id")

    for code in entities:
        if code in dormant_entities:
            continue

        name = _entity_name_8858(main, code)

        # CMP-8858-001: No Schedule C (income statement)
        if code not in c_entities:
            ctx.add(
                check_id="CMP-8858-001", severity="MEDIUM", category="completeness",
                entity_code=code, entity_name=name,
                description="FDE in return but no Schedule C (income statement missing)",
                context="Schedule C provides revenue/expense detail for the FDE",
            )

        # CMP-8858-002: No Schedule H (E&P)
        if code not in h_entities:
            ctx.add(
                check_id="CMP-8858-002", severity="HIGH", category="completeness",
                entity_code=code, entity_name=name,
                description="FDE in return but no Schedule H (E&P computation missing)",
                context="E&P is required for GILTI/Subpart F allocation from the tax owner CFC",
            )

        # CMP-8858-003: No Schedule F (balance sheet)
        if code not in f_entities:
            ctx.add(
                check_id="CMP-8858-003", severity="MEDIUM", category="completeness",
                entity_code=code, entity_name=name,
                description="FDE in return but no Schedule F (balance sheet missing)",
                context="Balance sheet needed for asset/liability tracking",
            )

        # CMP-8858-004: No functional currency
        if code in main_idx.index:
            row = main_idx.loc[code]
            currency = row.get("IRS8858_FunctionalCurrencyCd", "") if hasattr(row, "get") else ""
            if not currency or currency == "":
                fc = row["_functional_currency"] if "_functional_currency" in row.index else ""
                if not fc:
                    ctx.add(
                        check_id="CMP-8858-004", severity="MEDIUM", category="completeness",
                        entity_code=code, entity_name=name,
                        description="Non-dormant FDE without functional currency specified",
                        context="Functional currency is required for E&P translation",
                    )

        # CMP-8858-005: No exchange rate on Sch H for non-USD entity
        if code in h_entities:
            h_row = sch_h_idx.loc[code]
            fc = h_row.get("_functional_currency", "USD") if hasattr(h_row, "get") else "USD"
            if fc and fc != "USD":
                fx = safe_float(h_row, "IRS8858ScheduleH_ExchangeRt")
                if fx is None or fx == 0:
                    ctx.add(
                        check_id="CMP-8858-005", severity="MEDIUM", category="completeness",
                        entity_code=code, entity_name=name,
                        description=f"Non-USD entity ({fc}) missing exchange rate on Sch H",
                        context="Exchange rate is required for FC-to-USD E&P translation",
                    )

    return ctx.findings


def _entity_name_8858(main_df, code: str) -> str:
    """Resolve entity name from 8858 main form DataFrame."""
    if main_df.empty:
        return code
    match = main_df[main_df["_reference_id"] == code]
    if match.empty:
        return code
    return match.iloc[0].get("_entity_name", code)

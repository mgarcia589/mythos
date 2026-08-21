"""Rollover checks for Form 8858 (ROL-8858-001 to ROL-8858-003): PY-to-CY continuity."""

from __future__ import annotations

import pandas as pd

from lab.xml_parser.core.models import Finding
from lab.xml_parser.engine.checks._helpers import CheckContext, safe_float


def run_rollover_checks_8858(ctx: CheckContext, py_parser) -> list[Finding]:
    """Run rollover checks comparing PY vs CY Form 8858 data."""
    cy_parser = ctx.parser

    cy_main = cy_parser.extract_form_8858("IRS8858")
    py_main = py_parser.extract_form_8858("IRS8858")

    cy_entities = set(cy_main["_reference_id"].unique()) - {""} if not cy_main.empty else set()
    py_entities = set(py_main["_reference_id"].unique()) - {""} if not py_main.empty else set()

    # ROL-8858-001: Entity in PY but dropped from CY
    for code in py_entities - cy_entities:
        name = _entity_name(py_main, code)
        ctx.add(
            check_id="ROL-8858-001", severity="MEDIUM", category="rollover",
            entity_code=code, entity_name=name,
            description="FDE present in PY but absent from CY return",
            context="Dropped FDE may indicate dissolution, sale, or conversion — verify intentional",
        )

    # ROL-8858-002: New entity in CY not in PY
    for code in cy_entities - py_entities:
        name = _entity_name(cy_main, code)
        ctx.add(
            check_id="ROL-8858-002", severity="LOW", category="rollover",
            entity_code=code, entity_name=name,
            description="New FDE in CY not present in PY return",
            context="New FDE — verify formation/acquisition date and that BOY balances are zero or correct",
        )

    # ROL-8858-003: Sch F EOY(PY) ≠ BOY(CY) — balance sheet discontinuity
    cy_f = cy_parser.extract_form_8858("IRS8858ScheduleF")
    py_f = py_parser.extract_form_8858("IRS8858ScheduleF")

    if not cy_f.empty and not py_f.empty:
        cy_f_idx = cy_f.set_index("_reference_id")
        py_f_idx = py_f.set_index("_reference_id")
        common = (set(cy_f_idx.index.unique()) & set(py_f_idx.index.unique())) - {""}

        prefix = "IRS8858ScheduleF_"
        fields = [
            ("TotalAssetsBalanceSheet", "Total assets"),
            ("LiabilitiesBalanceSheet", "Liabilities"),
            ("OwnerEquityBalanceSheet", "Owner equity"),
        ]

        for code in common:
            cy_row = cy_f_idx.loc[code]
            py_row = py_f_idx.loc[code]
            if isinstance(cy_row, pd.DataFrame):
                cy_row = cy_row.iloc[0]
            if isinstance(py_row, pd.DataFrame):
                py_row = py_row.iloc[0]
            name = cy_row.get("_entity_name", code)

            for field_base, label in fields:
                py_eoy = safe_float(py_row, f"{prefix}{field_base}_EndingAmt")
                cy_boy = safe_float(cy_row, f"{prefix}{field_base}_BeginningAmt")

                if py_eoy is None or cy_boy is None:
                    continue

                diff = abs(py_eoy - cy_boy)
                tolerance = max(100, abs(py_eoy) * 0.001)
                if diff > tolerance:
                    ctx.add(
                        check_id="ROL-8858-003", severity="HIGH", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"Sch F {label}: PY EOY ({py_eoy:,.0f}) ≠ CY BOY ({cy_boy:,.0f})",
                        expected=f"{py_eoy:,.0f}", actual=f"{cy_boy:,.0f}",
                        delta=cy_boy - py_eoy,
                        context="Balance sheet should roll forward: PY ending = CY beginning",
                    )

    return ctx.findings


def _entity_name(df, code: str) -> str:
    if df.empty:
        return code
    match = df[df["_reference_id"] == code]
    if match.empty:
        return code
    return match.iloc[0].get("_entity_name", code)

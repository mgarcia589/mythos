"""Reports for Form 8858 FDE/FB entities."""

from __future__ import annotations

from lab.xml_parser.core.models import RolloverItem, RolloverReport
from lab.xml_parser.engine.checks._helpers import safe_float
from lab.xml_parser.models import ParsedReturn
from lab.xml_parser.parser import EFileParser
from lab.xml_parser.field_maps import SCHEDULE_8858_F_ROLLOVER_PAIRS


def sch_f_8858_rollover(py: EFileParser, cy: EFileParser) -> RolloverReport:
    """Balance sheet rollover: PY EOY vs CY BOY for 8858 entities."""
    py_f = py.extract_form_8858("IRS8858ScheduleF")
    cy_f = cy.extract_form_8858("IRS8858ScheduleF")

    items = []
    if py_f.empty or cy_f.empty:
        return RolloverReport(
            title="8858 Sch F Rollover — Balance Sheet (PY EOY vs CY BOY)",
            items=items,
        )

    py_idx = py_f.set_index("_reference_id")
    cy_idx = cy_f.set_index("_reference_id")
    common = sorted(set(py_idx.index) & set(cy_idx.index) - {""})

    prefix = "IRS8858ScheduleF_"

    for code in common:
        py_row = py_idx.loc[code]
        cy_row = cy_idx.loc[code]
        name = cy_row.get("_entity_name", code)

        for eoy_field, boy_field, label in SCHEDULE_8858_F_ROLLOVER_PAIRS:
            py_val = safe_float(py_row, f"{prefix}{eoy_field}")
            cy_val = safe_float(cy_row, f"{prefix}{boy_field}")

            if py_val is None and cy_val is None:
                continue

            py_str = f"{py_val:,.0f}" if py_val is not None else "—"
            cy_str = f"{cy_val:,.0f}" if cy_val is not None else "—"
            diff = (cy_val or 0) - (py_val or 0)
            passes = abs(diff) < max(100, abs(py_val or 0) * 0.001)

            items.append(RolloverItem(
                entity_name=name,
                reference_id=code,
                field_description=label,
                py_value=py_str,
                cy_value=cy_str,
                difference=diff,
                passes=passes,
                line=eoy_field.split("_")[0][:6],
            ))

    return RolloverReport(
        title="8858 Sch F Rollover — Balance Sheet (PY EOY vs CY BOY)",
        items=items,
    )


def ep_summary_8858(py: EFileParser, cy: EFileParser) -> RolloverReport:
    """E&P summary from Schedule H: net income, adjustments, current E&P, FX."""
    cy_h = cy.extract_form_8858("IRS8858ScheduleH")

    items = []
    if cy_h.empty:
        return RolloverReport(title="8858 E&P Summary (Sch H)", items=items)

    prefix = "IRS8858ScheduleH_"
    fields = [
        ("ForeignCYNetIncomePerBooksAmt", "Net income per books (FC)"),
        ("TotalNetAdditionsAmt", "Net additions"),
        ("TotalNetSubtractionsAmt", "Net subtractions"),
        ("CurrentEarningsAndProfitsAmt", "Current E&P (FC)"),
        ("EarningAndPrftPlusDASTMGainAmt", "E&P + DASTM gain"),
        ("CurrEarnAndPrftInUSDollarsAmt", "Current E&P (USD)"),
        ("ExchangeRt", "Exchange rate"),
    ]

    for _, row in cy_h.iterrows():
        code = row.get("_reference_id", "")
        if not code:
            continue
        name = row.get("_entity_name", code)

        for field, label in fields:
            val = safe_float(row, f"{prefix}{field}")
            if val is None:
                continue

            if field == "ExchangeRt":
                val_str = f"{val:.6f}"
            else:
                val_str = f"{val:,.0f}"

            items.append(RolloverItem(
                entity_name=name,
                reference_id=code,
                field_description=label,
                py_value="—",
                cy_value=val_str,
                difference=0.0,
                passes=True,
                line=field[:8],
            ))

    return RolloverReport(title="8858 E&P Summary (Sch H)", items=items)


def income_statement_8858(py: EFileParser, cy: EFileParser) -> RolloverReport:
    """Income statement summary from Schedule C."""
    cy_c = cy.extract_form_8858("IRS8858ScheduleC")

    items = []
    if cy_c.empty:
        return RolloverReport(title="8858 Income Statement (Sch C)", items=items)

    prefix = "IRS8858ScheduleC_"
    fields = [
        ("GrossReceiptsOrSalesIncmStmt_USDollarAmt", "Revenue"),
        ("CostOfGoodsSoldIncmStmt_USDollarAmt", "COGS"),
        ("GrossProfitIncmStmt_USDollarAmt", "Gross profit"),
        ("TotalIncmStmt_USDollarAmt", "Total income"),
        ("TotalDeductionsIncmStmt_USDollarAmt", "Total deductions"),
        ("IncomeTaxExpenseIncmStmt_USDollarAmt", "Income tax expense"),
        ("NetIncomeLossPerBooksIncmStmt_USDollarAmt", "Net income (USD)"),
    ]

    for _, row in cy_c.iterrows():
        code = row.get("_reference_id", "")
        if not code:
            continue
        name = row.get("_entity_name", code)

        for field, label in fields:
            val = safe_float(row, f"{prefix}{field}")
            if val is None:
                continue

            items.append(RolloverItem(
                entity_name=name,
                reference_id=code,
                field_description=label,
                py_value="—",
                cy_value=f"{val:,.0f}",
                difference=0.0,
                passes=True,
                line=label[:6],
            ))

    return RolloverReport(title="8858 Income Statement (Sch C)", items=items)


def entity_changes_8858(py: EFileParser, cy: EFileParser) -> RolloverReport:
    """New and dropped FDE entities between PY and CY."""
    py_main = py.extract_form_8858("IRS8858")
    cy_main = cy.extract_form_8858("IRS8858")

    py_entities = set(py_main["_reference_id"].unique()) - {""} if not py_main.empty else set()
    cy_entities = set(cy_main["_reference_id"].unique()) - {""} if not cy_main.empty else set()

    items = []

    for code in sorted(cy_entities - py_entities):
        row = cy_main[cy_main["_reference_id"] == code].iloc[0]
        items.append(RolloverItem(
            entity_name=row.get("_entity_name", code),
            reference_id=code,
            field_description="NEW in CY",
            py_value="—",
            cy_value=row.get("_country_code", ""),
            difference=0.0,
            passes=True,
            line="new",
        ))

    for code in sorted(py_entities - cy_entities):
        row = py_main[py_main["_reference_id"] == code].iloc[0]
        items.append(RolloverItem(
            entity_name=row.get("_entity_name", code),
            reference_id=code,
            field_description="DROPPED from CY",
            py_value=row.get("_country_code", ""),
            cy_value="—",
            difference=0.0,
            passes=False,
            line="drop",
        ))

    return RolloverReport(title="8858 Entity Changes (New/Dropped FDEs)", items=items)


def tax_owner_map_8858(py: EFileParser, cy: EFileParser) -> RolloverReport:
    """FDE → Tax Owner relationship map."""
    cy_main = cy.extract_form_8858("IRS8858")

    items = []
    if cy_main.empty:
        return RolloverReport(title="8858 Tax Owner Map", items=items)

    for _, row in cy_main.iterrows():
        code = row.get("_reference_id", "")
        if not code:
            continue

        name = row.get("_entity_name", code)
        owner = row.get("_tax_owner", "")
        owner_ref = row.get("_tax_owner_ref_id", "")
        country = row.get("_country_code", "")
        currency = row.get("_functional_currency", "")
        dormant = row.get("_dormant", False)

        items.append(RolloverItem(
            entity_name=name,
            reference_id=code,
            field_description=f"Owner: {owner[:30]}" + (f" ({owner_ref})" if owner_ref else ""),
            py_value=f"{country}/{currency}",
            cy_value="Dormant" if dormant else "Active",
            difference=0.0,
            passes=not dormant,
            line="map",
        ))

    return RolloverReport(title="8858 Tax Owner Map", items=items)

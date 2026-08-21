"""E&P calculation validator — replicates Schedule H logic and compares."""

from dataclasses import dataclass

import pandas as pd

from lab.core.entity_registry import EntityRegistry
from lab.core.fx_rates import FXRateManager
from lab.core.xlsx_reader import XlsxReader


@dataclass
class EPResult:
    entity_code: str
    net_income_fc: float
    total_additions: float
    total_subtractions: float
    current_ep_fc: float
    current_ep_usd: float
    workbook_ep_fc: float
    workbook_ep_usd: float
    variance_fc: float
    variance_usd: float
    passes: bool


def validate_ep(
    reader: XlsxReader,
    registry: EntityRegistry,
    fx_manager: FXRateManager,
) -> list[EPResult]:
    """Validate E&P computation by replicating Sch H logic.

    Logic: Current E&P (FC) = Net Income + Total Additions + Total Subtractions
           Current E&P (USD) = E&P (FC) / Avg FX Rate

    Additions = sum of positive adjustments (lines 2a-2i)
    Subtractions = sum of negative adjustments (lines 2a-2i)
    """
    sch_h_data, _ = reader.read_sheet("5471 Sch H - FC")
    entities = reader.get_entity_columns("5471 Sch H - FC", code_row=4, name_row=5)

    results = []
    for ecol in entities:
        code = ecol["code"]
        col = ecol["col"]
        entity = registry.get(code)
        if not entity:
            continue

        get = lambda row: reader.get_numeric(sch_h_data, row, col)

        net_income = get(11)

        # Sum adjustments (rows 13-22)
        adjustments = [get(r) for r in range(13, 23)]
        total_add = sum(a for a in adjustments if a > 0)
        total_sub = sum(a for a in adjustments if a < 0)

        # Computed E&P
        computed_ep_fc = net_income + total_add + total_sub
        computed_ep_usd = fx_manager.fc_to_usd(computed_ep_fc, entity.fc)

        # Workbook cached values (Row 34 = CY E&P FC, Row 36 = CY E&P USD)
        wb_ep_fc = get(34)
        wb_ep_usd = get(36)

        variance_fc = abs(computed_ep_fc - wb_ep_fc) if wb_ep_fc != 0 else 0
        variance_usd = abs(computed_ep_usd - wb_ep_usd) if wb_ep_usd != 0 else 0

        results.append(EPResult(
            entity_code=code,
            net_income_fc=net_income,
            total_additions=total_add,
            total_subtractions=total_sub,
            current_ep_fc=computed_ep_fc,
            current_ep_usd=computed_ep_usd,
            workbook_ep_fc=wb_ep_fc,
            workbook_ep_usd=wb_ep_usd,
            variance_fc=variance_fc,
            variance_usd=variance_usd,
            passes=variance_fc < 1.0,  # $1 tolerance for rounding
        ))

    return results


def validate_ep_vs_oit(
    wb_results: list[EPResult],
    oit_tb: pd.DataFrame,
    registry: EntityRegistry,
) -> pd.DataFrame:
    """Cross-validate workbook E&P against OIT Working Trial Balance.

    OIT sign convention: negative = income. We flip and compare.
    """
    records = []
    for r in wb_results:
        entity = registry.get(r.entity_code)
        if not entity:
            continue

        # Get OIT income statement total for this entity
        mask = (
            (oit_tb["Company Number"] == r.entity_code)
            & (oit_tb["Binder Year"] == 2025)
            & (oit_tb["Account Number"].str.match(r"^(3[0-9]|4[0-1])-"))
        )
        oit_net = oit_tb.loc[mask, "Adjusted Tax Balance USD"].sum()
        oit_net_flipped = -oit_net  # flip sign convention

        records.append({
            "entity_code": r.entity_code,
            "entity_name": entity.name[:30],
            "workbook_ep_usd": r.current_ep_usd,
            "oit_net_income_usd": oit_net_flipped,
            "variance": abs(r.current_ep_usd - oit_net_flipped),
            "match": abs(r.current_ep_usd - oit_net_flipped) < 100,
        })

    return pd.DataFrame(records)

"""Formula pattern validation — detects inconsistencies across entity columns."""

import re
from dataclasses import dataclass

from lab.core.xlsx_reader import XlsxReader


@dataclass
class FormulaIssue:
    sheet: str
    row: int
    col: str
    entity_code: str
    severity: str  # CRITICAL, MODERATE, LOW
    issue_type: str
    description: str
    expected: str = ""
    actual: str = ""


def check_xlookup_row_refs(
    formulas: dict[int, dict[str, str]],
    rows: list[int],
    sheet_name: str,
    entity_cols: list[dict],
) -> list[FormulaIssue]:
    """Detect off-by-row XLOOKUP references (like the insurance FX bug)."""
    issues = []
    for row in rows:
        if row not in formulas:
            continue
        for ecol in entity_cols:
            col = ecol["col"]
            if col not in formulas.get(row, {}):
                continue
            formula = formulas[row][col]
            # Check if XLOOKUP references $B{wrong_row}
            ref_match = re.search(r'\$B(\d+)', formula)
            if ref_match:
                ref_row = int(ref_match.group(1))
                if ref_row != row:
                    issues.append(FormulaIssue(
                        sheet=sheet_name,
                        row=row,
                        col=col,
                        entity_code=ecol["code"],
                        severity="CRITICAL",
                        issue_type="XLOOKUP_OFF_BY_ROW",
                        description=f"XLOOKUP references $B{ref_row} but should reference $B{row}",
                        expected=f"$B{row}",
                        actual=f"$B{ref_row}",
                    ))
    return issues


def check_fx_direction(
    formulas: dict[int, dict[str, str]],
    rows: list[int],
    cols: list[str],
    sheet_name: str,
    expected_op: str = "/",
) -> list[FormulaIssue]:
    """Detect FX conversion direction inconsistency (multiply vs divide)."""
    issues = []
    for row in rows:
        if row not in formulas:
            continue
        for col in cols:
            if col not in formulas.get(row, {}):
                continue
            formula = formulas[row][col]
            # Check for multiplication where division expected (or vice versa)
            has_multiply = re.search(r'\*.*\$\d+', formula) or re.search(r'\$\d+.*\*', formula)
            has_divide = '/' in formula
            if expected_op == "/" and has_multiply and not has_divide:
                issues.append(FormulaIssue(
                    sheet=sheet_name,
                    row=row,
                    col=col,
                    entity_code="",
                    severity="CRITICAL",
                    issue_type="FX_DIRECTION_INVERTED",
                    description=f"Formula multiplies by FX rate instead of dividing",
                    expected=f"value / FX_rate",
                    actual=formula[:60],
                ))
    return issues


def check_entity_lookup_exists(
    formulas: dict[int, dict[str, str]],
    rows: list[int],
    entity_cols: list[dict],
    sheet_name: str,
    lookup_sheet: str = "Entity Listing",
) -> list[FormulaIssue]:
    """Detect #N/A risk from pseudo-entities not in lookup source."""
    issues = []
    pseudo_entities = ["C0063 Consol", "C0022 Consol"]
    for ecol in entity_cols:
        if ecol["code"] in pseudo_entities or "Consol" in ecol.get("name", ""):
            issues.append(FormulaIssue(
                sheet=sheet_name,
                row=0,
                col=ecol["col"],
                entity_code=ecol["code"],
                severity="CRITICAL",
                issue_type="PSEUDO_ENTITY_LOOKUP",
                description=f"'{ecol['code']}' is a consolidation entity not in {lookup_sheet} — lookups will #N/A",
            ))
    return issues


def check_sign_consistency(
    rows_data: dict[int, dict[str, str]],
    row: int,
    entity_cols: list[dict],
    sheet_name: str,
    expected_sign: str = "negative",
) -> list[FormulaIssue]:
    """Detect sign convention errors (e.g., negative BIE when entity has net interest income)."""
    issues = []
    for ecol in entity_cols:
        col = ecol["col"]
        val = rows_data.get(row, {}).get(col, "0")
        try:
            num = float(val)
        except (ValueError, TypeError):
            continue
        if expected_sign == "negative" and num > 0:
            issues.append(FormulaIssue(
                sheet=sheet_name,
                row=row,
                col=col,
                entity_code=ecol["code"],
                severity="CRITICAL",
                issue_type="SIGN_CONVENTION_ERROR",
                description=f"Expected negative value (expense) but got {num:,.0f}",
            ))
        elif expected_sign == "positive" and num < 0:
            issues.append(FormulaIssue(
                sheet=sheet_name,
                row=row,
                col=col,
                entity_code=ecol["code"],
                severity="CRITICAL",
                issue_type="SIGN_CONVENTION_ERROR",
                description=f"Expected positive value but got {num:,.0f}",
            ))
    return issues


def check_negative_assets(
    rows_data: dict[int, dict[str, str]],
    asset_row: int,
    entity_cols: list[dict],
    sheet_name: str,
) -> list[FormulaIssue]:
    """Detect negative average asset values (filing risk on Schedule Q)."""
    issues = []
    for ecol in entity_cols:
        col = ecol["col"]
        val = rows_data.get(asset_row, {}).get(col, "0")
        try:
            num = float(val)
        except (ValueError, TypeError):
            continue
        if num < 0:
            issues.append(FormulaIssue(
                sheet=sheet_name,
                row=asset_row,
                col=col,
                entity_code=ecol["code"],
                severity="CRITICAL",
                issue_type="NEGATIVE_ASSET_VALUE",
                description=f"Negative average asset value ({num:,.0f}) — filing risk on Schedule Q",
            ))
    return issues

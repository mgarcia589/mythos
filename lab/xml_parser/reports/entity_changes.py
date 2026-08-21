"""Entity change reports — structural changes between PY and CY.

Generates RolloverReport objects for:
- New/Final entities (added or removed)
- Schedule G indicator flips (Yes/No changes)
"""

from __future__ import annotations

from lab.xml_parser.core.models import RolloverItem, RolloverReport
from lab.xml_parser.models import ParsedReturn, SubsidiaryReturn
from lab.xml_parser.reports.rollover import _match_entities, _get_field


# ─────────────────────────────────────────────────────────────────
# New & Final Entities
# ─────────────────────────────────────────────────────────────────

def new_final_entities(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Identify entities added or removed between PY and CY."""
    report = RolloverReport(title="Entity Changes — New & Final Returns")

    py_refs = {s.entity.reference_id or s.entity.name: s for s in py.subsidiaries}
    cy_refs = {s.entity.reference_id or s.entity.name: s for s in cy.subsidiaries}

    for key, cy_sub in cy_refs.items():
        if key not in py_refs:
            report.items.append(RolloverItem(
                entity_name=cy_sub.entity.name,
                reference_id=cy_sub.entity.reference_id,
                field_description="NEW ENTITY (not in prior year)",
                line="—",
                py_value="",
                cy_value=f"{cy_sub.entity.country_code} | {cy_sub.entity.functional_currency}",
                passes=False,
            ))

    for key, py_sub in py_refs.items():
        if key not in cy_refs:
            report.items.append(RolloverItem(
                entity_name=py_sub.entity.name,
                reference_id=py_sub.entity.reference_id,
                field_description="REMOVED (final return or liquidated)",
                line="—",
                py_value=f"{py_sub.entity.country_code} | {py_sub.entity.functional_currency}",
                cy_value="",
                passes=False,
            ))

    return report


# ─────────────────────────────────────────────────────────────────
# Schedule G — Indicator Changes
# ─────────────────────────────────────────────────────────────────

_INDICATOR_FIELDS = [
    ("DisallowedInterestExpenseInd", "163(j) disallowed interest?", "15a"),
    ("BaseErosionPaymentBenefitInd", "Base erosion payments?", "6"),
    ("FDIIBenefitsClaimInd", "FDII benefits claimed?", "8"),
    ("PayOrAccrueTopUpTaxInd", "Top-up tax (Pillar Two)?", "new"),
    ("ExpatriatedFrgnSubsidiaryInd", "Expatriated subsidiary?", "4"),
    ("ForeignTaxSection909Ind", "Section 909 splitter?", "7"),
    ("ReportableTransactionPrtcptInd", "Reportable transaction?", "11"),
]


def schedule_g_changes(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Flag any Yes/No indicators that changed PY→CY."""
    report = RolloverReport(title="Schedule G — Indicator Changes")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _INDICATOR_FIELDS:
            py_val = _get_field(py_sub, "IRS5471", f"IRS5471ScheduleG_{field_name}")
            cy_val = _get_field(cy_sub, "IRS5471", f"IRS5471ScheduleG_{field_name}")

            if py_val == cy_val:
                continue
            if not py_val and not cy_val:
                continue

            report.items.append(RolloverItem(
                entity_name=py_sub.entity.name,
                reference_id=py_sub.entity.reference_id,
                field_description=description,
                line=line,
                py_value=py_val or "—",
                cy_value=cy_val or "—",
                passes=False,
            ))

    return report

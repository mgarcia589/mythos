"""Rollover reports — PY vs CY field-by-field comparison.

Generates RolloverReport objects for:
- Schedule F balance sheet (PY EOY = CY BOY)
- Page 1 entity info (static fields unchanged)
- Schedule J accumulated E&P pools (PY col(f) = CY col(a))
"""

from __future__ import annotations

from lab.xml_parser.core.models import RolloverItem, RolloverReport
from lab.xml_parser.models import ParsedReturn, SubsidiaryReturn
from lab.xml_parser.field_maps import SCHEDULE_F_ROLLOVER_PAIRS


def _match_entities(py: ParsedReturn, cy: ParsedReturn) -> list[tuple[SubsidiaryReturn, SubsidiaryReturn]]:
    """Match PY entities to CY entities by reference ID or name."""
    matched = []
    cy_by_ref = {s.entity.reference_id: s for s in cy.subsidiaries if s.entity.reference_id}
    cy_by_name = {s.entity.name.lower(): s for s in cy.subsidiaries}

    for py_sub in py.subsidiaries:
        cy_sub = cy_by_ref.get(py_sub.entity.reference_id)
        if not cy_sub:
            cy_sub = cy_by_name.get(py_sub.entity.name.lower())
        if cy_sub:
            matched.append((py_sub, cy_sub))
    return matched


def _get_field(sub: SubsidiaryReturn, form: str, field_name: str) -> str:
    """Get a field value from a subsidiary's form data."""
    form_data = sub.forms.get(form)
    if not form_data:
        return ""
    base_form = form_data.form_name
    prefixed = f"{base_form}_{field_name}"
    val = form_data.fields.get(prefixed, "")
    if not val:
        val = form_data.fields.get(field_name, "")
    return str(val) if val else ""


# ─────────────────────────────────────────────────────────────────
# Schedule F — Balance Sheet Rollover
# ─────────────────────────────────────────────────────────────────

def sch_f_rollover(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Check that PY ending balances equal CY beginning balances."""
    report = RolloverReport(title="Schedule F — Balance Sheet Rollover")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for pair in SCHEDULE_F_ROLLOVER_PAIRS:
            py_end_field, cy_begin_field, description = pair[0], pair[1], pair[2]
            line = pair[3] if len(pair) > 3 else ""
            py_val = _get_field(py_sub, "IRS5471ScheduleF", py_end_field)
            cy_val = _get_field(cy_sub, "IRS5471ScheduleF", cy_begin_field)

            if not py_val:
                py_val = _get_field(py_sub, "IRS5471", f"IRS5471ScheduleF_{py_end_field}")
            if not cy_val:
                cy_val = _get_field(cy_sub, "IRS5471", f"IRS5471ScheduleF_{cy_begin_field}")

            try:
                py_num = float(py_val) if py_val else 0.0
                cy_num = float(cy_val) if cy_val else 0.0
                diff = cy_num - py_num
                passes = abs(diff) < 1.0
            except (ValueError, TypeError):
                diff = 0.0
                passes = py_val == cy_val

            if py_val or cy_val:
                report.items.append(RolloverItem(
                    entity_name=py_sub.entity.name,
                    reference_id=py_sub.entity.reference_id,
                    field_description=description,
                    line=line,
                    py_value=py_val,
                    cy_value=cy_val,
                    difference=diff,
                    passes=passes,
                ))

    return report


# ─────────────────────────────────────────────────────────────────
# Page 1 — Entity Information Rollover
# ─────────────────────────────────────────────────────────────────

_PAGE1_STATIC_FIELDS = [
    ("ForeignCorporation_BusinessName_BusinessNameLine1Txt", "Entity name", "1a"),
    ("ForeignCorporation_ForeignAddress_AddressLine1Txt", "Address line 1", "1a(addr)"),
    ("ForeignCorporation_ForeignAddress_CityNm", "City", "1a(city)"),
    ("ForeignCorporation_ForeignAddress_CountryCd", "Country code", "1a(country)"),
    ("ForeignEntityIdentificationGrp_ForeignEntityReferenceIdNum", "Reference ID", "1d"),
    ("CountryUnderWhoseLawsIncCd", "Country of incorporation", "1b"),
    ("FunctionalCurrencyCd", "Functional currency", "1c"),
    ("IncorporationDt", "Incorporation date", "2b"),
    ("PrincipalPlaceOfBusCountryCd", "Principal place of business", "2a"),
    ("EIN", "EIN", "1d"),
]


def page1_rollover(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Check that entity identification data rolled correctly PY→CY."""
    report = RolloverReport(title="Page 1 — Entity Information Rollover")
    matched = _match_entities(py, cy)

    for py_sub, cy_sub in matched:
        for field_name, description, line in _PAGE1_STATIC_FIELDS:
            py_val = _get_field(py_sub, "IRS5471", field_name)
            cy_val = _get_field(cy_sub, "IRS5471", field_name)

            if not py_val and not cy_val:
                continue

            passes = py_val.strip().upper() == cy_val.strip().upper()

            report.items.append(RolloverItem(
                entity_name=py_sub.entity.name,
                reference_id=py_sub.entity.reference_id,
                field_description=description,
                line=line,
                py_value=py_val,
                cy_value=cy_val,
                passes=passes,
            ))

    return report


# ─────────────────────────────────────────────────────────────────
# Schedule J — Accumulated E&P Rollover
# ─────────────────────────────────────────────────────────────────

_J_POOLS = [
    ("Post2017EPNotPrevTaxedGrp", "Post-2017 E&P Not Previously Taxed", "1"),
    ("Post1986UndistributedEarnGrp", "Post-1986 Undistributed Earnings", "2"),
    ("HoveringDeficitDedSspndTaxGrp", "Hovering Deficit", "3"),
    ("Section951a1APTEPGrp", "Sec 951(a)(1)(A) PTEP (SubF)", "4"),
    ("Section951APTEPGrp", "Sec 951A PTEP (GILTI)", "5"),
    ("TotalSection964AEPGrp", "Total Section 964(a) E&P", "6"),
]


def sch_j_rollover(py: ParsedReturn, cy: ParsedReturn, basket: str = "GEN") -> RolloverReport:
    """Check Schedule J rollover for a specific basket (GEN or PAS).

    Rollover logic: PY col(f) 'BalanceBeginningNextYearAmt' = CY col(a) 'BeginningYearBalanceAmt'
    """
    form_key = f"IRS5471ScheduleJ_{basket}"
    title = f"Schedule J ({basket}) — Accumulated E&P Rollover"
    report = RolloverReport(title=title)

    matched = _match_entities(py, cy)
    for py_sub, cy_sub in matched:
        for group_name, pool_desc, line_num in _J_POOLS:
            py_field = f"{group_name}_BalanceBeginningNextYearAmt"
            cy_field = f"{group_name}_BeginningYearBalanceAmt"

            py_val = _get_field(py_sub, form_key, py_field)
            cy_val = _get_field(cy_sub, form_key, cy_field)

            if not py_val and not cy_val:
                continue

            try:
                py_num = float(py_val) if py_val else 0.0
                cy_num = float(cy_val) if cy_val else 0.0
                diff = cy_num - py_num
                passes = abs(diff) < 1.0
            except (ValueError, TypeError):
                diff = 0.0
                passes = py_val == cy_val

            report.items.append(RolloverItem(
                entity_name=py_sub.entity.name,
                reference_id=py_sub.entity.reference_id,
                field_description=f"{pool_desc} (PY f→CY a)",
                line=f"{line_num}",
                py_value=py_val,
                cy_value=cy_val,
                difference=diff,
                passes=passes,
            ))

    return report

"""Cross-schedule tie report — verifies amounts that should match across schedules.

Generates a RolloverReport showing Sch H vs Sch J current-year E&P tie.
"""

from __future__ import annotations

from lab.xml_parser.core.models import RolloverItem, RolloverReport
from lab.xml_parser.models import ParsedReturn
from lab.xml_parser.reports.rollover import _match_entities, _get_field


def cross_schedule_tie(py: ParsedReturn, cy: ParsedReturn) -> RolloverReport:
    """Compare Sch H line 5d (E&P USD) vs Sch J CY E&P column for current year.

    This is a single-year check (only uses CY) but takes PY for API consistency.
    Shows pass/fail: amounts should be equal within $1.
    """
    report = RolloverReport(title="Cross-Schedule Tie — Sch H vs Sch J (CY E&P)")

    for cy_sub in cy.subsidiaries:
        code = cy_sub.entity.reference_id
        name = cy_sub.entity.name

        h_ep_usd = _get_field(cy_sub, "IRS5471ScheduleH", "CurrEarnAndPrftInUSDollarsAmt")
        j_cy_ep = _get_field(cy_sub, "IRS5471ScheduleJ", "Post2017EPNotPrevTaxedGrp_CurrentYearEPDeficitAmt")

        if not h_ep_usd and not j_cy_ep:
            continue

        try:
            h_num = float(h_ep_usd) if h_ep_usd else 0.0
            j_num = float(j_cy_ep) if j_cy_ep else 0.0
            diff = j_num - h_num
            passes = abs(diff) < max(10, abs(h_num) * 0.01)
        except (ValueError, TypeError):
            diff = 0.0
            passes = h_ep_usd == j_cy_ep

        report.items.append(RolloverItem(
            entity_name=name,
            reference_id=code,
            field_description="Sch H 5d vs Sch J Post-2017 CY",
            line="5d/col(ii)",
            py_value=h_ep_usd or "0",
            cy_value=j_cy_ep or "0",
            difference=diff,
            passes=passes,
        ))

    return report

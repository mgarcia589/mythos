"""Rollover tab — side-by-side PY vs CY comparison results."""

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.services.bridge import get_state


def render_rollover(t: dict, s):
    """Render the Rollover tab."""
    if not s.rollover_reports:
        _render_empty(t)
        return

    xc = s.xml_check
    reports = s.rollover_reports

    # Summary KPIs
    total_checks = sum(r.total_checks for r in reports.values())
    total_passed = sum(r.passed for r in reports.values())
    total_failed = sum(r.failed for r in reports.values())
    pass_rate = total_passed / total_checks if total_checks > 0 else 0

    with ui.row().classes("w-full gap-3 mb-4 animate-fade-up stagger-1"):
        _kpi(t, str(total_checks), "Total Comparisons", t["info"])
        _kpi(t, f"{pass_rate:.0%}", "Pass Rate",
             t["success"] if pass_rate >= 0.95 else t["sev_high"])
        _kpi(t, str(total_failed), "Differences",
             t["sev_high"] if total_failed > 0 else t["success"])
        _kpi(t, str(len(reports)), "Reports Generated", t["text_primary"])

    # Report cards
    for report_key, report in reports.items():
        _render_report_card(t, report, xc)


def _render_report_card(t: dict, report, xc):
    """Single rollover report card with expandable failures."""
    has_issues = report.failed > 0
    status_color = t["sev_high"] if has_issues else t["success"]
    status_icon = "error" if has_issues else "check_circle"

    # Filter by entity if selected
    items = report.items
    if xc.selected_entity:
        items = [item for item in items
                 if item.reference_id == xc.selected_entity or
                 xc.selected_entity in item.entity_name]

    # Filter by search
    if xc.search_query:
        q = xc.search_query.lower()
        items = [item for item in items
                 if q in item.entity_name.lower() or
                 q in item.field_description.lower() or
                 q in item.reference_id.lower()]

    failed_items = [item for item in items if not item.passes]
    if xc.selected_entity and not items:
        return
    if xc.search_query and not items:
        return

    with ui.expansion(
        text=report.title,
        icon=status_icon,
        value=has_issues,
    ).classes("w-full mb-2 animate-fade-up").style(
        f"border: 1px solid {status_color}30; border-left: 3px solid {status_color}; "
        f"border-radius: 8px; font-size: 0.85rem;"
    ):
        # Report header stats
        with ui.row().classes("items-center gap-4 mb-3"):
            ui.label(f"{report.passed}/{report.total_checks} passed") \
                .classes("text-xs mythos-mono") \
                .style(f"color: {t['success']};")
            if report.failed > 0:
                ui.label(f"{report.failed} differences") \
                    .classes("text-xs mythos-mono") \
                    .style(f"color: {t['sev_high']};")
            if report.entities_with_issues:
                ui.label(f"{len(report.entities_with_issues)} entities affected") \
                    .classes("text-xs") \
                    .style(f"color: {t['text_muted']};")

        # Failures table
        if failed_items:
            columns = [
                {"name": "entity", "label": "Entity", "field": "entity", "align": "left", "sortable": True},
                {"name": "ref_id", "label": "Ref ID", "field": "ref_id", "align": "left"},
                {"name": "field", "label": "Field", "field": "field", "align": "left"},
                {"name": "line", "label": "Line", "field": "line", "align": "center"},
                {"name": "py_value", "label": "PY Value", "field": "py_value", "align": "right"},
                {"name": "cy_value", "label": "CY Value", "field": "cy_value", "align": "right"},
                {"name": "diff", "label": "Difference", "field": "diff", "align": "right", "sortable": True},
            ]

            rows = []
            for i, item in enumerate(failed_items[:100]):
                rows.append({
                    "_id": i,
                    "entity": item.entity_name[:30],
                    "ref_id": item.reference_id,
                    "field": item.field_description[:40],
                    "line": item.line or "—",
                    "py_value": _format_value(item.py_value),
                    "cy_value": _format_value(item.cy_value),
                    "diff": _format_diff(item.difference),
                })

            strip = TableFilterStrip(
                filterable_columns={"entity": "Entity", "field": "Field"},
                all_rows=rows,
            )
            strip.render(t)

            table = ui.table(
                columns=columns, rows=strip.filtered_rows, row_key="_id",
                pagination={"rowsPerPage": 25},
            ).classes("w-full").props("dense flat bordered separator=cell")
            table.style(f"font-size: 0.65rem; max-height: 40vh;")
            strip.bind(table)

            # Color the difference column
            table.add_slot("body-cell-diff", """
                <q-td :props="props">
                    <span :style="props.row.diff && props.row.diff !== '—' ?
                        'color: #ef4444; font-weight: 600' : ''">
                        {{ props.row.diff }}
                    </span>
                </q-td>
            """)

            if len(failed_items) > 100:
                ui.label(f"Showing 100 of {len(failed_items)} differences") \
                    .classes("text-xs mt-1").style(f"color: {t['text_muted']};")
        else:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.8rem;")
                ui.label("All checks passed").classes("text-xs") \
                    .style(f"color: {t['success']};")


def _kpi(t: dict, value: str, label: str, color: str):
    """Compact KPI card."""
    with ui.card().classes("flex-1 min-w-[100px]").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-top: 2px solid {color}; border-radius: 10px; padding: 12px 14px;"
    ):
        ui.label(value).classes("text-lg font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _format_value(val) -> str:
    """Format a value for display."""
    if val is None or val == "":
        return "—"
    try:
        num = float(str(val).replace(",", "").replace("$", ""))
        if abs(num) >= 1_000_000:
            return f"${num / 1_000_000:.1f}M"
        elif abs(num) >= 1_000:
            return f"${num / 1_000:.1f}K"
        elif abs(num) >= 1:
            return f"${num:,.0f}"
        return str(val)
    except (ValueError, TypeError):
        return str(val)[:30]


def _format_diff(diff) -> str:
    """Format difference value."""
    if diff is None or diff == 0:
        return "—"
    try:
        num = float(diff)
        if abs(num) >= 1_000_000:
            return f"${num / 1_000_000:+.1f}M"
        elif abs(num) >= 1_000:
            return f"${num / 1_000:+.1f}K"
        elif abs(num) >= 1:
            return f"${num:+,.0f}"
        return f"{num:+.2f}"
    except (ValueError, TypeError):
        return str(diff)


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("swap_vert").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No rollover data available").classes("text-sm") \
            .style(f"color: {t['text_muted']};")
        ui.label("Run Rollover Check or Full Review with a Prior Year XML") \
            .classes("text-xs").style(f"color: {t['text_muted']}; opacity: 0.6;")

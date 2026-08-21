"""Issues tab — findings with severity, type, expandable detail."""

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.services.bridge import get_state


# Severity display config
SEV_LABELS = {"HIGH": "CRITICAL", "MEDIUM": "REVIEW", "LOW": "INFO"}
SEV_ICONS = {"HIGH": "error", "MEDIUM": "warning", "LOW": "info"}


def render_issues(t: dict, s):
    """Render the Issues tab."""
    if not s.report:
        _render_empty(t)
        return

    findings = s.report.findings
    xc = s.xml_check

    # Apply filters
    filtered = _apply_filters(findings, xc)

    # Header + search + severity filters
    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("bug_report").style(f"color: {t['accent']}; font-size: 1rem;")
            ui.label(f"Issues ({len(filtered)})").classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary']};")
            if len(filtered) != len(findings):
                ui.label(f"of {len(findings)} total").classes("text-xs") \
                    .style(f"color: {t['text_muted']};")

            # Search (inline, functional)
            ui.input(
                placeholder="Search issues...",
                value=xc.search_query,
                on_change=lambda e: _update_search(e.value),
            ).classes("w-52").props("dense outlined clearable") \
                .style(f"font-size: 0.65rem;")

        # Severity filter buttons
        with ui.row().classes("items-center gap-2"):
            for sev, color in [("HIGH", t["sev_high"]), ("MEDIUM", t["accent"]), ("LOW", t["info"])]:
                count = sum(1 for f in findings if f.severity == sev)
                if count > 0:
                    is_active = xc.active_filters.get("severity") == sev
                    ui.button(
                        f"{SEV_LABELS[sev]} ({count})",
                        on_click=lambda _, sv=sev: _toggle_severity(sv),
                    ).props("flat dense no-caps size=xs").style(
                        f"color: {color}; font-size: 0.6rem; "
                        f"background: {color}15; border-radius: 10px; padding: 2px 8px; "
                        f"border: {'1.5px' if is_active else '1px'} solid {color}{'80' if is_active else '30'};"
                    )

    if not filtered:
        with ui.column().classes("w-full items-center py-8 gap-3"):
            ui.icon("check_circle").classes("text-3xl") \
                .style(f"color: {t['success']};")
            ui.label("No issues match current filters").classes("text-sm") \
                .style(f"color: {t['success']};")
        return

    # Issues table
    columns = [
        {"name": "severity", "label": "Sev", "field": "severity", "align": "center", "sortable": True},
        {"name": "check_id", "label": "Check", "field": "check_id", "align": "left", "sortable": True},
        {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True},
        {"name": "entity", "label": "Entity", "field": "entity", "align": "left", "sortable": True},
        {"name": "description", "label": "Description", "field": "description", "align": "left"},
        {"name": "delta", "label": "Delta", "field": "delta", "align": "right", "sortable": True},
    ]

    rows = []
    for i, f in enumerate(filtered[:200]):
        delta_str = ""
        if f.delta is not None:
            delta_str = f"${f.delta:,.0f}" if abs(f.delta) >= 1 else str(f.delta)

        rows.append({
            "_id": i,
            "severity": f.severity,
            "check_id": f.check_id,
            "category": f.category.replace("_", " ").title(),
            "entity": f"{f.entity_code} — {f.entity_name[:20]}",
            "description": f.description[:80] + ("..." if len(f.description) > 80 else ""),
            "delta": delta_str,
            "_full_desc": f.description,
            "_expected": f.expected or "",
            "_actual": f.actual or "",
            "_context": f.context or "",
            "_entity_name": f.entity_name,
        })

    # Column filter strip
    strip = TableFilterStrip(
        filterable_columns={
            "severity": "Severity",
            "category": "Category",
            "entity": "Entity",
        },
        all_rows=rows,
    )
    strip.render(t)

    with ui.card().classes("w-full animate-fade-up stagger-2").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 0; overflow: hidden;"
    ):
        table = ui.table(
            columns=columns, rows=strip.filtered_rows, row_key="_id",
            pagination={"rowsPerPage": 50},
        ).classes("w-full").props("dense flat bordered separator=cell virtual-scroll")
        table.style(f"background: {t['bg_card']}; max-height: 55vh; font-size: 0.7rem;")
        strip.bind(table)

        # Custom severity cell
        table.add_slot("body-cell-severity", """
            <q-td :props="props">
                <q-badge
                    :color="props.row.severity === 'HIGH' ? 'red' :
                            props.row.severity === 'MEDIUM' ? 'amber' : 'blue'"
                    :label="props.row.severity === 'HIGH' ? 'CRT' :
                            props.row.severity === 'MEDIUM' ? 'REV' : 'INF'"
                    dense />
            </q-td>
        """)

        # Custom delta cell
        table.add_slot("body-cell-delta", """
            <q-td :props="props">
                <span :style="props.row.delta && props.row.delta.includes('-') ?
                    'color: #ef4444' : props.row.delta ? 'color: #f59e0b' : ''">
                    {{ props.row.delta || '—' }}
                </span>
            </q-td>
        """)

    # Category distribution
    if len(filtered) > 5:
        _render_category_summary(t, filtered)


def _render_category_summary(t: dict, findings: list):
    """Show category breakdown below the table."""
    from collections import Counter
    cats = Counter(f.category for f in findings)

    with ui.card().classes("w-full mt-4 animate-fade-up stagger-3").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 14px 18px;"
    ):
        ui.label("By Category").classes("text-xs font-semibold mb-2") \
            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                   f"letter-spacing: 0.05em; font-size: 0.6rem;")

        max_val = max(cats.values()) if cats else 1
        for cat, count in cats.most_common(8):
            pct = count / max_val * 100
            with ui.row().classes("items-center gap-2 w-full mb-1"):
                ui.label(cat.replace("_", " ").title()).classes("text-xs w-28") \
                    .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")
                ui.element("div").style(
                    f"height: 5px; width: {max(pct, 3)}%; "
                    f"background: {t['accent']}; border-radius: 3px;")
                ui.label(str(count)).classes("text-xs mythos-mono w-6 text-right") \
                    .style(f"color: {t['text_muted']};")


def _apply_filters(findings: list, xc) -> list:
    """Apply active filters to findings."""
    filtered = findings

    sev_filter = xc.active_filters.get("severity")
    if sev_filter:
        filtered = [f for f in filtered if f.severity == sev_filter]

    cat_filter = xc.active_filters.get("category")
    if cat_filter:
        filtered = [f for f in filtered if f.category == cat_filter]

    if xc.selected_entity:
        filtered = [f for f in filtered if f.entity_code == xc.selected_entity]

    if xc.search_query:
        q = xc.search_query.lower()
        filtered = [f for f in filtered if
                    q in f.description.lower() or
                    q in f.entity_name.lower() or
                    q in f.check_id.lower() or
                    q in f.category.lower()]

    return filtered


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("bug_report").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No review has been run").classes("text-sm") \
            .style(f"color: {t['text_muted']};")
        ui.label("Run Full Review to generate findings").classes("text-xs") \
            .style(f"color: {t['text_muted']}; opacity: 0.6;")


def _toggle_severity(sev: str):
    s = get_state()
    current = s.xml_check.active_filters.get("severity")
    if current == sev:
        s.xml_check.active_filters.pop("severity", None)
    else:
        s.xml_check.active_filters["severity"] = sev
    ui.navigate.to("/review")


def _update_search(value: str):
    s = get_state()
    s.xml_check.search_query = value or ""
    ui.navigate.to("/review")

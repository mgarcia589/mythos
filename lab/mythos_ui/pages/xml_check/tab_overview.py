"""Overview tab — summary KPIs, file info, and schedule tree."""

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.xml_check_state import ParseSummary, ScheduleNode
from lab.mythos_ui.services.parse_service import get_display_name


def render_overview(t: dict, s):
    """Render the Overview tab content."""
    xc = s.xml_check
    ps = xc.parse_summary

    if not ps:
        _render_no_summary(t)
        return

    # File info card
    _render_file_info(t, ps, s)

    # KPI strip
    _render_kpis(t, ps, s)

    # Schedule tree
    _render_schedule_tree(t, ps)


def _render_no_summary(t: dict):
    """Placeholder when no parse summary available."""
    with ui.column().classes("w-full items-center py-8 gap-3"):
        ui.icon("analytics").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No parse summary available") \
            .classes("text-sm").style(f"color: {t['text_muted']};")


def _render_file_info(t: dict, ps: ParseSummary, s):
    """Client/file context card."""
    xc = s.xml_check

    with ui.card().classes("w-full glass-card animate-fade-up stagger-1").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px 20px;"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            # Left: client info
            with ui.row().classes("items-center gap-4"):
                ui.icon("business").style(f"color: {t['accent']}; font-size: 1.3rem;")
                with ui.column().classes("gap-0"):
                    ui.label(ps.client_name or "Unknown Client") \
                        .classes("text-base font-bold") \
                        .style(f"color: {t['text_primary']};")
                    info_parts = []
                    if ps.tax_year:
                        info_parts.append(f"FY{ps.tax_year}")
                    if ps.return_type:
                        info_parts.append(f"Form {ps.return_type}")
                    info_parts.append(f"{ps.entity_count} entities")
                    ui.label(" · ".join(info_parts)).classes("text-xs") \
                        .style(f"color: {t['text_secondary']};")

            # Right: form types + metadata
            with ui.row().classes("items-center gap-2"):
                for ft in sorted(ps.form_types):
                    ui.badge(f"Form {ft}", color="transparent").props("dense") \
                        .style(f"color: {t['info']}; border: 1px solid {t['info']}40; "
                               f"font-size: 0.55rem;")
                if ps.software_id:
                    ui.badge(ps.software_id, color="transparent").props("dense") \
                        .style(f"color: {t['text_muted']}; border: 1px solid {t['border']}; "
                               f"font-size: 0.55rem;")


def _render_kpis(t: dict, ps: ParseSummary, s):
    """Metrics bar — unified row with vertical dividers."""
    report = s.report
    border = t["border"]

    with ui.element("div").classes("w-full animate-fade-up stagger-2").style(
        f"background: {t['bg_card']}; border: 1px solid {border}40; "
        f"border-radius: 10px; padding: 0; display: flex; align-items: stretch; "
        f"overflow: hidden;"
    ):
        # Build metrics list
        metrics = [
            (str(ps.entity_count), "Entities", t["text_primary"]),
            (str(ps.total_forms), "Forms", t["text_primary"]),
            (str(ps.total_schedules), "Schedules", t["text_primary"]),
            (f"{ps.total_records:,}", "Records", t["text_primary"]),
            (f"{ps.populated_fields:,}", "Fields", t["success"]),
        ]

        if report:
            sev = report.summary.get("by_severity", {})
            high = sev.get("HIGH", 0)
            med = sev.get("MEDIUM", 0)
            low = sev.get("LOW", 0)
            total = report.summary.get("total_findings", 0)
            issue_color = t["sev_high"] if high > 0 else (
                t["sev_medium"] if med > 0 else t["success"]
            )
            metrics.append((str(total), "Issues", issue_color))
        else:
            metrics.append((str(ps.empty_fields), "Empty", t["text_muted"]))

        for i, (value, label, color) in enumerate(metrics):
            is_last = i == len(metrics) - 1
            with ui.element("div").style(
                f"flex: 1; padding: 14px 16px; "
                f"{'border-right: 1px solid ' + border + '20;' if not is_last else ''}"
            ):
                ui.label(label).classes("text-xs") \
                    .style(f"color: {t['text_muted']}; font-size: 0.6rem; "
                           f"text-transform: uppercase; letter-spacing: 0.04em;")
                ui.html(
                    f'<div style="font-size: 1.25rem; font-weight: 700; '
                    f'color: {color}; font-family: var(--mythos-mono); '
                    f'margin-top: 2px; line-height: 1;">{value}</div>'
                )

        # Severity breakdown inline (if report has findings)
        if report and report.summary.get("total_findings", 0) > 0:
            sev = report.summary.get("by_severity", {})
            high = sev.get("HIGH", 0)
            med = sev.get("MEDIUM", 0)
            low = sev.get("LOW", 0)
            with ui.element("div").style(
                f"border-left: 1px solid {border}20; padding: 14px 16px; "
                f"display: flex; flex-direction: column; justify-content: center; "
                f"gap: 3px; min-width: 90px;"
            ):
                ui.label("Severity").classes("text-xs") \
                    .style(f"color: {t['text_muted']}; font-size: 0.55rem; "
                           f"text-transform: uppercase; letter-spacing: 0.04em; "
                           f"margin-bottom: 1px;")
                if high > 0:
                    ui.html(
                        f'<div style="display:flex; align-items:center; gap:5px;">'
                        f'<div style="width:6px; height:6px; border-radius:50%; '
                        f'background:{t["sev_high"]};"></div>'
                        f'<span style="font-size:0.65rem; color:{t["sev_high"]}; '
                        f'font-family:var(--mythos-mono);">{high} high</span></div>'
                    )
                if med > 0:
                    ui.html(
                        f'<div style="display:flex; align-items:center; gap:5px;">'
                        f'<div style="width:6px; height:6px; border-radius:50%; '
                        f'background:{t["sev_medium"]};"></div>'
                        f'<span style="font-size:0.65rem; color:{t["sev_medium"]}; '
                        f'font-family:var(--mythos-mono);">{med} med</span></div>'
                    )
                if low > 0:
                    ui.html(
                        f'<div style="display:flex; align-items:center; gap:5px;">'
                        f'<div style="width:6px; height:6px; border-radius:50%; '
                        f'background:{t["sev_low"]};"></div>'
                        f'<span style="font-size:0.65rem; color:{t["sev_low"]}; '
                        f'font-family:var(--mythos-mono);">{low} low</span></div>'
                    )

    # Processing metadata
    with ui.row().classes("w-full gap-4 mt-1 animate-fade-up stagger-3"):
        if ps.parse_duration_ms > 0:
            ui.label(f"Parsed in {ps.parse_duration_ms:.0f}ms").classes("text-xs mythos-mono") \
                .style(f"color: {t['text_muted']}; opacity: 0.6;")
        if ps.return_timestamp:
            ui.label(f"Return generated: {ps.return_timestamp}") \
                .classes("text-xs") \
                .style(f"color: {t['text_muted']}; opacity: 0.6;")


def _render_schedule_tree(t: dict, ps: ParseSummary):
    """Modern file-tree showing form/schedule hierarchy."""
    if not ps.schedule_inventory:
        return

    _type_colors = {
        "5471": t["info"],
        "8858": "#8b5cf6",
        "8865": "#06b6d4",
        "Other": t["text_muted"],
    }

    with ui.card().classes("w-full glass-card animate-fade-up stagger-4").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px 20px;"
    ):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("account_tree").style(f"color: {t['accent']}; font-size: 1rem;")
            ui.label("Form & Schedule Inventory").classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary']};")
            total_schedules = sum(len(n.children) for n in ps.schedule_inventory)
            ui.html(
                f'<span style="font-size:0.6rem; color:{t["text_muted"]}; '
                f'background:{t["bg_elevated"]}; padding:2px 8px; '
                f'border-radius:10px; font-family:var(--mythos-mono);">'
                f'{total_schedules} schedules</span>'
            )

        with ui.column().classes("w-full gap-0"):
            for i, top_node in enumerate(ps.schedule_inventory):
                is_last = i == len(ps.schedule_inventory) - 1
                _render_group_node(t, top_node, _type_colors, is_last)


def _render_group_node(t: dict, node: ScheduleNode, colors: dict, is_last: bool):
    """Top-level form group with color indicator and child tree."""
    type_color = colors.get(node.form_type, colors["Other"])
    has_children = bool(node.children)
    border_color = t["border"]
    bb = "none" if is_last else f"1px solid {border_color}15"
    pb = "0" if is_last else "8px"
    mb = "0" if is_last else "8px"

    with ui.element("div").classes("w-full").style(
        f"border-bottom: {bb}; padding-bottom: {pb}; margin-bottom: {mb};"
    ):
        with ui.row().classes("w-full items-center py-1 gap-3 mythos-tree-row") \
                .style("padding: 4px 8px; margin: 0 -8px;"):
            ui.html(
                f'<div style="width:8px; height:8px; border-radius:50%; '
                f'background:{type_color}; flex-shrink:0;"></div>'
            )
            ui.label(node.display_name).classes("text-xs font-semibold flex-1") \
                .style(f"color: {t['text_primary']}; letter-spacing: -0.01em;")
            with ui.row().classes("items-center gap-2"):
                if node.entity_count > 0:
                    ui.html(
                        f'<span style="font-size:0.6rem; color:{type_color}; '
                        f'background:{type_color}12; padding:1px 7px; '
                        f'border-radius:8px; font-family:var(--mythos-mono); '
                        f'border: 1px solid {type_color}25;">'
                        f'{node.entity_count} entities</span>'
                    )
                if node.field_count > 0:
                    ui.html(
                        f'<span style="font-size:0.6rem; color:{t["text_muted"]}; '
                        f'background:{t["bg_elevated"]}; padding:1px 7px; '
                        f'border-radius:8px; font-family:var(--mythos-mono);">'
                        f'{node.field_count:,} fields</span>'
                    )

        if has_children:
            with ui.column().classes("w-full gap-0").style(
                f"border-left: 1px solid {t['border']}30; "
                f"margin-left: 11px; padding-left: 12px; margin-top: 2px;"
            ):
                for j, child in enumerate(node.children):
                    _render_leaf_node(t, child, colors, j == len(node.children) - 1)


def _render_leaf_node(t: dict, node: ScheduleNode, colors: dict, is_last: bool):
    """Clickable leaf schedule node with labeled metadata pills."""
    type_color = colors.get(node.form_type, colors["Other"])

    with ui.row().classes("w-full items-center py-1 gap-2 cursor-pointer mythos-tree-row") \
            .style("padding: 4px 8px; margin: 0 -8px;") \
            .on("click", lambda _, fn=node.form_name: _navigate_to_form(fn)):
        ui.html(
            f'<span style="color:{t["border"]}; font-size:0.65rem; '
            f'opacity:0.6; width:10px; text-align:center; flex-shrink:0;">'
            f'{"└" if is_last else "├"}</span>'
        )
        ui.label(node.display_name).classes("text-xs flex-1") \
            .style(f"color: {t['text_secondary']}; font-size: 0.7rem;")
        with ui.row().classes("items-center gap-1"):
            if node.entity_count > 0:
                ui.html(
                    f'<span style="font-size:0.55rem; color:{t["text_muted"]}; '
                    f'background:{t["bg_elevated"]}; padding:1px 6px; '
                    f'border-radius:6px; font-family:var(--mythos-mono); '
                    f'white-space:nowrap;">'
                    f'{node.entity_count} ent</span>'
                )
            if node.field_count > 0:
                ui.html(
                    f'<span style="font-size:0.55rem; color:{t["text_muted"]}; '
                    f'background:{t["bg_elevated"]}; padding:1px 6px; '
                    f'border-radius:6px; font-family:var(--mythos-mono); '
                    f'white-space:nowrap;">'
                    f'{node.field_count:,} fields</span>'
                )
            if node.has_multi_instance:
                ui.html(
                    f'<span style="font-size:0.5rem; color:{t["info"]}; '
                    f'background:{t["info"]}10; border: 1px solid {t["info"]}30; '
                    f'padding:0px 5px; border-radius:4px; white-space:nowrap;">'
                    f'multi</span>'
                )


def _navigate_to_form(form_name: str):
    """Navigate to parsed data tab filtered to this form."""
    s = get_state()
    s.xml_check.selected_form = form_name
    s.xml_check.active_tab = "parsed_data"
    ui.navigate.to("/review")

"""Home Dashboard — Executive cockpit consolidating all Mythos module statuses."""

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.pages.dashboard_data import compute_dashboard, DashboardData, ModuleStatus


def render():
    """Render the Home dashboard."""
    t = get_theme()
    s = get_state()

    if not s.report and not s.current_xml:
        _render_empty(t)
        return

    if s.current_xml and not s.report:
        _render_pending(t, s)
        return

    data = compute_dashboard(s)
    _render_dashboard(t, data)


# ─── FULL DASHBOARD ──────────────────────────────────────────────────────────

def _render_dashboard(t: dict, data: DashboardData):
    """Main dashboard with all sections."""

    # Section 1: Project Header
    _project_header(t, data)

    # Section 2: KPI Strip
    _kpi_strip(t, data)

    # Section 3: Module Grid
    _module_grid(t, data)

    # Section 4: Issue Distribution (only if there are issues)
    if data.total_issues > 0:
        _issue_distribution(t, data)

    # Section 5: Top Entities (only if there are findings)
    if data.top_entities:
        _top_entities(t, data)

    # Two-column: Activity + Actions — stacks on narrow windows
    with ui.row().classes("w-full gap-4 flex-wrap animate-fade-up stagger-6"):
        with ui.column().classes("flex-1 min-w-[300px]"):
            _recent_activity(t, data)

        with ui.column().classes("flex-1 min-w-[300px]"):
            _action_items(t, data)


# ─── SECTION 1: PROJECT HEADER ───────────────────────────────────────────────

def _project_header(t: dict, data: DashboardData):
    """Glass panel with project context."""
    status_colors = {
        "clean": t["success"],
        "issues": t["accent"],
        "critical": t["sev_high"],
        "not_started": t["text_muted"],
    }
    status_labels = {
        "clean": "All Clear",
        "issues": "Issues Detected",
        "critical": "Critical Issues",
        "not_started": "Not Started",
    }
    color = status_colors.get(data.overall_status, t["text_muted"])
    label = status_labels.get(data.overall_status, "Unknown")

    with ui.card().classes("w-full glass-card animate-fade-up stagger-1").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-top: 3px solid {color}; "
        f"border-radius: 12px; padding: 20px 24px;"
    ):
        with ui.row().classes("w-full items-start justify-between flex-wrap gap-4"):
            # Left: client + project info
            with ui.column().classes("gap-1"):
                with ui.row().classes("items-center gap-3"):
                    ui.label(data.client_name or "No Client Loaded") \
                        .classes("text-xl font-bold") \
                        .style(f"color: {t['text_primary']};")
                    if data.tax_year:
                        ui.badge(f"FY{data.tax_year}", color="transparent").props("dense") \
                            .style(f"color: {t['accent']}; border: 1px solid {t['accent']}40; "
                                   f"font-size: 0.6rem;")
                    ui.badge(label, color="transparent").props("dense") \
                        .style(f"color: {color}; border: 1px solid {color}40; "
                               f"font-size: 0.6rem;")

                with ui.row().classes("items-center gap-4 mt-1"):
                    if data.current_file:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("description").style(
                                f"color: {t['text_muted']}; font-size: 0.8rem;")
                            ui.label(f"CY: {data.current_file}").classes("text-xs") \
                                .style(f"color: {t['text_secondary']};")
                    if data.prior_file:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("history").style(
                                f"color: {t['text_muted']}; font-size: 0.8rem;")
                            ui.label(f"PY: {data.prior_file}").classes("text-xs") \
                                .style(f"color: {t['text_secondary']};")

            # Right: timestamp + actions
            with ui.column().classes("items-end gap-1"):
                if data.last_updated:
                    ui.label(f"Last updated: {data.last_updated[:16]}") \
                        .classes("text-xs") \
                        .style(f"color: {t['text_muted']};")
                with ui.row().classes("gap-2 mt-1"):
                    ui.button("Review", icon="verified",
                              on_click=lambda: ui.navigate.to("/review")) \
                        .props("flat dense no-caps size=sm") \
                        .style(f"color: {t['accent']}; font-size: 0.7rem;")
                    ui.button("Export", icon="download",
                              on_click=lambda: _handle_export()) \
                        .props("flat dense no-caps size=sm") \
                        .style(f"color: {t['text_muted']}; font-size: 0.7rem;")


# ─── SECTION 2: KPI STRIP ────────────────────────────────────────────────────

def _kpi_strip(t: dict, data: DashboardData):
    """Row of 6 KPI cards — wraps to 2 rows on narrow windows."""
    with ui.row().classes("w-full gap-3 flex-wrap animate-fade-up stagger-2"):
        _kpi_card(t, str(data.total_entities), "Entities", t["info"], "groups")
        _kpi_card(t, str(data.files_processed), "Files Loaded", t["text_primary"], "folder")
        _kpi_card(t, f"{data.modules_completed}/{data.total_modules}", "Modules",
                  t["success"] if data.modules_completed == data.total_modules else t["accent"],
                  "check_circle")
        _kpi_card(t, str(data.total_issues), "Issues",
                  t["sev_high"] if data.total_issues > 0 else t["success"], "bug_report")
        _kpi_card(t, str(data.critical_issues), "Critical",
                  t["sev_high"] if data.critical_issues > 0 else t["success"], "error")
        _kpi_card(t, f"{data.completion_pct:.0f}%", "Complete",
                  t["success"] if data.completion_pct >= 75 else t["accent"], "pie_chart")


def _kpi_card(t: dict, value: str, label: str, color: str, icon: str):
    """Single KPI card."""
    with ui.card().classes("flex-1 min-w-[140px] max-w-[220px] hover-lift").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-top: 2px solid {color}; border-radius: 10px; padding: 14px 16px;"
    ):
        with ui.row().classes("items-center justify-between"):
            ui.icon(icon).style(f"color: {color}; opacity: 0.5; font-size: 0.9rem;")
        ui.label(value).classes("text-lg font-bold mythos-mono mt-1") \
            .style(f"color: {color};")
        ui.label(label).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


# ─── SECTION 3: MODULE GRID ──────────────────────────────────────────────────

def _module_grid(t: dict, data: DashboardData):
    """Grid of 4 module status cards — wraps on narrow windows."""
    with ui.row().classes("w-full gap-3 flex-wrap animate-fade-up stagger-3"):
        for module in data.modules:
            _module_card(t, module)


def _module_card(t: dict, m: ModuleStatus):
    """Single module status card — clickable, navigates to module page."""
    status_styles = {
        "completed": {"color": t["success"], "icon": "check_circle", "label": "Completed"},
        "warning": {"color": t["accent"], "icon": "warning", "label": "Issues Found"},
        "failed": {"color": t["sev_high"], "icon": "error", "label": "Failed"},
        "not_run": {"color": t["text_muted"], "icon": "radio_button_unchecked", "label": "Not Run"},
    }
    style = status_styles.get(m.status, status_styles["not_run"])

    with ui.card().classes("flex-1 min-w-[220px] glass-card hover-lift cursor-pointer") \
            .style(
                f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
                f"border-left: 3px solid {style['color']}; "
                f"border-radius: 10px; padding: 16px;"
            ).on("click", lambda _, r=m.route: ui.navigate.to(r)):

        with ui.row().classes("items-center justify-between w-full"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(m.icon).style(f"color: {style['color']}; font-size: 1.1rem;")
                ui.label(m.name).classes("text-sm font-semibold") \
                    .style(f"color: {t['text_primary']};")
            ui.icon(style["icon"]).style(f"color: {style['color']}; font-size: 0.9rem;")

        # Stats row
        with ui.row().classes("items-center gap-3 mt-3"):
            if m.entity_count > 0:
                _mini_stat(t, str(m.entity_count), "entities")
            if m.issue_count > 0:
                _mini_stat(t, str(m.issue_count), "issues")
            elif m.status in ("completed", "warning"):
                _mini_stat(t, "0", "issues")

        # Status label
        ui.label(style["label"]).classes("text-xs mt-2") \
            .style(f"color: {style['color']}; font-size: 0.6rem;")


def _mini_stat(t: dict, value: str, label: str):
    """Tiny inline stat."""
    with ui.row().classes("items-center gap-1"):
        ui.label(value).classes("text-xs font-bold mythos-mono") \
            .style(f"color: {t['text_primary']};")
        ui.label(label).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.55rem;")


# ─── SECTION 4: ISSUE DISTRIBUTION ───────────────────────────────────────────

def _issue_distribution(t: dict, data: DashboardData):
    """Two-column: severity bars + category bars — stacks vertically on narrow windows."""
    with ui.row().classes("w-full gap-4 flex-wrap animate-fade-up stagger-4"):
        # Severity breakdown
        with ui.card().classes("flex-1 min-w-[280px] glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 16px;"
        ):
            ui.label("By Severity").classes("text-xs font-semibold mb-3") \
                .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                       f"letter-spacing: 0.05em; font-size: 0.6rem;")

            sev_colors = {"HIGH": t["sev_high"], "MEDIUM": t["accent"], "LOW": t["info"]}
            max_val = max(data.issues_by_severity.values()) if data.issues_by_severity else 1

            for sev in ["HIGH", "MEDIUM", "LOW"]:
                count = data.issues_by_severity.get(sev, 0)
                pct = count / max_val * 100 if max_val > 0 else 0
                color = sev_colors.get(sev, t["text_muted"])

                with ui.row().classes("items-center gap-2 w-full mb-2"):
                    ui.label(sev.capitalize()).classes("text-xs w-16") \
                        .style(f"color: {t['text_secondary']};")
                    with ui.row().classes("flex-1 items-center"):
                        ui.element("div").style(
                            f"height: 6px; width: {max(pct, 2)}%; "
                            f"background: {color}; border-radius: 3px; "
                            f"transition: width 0.5s ease;")
                    ui.label(str(count)).classes("text-xs font-bold mythos-mono w-8 text-right") \
                        .style(f"color: {color};")

        # Category breakdown
        with ui.card().classes("flex-1 min-w-[280px] glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 16px;"
        ):
            ui.label("By Category").classes("text-xs font-semibold mb-3") \
                .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                       f"letter-spacing: 0.05em; font-size: 0.6rem;")

            cat_colors = {
                "flow": t["info"], "completeness": t["accent"],
                "reasonableness": t["success"], "rollover": t["error"],
                "cross_schedule": "#8b5cf6", "cross_form": "#ec4899",
            }
            max_cat = max(data.issues_by_category.values()) if data.issues_by_category else 1

            sorted_cats = sorted(data.issues_by_category.items(),
                                 key=lambda x: x[1], reverse=True)
            for cat, count in sorted_cats[:6]:
                pct = count / max_cat * 100 if max_cat > 0 else 0
                color = cat_colors.get(cat, t["text_muted"])
                display_name = cat.replace("_", " ").title()

                with ui.row().classes("items-center gap-2 w-full mb-2"):
                    ui.label(display_name).classes("text-xs w-24") \
                        .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")
                    with ui.row().classes("flex-1 items-center"):
                        ui.element("div").style(
                            f"height: 6px; width: {max(pct, 2)}%; "
                            f"background: {color}; border-radius: 3px; "
                            f"transition: width 0.5s ease;")
                    ui.label(str(count)).classes("text-xs font-bold mythos-mono w-8 text-right") \
                        .style(f"color: {color};")


# ─── SECTION 5: TOP ENTITIES ─────────────────────────────────────────────────

def _top_entities(t: dict, data: DashboardData):
    """Table of entities with most issues."""
    with ui.card().classes("w-full glass-card animate-fade-up stagger-5").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px;"
    ):
        with ui.row().classes("items-center justify-between mb-3"):
            ui.label("Entities Requiring Attention").classes("text-xs font-semibold") \
                .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                       f"letter-spacing: 0.05em; font-size: 0.6rem;")
            ui.button("View All", icon="arrow_forward",
                      on_click=lambda: ui.navigate.to("/review")) \
                .props("flat dense no-caps size=sm") \
                .style(f"color: {t['accent']}; font-size: 0.65rem;")

        columns = [
            {"name": "code", "label": "Code", "field": "code", "align": "left"},
            {"name": "name", "label": "Entity", "field": "name", "align": "left"},
            {"name": "critical", "label": "Critical", "field": "critical", "align": "center",
             "sortable": True},
            {"name": "total", "label": "Total", "field": "total", "align": "center",
             "sortable": True},
        ]

        rows = [
            {"id": code, "code": code,
             "name": (name[:35] + "..." if len(name) > 35 else name),
             "critical": critical, "total": total}
            for code, name, total, critical in data.top_entities[:8]
        ]

        table = ui.table(
            columns=columns, rows=rows, row_key="id",
            pagination={"rowsPerPage": 8},
        ).classes("w-full").props("dense flat bordered separator=cell")

        table.style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}20; "
            f"border-radius: 8px;")

        table.add_slot("body-cell-critical", """
            <q-td :props="props">
                <span :style="props.row.critical > 0 ?
                    'color: #ef4444; font-weight: 700' : 'color: inherit'">
                    {{ props.row.critical }}
                </span>
            </q-td>
        """)


# ─── SECTION 6: RECENT ACTIVITY ──────────────────────────────────────────────

def _recent_activity(t: dict, data: DashboardData):
    """Compact timeline of recent reviews."""
    with ui.card().classes("w-full glass-card").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px; min-height: 180px;"
    ):
        ui.label("Recent Activity").classes("text-xs font-semibold mb-3") \
            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                   f"letter-spacing: 0.05em; font-size: 0.6rem;")

        if not data.recent_history:
            ui.label("No activity yet — run a review to get started.") \
                .classes("text-xs").style(f"color: {t['text_muted']};")
            return

        for entry in data.recent_history:
            with ui.row().classes("items-center gap-3 w-full py-2") \
                    .style(f"border-bottom: 1px solid {t['border']}20;"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.85rem;")
                with ui.column().classes("gap-0 flex-1"):
                    ui.label(f"{entry.client_name} · FY{entry.tax_year}") \
                        .classes("text-xs font-semibold") \
                        .style(f"color: {t['text_primary']};")
                    ui.label(
                        f"{entry.entity_count} entities · {entry.finding_count} findings"
                    ).classes("text-xs") \
                        .style(f"color: {t['text_muted']}; font-size: 0.6rem;")
                ui.label(entry.timestamp).classes("text-xs mythos-mono") \
                    .style(f"color: {t['text_muted']}; font-size: 0.55rem;")


# ─── SECTION 7: ACTION ITEMS ─────────────────────────────────────────────────

def _action_items(t: dict, data: DashboardData):
    """Priority-sorted action cards."""
    with ui.card().classes("w-full glass-card").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 16px; min-height: 180px;"
    ):
        ui.label("Action Required").classes("text-xs font-semibold mb-3") \
            .style(f"color: {t['text_muted']}; text-transform: uppercase; "
                   f"letter-spacing: 0.05em; font-size: 0.6rem;")

        if not data.action_items:
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.9rem;")
                ui.label("All caught up — no pending actions.") \
                    .classes("text-xs").style(f"color: {t['success']};")
            return

        priority_colors = {
            "high": t["sev_high"],
            "medium": t["accent"],
            "low": t["text_muted"],
        }

        for item in data.action_items:
            color = priority_colors.get(item.get("priority", "medium"), t["text_muted"])
            with ui.row().classes("items-center gap-3 w-full py-2 cursor-pointer") \
                    .style(f"border-left: 2px solid {color}; padding-left: 12px; "
                           f"border-bottom: 1px solid {t['border']}15;") \
                    .on("click", lambda _, r=item["route"]: ui.navigate.to(r)):
                ui.icon(item["icon"]).style(f"color: {color}; font-size: 0.9rem;")
                ui.label(item["text"]).classes("text-xs flex-1") \
                    .style(f"color: {t['text_secondary']};")
                ui.icon("chevron_right").style(
                    f"color: {t['text_muted']}; font-size: 0.8rem; opacity: 0.5;")


# ─── EMPTY STATE ──────────────────────────────────────────────────────────────

def _render_empty(t: dict):
    """No data loaded — welcome screen."""
    from lab.mythos_ui.layout import LOGO_SVG

    with ui.column().classes("w-full items-center justify-center py-12 gap-5 animate-fade-up"):
        ui.html(LOGO_SVG.replace('width="16"', 'width="48"')
                .replace('height="18"', 'height="54"')) \
            .style(f"color: {t['accent']};")

        ui.label("Welcome to Mythos").classes("text-2xl font-bold") \
            .style(f"color: {t['text_primary']};")

        ui.label(
            "Automated compliance engine for US international tax returns. "
            "Load an XML e-file to begin your review."
        ).classes("text-sm text-center max-w-lg") \
            .style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-3 mt-4"):
            ui.button("Start Review", icon="play_circle",
                      on_click=lambda: ui.navigate.to("/review")) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 10px 28px; border-radius: 6px; font-size: 0.85rem;")


        # Value props
        ui.separator().classes("w-48 my-6").style(f"background: {t['border']}30;")
        with ui.row().classes("gap-8"):
            _value_prop(t, "bolt", "< 3 sec", "Per entity")
            _value_prop(t, "checklist", "32 checks", "4 dimensions")
            _value_prop(t, "picture_as_pdf", "PDF lock", "Cross-validation")
            _value_prop(t, "swap_vert", "Rollover", "YoY analysis")


def _render_pending(t: dict, s):
    """XML loaded but review not yet run."""
    with ui.column().classes("w-full items-center justify-center py-12 gap-5 animate-fade-up"):
        ui.icon("description").classes("text-5xl") \
            .style(f"color: {t['success']}; opacity: 0.7;")

        ui.label("XML Loaded — Ready to Review").classes("text-lg font-bold") \
            .style(f"color: {t['text_primary']};")

        ui.label(
            f"File: {s.current_xml.name}" +
            (f" + Prior: {s.prior_xml.name}" if s.prior_xml else "")
        ).classes("text-sm text-center") \
            .style(f"color: {t['text_secondary']};")

        ui.button("Run Review", icon="play_circle",
                  on_click=lambda: ui.navigate.to("/review")) \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"padding: 10px 28px; border-radius: 6px; font-size: 0.85rem;")


def _value_prop(t: dict, icon: str, title: str, subtitle: str):
    """Mini value proposition."""
    with ui.column().classes("items-center gap-1"):
        ui.icon(icon).classes("text-lg") \
            .style(f"color: {t['accent']}; opacity: 0.7;")
        ui.label(title).classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(subtitle).classes("text-xs") \
            .style(f"color: {t['text_muted']};")


# ─── HANDLERS ─────────────────────────────────────────────────────────────────


async def _handle_export():
    """Export from dashboard."""
    from lab.mythos_ui.services.bridge import run_export

    result = await run_export(fmt="excel")
    if result and result.success:
        ui.notify(f"Exported: {result.path.name}", type="positive")
    else:
        ui.notify("Nothing to export", type="warning")

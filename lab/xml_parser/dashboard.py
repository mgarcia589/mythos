"""Mythos Dashboard — Native compliance review application.

Professional dark-mode analytics dashboard with tabular reporting,
multi-filter controls, and interactive entity/check exploration.

Launch: python -m lab.xml_parser.dashboard
"""

import tempfile
from pathlib import Path

import pandas as pd
from nicegui import ui, app

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.review_engine import ReviewEngine, ReviewReport

# ─── DESIGN TOKENS (shadcn/radix-inspired dark palette) ─────────────────────

T = {
    # Backgrounds (slate-based, warm neutral)
    "bg": "#09090b",           # zinc-950
    "bg_raised": "#18181b",    # zinc-900
    "bg_surface": "#27272a",   # zinc-800
    "bg_hover": "#3f3f46",     # zinc-700

    # Borders
    "border": "#27272a",       # zinc-800
    "border_subtle": "#1f1f23",
    "border_focus": "#a1a1aa", # zinc-400

    # Text
    "text": "#fafafa",         # zinc-50
    "text_secondary": "#a1a1aa",  # zinc-400
    "text_muted": "#71717a",   # zinc-500
    "text_faint": "#52525b",   # zinc-600

    # Accent (warm amber/orange)
    "accent": "#f59e0b",       # amber-500
    "accent_muted": "#92400e", # amber-800
    "accent_text": "#fbbf24",  # amber-400

    # Semantic
    "success": "#22c55e",      # green-500
    "warning": "#f59e0b",      # amber-500
    "error": "#ef4444",        # red-500
    "info": "#3b82f6",         # blue-500

    # Severity
    "sev_high": "#ef4444",
    "sev_high_bg": "#451a1a",
    "sev_medium": "#f59e0b",
    "sev_medium_bg": "#422006",
    "sev_low": "#71717a",
    "sev_low_bg": "#27272a",
}


# ─── APP STATE ───────────────────────────────────────────────────────────────

class AppState:
    def __init__(self):
        self.report: ReviewReport | None = None
        self.current_xml: Path | None = None
        self.prior_xml: Path | None = None
        self.parser: EFileParser | None = None
        # Filters
        self.filter_severity: list[str] = []
        self.filter_category: list[str] = []
        self.filter_entities: list[str] = []

    def filtered_findings(self):
        if not self.report:
            return []
        findings = self.report.findings
        if self.filter_severity:
            findings = [f for f in findings if f.severity in self.filter_severity]
        if self.filter_category:
            findings = [f for f in findings if f.category in self.filter_category]
        if self.filter_entities:
            findings = [f for f in findings if f.entity_code in self.filter_entities]
        return findings

    @property
    def entity_codes(self) -> list[str]:
        if not self.report:
            return []
        return sorted(set(f.entity_code for f in self.report.findings))

    @property
    def categories(self) -> list[str]:
        if not self.report:
            return []
        return sorted(set(f.category for f in self.report.findings))


state = AppState()


# ─── STYLES ──────────────────────────────────────────────────────────────────

GLOBAL_CSS = f"""
<style>
:root {{
    --bg: {T['bg']};
    --surface: {T['bg_raised']};
    --border: {T['border']};
}}
body {{
    background: {T['bg']} !important;
    color: {T['text']} !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}
.q-header {{
    background: {T['bg_raised']} !important;
    border-bottom: 1px solid {T['border']} !important;
    box-shadow: none !important;
}}
.q-drawer {{
    background: {T['bg_raised']} !important;
    border-right: 1px solid {T['border']} !important;
}}
.q-card {{
    background: {T['bg_raised']} !important;
    border: 1px solid {T['border']} !important;
    box-shadow: none !important;
    border-radius: 8px !important;
}}
.q-table {{
    background: {T['bg_raised']} !important;
}}
.q-table thead th {{
    background: {T['bg_surface']} !important;
    color: {T['text_secondary']} !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    font-weight: 600 !important;
    border-bottom: 1px solid {T['border']} !important;
}}
.q-table tbody td {{
    color: {T['text']} !important;
    border-bottom: 1px solid {T['border_subtle']} !important;
    font-size: 13px !important;
}}
.q-table tbody tr:hover td {{
    background: {T['bg_surface']} !important;
}}
.q-field--outlined .q-field__control {{
    background: {T['bg_surface']} !important;
    border-color: {T['border']} !important;
}}
.q-chip {{
    font-size: 11px !important;
    font-weight: 600 !important;
}}
.metric-box {{
    background: {T['bg_raised']};
    border: 1px solid {T['border']};
    border-radius: 8px;
    padding: 20px;
}}
.filter-bar {{
    background: {T['bg_raised']};
    border: 1px solid {T['border']};
    border-radius: 8px;
    padding: 12px 16px;
}}
.sev-badge-high {{ background: {T['sev_high_bg']}; color: {T['sev_high']}; border: 1px solid {T['sev_high']}44; }}
.sev-badge-medium {{ background: {T['sev_medium_bg']}; color: {T['sev_medium']}; border: 1px solid {T['sev_medium']}44; }}
.sev-badge-low {{ background: {T['sev_low_bg']}; color: {T['sev_low']}; border: 1px solid {T['sev_low']}44; }}
.nav-btn {{
    border-radius: 6px !important;
    text-transform: none !important;
    font-weight: 500 !important;
    justify-content: flex-start !important;
    padding: 8px 12px !important;
}}
.nav-btn.active {{
    background: {T['accent']}15 !important;
    color: {T['accent_text']} !important;
}}
</style>
"""


# ─── PAGE SHELL ──────────────────────────────────────────────────────────────

def shell(active_page: str = "overview"):
    """Shared app shell: header + sidebar + content area."""
    ui.dark_mode(True)
    ui.add_head_html(GLOBAL_CSS)
    ui.add_head_html('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">')

    # Header
    with ui.header().classes("h-12 px-4 items-center"):
        with ui.row().classes("items-center gap-2"):
            ui.label("M").classes("text-base font-bold bg-gradient-to-br from-amber-400 to-orange-500 text-transparent bg-clip-text")
            ui.label("MYTHOS").classes("text-sm font-semibold tracking-[0.15em]")
        with ui.row().classes("items-center gap-4 ml-auto"):
            if state.report:
                ui.label(state.report.client_name).classes("text-xs text-zinc-400")
                ui.separator().props("vertical").classes("h-4 opacity-30")
                ui.label(f"TY {state.report.tax_year}").classes("text-xs text-zinc-500")
            ui.label("v0.5").classes("text-[10px] text-zinc-600 border border-zinc-700 px-1.5 py-0.5 rounded")

    # Sidebar
    with ui.left_drawer(value=True).classes("w-48 pt-3"):
        nav_items = [
            ("overview", "dashboard", "Overview"),
            ("findings", "format_list_bulleted", "Findings"),
            ("entities", "domain", "Entities"),
        ]
        for key, icon, label in nav_items:
            href = "/" if key == "overview" else f"/{key}"
            active_cls = "active" if active_page == key else ""
            with ui.link(target=href).classes("no-underline block mb-0.5"):
                ui.button(label, icon=icon, on_click=lambda h=href: ui.navigate.to(h)).props(
                    "flat no-caps align=left"
                ).classes(f"w-full nav-btn {active_cls}")

        ui.separator().classes("my-3 opacity-20")
        ui.label("DATA").classes("text-[10px] tracking-widest text-zinc-600 px-3 mb-1")
        ui.button("Load Demo", icon="science", on_click=load_demo).props(
            "flat no-caps dense size=sm"
        ).classes("w-full nav-btn")
        ui.button("Export XLSX", icon="download", on_click=export_current).props(
            "flat no-caps dense size=sm"
        ).classes("w-full nav-btn")


# ─── OVERVIEW PAGE ───────────────────────────────────────────────────────────

@ui.page("/")
def page_overview():
    shell("overview")

    with ui.column().classes("w-full p-5 gap-5 max-w-[1400px] mx-auto"):
        # Upload section (only if no report loaded)
        if not state.report:
            _render_upload()
            return

        report = state.report
        s = report.summary

        # Metric cards
        with ui.row().classes("w-full gap-4"):
            _metric(str(report.entity_count), "Entities", "domain", T["info"])
            _metric(str(s["total_findings"]), "Findings", "flag", T["accent"])
            _metric(str(s["by_severity"]["HIGH"]), "Critical", "error",
                    T["sev_high"] if s["by_severity"]["HIGH"] > 0 else T["success"])
            _metric(f"{s['clean_entities']}/{report.entity_count}", "Clean", "verified", T["success"])

        # Charts row
        with ui.row().classes("w-full gap-4"):
            # Severity breakdown
            with ui.card().classes("flex-1 p-4"):
                ui.label("Severity").classes("text-xs text-zinc-500 uppercase tracking-wide mb-3")
                if s["total_findings"] > 0:
                    _severity_chart(s["by_severity"])
                else:
                    ui.label("No findings").classes("text-sm text-zinc-500 text-center py-8")

            # Category breakdown
            with ui.card().classes("flex-1 p-4"):
                ui.label("Category").classes("text-xs text-zinc-500 uppercase tracking-wide mb-3")
                cats = s.get("by_category", {})
                if cats:
                    _category_chart(cats)

            # Quick stats
            with ui.card().classes("w-64 p-4"):
                ui.label("Summary").classes("text-xs text-zinc-500 uppercase tracking-wide mb-3")
                _stat_row("Rollover", "Enabled" if state.prior_xml else "Off",
                          T["success"] if state.prior_xml else T["text_muted"])
                _stat_row("Checks Run", "28 rules", T["text_secondary"])
                _stat_row("Pass Rate",
                          f"{(s['clean_entities']/report.entity_count*100):.0f}%",
                          T["success"])
                ui.separator().classes("my-2 opacity-10")
                for cat, count in cats.items():
                    _stat_row(cat.title(), str(count), T["text_secondary"])

        # Top findings table
        with ui.card().classes("w-full p-4"):
            with ui.row().classes("items-center justify-between mb-3"):
                ui.label("Top Findings").classes("text-sm font-semibold")
                with ui.link(target="/findings"):
                    ui.button("View All", icon="east").props("flat dense no-caps size=sm color=amber")

            _findings_table(report.findings[:10])


# ─── FINDINGS PAGE ───────────────────────────────────────────────────────────

@ui.page("/findings")
def page_findings():
    shell("findings")

    with ui.column().classes("w-full p-5 gap-4 max-w-[1400px] mx-auto"):
        if not state.report:
            _no_data_card()
            return

        report = state.report

        # Reactive filter + table
        findings_container = ui.column().classes("w-full gap-0")

        def refresh_table():
            filtered = state.filtered_findings()
            count_badge.set_text(f"{len(filtered)} of {len(report.findings)}")
            findings_container.clear()
            with findings_container:
                _findings_table(filtered)

        def on_severity(e):
            state.filter_severity = e.value or []
            refresh_table()

        def on_category(e):
            state.filter_category = e.value or []
            refresh_table()

        def on_entity(e):
            state.filter_entities = e.value or []
            refresh_table()

        with ui.row().classes("w-full filter-bar items-center gap-3"):
            ui.icon("filter_list", size="xs").classes("text-zinc-500")
            ui.label("Filters").classes("text-xs text-zinc-500 uppercase tracking-wide mr-2")

            ui.select(
                options=["HIGH", "MEDIUM", "LOW"],
                label="Severity",
                multiple=True,
                value=state.filter_severity,
                on_change=on_severity,
            ).props("dense outlined clearable use-chips").classes("w-44")

            ui.select(
                options=state.categories,
                label="Category",
                multiple=True,
                value=state.filter_category,
                on_change=on_category,
            ).props("dense outlined clearable use-chips").classes("w-48")

            ui.select(
                options=state.entity_codes,
                label="Entity",
                multiple=True,
                value=state.filter_entities,
                on_change=on_entity,
            ).props("dense outlined clearable use-chips").classes("w-56")

            ui.space()
            count_badge = ui.label(f"{len(report.findings)} of {len(report.findings)}").classes("text-xs text-zinc-500")

        # Initial table
        with findings_container:
            _findings_table(report.findings)


# ─── ENTITIES PAGE ───────────────────────────────────────────────────────────

@ui.page("/entities")
def page_entities():
    shell("entities")

    with ui.column().classes("w-full p-5 gap-4 max-w-[1400px] mx-auto"):
        if not state.report or not state.parser:
            _no_data_card()
            return

        report = state.report
        sch_h = state.parser.extract_form("IRS5471ScheduleH")

        if sch_h.empty:
            _no_data_card("No Schedule H data found in XML")
            return

        sch_h = sch_h.set_index("_reference_id")
        ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
        fx_col = "IRS5471ScheduleH_ExchangeRt"
        income_col = "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt"

        rows = []
        for code in sorted(sch_h.index):
            if code == "":
                continue
            h = sch_h.loc[code]
            ep = pd.to_numeric(h.get(ep_col), errors="coerce") if ep_col in h.index else None
            fx = pd.to_numeric(h.get(fx_col), errors="coerce") if fx_col in h.index else None
            income = pd.to_numeric(h.get(income_col), errors="coerce") if income_col in h.index else None
            findings_count = len(report.by_entity(code))

            rows.append({
                "entity_code": code,
                "ep_usd": int(ep) if pd.notna(ep) else None,
                "fx_rate": round(float(fx), 4) if pd.notna(fx) else None,
                "net_income_fc": int(income) if pd.notna(income) else None,
                "findings": findings_count,
                "status": "Clean" if findings_count == 0 else f"{findings_count} issues",
            })

        # Entity table (Quasar table for better styling)
        with ui.card().classes("w-full p-4"):
            ui.label("Entity Schedule H Data").classes("text-xs text-zinc-500 uppercase tracking-wide mb-3")

            table_columns = [
                {"name": "entity_code", "label": "Code", "field": "entity_code", "align": "left", "sortable": True},
                {"name": "ep_usd", "label": "E&P (USD)", "field": "ep_usd", "align": "right", "sortable": True,
                 "format": "val => val != null ? '$' + val.toLocaleString() : 'N/A'"},
                {"name": "net_income_fc", "label": "Net Income (FC)", "field": "net_income_fc", "align": "right", "sortable": True,
                 "format": "val => val != null ? val.toLocaleString() : 'N/A'"},
                {"name": "fx_rate", "label": "FX Rate", "field": "fx_rate", "align": "right", "sortable": True,
                 "format": "val => val != null ? val.toFixed(4) : 'N/A'"},
                {"name": "findings", "label": "Findings", "field": "findings", "align": "center", "sortable": True},
                {"name": "status", "label": "Status", "field": "status", "align": "center"},
            ]

            ui.table(
                columns=table_columns,
                rows=rows,
                row_key="entity_code",
                pagination={"rowsPerPage": 30},
            ).props("flat bordered dense").classes("w-full")

        # E&P waterfall chart
        with ui.card().classes("w-full p-4"):
            ui.label("E&P by Entity (USD)").classes("text-xs text-zinc-500 uppercase tracking-wide mb-3")
            sorted_rows = sorted([r for r in rows if r["ep_usd"] is not None], key=lambda r: r["ep_usd"], reverse=True)

            fig = {
                "data": [{
                    "type": "bar",
                    "x": [r["entity_code"] for r in sorted_rows],
                    "y": [r["ep_usd"] for r in sorted_rows],
                    "marker": {
                        "color": [T["success"] if (r["ep_usd"] or 0) >= 0 else T["error"] for r in sorted_rows],
                        "opacity": 0.85,
                    },
                    "hovertemplate": "%{x}<br>$%{y:,.0f}<extra></extra>",
                }],
                "layout": {
                    "height": 280,
                    "margin": {"t": 10, "b": 70, "l": 80, "r": 20},
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "font": {"color": T["text_muted"], "size": 10, "family": "Inter"},
                    "xaxis": {"gridcolor": T["border"], "tickangle": -45},
                    "yaxis": {"gridcolor": T["border"], "tickformat": "$,.0s", "zeroline": True, "zerolinecolor": T["border"]},
                },
            }
            ui.plotly(fig).classes("w-full")


# ─── SHARED COMPONENTS ───────────────────────────────────────────────────────

def _metric(value: str, label: str, icon: str, color: str):
    with ui.element("div").classes("flex-1 metric-box"):
        with ui.row().classes("items-start justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(value).classes("text-2xl font-bold").style(f"color: {color}")
                ui.label(label).classes("text-xs text-zinc-500 mt-0.5")
            ui.icon(icon, size="sm").classes("text-zinc-700")


def _severity_chart(by_severity: dict):
    values = [by_severity["HIGH"], by_severity["MEDIUM"], by_severity["LOW"]]
    if sum(values) == 0:
        return
    fig = {
        "data": [{
            "type": "pie",
            "hole": 0.65,
            "values": values,
            "labels": ["High", "Medium", "Low"],
            "marker": {"colors": [T["sev_high"], T["sev_medium"], T["sev_low"]]},
            "textinfo": "value",
            "textfont": {"color": T["text"], "size": 13, "family": "Inter"},
            "hovertemplate": "%{label}: %{value}<extra></extra>",
        }],
        "layout": {
            "height": 180, "margin": {"t": 5, "b": 5, "l": 5, "r": 5},
            "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": T["text_muted"], "family": "Inter"},
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.15, "font": {"size": 10}},
        },
    }
    ui.plotly(fig).classes("w-full")


def _category_chart(cats: dict):
    fig = {
        "data": [{
            "type": "bar",
            "y": list(cats.keys()),
            "x": list(cats.values()),
            "orientation": "h",
            "marker": {"color": T["accent"], "opacity": 0.75},
            "text": list(cats.values()),
            "textposition": "outside",
            "textfont": {"color": T["text_secondary"], "size": 11},
            "hovertemplate": "%{y}: %{x}<extra></extra>",
        }],
        "layout": {
            "height": 180, "margin": {"t": 5, "b": 5, "l": 90, "r": 40},
            "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": T["text_muted"], "size": 11, "family": "Inter"},
            "xaxis": {"showgrid": False, "showticklabels": False},
            "yaxis": {"gridcolor": "rgba(0,0,0,0)"},
        },
    }
    ui.plotly(fig).classes("w-full")


def _stat_row(label: str, value: str, color: str = ""):
    with ui.row().classes("w-full justify-between items-center py-1"):
        ui.label(label).classes("text-xs text-zinc-500")
        ui.label(value).classes("text-xs font-medium").style(f"color: {color}" if color else "")


def _findings_table(findings: list):
    """Render findings as a proper data table."""
    if not findings:
        ui.label("No findings match the current filters.").classes("text-sm text-zinc-500 py-4 text-center")
        return

    table_rows = []
    for f in findings:
        table_rows.append({
            "severity": f.severity,
            "check_id": f.check_id,
            "category": f.category,
            "entity_code": f.entity_code,
            "entity_name": f.entity_name[:28],
            "description": f.description[:80],
            "delta": f"${f.delta:,.0f}" if f.delta else "",
        })

    columns = [
        {"name": "severity", "label": "Sev", "field": "severity", "align": "center", "sortable": True, "style": "width: 70px"},
        {"name": "check_id", "label": "Check", "field": "check_id", "align": "left", "sortable": True, "style": "width: 80px"},
        {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True, "style": "width: 100px"},
        {"name": "entity_code", "label": "Entity", "field": "entity_code", "align": "left", "sortable": True, "style": "width: 100px"},
        {"name": "entity_name", "label": "Name", "field": "entity_name", "align": "left", "style": "width: 180px"},
        {"name": "description", "label": "Description", "field": "description", "align": "left"},
        {"name": "delta", "label": "Delta", "field": "delta", "align": "right", "sortable": True, "style": "width: 100px"},
    ]

    ui.table(
        columns=columns,
        rows=table_rows,
        row_key="check_id",
        pagination={"rowsPerPage": 25, "sortBy": "severity"},
    ).props("flat bordered dense").classes("w-full")


def _render_upload():
    """Upload section when no data is loaded."""
    with ui.card().classes("w-full p-8"):
        with ui.column().classes("items-center gap-4 w-full"):
            ui.icon("upload_file", size="xl").classes("text-zinc-700")
            ui.label("Load XML returns to begin review").classes("text-sm text-zinc-400")

            with ui.row().classes("w-full gap-6 mt-4 justify-center"):
                with ui.column().classes("w-80"):
                    ui.label("Current Year (required)").classes("text-xs text-zinc-500 mb-1")
                    ui.upload(
                        label="Drop .xml",
                        auto_upload=True,
                        on_upload=lambda e: handle_upload(e, "current"),
                    ).props("accept=.xml flat bordered color=amber").classes("w-full")

                with ui.column().classes("w-80"):
                    ui.label("Prior Year (optional)").classes("text-xs text-zinc-500 mb-1")
                    ui.upload(
                        label="Drop .xml",
                        auto_upload=True,
                        on_upload=lambda e: handle_upload(e, "prior"),
                    ).props("accept=.xml flat bordered").classes("w-full")

            with ui.row().classes("gap-3 mt-4"):
                ui.button("Run Review", on_click=run_review, icon="play_arrow").props(
                    "unelevated color=amber no-caps"
                ).classes("px-6")
                ui.button("Load Demo (CNG)", on_click=load_demo, icon="science").props(
                    "flat no-caps color=grey"
                )


def _no_data_card(msg: str = "Run a review first to see data here."):
    with ui.card().classes("w-full p-12"):
        with ui.column().classes("items-center gap-2"):
            ui.icon("inbox", size="xl").classes("text-zinc-700")
            ui.label(msg).classes("text-sm text-zinc-500")


# ─── ACTIONS ─────────────────────────────────────────────────────────────────

def handle_upload(e, target: str):
    tmp = Path(tempfile.gettempdir()) / e.name
    tmp.write_bytes(e.content.read())
    if target == "current":
        state.current_xml = tmp
        ui.notify(f"Loaded: {e.name}", type="positive")
    else:
        state.prior_xml = tmp
        ui.notify(f"Prior year: {e.name}", type="positive")


def load_demo():
    base = Path("C:/Users/mgarcia241/OneDrive - PwC/Desktop/Cerebro/sources/cng")
    cy = base / "cng-fy25.xml"
    py = base / "cng-fy24.xml"
    if cy.exists():
        state.current_xml = cy
        state.prior_xml = py if py.exists() else None
        run_review()
    else:
        ui.notify("Demo files not found", type="negative")


def run_review():
    if not state.current_xml:
        ui.notify("Load a current year XML first", type="warning")
        return

    engine = ReviewEngine()
    state.report = engine.review(state.current_xml, state.prior_xml)
    state.parser = EFileParser(state.current_xml)
    state.filter_severity = []
    state.filter_category = []
    state.filter_entities = []

    ui.navigate.to("/")


def export_current():
    if not state.report:
        ui.notify("No review to export", type="warning")
        return

    report = state.report
    output_dir = Path("C:/Users/mgarcia241/OneDrive - PwC/Desktop/Cerebro/lab/xml_parser/output")
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"review_{report.tax_year}.xlsx"

    df = report.to_dataframe()
    if df.empty:
        ui.notify("Nothing to export", type="info")
        return

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Findings", index=False)
        high = df[df["severity"] == "HIGH"]
        if not high.empty:
            high.to_excel(writer, sheet_name="Critical", index=False)

    ui.notify(f"Saved: {path.name}", type="positive")


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def start():
    ui.run(
        title="Mythos",
        native=True,
        window_size=(1440, 900),
        reload=False,
    )


if __name__ == "__main__":
    start()

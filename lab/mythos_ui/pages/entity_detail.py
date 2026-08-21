"""Entity Detail page — drill-down view for a single entity."""

import plotly.graph_objects as go
from nicegui import ui

from lab.mythos_ui.theme import get_theme, plotly_template
from lab.mythos_ui.services.bridge import get_state


def render(entity_code: str):
    """Render entity drill-down for the given entity code."""
    t = get_theme()
    s = get_state()

    if not s.report:
        _render_empty(t)
        return

    report = s.report
    entity_findings = report.by_entity(entity_code)

    if not entity_findings:
        _render_not_found(t, entity_code)
        return

    entity_name = entity_findings[0].entity_name

    # Get entity metadata from parser if available
    entity_meta = _get_entity_meta(s, entity_code)

    # ── Breadcrumb Navigation ──
    with ui.row().classes("w-full items-center gap-1 mb-4 animate-fade-up stagger-1"):
        ui.link("Home", "/").classes("text-xs no-underline hover:underline") \
            .style(f"color: {t['text_muted']};")
        ui.icon("chevron_right").classes("text-xs") \
            .style(f"color: {t['border']};")
        ui.link("Entities", "/entities").classes("text-xs no-underline hover:underline") \
            .style(f"color: {t['text_muted']};")
        ui.icon("chevron_right").classes("text-xs") \
            .style(f"color: {t['border']};")
        ui.label(entity_code).classes("text-xs font-semibold mythos-mono") \
            .style(f"color: {t['text_primary']};")

    # ── Entity Header Card ──
    with ui.card().classes("w-full glass-card gradient-border animate-fade-up stagger-2").style(
        f"background: {t['glass_bg']}; border-radius: 16px; padding: 24px;"
    ):
        with ui.row().classes("w-full items-start justify-between"):
            with ui.column().classes("gap-1"):
                ui.label(entity_code).classes("text-2xl font-extrabold mythos-mono") \
                    .style(f"color: {t['accent']};")
                ui.label(entity_name).classes("text-sm") \
                    .style(f"color: {t['text_secondary']};")
            # Status badge
            high_count = sum(1 for f in entity_findings if f.severity == "HIGH")
            if high_count > 0:
                ui.badge(f"{high_count} Critical", color="red").props("outline")
            elif entity_findings:
                ui.badge(f"{len(entity_findings)} Issues", color="amber").props("outline")
            else:
                ui.badge("Clean", color="green").props("outline")

        # Meta row (if available)
        if entity_meta:
            ui.separator().classes("my-3").style(f"background: {t['border']}40;")
            with ui.row().classes("w-full gap-6"):
                if entity_meta.get("country"):
                    _meta_chip(t, "Country", entity_meta["country"])
                if entity_meta.get("currency"):
                    _meta_chip(t, "Currency", entity_meta["currency"])
                # Schedule flags
                schedules = entity_meta.get("schedules", [])
                if schedules:
                    _meta_chip(t, "Schedules", " · ".join(schedules))

    # ── KPI Strip ──
    with ui.row().classes("w-full gap-4 my-6 animate-fade-up stagger-3"):
        _mini_kpi(t, str(len(entity_findings)), "Total Findings", t["accent"])
        _mini_kpi(t, str(high_count), "High",
                  t["sev_high"] if high_count > 0 else t["text_muted"])
        _mini_kpi(t, str(sum(1 for f in entity_findings if f.severity == "MEDIUM")),
                  "Medium", t["sev_medium"])
        _mini_kpi(t, str(sum(1 for f in entity_findings if f.severity == "LOW")),
                  "Low", t["sev_low"])
        _mini_kpi(t, str(len(set(f.category for f in entity_findings))),
                  "Categories", t["info"])

    # ── Charts Row ──
    with ui.row().classes("w-full gap-4 mb-6 items-start"):
        # Severity pie
        with ui.card().classes("flex-1 glass-card animate-fade-up stagger-4").style(
            f"background: {t['glass_bg']}; border: 1px solid {t['glass_border']}; "
            f"border-radius: 16px; padding: 20px;"
        ):
            ui.label("Severity Split").classes("mythos-label mb-3")
            _severity_mini_chart(t, entity_findings)

        # By category
        with ui.card().classes("flex-1 glass-card animate-fade-up stagger-5").style(
            f"background: {t['glass_bg']}; border: 1px solid {t['glass_border']}; "
            f"border-radius: 16px; padding: 20px;"
        ):
            ui.label("By Category").classes("mythos-label mb-3")
            _category_mini_chart(t, entity_findings)

    # ── Full Findings Table ──
    with ui.column().classes("w-full animate-fade-up stagger-6"):
        ui.label(f"All Findings for {entity_code}").classes("mythos-label mb-3")
        _findings_table(t, entity_findings)


# ─── COMPONENTS ─────────────────────────────────────────────────────────────

def _mini_kpi(t: dict, value: str, label: str, color: str):
    """Compact KPI chip."""
    with ui.card().classes("hover-lift").style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(10px); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-top: 2px solid {color}; "
        f"border-radius: 12px; padding: 14px 20px;"
    ):
        ui.label(value).classes("text-xl font-bold mythos-mono") \
            .style(f"color: {color};")
        ui.label(label).classes("mythos-label mt-0.5")


def _meta_chip(t: dict, label: str, value: str):
    """Metadata key-value display."""
    with ui.column().classes("gap-0"):
        ui.label(label).classes("text-xs uppercase tracking-wider") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")
        ui.label(value).classes("text-sm font-semibold mythos-mono") \
            .style(f"color: {t['text_primary']};")


def _severity_mini_chart(t: dict, findings: list):
    """Small donut for entity severity."""
    high = sum(1 for f in findings if f.severity == "HIGH")
    med = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    if not findings:
        ui.label("No findings").classes("text-sm py-4") \
            .style(f"color: {t['success']};")
        return

    tmpl = plotly_template()
    fig = go.Figure(data=[go.Pie(
        values=[high, med, low],
        labels=["High", "Medium", "Low"],
        hole=0.7,
        marker=dict(colors=[t["sev_high"], t["sev_medium"], t["sev_low"]]),
        textinfo="value",
        textfont=dict(color=t["text_primary"], size=12, family="Inter"),
        hovertemplate="%{label}: %{value}<extra></extra>",
    )])
    fig.update_layout(
        template=tmpl,
        height=180,
        showlegend=False,
        margin=dict(t=5, b=5, l=5, r=5),
    )
    fig.add_annotation(
        text=f"<b>{len(findings)}</b>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=18, color=t["text_primary"], family="Inter"),
    )
    ui.plotly(fig).classes("w-full animate-fade-in")


def _category_mini_chart(t: dict, findings: list):
    """Horizontal bar for entity categories."""
    cats = {}
    for f in findings:
        cats[f.category] = cats.get(f.category, 0) + 1

    if not cats:
        return

    sorted_cats = dict(sorted(cats.items(), key=lambda x: x[1], reverse=True))
    tmpl = plotly_template()

    fig = go.Figure(data=[go.Bar(
        y=list(sorted_cats.keys()),
        x=list(sorted_cats.values()),
        orientation="h",
        marker=dict(color=t["accent"], opacity=0.85),
        text=list(sorted_cats.values()),
        textposition="outside",
        textfont=dict(color=t["text_secondary"], size=11),
        hovertemplate="%{y}: %{x}<extra></extra>",
    )])
    fig.update_layout(
        template=tmpl,
        height=max(120, len(sorted_cats) * 30 + 40),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(autorange="reversed"),
        margin=dict(t=5, b=5, l=90, r=40),
    )
    ui.plotly(fig).classes("w-full animate-fade-in")


def _findings_table(t: dict, findings: list):
    """Full table for entity findings."""
    columns = [
        {"name": "severity", "label": "Sev", "field": "severity", "align": "left", "sortable": True},
        {"name": "check_id", "label": "Check", "field": "check_id", "align": "left", "sortable": True},
        {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True},
        {"name": "description", "label": "Description", "field": "description", "align": "left"},
        {"name": "expected", "label": "Expected", "field": "expected", "align": "right"},
        {"name": "actual", "label": "Actual", "field": "actual", "align": "right"},
        {"name": "delta", "label": "Delta", "field": "delta", "align": "right", "sortable": True},
    ]

    rows = []
    for i, f in enumerate(findings):
        rows.append({
            "id": f"{f.check_id}_{i}",
            "severity": f.severity,
            "check_id": f.check_id,
            "category": f.category,
            "description": f.description,
            "expected": f.expected or "—",
            "actual": f.actual or "—",
            "delta": f"${f.delta:,.0f}" if f.delta else "—",
            "delta_raw": f.delta or 0,
        })

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
        pagination={"rowsPerPage": 50, "sortBy": "severity", "descending": True},
    ).classes("w-full").props("dense flat bordered separator=cell")

    table.style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(10px); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-radius: 12px;"
    )

    table.add_slot("body-cell-severity", """
        <q-td :props="props">
            <q-badge :color="props.row.severity === 'HIGH' ? 'red' :
                             props.row.severity === 'MEDIUM' ? 'amber' : 'grey'"
                     :label="props.row.severity === 'HIGH' ? 'CRITICAL' :
                             props.row.severity === 'MEDIUM' ? 'REVIEW' : 'INFO'"
                     outline dense />
        </q-td>
    """)

    table.add_slot("body-cell-delta", """
        <q-td :props="props">
            <span :style="props.row.delta_raw > 0 ? 'color: #ef4444; font-weight: 600' :
                         props.row.delta_raw < 0 ? 'color: #22c55e; font-weight: 600' :
                         'color: inherit'">
                {{ props.row.delta }}
            </span>
        </q-td>
    """)


def _get_entity_meta(s, entity_code: str) -> dict | None:
    """Extract entity metadata from parser if available."""
    if not s.parser:
        return None

    try:
        df = s.parser.to_dataframe()
        entity_rows = df[df["_reference_id"] == entity_code]
        if entity_rows.empty:
            return None

        row = entity_rows.iloc[0]
        country = str(row.get("IRS5471_CountryUnderWhoseLawsIncCd", ""))
        currency = str(row.get("IRS5471_FunctionalCurrencyCd", ""))

        # Detect schedules present
        schedules = []
        for sch, form in [("H", "IRS5471ScheduleH"), ("I-1", "IRS5471ScheduleI1"),
                          ("J", "IRS5471ScheduleJ"), ("E", "IRS5471ScheduleE"),
                          ("F", "IRS5471ScheduleF")]:
            try:
                sch_df = s.parser.extract_form(form)
                if not sch_df.empty and entity_code in sch_df["_reference_id"].values:
                    schedules.append(sch)
            except Exception:
                pass

        return {"country": country, "currency": currency, "schedules": schedules}
    except Exception:
        return None


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center justify-center py-20 gap-4 animate-fade-up"):
        ui.icon("person_off").classes("text-6xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label("No review loaded").classes("text-lg font-semibold") \
            .style(f"color: {t['text_muted']};")


def _render_not_found(t: dict, code: str):
    with ui.column().classes("w-full items-center justify-center py-20 gap-4 animate-fade-up"):
        ui.icon("search_off").classes("text-6xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label(f"Entity '{code}' not found in current review") \
            .classes("text-lg font-semibold") \
            .style(f"color: {t['text_muted']};")
        ui.button("Back to Entities", on_click=lambda: ui.navigate.to("/entities")) \
            .props("flat").style(f"color: {t['accent']};")

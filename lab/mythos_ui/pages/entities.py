"""Entities page — Card grid with hover-lift, staggered entrance, E&P chart, filterable table."""

import plotly.graph_objects as go
from nicegui import ui

from lab.mythos_ui.theme import get_theme, plotly_template
from lab.mythos_ui.services.bridge import get_state


# ─── TAG COLORS & LABELS ──────────────────────────────────────────────────
TAG_COLORS = {
    "tested_income": "green",
    "tested_loss": "red",
    "high_tax_exclusion": "orange",
    "subpart_f": "deep-purple",
    "de_minimis": "cyan",
    "full_inclusion": "indigo",
    "dormant": "grey",
    "us_property": "red",
    "sec_245a": "teal",
    "income_blocked": "red",
    "has_qbai": "light-green",
    "interest_expense": "amber",
    "negative_ep": "pink",
    "insurance": "blue",
    "dre": "purple",
    "sec_956": "deep-orange",
    "fde_8858": "purple",
}

TAG_LABELS = {
    "tested_income": "Tested Income",
    "tested_loss": "Tested Loss",
    "high_tax_exclusion": "High Tax Excl",
    "subpart_f": "Subpart F",
    "de_minimis": "De Minimis",
    "full_inclusion": "100% Owned",
    "dormant": "Dormant",
    "us_property": "US Property",
    "sec_245a": "Sec 245A",
    "income_blocked": "Blocked",
    "has_qbai": "QBAI",
    "interest_expense": "Int Expense",
    "negative_ep": "Neg E&P",
    "insurance": "Insurance",
    "dre": "DRE",
    "sec_956": "Sec 956",
    "fde_8858": "FDE/8858",
}


def render():
    """Render the entities page content."""
    t = get_theme()
    s = get_state()

    if not s.report:
        _render_empty(t)
        return

    report = s.report
    findings = report.findings
    entity_data = _build_entity_data(findings, s)

    # ── Header (animated) ──
    summary = report.summary
    with_findings = summary.get('entities_with_findings', 0)
    clean = summary.get('clean_entities', 0)

    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Entity Analysis").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label(f"{report.entity_count} entities · "
                     f"{with_findings} with issues · "
                     f"{clean} clean") \
                .classes("text-sm").style(f"color: {t['text_secondary']};")

    # ── Findings by Entity Chart (glass container) ──
    with ui.card().classes("w-full mb-6 glass-card animate-fade-up stagger-2").style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(14px); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-radius: 16px; padding: 20px;"
    ):
        ui.label("Findings by Entity").classes("mythos-label mb-3")
        _entity_bar_chart(t, entity_data)

    # ── Entity Cards Grid (staggered entrance + hover glow) ──
    with ui.column().classes("w-full animate-fade-up stagger-3"):
        with ui.row().classes("w-full items-center justify-between mb-3"):
            ui.label("Entity Cards").classes("mythos-label")
            ui.label(f"{len(entity_data)} entities with findings") \
                .classes("text-xs").style(f"color: {t['text_muted']};")

    # Limit initial render to 50 cards for performance
    display_limit = 50
    with ui.row().classes("w-full flex-wrap gap-4"):
        for i, ent in enumerate(entity_data[:display_limit]):
            stagger = min(i + 3, 8)
            _entity_card(t, ent, stagger)

    if len(entity_data) > display_limit:
        ui.label(
            f"Showing top {display_limit} of {len(entity_data)} entities (sorted by severity). "
            f"Use the table below to filter."
        ).classes("text-xs mt-4 text-center w-full") \
            .style(f"color: {t['text_muted']};")

    # ── Filterable Table ──
    _entity_table(t, entity_data)


# ─── COMPONENTS ─────────────────────────────────────────────────────────────

def _entity_card(t: dict, ent: dict, stagger: int = 3):
    """Single entity card with hover-lift + glow."""
    total = ent["total"]
    high = ent["high"]
    has_issues = total > 0

    border_color = t["sev_high"] if high > 0 else (
        t["sev_medium"] if total > 0 else t["success"]
    )

    extra_cls = " glow-critical" if high >= 3 else ""

    with ui.card().classes(
        f"w-[280px] hover-glow animate-scale-in stagger-{stagger}{extra_cls}"
    ).style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(12px) saturate(1.2); "
        f"-webkit-backdrop-filter: blur(12px) saturate(1.2); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-left: 3px solid {border_color}; "
        f"border-radius: 12px; padding: 16px; cursor: pointer;"
    ).on("click", lambda _, c=ent["code"]: ui.navigate.to(f"/entities/{c}")):
        # Header row
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(ent["code"]).classes("text-sm font-bold mythos-mono") \
                .style(f"color: {t['text_primary']};")
            if has_issues:
                badge_color = "red" if high > 0 else "amber"
                ui.badge(str(total), color=badge_color).props("dense")
            else:
                ui.icon("check_circle").classes("text-sm") \
                    .style(f"color: {t['success']};")

        # Name
        ui.label(ent["name"]).classes("text-xs mb-3") \
            .style(f"color: {t['text_secondary']}; "
                   f"white-space: nowrap; overflow: hidden; text-overflow: ellipsis; "
                   f"max-width: 240px;")

        # Severity breakdown (actionable labels)
        if has_issues:
            with ui.row().classes("w-full gap-2"):
                if ent["high"] > 0:
                    _sev_chip(t, "CRT", ent["high"], t["sev_high"])
                if ent["medium"] > 0:
                    _sev_chip(t, "REV", ent["medium"], t["sev_medium"])
                if ent["low"] > 0:
                    _sev_chip(t, "INF", ent["low"], t["sev_low"])
        else:
            ui.label("All checks passed").classes("text-xs") \
                .style(f"color: {t['success']}; opacity: 0.8;")

        # Classifier tags
        if ent["tags"]:
            with ui.row().classes("w-full flex-wrap gap-1 mt-2"):
                for tag in sorted(ent["tags"]):
                    color = TAG_COLORS.get(tag, "grey-8")
                    label = TAG_LABELS.get(tag, tag.replace("_", " "))
                    ui.badge(label, color=color).props("dense") \
                        .classes("text-xs").style("font-size: 0.55rem; padding: 1px 5px;")


def _sev_chip(t: dict, label: str, count: int, color: str):
    """Tiny severity chip."""
    with ui.row().classes("items-center gap-1 px-2 py-0.5 rounded") \
            .style(f"background: {color}15;"):
        ui.label(f"{label}:{count}").classes("text-xs font-semibold mythos-mono") \
            .style(f"color: {color};")


def _entity_bar_chart(t: dict, entity_data: list):
    """Horizontal stacked bar chart — top 15 entities by findings."""
    with_findings = [e for e in entity_data if e["total"] > 0]
    with_findings.sort(key=lambda x: x["total"], reverse=True)
    top = with_findings[:15]

    if not top:
        ui.label("All entities passed all checks").classes("text-sm py-4") \
            .style(f"color: {t['success']};")
        return

    tmpl = plotly_template()
    codes = [e["code"] for e in top]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=codes,
        x=[e["high"] for e in top],
        name="High",
        orientation="h",
        marker=dict(color=t["sev_high"], line=dict(width=0)),
        hovertemplate="%{y}: %{x} HIGH<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=codes,
        x=[e["medium"] for e in top],
        name="Medium",
        orientation="h",
        marker=dict(color=t["sev_medium"], line=dict(width=0)),
        hovertemplate="%{y}: %{x} MEDIUM<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=codes,
        x=[e["low"] for e in top],
        name="Low",
        orientation="h",
        marker=dict(color=t["sev_low"], line=dict(width=0)),
        hovertemplate="%{y}: %{x} LOW<extra></extra>",
    ))

    fig.update_layout(
        template=tmpl,
        barmode="stack",
        height=max(200, len(top) * 28 + 60),
        xaxis=dict(title="Findings", showgrid=True, gridcolor=f"{t['border']}40"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", y=-0.15, font=dict(size=11, color=t["text_muted"])),
        margin=dict(t=10, b=50, l=80, r=20),
    )
    ui.plotly(fig).classes("w-full animate-fade-in")


# ─── FILTERABLE TABLE ──────────────────────────────────────────────────────

def _entity_table(t: dict, entity_data: list[dict]):
    """Filterable entity table with Excel-like column header filters."""
    if not entity_data:
        return

    # Collect unique values for filter dropdowns
    all_tags = set()
    for ent in entity_data:
        all_tags.update(ent["tags"])
    all_tags_sorted = sorted(all_tags)

    with ui.card().classes("w-full mt-6 animate-fade-up stagger-4").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 12px; padding: 16px;"
    ):
        with ui.row().classes("items-center gap-2 mb-3"):
            ui.icon("filter_list").style(f"color: {t['accent']}; font-size: 1rem;")
            ui.label("Entity Table").classes("text-sm font-semibold") \
                .style(f"color: {t['text_primary']};")

        # ── Filter row (Excel-like) ──
        with ui.row().classes("w-full gap-3 mb-3 items-end flex-wrap").style(
            f"background: {t['bg_main']}; border: 1px solid {t['border']}30; "
            f"border-radius: 8px; padding: 10px 14px;"
        ):
            entity_search = ui.input(
                placeholder="Search entity...",
            ).classes("w-40").props("dense outlined clearable") \
                .style("font-size: 0.7rem;")

            sev_filter = ui.select(
                options=["All", "Critical (HIGH)", "Review (MEDIUM)", "Info (LOW)", "Clean"],
                value="All",
                label="Severity",
            ).classes("w-40").props("dense outlined")

            tag_filter = ui.select(
                options=["All"] + [t_name.replace("_", " ") for t_name in all_tags_sorted],
                value="All",
                label="Tag",
            ).classes("w-40").props("dense outlined")

            count_label = ui.label(f"{len(entity_data)} entities") \
                .classes("text-xs ml-auto mythos-mono") \
                .style(f"color: {t['text_muted']};")

        # Build table
        columns = [
            {"name": "code", "label": "Entity Code", "field": "code", "align": "left", "sortable": True},
            {"name": "name", "label": "Name", "field": "name", "align": "left", "sortable": True},
            {"name": "total", "label": "Findings", "field": "total", "align": "center", "sortable": True},
            {"name": "high", "label": "Critical", "field": "high", "align": "center", "sortable": True},
            {"name": "medium", "label": "Review", "field": "medium", "align": "center", "sortable": True},
            {"name": "low", "label": "Info", "field": "low", "align": "center", "sortable": True},
            {"name": "tags", "label": "Tags", "field": "tags_str", "align": "left"},
        ]

        all_rows = _build_table_rows(entity_data)

        table = ui.table(
            columns=columns,
            rows=all_rows,
            row_key="code",
            pagination={"rowsPerPage": 25, "sortBy": "high", "descending": True},
        ).classes("w-full").props("dense flat bordered separator=cell virtual-scroll")
        table.style(f"background: {t['bg_card']}; max-height: 50vh; font-size: 0.7rem;")

        # Custom severity cells with color
        table.add_slot("body-cell-high", """
            <q-td :props="props">
                <span :style="props.row.high > 0 ? 'color: #ef4444; font-weight: 700;' : 'color: #666;'">
                    {{ props.row.high || '—' }}
                </span>
            </q-td>
        """)
        table.add_slot("body-cell-medium", """
            <q-td :props="props">
                <span :style="props.row.medium > 0 ? 'color: #f59e0b; font-weight: 600;' : 'color: #666;'">
                    {{ props.row.medium || '—' }}
                </span>
            </q-td>
        """)
        table.add_slot("body-cell-low", """
            <q-td :props="props">
                <span :style="props.row.low > 0 ? 'color: #6b7280;' : 'color: #666;'">
                    {{ props.row.low || '—' }}
                </span>
            </q-td>
        """)

        # Tags cell — colored badges
        table.add_slot("body-cell-tags", """
            <q-td :props="props">
                <div class="row items-center q-gutter-xs" v-if="props.row.tags_str">
                    <q-badge v-for="tag in props.row.tags_str.split('|')" :key="tag"
                        :color="tag.includes('tested_income') || tag.includes('has_qbai') ? 'green' :
                                tag.includes('tested_loss') || tag.includes('us_property') || tag.includes('negative_ep') || tag.includes('income_blocked') ? 'red' :
                                tag.includes('dormant') ? 'grey' :
                                tag.includes('high_tax') ? 'orange' :
                                tag.includes('subpart_f') ? 'deep-purple' :
                                tag.includes('insurance') ? 'blue' :
                                tag.includes('dre') || tag.includes('fde') ? 'purple' :
                                tag.includes('full_inclusion') ? 'indigo' :
                                tag.includes('de_minimis') ? 'cyan' :
                                'teal'"
                        :label="tag.replace(/_/g, ' ')"
                        dense
                        style="font-size: 0.55rem; padding: 1px 5px; border-radius: 8px;" />
                </div>
                <span v-else style="color: #666;">—</span>
            </q-td>
        """)

        # Row click
        table.on("row-click", lambda e: ui.navigate.to(
            f"/entities/{e.args[1].get('code', '')}" if len(e.args) > 1 else "/entities"
        ))

    # ── Filter logic ──
    def apply_table_filters():
        search = (entity_search.value or "").lower()
        sev = sev_filter.value
        tag_val = tag_filter.value

        filtered = entity_data

        if search:
            filtered = [e for e in filtered if
                        search in e["code"].lower() or
                        search in e["name"].lower()]

        if sev == "Critical (HIGH)":
            filtered = [e for e in filtered if e["high"] > 0]
        elif sev == "Review (MEDIUM)":
            filtered = [e for e in filtered if e["medium"] > 0 and e["high"] == 0]
        elif sev == "Info (LOW)":
            filtered = [e for e in filtered if e["total"] > 0 and e["high"] == 0 and e["medium"] == 0]
        elif sev == "Clean":
            filtered = [e for e in filtered if e["total"] == 0]

        if tag_val != "All":
            tag_key = tag_val.replace(" ", "_")
            filtered = [e for e in filtered if tag_key in e["tags"]]

        table.rows = _build_table_rows(filtered)
        count_label.text = f"{len(filtered)} entities"
        table.update()

    entity_search.on("update:model-value", lambda: apply_table_filters())
    sev_filter.on("update:model-value", lambda: apply_table_filters())
    tag_filter.on("update:model-value", lambda: apply_table_filters())


def _build_table_rows(entity_data: list[dict]) -> list[dict]:
    """Build rows for the entity table."""
    rows = []
    for ent in entity_data:
        tags_str = "|".join(sorted(ent["tags"])) if ent["tags"] else ""
        rows.append({
            "code": ent["code"],
            "name": ent["name"][:50],
            "total": ent["total"],
            "high": ent["high"],
            "medium": ent["medium"],
            "low": ent["low"],
            "tags_str": tags_str,
        })
    return rows


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _build_entity_data(findings: list, s=None) -> list[dict]:
    """Aggregate findings by entity + enrich with classifier tags."""
    entities = {}
    for f in findings:
        key = f.entity_code
        if key not in entities:
            entities[key] = {
                "code": f.entity_code,
                "name": f.entity_name,
                "total": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "tags": set(),
            }
        ent = entities[key]
        ent["total"] += 1
        if f.severity == "HIGH":
            ent["high"] += 1
        elif f.severity == "MEDIUM":
            ent["medium"] += 1
        else:
            ent["low"] += 1

    # Enrich with EntityClassifier tags if parser is available
    classified_data = _get_classifier_tags(s)
    for code, data in classified_data.items():
        if code in entities:
            entities[code]["tags"] = data["tags"]
        else:
            entities[code] = {
                "code": code,
                "name": data["name"],
                "total": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "tags": data["tags"],
            }

    return sorted(entities.values(), key=lambda x: (-x["high"], -x["total"], x["code"]))


def _get_classifier_tags(s) -> dict[str, dict]:
    """Get classifier tags + name per entity (reference_id → {tags, name})."""
    if s is None or not hasattr(s, "parser") or s.parser is None:
        return {}
    try:
        from lab.core.entity_classifier import EntityClassifier
        classifier = EntityClassifier()
        classified = classifier.classify(s.parser)
        result = {}
        for ent in classified:
            result[ent.reference_id] = {
                "tags": set(ent.tags) if ent.tags else set(),
                "name": ent.entity_name or ent.reference_id,
            }
        return result
    except Exception:
        return {}


def _render_empty(t: dict):
    """Empty state — guides user to load data first."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("account_tree").classes("text-5xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label("No entities loaded").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(
            "Run a compliance review to explore findings per entity. "
            "Each entity card shows severity breakdown and links to detail."
        ).classes("text-sm text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-3 mt-2"):
            ui.button("Start Review", icon="play_circle",
                      on_click=lambda: ui.navigate.to("/review")) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")



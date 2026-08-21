"""Findings page — Full table with severity/category/entity filters + glass effects."""

from nicegui import ui

from lab.mythos_ui.theme import get_theme
from lab.mythos_ui.services.bridge import get_state

# Severity display mapping (data model stays HIGH/MEDIUM/LOW)
SEV_LABEL = {"HIGH": "CRITICAL", "MEDIUM": "REVIEW", "LOW": "INFO"}
SEV_COLOR = {"HIGH": "red", "MEDIUM": "amber", "LOW": "grey"}

# Check ID prefix tooltips
CHECK_TOOLTIPS = {
    "FLO": "Flow check — validates amounts flow correctly between schedules",
    "CMP": "Completeness — verifies all required fields are populated",
    "RSN": "Reasonableness — flags unusual values or outliers",
    "ROL": "Rollover — validates year-over-year continuity",
    "XSC": "Cross-schedule — checks consistency across schedules",
    "XFM": "Cross-form — validates data against other forms in the return",
    "BAL": "Balance — verifies totals, sums, and arithmetic",
    "SGN": "Sign — checks for incorrect sign conventions",
    "FX": "FX — validates currency conversion consistency",
}


def render():
    """Render the findings page content."""
    t = get_theme()
    s = get_state()

    if not s.report:
        _render_empty(t)
        return

    report = s.report
    findings = report.findings

    # ── Header (animated) ──
    with ui.row().classes("w-full items-center justify-between mb-4 animate-fade-up stagger-1"):
        with ui.column().classes("gap-1"):
            ui.label("Findings").classes("text-2xl font-bold") \
                .style(f"color: {t['text_primary']};")
            ui.label(f"{len(findings)} findings across {report.entity_count} entities") \
                .classes("text-sm").style(f"color: {t['text_secondary']};")

    # ── Filters Row (glass panel) — values restored from state ──
    fs = s.filters

    with ui.row().classes(
        "w-full gap-3 mb-4 items-end glass-panel animate-fade-up stagger-2"
    ).style(
        f"background: {t['glass_bg']}; "
        f"backdrop-filter: blur(12px); "
        f"border: 1px solid {t['glass_border']}; "
        f"border-radius: 12px; padding: 16px 20px;"
    ):
        severity_filter = ui.select(
            options={"All": "All", "HIGH": "CRITICAL", "MEDIUM": "REVIEW", "LOW": "INFO"},
            value=fs.severity,
            label="Severity",
        ).classes("w-36").props("dense outlined")

        categories = sorted(set(f.category for f in findings))
        category_filter = ui.select(
            options=["All"] + categories,
            value=fs.category if fs.category in (["All"] + categories) else "All",
            label="Category",
        ).classes("w-44").props("dense outlined")

        entities = sorted(set(f"{f.entity_code} — {f.entity_name[:20]}" for f in findings))
        entity_filter = ui.select(
            options=["All"] + entities,
            value=fs.entity if fs.entity in (["All"] + entities) else "All",
            label="Entity",
        ).classes("w-56").props("dense outlined")

        search_input = ui.input(placeholder="Search descriptions...",
                                value=fs.search) \
            .classes("flex-1").props("dense outlined clearable")

    # ── Stats Strip (clickable badges → apply filter) ──
    with ui.row().classes("w-full gap-3 mb-4 animate-fade-up stagger-3"):
        _clickable_badge(t, "CRITICAL", "error", report.summary["by_severity"]["HIGH"],
                         t["sev_high"], severity_filter, "HIGH", critical=True)
        _clickable_badge(t, "REVIEW", "warning", report.summary["by_severity"]["MEDIUM"],
                         t["sev_medium"], severity_filter, "MEDIUM")
        _clickable_badge(t, "INFO", "info", report.summary["by_severity"]["LOW"],
                         t["sev_low"], severity_filter, "LOW")
        # Total count + Export filtered
        with ui.row().classes("items-center gap-3 ml-auto"):
            ui.label("Showing:").classes("text-xs") \
                .style(f"color: {t['text_muted']};")
            count_label = ui.label(str(len(findings))).classes("text-xs font-bold mythos-mono") \
                .style(f"color: {t['text_primary']};")
            ui.button("Export filtered", icon="download",
                      on_click=lambda: _export_filtered(findings, severity_filter,
                                                        category_filter, entity_filter,
                                                        search_input)) \
                .props("flat dense size=sm") \
                .style(f"color: {t['accent']}; font-size: 0.7rem;")

    # ── Table (6 columns max + row expansion for details) ──
    columns = [
        {"name": "severity", "label": "Sev", "field": "severity", "align": "left", "sortable": True},
        {"name": "entity_code", "label": "Entity", "field": "entity_code", "align": "left", "sortable": True},
        {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True},
        {"name": "check_id", "label": "Check", "field": "check_id", "align": "left", "sortable": True},
        {"name": "description", "label": "Description", "field": "description", "align": "left"},
        {"name": "delta", "label": "Delta", "field": "delta", "align": "right", "sortable": True},
        {"name": "expand", "label": "", "field": "expand", "align": "center"},
    ]

    all_rows = _build_rows(findings)

    with ui.column().classes("w-full animate-fade-up stagger-4"):
        table = ui.table(
            columns=columns,
            rows=all_rows,
            row_key="id",
            pagination={"rowsPerPage": 25, "sortBy": "severity", "descending": True},
        ).classes("w-full").props("dense flat bordered separator=cell virtual-scroll")

        table.style(
            f"background: {t['glass_bg']}; "
            f"backdrop-filter: blur(10px); "
            f"-webkit-backdrop-filter: blur(10px); "
            f"border: 1px solid {t['glass_border']}; "
            f"border-radius: 12px; max-height: 60vh;"
        )

        # Header filter slots removed — filtering handled by Python selects above

        # Severity cell: icon + color + text (3 channels)
        table.add_slot("body-cell-severity", """
            <q-td :props="props">
                <div class="row items-center no-wrap gap-1">
                    <q-icon :name="props.row.severity === 'HIGH' ? 'error' :
                                   props.row.severity === 'MEDIUM' ? 'warning' : 'info'"
                            :color="props.row.severity === 'HIGH' ? 'red' :
                                    props.row.severity === 'MEDIUM' ? 'amber' : 'grey'"
                            size="xs" />
                    <q-badge :color="props.row.severity === 'HIGH' ? 'red' :
                                     props.row.severity === 'MEDIUM' ? 'amber' : 'grey'"
                             :label="props.row.severity === 'HIGH' ? 'CRITICAL' :
                                     props.row.severity === 'MEDIUM' ? 'REVIEW' : 'INFO'"
                             outline dense />
                </div>
            </q-td>
        """)

        # Category cell — styled badge
        table.add_slot("body-cell-category", """
            <q-td :props="props">
                <q-badge :color="props.row.category === 'flow' ? 'blue' :
                                  props.row.category === 'completeness' ? 'orange' :
                                  props.row.category === 'reasonableness' ? 'teal' :
                                  props.row.category === 'rollover' ? 'purple' :
                                  props.row.category === 'cross_schedule' ? 'indigo' :
                                  props.row.category === 'cross_form' ? 'cyan' : 'grey'"
                         :label="props.row.category"
                         dense outline
                         style="font-size: 0.6rem;" />
            </q-td>
        """)

        # Delta cell with sign coloring
        table.add_slot("body-cell-delta", """
            <q-td :props="props">
                <span :style="props.row.delta_raw > 0 ? 'color: #ef4444; font-weight: 600' :
                             props.row.delta_raw < 0 ? 'color: #22c55e; font-weight: 600' :
                             'color: inherit'">
                    {{ props.row.delta }}
                </span>
            </q-td>
        """)

        # Expand toggle button
        table.add_slot("body-cell-expand", """
            <q-td :props="props">
                <q-btn flat round dense size="xs"
                       :icon="props.expand ? 'expand_less' : 'expand_more'"
                       @click="props.expand = !props.expand" />
            </q-td>
        """)

        # Expanded row content (details panel)
        table.add_slot("body-cell-expand", """
            <q-td :props="props">
                <q-btn flat round dense size="xs"
                       :icon="props.expand ? 'expand_less' : 'expand_more'"
                       @click="props.expand = !props.expand" />
            </q-td>
        """)

        # Row expansion detail
        table.add_slot("item", """
            <q-tr :props="props">
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                    <template v-if="col.name === 'severity'">
                        <div class="row items-center no-wrap gap-1">
                            <q-icon :name="props.row.severity === 'HIGH' ? 'error' :
                                           props.row.severity === 'MEDIUM' ? 'warning' : 'info'"
                                    :color="props.row.severity === 'HIGH' ? 'red' :
                                            props.row.severity === 'MEDIUM' ? 'amber' : 'grey'"
                                    size="xs" />
                            <q-badge :color="props.row.severity === 'HIGH' ? 'red' :
                                             props.row.severity === 'MEDIUM' ? 'amber' : 'grey'"
                                     :label="props.row.severity === 'HIGH' ? 'CRITICAL' :
                                             props.row.severity === 'MEDIUM' ? 'REVIEW' : 'INFO'"
                                     outline dense />
                        </div>
                    </template>
                    <template v-else-if="col.name === 'delta'">
                        <span :style="props.row.delta_raw > 0 ? 'color: #ef4444; font-weight: 600' :
                                     props.row.delta_raw < 0 ? 'color: #22c55e; font-weight: 600' :
                                     'color: inherit'">
                            {{ props.row.delta }}
                        </span>
                    </template>
                    <template v-else-if="col.name === 'expand'">
                        <q-btn flat round dense size="xs"
                               :icon="props.expand ? 'expand_less' : 'expand_more'"
                               @click="props.expand = !props.expand" />
                    </template>
                    <template v-else-if="col.name === 'check_id'">
                        <span style="cursor: help;">{{ col.value }}
                            <q-tooltip>{{ props.row.check_tooltip }}</q-tooltip>
                        </span>
                    </template>
                    <template v-else>{{ col.value }}</template>
                </q-td>
            </q-tr>
            <q-tr v-show="props.expand" :props="props">
                <q-td colspan="100%" style="padding: 12px 24px; background: rgba(255,255,255,0.02);">
                    <div class="row q-gutter-md text-caption">
                        <div><strong>Category:</strong> {{ props.row.category }}</div>
                        <div><strong>Entity:</strong> {{ props.row.entity_name }}</div>
                        <div v-if="props.row.expected !== '—'"><strong>Expected:</strong> {{ props.row.expected }}</div>
                        <div v-if="props.row.actual !== '—'"><strong>Actual:</strong> {{ props.row.actual }}</div>
                        <div v-if="props.row.context"><strong>Context:</strong> {{ props.row.context }}</div>
                    </div>
                    <div class="text-caption q-mt-sm" style="opacity: 0.7;">
                        {{ props.row.full_description }}
                    </div>
                </q-td>
            </q-tr>
        """)

    # ── Filter logic (persists to state) ──
    def apply_filters():
        sev = severity_filter.value
        cat = category_filter.value
        ent = entity_filter.value
        search = (search_input.value or "").lower()

        # Persist to state so they survive navigation
        fs.severity = sev
        fs.category = cat
        fs.entity = ent
        fs.search = search_input.value or ""

        filtered = findings
        if sev != "All":
            filtered = [f for f in filtered if f.severity == sev]
        if cat != "All":
            filtered = [f for f in filtered if f.category == cat]
        if ent != "All":
            code = ent.split(" — ")[0]
            filtered = [f for f in filtered if f.entity_code == code]
        if search:
            filtered = [f for f in filtered if search in f.description.lower()
                        or search in f.entity_name.lower()
                        or search in f.check_id.lower()]

        table.rows = _build_rows(filtered)
        count_label.text = str(len(filtered))
        table.update()

    # Apply persisted filters on page load
    if fs.severity != "All" or fs.category != "All" or fs.entity != "All" or fs.search:
        apply_filters()

    severity_filter.on("update:model-value", lambda: apply_filters())
    category_filter.on("update:model-value", lambda: apply_filters())
    entity_filter.on("update:model-value", lambda: apply_filters())
    search_input.on("update:model-value", lambda: apply_filters())





# ─── HELPERS ────────────────────────────────────────────────────────────────

def _build_rows(findings: list) -> list[dict]:
    """Convert Finding objects to table row dicts (with expansion fields)."""
    rows = []
    for i, f in enumerate(findings):
        prefix = f.check_id.split("-")[0].split("_")[0][:3].upper()
        tooltip = CHECK_TOOLTIPS.get(prefix, f"Check type: {prefix}")
        rows.append({
            "id": f"{f.check_id}_{f.entity_code}_{i}",
            "severity": f.severity,
            "check_id": f.check_id,
            "check_tooltip": tooltip,
            "category": f.category,
            "entity_code": f.entity_code,
            "entity_name": f.entity_name,
            "description": f.description[:80] + ("..." if len(f.description) > 80 else ""),
            "full_description": f.description,
            "expected": f.expected or "—",
            "actual": f.actual or "—",
            "delta": f"${f.delta:,.0f}" if f.delta else "—",
            "delta_raw": f.delta or 0,
            "context": f.context or "",
        })
    return rows


def _clickable_badge(t: dict, label: str, icon: str, count: int, color: str,
                     severity_filter, filter_val: str, critical: bool = False):
    """Severity badge — click applies filter."""
    extra_cls = " glow-critical" if critical and count > 0 else ""
    with ui.row().classes(f"items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer{extra_cls}") \
            .style(f"background: {color}15; border: 1px solid {color}30;") \
            .on("click", lambda: _apply_sev_filter(severity_filter, filter_val)):
        ui.icon(icon).classes("text-xs").style(f"color: {color};")
        ui.label(label).classes("text-xs font-bold") \
            .style(f"color: {color};")
        ui.label(str(count)).classes("text-xs font-semibold mythos-mono") \
            .style(f"color: {t['text_primary']};")


def _apply_sev_filter(severity_filter, val: str):
    """Set severity filter and trigger update."""
    severity_filter.value = val
    severity_filter.update()


async def _export_filtered(all_findings, sev_filter, cat_filter, ent_filter, search_input):
    """Export only the currently filtered findings to Excel."""
    filtered = all_findings
    sev = sev_filter.value
    cat = cat_filter.value
    ent = ent_filter.value
    search = (search_input.value or "").lower()

    if sev != "All":
        filtered = [f for f in filtered if f.severity == sev]
    if cat != "All":
        filtered = [f for f in filtered if f.category == cat]
    if ent != "All":
        code = ent.split(" — ")[0]
        filtered = [f for f in filtered if f.entity_code == code]
    if search:
        filtered = [f for f in filtered if search in f.description.lower()
                    or search in f.entity_name.lower()
                    or search in f.check_id.lower()]

    if not filtered:
        ui.notify("No findings to export with current filters", type="warning")
        return

    import tempfile
    from pathlib import Path

    try:
        import pandas as pd
        df = pd.DataFrame([
            {
                "Severity": f.severity,
                "Check": f.check_id,
                "Category": f.category,
                "Entity Code": f.entity_code,
                "Entity Name": f.entity_name,
                "Description": f.description,
                "Expected": f.expected or "",
                "Actual": f.actual or "",
                "Delta": f.delta or 0,
            }
            for f in filtered
        ])
        out_path = Path(tempfile.gettempdir()) / "mythos_filtered_export.xlsx"
        df.to_excel(out_path, index=False, sheet_name="Filtered Findings")
        ui.notify(f"Exported {len(filtered)} findings → {out_path.name}", type="positive")
    except Exception as e:
        ui.notify(f"Export failed: {e}", type="negative")


def _render_empty(t: dict):
    """Empty state — guides user to run a review."""
    with ui.column().classes("w-full items-center justify-center py-16 gap-5 animate-fade-up"):
        ui.icon("search_off").classes("text-5xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.3;")
        ui.label("No findings to display").classes("text-lg font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(
            "Load an XML return and run a review to see compliance findings here."
        ).classes("text-sm text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

        with ui.row().classes("gap-3 mt-2"):
            ui.button("Start Review", icon="play_circle",
                      on_click=lambda: ui.navigate.to("/review")) \
                .props("unelevated no-caps") \
                .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                       f"padding: 8px 20px; border-radius: 6px; font-size: 0.8rem;")

        with ui.row().classes("gap-6 mt-6"):
            _step_hint(t, "1", "Load XML", "Upload your e-file XML")
            _step_hint(t, "2", "Run Review", "32 checks across 4 dimensions")
            _step_hint(t, "3", "Explore", "Filter, sort, and drill down")


def _step_hint(t: dict, num: str, title: str, desc: str):
    """Mini step indicator for empty state."""
    with ui.column().classes("items-center gap-1"):
        ui.badge(num, color="grey-8").props("rounded dense") \
            .style(f"background: {t['accent']}20; color: {t['accent']};")
        ui.label(title).classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(desc).classes("text-xs text-center") \
            .style(f"color: {t['text_muted']};")



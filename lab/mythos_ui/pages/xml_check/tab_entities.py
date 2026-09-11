"""Entities tab — classified entity list using EntityClassifier pipeline."""

from nicegui import ui

from lab.mythos_ui.components import TableFilterStrip
from lab.mythos_ui.services.bridge import get_state


def render_entities(t: dict, s):
    """Render the Entities tab."""
    if not s.parser:
        _render_empty(t)
        return

    # Use EntityClassifier for full entity data
    entities = _classify_entities(s)
    if not entities:
        _render_empty(t)
        return

    all_rows = _build_rows(entities)

    # ── Header + filters in one compact row ──
    strip = TableFilterStrip(
        filterable_columns={
            "country": "Country",
            "form_type": "Form",
            "currency": "FC",
        },
        all_rows=all_rows,
    )

    with ui.row().classes("items-center w-full mb-1").style("gap: 10px;"):
        ui.icon("account_tree").style(f"color: {t['accent']}; font-size: 0.9rem;")
        ui.label(f"Entities ({len(entities)})").classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")

        # Inline filters
        strip.render_inline(t)

        # Search pushed to far right
        search_input = ui.input(
            placeholder="Search entities...",
            value="",
        ).classes("w-44 ml-auto").props("dense outlined clearable debounce=400") \
            .style("font-size: 0.65rem;")

    # ── Entity table ──
    columns = [
        {"name": "ref_id", "label": "Ref ID", "field": "ref_id", "align": "left", "sortable": True},
        {"name": "locator", "label": "Locator", "field": "locator", "align": "center", "sortable": True},
        {"name": "name", "label": "Entity Name", "field": "name", "align": "left", "sortable": True},
        {"name": "country", "label": "Country", "field": "country", "align": "center", "sortable": True},
        {"name": "currency", "label": "FC", "field": "currency", "align": "center", "sortable": True},
        {"name": "form_type", "label": "Form", "field": "form_type", "align": "center", "sortable": True},
        {"name": "ownership", "label": "Voting %", "field": "ownership", "align": "center", "sortable": True},
        {"name": "tags", "label": "Tags", "field": "tags", "align": "left"},
    ]

    with ui.card().classes("w-full").style(
        f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
        f"border-radius: 10px; padding: 0; overflow: hidden;"
    ):
        table = ui.table(
            columns=columns, rows=strip.filtered_rows, row_key="_id",
            pagination={"rowsPerPage": 50},
        ).classes("w-full mythos-sticky-table").props("dense flat bordered separator=cell virtual-scroll")
        table.style(f"background: {t['bg_card']}; max-height: 60vh; font-size: 0.7rem;")

        # Bind filter strip to table
        strip.bind(table)

        # Custom form_type cell
        table.add_slot("body-cell-form_type", """
            <q-td :props="props">
                <q-badge :color="props.row.form_type.includes('5471') ? 'blue' :
                                 props.row.form_type.includes('8858') ? 'purple' : 'grey'"
                         :label="props.row.form_type" dense />
            </q-td>
        """)

        # Custom tags cell — modern pill design (Linear/Vercel style)
        table.add_slot("body-cell-tags", """
            <q-td :props="props">
                <div class="row items-center" style="gap: 4px; flex-wrap: wrap;" v-if="props.row.tags">
                    <span v-for="tag in props.row.tags.split('|')" :key="tag"
                        :style="{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            padding: '1px 7px',
                            borderRadius: '4px',
                            fontSize: '0.6rem',
                            fontWeight: '500',
                            letterSpacing: '0.01em',
                            lineHeight: '1.5',
                            background: tag.includes('tested_income') || tag.includes('has_qbai') ? 'rgba(48, 164, 108, 0.12)' :
                                        tag.includes('tested_loss') || tag.includes('negative_ep') ? 'rgba(229, 72, 77, 0.12)' :
                                        tag.includes('us_property') || tag.includes('income_blocked') ? 'rgba(229, 72, 77, 0.10)' :
                                        tag.includes('high_tax') ? 'rgba(255, 197, 61, 0.12)' :
                                        tag.includes('subpart_f') ? 'rgba(171, 74, 186, 0.12)' :
                                        tag.includes('full_inclusion') ? 'rgba(62, 99, 221, 0.12)' :
                                        tag.includes('interest_expense') ? 'rgba(255, 197, 61, 0.10)' :
                                        tag.includes('insurance') ? 'rgba(62, 99, 221, 0.10)' :
                                        tag.includes('dre') || tag.includes('fde') ? 'rgba(171, 74, 186, 0.10)' :
                                        tag.includes('de_minimis') ? 'rgba(62, 99, 221, 0.08)' :
                                        tag.includes('dormant') ? 'rgba(105, 110, 119, 0.12)' :
                                        'rgba(105, 110, 119, 0.08)',
                            border: '1px solid ' + (
                                        tag.includes('tested_income') || tag.includes('has_qbai') ? 'rgba(48, 164, 108, 0.25)' :
                                        tag.includes('tested_loss') || tag.includes('negative_ep') ? 'rgba(229, 72, 77, 0.25)' :
                                        tag.includes('us_property') || tag.includes('income_blocked') ? 'rgba(229, 72, 77, 0.20)' :
                                        tag.includes('high_tax') ? 'rgba(255, 197, 61, 0.25)' :
                                        tag.includes('subpart_f') ? 'rgba(171, 74, 186, 0.25)' :
                                        tag.includes('full_inclusion') ? 'rgba(62, 99, 221, 0.25)' :
                                        tag.includes('interest_expense') ? 'rgba(255, 197, 61, 0.20)' :
                                        tag.includes('insurance') ? 'rgba(62, 99, 221, 0.20)' :
                                        tag.includes('dre') || tag.includes('fde') ? 'rgba(171, 74, 186, 0.20)' :
                                        tag.includes('de_minimis') ? 'rgba(62, 99, 221, 0.15)' :
                                        tag.includes('dormant') ? 'rgba(105, 110, 119, 0.20)' :
                                        'rgba(105, 110, 119, 0.15)'),
                            color: tag.includes('tested_income') || tag.includes('has_qbai') ? '#30a46c' :
                                   tag.includes('tested_loss') || tag.includes('negative_ep') ? '#e5484d' :
                                   tag.includes('us_property') || tag.includes('income_blocked') ? '#e5484d' :
                                   tag.includes('high_tax') || tag.includes('interest_expense') ? '#ffc53d' :
                                   tag.includes('subpart_f') ? '#ab4aba' :
                                   tag.includes('full_inclusion') || tag.includes('insurance') || tag.includes('de_minimis') ? '#3e63dd' :
                                   tag.includes('dre') || tag.includes('fde') ? '#ab4aba' :
                                   tag.includes('dormant') ? '#696e77' :
                                   '#b0b4ba'
                        }">
                        <span :style="{
                            width: '5px', height: '5px', borderRadius: '50%', flexShrink: 0,
                            background: tag.includes('tested_income') || tag.includes('has_qbai') ? '#30a46c' :
                                        tag.includes('tested_loss') || tag.includes('negative_ep') ? '#e5484d' :
                                        tag.includes('us_property') || tag.includes('income_blocked') ? '#e5484d' :
                                        tag.includes('high_tax') || tag.includes('interest_expense') ? '#ffc53d' :
                                        tag.includes('subpart_f') ? '#ab4aba' :
                                        tag.includes('full_inclusion') || tag.includes('insurance') || tag.includes('de_minimis') ? '#3e63dd' :
                                        tag.includes('dre') || tag.includes('fde') ? '#ab4aba' :
                                        tag.includes('dormant') ? '#696e77' :
                                        '#696e77'
                        }"></span>
                        {{ tag === 'negative_ep' ? 'Neg E&P' :
                           tag === 'tested_income' ? 'Tested Inc' :
                           tag === 'tested_loss' ? 'Tested Loss' :
                           tag === 'full_inclusion' ? '100%' :
                           tag === 'high_tax_exclusion' ? 'HTE' :
                           tag === 'has_qbai' ? 'QBAI' :
                           tag === 'interest_expense' ? 'Int Exp' :
                           tag === 'subpart_f' ? 'Sub F' :
                           tag === 'de_minimis' ? 'De Min' :
                           tag === 'sec_245a' ? '245A' :
                           tag === 'sec_956' ? '956' :
                           tag === 'us_property' ? 'US Prop' :
                           tag === 'income_blocked' ? 'Blocked' :
                           tag.replace(/_/g, ' ') }}
                    </span>
                </div>
                <span v-else style="color: #696e77; font-size: 0.6rem;">—</span>
            </q-td>
        """)

        # Row click
        table.on("row-click", lambda e: _navigate_to_entity(
            e.args[1].get("ref_id", "") if len(e.args) > 1 else ""
        ))

    # ── Search logic (debounced, no DOM rebuild) ──
    def _on_search(e):
        q = (e.args if isinstance(e.args, str) else (e.args or "")).lower() if hasattr(e, "args") else ""
        if q:
            filtered = [r for r in strip.filtered_rows if
                        q in r["name"].lower() or
                        q in r["ref_id"].lower() or
                        q in r["country"].lower() or
                        q in r["currency"].lower() or
                        q in r["tags"].lower()]
        else:
            filtered = strip.filtered_rows
        table.rows = filtered
        table.update()

    search_input.on("update:model-value", _on_search)

    # ── Stats footer ──
    by_form = {}
    for e in entities:
        ft = getattr(e, "form_type", "5471")
        by_form[ft] = by_form.get(ft, 0) + 1

    with ui.row().classes("items-center gap-4 mt-2"):
        ui.label(f"{len(entities)} entities").classes("text-xs mythos-mono") \
            .style(f"color: {t['text_primary']};")
        for ft, cnt in sorted(by_form.items()):
            ui.label(f"{cnt} {ft}").classes("text-xs mythos-mono") \
                .style(f"color: {t['text_muted']};")


# ─── HELPERS ────────────────────────────────────────────────────────────────

def _build_rows(entities: list) -> list[dict]:
    """Build table row dicts from classified entities."""
    rows = []
    for i, ent in enumerate(entities):
        form_type = getattr(ent, "form_type", None) or _determine_form_type(ent)
        ownership = f"{ent.voting_stock_pct * 100:.1f}%" if ent.voting_stock_pct else "—"
        cat_str = ", ".join(ent.category_filers) if ent.category_filers else "—"

        if ent.dormant:
            status = "Dormant"
        elif ent.is_dre:
            status = "DRE"
        elif ent.is_insurance:
            status = "Insurance"
        else:
            status = "Active"

        visible_tags = {t for t in ent.tags if t != "full_inclusion"} if ent.tags else set()
        tag_str = "|".join(sorted(visible_tags)) if visible_tags else ""

        locator = getattr(ent, "oit_locator", "") or "—"

        score = getattr(ent, "completeness_score", 0.0)
        completeness_str = f"{score:.0%}" if score is not None else "—"

        rows.append({
            "_id": i,
            "ref_id": ent.reference_id,
            "locator": locator,
            "name": ent.entity_name[:45],
            "country": ent.country_code or "—",
            "currency": ent.functional_currency or "—",
            "form_type": form_type,
            "category": cat_str,
            "ownership": ownership,
            "completeness": completeness_str,
            "status": status,
            "tags": tag_str,
        })
    return rows


def _classify_entities(s) -> list:
    """Run EntityClassifier on the parsed data. Cache invalidates when parser changes."""
    cached = getattr(s, "_classified_entities", None)
    cached_path = getattr(s, "_classified_entities_path", None)
    current_path = str(getattr(s.parser, "path", None))

    if cached and cached_path == current_path:
        return cached

    try:
        from lab.core.entity_classifier import EntityClassifier, ClassifiedEntity
        from lab.core.entity_registry import EntityRegistry

        registry = EntityRegistry()
        registry.populate_from_parser(s.parser)

        classifier = EntityClassifier(registry=registry)
        entities = classifier.classify(s.parser)

        s._classified_entities = entities
        s._classified_entities_path = str(getattr(s.parser, "path", None))
        return entities
    except Exception:
        return []


def _determine_form_type(ent) -> str:
    """Determine primary form type from classified entity data."""
    has_5471 = bool(ent.sch_c or ent.sch_h or ent.sch_i or ent.sch_j or ent.sch_e)
    is_8858 = ent.is_dre or "fde_8858" in ent.tags

    if has_5471 and is_8858:
        return "5471 / 8858"
    elif is_8858:
        return "8858"
    else:
        return "5471"


def _render_empty(t: dict):
    with ui.column().classes("w-full items-center py-12 gap-3"):
        ui.icon("account_tree").classes("text-4xl") \
            .style(f"color: {t['text_muted']}; opacity: 0.4;")
        ui.label("No entity data available").classes("text-sm") \
            .style(f"color: {t['text_muted']};")


def _navigate_to_entity(ref_id: str):
    if not ref_id:
        return
    s = get_state()
    s.xml_check.selected_entity = ref_id
    s.xml_check.active_tab = "parsed_data"
    ui.navigate.to("/review")

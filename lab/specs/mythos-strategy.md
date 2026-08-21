# Mythos — Estrategia de Desarrollo Completa

> De herramienta CLI a plataforma desktop/web de compliance review para US int'l tax.
> Estado actual: **v0.7.2** | 47+ checks | 5471+8858 | NiceGUI desktop app | 80+ tests

---

## 1. Diagnóstico: Dónde Estamos

### Inventario de Activos Construidos

| Capa | Componentes | Estado |
|------|------------|--------|
| **Parser** | EFileParser (5471, 8858), extract_form(), to_dataframe(), detect_forms() | ✅ Completo |
| **Engine** | ReviewEngine (5471+8858), 6 check categories, CheckContext DI | ✅ Completo |
| **Checks** | 32 FLO/CMP/RSN/ROL + 9 XSC + 3 XFM = **44 checks** | ✅ Completo |
| **Reports** | 7 report types (rollover, movement, entity_changes), pure functions | ✅ Completo |
| **Export** | Excel, PDF, HTML, CSV — DesignSystem tokens | ✅ Completo |
| **Service** | MythosService + typed results + progress callback | ✅ Completo |
| **CLI** | Click: list, parse, compare, review, check, reconcile, dashboard | ✅ Completo |
| **UI Desktop** | NiceGUI frameless window, 9 pages, sidebar, theme system | ✅ 80% |
| **PDF Validator** | 12 schedules (A, B, C, E, F, G, H, I, I-1, J, P, R) | ✅ Completo |
| **Reconciler** | XML vs Workbook (openpyxl), tolerance-based matching | ✅ Completo |
| **Core** | Config (env-aware), exceptions, structured logging, models | ✅ Completo |
| **Tests** | 80+ unit/integration tests, fixtures for 5471 + 8858 + mixed | ✅ Completo |

### Cobertura de Formularios

| Form | Schedule | Parser | Checks | PDF Validator | Rollover |
|------|----------|--------|--------|---------------|----------|
| 5471 | Page 1, A, B | ✅ | ✅ (ROL-008) | ✅ | ✅ |
| 5471 | C (Income) | ✅ | ✅ (FLO-001,006) | ✅ | ❌ |
| 5471 | E (Taxes) | ✅ | ✅ (FLO-004,005) | ✅ | ❌ |
| 5471 | F (Balance Sheet) | ✅ | ✅ (FLO-007,008, ROL-001) | ✅ | ✅ |
| 5471 | G (Other Info) | ✅ | ✅ (ROL-009) | ✅ | ❌ |
| 5471 | H (E&P) | ✅ | ✅ (FLO-002, CMP-001,005) | ✅ | ❌ |
| 5471 | I (SubF) | ✅ | ✅ (XSC-008) | ✅ | ❌ |
| 5471 | I-1 (GILTI) | ✅ | ✅ (FLO-003,005) | ✅ | ❌ |
| 5471 | J (E&P Pools) | ✅ | ✅ (ROL-007, XSC-006,007) | ✅ | ✅ |
| 5471 | P (PTEP) | ✅ | ✅ (XSC-006,007) | ✅ | ❌ |
| 5471 | Q (CFC Income) | ✅ | ✅ (XSC-001 to 005) | ❌ | ❌ |
| 5471 | R (Distributions) | ✅ | ❌ | ✅ | ❌ |
| 8858 | Main + SchM | ✅ | ✅ (4 categories) | ❌ | ✅ |
| 8990 | Top-level | ✅ | ✅ (XFM-001 to 003) | ❌ | ❌ |

### Gaps Identificados (Priority-ordered)

1. **Packaging** — No `pip install` funcional, no CI, no `.exe` distribuible
2. **Entity Tagger** — Spec escrito, no implementado aún
3. **Dashboard UX** — 80% funcional, falta entity detail polish, graph viz
4. **Schedule M/Q PDF Validator** — Últimos schedules no cubiertos
5. **Ownership Graph** — networkx engine diseñado pero no implementado
6. **Multi-year** — Solo PY/CY hoy, no 3+ years trending
7. **Error Architecture** — `lab/core/errors.py` creado, no integrado aún

---

## 2. Visión: Adónde Vamos

### Producto Final (v1.0)

```
┌──────────────────────────────────────────────────────────────────┐
│                    MYTHOS COMPLIANCE PLATFORM                      │
│                                                                    │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │
│   │   CLI    │   │ Desktop  │   │   Web    │   │   API    │    │
│   │  (rich)  │   │(NiceGUI) │   │(NiceGUI) │   │  (REST)  │    │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘    │
│        │               │               │               │          │
│        └───────────────┴───────┬───────┴───────────────┘          │
│                                │                                   │
│                    ┌───────────▼──────────┐                       │
│                    │    MythosService     │ ← Single entry point   │
│                    └───────────┬──────────┘                       │
│             ┌─────────┬───────┼───────┬─────────┐                │
│             ▼         ▼       ▼       ▼         ▼                │
│        ┌─────────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌───────┐           │
│        │ Review  │ │Tags │ │Recon│ │Graph│ │Reports│           │
│        │ Engine  │ │     │ │     │ │     │ │       │           │
│        └────┬────┘ └──┬──┘ └──┬──┘ └──┬──┘ └───┬───┘           │
│             │         │       │       │         │                │
│             └─────────┴───────┴───────┴─────────┘                │
│                                │                                   │
│                    ┌───────────▼──────────┐                       │
│                    │  Core (models, cfg)  │                       │
│                    └─────────────────────┘                        │
└──────────────────────────────────────────────────────────────────┘
```

### Diferenciadores (v1.0 vs competitors)

| Feature | Bolt/Alteryx | OIT Diagnostics | Mythos v1.0 |
|---------|-------------|-----------------|-------------|
| Speed | 5-10 min | Real-time | < 3 sec |
| License cost | $5K+/yr | Included (limited) | $0 |
| Review automation | None | Format-only | 44+ substantive checks |
| Entity classification | Manual | None | Auto-tagged (16 tags) |
| Ownership graph | None | None | Interactive viz |
| Multi-form (5471+8858) | One at a time | Separate | Unified composite |
| Distribution | Desktop only | SaaS | Desktop + Web + CLI |
| Audit trail | None | Basic | Full (finding → check → evidence) |
| PDF cross-check | None | None | 12 schedules validated |

---

## 3. Roadmap por Fases

### Phase 7: Entity Tagger + Error Architecture ← NEXT

**Duración estimada:** 2-3 sessions

**Deliverables:**
- [ ] `lab/core/entity_tagger.py` — Motor principal (EntityTagger, EntityData, TagResult)
- [ ] `lab/core/tagging_rules.py` — 16 tag rules (v1)
- [ ] `lab/tests/test_entity_tagger.py` — Unit tests (32+ tests)
- [ ] Integrar `lab/core/errors.py` en parser y reconciler (try/except → typed errors)
- [ ] `MythosService.tag_entities()` — nuevo endpoint en service layer
- [ ] CLI: `mythos tag <file.xml>` — terminal output con tags por entidad
- [ ] Dashboard: Entity list con badges de tags

**Spec completo:** `lab/specs/entity-tagger.md`

**Key decisions:**
- Tags son determinísticos (reglas puras, no ML)
- EntityData se construye desde EFileParser output (adapter pattern)
- Contradictions se surfacean como LOW severity findings
- Tagger es *read-only* — no modifica datos, solo clasifica

### Phase 8: Packaging + Distribution

**Duración estimada:** 1-2 sessions

**Deliverables:**
- [ ] `pyproject.toml` completar con build-system, classifiers
- [ ] `python -m mythos` entry point funcional
- [ ] Remove todos los `sys.path.insert(0, ...)` hacks
- [ ] `lab/__init__.py` + proper package structure
- [ ] GitHub Actions workflow: lint (ruff) + test (pytest) on push
- [ ] PyInstaller/Nuitka spec → `mythos.exe` (one-file, portable)
- [ ] `nsis` or `wix` installer para Windows (optional)
- [ ] Version pinning en requirements.txt (lock file)
- [ ] `.env.example` con MYTHOS_* variables documentadas

**Verification:**
```bash
pip install -e .                     # dev install
mythos review cy.xml py.xml          # CLI works
python -m mythos.ui                  # desktop launches
pytest --tb=short                    # all green
./dist/mythos.exe review cy.xml      # standalone binary
```

### Phase 9: Ownership Graph + Aggregation Checks

**Duración estimada:** 2 sessions

**Deliverables:**
- [ ] `lab/xml_parser/engine/ownership_graph.py` — networkx DAG from Sch G ownership %
- [ ] Parse: `VotingStockOwnedUSPrsnPct`, `VotingStockOwnedFrgnEntPct`, parent codes
- [ ] Graph operations: `is_leaf()`, `get_chain()`, `effective_ownership()`, `tiered_entities()`
- [ ] AGG-001 to AGG-008 checks:
  - AGG-001: Orphan entity (no parent link)
  - AGG-002: Circular ownership detected
  - AGG-003: Ownership sum > 100%
  - AGG-004: Tested income entity has parent with tested loss (partial offset risk)
  - AGG-005: DRE owner missing from return
  - AGG-006: Tiered CFC without full chain in return
  - AGG-007: 10%+ US shareholder not filing
  - AGG-008: Insurance entity not flagged
- [ ] Dashboard: Interactive graph visualization (Plotly network graph or vis.js)
- [ ] `MythosService.ownership_graph()` → returns graph data
- [ ] Tests against flat structure and tiered structure returns

### Phase 10: Dashboard Polish + Multi-Year

**Duración estimada:** 2-3 sessions

**Deliverables:**
- [ ] Entity detail page complete (all schedules, tags, findings, ownership chain)
- [ ] Multi-year trending (3+ years comparison)
  - Upload N XMLs → automatic year detection
  - E&P trend chart per entity
  - Finding trend (improved/degraded/new)
- [ ] Comparative view: side-by-side two returns
- [ ] Search/filter: by entity, tag, severity, schedule
- [ ] Keyboard shortcuts for power users (already wired via shortcuts.py)
- [ ] Dark/light theme persistence (already works)
- [ ] Print-friendly PDF export directly from dashboard
- [ ] Session history (persist reviews, reload without re-running)
- [ ] Performance: lazy-load schedule data, virtualized tables for 200+ entities

### Phase 11: Advanced Features (v1.1+)

**Duración estimada:** Ongoing

**Deliverables:**
- [ ] **Form 8865** — Partnership return (similar structure to 5471)
- [ ] **Form 5713** — International boycott factor
- [ ] **Pillar Two integration** — GloBE calculations cross-check
- [ ] **User-defined rules** — JSON DSL for custom checks (like competitor tool)
- [ ] **API server** — FastAPI REST layer for team-wide access
- [ ] **WebSocket progress** — Real-time review progress from server
- [ ] **Diff engine** — Two-return visual diff (field-by-field, colored delta)
- [ ] **Batch mode** — Process N returns in parallel, aggregate dashboard
- [ ] **RAG integration** — Query wiki/IRC for check context (from lab/RAG.md)

---

## 4. Arquitectura de Calidad

### Testing Strategy

```
Unit Tests (fast, isolated)              → 90% of test volume
├── test_entity_tagger.py               (32+ tests — rules, contradictions, tolerance)
├── test_review_engine.py               (25 tests — baseline regression)
├── test_service.py                     (9 tests — service layer)
├── test_reports_export.py              (13 tests — smoke tests all formats)
├── test_pdf_validator.py               (50+ tests — layout regex + reconciliation)
├── test_8858.py                        (15+ tests — 8858 checks)
├── test_parser_unit.py                 (parser edge cases)
├── test_filters.py                     (entity filtering)
└── test_reconciler.py                  (workbook vs XML)

Integration Tests (slower, real XML)     → 10% of test volume
├── test_integration_pipeline.py        (end-to-end: XML → review → export)
└── test_export_content.py              (export format validation)

Fixtures
├── sample_cy.xml / sample_py.xml       (5 entities, triggers 14 findings)
├── sample_8858_cy/py.xml               (FDE/FB entities)
└── sample_mixed_cy/py.xml              (5471 + 8858 combined)
```

**Baseline inmutable:** 14 findings (7 HIGH, 7 MEDIUM) — any deviation = regression.

### Error Handling Strategy

```python
# Architecture layers:
#
# Presentation (CLI/Dashboard)     → catch CerebroError, show user_message
# Service (MythosService)          → catch CerebroError, wrap in Result types
# Engine (ReviewEngine/Tagger)     → raise specific errors OR log + continue
# Parser (EFileParser)             → raise ParseError subtypes
# Core (models)                    → never raises (pure data)

# Pattern for checks (fault-tolerant):
def _check_something(ctx: CheckContext, ...):
    """Checks continue on individual failures — never halt the batch."""
    try:
        value = safe_float(row, "SomeField")
        # ... check logic ...
    except Exception:
        # Individual check failure → skip this entity, continue batch
        pass

# Pattern for parser (fail-fast):
def extract_form(self, form_name: str) -> pd.DataFrame:
    """Parser failures halt the operation — data must be trustworthy."""
    try:
        # ... XML parsing ...
    except lxml.etree.XMLSyntaxError as e:
        raise XMLParseError(f"Malformed XML in {form_name}", cause=e,
                           context=ErrorContext(source_file=str(self.path)))
```

### Performance Targets

| Operation | Target | Method |
|-----------|--------|--------|
| Parse 200 entities | < 2 sec | lxml C-extension, selective extraction |
| Review 200 entities | < 5 sec | No redundant parsing, O(n) checks |
| Export Excel | < 3 sec | xlsxwriter streaming (not openpyxl) |
| Export PDF | < 5 sec | xhtml2pdf single-pass |
| Dashboard load | < 1 sec | Pre-computed state, lazy tabs |
| PDF Validator | < 10 sec/file | pdfplumber page-by-page |

---

## 5. Stack Tecnológico

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.11+ | Team familiarity, data ecosystem |
| XML | lxml | C-speed, correct namespace handling |
| Data | pandas | Natural for tabular checks |
| CLI | Click + Rich | Color output, progress bars, help text |
| Desktop | NiceGUI + pywebview | Python-native, Quasar components, dark mode |
| Graphs | networkx | In-memory DAG, no server needed |
| Charting | Plotly | Interactive, supports network graphs |
| Testing | pytest | Standard, fast, fixture system |
| Linting | ruff | Fast, all-in-one |
| Build | PyInstaller | Single .exe for Windows distribution |
| CI | GitHub Actions | Free for org repos |

### Dependencies (locked)

```
# Core (required)
pandas>=2.0
lxml>=5.0
openpyxl>=3.1          # workbook reading
xlsxwriter>=3.2        # Excel export (write-only, fast)
click>=8.0             # CLI framework
rich>=13.0             # Terminal formatting

# UI (required for dashboard)
nicegui>=1.4           # Web/Desktop framework
plotly>=5.18           # Charts
pywebview>=5.0         # Native window (desktop mode)

# Export (optional, degrades gracefully)
reportlab>=4.0         # PDF generation
weasyprint>=60.0       # Alternative PDF (better CSS support)

# Analysis (future)
networkx>=3.0          # Ownership graph (Phase 9)
pdfplumber>=0.10       # PDF Validator

# Dev
pytest>=7.0
pytest-cov>=4.0
ruff>=0.4
pyinstaller>=6.0
```

---

## 6. Distribución

### Target Users

| Tier | User | Interface | Distribution |
|------|------|-----------|-------------|
| 1 | QST Mexico team (5 people) | Desktop app | Shared drive `.exe` |
| 2 | US int'l compliance associates | Web dashboard | Internal server |
| 3 | Managers/partners | Export reports | Email/SharePoint |
| 4 | Other PwC offices | CLI + API | Git clone + pip install |

### Distribution Channels

```
Channel 1: Portable .exe (PyInstaller)
├── mythos.exe                   # Self-contained, no Python needed
├── sources/                     # User drops XML here
└── output/                      # Reports appear here

Channel 2: pip install (dev/power users)
├── pip install -e .             # From git clone
├── mythos review cy.xml py.xml  # CLI available globally
└── python -m mythos.ui          # Dashboard

Channel 3: Web server (team access)
├── python lab/mythos_ui/main.py --web --port 8080
└── http://server:8080/          # Anyone with network access
```

---

## 7. Métricas de Éxito

### Calidad del Motor

| Metric | Target | Measured By |
|--------|--------|-------------|
| True Positive Rate | > 80% | Validated against manual review of N clients |
| False Positive Rate | < 15% | Findings reviewed by senior → marked "not actionable" |
| Check coverage | 50+ checks | Count of distinct check IDs |
| Schedule coverage | 100% of filed schedules | Every schedule in return gets at least 1 check |
| Form coverage | 5471 + 8858 + 8990 | detect_forms() list |

### Operacional

| Metric | Target | Measured By |
|--------|--------|-------------|
| Time saved per return | 4+ hours | vs manual Excel review (baseline: 4-8 hrs) |
| First-run success | > 95% | XML → report without errors |
| Adoption | 5+ users | Active users in QST team |
| Defect rate | 0 regressions per release | Baseline test suite |

### UX

| Metric | Target | Measured By |
|--------|--------|-------------|
| Time to first insight | < 30 sec | Upload → see findings |
| Click depth to detail | ≤ 2 clicks | From dashboard → specific finding |
| Export quality | "Client-ready" | Manager can send report without edits |

---

## 8. Riesgos y Mitigaciones

| Risk | Impact | Mitigation |
|------|--------|-----------|
| IRS XML schema change | Parser breaks | Pin to known schema version; namespace-aware selectors |
| ONESOURCE version bump | Workbook reader fails | Column detection by header text, not position |
| Python blocked by IT | Can't install | PyInstaller standalone; no admin needed |
| networkx heavy for .exe | 50MB+ binary | Use lightweight graph (dict-of-dicts) if needed |
| NiceGUI breaking change | UI breaks | Pin version; dashboard is separate from engine |
| Team adoption low | Wasted effort | Demo to team early; gather feedback before Phase 10 |

---

## 9. Plan de Ejecución Inmediato

### Next 3 Sessions (Priority Order)

**Session A: Entity Tagger**
```
1. Implement lab/core/entity_tagger.py (EntityTagger, EntityData)
2. Implement lab/core/tagging_rules.py (16 rules)
3. Write lab/tests/test_entity_tagger.py (32+ tests)
4. Add MythosService.tag_entities() endpoint
5. Add CLI command: mythos tag <file.xml>
6. Run full test suite — confirm 0 regressions
```

**Session B: Packaging**
```
1. Fix all sys.path hacks
2. Complete pyproject.toml (build-system, entry points)
3. pip install -e . → verify CLI + UI work
4. PyInstaller spec → build .exe
5. Test .exe on clean machine (no Python)
6. GitHub Actions: ruff + pytest on push
```

**Session C: Ownership Graph**
```
1. Parse Sch G ownership fields from XML
2. Build networkx DAG per return
3. Implement AGG-001 to AGG-008
4. Add graph visualization to dashboard
5. Test against 2+ real returns (flat and tiered structures)
```

---

## 10. Criterios de Versión

| Version | Gate Criteria |
|---------|--------------|
| **v0.8** | Entity Tagger functional + packaging complete |
| **v0.9** | Ownership graph + AGG checks + dashboard polish |
| **v1.0** | Multi-year + batch mode + team validated (5+ users) + .exe stable |
| **v1.1** | Form 8865 + user rules DSL + API server |
| **v1.2** | Pillar Two integration + RAG context |

---

## Apéndice A: File Tree (Complete as of v0.7.2)

```
lab/
├── pyproject.toml
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── errors.py                    # Structured error hierarchy (NEW)
│   ├── entity_registry.py           # Entity metadata store
│   ├── fx_rates.py                  # FX rate utilities
│   ├── oit_parser.py                # OIT data parsing
│   └── xlsx_reader.py               # Generic Excel reader
├── xml_parser/
│   ├── __init__.py                  # Package entry + public API
│   ├── __main__.py                  # python -m lab.xml_parser
│   ├── cli.py                       # Click CLI
│   ├── parser.py                    # EFileParser
│   ├── models.py                    # ParsedReturn, SubsidiaryReturn
│   ├── comparator.py                # XMLComparator (PY vs CY)
│   ├── reconciler.py                # Workbook vs XML
│   ├── workbook_reader.py           # openpyxl reader
│   ├── field_maps.py                # Schedule field definitions
│   ├── review_engine.py             # Thin orchestrator
│   ├── output.py                    # [LEGACY] PwC orange Excel
│   ├── gt_output.py                 # [SHIM] → export/html
│   ├── dashboard.py                 # [LEGACY] NiceGUI original
│   ├── dashboard_st.py              # [LEGACY] Streamlit
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py                # Finding, ReviewReport, RolloverReport
│   │   ├── config.py                # MythosConfig (env-aware)
│   │   ├── constants.py             # EXPECTED_FX_RANGES
│   │   ├── exceptions.py            # ParseError, ValidationError
│   │   ├── filters.py               # Entity filtering logic
│   │   └── logging.py               # Structured logging
│   ├── engine/
│   │   ├── __init__.py
│   │   └── checks/
│   │       ├── __init__.py          # ALL_CHECKS registry
│   │       ├── _helpers.py          # CheckContext, safe_float
│   │       ├── flow.py              # FLO-001 to FLO-020
│   │       ├── completeness.py      # CMP-001 to CMP-006
│   │       ├── reasonableness.py    # RSN-001 to RSN-007
│   │       ├── rollover.py          # ROL-001 to ROL-011
│   │       ├── cross_schedule.py    # XSC-001 to XSC-009
│   │       ├── cross_form.py        # XFM-001 to XFM-003
│   │       ├── completeness_8858.py # 8858 completeness
│   │       ├── flow_8858.py         # 8858 flow
│   │       ├── reasonableness_8858.py
│   │       └── rollover_8858.py
│   ├── reports/
│   │   ├── __init__.py              # run_all_reports(), ReportEngine
│   │   ├── rollover.py              # sch_f, page1, sch_j rollover
│   │   ├── movement.py              # ep_movement, gilti_comparison
│   │   ├── entity_changes.py        # new/final entities, sch_g changes
│   │   ├── cross_schedule.py        # Cross-schedule reports
│   │   └── reports_8858.py          # 8858-specific reports
│   ├── export/
│   │   ├── __init__.py
│   │   ├── design_system.py         # DesignSystem (navy/copper palette)
│   │   ├── excel_exporter.py        # xlsxwriter corporate workbook
│   │   ├── pdf_exporter.py          # WeasyPrint/xhtml2pdf PDF
│   │   ├── html_exporter.py         # Great Tables HTML
│   │   └── csv_exporter.py          # Flat CSV
│   └── api/
│       ├── __init__.py
│       └── service.py               # MythosService
├── pdf_validator/
│   ├── config.py
│   ├── models.py
│   ├── report.py
│   ├── extractor.py                 # PDF → structured data (12 schedules)
│   ├── reconciler.py                # PDF vs XML comparison
│   ├── validator.py                 # Full validation orchestrator
│   ├── run_validation.py            # CLI + demo modes
│   └── layouts/
│       ├── __init__.py
│       ├── page1_schedule_a.py
│       ├── schedule_b.py
│       ├── schedule_c.py
│       ├── schedule_e.py
│       ├── schedule_f.py
│       ├── schedule_g.py
│       ├── schedule_h.py
│       ├── schedule_i.py
│       ├── schedule_i1.py
│       ├── schedule_j.py
│       ├── schedule_p.py
│       └── schedule_r.py
├── mythos_ui/
│   ├── __init__.py
│   ├── __main__.py
│   ├── main.py                      # Entry point (native + web)
│   ├── layout.py                    # Shell: header, sidebar, content
│   ├── theme.py                     # Dark/light token system
│   ├── components.py                # Reusable UI components
│   ├── shortcuts.py                 # Keyboard shortcuts
│   ├── services/
│   │   ├── __init__.py
│   │   ├── bridge.py                # Service bridge (state management)
│   │   ├── parse_service.py         # Parse operations
│   │   └── xml_check_state.py       # XML check page state
│   └── pages/
│       ├── __init__.py
│       ├── dashboard.py             # Home/overview
│       ├── dashboard_data.py        # Dashboard data layer
│       ├── about.py
│       ├── entities.py
│       ├── entity_detail.py
│       ├── findings.py
│       ├── history.py
│       ├── pdf_check.py
│       ├── reconciliation.py
│       ├── rollover.py
│       └── xml_check/               # Multi-tab XML review page
│           ├── __init__.py
│           ├── page.py
│           ├── upload_panel.py
│           ├── processing_panel.py
│           ├── toolbar.py
│           ├── export_dialog.py
│           ├── tab_overview.py
│           ├── tab_issues.py
│           ├── tab_entities.py
│           ├── tab_schedules.py
│           ├── tab_rollover.py
│           ├── tab_parsed_data.py
│           └── tab_forms.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_review_engine.py        # 25 baseline tests
│   ├── test_service.py              # 9 service tests
│   ├── test_reports_export.py       # 13 smoke tests
│   ├── test_pdf_validator.py        # 50+ tests
│   ├── test_8858.py                 # 8858 checks
│   ├── test_parser_unit.py          # Parser unit tests
│   ├── test_export_content.py       # Export content verification
│   ├── test_integration_pipeline.py # End-to-end
│   ├── test_reconciler.py           # Reconciler tests
│   ├── test_filters.py              # Filter tests
│   └── fixtures/
│       ├── sample_cy.xml
│       ├── sample_py.xml
│       ├── sample_8858_cy.xml
│       ├── sample_8858_py.xml
│       ├── sample_mixed_cy.xml
│       └── sample_mixed_py.xml
├── specs/
│   ├── mythos-framework.md          # Architecture spec (living doc)
│   ├── mythos-strategy.md           # THIS FILE — full strategy
│   ├── entity-tagger.md             # Entity tagger spec
│   ├── audit-engine.md
│   ├── reconciler.md
│   ├── workbook-reader.md
│   ├── xml-parser.md
│   ├── pdf-validator.md
│   ├── review-engine.md
│   └── ...
└── ...
```

---

## Apéndice B: Competitive Landscape

### Known Competitor Tools (PwC Internal)

| Tool | Owner | Strengths | Weaknesses vs Mythos |
|------|-------|-----------|---------------------|
| FormReviewerDUOPwCV4 | US team | 23 rules, configurable JSON DSL | HTML-only output, no graph, no rollover |
| XML_PARSERv2 | Unknown | Schedule extraction | No review logic, just parsing |
| irs_rollover_analyzer | Unknown | Year-over-year | Limited checks (ROL only) |
| Bolt (QST Parser) | QST MX | Alteryx-powered extraction | Requires license, slow, no review |

### Gap Analysis (Mythos vs All)

Mythos uniquely covers:
- Combined 5471+8858+8990 in single pass
- Ownership graph + aggregation checks
- PDF-to-XML cross-validation (12 schedules)
- NiceGUI desktop app (zero deploy)
- Entity tagging/classification engine
- Service layer (API-ready architecture)

All competitors lack:
- Multi-form composite review
- Severity-ranked output with audit trail
- Sub-3-second execution
- Zero-config operation
- Automated PDF validation against source XML

# Mythos Development Framework

> Automated compliance review engine for IRS e-file XML returns (Forms 5471/8858).
> Current version: **v0.7.5** — Phases 1-6 complete + reports/export + cross-schedule checks + entity classifier + evidence traceability.

---

## Posicion Competitiva

### Herramientas Actuales y sus Limitaciones

| Tool | What It Does | Limitations |
|------|-------------|-------------|
| **Bolt (QST Parser)** | Extrae schedule data de XML a Excel via Alteryx | Solo extraccion — no hay logica de review. Requiere Alteryx ($$$). 5-10 min/schedule. |
| **Alteryx Workflows** | Reconciliacion OIT vs source data | Requiere licencia. Setup per-client. No portable. Fragil ante cambios de estructura. |
| **ONESOURCE Diagnostics** | Validacion pre-e-file (form-level) | Limitado a format rules. No revisa reasonableness. No cruza contra prior year. |
| **graphBeacon Reports** | Calculation summaries (GILTI, SubF, FTC) | Solo para clientes en gB. No valida — solo presenta. |
| **Manual Excel Review** | Senior/manager abre workbook y checa | 4-8 horas por return. Inconsistent. No audit trail. |

### Mythos Competitive Advantage

```
                    BOLT          Mythos
Speed:              5-10 min      < 3 sec
License needed:     Alteryx       None (Python)
Automated review:   No            Yes (32 checks)
Multi-year:         Manual        Automatic
Portability:        Desktop only  CLI + Dashboard + API
Client setup:       Per-client    Zero-config (XML-first)
Output:             Raw Excel     Ranked findings + export
```

**Mythos = BOLT + ONESOURCE diagnostics + reviewer judgment, automated.**

---

## Architecture (v0.7.1)

```
lab/xml_parser/
├── __init__.py              # Package entry — re-exports public API
├── __main__.py              # python -m lab.xml_parser
│
├── core/                    # Zero-dependency shared layer
│   ├── __init__.py          # Public re-exports
│   ├── models.py            # Finding, ReviewReport, RolloverItem, RolloverReport
│   ├── constants.py         # EXPECTED_FX_RANGES, thresholds
│   ├── config.py            # MythosConfig (env-aware, singleton)
│   ├── exceptions.py        # ParseError, ValidationError, ExportError
│   ├── logging.py           # Structured logging setup
│   └── filters.py           # FilterSpec, filter_review_report, filter_rollover_reports
│
├── engine/                  # Check orchestration
│   ├── __init__.py
│   └── checks/
│       ├── __init__.py      # ALL_CHECKS registry
│       ├── _helpers.py      # CheckContext, safe_float
│       ├── flow.py          # FLO-001 to FLO-008 (8 checks)
│       ├── completeness.py  # CMP-001 to CMP-006 (6 checks)
│       ├── reasonableness.py # RSN-001 to RSN-007 (7 checks)
│       └── rollover.py      # ROL-001 to ROL-011 (11 checks)
│
├── reports/                 # Data generation — pure functions, no rendering
│   ├── __init__.py          # run_all_reports(), ReportEngine (backward-compat)
│   ├── rollover.py          # sch_f_rollover, page1_rollover, sch_j_rollover
│   ├── movement.py          # ep_movement, gilti_comparison
│   └── entity_changes.py    # new_final_entities, schedule_g_changes
│
├── export/                  # All output formats — formatting only, no logic
│   ├── __init__.py          # Re-exports: export_excel, export_pdf, export_html, export_csv
│   ├── design_system.py     # DesignSystem — unified visual tokens (navy/copper palette)
│   ├── excel_exporter.py    # Premium corporate workbook (xlsxwriter)
│   ├── pdf_exporter.py      # Editorial-quality landscape PDF (WeasyPrint/xhtml2pdf)
│   ├── html_exporter.py     # Great Tables styled HTML (summary + detail + combined)
│   └── csv_exporter.py      # Flat CSV for downstream analysis
│
├── api/                     # Service layer — single entry point
│   ├── __init__.py          # Exports MythosService
│   └── service.py           # MythosService + result dataclasses
│
├── review_engine.py         # Thin orchestrator (~95 lines)
├── parser.py                # EFileParser — XML → DataFrames
├── models.py                # ParsedReturn, SubsidiaryReturn (parser models)
├── comparator.py            # XMLComparator — PY vs CY diff
├── reconciler.py            # Workbook vs XML reconciliation
├── workbook_reader.py       # openpyxl-based workbook parser
├── field_maps.py            # Schedule field → line number mappings
├── output.py                # [LEGACY] Wide-format Excel/PDF (PwC orange) — still used by ReportEngine._to_excel()
├── gt_output.py             # [SHIM] Delegates to export/html_exporter.py
├── cli.py                   # Click CLI (list, parse, compare, review, check, reconcile, tag, dashboard)
├── dashboard.py             # NiceGUI web dashboard
└── dashboard_st.py          # Streamlit alternative (legacy)
```

### Layer Dependencies

```
┌────────────────────────────────────────────────────────────────┐
│  Presentation (CLI, Dashboard, Scripts)                        │
├────────────────────────────────────────────────────────────────┤
│  API (MythosService)                              ← entry pt  │
├──────────────────────────┬────────────────────────────────────┤
│  Engine (ReviewEngine)   │  Reports (run_all_reports)         │
│  engine/checks/*         │  reports/rollover, movement, etc.  │
├──────────────────────────┴────────────────────────────────────┤
│  Export (export_excel, export_pdf, export_html, export_csv)   │
├────────────────────────────────────────────────────────────────┤
│  Parser (EFileParser, WorkbookReader, Reconciler)             │
├────────────────────────────────────────────────────────────────┤
│  Core (models, config, constants, logging)     ← zero deps   │
└────────────────────────────────────────────────────────────────┘
```

### Key Design: reports/ vs export/

| Package | Responsibility | Inputs | Outputs |
|---------|---------------|--------|---------|
| `reports/` | Generate structured data from parsed XML | `ParsedReturn` (PY, CY) | `RolloverReport` objects |
| `export/` | Format data into files for human consumption | `RolloverReport`, `ReviewReport` | `.xlsx`, `.pdf`, `.html`, `.csv` |

This separation means:
- Report logic is testable without file I/O
- Export formats can be added/changed without touching business logic
- Consumers choose which export format at the presentation layer
- The `DesignSystem` in export/ controls all visual tokens (navy/copper palette)

---

## Check Inventory (32 checks)

### Flow (8) — Internal consistency within a single year

| ID | Severity | What it catches |
|----|----------|----------------|
| FLO-001 | HIGH | Sch C net income ≠ Sch H line 1 |
| FLO-002 | MEDIUM | E&P FC ÷ FX ≠ USD amount |
| FLO-003 | HIGH | Sch I-1 components don't reconcile to gross |
| FLO-004 | MEDIUM | Sch E taxes > 45% of pre-tax income |
| FLO-005 | HIGH | Tested loss entity has positive foreign taxes |
| FLO-006 | HIGH | Sch C income − deductions ≠ net |
| FLO-007 | HIGH | Negative total assets on balance sheet |
| FLO-008 | HIGH | Balance sheet doesn't balance (assets ≠ L+E) |

### Completeness (6) — Missing schedules or required data

| ID | Severity | What it catches |
|----|----------|----------------|
| CMP-001 | HIGH | Entity in return but no Sch H |
| CMP-002 | MEDIUM | Has Sch H but no Sch I-1 (GILTI classification missing) |
| CMP-003 | MEDIUM | Tested income entity has no Sch E taxes |
| CMP-004 | HIGH | Sch F has BOY but EOY is zero/missing |
| CMP-005 | MEDIUM | No exchange rate on Sch H |
| CMP-006 | HIGH | Invalid/missing reference ID |

### Reasonableness (7) — Values outside expected ranges

| ID | Severity | What it catches |
|----|----------|----------------|
| RSN-001 | LOW | E&P exceeds $1B |
| RSN-002 | MEDIUM | FX rate outside expected range for currency |
| RSN-003 | MEDIUM | Implied ETR outside 0-50% |
| RSN-004 | LOW | Tested income = SubF income (possible misclass) |
| RSN-005 | LOW | All entities same E&P sign (unusual) |
| RSN-006 | HIGH | QBAI > total assets (impossible) |
| RSN-007 | MEDIUM | Interest expense > gross income |

### Rollover (11) — PY-to-CY continuity

| ID | Severity | What it catches |
|----|----------|----------------|
| ROL-001 | HIGH/MED | Sch F per-line rollover (16 BS lines, $10K materiality) |
| ROL-002 | MEDIUM | Entity dropped PY→CY |
| ROL-003 | MEDIUM | Entity added in CY |
| ROL-004 | MEDIUM | E&P sign flip |
| ROL-005 | LOW | FX rate change >25% YoY |
| ROL-006 | HIGH | Material E&P disappears to zero |
| ROL-007 | HIGH | Sch J pool rollover mismatch (5 PTEP pools) |
| ROL-008 | MED/HIGH | Page 1 entity info changed (name, FC, country) |
| ROL-009 | MEDIUM | Sch G indicator flip (163j, BEAT, FDII, P2) |
| ROL-010 | MEDIUM | GILTI classification flip (income ↔ loss) |
| ROL-011 | HIGH/MED | Sch H vs Sch J E&P accumulation math |

---

## API Reference

### MythosService (primary interface)

```python
from lab.xml_parser.api import MythosService

svc = MythosService(
    config=None,          # Optional MythosConfig override
    progress=None,        # Optional Callable[[str, float], None]
)

# Run compliance review
result = svc.review(
    current_xml="path/to/cy.xml",
    prior="path/to/py.xml",     # Optional — enables rollover checks
    export=False,                # Auto-export to Excel
    export_path=None,            # Custom export path
)
# Returns: ReviewResult(success, report, duration_ms, finding_count, high_count, ...)

# List entities with schedule flags
entities = svc.list_entities("path/to/file.xml")
# Returns: list[EntitySummary(reference_id, name, country, currency, has_sch_*)]

# Classify entities (unified pipeline — parse → enrich → tag)
cr = svc.classify_entities("path/to/file.xml", registry=None)
# Returns: ClassificationResult(success, entities: list[ClassifiedEntity], summary, duration_ms)
# ClassifiedEntity has: identity, type flags, all schedule dicts, tags, contradictions, tag_metadata
# tag_metadata maps tag_name → {schedule.field: value} (evidence of what triggered the tag)

# Tag entities (backward-compat wrapper over classify_entities)
tag_result = svc.tag_entities("path/to/file.xml")
# Returns: TagSummary(success, entity_count, results: list[TagResult], summary, ...)

# Reconcile workbook vs XML
result = svc.reconcile(
    xml_path="path/to/xml",
    workbook_path="path/to/wb.xlsx",
    tolerance=1.0,
    schedules=None,              # Or ["IRS5471ScheduleH", ...]
)
# Returns: ReconcileResult(success, pass_rate, fail_count, failures_df, ...)

# Export findings
export = svc.export_review(report, path="output.xlsx", format="excel")
# Returns: ExportResult(success, path, format, message)

# Full review pipeline (tabular + automated)
reports = svc.full_review(current_xml, prior_xml, output_path=None)
# Returns: dict of RolloverReport objects
```

### Reports Package (data generation)

```python
from lab.xml_parser.reports import run_all_reports, sch_f_rollover, ep_movement

# Orchestrator — runs all 7 reports, returns dict
reports = run_all_reports("prior.xml", "current.xml")
# Returns: {"Sch F Rollover": RolloverReport, "Sch J Rollover": ..., ...}

# Individual report functions (for targeted use)
from lab.xml_parser.parser import EFileParser
py = EFileParser("prior.xml").parse()
cy = EFileParser("current.xml").parse()

report = sch_f_rollover(py, cy)   # Pure function: ParsedReturn → RolloverReport
print(f"{report.passed}/{report.total_checks} passed")

# Backward-compatible class (delegates to pure functions)
from lab.xml_parser.reports import ReportEngine
engine = ReportEngine("prior.xml", "current.xml")
engine.full_review(output_path="output.xlsx")  # Runs all + terminal display + export
```

### Export Package (output formats)

```python
from lab.xml_parser.export import export_excel, export_pdf, export_html, export_csv, export_findings_csv

# Excel — premium corporate workbook
export_excel("output.xlsx", review_report=report, rollover_reports=reports, client_name="Client")

# HTML — Great Tables publication-quality (summary + detail + combined)
files = export_html(reports, "output_dir/", client_name="Client", tax_year="2025")

# PDF — editorial-quality landscape
export_pdf("output.pdf", review_report=report, rollover_reports=reports, client_name="Client")

# CSV — flat files for downstream analysis
files = export_csv(reports, "output_dir/", prefix="review", include_pass=True)
export_findings_csv(review_report, "findings.csv")

# Design system (for custom rendering)
from lab.xml_parser.export import DesignSystem
print(DesignSystem.NAVY, DesignSystem.COPPER)  # #1B2A4A, #C77B4A
```

### Direct Engine Access (for advanced use)

```python
from lab.xml_parser.review_engine import ReviewEngine
from lab.xml_parser.core.models import Finding, ReviewReport

engine = ReviewEngine()
report = engine.review("cy.xml", "py.xml")

for f in report.high_severity():
    print(f"{f.check_id} {f.entity_code}: {f.description}")
```

### Individual Check Modules (for testing/extending)

```python
from lab.xml_parser.engine.checks._helpers import CheckContext
from lab.xml_parser.engine.checks.flow import run_flow_checks
from lab.xml_parser.parser import EFileParser

parser = EFileParser("return.xml")
df = parser.to_dataframe()

def get_name(df, code):
    return code  # simplified

ctx = CheckContext(parser, df, get_name)
findings = run_flow_checks(ctx)
```

### Configuration

```python
from lab.xml_parser.core.config import get_config, reset_config

# Auto-detects project root, env vars override
cfg = get_config()
cfg.sources_dir     # Path to sources/
cfg.output_dir      # Path to output directory
cfg.client_dir("cng")  # sources/cng/

# Environment variables:
# MYTHOS_SOURCES_DIR, MYTHOS_OUTPUT_DIR, MYTHOS_LOG_LEVEL
```

---

## Test Suite

| File | Tests | Coverage |
|------|-------|----------|
| `lab/tests/test_review_engine.py` | 25 | Baseline regression (14 findings), all check IDs, severities, entities |
| `lab/tests/test_service.py` | 9 | Service layer: review, entities, export, progress, error handling |
| `lab/tests/test_reports_export.py` | 13 | Smoke tests: all 7 report functions, ReportEngine compat, CSV/Excel/HTML export |
| `lab/tests/test_entity_tagger.py` | 41 | 8 rules (True/False), contradictions, tolerance, batch, accessors, evidence traceability |
| `lab/tests/test_entity_classifier.py` | 45 | Pipeline, identity, OIT locator, summary, registry enrichment, bridge methods, tag consistency, service integration |
| `lab/tests/test_pdf_validator.py` | 130+ | Layout regex + reconciliation for 12 schedules |
| `lab/tests/test_8858.py` | 15+ | Form 8858 completeness, flow, reasonableness, rollover |
| **Total** | **593** | All pass in ~20s |

### Fixtures

- `lab/tests/fixtures/sample_cy.xml` — 5 entities designed to trigger specific checks
- `lab/tests/fixtures/sample_py.xml` — 5+1 entities (EDROP for ROL-002)

### Baseline (immutable until deliberate change)

```
14 findings total (7 HIGH, 7 MEDIUM):
HIGH   CMP-001  E003   Missing Schedule H
HIGH   FLO-003  E005   Sch I-1 reconciliation (delta $300M)
HIGH   FLO-005  E002   Tested loss with taxes
HIGH   FLO-008  E004   Balance sheet imbalance (delta $500K)
HIGH   ROL-007  E001   Sch J Post-2017 E&P rollover
HIGH   ROL-007  E001   Sch J Total 964(a) E&P rollover
HIGH   RSN-006  E004   QBAI > total assets
MEDIUM CMP-003  E005   Tested income, no Sch E
MEDIUM CMP-005  E005   No exchange rate
MEDIUM ROL-002  EDROP  Entity dropped
MEDIUM ROL-003  E005   New entity
MEDIUM ROL-004  E002   E&P sign flip
MEDIUM ROL-010  E002   GILTI classification flip
MEDIUM RSN-003  E002   ETR anomaly (-60%)
```

---

## KPI Framework

### Engine Quality

| KPI | Target | Current |
|-----|--------|---------|
| Check Coverage | 32/32 | 32/32 ✅ |
| True Positive Rate | > 70% | ~85% (sample return validated) |
| Category Completeness | 4/4 | 4/4 ✅ |
| Entity Coverage | 100% | 100% ✅ |

### Operational

| KPI | Target | Current |
|-----|--------|---------|
| Time to First Review | < 5 sec | ~200ms (fixtures), ~3s (real returns) |
| Zero-Config | 100% clients | 100% ✅ |
| Test Suite | Green | 47/47 ✅ |

---

## Refactoring History

| Phase | Status | Key Outcome |
|-------|--------|-------------|
| 1 — Stabilize | ✅ | 25 regression tests, 14-finding baseline |
| 2 — Core Models | ✅ | `core/models.py`, numpy eliminated |
| 3 — Split Checks | ✅ | 4 independent modules, engine 957→95 lines |
| 4 — Unify Engines | ✅ | ReviewEngine integrated into ReportEngine |
| 5 — Infrastructure | ✅ | Config system, logging, exceptions |
| 6 — Service Layer | ✅ | MythosService + typed results + 9 tests |
| 6.1 — Reports/Export Split | ✅ | reports/ (pure data) + export/ (all formats) + 13 smoke tests |
| 6.2 — Entity Tagger | ✅ | 8 rules, EntityTagger + TagRule protocol, CLI `tag` command, MythosService.tag_entities() |
| 6.3 — Entity Classifier | ✅ | Unified pipeline: ClassifiedEntity canonical model, EntityClassifier (parse→enrich→tag), OIT locator extraction, ClassificationSummary, registry bridge methods, 45 tests |
| 6.4 — Evidence Traceability | ✅ | TagRule.xml_fields declares evaluated XML fields; TagResult.evidence captures triggering values; flows to ClassifiedEntity.tag_metadata |
| 7 — Dashboard | 🔲 PENDING | Multi-session, componentized, polished |
| 8 — Packaging | 🔲 PENDING | pip install, CI, .exe distribution |
| 9 — v0.7 Features | 🔲 PENDING | Ownership graph, cross-entity checks |
| 9.5 — Cross-Schedule Consistency | 🔲 PENDING | 9 new XSC checks from competitor analysis |

---

## Remaining Work (Phases 7-9)

### Phase 7: Dashboard Modernization

**Goal:** Multi-session safe, componentized, polished UI/UX.

**Deliverables:**
- [ ] Per-session state (eliminate module-level global `state`)
- [ ] Split pages into individual files (overview, findings, entities)
- [ ] Extract reusable components (metric card, findings table, severity badge)
- [ ] Progress feedback during review execution (via ProgressCallback)
- [ ] Entity detail view (click entity → all findings + schedule data)
- [ ] File picker improvements (drag-drop, recent files, client selector)
- [ ] Consume MythosService instead of direct engine instantiation

**Verification:** Two browser tabs work independently. No state leaks.

### Phase 8: Package Structure + Distribution

**Goal:** Installable, distributable, CI-ready.

**Deliverables:**
- [ ] Complete `pyproject.toml` with pinned dependencies
- [ ] `python -m mythos` entry point (replaces `python -m lab.xml_parser`)
- [ ] Remove all `sys.path` hacks from tests
- [ ] GitHub Actions CI (lint + test on push)
- [ ] PyInstaller or Nuitka spec for standalone `.exe`

**Verification:** `pip install -e .` works. CI green. `.exe` launches dashboard.

### Phase 9: v0.7 Features (Ownership Graph + Aggregation)

**Goal:** Cross-entity validation via ownership graph.

**Deliverables:**
- [ ] `engine/ownership_graph.py` using networkx
- [ ] Parse Sch G ownership percentage fields
- [ ] AGG-001 through AGG-008 aggregation checks
- [ ] Ownership visualization in dashboard
- [ ] Test against flat structure and tiered structure returns

**Verification:** AGG checks fire correctly. Graph matches known structure.

### Phase 9.5: Cross-Schedule Consistency Checks

**Goal:** Validate data ties across Schedules Q, I-1, E, J, P that are not covered by existing flow/rollover checks. Derived from competitive analysis of peer-developed IRS XML review tools.

**Origin:** Team-internal HTML tool suite (`FormReviewerDUOPwCV4`, `XML_PARSERv2`, `irs_rollover_analyzer`) defined 23 configurable rules. 6 overlap with Mythos; the remaining 17 expose genuine coverage gaps — primarily Schedule Q cross-ties and J/P basket consistency.

**New Module:** `engine/checks/cross_schedule.py`

**Check Inventory (9 new checks):**

| ID | Severity | What it catches | Source Rule |
|----|----------|----------------|-------------|
| XSC-001 | HIGH | Sch I-1 Gross Income ≠ Sch Q Total Gross Income (GEN basket) | Competitor #9 |
| XSC-002 | HIGH | Sch I-1 SubF Income ≠ Sch Q CFC Total Gross Income (PAS basket) | Competitor #10 |
| XSC-003 | HIGH | Sch I-1 Tested Income ≠ Sch Q Tested Income Net (GEN basket) | Competitor #23 |
| XSC-004 | MEDIUM | Sch E1 Tested Taxes USD ≠ Sch Q Allowed FTC (GEN basket) | Competitor #22 |
| XSC-005 | LOW | Sch Q Other Expenses ≠ 0 (unexpected allocation) | Competitor #8 |
| XSC-006 | HIGH | Category 1 filer without Schedule P populated | Competitor #18 |
| XSC-007 | MEDIUM | Sch J basket exists but corresponding Sch P basket missing | Competitor #19-21 |
| XSC-008 | MEDIUM | Sch I indicator unexpectedly "Yes" (blocked/unblocked/ED) | Competitor #11-13 |
| XSC-009 | LOW | Sch E local currency tax ≠ FC tax (when FC = local) | Competitor #14 |

**Enhancement to existing check:**
- FLO-017 enhanced: compare H vs J **per basket** (PAS, GEN separately) instead of aggregate only

**Deliverables:**
- [ ] `engine/checks/cross_schedule.py` — 9 check functions
- [ ] FLO-017 basket split in `engine/checks/flow.py`
- [ ] Registration in `engine/checks/__init__.py`
- [ ] Test coverage via existing fixture or minimal extension

**Out-of-Scope (Phase 10+):**
- Form 8990 cross-form ties (rules #6, #7, #15) — requires new form parser
- Configurable user-defined rules engine (JSON-based rule DSL like competitor)

**Verification:**
- [ ] XSC checks produce findings on test data without errors
- [ ] FLO-017 now fires per-basket findings instead of single aggregate
- [ ] All existing 5471 tests still pass (zero regression)
- [ ] `python -m pytest lab/tests/ -v` all green

---

## Architecture Principles

1. **XML-first**: Never require workbook access for core review
2. **Zero-config**: Works on any 5471/8858 return without client-specific setup
3. **Severity is actionable**: HIGH = must resolve before filing, MEDIUM = review required, LOW = note
4. **No false confidence**: "Clean" means ALL checks passed, not "some checks ran"
5. **Audit trail**: Every finding has check_id, expected, actual, delta, context
6. **Extensible**: Adding a check = one function in the appropriate module
7. **Testable**: Every check module can run independently with its own fixtures
8. **Service-first**: All consumers go through MythosService, not raw engines

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-24 | NiceGUI for UI | Supports native + web, Tailwind/Quasar styling, Python-native |
| 2026-07-24 | lxml for XML | Performance validated, correct IRS namespace handling |
| 2026-07-24 | pandas for tabular | EFileParser→DataFrame is natural for checks |
| 2026-07-24 | networkx for ownership | Ephemeral graph, no server needed, pure Python |
| 2026-07-24 | ReviewEngine = single source of truth | Eliminates inconsistency between `review` and `check` commands |
| 2026-07-24 | Tests FIRST | Cannot safely refactor without regression protection |
| 2026-07-24 | CheckContext pattern | Lightweight DI — avoids ABC/Protocol overhead while keeping modules independent |
| 2026-07-24 | Service layer with typed results | Clean boundary enables UI swap without touching business logic |
| 2026-07-24 | Config from env vars | Portable across machines without code changes |
| 2026-07-24 | reports/ = pure data, export/ = all formats | Enables testing report logic without file I/O; formats added independently |
| 2026-07-24 | DesignSystem tokens (navy/copper) | Single source of truth for branded output across HTML, PDF, Excel |
| 2026-07-24 | Backward-compat shims (gt_output, output.py) | Consumers migrate incrementally; old scripts keep working |
| 2026-07-24 | Phase 9.5 from competitor analysis | 23 peer rules mapped; 6 overlap, 17 gaps → 9 new XSC checks + 1 enhancement |
| 2026-07-24 | Separate cross_schedule.py module | Avoids bloating flow.py; keeps XSC namespace distinct from FLO/CMP/RSN/ROL |
| 2026-07-29 | Reduce tag rules 16→8, add evidence | Removed dormant/dre/insurance/has_qbai/sec_956/sec_245a/us_property/income_blocked (not actionable classifications). Added xml_fields to TagRule + evidence capture for tag→XML traceability |

---

## Assumptions

- XML files remain IRS e-file format (namespace `http://www.irs.gov/efile`)
- Returns are primarily 5471/8858 with potential expansion to 8865, 8992, 1118
- Single-machine execution (no distributed processing needed at current scale)
- Maximum expected return size: ~200 entities (handles in < 10 sec)
- Users are US int'l tax professionals (associates through partners)
- PwC internal distribution only (no external client access to tool)

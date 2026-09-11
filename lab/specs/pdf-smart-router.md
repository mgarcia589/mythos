# Spec: PDF Smart Router — Multi-Form Batch PDF Processing

> Expande `lab/pdf_validator/` con un router inteligente que procesa PDFs batch
> de OIT que contienen TODAS las forms de un deal/engagement en un solo archivo.
> Resuelve el gap donde el validator actual espera un PDF separado por schedule,
> pero OIT exporta un solo PDF masivo (ej: 1,070 páginas para Client-A).

## Motivacion

El PDF Validator actual (15 schedules, 264 tests) funciona correctamente cuando
recibe un PDF por schedule. Pero en produccion, OIT exporta un unico PDF batch:

```
"FY25 Client-A Forms Print - All Foreign Entity Forms.pdf"
  → 1,070 paginas
  → 28 entidades (5471 + 8858)
  → 16 schedule types detectados
  → Forms intercaladas: 5471 → 8990 (163j) → 5471 → 8858 → ...
```

El `PDFValidator.full_validation()` espera archivos separados (`schj-*.pdf`,
`schf-*.pdf`). No puede procesar este formato batch. El Scanner detecta forms y
schedules pero no esta conectado al Extractor.

## Outcomes

1. **Procesar un PDF batch multi-form** de OIT sin pre-procesamiento manual
2. **Detectar y agrupar paginas** por entidad y schedule automaticamente
3. **Validar todos los schedules** contra un XML en un solo comando
4. **Producir un reporte consolidado** (Excel multi-sheet) con dashboard
5. **Calibrar con data real** de Engagement-1/Client-A iterativamente

## Problemas Detectados en Scan Real (Client-A FY25)

### Scanner Issues
| # | Problema | Evidencia |
|---|----------|-----------|
| S1 | Entity names parseados incorrectamente | "for example, Form 5471" en vez de "ENTITY ALPHA LTD" |
| S2 | Schedules por entidad incompletos | Mayoria muestra solo `['B', 'A']` en vez de todos |
| S3 | Page ranges incorrectos | Primera entidad: `(2, 1063)` — casi todo el PDF |
| S4 | Ref ID de primera entidad = "ber" | Fragmento de "number" del header de Form 8990 |
| S5 | Form 8990 (163j) no reconocida | Las paginas de 8990 se confunden con 5471 |
| S6 | Scan time: 164 segundos | Para 1,070 paginas — aceptable pero mejorable |

### Estructura Real del PDF Batch

OIT organiza el PDF asi para cada entidad:
```
Entity Block (Entity Alpha — C0001):
  Page 2:   Form 5471 Page 1 (entity info, Schedule A)
  Page 3:   Schedule B (Shareholders)
  Page 4:   Schedule C (Income Statement)
  Page 5:   Schedule F (Balance Sheet)
  Page 6-7: Schedule G (Other Information)
  Page 8:   Schedule E (Foreign Taxes) — part 1
  Page 9:   Schedule E Detail
  Page 10-12: Schedule I, I-1
  Page 13-15: Schedule J (3 pages per entity/basket)
  Page 16-18: Schedule P (multi-page)
  Page 19:  Schedule R (Distributions)
  --- THEN ---
  Page 25-26: Form 8990 (163j) for same entity
  --- THEN next entity ---
```

Key observations:
- Entities son bloques contiguos de ~15-25 paginas para 5471
- Form 8990 aparece DESPUES de todo el bloque 5471 de cada entidad
- 8858 entities estan intercaladas (separate FDE/FB entities)
- Schedule E tiene paginas "Detail" con layout non-table
- Schedule J usa 3 paginas por entity/basket
- Algunos schedules estan vacios (solo headers, no data)

## Scope

### Phase 1: Smart Page Router (core)

Nuevo componente `PDFRouter` que:
1. Toma un PDF batch + XML
2. Escanea paginas para construir un **page map**: `{(entity_ref, schedule): [page_nums]}`
3. Pasa cada grupo de paginas al `PDFExtractor` existente
4. Corre `PDFReconciler` por schedule
5. Produce reporte consolidado

### Phase 2: Scanner Fixes (calibration)

Corregir los 6 issues del scanner detectados con data real:
- S1: Mejorar entity name parsing (el name esta en la linea DESPUES de "Name of foreign corporation")
- S2: Mejorar schedule detection per-entity (actualmente pierde schedules)
- S3: Fix page range tracking (usar entity transitions, no solo ref_id matches)
- S4: Filtrar ref IDs invalidos (fragmentos cortos como "ber")
- S5: Agregar Form 8990 detection para no confundir con 5471

### Phase 3: Consolidated Report

Un solo Excel con:
- Dashboard sheet (entity x schedule matrix con pass/fail)
- Per-schedule sheets (discrepancies)
- Entity completeness check (XML entities vs PDF entities)

## Design

### PDFRouter Class

```python
class PDFRouter:
    """Route pages from a multi-form batch PDF to schedule-specific extractors.
    
    Takes a single OIT batch PDF containing all forms for all entities
    and produces validated results for each detected schedule.
    """
    
    def __init__(self, pdf_path: Path, xml_path: Path,
                 tolerance: float = 10.0,
                 schedules: list[str] | None = None):
        """
        Args:
            pdf_path: OIT batch PDF (all forms, all entities)
            xml_path: XML e-file for reconciliation
            tolerance: Materiality threshold ($10 default)
            schedules: Specific schedules to validate (None = all detected)
        """
    
    def route(self) -> BatchValidationResult:
        """Full pipeline: scan → route → extract → reconcile → report."""
    
    def scan(self) -> PageMap:
        """Phase 1: Build page map from PDF scan."""
    
    def validate_schedule(self, schedule: str, pages: list[int]) -> PDFValidationReport:
        """Validate one schedule using specific pages from the batch PDF."""
```

### PageMap Data Structure

```python
@dataclass
class PageMap:
    """Map of (entity, schedule) -> page numbers within a batch PDF."""
    total_pages: int
    entities: dict[str, EntityBlock]  # ref_id -> block
    unrecognized_pages: list[int]     # pages that couldn't be classified
    scan_duration_ms: float
    
@dataclass
class EntityBlock:
    """All pages belonging to one entity in the batch PDF."""
    reference_id: str
    entity_name: str
    form_type: str          # "5471", "8858"
    country: str
    schedules: dict[str, list[int]]  # schedule -> [page_numbers]
    # e.g. {"J": [13,14,15], "F": [5], "H": [70], ...}
    
@dataclass
class BatchValidationResult:
    """Result of validating all schedules in a batch PDF."""
    pdf_source: str
    xml_source: str
    page_map: PageMap
    schedule_reports: dict[str, PDFValidationReport]
    entity_completeness: EntityCompleteness
    duration_seconds: float
    
    @property
    def total_discrepancies(self) -> int: ...
    @property  
    def has_phantoms(self) -> bool: ...
    @property
    def summary(self) -> str: ...

@dataclass
class EntityCompleteness:
    """Cross-check: are all XML entities present in the PDF?"""
    xml_entities: set[str]
    pdf_entities: set[str]
    missing_from_pdf: set[str]
    extra_in_pdf: set[str]
```

### Page Classification Strategy

El clasificador de paginas debe identificar:

```python
PAGE_TYPES = {
    "5471_page1":   "Form 5471 Page 1 + Schedule A",
    "5471_schb":    "Schedule B (Shareholders)",
    "5471_schc":    "Schedule C (Income Statement)",
    "5471_sche":    "Schedule E (Foreign Taxes)",
    "5471_sche_detail": "Schedule E Detail (non-table)",
    "5471_schf":    "Schedule F (Balance Sheet)",
    "5471_schg":    "Schedule G (Other Information)",
    "5471_schh":    "Schedule H (Current E&P)",
    "5471_schi":    "Schedule I (Shareholder's Income)",
    "5471_schi1":   "Schedule I-1 (GILTI)",
    "5471_schj_p1": "Schedule J Page 1",
    "5471_schj_p2": "Schedule J Page 2",
    "5471_schj_p3": "Schedule J Page 3 (Recapture)",
    "5471_schp":    "Schedule P (PTEP)",
    "5471_schr":    "Schedule R (Distributions)",
    "8858_page1":   "Form 8858 Page 1",
    "8858_schc":    "8858 Schedule C",
    "8858_schf":    "8858 Schedule F",
    "8858_schg":    "8858 Schedule G",
    "8858_schh":    "8858 Schedule H",
    "8990":         "Form 8990 (163j) — skip for now",
    "cover":        "Cover page / summary — skip",
    "unknown":      "Unrecognized page",
}
```

Entity detection priority:
1. "Reference ID number" line → extract ref_id directly
2. "Name of foreign corporation" / "Name of foreign entity" → entity name
3. If page is Form 8990, extract ref_id from the "A" line
4. If none found, inherit from previous page (same entity block)

### Extractor Integration

El Extractor actual abre el PDF completo y escanea TODAS las paginas buscando
su schedule. Para el router, necesitamos poder pasarle page ranges:

**Option A: Page-filtered extraction** (preferred)
- PDFExtractor acepta un parametro `pages: list[int]` que limita el scan
- Solo procesa las paginas indicadas por el router
- Minimal changes al extractor existente

**Option B: Split PDF to temp files**
- Router crea PDFs temporales por schedule (via pdfplumber crop)
- Pasa cada temp PDF al extractor existente
- Mas overhead pero zero changes al extractor

→ **Decision: Option A** — agregar `pages` parameter al extractor.

### Performance Target

| Metric | Current (full scan) | Target |
|--------|-------------------|--------|
| Scan (page map) | 164s (1,070 pgs) | <60s |
| Per-schedule extraction | N/A | <15s per schedule |
| Full batch validation | N/A | <5 min total |
| Report generation | <1s | <3s (consolidated) |

Optimizacion: el scan solo necesita leer los primeros 500 chars de cada pagina
(no text completo), y puede cachear page text para reusar en extraction.

## API

```python
from lab.pdf_validator import PDFRouter

# One-command batch validation
router = PDFRouter(
    pdf_path="sources/engagement-1/batch-fy25-all-forms-print.pdf",
    xml_path="sources/engagement-1/efile-fy25-v15.xml",
)
result = router.route()

# Inspect page map
print(f"Entities: {len(result.page_map.entities)}")
for ref_id, block in result.page_map.entities.items():
    print(f"  {ref_id}: {block.entity_name} — {list(block.schedules.keys())}")

# Access per-schedule results
for sch, report in result.schedule_reports.items():
    print(f"  Sch {sch}: {report.ok_count} OK, {report.phantom_count} PHANTOM")

# Entity completeness
print(f"Missing from PDF: {result.entity_completeness.missing_from_pdf}")

# Export consolidated report
result.to_excel("output/client-a-batch-validation.xlsx")
```

## Task Breakdown

### Phase 1: Smart Router Core (7 tasks)

| # | Task | Output |
|---|------|--------|
| 1.1 | Crear modelos: `PageMap`, `EntityBlock`, `BatchValidationResult`, `EntityCompleteness` en `models.py` | Data structures |
| 1.2 | Crear `PDFRouter` class en `router.py` con `scan()` method | Page classification |
| 1.3 | Implementar page classifier mejorado (todos los page types + Form 8990 detection) | Classification logic |
| 1.4 | Implementar entity block builder (agrupar paginas por entidad) | Entity grouping |
| 1.5 | Agregar `pages` parameter a `PDFExtractor` para page-filtered extraction | Extractor enhancement |
| 1.6 | Implementar `route()` pipeline completo: scan → extract → reconcile | Pipeline |
| 1.7 | Implementar `to_excel()` con reporte consolidado multi-schedule | Report |

### Phase 2: Scanner Calibration (4 tasks)

| # | Task | Output |
|---|------|--------|
| 2.1 | Fix entity name parsing (capture name from header line, not regex fragments) | Better names |
| 2.2 | Fix schedule-per-entity tracking (use page classifier, not just pattern match) | Complete schedule lists |
| 2.3 | Fix page range tracking (entity transitions based on ref_id changes) | Accurate ranges |
| 2.4 | Add Form 8990 detection to skip/classify correctly | No false positives |

### Phase 3: Integration Tests with Real Data (3 tasks)

| # | Task | Output |
|---|------|--------|
| 3.1 | Test router against Client-A PDF + latest XML | Real validation |
| 3.2 | Analyze and fix extraction failures detected by real data | Calibrated layouts |
| 3.3 | Unit tests for router, page classifier, entity block builder | Test coverage |

## Constraints

- No new dependencies — solo pdfplumber, pandas, openpyxl (ya presentes)
- Backward compatible — PDFValidator, PDFExtractor, PDFReconciler no cambian interface
- El router es un layer ENCIMA del stack existente, no un rewrite
- Form 8990 se detecta y se skipea (out of scope para este modulo)
- Schedule E Detail pages: intentar parsear, flag si falla
- Performance: no releer paginas ya leidas — cachear text entre scan y extraction

## Calibration Results (2026-09-04)

### Client-A FY25 (canopius-fy25-all-forms-print.pdf, 1,070 pages)
- **Scanner**: 38 entities, 902 classified, 168 skipped, 0 unrecognized (100%)
- **Route (E, I1, J)**: 438 comparisons, 300 discrepancies (113 phantoms)
- **Duration**: scan 167s, route+extract+reconcile 262s total
- **Entity completeness**: 35 matched, 29 missing (Client-B/Client-C — expected)

### Client-B FY25 (solidus-fy25-all-forms-print.pdf, 854 pages)
- **Scanner**: 28 entities, 694 classified, 160 skipped, 0 unrecognized (100%)
- **Route (E, I1, J)**: 420 comparisons, 324 discrepancies (111 phantoms)
- **Duration**: route total 171s
- **Entity completeness**: 26 matched, 2 extra (D56288, NN17)

### Issues Found and Fixed
| # | Issue | Fix Applied |
|---|-------|-------------|
| C1 | Schedule F classified as G (multi-schedule pages) | Use earliest match position, not first-match-in-list |
| C2 | Schedule Q (CFC Income Groups) unrecognized | Added Q pattern + canonical mapping |
| C3 | Schedule M (Transactions) unrecognized | Added M pattern + canonical mapping |
| C4 | Schedule O (Reorganization) unrecognized | Added O pattern + canonical mapping |
| C5 | Entity names "Filed Pursuant..." / "Final Return" | Extended exclusion list in first-line fallback |
| C6 | Form 5471/8858 Detail pages unrecognized | Added detail/statement page detection → skip |
| C7 | Dormant FDE (Announcement 2004-4) unrecognized | Added dormant_fde detection → skip |
| C8 | 8858 page 1 (no schedule) unrecognized | Map to 8858_G as default |

### Known Limitations
- **Schedules A, B, C, F, H, P, R**: Extractors return empty on batch PDF pages.
  Pre-existing layout issue — not a router problem. Extractor calibration needed.
- **Schedule I**: No pages detected (all classify as I-1/GILTI instead of plain I).
  Client-A may not have standalone Schedule I pages.
- **High phantom/missing in E, I1**: Likely entity ref_id alignment issue between
  extractor output and reconciler XML matching. Needs investigation.

## Verification

1. `PDFRouter.scan()` produce un PageMap con 28+ entidades del PDF de Client-A — PASS (38)
2. Entity names son correctos (ENTITY ALPHA LTD, not "for example, Form 5471") — PASS
3. Schedule detection completo por entidad (J, F, H, I1, etc.) — PASS (15 schedule types)
4. Form 8990 pages clasificadas correctamente — PASS (skipped)
5. `PDFRouter.route()` produce BatchValidationResult con per-schedule reports — PASS
6. Entity completeness check identifica entities en XML no presentes en PDF — PASS
7. Consolidated Excel tiene dashboard + per-schedule sheets — PASS
8. All existing tests continue to pass — PASS (608 tests)
9. 100% page coverage on both Client-A (1,070) and Client-B (854) — PASS

## File Structure

```
lab/pdf_validator/
  router.py          — NEW: PDFRouter class + page classifier
  models.py          — MODIFIED: add PageMap, EntityBlock, BatchValidationResult
  extractor.py       — MODIFIED: add pages parameter for filtered extraction
  scanner.py         — MODIFIED: fix entity parsing, schedule detection
  report.py          — MODIFIED: add consolidated report format
  __init__.py        — MODIFIED: export PDFRouter, new models
  validator.py       — UNCHANGED
  reconciler.py      — UNCHANGED
  comparator.py      — UNCHANGED
  config.py          — UNCHANGED
  layouts/*.py       — UNCHANGED (may need minor calibration from real data)
```

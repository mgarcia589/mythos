# Spec: PDF Analyzer Expansion — Scan, PDF-vs-PDF, Form 8858

> Expande el módulo `lab/pdf_validator/` con tres capacidades nuevas:
> detección automática de contenido (scan), comparación PDF CY vs PDF PY,
> y soporte para Form 8858 FDE/FB.

## Outcomes

1. **Scan Mode** — Un pass rápido que inventaría el contenido de un PDF sin extraer
   toda la data: cuántas forms, qué schedules, cuántas entidades, qué ref IDs.
2. **PDF vs PDF Comparison** — Comparar dos PDFs del mismo schedule (PY vs CY)
   campo-a-campo, produciendo un reporte de diferencias con deltas.
3. **Form 8858 Support** — Extraer y reconciliar schedules de Form 8858
   (Sch C Income, Sch F Balance Sheet, Sch H E&P) desde PDFs generados por OIT.

## In-Scope

### Phase 1: Scan Mode

- `PDFScanner` class con método `scan(pdf_path) -> ScanResult`
- Detección de form type: 5471 vs 8858 (por keywords en headers)
- Detección de schedules presentes (J, F, H, I-1, C, G, etc. para 5471;
  Sch C, F, H para 8858)
- Inventario de entidades: ref_id, name, country (por header parsing)
- Page count por entity/schedule
- Modo lightweight — solo text extraction, no table parsing
- Output: `ScanResult` dataclass con metadata completa

### Phase 2: PDF vs PDF Comparison

- `PDFComparator` class con método `compare(py_pdf, cy_pdf, schedule) -> PDFComparisonReport`
- Reutiliza `PDFExtractor` para ambos PDFs
- Matching por `(reference_id, basket, field_name)`
- Clasificación: UNCHANGED, CHANGED, NEW_IN_CY, DROPPED_FROM_PY
- Threshold configurable (default: $1 — más estricto que PDF vs XML)
- Reporte con: entity, field, PY value, CY value, delta, status
- Excel export via `write_report_excel` existente (adaptado)

### Phase 3: Form 8858 Layouts

- Nuevos page detection patterns para 8858 schedules
- Layout modules: `layouts/schedule_8858_c.py`, `layouts/schedule_8858_f.py`,
  `layouts/schedule_8858_h.py`
- Extractor routing: `PDFExtractor(pdf, schedule="8858_C")`
- Reconciler: `_parse_xml_8858_*()` methods que usan `EFileParser.extract_form_8858()`
- 8858 Sch C: dual-amount pattern (FC + USD) — extract both columns
- 8858 Sch F: BOY/EOY like 5471 Sch F but different line items
- 8858 Sch H: E&P calculation with exchange rate

## Out-of-Scope

- Form 8865 (Partnership) — future phase
- Schedule M (8858 transactions between FDE and tax owner) — complex nested layout
- OCR for scanned PDFs — only machine-readable OIT exports
- PDF generation — read-only module

## Constraints

- pdfplumber como única dependencia de PDF (ya presente)
- Zero coupling con xml_parser/review_engine — el PDF validator es independiente
- Backward compatible: `PDFValidator`, `PDFExtractor`, `PDFReconciler` no cambian signature
- OIT-specific: los layouts asumen formato Thomson Reuters ONESOURCE
- Interleaved "m" spacer handling aplica a 8858 igual que a 5471

## Prior Decisions

- El extractor usa pdfplumber table detection + text fallback (ya probado)
- Header parsing reutiliza `_parse_schf_header()` pattern (entity name + ref ID via "m" spacers)
- DataFrame schema normalizado: `entity_name, reference_id, basket, pool_name, field_name, value`
- El reconciler clasifica: OK, PHANTOM, MISSING, MISMATCH (con severity)

## Task Breakdown

### Phase 1: Scan Mode (5 tasks)

| # | Task | Output |
|---|------|--------|
| 1.1 | Crear `ScanResult` y `EntityInfo` dataclasses en models.py | Modelos |
| 1.2 | Crear `PDFScanner` class en `scanner.py` | Scan logic |
| 1.3 | Implementar form type detection (5471 vs 8858 keywords) | Detection |
| 1.4 | Implementar schedule detection + entity inventory | Inventory |
| 1.5 | Tests + integración con `__init__.py` | Tests |

### Phase 2: PDF vs PDF Comparison (4 tasks)

| # | Task | Output |
|---|------|--------|
| 2.1 | Crear `PDFComparisonReport` y `ComparisonItem` models | Modelos |
| 2.2 | Crear `PDFComparator` class en `comparator.py` | Compare logic |
| 2.3 | Matching logic: align PY entities with CY entities | Alignment |
| 2.4 | Tests con fixtures (mock PY/CY DataFrames) + Excel export | Tests |

### Phase 3: Form 8858 Layouts (5 tasks)

| # | Task | Output |
|---|------|--------|
| 3.1 | Page detection patterns para 8858 (Sch C, F, H) | Patterns |
| 3.2 | `layouts/schedule_8858_c.py` — income statement dual-amount | Layout |
| 3.3 | `layouts/schedule_8858_f.py` — balance sheet BOY/EOY | Layout |
| 3.4 | `layouts/schedule_8858_h.py` — E&P with FX rate | Layout |
| 3.5 | Extractor routing + reconciler XML parsing for 8858 | Integration |

## Data Models

### ScanResult (Phase 1)

```python
@dataclass
class EntityInfo:
    reference_id: str
    name: str
    country: str = ""
    schedules_present: list[str] = field(default_factory=list)
    page_range: tuple[int, int] = (0, 0)

@dataclass
class ScanResult:
    file_path: str
    total_pages: int
    form_types: set[str]           # {"5471", "8858"}
    schedules_detected: set[str]   # {"J", "F", "H", "I1", "8858_C", ...}
    entities: list[EntityInfo]
    entity_count: int
    scan_duration_ms: float
```

### PDFComparisonReport (Phase 2)

```python
@dataclass
class ComparisonItem:
    entity_name: str
    reference_id: str
    basket: str
    schedule: str
    field: str
    field_description: str
    py_value: float
    cy_value: float
    delta: float
    status: str  # "UNCHANGED", "CHANGED", "NEW_IN_CY", "DROPPED_FROM_PY"

@dataclass
class PDFComparisonReport:
    schedule: str
    py_source: str
    cy_source: str
    items: list[ComparisonItem]
    # Properties: total, unchanged, changed, new_count, dropped_count
```

## 8858 Page Detection Keywords

```python
# Form 8858 main page
FORM_8858_PATTERNS = [
    re.compile(r"Form\s*8858|Information\s+Return.*Disregarded", re.IGNORECASE),
    re.compile(r"Foreign\s+Disregarded\s+Entity|Foreign\s+Branch", re.IGNORECASE),
]

# 8858 Schedule C (Income Statement)
SCH_8858_C_PATTERNS = [
    re.compile(r"Form\s*8858|8858", re.IGNORECASE),
    re.compile(r"Income\s+Statement|Schedule\s*C", re.IGNORECASE),
]

# 8858 Schedule F (Balance Sheet)
SCH_8858_F_PATTERNS = [
    re.compile(r"Form\s*8858|8858", re.IGNORECASE),
    re.compile(r"Balance\s+Sheet|Schedule\s*F", re.IGNORECASE),
]

# 8858 Schedule H (E&P)
SCH_8858_H_PATTERNS = [
    re.compile(r"Form\s*8858|8858", re.IGNORECASE),
    re.compile(r"Current\s+Earnings|Schedule\s*H", re.IGNORECASE),
]
```

Disambiguation entre 5471 y 8858 when both have "Schedule F" or "Schedule H":
- Si la página contiene "Form 8858" o "Disregarded Entity" → 8858
- Si contiene "Form 5471" o "Controlled Foreign" → 5471
- Fallback: contexto de páginas anteriores (same form type runs consecutively)

## 8858 Schedule C Field Map (dual-amount)

OIT renders 8858 Sch C with two amount columns per line:
- Column 1: Functional Currency amount
- Column 2: USD amount (translated)

```python
SCHEDULE_8858_C_LINES = [
    ("1a", "GrossReceiptsOrSalesIncmStmt", "Gross receipts or sales"),
    ("1b", "ReturnsAndAllowancesAmt", "Returns and allowances"),
    ("1c", "NetGrossReceiptsAmt", "Net gross receipts (1a - 1b)"),
    ("2", "CostOfGoodsSoldAmt", "Cost of goods sold"),
    ("3", "GrossProfitAmt", "Gross profit (1c - 2)"),
    # ... (rest of income/deduction lines)
    ("21", "NetIncomeLossPerIncomeStmt", "Net income (loss)"),
]
```

## Verification Criteria

1. `PDFScanner.scan(pdf)` returns correct form_type, schedule count, entity count
   on existing test fixtures (5471 Sch J batch PDF)
2. `PDFComparator.compare(py_pdf, cy_pdf, "F")` correctly identifies CHANGED fields
   where PY EOY ≠ CY BOY, and UNCHANGED where they match
3. `PDFExtractor(pdf, schedule="8858_C").extract()` returns DataFrame with
   both FC and USD amounts for each line item
4. All existing tests continue to pass (backward compat)
5. `python -m pytest lab/tests/ -v` — all green including new tests

## Usage Examples

```python
from lab.pdf_validator import PDFScanner, PDFComparator, PDFValidator

# Phase 1: Scan
scanner = PDFScanner("sources/client/batch-export.pdf")
result = scanner.scan()
print(f"Forms: {result.form_types}")
print(f"Entities: {result.entity_count}")
for e in result.entities:
    print(f"  {e.reference_id}: {e.name} — schedules: {e.schedules_present}")

# Phase 2: PDF vs PDF
comparator = PDFComparator(
    py_pdf="sources/client/schf-fy24.pdf",
    cy_pdf="sources/client/schf-fy25.pdf",
    schedule="F",
)
report = comparator.compare()
print(f"Changes: {report.changed_count} of {report.total}")
for item in report.changes:
    print(f"  {item.reference_id} {item.field}: {item.py_value} → {item.cy_value} (Δ{item.delta:,.0f})")

# Phase 3: 8858 PDF vs XML
validator = PDFValidator(
    pdf_path="sources/client/8858-schf-fy25.pdf",
    xml_path="sources/client/efile-fy25.xml",
    schedule="8858_F",
)
report = validator.validate()
print(report.summary)
```

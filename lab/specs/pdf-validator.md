# Spec: PDF Validator — Visual Candado de Reconciliación

> Part of Project Mythos — módulo de validación visual que extrae datos de PDFs
> exportados de OIT y los reconcilia contra el XML, actuando como second check
> independiente. Resuelve el gap donde el XML puede no reflejar el estado actual
> de OIT (ej: C0002 Section 951A PTEP con balance 92 en OIT que no aparece en XML).

## Motivación

El XML es generado por OIT en un punto en el tiempo. Si un valor se modifica en
OIT después de la exportación del XML (o si el XML tiene un bug de exportación),
Mythos no puede detectar la discrepancia porque solo ve XMLs.

El PDF, en cambio, refleja el estado **actual** de OIT al momento de exportar. Al
comparar PDF vs XML, se crea un candado cruzado:

```
VALIDATED = XML_Rollover_Check PASS  +  PDF_vs_XML_Check PASS
```

Si el XML dice 0 pero el PDF dice 92, Mythos lo flaggea como discrepancia —
independientemente de si el rollover PY→CY "pasa" en XML.

## Outcomes

1. **Extraer datos de PDFs de OIT** (Schedule J, F, H, I-1) con precisión >99%
2. **Reconciliar PDF vs XML** por entidad/schedule/campo — cualquier delta ≥$10 → flag
3. **Detectar "phantom data"** — valores presentes en PDF pero ausentes en XML (y viceversa)
4. **Producir reporte de discrepancias** en formato estándar Mythos (Excel + terminal)
5. **Actuar como candado** — una validación completa requiere AMBOS checks:
   - Check A: XML PY→CY rollover (ya implementado)
   - Check B: PDF vs XML reconciliation (este módulo)

## Scope

### Phase 1: Schedule J (MVP — resuelve el caso C0002)

- Input: PDF batch export de Schedule J desde OIT (un PDF con todas las entities)
- Extraction: Cada entity/basket → pools (col a through j) → row values
- Reconciliation: PDF col(a) vs XML BeginningYearBalanceAmt por pool
- Output: Discrepancias con entity, pool, PDF value, XML value, delta

### Phase 2: Schedule F Balance Sheet

- Input: PDF batch export de Schedule F
- Extraction: BOY/EOY amounts por entity por line item
- Reconciliation: PDF vs XML balance sheet lines

### Phase 3: Schedule H + I-1

- Input: PDFs de Sch H y Sch I-1
- Extraction: E&P calculation lines, GILTI tested income/loss
- Reconciliation: PDF vs XML income/deduction lines

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     PDF Validator Module                          │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────────┐│
│  │ PDF Ingester│──▶│ Table Parser │──▶│  Structured DataFrames ││
│  │ (pdfplumber)│   │ (layout-aware)│   │  (entity/pool/field)  ││
│  └─────────────┘   └──────────────┘   └───────────┬───────────┘│
│                                                     │            │
│                                        ┌────────────▼──────────┐│
│                                        │  Reconciliation Engine ││
│                                        │  PDF data vs XML data  ││
│                                        └────────────┬──────────┘│
│                                                     │            │
│                                        ┌────────────▼──────────┐│
│                                        │  Discrepancy Report    ││
│                                        │  (Excel + terminal)    ││
│                                        └───────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

## Input Formats

### OIT PDF Structure (Schedule J)

OIT exports Schedule J como un reporte paginado con este layout:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Schedule J - Accumulated E&P of CFC                                 │
│ Sample Client LP                                │
│ Tax Year: 12/31/2025                                                │
│ Entity: ALPHA TOPCO LTD (C0002) | FC: GBP | Basket: General      │
├─────────────────────────────────────────────────────────────────────┤
│ Col │ Description              │  Beg Bal │ Adj Beg │ CY E&P │ ... │
│ (a) │ Post-2017 Not Prev Taxed │ -15,272  │ -15,272 │   1    │     │
│ (b) │ Post-2017 Prev Taxed     │        0 │       0 │        │     │
│ (c) │ Section 951A PTEP        │       92 │      92 │        │     │
│ ... │                          │          │         │        │     │
└─────────────────────────────────────────────────────────────────────┘
```

Características:
- Una sección por entity/basket (page break or separator)
- Header identifica entity (name + ref_id), FC, basket
- Tabla con columnas fijas: Col letter, Description, then row amounts
- Amounts en formato numérico con comas, negativos con paréntesis o signo
- OIT genera PDFs con texto seleccionable (no son scans/imágenes)

### OIT PDF Structure (Schedule F)

Similar estructura tabular con:
- Entity header (name, ref_id, FC)
- Line items: Asset/Liability/Equity lines
- BOY and EOY columns

## Logic

### PDF Extraction Pipeline

```python
class PDFExtractor:
    """Extract structured data from OIT-generated PDF reports."""
    
    def __init__(self, pdf_path: Path, schedule: str):
        self.path = pdf_path
        self.schedule = schedule  # "J", "F", "H", "I1"
    
    def extract(self) -> pd.DataFrame:
        """Extract all data from PDF into structured DataFrame.
        
        Returns DataFrame with columns:
          - entity_name: str
          - reference_id: str  
          - basket: str (for Sch J)
          - field_name: str (pool name or line item)
          - column: str ("beg_bal", "adj_beg", "cy_ep", "end_bal", etc.)
          - value: float
        """
        ...
```

### Entity Detection in PDF

```python
# Patterns to identify entity sections in PDF
ENTITY_PATTERNS = [
    r"Entity:\s*(.+?)\s*\((\w+)\)",           # "Entity: ALPHA TOPCO LTD (C0002)"
    r"Foreign Corporation:\s*(.+?)\s*[-|]\s*(\w+)",  # alternate format
]

# Basket detection
BASKET_PATTERNS = [
    r"Basket:\s*(General|Passive)",
    r"Category:\s*(General Limitation|Passive)",
    r"Separate Category.*?(GEN|PAS|General|Passive)",
]
```

### Table Extraction Strategy

```python
# pdfplumber table settings optimized for OIT exports
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines", 
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "min_words_vertical": 1,
}

# If lines-based fails, fall back to text-based
FALLBACK_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 5,
}
```

### Reconciliation Logic

```python
class PDFReconciler:
    """Compare PDF-extracted data against XML-parsed data."""
    
    def __init__(self, pdf_data: pd.DataFrame, xml_path: Path):
        self.pdf = pdf_data
        self.xml = self._parse_xml(xml_path)
    
    def reconcile(self) -> ReconciliationReport:
        """Compare every PDF value against corresponding XML value.
        
        For each (entity, basket, pool, field):
          pdf_val = value from PDF extraction
          xml_val = value from XML parsing
          delta = pdf_val - xml_val
          
          if abs(delta) < 10:  status = "OK"
          elif pdf_val != 0 and xml_val == 0:  status = "PHANTOM" (in PDF not XML)
          elif pdf_val == 0 and xml_val != 0:  status = "MISSING" (in XML not PDF)
          else:  status = "MISMATCH"
        """
        ...
```

### Status Classification

| Status | Meaning | Severity | Example |
|--------|---------|----------|---------|
| OK | PDF ≈ XML (delta < $10) | None | Normal agreement |
| PHANTOM | PDF has value, XML = 0 or absent | HIGH | C0002 Sec 951A = 92 in PDF, 0 in XML |
| MISSING | XML has value, PDF = 0 or absent | HIGH | Data in XML not showing in OIT |
| MISMATCH | Both have values but differ ≥ $10 | MEDIUM | Rounding, timing, or data error |

**PHANTOM es el caso más peligroso** — indica que OIT tiene datos que el XML
(y por ende Mythos) no puede ver. El rollover check dice PASS pero hay un gap real.

## Output Structure

```python
@dataclass
class PDFDiscrepancy:
    entity_name: str
    reference_id: str
    basket: str
    schedule: str          # "J", "F", "H", "I1"
    field: str             # pool name, line item, etc.
    pdf_value: float
    xml_value: float
    delta: float
    status: str            # "OK", "PHANTOM", "MISSING", "MISMATCH"
    severity: str          # "HIGH", "MEDIUM", "LOW"

@dataclass  
class PDFValidationReport:
    schedule: str
    pdf_source: str
    xml_source: str
    total_comparisons: int
    ok_count: int
    phantom_count: int     # IN PDF, NOT IN XML — most dangerous
    missing_count: int     # IN XML, NOT IN PDF
    mismatch_count: int
    discrepancies: list[PDFDiscrepancy]
    entities_checked: int
    entities_with_issues: list[str]
    summary: str
```

## API

```python
from lab.pdf_validator import PDFValidator

# Single schedule validation
validator = PDFValidator(
    pdf_path="path/to/schedule-batch.pdf",
    xml_path="path/to/return.xml",
    schedule="J",
)
report = validator.validate()

# Access results
print(report.summary)
print(f"Phantoms: {report.phantom_count}")  # Data in OIT not in XML
for d in report.discrepancies:
    if d.status == "PHANTOM":
        print(f"  {d.entity_name} | {d.field} | PDF={d.pdf_value} | XML={d.xml_value}")

# Full validation (all schedules)
full = PDFValidator.full_validation(
    pdf_dir="path/to/pdf-exports/",
    xml_path="path/to/return.xml",
)

# Export to Excel
report.to_excel("Desktop/Outputs/pdf-validation-report.xlsx")
```

## Integration with Existing Mythos Workflow

### Validation Candado

```python
from lab.xml_parser.reports import ReportEngine
from lab.pdf_validator import PDFValidator

# Step 1: XML rollover check (existing)
engine = ReportEngine(prior_xml="cb-fy24.xml", current_xml="cb-fy25-v15.xml")
xml_report = engine.sch_j_gen_rollover()

# Step 2: PDF vs XML check (new)
validator = PDFValidator(pdf_path="schj-batch.pdf", xml_path="cb-fy25-v15.xml", schedule="J")
pdf_report = validator.validate()

# Step 3: Combined validation
validated = (xml_report.failed == 0) and (pdf_report.phantom_count == 0 and pdf_report.mismatch_count == 0)
print(f"FULLY VALIDATED: {validated}")
# If False, the specific failures indicate WHERE to look
```

### Report Output (Excel — per spec 00-report-standards)

```
Sheet 1: "Summary"
  - Header estándar (Client, Engagement, Report, Comparison, Generated)
  - Results overview: total comparisons, OK, PHANTOM, MISSING, MISMATCH
  - Material discrepancies table (sorted by severity then delta)

Sheet 2: "Phantom Data" (HIGH priority)
  - Entity | Basket | Pool/Field | PDF Value | XML Value | Notes
  - These are items in OIT that the XML doesn't reflect

Sheet 3: "Mismatches"
  - Entity | Basket | Pool/Field | PDF Value | XML Value | Delta | %

Sheet 4: "All Comparisons"
  - Full detail for audit trail
```

## Constraints

- Solo PDFs generados por OIT (texto seleccionable, no OCR needed)
- pdfplumber como parser primario (MIT license, pure Python, good table extraction)
- Fallback: si pdfplumber no puede parsear tablas, usar regex line-by-line
- Numbers con formato US: comas = thousands separator, period = decimal
- Negativos: "(1,234)" o "-1,234" — ambos formatos posibles
- Entity matching: by reference_id (C0002, AM01, etc.) — case insensitive
- Tolerance: $10 (same as XML rollover check per spec 00-report-standards)
- Performance: un batch PDF típico (~70 entities × 2 baskets) debe procesar en <30s
- El módulo NO modifica datos — es read-only/validation

## Edge Cases

1. **Entity in PDF but not in XML** → flag as "Entity not in XML" (informational)
2. **Entity in XML but not in PDF** → flag as "Entity not exported" (check PDF completeness)
3. **Pool exists in PDF with value, absent in XML** → PHANTOM (the C0002 case)
4. **PDF has "(0)" or blank vs XML has "0"** → treat as equal (OK)
5. **PDF amounts rounded to nearest dollar vs XML exact** → tolerance handles this
6. **Multi-page entities** (large entities span pages) → concatenate before parsing
7. **Basket not identified in PDF header** → try to infer from pool values, else flag

## Dependencies

```
pdfplumber>=0.10.0    # PDF table extraction
pandas>=2.0           # DataFrames
openpyxl>=3.1         # Excel output
```

## Verification

- [ ] Extract Schedule J data from OIT batch PDF for Sample Client (66+ entities)
- [ ] Match extracted values to XML values by entity/basket/pool
- [ ] Detect the C0002 PHANTOM case (92 in PDF, 0 in XML for Section951APTEPGrp)
- [ ] Handle both GEN and PAS baskets correctly
- [ ] Report output follows spec 00-report-standards (header, color coding, formatting)
- [ ] No false positives from rounding or format differences
- [ ] Process full batch PDF in under 30 seconds
- [ ] Graceful handling when PDF layout is unexpected (log warning, skip entity, continue)

## File Structure

```
lab/
  pdf_validator/
    __init__.py          — Public API (PDFValidator class)
    extractor.py         — PDF parsing and table extraction
    reconciler.py        — PDF vs XML comparison logic
    report.py            — Output formatting (Excel, terminal)
    layouts/
      schedule_j.py      — Sch J specific extraction rules
      schedule_f.py      — Sch F specific extraction rules (Phase 2)
      schedule_h.py      — Sch H specific extraction rules (Phase 3)
```

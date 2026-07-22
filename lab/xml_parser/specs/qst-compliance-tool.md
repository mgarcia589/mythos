# Spec: Project Mythos — IRS e-File Compliance Analysis Tool

> Supersedes: `xml-parser.md` (Phase 1 — parsing only)

## Outcomes

Una herramienta integral de análisis de compliance data para US International Tax que permite:

1. **Parsear** cualquier IRS e-file XML en DataFrames estructurados
2. **Comparar XML vs XML** — rollover review (PY→CY), draft vs final
3. **Comparar XML vs Workbook** — reconciliar cálculos (E&P, Sub F, GILTI) entre lo filed y lo calculado
4. **Análisis profundo de un solo XML** — completeness, anomalías, reasonableness checks
5. **Generar reportes profesionales** — Excel (XlsxWriter), HTML (great-tables), PDF (reportlab/WeasyPrint)

El usuario final es un **associate o senior en international tax compliance** que quiere:
- Validar que el rollover de PY a CY fue correcto
- Identificar rápidamente qué cambió y por qué
- Reconciliar sus workbooks contra el XML final
- Documentar hallazgos para el reviewer/manager

## Scope

### In-Scope

**Parsing (ya construido)**
- IRS e-file namespace `http://www.irs.gov/efile`
- Return types: 1120, 1065
- Forms: 5471 (A-R), 8858, 8865, 8992, 1118
- Multi-subsidiary returns (100+ entities)

**Comparación XML vs XML (ya construido — refinar)**
- Rollover checks: Sch F, Sch J, Page 1, Sch G indicators
- Movement analysis: E&P (Sch H), GILTI (Sch I-1)
- Entity changes: new/removed CFCs
- Draft vs final: detect last-minute adjustments

**Comparación XML vs Workbook (nuevo)**
- E&P reconciliation: XML Sch H vs workbook Sch H column
- Sub F reconciliation: XML vs workbook de minimis/Sub F summary
- GILTI reconciliation: XML Sch I-1 vs workbook GILTI page
- 163(j) reconciliation: XML indicators vs workbook calculations
- Tolerance-based matching (rounding ±1, FX conversions)

**Análisis profundo de un solo XML (nuevo)**
- Completeness check: ¿todas las entities tienen todos los schedules requeridos?
- Reasonableness: assets negativos, E&P inconsistencies, missing required fields
- Anomaly detection: outliers en tested income, unusual FX rates, zero-balance entities
- Cross-schedule validation: Sch H total = Sch J movement, Sch F assets = liabilities + equity

**Reportes (refinar)**
- Summary dashboard (pass/fail by category)
- Detail drill-down por entity
- Comparative tables PY vs CY
- Reconciliation tables XML vs Workbook
- Export: Excel, HTML (great-tables), PDF branded, CSV

### Out-of-Scope

- Generar o modificar XML (read-only)
- IRS e-filing/transmission
- State returns
- Cálculos propios de tax (no calcula GILTI — solo compara)
- GUI/web app (CLI + scripts por ahora)

## Constraints

- Python 3.12+
- Core: lxml, pandas, numpy
- Output: xlsxwriter, great-tables, reportlab
- Future: weasyprint (HTML→PDF), typst (template PDF)
- Performance: < 5s parse, < 3s compare, < 10s full analysis
- Must handle XML up to 15MB (100+ entities × all schedules)
- Output column naming compatible con Alteryx legacy format
- PwC brand compliance en outputs profesionales

## Architecture

```
lab/xml_parser/
  __init__.py          — Public API exports
  parser.py            — EFileParser: XML → DataFrame (done)
  comparator.py        — XMLComparator: XML vs XML delta (done)
  reports.py           — ReportEngine: predefined rollover checks (done — refine)
  analyzer.py          — NEW: Single-XML deep analysis
  reconciler.py        — NEW: XML vs Workbook reconciliation
  field_maps.py        — Field definitions + rollover pairs (done — expand)
  output.py            — Excel/PDF exporters (done — improving)
  gt_output.py         — great-tables HTML output (done — improving)
  form_view.py         — Rich terminal form rendering (done)
  cli.py               — CLI interface (fix pending)
  README.md            — User guide (done)
```

## Modules — Detailed Design

### 1. Reports (refine existing)

Cada reporte se redefine como un módulo independiente con:
- Input claro (qué data necesita)
- Logic explícita (qué compara, qué tolera)
- Output estandarizado (status, findings, metrics)
- Visual propio (cómo se renderiza en cada formato)

**Reports a definir uno por uno:**
- [ ] Sch F Rollover
- [ ] Sch J Rollover  
- [ ] Page 1 Static Data
- [ ] E&P Movement (Sch H YoY)
- [ ] GILTI Comparison (Sch I-1 YoY)
- [ ] Entity Changes (New/Removed)
- [ ] Sch G Indicator Changes
- [ ] Full Review Package

### 2. Analyzer (new module)

```python
class XMLAnalyzer:
    def __init__(self, xml_path: str):
        ...
    
    def completeness_check(self) -> CompletenessReport
    def reasonableness_check(self) -> ReasonablenessReport
    def anomaly_detection(self) -> AnomalyReport
    def cross_schedule_validation(self) -> ValidationReport
    def full_analysis(self) -> FullAnalysisReport
```

### 3. Reconciler (new module)

```python
class WorkbookReconciler:
    def __init__(self, xml_path: str, workbook_path: str):
        ...
    
    def reconcile_ep(self, xml_schedule: str, wb_sheet: str, wb_column: str) -> ReconciliationReport
    def reconcile_subf(self) -> ReconciliationReport
    def reconcile_gilti(self) -> ReconciliationReport
    def full_reconciliation(self) -> FullReconciliationReport
```

## Verification Criteria

- [ ] Cada reporte tiene spec individual aprobada antes de implementar
- [ ] Output visual revisado y aprobado en cada formato (Excel, HTML, PDF)
- [ ] Corre contra 6+ XMLs de clientes distintos sin error
- [ ] Reconciler matchea 100% contra auditoría manual previa (Centerbridge)
- [ ] Analyzer detecta los 6 bugs conocidos del workbook CB cuando se corre contra el XML
- [ ] Performance < 10s para full_analysis + full_review en XML de 100 entities
- [ ] Cada formato de output tiene look profesional aprobado

## Development Plan

1. **Redefinir reportes** (uno por uno, spec→implement→visual review)
2. **Mejorar outputs** (great-tables styling, Excel formatting, PDF layout)
3. **Agregar Analyzer** (completeness + reasonableness + anomalies)
4. **Agregar Reconciler** (XML vs Workbook)
5. **WeasyPrint integration** (HTML→PDF con CSS templates)
6. **Typst templates** (final PDF quality tier)

## Prior Decisions

- Spec-driven: cada componente se define antes de implementar
- Iterativo: un reporte a la vez, visual review entre cada uno
- great-tables para tablas → WeasyPrint para PDF (HTML como intermediate)
- XlsxWriter para Excel profesional
- reportlab como fallback PDF (ya funcional)
- PwC brand palette hardcoded (#D04A02 orange, etc.)

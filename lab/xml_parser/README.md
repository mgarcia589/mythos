# Project Mythos

**Automated compliance analysis for US International Tax e-file returns.**

Mythos parsea, compara y valida IRS e-file XMLs en segundos — reemplazando horas
de rollover review manual, reconciliaciones en Excel, y QC line-by-line.

---

## What It Is

Project Mythos es una herramienta de analisis que transforma XML crudo de IRS
e-file returns en informacion accionable para el reviewer de compliance:

1. **Parse** — Extrae cualquier form/schedule de un XML a DataFrames estructurados
2. **Compare** — Compara PY vs CY campo por campo, flaggea material changes
3. **Review** — Corre 7 rollover checks automatizados con pass/fail por entidad
4. **Report** — Genera output profesional (Excel, HTML, PDF) con branding PwC

**Replaces**: BOLT (Alteryx), QST Parser v3.exe, manual Excel rollover reviews.

---

## Why "Mythos"

Porque construye la narrativa estructurada detras de cada return — transforma
miles de XML nodes en una historia coherente de compliance que el reviewer puede
seguir, cuestionar y documentar.

---

## Quick Start

```bash
# List all entities in an XML
python -m lab.xml_parser list "path/to/file.xml"

# Parse all schedules to Excel
python -m lab.xml_parser parse "path/to/file.xml"

# Compare PY vs CY (rollover review)
python -m lab.xml_parser compare "PY.xml" "CY.xml"

# Full rollover review package (all 7 reports + Excel + HTML)
python -m lab.xml_parser review "PY.xml" "CY.xml"
```

---

## Commands

### `list` — Quick Entity Scan

```bash
python -m lab.xml_parser list "CB - 25.xml"
```

Shows: Entity name, Reference ID, Country, Functional Currency, Dormant status.
Time: < 1 second.

### `parse` — Extract to Excel

```bash
python -m lab.xml_parser parse "CB - 25.xml"
python -m lab.xml_parser parse "CB - 25.xml" --form IRS5471ScheduleH
python -m lab.xml_parser parse "CB - 25.xml" --entity "C0004"
```

Output: Excel file with one tab per schedule. Rows = entities, Columns = form fields.
Time: < 2 seconds for 66 entities.

### `compare` — Field-Level Comparison

```bash
python -m lab.xml_parser compare "PY.xml" "CY.xml"
python -m lab.xml_parser compare "PY.xml" "CY.xml" --threshold 5000000
python -m lab.xml_parser compare "PY.xml" "CY.xml" --form IRS5471ScheduleF
```

Shows: Added/removed entities, field-by-field changes, material changes highlighted.

### `review` — Full Rollover Review Package

```bash
python -m lab.xml_parser review "PY.xml" "CY.xml"
python -m lab.xml_parser review "PY.xml" "CY.xml" --client "Centerbridge"
python -m lab.xml_parser review "PY.xml" "CY.xml" --format html
python -m lab.xml_parser review "PY.xml" "CY.xml" --format pdf
```

Runs all 7 automated checks:
- Schedule F Rollover (PY End = CY Begin)
- Schedule J Rollover (Accumulated E&P pools)
- Page 1 Rollover (Entity info unchanged)
- E&P Movement (Schedule H YoY)
- GILTI Comparison (Schedule I-1 YoY)
- Entity Changes (New/Removed CFCs)
- Schedule G Indicators (163(j), BEAT, Pillar Two flips)

Output: Terminal summary + Excel workbook + HTML report (optional PDF).

---

## Coverage

| Form/Schedule | What It Parses |
|---|---|
| **5471 Page 1** | Entity info, categories, ownership, addresses |
| **Schedule C** | Income statement (FC + USD) |
| **Schedule E** | Foreign taxes paid/accrued |
| **Schedule F** | Balance sheet (begin + end) |
| **Schedule G** | Yes/No indicators (163(j), BEAT, Pillar Two) |
| **Schedule H** | Earnings & Profits |
| **Schedule I** | Shareholder's income from CFC |
| **Schedule I-1** | GILTI (tested income, QBAI) |
| **Schedule J** | Accumulated E&P (PTEP layers, all baskets) |
| **Schedule P** | Previously taxed E&P |
| **Schedule Q** | CFC income by category/basket |
| **8858** | Disregarded entities |

---

## vs BOLT (Alteryx)

| | BOLT | Mythos |
|---|---|---|
| Setup | Open Alteryx, load .yxzp, configure | One command |
| Speed | ~5-10 min per schedule | < 2 seconds total |
| Comparison | Manual in Excel | Built-in `compare` + `review` |
| Output | Raw data dump | Formatted, branded, multi-format |
| License | Alteryx ($$$) | Python (free) |
| Sharing | Manual .xlsx | Auto-generates, ready to email |

---

## Architecture

```
lab/xml_parser/
  parser.py       — EFileParser: XML -> DataFrames
  comparator.py   — XMLComparator: XML vs XML delta
  reports.py      — ReportEngine: 7 automated rollover checks
  field_maps.py   — Field definitions + line numbers
  output.py       — Excel/PDF professional exporters
  gt_output.py    — great-tables HTML output
  form_view.py    — Rich terminal form rendering
  cli.py          — Click CLI interface
```

---

## Requirements

- Python 3.12+
- Core: `lxml`, `pandas`, `numpy`, `click`, `rich`
- Output: `xlsxwriter`, `great-tables`, `reportlab`
- Optional: `weasyprint` (HTML->PDF)

```bash
pip install lxml pandas numpy click rich xlsxwriter great-tables reportlab
```

---

## Programmatic Usage

```python
from lab.xml_parser import EFileParser, XMLComparator
from lab.xml_parser.reports import ReportEngine

# Parse
parser = EFileParser("file.xml")
df = parser.to_dataframe()

# Compare
comp = XMLComparator(threshold=5000)
report = comp.compare("py.xml", "cy.xml")

# Full review
engine = ReportEngine("py.xml", "cy.xml")
reports = engine.full_review()
```

---

## Roadmap

- [x] Parsing (all 5471 schedules)
- [x] XML vs XML comparison
- [x] 7 rollover reports
- [x] Professional output (Excel, HTML, PDF)
- [ ] Single-XML deep analysis (completeness, anomalies)
- [ ] XML vs Workbook reconciliation (E&P, Sub F, GILTI)
- [ ] WeasyPrint HTML->PDF pipeline

---

*Project Mythos | PwC US Tax LLP | Confidential*

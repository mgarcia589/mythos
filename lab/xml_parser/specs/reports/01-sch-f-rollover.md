# Spec: Report 01 — Schedule F Rollover

> Inherits: [[00-report-standards]] (headers, materialidad, formato tabular)

## Qué es

Schedule F (Form 5471) es el balance sheet de cada CFC en functional currency.
Tiene dos columnas: Beginning of Annual Accounting Period y End of Annual Accounting Period.

**Principio**: El ending balance del año anterior (PY) DEBE ser idéntico al beginning balance del año corriente (CY). Si no matchea, algo se corrompió en el rollover de OIT o hubo un ajuste manual no documentado.

## Outcomes

- Para cada entidad presente en ambos XMLs, comparar los 16 line items de Sch F
- Determinar PASS (match exacto o ±1 rounding) o FAIL (diferencia material)
- Cuantificar la diferencia en functional currency
- Clasificar severidad: rounding (±1-2), minor ($1-$1000), material (>$1000)
- Producir output limpio para reviewer con entity, line, PY value, CY value, diff

## Input

- `prior_xml`: Path al XML del año anterior (PY)
- `current_xml`: Path al XML del año corriente (CY)
- `tolerance`: Monto máximo para considerar "rounding" (default: $2)

## Logic

### Entity Matching
1. Buscar entities por `ReferenceIdNum` (más confiable)
2. Fallback: match por `BusinessNameLine1Txt` (normalizado)
3. Entities en PY pero no CY → flag como "removed/liquidated"
4. Entities en CY pero no PY → flag como "new CFC" (skip rollover check)

### Field Comparison (16 pairs)
Para cada entity matcheada, comparar:

| # | PY Ending Field | CY Beginning Field | Line Item |
|---|---|---|---|
| 1 | EndAcctPrdCashAmt | BegngAcctPrdCashAmt | Cash |
| 2 | EndAcctPrdTradeNotesAmt | BegngAcctPrdTradeNotesAmt | Trade notes & A/R |
| 3 | EndAcctPrdInventoriesAmt | BegngAcctPrdInventoriesAmt | Inventories |
| 4 | EndAcctPrdInvstSubsidiaryAmt | BegngAcctPrdInvstSubsidiaryAmt | Investment in subsidiaries |
| 5 | EndAcctPrdBldgAndOtherAstAmt | BegngAcctPrdBldgAndOtherAstAmt | Buildings & depreciable assets |
| 6 | EndAcctPrdLandAmt | BegngAcctPrdLandAmt | Land |
| 7 | EndAcctPrdPatentsOthAstAmt | BegngAcctPrdPatentsOthAstAmt | Intangible assets |
| 8 | EndAcctPrdOtherAssetsAmt | BegngAcctPrdOtherAssetsAmt | Other assets |
| 9 | EndAcctPrdTotalAssetsAmt | BegngAcctPrdTotalAssetsAmt | Total assets |
| 10 | EndAcctPrdAccountsPayableAmt | BegngAcctPrdAccountsPayableAmt | Accounts payable |
| 11 | EndAcctPrdOtherCurrLiabAmt | BegngAcctPrdOtherCurrLiabAmt | Other current liabilities |
| 12 | EndAcctPrdOthLiabilitiesAmt | BegngAcctPrdOthLiabilitiesAmt | Other liabilities |
| 13 | EndAcctPrdCommonStockAmt | BegngAcctPrdCommonStockAmt | Capital stock |
| 14 | EndAcctPrdPaidInOrSurplusAmt | BegngAcctPrdPaidInOrSurplusAmt | Paid-in surplus |
| 15 | EndAcctPrdRtnEarningsAmt | BegngAcctPrdRtnEarningsAmt | Retained earnings |
| 16 | EndAcctPrdTotLiabShrEqtyAmt | BegngAcctPrdTotLiabShrEqtyAmt | Total liabilities & equity |

### Comparison Logic
```
difference = cy_beginning - py_ending
if abs(difference) == 0 → PASS
if abs(difference) < 10  → FAIL (immaterial)
if abs(difference) >= 10 → FAIL (material)
```

### Severity Classification
- **Immaterial**: |diff| < $10 — acceptable (rounding, FX conversion artifacts)
- **Material**: |diff| ≥ $10 — requires explanation/investigation

### Cross-checks
- Total assets (line 9) should = sum of lines 1-8
- Total liabilities & equity (line 16) should = sum of lines 10-15
- Total assets (line 9) should = Total liabilities & equity (line 16)

## Output Structure

```python
@dataclass
class SchFRolloverItem:
    entity_name: str
    reference_id: str
    line_number: str          # "1" through "16"
    description: str          # "Cash", "Trade notes & A/R", etc.
    py_ending: float          # PY End value
    cy_beginning: float       # CY Begin value  
    difference: float         # cy_beginning - py_ending
    status: str               # "PASS" | "FAIL"
    severity: str             # "immaterial" | "material"

@dataclass
class SchFRolloverReport:
    items: list[SchFRolloverItem]
    total_checks: int
    passed: int
    failed: int
    entities_checked: int
    entities_with_issues: list[str]
    entities_removed: list[str]    # In PY but not CY
    entities_added: list[str]      # In CY but not PY
    summary: str                   # "Sch F Rollover: 325/339 pass, 14 immaterial diffs (<$10)"
```

## Modos de Reporte

### Modo 1: Single Entity
Reporte de UNA entidad específica — tabla columnar con las 16 líneas completas.
- Parámetro: `entity` (match por name o ref_id, case-insensitive, substring)
- Muestra TODOS los line items (pass y fail)
- Incluye cross-check (assets = liab + equity)
- Output: un archivo/tabla por entity
- Útil para: drill-down, responder pregunta de reviewer, documentar una entity problemática

### Modo 2: Batch — All Entities
Genera el reporte completo de TODAS las entidades de una sola vez.
- Una tabla columnar por cada entity (mismo formato que Modo 1)
- Precedido por el resumen ejecutivo de diferencias materiales
- Output: un solo archivo multi-page (PDF/Excel con tabs) o un archivo por entity (CSV/HTML)
- Útil para: review general, manager sign-off, filing QC, archive

### Modo 3: Batch — Filtered
Genera reportes solo para un subset de entities (por lista de ref_ids o nombres).
- Parámetro: `entities` (list of names/ref_ids)
- Mismo formato que batch pero solo las entities seleccionadas
- Útil para: reviewer que tiene asignadas solo ciertas entities

### API
```python
# Single entity
engine.sch_f_rollover(entity="C0045")             # By ref ID
engine.sch_f_rollover(entity="Solidus Solutions") # By name (partial match)

# Batch — all entities
engine.sch_f_rollover()                           # Todas, solo con diffs por default
engine.sch_f_rollover(show_all=True)              # Todas, incluyendo clean entities

# Batch — filtered subset
engine.sch_f_rollover(entities=["C0045", "C0018", "C0087"])
engine.sch_f_rollover(entities=["Canopius", "Solidus"])  # Partial match each
```

### Output por Modo

| Modo | Excel | HTML | PDF | CSV |
|------|-------|------|-----|-----|
| Single Entity | 1 tab | 1 page | 1 page | 1 file |
| Batch All | 1 tab per entity + Summary tab | 1 file multi-section | Multi-page (1 entity per page) | 1 file per entity in folder |
| Batch Filtered | Same as batch but only selected | Same | Same | Same |

## Visual Output

### Estructura del Reporte

El reporte se genera **por entidad** (una tabla columnar por cada entity). El output
consolidado (all entities) es la concatenación de todas las tablas individuales,
precedido por un **resumen de diferencias materiales** al inicio.

### Resumen de Diferencias Materiales (siempre al inicio)

Antes de cualquier detalle, el reporte abre con un bloque ejecutivo que lista
SOLO las diferencias materiales (≥$10). Si no hay ninguna, indica "No material
differences found."

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  SCHEDULE F ROLLOVER — MATERIAL DIFFERENCES SUMMARY                        ║
║  Centerbridge Capital Partners III | FY2024 → FY2025 | 66 entities         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Material differences (≥$10): 0                                            ║
║  Immaterial differences (<$10): 14                                         ║
║  Clean (no diff): 325/339 checks                                           ║
║                                                                            ║
║  → No material differences found. All variances are rounding (±$1-2).      ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Si hay diferencias materiales:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║  SCHEDULE F ROLLOVER — MATERIAL DIFFERENCES SUMMARY                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Material differences (≥$10): 3                                            ║
║  Immaterial differences (<$10): 11                                         ║
║                                                                            ║
║  ENTITY                          LINE    DESCRIPTION         DIFFERENCE    ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  Canopius Europe Limited         9       Total assets           +15,420    ║
║  VAVE Holdings Ltd               15      Retained earnings     -82,000    ║
║  Solidus Crumlin Ltd             1       Cash                  +10,500    ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Tabla por Entidad (formato columnar)

Cada entity tiene su propia tabla con TODAS las 16 líneas del Schedule F.
Las columnas son:

| Line | Description | PY XML | CY XML | Difference | Status |
|------|-------------|--------|--------|------------|--------|

Donde:
- **Line** = número de línea del form (1-16)
- **Description** = nombre del line item
- **PY XML** = valor del ending balance en el XML del prior year
- **CY XML** = valor del beginning balance en el XML del current year
- **Difference** = CY XML - PY XML
- **Status** = "OK" (diff < $10) o "Review" (diff ≥ $10)

Ejemplo:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Entity: Solidus Solutions Videcart SAU (C0045) | FC: EUR                          │
├──────┬─────────────────────────────────┬──────────────┬──────────────┬───────────┬────────┐
│ Line │ Description                     │    PY XML    │    CY XML    │   Diff    │ Status │
├──────┼─────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│  1   │ Cash                            │  1,234,567   │  1,234,567   │     —     │   OK   │
│  2   │ Trade notes & A/R               │  5,678,901   │  5,678,901   │     —     │   OK   │
│  3   │ Inventories                     │  7,880,945   │  7,880,946   │    +1     │   OK   │
│  4   │ Investment in subsidiaries      │          0   │          0   │     —     │   OK   │
│  5   │ Buildings & depreciable assets  │ 32,934,906   │ 32,934,908   │    +2     │   OK   │
│  6   │ Land                            │          0   │          0   │     —     │   OK   │
│  7   │ Intangible assets               │  2,100,000   │  2,100,000   │     —     │   OK   │
│  8   │ Other assets                    │    500,000   │    500,000   │     —     │   OK   │
├──────┼─────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│  9   │ TOTAL ASSETS                    │ 50,329,319   │ 50,329,322   │    +3     │   OK   │
├──────┼─────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│ 10   │ Accounts payable                │  6,431,622   │  6,431,623   │    +1     │   OK   │
│ 11   │ Other current liabilities       │  4,098,010   │  4,098,009   │    -1     │   OK   │
│ 12   │ Other liabilities               │ 15,000,000   │ 15,000,000   │     —     │   OK   │
│ 13   │ Capital stock                   │  1,000,000   │  1,000,000   │     —     │   OK   │
│ 14   │ Paid-in surplus                 │  5,000,000   │  5,000,000   │     —     │   OK   │
│ 15   │ Retained earnings               │ 18,799,687   │ 18,799,690   │    +3     │   OK   │
├──────┼─────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│ 16   │ TOTAL LIAB & EQUITY             │ 50,329,319   │ 50,329,322   │    +3     │   OK   │
└──────┴─────────────────────────────────┴──────────────┴──────────────┴───────────┴────────┘
Cross-check: Assets (50,329,322) = Liab+Equity (50,329,322) ✓
```

### All Entities Mode

Cuando se corre para todas las entities:
1. **Resumen de materiales** al inicio (bloque ejecutivo arriba)
2. **Una tabla por entity** — solo entities con diferencias por default, todas si `show_all=True`
3. Al final: summary line con totales

### Color Coding (para HTML/Excel)
- "OK" → verde (cell background verde claro, texto verde oscuro)
- "Review" → rojo (cell background rojo claro, texto rojo bold)
- Difference = 0 → gris claro (no distrae)
- Headers → naranja PwC con texto blanco

## Constraints

- Si una entity no tiene Sch F en alguno de los XMLs → skip (no es FAIL)
- Valores null/vacíos se tratan como 0
- Formato numérico sin decimales (FC amounts son enteros)
- Modo All Entities: SOLO muestra failures por default (opción `show_all=True`)
- Modo Single Entity: SIEMPRE muestra las 16 líneas completas
- Partial match en entity name: case-insensitive, substring match

## Verification

- [ ] Centerbridge FY24→FY25: 14 rounding diffs detectadas (consistente con demo actual)
- [ ] Todas las diffs de CB son ±1-2 (severity = rounding)
- [ ] AmTrust XML: no tiene Sch F → report gracefully skips
- [ ] Entity en PY pero no CY → aparece en `entities_removed`
- [ ] Cross-check: Total Assets = Sum(lines 1-8) para cada entity
- [ ] Output se ve limpio en Excel (XlsxWriter), HTML (great-tables), PDF (reportlab)

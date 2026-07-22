# Spec: Report 02 — Schedule J Rollover

> Inherits: [[00-report-standards]] (headers, materialidad, formato tabular)

## Qué es

Schedule J (Form 5471) es el statement of accumulated E&P de cada CFC.
Trackea los balances de E&P por categoría (pools) con movimientos anuales:
beginning balance + increases - decreases = ending balance → rolls to next year.

**Principio**: El ending balance del año anterior (PY) DEBE ser idéntico al
beginning balance del año corriente (CY) para cada pool de E&P. Si no matchea,
hubo un error en el rollover o un ajuste no documentado.

## Outcomes

- Para cada entidad, comparar los balances de E&P por pool/grupo
- El PY field `BalanceBeginningNextYearAmt` debe = CY field `BeginningYearBalanceAmt`
- Determinar OK (match o diff < $10) vs Review (diff ≥ $10)
- Generar reporte columnar por entidad con todos los pools
- Resumen ejecutivo de diferencias materiales al inicio

## Input

- `prior_xml`: Path al XML del año anterior (PY)
- `current_xml`: Path al XML del año corriente (CY)

## Logic

### E&P Pools (Schedule J Groups)

Schedule J tiene múltiples columnas/pools que representan categorías de E&P:

| # | Group Name (XML) | Description | Column |
|---|---|---|---|
| 1 | Post2017EPNotPrevTaxedGrp | Post-2017 E&P Not Previously Taxed | (a) |
| 2 | Post2017EPPrevTaxedGrp | Post-2017 E&P Previously Taxed | (b) |
| 3 | Section951APTEPGrp | Section 951A PTEP (GILTI) | (c) |
| 4 | Section245AdPTEPGrp | Section 245A(d) PTEP | (d) |
| 5 | Section951a1APTEPGrp | Section 951(a)(1)(A) PTEP (Sub F) | (e)(i) |
| 6 | Section951a1BPTEPGrp | Section 951(a)(1)(B) PTEP | (e)(ii) |
| 7 | Section959c2PTEPGrp | Section 959(c)(2) PTEP (pre-2018) | (e)(iii) |
| 8 | Section965aPTEPGrp | Section 965(a) PTEP | (f) |
| 9 | Section965bPTEPGrp | Section 965(b) PTEP | (g) |
| 10 | TotalSection964AEPGrp | Total Section 964(a) E&P | (h) |
| 11 | Post1986UndistributedEarnGrp | Post-1986 Undistributed Earnings | (i) |
| 12 | HoveringDeficitDedSspndTaxGrp | Hovering Deficit / Suspended Tax | (j) |

### Row-Level Fields dentro de cada Group

Cada pool tiene estas rows en el Schedule J:

| Row | XML Field | Description |
|-----|-----------|-------------|
| 1 | BeginningYearBalanceAmt | Balance at beginning of year |
| 2a | TotalCurrentYearEPAmt | Current year E&P |
| 2b | EarningsPayableDateAmt | E&P as of date payable |
| 3 | TotalEPDistribDuringTYAmt | Total E&P distributed during TY |
| 4 | TotalEPDeemedDistribAmt | E&P deemed distributed |
| 5 | ReclassifiedSect959c2EPAmt | Reclassified under 959(c)(2) |
| 6 | ActualDistribDuringTYAmt | Actual distributions during TY |
| 7 | BalanceEndOfYearAmt | Balance at end of year |
| 8 | BalanceBeginningNextYearAmt | Balance at beginning of next year |

### Rollover Comparison Logic

```
For each entity, for each E&P pool:
  py_value = PY XML → Group → BalanceBeginningNextYearAmt (row 8)
  cy_value = CY XML → Group → BeginningYearBalanceAmt (row 1)
  difference = cy_value - py_value
  
  if abs(difference) == 0 → status = "OK" (no diff)
  if abs(difference) < 10  → status = "OK" (immaterial)
  if abs(difference) >= 10 → status = "Review" (material)
```

### Cross-checks

- Total Section 964(a) E&P (pool 10) should = sum of pools 1-9
- PY row 7 (end of year) should ≈ PY row 8 (beginning next year) — may differ by hovering deficit adjustments
- CY row 1 (beginning) should align with what's reported on Sch H line 5a (current E&P)

### Entity Matching
- Same logic as Sch F: match by `ReferenceIdNum`, fallback by name
- Skip entities without Schedule J in either XML

## Output Structure

```python
@dataclass
class SchJRolloverItem:
    entity_name: str
    reference_id: str
    pool_column: str          # "(a)", "(b)", etc.
    pool_description: str     # "Post-2017 E&P Not Previously Taxed"
    py_value: float           # PY BalanceBeginningNextYearAmt
    cy_value: float           # CY BeginningYearBalanceAmt
    difference: float         # cy - py
    status: str               # "OK" | "Review"

@dataclass
class SchJRolloverReport:
    items: list[SchJRolloverItem]
    total_checks: int
    passed: int               # OK count
    failed: int               # Review count
    entities_checked: int
    entities_with_issues: list[str]
    material_differences: list[SchJRolloverItem]  # Only items with status="Review"
    summary: str
```

## Modos de Reporte

### Modo 1: Single Entity
Reporte de UNA entidad — tabla columnar con TODOS los pools de E&P.
- Parámetro: `entity` (match por name o ref_id)
- Muestra todos los pools (incluyendo los que son 0/0)
- Útil para: drill-down de una entity con issues

### Modo 2: Batch — All Entities
Genera reporte de TODAS las entidades.
- Resumen ejecutivo de diferencias materiales al inicio
- Una tabla por entity
- Output: multi-page PDF, multi-tab Excel, o folder de archivos

### Modo 3: Batch — Filtered
Subset de entities seleccionadas.

### API
```python
# Single entity
engine.sch_j_rollover(entity="C0045")
engine.sch_j_rollover(entity="Canopius")

# Batch — all entities
engine.sch_j_rollover()
engine.sch_j_rollover(show_all=True)       # Include entities with no diffs

# Batch — filtered
engine.sch_j_rollover(entities=["C0045", "C0018", "C0087"])
```

## Visual Output

### Resumen de Diferencias Materiales (siempre al inicio)

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║  SCHEDULE J ROLLOVER — MATERIAL DIFFERENCES SUMMARY                            ║
║  Centerbridge Capital Partners III | FY2024 → FY2025 | 66 entities             ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║  Material differences (≥$10): 12                                               ║
║  Immaterial differences (<$10): 3                                              ║
║  Clean (no diff): 156/171 checks                                               ║
║                                                                                ║
║  ENTITY                          POOL                         DIFFERENCE       ║
║  ─────────────────────────────────────────────────────────────────────────────  ║
║  Canopius Europe Limited         (a) Post-2017 Not Prev Tax      +1,245,830   ║
║  Canopius Europe Limited         (h) Total 964(a) E&P            +1,245,830   ║
║  VAVE Holdings Ltd               (a) Post-2017 Not Prev Tax        -582,100   ║
║  ...                                                                           ║
║                                                                                ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

### Tabla por Entidad (formato columnar)

| Pool | Description | PY XML | CY XML | Difference | Status |
|------|-------------|--------|--------|------------|--------|

Ejemplo:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ Entity: Canopius Europe Limited (C0003) | FC: GBP                                    │
├──────┬────────────────────────────────────┬──────────────┬──────────────┬───────────┬────────┐
│ Pool │ Description                        │    PY XML    │    CY XML    │   Diff    │ Status │
├──────┼────────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│ (a)  │ Post-2017 E&P Not Prev Taxed       │ 12,450,000   │ 13,695,830   │+1,245,830 │ Review │
│ (b)  │ Post-2017 E&P Prev Taxed           │          0   │          0   │     —     │   OK   │
│ (c)  │ Section 951A PTEP (GILTI)          │  3,200,000   │  3,200,000   │     —     │   OK   │
│ (d)  │ Section 245A(d) PTEP               │          0   │          0   │     —     │   OK   │
│(e)(i)│ Section 951(a)(1)(A) PTEP (Sub F)  │    800,000   │    800,000   │     —     │   OK   │
│(e)(ii)│ Section 951(a)(1)(B) PTEP         │          0   │          0   │     —     │   OK   │
│(e)(iii)│ Section 959(c)(2) PTEP (pre-2018)│          0   │          0   │     —     │   OK   │
│ (f)  │ Section 965(a) PTEP                │          0   │          0   │     —     │   OK   │
│ (g)  │ Section 965(b) PTEP                │          0   │          0   │     —     │   OK   │
├──────┼────────────────────────────────────┼──────────────┼──────────────┼───────────┼────────┤
│ (h)  │ TOTAL Section 964(a) E&P           │ 16,450,000   │ 17,695,830   │+1,245,830 │ Review │
│ (i)  │ Post-1986 Undistributed Earnings   │ 16,450,000   │ 17,695,830   │+1,245,830 │ Review │
│ (j)  │ Hovering Deficit                   │          0   │          0   │     —     │   OK   │
└──────┴────────────────────────────────────┴──────────────┴──────────────┴───────────┴────────┘
Cross-check: Total 964(a) = Sum(pools a-g) ✓
```

### Color Coding
- "OK" → verde (cell background verde claro, texto verde oscuro)
- "Review" → rojo (cell background rojo claro, texto rojo bold)
- Difference = 0 → gris claro (se muestra como "—")
- Pool totals (h, i) → row con font bold (subtotals)
- Headers → naranja PwC con texto blanco

### Layout por Formato

#### Excel — Layout Horizontal (columnas hacia la derecha)

En Excel tenemos espacio ilimitado horizontal. El layout expande los pools
como columnas hacia la derecha, agrupando PY vs CY por cada pool:

```
       │         Pool (a)          │         Pool (b)          │       Pool (c)         │ ...
Entity │  PY XML  │  CY XML │ Diff │  PY XML  │  CY XML │ Diff │  PY XML │  CY XML │ Diff │ ...
───────┼──────────┼─────────┼──────┼──────────┼─────────┼──────┼─────────┼─────────┼──────┼
C0003  │12,450,000│13,695,830│+1.2M│     0    │     0   │  —   │3,200,000│3,200,000│  —   │
C0005  │ 8,100,000│ 8,100,000│  —  │     0    │     0   │  —   │1,500,000│1,500,000│  —   │
```

- Freeze panes: entity column + header row fijos
- Column groups colapsables por pool (Excel grouping)
- Conditional formatting: Diff cells con color (verde=OK, rojo=Review)
- Una row por entity, todas las entities visibles de un vistazo
- Summary row al final con count de OK/Review por pool

#### PDF — Layout Paginado (no cortar comparisons)

En PDF (formato carta landscape 11"×8.5") NO caben todos los pools en una fila.
El layout se adapta para que:

1. **Nunca se corte un comparison a la mitad** — si un pool (PY | CY | Diff | Status)
   no cabe completo en la página actual, se mueve entero a la siguiente página.

2. **Cada página re-enlista las líneas (Entity + Description)** como columnas fijas
   a la izquierda, de forma que el reviewer pueda seguir el track sin voltear páginas.

3. **Paginación por grupos de pools** — se dividen los 12 pools en bloques que quepan:
   - Página 1: Entity | Pool (a) PY/CY/Diff/Status | Pool (b) PY/CY/Diff/Status | Pool (c) ...
   - Página 2: Entity | Pool (d) PY/CY/Diff/Status | Pool (e)(i) ... (repite col Entity)
   - Página 3: Entity | Pool (h) Total ... | Pool (i) ... | Pool (j) ...

Layout visual de una página de PDF:

```
┌─── Page 1 of 3 ───────────────────────────────────────────────────────────┐
│ Schedule J Rollover — Centerbridge FY24→FY25                              │
│                                                                           │
│                    │     Pool (a)              │     Pool (b)              │
│                    │  Post-2017 Not Prev Tax   │  Post-2017 Prev Taxed    │
│ Entity             │  PY XML │  CY XML │Status│  PY XML │  CY XML │Status│
│ ───────────────────┼─────────┼─────────┼──────┼─────────┼─────────┼──────│
│ Canopius Europe    │12,450,000│13,695,830│Review│     0  │      0  │  OK  │
│ VAVE Holdings      │ 5,000,000│ 4,417,900│Review│     0  │      0  │  OK  │
│ Solidus Videcart   │ 2,300,000│ 2,300,000│  OK  │     0  │      0  │  OK  │
│ ...                │         │         │      │         │         │      │
│                                                                           │
│                                                     Page 1 of 3 — Pools a-c│
└───────────────────────────────────────────────────────────────────────────┘

┌─── Page 2 of 3 ───────────────────────────────────────────────────────────┐
│ Schedule J Rollover — Centerbridge FY24→FY25 (continued)                  │
│                                                                           │
│                    │   Pool (d)                │  Pool (e)(i)              │
│                    │  Section 245A(d) PTEP     │  951(a)(1)(A) Sub F PTEP  │
│ Entity             │  PY XML │  CY XML │Status│  PY XML │  CY XML │Status│
│ ───────────────────┼─────────┼─────────┼──────┼─────────┼─────────┼──────│
│ Canopius Europe    │      0  │      0  │  OK  │  800,000│  800,000│  OK  │
│ VAVE Holdings      │      0  │      0  │  OK  │  200,000│  200,000│  OK  │
│ Solidus Videcart   │      0  │      0  │  OK  │      0  │      0  │  OK  │
│ ...                │         │         │      │         │         │      │
│                                                                           │
│                                                     Page 2 of 3 — Pools d-g│
└───────────────────────────────────────────────────────────────────────────┘
```

**Reglas de paginación PDF:**
- Calcular cuántos pools caben por página (basado en ancho disponible)
- Siempre mantener columna "Entity" repetida a la izquierda de cada página
- Un pool = 3 sub-columnas (PY XML | CY XML | Status) — nunca separar
- Si solo cabe 1 pool en el espacio restante → mover a siguiente página
- Header de cada página repite: título del reporte + cuáles pools muestra
- Footer: "Page X of Y — Pools [range]"

#### HTML — Layout Completo (scrollable)
- Tabla completa sin paginación (el browser scrollea)
- Sticky header + sticky entity column (CSS position:sticky)
- Misma estructura horizontal que Excel

### Output por Modo

| Modo | Excel | HTML | PDF | CSV |
|------|-------|------|-----|-----|
| Single Entity | 1 tab (vertical: pools as rows) | 1 page | 1 page | 1 file |
| Batch All | 1 sheet horizontal (entities=rows, pools=cols) + Summary | Multi-section | Multi-page paginado | 1 file per entity |
| Batch Filtered | Same as batch, only selected | Same | Same | Same |

**Nota**: En Single Entity mode, el layout es **vertical** (pools como filas) porque
estamos viendo una sola entity. En Batch mode, el layout es **horizontal** (entities
como filas, pools como columnas) para comparar across entities.

## Constraints

- Si una entity no tiene Schedule J → skip (no es failure)
- Pools con PY=0 y CY=0 → se muestran pero como "—" en Difference, status "OK"
- El XML puede no tener todos los pools (algunos son nuevos post-2018) → handle gracefully
- Valores en functional currency (misma moneda que Sch F)
- Negative E&P (deficits) son valores negativos — el status check aplica sobre abs(diff)
- Sch J es particularmente sensible porque errors aquí implican PTEP/Sub F issues downstream

## Contexto Técnico

El alto número de failures (95) en el demo actual se debe a que:
- Muchas entities tienen E&P movement real (current year E&P adds to balance)
- El check actual compara row 8 vs row 1 — si OIT recalculó correctamente, el CY
  beginning SHOULD reflect PY ending + any reclassification adjustments
- A diferencia de Sch F (static balance sheet), Sch J es un rolling statement
- Expected behavior: si E&P movió correctamente, diff = current year movement
  (this is NOT an error, it's the expected behavior of a rollover with activity)

**Nota importante**: En Sch J, una "diferencia" entre PY row 8 y CY row 1 puede ser
legitimate si hubo reclassifications entre pools en el nuevo año. El reporte debe
flaggear estas diferencias para review, pero el associate debe evaluar si la diferencia
se explica por movement legítimo.

## Verification

- [ ] Centerbridge FY24→FY25: genera tabla por cada entity con Sch J data
- [ ] Entities sin Sch J → skip gracefully
- [ ] Total pool (h) = sum de pools individuales → cross-check pasa
- [ ] Formato columnar: Pool | Description | PY XML | CY XML | Difference | Status
- [ ] Material summary al inicio lista solo diffs ≥ $10
- [ ] Batch mode genera output para 66 entities sin error
- [ ] Single entity mode para "C0003" muestra todos los 12 pools
- [ ] Output limpio en Excel, HTML (great-tables), PDF

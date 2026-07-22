# Spec: Report 03 — Page 1 Static Data

> Inherits: [[00-report-standards]] (headers, materialidad, formato tabular)

## Qué es

Page 1 del Form 5471 (y Form 8858) contiene la información de identificación de cada
CFC/FDE: nombre, dirección, país de incorporación, EIN, functional currency, etc.

**Principio**: Estos campos son datos estáticos que NO deberían cambiar de un año a otro.
Si algo cambió, es probable que sea un error de data entry en OIT, un typo, o en raros
casos un cambio legítimo que debe documentarse.

A diferencia de Sch F y Sch J que comparan montos numéricos, este reporte compara
**texto y fechas** — el match es exact string.

## Outcomes

- Para cada entidad, comparar TODOS los campos de Page 1 entre PY y CY
- Las líneas se enlistan en el **mismo orden en que aparecen en la forma IRS** (ref: PDF de Form 5471 y 8858 en sources)
- Formato tabular: Line | Description | PY XML | CY XML | Status
- Status: "OK" (sin cambio) o "Review" (cambio detectado)
- Resumen ejecutivo al inicio con cambios detectados

## Input

- `prior_xml`: Path al XML del año anterior (PY)
- `current_xml`: Path al XML del año corriente (CY)
- Referencia de orden: Form 5471 PDF (sources/) y Form 8858 PDF (sources/)

## Logic

### Campos en Orden de Aparición en Form 5471 Page 1

El orden sigue exactamente la forma impresa, de arriba a abajo, izquierda a derecha:

Orden per Form 5471 (Rev. December 2025) — exactamente como aparece en la forma impresa:

| # | Line | Description |
|---|------|-------------|
| 1 | 1a | Name of foreign corporation |
| 2 | 1a | Address (number and street) |
| 3 | 1a | City or town |
| 4 | 1a | State or province |
| 5 | 1a | Postal code |
| 6 | 1a | Country |
| 7 | 1b(1) | Employer identification number |
| 8 | 1b(2) | Reference ID number |
| 9 | 1c | Country under whose laws incorporated |
| 10 | 1d | Date of incorporation |
| 11 | 1e | Principal place of business |
| 12 | 1f | Principal business activity code |
| 13 | 1g | Principal business activity |
| 14 | 1h | Functional currency code |

> Referencia: `sources/xml-parser/f5471.pdf` page 1

### Campos para Form 8858 (FDEs/FBs)

Si la entity es un FDE o Foreign Branch (Form 8858), comparar estos campos
en el orden de la Form 8858 (Rev. December 2024):

| # | Line | Description |
|---|------|-------------|
| 1 | 1a | Name of FDE or FB |
| 2 | 1a | Address |
| 3 | 1a | City |
| 4 | 1a | Country |
| 5 | 1b(1) | U.S. identifying number |
| 6 | 1b(2) | Reference ID number |
| 7 | 1c | Country of organization / entity type |
| 8 | 1d | Date(s) of organization |
| 9 | 1e | Effective date as FDE |
| 10 | 1g | Country of principal business activity |
| 11 | 1h | Business activity code |
| 12 | 1i | Principal business activity |
| 13 | 1j | Functional currency |
| 14 | 3a | Tax owner name |
| 15 | 3d | Tax owner country |
| 16 | 3e | Tax owner functional currency |

> Referencia: `sources/xml-parser/f8858.pdf` page 1

**Nota**: Los XML field names se mantienen internamente en el código (field_maps.py)
pero NO se muestran en el output del reporte — solo Line y Description.

### Comparison Logic

```
For each entity, for each field (in form order):
  py_value = PY XML → field value (trimmed)
  cy_value = CY XML → field value (trimmed)
  
  Compare case-insensitive (for matching purposes)
  Display original case in output
  
  if py_value == cy_value → status = "OK"
  if py_value != cy_value → status = "Review"
  if both empty → skip (don't include in table)
  if one empty, one has value → status = "Review" — show "(empty)" for the blank
```

### Entity Matching
- Match by ReferenceIdNum (primary), fallback by name
- Entities in PY but not CY → separate section "Entities Removed"
- Entities in CY but not PY → separate section "New Entities"

## Output Structure

```python
@dataclass
class Page1Item:
    entity_name: str
    reference_id: str
    line_number: str          # Form line: "1a", "1b", "2a", etc.
    field_name: str           # "Name of foreign corporation", etc.
    py_value: str             # PY text value (or "(empty)")
    cy_value: str             # CY text value (or "(empty)")
    changed: bool
    status: str               # "OK" | "Review"

@dataclass
class Page1Report:
    items: list[Page1Item]
    total_checks: int
    ok_count: int
    review_count: int
    entities_checked: int
    entities_with_changes: list[str]
    summary: str
```

## Modos de Reporte

### Modo 1: Single Entity
Tabla completa de UNA entity con TODOS los campos de Page 1 (en form order).
- Muestra todos los fields (OK y Review)
- Útil para: verificar que una entity específica está limpia

### Modo 2: Batch — All Entities
Genera tabla por CADA entity (formato completo, todas las líneas).
- Resumen ejecutivo al inicio con todos los "Review" items
- Una tabla por entity (show_all=True para incluir clean entities también)
- Útil para: QC completo antes de filing

### Modo 3: Batch — Filtered
Subset de entities.

### API
```python
# Single entity
engine.page1_rollover(entity="C0003")

# Batch — all entities
engine.page1_rollover()                    # Solo entities con cambios
engine.page1_rollover(show_all=True)       # Todas las entities

# Batch — filtered
engine.page1_rollover(entities=["C0003", "C0045"])
```

## Visual Output

### Header (per [[00-report-standards]])

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  CLIENT:       Centerbridge Capital Partners III LP                          │
│  ENGAGEMENT:   Centerbridge FY25 International Tax Compliance                │
│  REPORT:       Page 1 — Static Data Rollover                                 │
│  COMPARISON:   FY2024 (PY) vs FY2025 (CY)                                   │
│                                                                              │
│  Generated: 2026-07-20 14:35:22                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Resumen Ejecutivo

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  PAGE 1 STATIC DATA — CHANGES SUMMARY                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  Changes detected: 8                                                        ║
║  Fields unchanged: 604/612                                                  ║
║  Entities affected: 4 of 66                                                 ║
║                                                                            ║
║  CHANGES:                                                                  ║
║  ENTITY                     LINE   FIELD                  PY → CY          ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  Canopius Europe Limited    1d     Incorporation date    2011-04-01→04-02  ║
║  VAVE Holdings Ltd          1a     Address line 1        22 Grenville→(empty)║
║  VAVE Holdings Ltd          1a     City                  St Helier→(empty) ║
║  VAVE Holdings Ltd          1a     Country               JE → (empty)     ║
║  Solidus Crumlin Ltd        1h     Functional currency   EUR → GBP        ║
║  ...                                                                       ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Tabla por Entidad (formato tabular — orden de la forma)

Cada entity tiene su tabla con TODOS los campos, enlistados en el orden exacto
en que aparecen en la Form 5471/8858 impresa:

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Entity: Canopius Europe Limited (C0003) | Form: 5471                                  │
├──────┬─────────────────────────────────┬───────────────────┬───────────────────┬────────┐
│ Line │ Description                     │       PY          │       CY          │ Status │
├──────┼─────────────────────────────────┼───────────────────┼───────────────────┼────────┤
│ 1a   │ Name of foreign corporation     │ Canopius Europe   │ Canopius Europe   │   OK   │
│ 1a   │ Address (number and street)     │ 7th Floor, One Fe │ 7th Floor, One Fe │   OK   │
│ 1a   │ City or town                    │ London            │ London            │   OK   │
│ 1a   │ State or province               │ (empty)           │ (empty)           │   —    │
│ 1a   │ Postal code                     │ EC3A 8AA          │ EC3A 8AA          │   OK   │
│ 1a   │ Country                         │ GB                │ GB                │   OK   │
│1b(1) │ Employer identification number  │ (empty)           │ (empty)           │   —    │
│1b(2) │ Reference ID number             │ C0003             │ C0003             │   OK   │
│ 1c   │ Country of incorporation        │ GB                │ GB                │   OK   │
│ 1d   │ Date of incorporation           │ 2011-04-01        │ 2011-04-02        │ Review │
│ 1e   │ Principal place of business     │ GB                │ GB                │   OK   │
│ 1f   │ Business activity code          │ 524126            │ 524126            │   OK   │
│ 1g   │ Business activity               │ Direct Insurance  │ Direct Insurance  │   OK   │
│ 1h   │ Functional currency             │ GBP               │ GBP               │   OK   │
└──────┴─────────────────────────────────┴───────────────────┴───────────────────┴────────┘
1 change: Line 1d — Date of incorporation
```

### Color Coding
- "OK" → verde (background verde claro)
- "Review" → rojo (background rojo claro, texto rojo bold)
- "—" (both empty/skipped) → gris claro
- Headers → naranja PwC con texto blanco
- Line numbers → bold

### Layout por Formato

#### Excel
- Vertical (fields como rows) — una tab por entity, o una tab consolidada
- Columns: Line | Description | PY XML | CY XML | Status
- Freeze panes en header row
- Conditional formatting en Status column

#### PDF
- Vertical layout (cabe perfectamente — text fields son cortos)
- Una entity por page (o varias si son pocas líneas con cambios)
- Header repetido en cada página per [[00-report-standards]]
- Footer con fecha/página

#### HTML
- Tabla completa, sticky header
- Hover highlight en rows

### Output por Modo

| Modo | Excel | HTML | PDF | CSV |
|------|-------|------|-----|-----|
| Single Entity | 1 tab | 1 page | 1 page | 1 file |
| Batch All | 1 tab per entity + Summary | Multi-section | Multi-page | 1 file per entity |
| Batch Filtered | Same, only selected | Same | Same | Same |

## Constraints

- El orden de campos SIEMPRE sigue la forma IRS impresa (no alfabético, no por severity)
- Comparación case-insensitive para matching, pero muestra case original
- Both empty → status "—" (skip, no es ni OK ni Review — no hay dato que comparar)
- Si entity tiene 5471 Y 8858, reportar ambos en secciones separadas
- Address changes son comunes (formatting) — el associate decide si es issue real
- Functional currency change es SIEMPRE significativo (requiere restatement)
- Reference forms: Form 5471 PDF y Form 8858 PDF en sources/ (para verificar orden)

## Verification

- [ ] Centerbridge FY24→FY25: detecta 8 cambios
- [ ] Orden de campos = orden de la forma impresa (1a name → 1a addr → ... → 4 category)
- [ ] VAVE Holdings: address fields show "(empty)" en CY column
- [ ] Solidus: functional currency EUR→GBP flagged
- [ ] Canopius: incorporation date 2011-04-01→2011-04-02 flagged
- [ ] Header incluye: Client, Engagement, Report name, Comparison years, Timestamp
- [ ] Batch genera output para 66 entities sin error
- [ ] Single entity muestra todos los campos completos en form order
- [ ] 8858 entities muestran campos de Form 8858 (no Form 5471)

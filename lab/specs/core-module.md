# Core Module — Spec (v0.7.5)

> Spec autoritativo para `lab/core/` — shared services layer de Mythos.
> Este documento describe el estado actual, contratos, consumidores, y gaps.

## Rol en la Arquitectura

`core/` es la capa transversal que provee servicios reutilizados por los tres
módulos principales de Mythos:

```
xml_parser/  ──┐
pdf_validator/ ─┼──→  core/  (shared services)
mythos_ui/   ──┘
```

**Principio:** zero-dependency entre módulos principales. Si `xml_parser/` y
`pdf_validator/` necesitan la misma funcionalidad, vive en `core/`.

---

## Inventario de Archivos (1,735 LOC)

| Archivo | LOC | Clase principal | Responsabilidad |
|---------|-----|-----------------|-----------------|
| `entity_classifier.py` | 388 | `EntityClassifier`, `ClassifiedEntity` | Pipeline unificado: parse → enrich → tag → canonical entity |
| `entity_tagger.py` | 157 | `EntityTagger`, `TagResult`, `TagRule` | Motor de reglas determinísticas → set de tags fiscales |
| `tagging_rules.py` | 200 | `DEFAULT_RULES` (8 reglas) | Funciones puras `(EntityData) → bool` |
| `entity_registry.py` | 147 | `EntityRegistry`, `Entity` | Catálogo estático de entities con metadata (insurance, DRE, dormant) |
| `oit_parser.py` | 415 | `OITDataSource` | Parser de exports ONESOURCE → DataFrames con shape de schedule |
| `xlsx_reader.py` | 183 | `XlsxReader` | Reader robusto de Excel via zipfile+XML (bypass openpyxl bugs) |
| `fx_rates.py` | 66 | `FXRateManager` | Conversión FC↔USD con rates spot y average |
| `errors.py` | 186 | `CerebroError` hierarchy | Excepciones estructuradas con context, severity, user message |
| `__init__.py` | 1 | — | Docstring |

---

## Subsistema 1: Entity Intelligence Pipeline

### Flujo

```
XML (EFileParser)
    │
    ▼
EntityClassifier.classify(parser)
    ├── 1. parser.parse() → subsidiaries + schedule DataFrames
    ├── 2. _index_by_ref() → {ref_id: Series} per schedule (C, E, H, I, I-1, J, P)
    ├── 3. _build_entity_from_sub() → ClassifiedEntity (identity + schedule dicts)
    ├── 4. _enrich_from_registry() → insurance/DRE/dormant flags (optional)
    └── 5. _apply_tags() → EntityTagger.tag() → tags + contradictions + evidence
            │
            ▼
      ClassifiedEntity  ← objeto canónico de salida
```

### ClassifiedEntity — Canonical Model

Consolida 6 representaciones fragmentadas anteriores en un solo objeto:

```python
@dataclass
class ClassifiedEntity:
    # Identity (siempre poblado)
    reference_id: str
    entity_name: str
    country_code: str
    functional_currency: str
    voting_stock_pct: float | None
    dormant: bool
    category_filers: list[str]

    # Extended identity (Page 1)
    ein, incorporation_date, address_line1, city, province, postal_code
    principal_place_of_business, form_type, document_id, oit_locator

    # 8858-specific
    tax_owner_name, tax_owner_ref_id, tax_owner_ein, tax_owner_country
    is_fde_us_person, is_fb_cfc

    # Type flags
    is_insurance: bool
    is_dre: bool

    # Schedule data (prefix-stripped dicts)
    sch_c, sch_e, sch_g, sch_h, sch_i, sch_i1, sch_j, sch_p: dict

    # Classification output
    tags: set[str]
    contradictions: list[tuple[str, str, str]]
    tag_metadata: dict[str, Any]  # evidence trail
```

### EntityData — Input lean para el Tagger

```python
@dataclass
class EntityData:
    reference_id: str
    entity_name: str
    is_dormant, is_insurance, is_dre: bool
    voting_stock_pct: float | None
    sch_c, sch_h, sch_i, sch_i1, sch_j, sch_g, sch_e, sch_p: dict

    def get(schedule, field, default=0.0) -> float  # safe accessor, nunca crashea
    def has_schedule(schedule) -> bool
```

### TagRule Protocol

```python
@dataclass
class TagRule:
    tag_name: str                          # "tested_income"
    description: str                       # human-readable
    evaluate: Callable[[EntityData], bool] # función pura
    category: str                          # "classification" | "risk"
    priority: int                          # higher = evaluated first
    xml_fields: list[tuple[str, str]]      # evidence trail fields
```

### Reglas Implementadas (8/16)

| Tag | Fuente | Regla |
|-----|--------|-------|
| `tested_income` | Sch I-1 | TestedIncomeAmt > 0 OR TestedIncomeLossGrp_USDollarAmt > 0 |
| `tested_loss` | Sch I-1 | TestedLossAmt > 0 OR TestedIncomeLossGrp_USDollarAmt < 0 |
| `high_tax_exclusion` | Sch I-1 | ExclGrossIncmHghTxdIncmAmt > 0 OR HighTaxExclusionElectionAmt > 0 |
| `subpart_f` | Sch I | Sum(SubpartF*Amt) > 0 |
| `de_minimis` | Sch I+C | Total SubF < min($1M, 5% × gross income) — IRC 954(b)(3) |
| `full_inclusion` | Page 1+I-1 | voting_stock_pct ≥ 1.0 AND tested income > 0 |
| `interest_expense` | Sch I-1 | TestedInterestExpenseAmt > 0 |
| `negative_ep` | Sch H | CurrentEarningsAndProfitsAmt < 0 |

### Contradictions Implementadas (1/3)

| Par | Razón |
|-----|-------|
| `tested_income` + `tested_loss` | ✅ Mutuamente excluyentes |
| `dormant` + `subpart_f` | ❌ No implementada |
| `dormant` + `tested_income` | ❌ No implementada |

---

## Subsistema 2: Entity Registry

### Estado actual

- Catálogo estático de 36 entities hardcoded (sample/demo)
- Lookup: `match_by_name()` (case-insensitive + substring), `match_by_ref_id()` (linear scan)
- Metadata: `is_insurance`, `is_dre`, `is_dormant`, `fx_rate`, `deal`
- `load_from_workbook()` → **stub vacío**
- No integrado con XML parsed entities

### Consumidores

| Consumidor | Cómo lo usa |
|-----------|-------------|
| `EntityClassifier._enrich_from_registry()` | Opcional — setea insurance/DRE/dormant flags |
| `MythosService.classify_entities()` | Pasa registry como parámetro opcional |
| `tests/test_entity_classifier.py` | Usa `.sample()` y registries custom |
| `audit/ep_validator.py` | Script externo (fuera de Mythos core) |

---

## Subsistema 3: Data Source Adapters

### OITDataSource (`oit_parser.py`, 415 LOC)

- Parsea 5 tipos de CSV/XLSX de ONESOURCE Income Tax
- Sign convention handler (OIT: neg=income → Mythos: pos=income)
- Produce DataFrames con columnas nombradas para match XML fields
- Schedules: `sch_c_fc`, `sch_h_fc`, `sch_f_usd`, `sch_e`, `subf_sourcing`
- **Estado:** HUÉRFANO — ningún import en runtime de Mythos

### XlsxReader (`xlsx_reader.py`, 183 LOC)

- Reader vía zipfile+XML directo (evita crash openpyxl con print titles #N/A)
- `read_sheet()` → valores y fórmulas
- `read_sheet_as_df()` → DataFrame
- **Estado:** HUÉRFANO en Mythos core (solo usado por `audit/` scripts)

### FXRateManager (`fx_rates.py`, 66 LOC)

- 6 currencies hardcoded (USD, GBP, EUR, SGD, AUD, BMD)
- `fc_to_usd()`, `usd_to_fc()` con rate spot o average
- `load_from_workbook()` → **stub vacío**
- **Estado:** HUÉRFANO (solo `audit/ep_validator.py`)

---

## Subsistema 4: Error Hierarchy

### `core/errors.py` (186 LOC)

```
CerebroError (base)
├── DataSourceError
│   ├── FileNotFoundError_
│   └── FileFormatError
├── ParseError
│   ├── XMLParseError
│   ├── PDFExtractionError
│   └── WorkbookParseError
├── ValidationError
│   ├── MissingFieldError
│   ├── ValueOutOfRangeError
│   └── InconsistencyError
├── ReconciliationError
│   ├── PhantomValueError
│   └── MaterialMismatchError
└── ConfigError
    └── DependencyMissingError
```

Cada error lleva: `ErrorContext` (entity, schedule, field, page), `Severity`
(LOW→CRITICAL), `user_message` vs `technical_message`, `.to_log_entry()`.

### Estado: MUERTO

**Cero imports en todo el proyecto.** `xml_parser/` usa su propia jerarquía
(`MythosError` en `xml_parser/core/exceptions.py`) con clases de nombre
idéntico (`ParseError`, `ValidationError`) pero incompatibles.

---

## Consumidores por Módulo

| Archivo `core/` | `xml_parser/` | `mythos_ui/` | `pdf_validator/` | `tests/` |
|-----------------|---------------|--------------|-------------------|----------|
| `entity_classifier.py` | `api/service.py` | `pages/entities.py`, `xml_check/tab_entities.py` | — | `test_entity_classifier.py` |
| `entity_tagger.py` | `api/service.py` | — | — | `test_entity_tagger.py` |
| `tagging_rules.py` | (via tagger) | — | — | (via tagger) |
| `entity_registry.py` | — | — | — | `test_entity_classifier.py` |
| `oit_parser.py` | (docstring only) | — | — | — |
| `xlsx_reader.py` | — | — | — | — |
| `fx_rates.py` | — | — | — | — |
| `errors.py` | — | — | — | — |

---

## Test Coverage

| Test file | Tests | Cubre |
|-----------|-------|-------|
| `test_entity_tagger.py` | 41 | 8 rules (True/False), contradictions, tolerance, batch, accessors, evidence |
| `test_entity_classifier.py` | 45 | Pipeline, identity, OIT locator, summary, registry enrichment, tag consistency, service integration |
| **Total** | **86** | Entity pipeline well-tested; Registry/FX/OIT/errors untested |

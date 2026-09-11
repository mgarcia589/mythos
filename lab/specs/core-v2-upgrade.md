# Core Module v2 — Upgrade Spec

> Plan para convertir `lab/core/` de "shared utilities" a un **motor potente de
> identificación de entidades** que sea el cerebro analítico de Mythos.

## Visión

Después del upgrade, cualquier consumidor (xml_parser, pdf_validator, mythos_ui, CLI)
hace UNA llamada y obtiene un `ClassifiedEntity` con:

- Identidad completa (Page 1 + 8858 + OIT locator)
- 16 tags fiscales determinísticos con evidence trail
- Ownership chain (parent → child → FDE)
- FX conversion integrada
- Flags de riesgo y anomalías
- Score de completeness (qué schedules tiene vs debería tener)

```
core/ v2
├── entity_classifier.py    REFACTOR — cache, perf, completeness scoring
├── entity_tagger.py        AMPLIAR — 16 reglas, 5 contradictions
├── tagging_rules.py        AMPLIAR — 8 reglas nuevas
├── entity_registry.py      REWRITE — auto-populate desde XML, persistencia, O(1) lookup
├── ownership.py            NUEVO — ownership graph (parent/child/FDE chains)
├── fx_rates.py             CONECTAR — integrar con OITDataSource y Classifier
├── oit_parser.py           CONECTAR — wired into reconciler pipeline
├── xlsx_reader.py          CONSERVAR — ya funciona, solo necesita consumidores
├── errors.py               DECIDIR — unificar con MythosError o eliminar
└── __init__.py             ACTUALIZAR — re-exports públicos
```

---

## Fase 1: Tagger Completo (16 reglas + 5 contradictions)

**Impacto:** ALTO — duplica la cobertura de clasificación fiscal.
**Riesgo:** BAJO — código puro, sin I/O, tests inmediatos.
**LOC estimado:** ~150 nuevas en `tagging_rules.py`, ~20 en `entity_tagger.py`

### 1.1 Reglas nuevas (8)

| # | Tag | Schedule | Regla | Prioridad |
|---|-----|----------|-------|-----------|
| 1 | `dormant` | Sch C + H | `is_dormant` flag O (todos los campos Sch C == 0 AND CurrentE&P == 0) | 9 |
| 2 | `us_property` | Sch I | `EarningsInvestedInUSPropAmt > 0` — IRC §956 | 6 |
| 3 | `sec_245a` | Sch I | `Sect245AEligibleDividendsAmt > 0` | 5 |
| 4 | `income_blocked` | Sch I | `IncomeBlockedInd == 1` o campo truthy | 4 |
| 5 | `has_qbai` | Sch I-1 | `QBAIAmt > 0` — necesario para GILTI NDTIR | 6 |
| 6 | `insurance` | Registry | `entity.is_insurance == True` | 2 |
| 7 | `dre` | Registry | `entity.is_dre == True` | 2 |
| 8 | `s163j` | Sch C + G | `InterestExpenseAmt > 0 AND (indicador 163j en Sch G)` | 5 |

### 1.2 Contradictions nuevas (4)

| Par | Razón |
|-----|-------|
| `dormant` + `subpart_f` | Dormant entity no debería tener Subpart F income |
| `dormant` + `tested_income` | Dormant entity no debería tener tested income |
| `dormant` + `negative_ep` | Si es dormant con E&P=0, negative_ep es contradiction |
| `dre` + `tested_income` | DRE/FDE no reporta tested income (se consolida en tax owner) |

### 1.3 Verificación

- 1 test True + 1 test False por cada regla nueva (16 tests)
- 1 test por cada contradiction nueva (4 tests)
- Todos los tests existentes siguen green
- `python -m pytest lab/tests/test_entity_tagger.py -v` — 61+ tests

### 1.4 Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `tagging_rules.py` | +8 funciones de regla, +8 `TagRule` en `DEFAULT_RULES` |
| `entity_tagger.py` | +4 entries en `CONTRADICTIONS` |
| `tests/test_entity_tagger.py` | +20 tests (16 regla + 4 contradiction) |

---

## Fase 2: Registry Auto-Populate + O(1) Lookups

**Impacto:** ALTO — elimina la dependencia de datos hardcoded.
**Riesgo:** MEDIO — cambia el contrato del Registry.
**LOC estimado:** ~100 rewrite en `entity_registry.py`

### 2.1 Problema

El Registry actual tiene 36 entities hardcoded. En producción, cada XML contiene
las entities reales en `SubsidiaryReturn`. El Classifier ya las parsea pero no
las persiste — cada llamada re-parsea desde cero.

### 2.2 Solución: Auto-populate desde parser

```python
class EntityRegistry:
    def __init__(self):
        self._by_ref: dict[str, Entity] = {}     # O(1) lookup
        self._by_name: dict[str, Entity] = {}     # normalized name → Entity
        self._by_code: dict[str, Entity] = {}     # legacy code lookup

    def populate_from_parser(self, parser: EFileParser) -> int:
        """Auto-populate registry from parsed XML. Returns count added."""
        parsed = parser.parse()
        for sub in parsed.subsidiaries:
            ent = sub.entity
            entity = Entity(
                code=ent.reference_id,
                name=ent.name,
                fc=ent.functional_currency,
                country=ent.country_code,
                deal="",  # not in XML
                ein_ref=ent.reference_id,
            )
            self.register(entity)
        return len(self._by_ref)

    def register(self, entity: Entity) -> None:
        """Register single entity with O(1) index maintenance."""
        self._by_ref[entity.ein_ref or entity.code] = entity
        self._by_name[entity.name.lower().strip()] = entity
        self._by_code[entity.code] = entity

    def match_by_ref_id(self, ref_id: str) -> Entity | None:
        return self._by_ref.get(ref_id)          # O(1) vs O(n) actual

    def match_by_name(self, name: str) -> Entity | None:
        return self._by_name.get(name.lower().strip())  # O(1) exact match
```

### 2.3 Eliminaciones

- Remover `SAMPLE_ENTITIES` hardcoded (mover a `tests/conftest.py` como fixture)
- Remover `EntityRegistry.sample()` (reemplazar por factory en tests)

### 2.4 Backward compatibility

- `match_by_name()` y `match_by_ref_id()` mantienen misma firma
- Tests existentes usan registries construidos manualmente → no afectados
- Agregar `populate_from_parser()` como método nuevo (additive)

### 2.5 Verificación

- Test: `populate_from_parser()` con fixture XML → correct count
- Test: O(1) lookup funciona después de populate
- Test: register() actualiza los 3 índices
- Test: nombre duplicado → último gana (upsert)

---

## Fase 3: Classifier Performance + Completeness Scoring

**Impacto:** MEDIO — mejora UX en returns grandes.
**Riesgo:** BAJO — refactor interno, API no cambia.
**LOC estimado:** ~80 modificados en `entity_classifier.py`

### 3.1 Fix `_index_by_ref()` — O(n²) → O(n)

```python
# ANTES (O(n²)):
def _index_by_ref(self, df):
    result = {}
    for ref in df["_reference_id"].unique():
        result[ref] = df[df["_reference_id"] == ref].iloc[0]
    return result

# DESPUÉS (O(n)):
def _index_by_ref(self, df):
    if df.empty:
        return {}
    return dict(next(iter(g)) for _, g in df.groupby("_reference_id"))
```

### 3.2 Cache de clasificación

```python
class EntityClassifier:
    def __init__(self, registry=None):
        self._registry = registry
        self._tagger = EntityTagger()
        self._cache: dict[str, list[ClassifiedEntity]] = {}  # xml_path → entities

    def classify(self, parser) -> list[ClassifiedEntity]:
        cache_key = str(parser.path)
        if cache_key in self._cache:
            return self._cache[cache_key]
        entities = self._classify_impl(parser)
        self._cache[cache_key] = entities
        return entities
```

### 3.3 Completeness Score por Entity

Cada entity recibe un score de "qué tan completa está su data":

```python
@dataclass
class ClassifiedEntity:
    # ... existing fields ...
    completeness_score: float = 0.0        # 0.0 → 1.0
    missing_schedules: list[str] = field(default_factory=list)

# Reglas de completeness (depende del form_type):
# 5471 non-dormant: espera C, E, H, I, I-1, J, P (7 schedules)
# 5471 dormant: espera al menos H y J (2 schedules)
# 8858: espera C, F, H (3 schedules)
```

### 3.4 classify_single() sin re-parse

```python
def classify_single(self, parser, ref_id: str) -> ClassifiedEntity | None:
    entities = self.classify(parser)   # hits cache si ya se llamó
    return next((e for e in entities if e.reference_id == ref_id), None)
```

### 3.5 Verificación

- Benchmark: clasificar 40 entities antes vs después (target: <100ms)
- Test: cache hit devuelve misma lista
- Test: completeness score correcto para dormant vs active vs 8858

---

## Fase 4: Error Hierarchy — Unificar o Eliminar

**Impacto:** BAJO en funcionalidad, ALTO en higiene de código.
**Riesgo:** BAJO.
**Opción recomendada:** Eliminar `core/errors.py`, adoptar `MythosError` como único árbol.

### 4.1 Contexto

Dos jerarquías paralelas:
- `core/errors.py`: `CerebroError` → 12 subclases, 186 LOC, **cero consumidores**
- `xml_parser/core/exceptions.py`: `MythosError` → 3 subclases, 33 LOC, **usado en runtime**

### 4.2 Plan

1. Migrar los conceptos útiles de `CerebroError` a `MythosError`:
   - `ErrorContext` dataclass (entity, schedule, field, page) → útil
   - `Severity` enum → útil
   - `.to_log_entry()` → útil
2. Expandir `xml_parser/core/exceptions.py` con las subclases que sirvan:
   - `ReconciliationError` → sí, el reconciler lo necesita
   - `PDFExtractionError` → sí, para `pdf_validator/`
   - `ConfigError` → sí, para startup
3. Eliminar `core/errors.py`
4. Actualizar `core/__init__.py`

### 4.3 Verificación

- Grep: cero imports de `core.errors` en todo el proyecto (ya es así)
- Tests existentes siguen green (ninguno importaba errors.py)

---

## Fase 5: Conectar Adapters Huérfanos

**Impacto:** MEDIO — habilita reconciliación 3-way (XML vs OIT vs Workbook).
**Riesgo:** MEDIO — requiere datos reales para validar.

### 5.1 OITDataSource → Reconciler

El Reconciler ya documenta `oit_data` como parámetro. Conectar:

```python
# xml_parser/reconciler.py
def reconcile_three_way(self, xml_data, workbook_data, oit_data: OITDataSource):
    """XML vs Workbook vs OIT — triangulated comparison."""
```

### 5.2 FXRateManager → OITDataSource

`OITDataSource._build_sch_h()` deja `CurrEarnAndPrftInUSDollarsAmt = NaN`.
Inyectar FXRateManager:

```python
class OITDataSource:
    def __init__(self, ..., fx_manager: FXRateManager | None = None):
        self._fx = fx_manager

    def _build_sch_h(self):
        # ... existing code ...
        if self._fx:
            for entity_code in result.index:
                fc = entity_currencies.get(entity_code, "USD")
                fc_amt = result.loc[entity_code, "CurrEarnAndPrftInFuncCurAmt"]
                result.loc[entity_code, "CurrEarnAndPrftInUSDollarsAmt"] = (
                    self._fx.fc_to_usd(fc_amt, fc)
                )
```

### 5.3 FXRateManager — Load desde IRS published rates

Reemplazar sample rates hardcoded con loader real:

```python
class FXRateManager:
    @classmethod
    def from_irs_rates(cls, year: int) -> "FXRateManager":
        """Load from IRS yearly average exchange rates (público)."""

    @classmethod
    def from_workbook(cls, xlsx_reader: XlsxReader, sheet: str) -> "FXRateManager":
        """Load from client workbook FX sheet."""
```

### 5.4 Verificación

- Test: OITDataSource con FXRateManager produce USD amounts (no NaN)
- Test: FXRateManager.from_workbook() carga rates desde Excel real
- Integration: Reconciler three-way produce report con 3 columnas

---

## Fase 6 (Futuro): Ownership Graph

**Nota:** Esta fase está alineada con Phase 9 del roadmap Mythos (mythos-framework.md).
Spec separado cuando se aborde. Aquí solo se establece la interfaz esperada.

```python
# core/ownership.py (futuro)
class OwnershipGraph:
    """Directed graph: parent → child → FDE."""

    def add_entity(self, entity: ClassifiedEntity) -> None: ...
    def parent_of(self, ref_id: str) -> str | None: ...
    def children_of(self, ref_id: str) -> list[str]: ...
    def fdes_of(self, ref_id: str) -> list[str]: ...
    def chain(self, ref_id: str) -> list[str]: ...  # root → ... → entity
    def to_dict(self) -> dict: ...  # serializable
```

---

## Prioridad de Implementación

| Fase | Prioridad | Esfuerzo | Estado |
|------|-----------|----------|--------|
| **1: Tagger 16 reglas** | 🔴 ALTA | ~2h | PENDIENTE |
| **2: Registry auto-populate** | 🔴 ALTA | ~2h | ✅ COMPLETADA (2026-09-10) |
| **3: Classifier perf + completeness** | 🟡 MEDIA | ~1.5h | ✅ COMPLETADA (2026-09-10) |
| **4: Error hierarchy** | 🟢 BAJA | ~1h | ✅ COMPLETADA (2026-09-10) |
| **5: Conectar adapters** | 🟡 MEDIA | ~3h | PENDIENTE |
| **6: Ownership graph** | 🔵 FUTURO | ~4h | PENDIENTE — Phase 9 roadmap |

**Siguiente:** Fase 1 (Tagger 16 reglas) → Fase 5 (Conectar adapters)

---

## Métricas de Éxito

| Métrica | Actual | Target |
|---------|--------|--------|
| Tags implementados | 8 | 16 |
| Contradictions | 1 | 5 |
| Registry entities (producción) | 0 (hardcoded) | auto-populated desde XML |
| `_index_by_ref` complejidad | O(n²) | O(n) |
| Classify 40 entities | sin medición | < 100ms |
| Código muerto en core/ | 850 LOC (49%) | 0 LOC |
| Tests en core/ | 86 | 120+ |
| Completeness scoring | no existe | 0.0–1.0 per entity |

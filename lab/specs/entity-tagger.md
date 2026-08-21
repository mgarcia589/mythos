# Entity Tagger — Spec

## Outcome

Un motor que recibe datos parseados de un entity (XML fields de Schedules C, H, I, I-1, J, P)
y devuelve un `set[str]` de tags que clasifican el comportamiento fiscal de esa entidad para
el tax year en cuestión.

Estos tags sirven para:
1. Filtrado rapido en reconciliaciones ("solo entidades con tested loss")
2. Validacion cruzada (una entidad `full_inclusion` no deberia tener Sch P PTEP en 951A pool)
3. Dashboard/reporting (breakdown por tipo de entidad)
4. Deteccion de anomalias (tag esperado ausente, tag contradictorio)

## Scope

### Tags Definidos (v1)

| Tag | Condicion | Fuente |
|-----|-----------|--------|
| `tested_income` | TestedIncomeAmt > 0 | Sch I-1 L6(pos) |
| `tested_loss` | TestedLossAmt > 0 | Sch I-1 L6(neg) |
| `high_tax_exclusion` | ExclGrossIncmHghTxdIncmAmt > 0 | Sch I-1 L2c |
| `subpart_f` | Sum(SubpartFPHCIncomeAmt + SubpartFSalesIncomeAmt + SubpartFServicesIncomeAmt + OtherSubpartFNotIncludedAmt) > 0 | Sch I |
| `de_minimis` | Total Subpart F < min($1,000,000, 5% × ForeignTotalIncomeAmt) | Sch I + Sch C L12 |
| `full_inclusion` | VotingStockOwnedPct == 1.0 (100% ownership) | Page 1 |
| `dormant` | Todos los campos de Sch C == 0 (o ausentes) Y CurrentEarningsAndProfitsAmt == 0 | Sch C + Sch H |
| `us_property` | EarningsInvestedInUSPropAmt > 0 | Sch I L2 |
| `sec_245a` | Sect245AEligibleDividendsAmt > 0 | Sch I L5 |
| `income_blocked` | IncomeBlockedInd == 1 | Sch I indicator |
| `has_qbai` | QBAIAmt > 0 | Sch I-1 L8 |
| `interest_expense` | TestedInterestExpenseAmt > 0 | Sch I-1 L9a |
| `negative_ep` | CurrentEarningsAndProfitsAmt < 0 | Sch H L5a |
| `insurance` | entity.is_insurance == True | EntityRegistry |
| `dre` | entity.is_dre == True | EntityRegistry |
| `s163j` | ForeignInterestExpenseAmt > 0 AND regla 163(j) activa | Sch C L16 + Sch G |

### Tags Futuros (v2+)

- `pillar_two_scope` — entidad en scope de GloBE (revenue > €750M grupo)
- `check_the_box` — entidad con eleccion CTB vigente
- `hybrid` — entidad con tratamiento hibrido (dual-consolidated loss risk)
- `hovering_deficit` — HoveringDeficitDedSspndTaxGrp con balance > 0 en Sch J

## Constraints

1. **Puro** — El tagger es una funcion pura: recibe datos, devuelve tags. Sin side effects,
   sin I/O, sin dependencia de paths.
2. **Testeable** — Cada regla es una funcion independiente con signature:
   `(entity_data: EntityData) -> bool`
3. **Extensible** — Agregar un tag nuevo = agregar una funcion + registrarla en el registry.
4. **Tolerante** — Si un campo no existe en la data (entidad no tiene Sch I-1), la regla
   devuelve `False` sin error. Nunca crashea por datos faltantes.
5. **Contradictions** — El tagger detecta y reporta combinaciones invalidas:
   - `tested_income` + `tested_loss` (mutuamente excluyentes)
   - `dormant` + `subpart_f` (inconsistente)
   - `de_minimis` + `subpart_f` sin `de_minimis` (si aplica de minimis, Subpart F no se incluye)

## Architecture

```
lab/core/entity_tagger.py        — Motor principal
lab/core/tagging_rules.py        — Funciones individuales de regla
lab/tests/test_entity_tagger.py  — Unit tests (uno por regla + contradicciones)
```

### Data Model

```python
@dataclass
class EntityData:
    """Input para el tagger — datos consolidados de una entidad."""
    reference_id: str
    entity_name: str = ""

    # Metadata (from EntityRegistry)
    is_dormant: bool = False
    is_insurance: bool = False
    is_dre: bool = False
    voting_stock_pct: float | None = None

    # Schedule C (Income Statement)
    sch_c: dict[str, float] = field(default_factory=dict)

    # Schedule H (Current E&P)
    sch_h: dict[str, float] = field(default_factory=dict)

    # Schedule I (Subpart F Summary)
    sch_i: dict[str, float] = field(default_factory=dict)

    # Schedule I-1 (GILTI)
    sch_i1: dict[str, float] = field(default_factory=dict)

    # Schedule J (E&P pools) — optional, for advanced tags
    sch_j: dict[str, dict[str, float]] = field(default_factory=dict)

    # Schedule G (Other Information — indicators)
    sch_g: dict[str, float] = field(default_factory=dict)

    def get(self, schedule: str, field: str, default: float = 0.0) -> float:
        """Safe accessor: EntityData.get("i1", "TestedIncomeAmt") -> float."""
        source = getattr(self, f"sch_{schedule}", {})
        return source.get(field, default)
```

### Tagger API

```python
@dataclass
class TagResult:
    """Output del tagger para una entidad."""
    reference_id: str
    tags: set[str]
    contradictions: list[tuple[str, str, str]]  # (tag_a, tag_b, reason)
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata puede incluir valores calculados: total_subf, effective_tax_rate, etc.

class EntityTagger:
    """Aplica todas las reglas registradas a un EntityData."""

    def __init__(self, rules: list[TagRule] | None = None):
        self.rules = rules or DEFAULT_RULES

    def tag(self, entity: EntityData) -> TagResult: ...
    def tag_batch(self, entities: list[EntityData]) -> list[TagResult]: ...
    def summary(self, results: list[TagResult]) -> dict[str, int]:
        """Cuenta entidades por tag. Util para dashboard."""
```

### Rule Protocol

```python
@dataclass
class TagRule:
    """Una regla individual de tagging."""
    tag_name: str
    description: str
    evaluate: Callable[[EntityData], bool]
    category: str = "classification"  # classification | risk | validation
    priority: int = 0  # higher = evaluated first (for short-circuit)

# Ejemplo:
def _is_tested_loss(e: EntityData) -> bool:
    return e.get("i1", "TestedLossAmt") > 0

TESTED_LOSS_RULE = TagRule(
    tag_name="tested_loss",
    description="Entity has tested loss (Sch I-1 Line 6 negative)",
    evaluate=_is_tested_loss,
    category="classification",
)
```

### Contradiction Detection

```python
CONTRADICTIONS: list[tuple[str, str, str]] = [
    ("tested_income", "tested_loss", "Cannot have both tested income and tested loss"),
    ("dormant", "subpart_f", "Dormant entity should not have Subpart F income"),
    ("dormant", "tested_income", "Dormant entity should not have tested income"),
]
```

### Integration Points

1. **From EFileParser** — `parser.to_dataframe()` ya devuelve un DataFrame con todos los
   campos. Un adapter convierte cada row a `EntityData`.

2. **From WorkbookReader** — `gilti_calc`, `subf_summary`, `de_minimis` worksheets
   pueden enriquecer el EntityData con datos del workbook (cross-check vs XML).

3. **To Wiki** — Un comando `materialize_tags()` actualiza `entities.md` con una columna
   o seccion de tags por entidad.

4. **To Dashboard** — `tagger.summary(results)` alimenta la vista de resumen.

## Verification

1. Unit test por cada regla (minimo 2 cases: True + False)
2. Test de contradicciones (inyectar data contradictoria, verificar detection)
3. Test de tolerancia (EntityData con dicts vacios → sin crash, sin tags)
4. Integration test con XML real (parsear cb-fy25-v15.xml → tag todas las entidades
   → verificar que C0002 tiene `tested_income`, dormants tienen `dormant`)
5. `python -m pytest lab/tests/test_entity_tagger.py -v` — all green

## Ejemplo de Uso

```python
from lab.core.entity_tagger import EntityTagger, EntityData

# Desde el parser
parser = EFileParser("path/to/return.xml")
df = parser.to_dataframe()

tagger = EntityTagger()

for _, row in df.iterrows():
    entity_data = EntityData.from_dataframe_row(row)  # adapter
    result = tagger.tag(entity_data)
    print(f"{result.reference_id}: {sorted(result.tags)}")
    if result.contradictions:
        print(f"  ⚠ {result.contradictions}")

# Resumen
all_results = tagger.tag_batch([EntityData.from_dataframe_row(r) for _, r in df.iterrows()])
summary = tagger.summary(all_results)
# {'tested_income': 12, 'tested_loss': 3, 'dormant': 8, 'subpart_f': 5, ...}
```

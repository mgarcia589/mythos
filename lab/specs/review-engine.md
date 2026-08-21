# Spec: Review Engine — XML-First Automated Compliance Review

> Part of Project Mythos v0.5 — automated quality checks against IRS e-file XML
> without requiring workbook access. Surfaces anomalies, inconsistencies, and
> review points before a human reviewer touches the return.

## Outcomes

1. **Zero-workbook review** — analyze any client's XML return day-1, no mapping needed
2. **Multi-dimensional checks** — rollover (YoY), internal flow, completeness, reasonableness
3. **Anomaly flagging** — material items, outliers, and inconsistencies ranked by severity
4. **Reviewer-ready output** — findings presented as actionable review points with context
5. **Universal** — works for any 1120/1065 return with Forms 5471/8858/8865

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Review Engine                          │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Rollover │  │   Flow   │  │Complete- │  │Reason- │ │
│  │  Checks  │  │  Checks  │  │  ness    │  │ able-  │ │
│  │  (YoY)   │  │(Intra-yr)│  │  Audit   │  │  ness  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │       │
│       └──────────────┴──────┬───────┴─────────────┘       │
│                             │                             │
│                    ┌────────▼────────┐                    │
│                    │  Finding Engine │                    │
│                    │  (rank, dedup,  │                    │
│                    │   contextualize)│                    │
│                    └────────┬────────┘                    │
│                             │                             │
│                    ┌────────▼────────┐                    │
│                    │    Dashboard    │                    │
│                    │   (NiceGUI)     │                    │
│                    └─────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

## Check Categories

### 1. Rollover Checks (requires FY-1 XML)

| Check ID | Description | Severity |
|----------|-------------|----------|
| ROL-001 | Sch F BOY ≠ prior year EOY (balance sheet discontinuity) | HIGH |
| ROL-002 | Entity present in PY but absent in CY without Sch O transaction | MEDIUM |
| ROL-003 | Entity absent in PY but present in CY without Sch O transaction | MEDIUM |
| ROL-004 | E&P sign flip (positive→negative or vice versa) without material transaction | MEDIUM |
| ROL-005 | FX rate change > 25% YoY (potential data entry error) | LOW |
| ROL-006 | Material amount (>$100K) disappears to zero without explanation | HIGH |
| ROL-007 | Sch H accumulated E&P ≠ PY current + PY accumulated (if available) | HIGH |

### 2. Internal Flow Checks (single-year XML)

| Check ID | Description | Severity |
|----------|-------------|----------|
| FLO-001 | Sch H net income → Sch I-1 gross income consistency | HIGH |
| FLO-002 | Sch H E&P × FX rate ≠ USD E&P (within tolerance) | MEDIUM |
| FLO-003 | Sch I-1 tested income + HTE income + SubF ≈ gross income | HIGH |
| FLO-004 | Sch E taxes should be ≤ Sch H pre-tax income × max stat rate | MEDIUM |
| FLO-005 | Entities with tested loss should not have tested foreign taxes | HIGH |
| FLO-006 | Sch C net income should flow to Sch H line 1 | HIGH |
| FLO-007 | Sch F total assets must ≥ 0 (no negative balance sheets) | HIGH |
| FLO-008 | Sch F assets = liabilities + equity (BS must balance) | HIGH |

### 3. Completeness Audit (single-year XML)

| Check ID | Description | Severity |
|----------|-------------|----------|
| CMP-001 | Entity has 5471 header but no Sch H (missing E&P) | HIGH |
| CMP-002 | Entity has Sch H but no Sch I-1 (missing GILTI classification) | MEDIUM |
| CMP-003 | Entity has Sch I-1 income but no Sch E taxes | MEDIUM |
| CMP-004 | Sch F has BOY amounts but no EOY (incomplete) | HIGH |
| CMP-005 | Entity has no functional currency or exchange rate | MEDIUM |
| CMP-006 | Reference ID missing or duplicated | HIGH |

### 4. Reasonableness Checks (single-year XML)

| Check ID | Description | Severity |
|----------|-------------|----------|
| RSN-001 | E&P in USD > $1B for single entity (unusual, flag for review) | LOW |
| RSN-002 | FX rate outside expected range for known currencies | MEDIUM |
| RSN-003 | Effective tax rate > 50% or < 0% (anomalous) | MEDIUM |
| RSN-004 | Tested income exactly equals SubF income (possible misclass) | LOW |
| RSN-005 | All entities have identical E&P sign (unusual for diversified group) | LOW |
| RSN-006 | QBAI > total assets on Sch F (impossible) | HIGH |
| RSN-007 | Interest expense > gross income (leverage anomaly) | MEDIUM |

## Data Model

```python
@dataclass
class Finding:
    check_id: str           # "ROL-001", "FLO-003", etc.
    severity: str           # HIGH, MEDIUM, LOW
    category: str           # rollover, flow, completeness, reasonableness
    entity_code: str        # affected entity
    entity_name: str        # human-readable name
    description: str        # what was found
    expected: str | None    # what was expected
    actual: str | None      # what was observed
    delta: float | None     # numeric difference if applicable
    context: str | None     # additional context for reviewer

@dataclass
class ReviewReport:
    client_name: str
    tax_year: str
    entity_count: int
    findings: list[Finding]
    summary: dict           # by category, by severity, by entity
    run_timestamp: str

    def high_severity(self) -> list[Finding]
    def by_entity(self, code: str) -> list[Finding]
    def by_category(self, cat: str) -> list[Finding]
    def to_dataframe(self) -> pd.DataFrame
```

## In-Scope

- Form 5471 (all schedules parsed by EFileParser)
- Form 8858 (if parser supports)
- Single-year analysis (all checks except rollover)
- Two-year analysis (includes rollover checks)
- JSON/DataFrame output for dashboard consumption

## Out-of-Scope (v0.5)

- Form 8865 (partnership — different structure)
- Form 8992/8993 (consolidated GILTI — filer-level, not entity-level)
- Auto-correction or fix suggestions
- Workbook reconciliation (stays in Reconciler module)
- Tax position evaluation (that's professional judgment)

## Constraints

- Python 3.12+
- Uses existing EFileParser — no reimplementation
- All checks must be deterministic (no AI/LLM in the check logic)
- Performance: full review < 5s for 50-entity return
- Findings must be self-contained (reviewer can act without additional context)
- Severity levels must be consistent and defensible

## UI Integration (NiceGUI Dashboard)

The Review Engine feeds a NiceGUI dashboard that provides:
- Upload XML(s) → instant analysis
- Findings table with AG Grid (filter, sort, group by entity/category/severity)
- Entity-level detail view (all findings for one entity)
- YoY comparison visualization (if two XMLs provided)
- Summary cards (total findings by severity, pass rate)
- Export to Excel for workpaper documentation

## Verification Criteria

- [ ] Small return (single year): identifies at least 5 meaningful findings
- [ ] Small return (PY→CY): correctly flags added and removed entities
- [ ] Large return: identifies known issues (dormant entities, version diffs)
- [ ] No false positives on clean entities (entity with valid data = 0 findings)
- [ ] All checks run in < 3s for small returns (25 entities)
- [ ] All checks run in < 5s for large returns (34+ entities)
- [ ] Dashboard renders findings correctly with AG Grid
- [ ] Export produces valid Excel with all findings

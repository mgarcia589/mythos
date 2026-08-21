# Spec: Reconciler — Workbook vs XML Automated Comparison Engine

> Part of Project Mythos — reconciles compliance workbook data against
> IRS e-file XML to identify discrepancies before filing.

## Outcomes

1. **Automated field-by-field comparison** between WorkbookReader output and
   EFileParser output for any supported schedule
2. **Tolerance-aware matching** — differences below a configurable threshold
   (default $1 for rounding) are marked "pass" rather than flagged
3. **Structured discrepancy report** with entity, schedule, field, workbook
   value, XML value, delta, and severity classification
4. **Multi-schedule reconciliation** in a single run — compare all overlapping
   schedules between workbook and XML
5. **Entity matching by code** — WorkbookReader `_entity_code` maps to XML
   `_reference_id` (both use "C0002" format)
6. **Summary statistics** — pass rate by schedule, by entity, overall

## In-Scope

### Schedules Supported for Reconciliation

| Schedule | Workbook Key | XML Form Key | Notes |
|----------|-------------|--------------|-------|
| Sch H (E&P) | `sch_h_fc` | `IRS5471ScheduleH` | FC amounts |
| Sch I-1 (GILTI) | `sch_i1_fc` | `IRS5471ScheduleI1` | FC amounts |
| Sch I (SubF) | `sch_i` | `IRS5471ScheduleI` | FC amounts |
| Sch C (Income) | `sch_c_fc` | `IRS5471ScheduleC` | FC amounts |
| Sch F (BS) | `sch_f_usd` | `IRS5471ScheduleF` | USD EOY only |
| Sch E (Taxes) | `sch_e` | `IRS5471ScheduleE` | Mixed |

### Comparison Logic

- Match entities by code (workbook `_entity_code` = XML `_reference_id`)
- For each matched entity-schedule pair, compare each field that exists in both
- Tolerance: |wb_value - xml_value| <= threshold → PASS
- Missing entity in XML but present in workbook → flag as "XML_MISSING"
- Missing entity in workbook but present in XML → flag as "WB_MISSING"
- NaN/None in XML vs 0 in workbook for dormant entities → mark as "DORMANT_OK"

### Output

```python
@dataclass
class FieldResult:
    entity_code: str
    schedule: str
    field_name: str
    line: str
    wb_value: float | str | None
    xml_value: float | str | None
    delta: float | None
    status: str  # PASS, FAIL, DORMANT_OK, XML_MISSING, WB_MISSING, TYPE_MISMATCH

@dataclass 
class ReconciliationReport:
    results: list[FieldResult]
    summary: dict  # pass_rate, fail_count, by_schedule, by_entity
    
    def to_dataframe(self) -> pd.DataFrame
    def failures_only(self) -> pd.DataFrame
    def to_excel(self, path: str | Path)
```

## Out-of-Scope

- Schedule J reconciliation (no workbook equivalent — it's OIT-driven)
- Schedule G reconciliation (Yes/No indicators don't have numeric XML equivalents
  in the same structure)
- Modifying either source (read-only comparison)
- Auto-fixing discrepancies

## Constraints

- Python 3.12+
- pandas for DataFrames
- Uses existing EFileParser and WorkbookReader — no reimplementation
- Must handle entities that exist in one source but not the other
- Must handle NaN, None, 0 equivalence for dormant entities
- Performance: < 3s for full reconciliation (34 entities x 6 schedules)
- Field name mapping: workbook uses `field_maps.py` XML names already, so
  direct column name matching works for most fields

## Prior Decisions

- Entity Code is the universal key (both sources use "C0002" format)
- WorkbookReader already outputs field names matching XML element names
- EFileParser.extract_form() returns DataFrame with `_reference_id` as index
- Tolerance of $1 handles FX rounding differences
- Dormant entities (NaN in XML, 0 in WB) are a known acceptable pattern

## Task Breakdown

1. **ReconciliationEngine class** — takes WorkbookData + parsed XML, drives comparison
2. **Entity matcher** — align entities across sources by code
3. **Field comparator** — numeric comparison with tolerance, type handling
4. **Schedule dispatcher** — maps workbook schedule keys to XML form keys
5. **Result aggregator** — collects FieldResults, computes summary stats
6. **DataFrame export** — structured output for reporting
7. **Excel export** — formatted workbook with pass/fail highlighting

## Verification Criteria

- [ ] Sch H reconciliation: matches known results (7/9 pass, 2 dormant)
- [ ] Sch I-1 reconciliation: matches known results (7/9 pass, 2 version diffs)
- [ ] Sch C reconciliation: line 22 (net income) matches across all non-dormant entities
- [ ] Sch F reconciliation: total assets match for active entities
- [ ] Sch E reconciliation: tax amounts match for filing entities
- [ ] Tolerance works: $0.52 rounding diff → PASS (not FAIL)
- [ ] Dormant handling: NaN vs 0 → DORMANT_OK (not FAIL)
- [ ] Missing entity handling: entity in WB not in XML → XML_MISSING status
- [ ] Summary stats: correct pass rate calculation
- [ ] Full reconciliation < 3s
- [ ] Excel output generates without error

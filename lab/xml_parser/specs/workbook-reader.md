# Spec: Workbook Reader — Compliance Workbook Ingestion Engine

> Part of Project Mythos — reads compliance workbooks and produces structured
> DataFrames for reconciliation against IRS e-file XML.

## Outcomes

1. **Read any PwC 5471/8858 compliance workbook** regardless of version, year,
   or minor formatting variations
2. **Extract per-entity, per-schedule data** into DataFrames indexed by Entity Code
3. **Detect workbook layout patterns** automatically (entities-across-columns vs
   entities-down-rows)
4. **Map workbook rows/columns to IRS form lines** using the same field_maps.py
   taxonomy as the XML parser
5. **Handle openpyxl "invalid XML" errors** (print title bugs) gracefully via
   monkey-patching
6. **Produce output directly comparable** to `EFileParser.extract_form()` DataFrames
   — same column naming where applicable

## In-Scope

### Workbook Layouts Supported

**Layout A: Entities-Across-Columns (primary — CB pattern)**
- Header rows (1-7): Title, schedule name, year, entity codes, entity names, FC, FX rate
- Row labels in columns A-D: Line number, description, OIT account, OIT adjustment
- Entity data starts at column E onward
- One column per entity
- Sheets: `5471 Sch H - FC`, `5471 Sch I-1 - FC`, `5471 Sch I-1 - USD`, `5471 Sch I`,
  `5471 Sch C - FC`, `5471 Sch C - USD`, `5471 Sch F - USD`, `5471 Sch E`, `5471 Sch G`

**Layout B: Entities-Down-Rows (secondary — GILTI/SubF calc sheets)**
- Header row with column labels
- One row per entity
- Entity Code in column B or C
- Sheets: `2025 GILTI`, `2025 Subpart F`, `Subpart F - Summary`, `De Minimis - Analysis`

### Data Extraction

- Schedule H: E&P calculations (lines 1-5d) per entity in FC
- Schedule I-1: GILTI tested income, QBAI, deductions per entity (FC and USD)
- Schedule I: Subpart F income by category per entity
- Schedule C: Income statement per entity (FC and USD)
- Schedule F: Balance sheet per entity (USD)
- Schedule E: Foreign taxes per entity
- Schedule G: Yes/No indicators per entity
- GILTI calc: Tested income, tested loss, QBAI, interest, foreign taxes
- Subpart F calc: De minimis analysis, Sub F by category, high-tax test
- Entity Listing: Master list with Reference IDs, FC, country codes

### Output Format

```python
class WorkbookData:
    source_path: Path
    client_name: str
    tax_year: str
    entities: dict[str, EntityInfo]  # entity_code -> metadata
    schedules: dict[str, pd.DataFrame]  # schedule_key -> DataFrame
```

Each DataFrame in `schedules` has:
- Index: entity_code (e.g., "C0002")
- Columns: field names matching `field_maps.py` conventions where possible

## Out-of-Scope

- Writing/modifying workbooks
- Parsing formulas (read `data_only=True` — cached values)
- Supporting non-PwC workbook layouts (OIT native exports — already handled by `oit_parser.py`)
- Reverse-engineering formula logic (that's a separate analyzer module)
- Schedule J (not typically in workbook — it's an OIT output)

## Constraints

- Python 3.12+
- openpyxl (with monkey-patch for print title bugs)
- pandas for DataFrame output
- Must handle workbooks up to 60 sheets / 100 entities / 15MB
- Performance: < 5s for full workbook parse
- Graceful on missing sheets (return empty DataFrame, don't crash)
- Entity matching by Entity Code (e.g., "C0002") — the common key between
  workbook and XML (maps to `_reference_id` in XML)

## Prior Decisions

- openpyxl `read_only=True, data_only=True` for performance and formula resolution
- Monkey-patch `WorkbookParser.assign_names` to handle invalid print titles
- Entity Code is the primary matching key (same as XML `reference_id`)
- Separate "form sheets" (Layout A) from "calc sheets" (Layout B) detection
- Field naming follows `field_maps.py` convention for cross-reference

## Task Breakdown

1. **WorkbookReader class** — opens workbook, detects available sheets, provides
   sheet listing and metadata
2. **Layout detection** — given a sheet, determine if Layout A (across) or Layout B (down)
3. **Layout A parser** — extract entity header row, row labels, and entity data matrix
4. **Layout B parser** — extract column headers, entity column, and data rows
5. **Schedule-specific extractors** — for each schedule, map raw rows/cols to
   named fields (using field_maps where possible)
6. **Entity registry** — build master entity list from Entity Listing sheet
7. **Unified `parse()` method** — returns `WorkbookData` with all schedules extracted
8. **DataFrame compatibility layer** — rename columns to match XML parser output for
   direct reconciliation

## Verification Criteria

- [x] Opens CB workbook without error (handles print title bug)
- [x] Correctly identifies 34 5471 entities + 2 8858 entities from Entity Listing
- [x] Schedule H extraction: Line 1 (Net income) for C0002 = 6243 (from FC sheet)
- [x] Schedule I-1 extraction: Line 1 (Gross income) for C0002 = 2244503
- [x] Schedule I-1 extraction: Line 2b (Sub F) for C0003 = 39624163
- [x] GILTI calc: C0005 shows 0 tested income (correct — it's a Full Inclusion Sub F entity)
- [x] GILTI calc: C0002 tested_income_fc = 6243 (matches its net tested income after deductions)
- [x] De Minimis: FPHCI for C0005 = 233905664
- [x] All schedules return DataFrames indexed by entity code
- [x] Missing schedule returns empty DataFrame (not exception)
- [x] Reconciliation-ready: Sch H Line 1 matches XML 7/9 entities (2 "fails" are
  dormant entities with nan in XML vs 0 in workbook — expected)
- [x] Sch I-1 reconciliation: 7/9 match (2 diffs are version adjustments ~$449K and $1 rounding)
- [x] Performance: full parse < 5s (measured ~3s)

## Architecture Integration

```
lab/xml_parser/
  workbook_reader.py   — NEW: WorkbookReader class
  reconciler.py        — FUTURE: uses WorkbookReader + EFileParser to compare
```

The reconciler (future module) will:
1. Parse XML with `EFileParser`
2. Parse workbook with `WorkbookReader`
3. Match entities by code/reference_id
4. Compare field-by-field with tolerance
5. Report discrepancies

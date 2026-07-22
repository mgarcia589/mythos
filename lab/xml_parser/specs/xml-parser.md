# Spec: IRS e-File XML Parser

## Outcomes

- Parse any IRS e-file XML (Return type 1120/1065) into structured DataFrames — one row per subsidiary entity, columns = form fields
- Extract data selectively by form type (IRS5471, IRS8858, schedules E/H/I1/J/M/P/Q/R)
- Compare two XML files (prior year vs current year, draft vs final) and generate a delta report showing added/removed/changed values per entity per field
- Validate XML structure against expected schema (field presence, data types, required schedules)
- Output to: pandas DataFrame, Excel workbook, markdown report, or CSV
- Replace the Alteryx workflow (`Simple parsing - all rows.yxzp`) and compiled exe (`QST Parser v3.exe`) with a faster, more flexible Python tool

## In-Scope

- IRS e-file namespace: `http://www.irs.gov/efile`
- Return types: 1120, 1065 (partnership)
- Forms: IRS5471 (all schedules A-R), IRS8858 (all schedules), IRS8865, IRS8992, IRS1118
- Itemized schedules (assets, liabilities, other)
- Multi-subsidiary returns (66+ subsidiaries per file)
- Year-over-year comparison (same client, different tax years)
- Version comparison (same year, different drafts/iterations)
- Field-level extraction with XPath mapping
- Batch processing of multiple XML files
- Integration with `lab/core/entity_registry.py` for entity matching

## Out-of-Scope

- Modifying or generating XML (read-only)
- IRS e-filing/transmission
- State return XMLs (only federal)
- PDF form rendering
- XSD schema creation (only validation against existing schemas)

## Constraints

- Python 3.12, lxml 6.0.2, pandas 3.0.1
- Must handle XML files up to 10MB+ (66+ subsidiaries, 80+ schedules each)
- Parse time target: < 5 seconds for full extraction of a 1.5MB XML
- Memory: should not exceed 500MB for a single file
- Output column naming must match Alteryx convention: `FormName_Path_To_Field` (underscore-separated)
- Must handle namespace prefixes gracefully (strip or normalize)
- Must handle missing/optional elements without crashing (return None/empty)

## Prior Decisions

- Use `lxml` for parsing (10-50x faster than ElementTree for XPath)
- Maintain backward compatibility with the Alteryx output format (same column names)
- Config-driven: form/field extraction defined in a YAML/dict config, not hardcoded
- Part of `lab/` framework — lives in `lab/xml_parser/`
- Reports integrate with wiki (markdown output for documentation)

## Task Breakdown

### Phase 1: Core Parser
1. `lab/xml_parser/__init__.py`
2. `lab/xml_parser/parser.py` — Main `EFileParser` class:
   - `parse(path) → ParsedReturn` (full extraction)
   - `extract_form(path, form_name) → DataFrame` (selective)
   - `list_subsidiaries(path) → list[dict]` (quick scan)
   - `get_field(path, entity_id, field_xpath) → value` (single field lookup)
3. `lab/xml_parser/config.py` — Form/field definitions:
   - `FORM_5471_FIELDS`: dict mapping column names → XPath expressions
   - `FORM_8858_FIELDS`: same for 8858
   - `SCHEDULE_H_FIELDS`, `SCHEDULE_I1_FIELDS`, etc.
4. `lab/xml_parser/models.py` — Data classes:
   - `ParsedReturn`: header info + list of `SubsidiaryReturn`
   - `SubsidiaryReturn`: entity info + dict of form data
   - `FormData`: form name + dict of field→value

### Phase 2: Comparison Engine
5. `lab/xml_parser/comparator.py` — `XMLComparator` class:
   - `compare(xml_path_1, xml_path_2) → ComparisonReport`
   - Match entities across files by EIN/Reference ID/Business Name
   - Field-by-field diff with tolerance for numeric fields
   - Detect: added entities, removed entities, changed values
   - Flag material changes (numeric diff > threshold)
6. `lab/xml_parser/report.py` — Output formatters:
   - `to_excel(parsed, output_path)` — one sheet per form type
   - `to_markdown(comparison)` — wiki-ready diff report
   - `to_csv(parsed, output_path)` — flat file export

### Phase 3: CLI & Integration
7. `lab/xml_parser/cli.py` — Command-line interface:
   - `python -m lab.xml_parser parse <file.xml> [--form IRS5471] [--output xlsx]`
   - `python -m lab.xml_parser compare <file1.xml> <file2.xml> [--threshold 1000]`
   - `python -m lab.xml_parser list <file.xml>` (quick entity list)
8. Integration with `lab/core/entity_registry.py` — match XML entities to registry codes
9. Integration with workbook audit — compare XML output vs workbook values

## Verification Criteria

- [ ] `parse("sample-cb-fy25.xml")` extracts all 66 subsidiaries with correct entity names
- [ ] `extract_form("sample-cb-fy25.xml", "IRS5471")` returns DataFrame with 62 rows × 100+ columns
- [ ] Column names match Alteryx output format (e.g., `IRS5471_FunctionalCurrencyCd`)
- [ ] `compare("sample-cb-fy24.xml", "sample-cb-fy25.xml")` identifies added/removed/changed entities
- [ ] Numeric comparison with $1 tolerance flags only material differences
- [ ] Handles missing schedules gracefully (entity without Schedule M → None columns)
- [ ] Parse time < 5 seconds for the 1.5MB sample files
- [ ] `list_subsidiaries()` returns entity name, country code, EIN/Ref ID, functional currency in < 1 second
- [ ] Excel output produces one sheet per form with entity as rows
- [ ] TARTAR.xml (different client) parses successfully — tool is not Centerbridge-specific
- [ ] All 4 sample XMLs parse without errors

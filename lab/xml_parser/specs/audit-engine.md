# Spec: Audit Engine

## Outcomes

- Given a 5471/8858 workbook xlsx, automatically detect formula inconsistencies, calculation errors, and filing risks
- Output a structured markdown report with issues categorized by severity (CRITICAL/MODERATE/LOW)
- Replicate key calculations (E&P, Sub F, GILTI, 163(j)) independently and compare vs workbook cached values
- Flag known issue patterns: off-by-row refs, FX direction, pseudo-entities, sign errors, negative assets

## In-Scope

- Reading xlsx files with broken print titles (openpyxl incompatible)
- E&P validation (Sch H: Net Income + Adjustments = Current E&P)
- Formula pattern analysis (XLOOKUP refs, shared formulas, FX operations)
- Entity validation (pseudo-entities, missing lookup targets)
- Sign convention checks (BIE should be negative/expense)
- Asset value validation (no negatives on Sch Q)
- Cross-validation against OIT exports (sign flip + tolerance matching)
- Markdown report generation

## Out-of-Scope

- Modifying the workbook (read-only)
- Executing Excel formulas (only read cached values + formula text)
- ONESOURCE platform interaction (only reads CSV/XLSX exports)
- Insurance-specific Sub F calculations (Phase 3)
- Accumulated E&P / Sch J (PTEP) validation
- Form 8865 (partnership) audit

## Constraints

- Must use zipfile+XML approach (openpyxl fails on this workbook)
- Python 3.12, pandas 3.0.1, numpy 2.4.4
- No external API calls — fully offline
- Workbook may have formula-only cells with no cached value (handle gracefully)
- Tolerance for rounding: $1 for E&P, 0.01 for FX rates

## Prior Decisions

- Architecture: `core/` provides readers + registry + FX; `audit/` provides validators
- Entity registry pre-loaded with Centerbridge data (36 entities hardcoded)
- FX rates hardcoded for FY2025; `load_from_workbook()` for dynamic loading
- Report format: Markdown (consumable by wiki and by Claude in-session)
- CLI entry: `python lab/audit/run_audit.py <path>`

## Task Breakdown

1. `core/xlsx_reader.py` — XlsxReader class with read_sheet(), get_entity_columns(), get_numeric() ✅
2. `core/entity_registry.py` — EntityRegistry with Centerbridge pre-load ✅
3. `core/fx_rates.py` — FXRateManager with fc_to_usd() ✅
4. `audit/formula_checker.py` — 6 check functions ✅
5. `audit/ep_validator.py` — validate_ep() + validate_ep_vs_oit() ✅
6. `audit/run_audit.py` — CLI orchestrator ✅
7. `audit/subf_validator.py` — Replicate 2025 Subpart F sheet logic ⏳
8. `audit/gilti_validator.py` — Replicate 2025 GILTI sheet logic ⏳
9. `audit/s163j_validator.py` — Replicate 8990 logic ⏳
10. `tests/test_ep_validator.py` — Unit tests with known Centerbridge values ⏳

## Verification Criteria

- [ ] `run_audit.py` on the Centerbridge workbook detects ALL 6 known critical issues
- [ ] E&P validator passes for entities with cached values (variance < $1)
- [ ] E&P validator correctly identifies entities where cached values are empty (Rows 26-29)
- [ ] Formula checker flags the 8 insurance rows with off-by-row XLOOKUP
- [ ] Formula checker flags FX direction inversion in 8990 cols Z+
- [ ] Sign check flags C0052, C0042, C0086 in INS 8990
- [ ] Report output is valid markdown parseable by any renderer
- [ ] Total runtime < 30 seconds for full workbook (62 sheets)
- [ ] No false positives on known-correct entities (C0005, C0034)

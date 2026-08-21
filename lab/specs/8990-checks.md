# Form 8990 Check Module — Spec

## Overview

Module: `lab/xml_parser/engine/checks/form_8990.py`
Entry: `run_form_8990_checks(ctx: CheckContext) -> list[Finding]`
Category: `"section_163j"`
Check prefix: `BIE-`

Form 8990 (Limitation on Business Interest Expense Under Section 163(j)) is filed
**per-entity** — each CFC with business interest expense gets its own Form 8990.
The parser extracts these via `parser.extract_form('IRS8990')` which returns a
DataFrame with one row per entity, indexed by `_reference_id`.

## Data Source

```python
df_8990 = parser.extract_form("IRS8990")
# Columns (all prefixed IRS8990_):
#   TaxableIncomeAmt
#   BusInterestExpnsNotPassThruAmt        (Line 4: Current Year BIE)
#   TotalAdditionsAmt                     (Line 8: sum of add-backs)
#   NotPassThruEntBusIntIncomeAmt         (Line 10: negative = subtraction)
#   TotalReductionsAmt                    (Line 14: total reductions)
#   AdjustedTaxableIncomeAmt              (Line 15: ATI = TI + additions - reductions)
#   CYBusinessInterestIncomeAmt           (Line 18: CY BII)
#   TotalBusinessInterestIncomeAmt        (Line 21: Total BII)
#   AdjTaxableIncomeApplcblPctAmt         (Line 23: ATI × 30%)
#   TotalBusIntExpnsLimitationAmt         (Line 25: Limitation = BII + 30% ATI)
#   CYBusIntExpnsBfr163jLmtAmt           (Line 27: CY BIE before limitation)
#   CfwdPrevDsallwIntExpenseAmt           (Line 28: Carryforward from PY)
#   TotalAllowableBusIntExpnsAmt          (Line 29: Total allowable = CY + Cfwd)
#   TotCYBusinessIntExpnsDedAmt           (Line 31: Actual deduction taken)
#   DisallowedBusInterestExpnsAmt         (Line 33: Disallowed = BIE - allowed)
#   DeprecAmortzDpltnDedTakenAmt          (Line 7: D&A add-back to ATI)
#   CFCGroupElectionInd                   (CFC Group election flag)
#   FrmFldBySpcfdGrpParentInd             (Parent consolidation flag)
#   SafeHarborElectionInd                 (Safe harbor election)
```

## Line-by-Line Form 8990 Structure

```
Part II — Adjusted Taxable Income (ATI)
  Line 1:  Taxable Income (TaxableIncomeAmt)
  Line 4:  Business Interest Expense (BusInterestExpnsNotPassThruAmt)
  Line 7:  Depreciation/Amortization/Depletion (DeprecAmortzDpltnDedTakenAmt)
  Line 8:  Total Additions (TotalAdditionsAmt) = sum(Lines 2-7)
  Line 10: Not-Pass-Through Entity Business Int Income (NotPassThruEntBusIntIncomeAmt)
  Line 14: Total Reductions (TotalReductionsAmt) = sum(Lines 9-13)
  Line 15: Adjusted Taxable Income (AdjustedTaxableIncomeAmt) = Line 1 + Line 8 - Line 14

Part III — Business Interest Limitation
  Line 18: CY Business Interest Income (CYBusinessInterestIncomeAmt)
  Line 21: Total Business Interest Income (TotalBusinessInterestIncomeAmt)
  Line 23: ATI × applicable % (AdjTaxableIncomeApplcblPctAmt) = Line 15 × 30%
  Line 25: Limitation (TotalBusIntExpnsLimitationAmt) = Line 21 + Line 23

Part IV — Calculation of Allowable BIE
  Line 27: CY BIE before limitation (CYBusIntExpnsBfr163jLmtAmt)
  Line 28: Carryforward of previously disallowed (CfwdPrevDsallwIntExpenseAmt)
  Line 29: Total allowable (TotalAllowableBusIntExpnsAmt) = Line 27 + Line 28
  Line 31: CY BIE deducted (TotCYBusinessIntExpnsDedAmt) = min(Line 25, Line 29)
  Line 33: Disallowed BIE (DisallowedBusInterestExpnsAmt) = Line 29 - Line 31
```

## Check Definitions

### BIE-001: ATI Calculation Validation (HIGH)
**Rule:** ATI = Taxable Income + Total Additions - Total Reductions
```
AdjustedTaxableIncomeAmt == TaxableIncomeAmt + TotalAdditionsAmt - TotalReductionsAmt
```
**Tolerance:** $1 (rounding)
**Fires when:** Entity has non-zero TaxableIncomeAmt or AdjustedTaxableIncomeAmt
**Risk:** Wrong ATI flows into incorrect 30% limitation → wrong allowed/disallowed BIE

### BIE-002: 30% ATI Limitation Math (HIGH)
**Rule:** Applicable % amount = ATI × 30%
```
AdjTaxableIncomeApplcblPctAmt == AdjustedTaxableIncomeAmt × 0.30
```
**Tolerance:** $1 (rounding)
**Edge case:** If ATI is negative, applicable % should be 0 (floor at zero).
**Fires when:** Entity has non-zero AdjustedTaxableIncomeAmt
**Risk:** Wrong percentage = wrong limitation = over/under deduction

### BIE-003: Total Limitation = BII + 30% ATI (HIGH)
**Rule:** Total limitation = Total BII + applicable % of ATI
```
TotalBusIntExpnsLimitationAmt == TotalBusinessInterestIncomeAmt + AdjTaxableIncomeApplcblPctAmt
```
**Tolerance:** $1
**Fires when:** Entity has any BIE limitation
**Risk:** Understated limitation = unnecessary disallowance; overstated = excess deduction

### BIE-004: Disallowed BIE = Total Allowable - Deducted (MEDIUM)
**Rule:** Disallowed = Total Allowable BIE - CY BIE Deducted
```
DisallowedBusInterestExpnsAmt == TotalAllowableBusIntExpnsAmt - TotCYBusinessIntExpnsDedAmt
```
**Tolerance:** $1
**Notes:** Total allowable includes carryforward. This checks the math carries through.
**Risk:** Wrong disallowed BIE = wrong carryforward to next year

### BIE-005: CY BIE Deducted ≤ Limitation (MEDIUM)
**Rule:** CY deduction cannot exceed the limitation
```
TotCYBusinessIntExpnsDedAmt <= TotalBusIntExpnsLimitationAmt
```
**Tolerance:** $1
**Fires when:** Entity has BIE deduction
**Risk:** Excess deduction = audit exposure

### BIE-006: BIE Additions Consistency (MEDIUM)
**Rule:** BIE per Line 4 should equal the main interest expense field
```
BusInterestExpnsNotPassThruAmt == CYBusIntExpnsBfr163jLmtAmt (if both present)
```
**Tolerance:** $1
**Fires when:** Both fields are populated
**Risk:** Internal inconsistency within the same form = data mapping error in OIT

### BIE-007: Carryforward Non-Negative (MEDIUM)
**Rule:** Carryforward of previously disallowed interest should be ≥ 0
```
CfwdPrevDsallwIntExpenseAmt >= 0
```
**Fires when:** Field is present and non-zero
**Risk:** Negative carryforward is always wrong — sign convention error

### BIE-008: Total Allowable = CY BIE + Carryforward (MEDIUM)
**Rule:** Total allowable should combine current year BIE and prior year carryforward
```
TotalAllowableBusIntExpnsAmt == CYBusIntExpnsBfr163jLmtAmt + CfwdPrevDsallwIntExpenseAmt
```
**Tolerance:** $1
**Fires when:** Entity has both CY BIE and carryforward
**Risk:** Missing carryforward = permanently lost deduction

### BIE-009: Total Additions ≥ BIE Add-back (LOW)
**Rule:** Total additions should include at minimum the BIE add-back (Line 4)
```
TotalAdditionsAmt >= BusInterestExpnsNotPassThruAmt (if both present)
```
**Tolerance:** $1
**Fires when:** Entity has BIE being added back to ATI
**Risk:** If additions < BIE, then D&A or other items are incorrectly negative

### BIE-010: Negative ATI → Zero Applicable % (MEDIUM)
**Rule:** When ATI is negative, the 30% applicable amount should be 0
```
if AdjustedTaxableIncomeAmt < 0: AdjTaxableIncomeApplcblPctAmt == 0
```
**Fires when:** Entity has negative ATI
**Risk:** Applying 30% to a negative number is always wrong; floor is zero

### BIE-011: CFC Group Election Consistency (LOW)
**Rule:** If any entity has CFCGroupElectionInd = true, all entities in the return
should also have it (it's a group-wide election, not per-entity).
**Fires when:** Mixed true/false across entities in the same return
**Risk:** Inconsistent election flags indicate data mapping error

### BIE-012: BII ≤ BIE → Potential Issue (LOW)
**Rule:** Informational — when Business Interest Income ≥ BIE, entity is a net
creditor and 163(j) limitation shouldn't actually bite. If there's still a
disallowed amount, something is wrong.
```
if TotalBusinessInterestIncomeAmt >= CYBusIntExpnsBfr163jLmtAmt:
    DisallowedBusInterestExpnsAmt should be 0
```
**Fires when:** Net creditor entity shows disallowed BIE
**Risk:** Incorrect disallowance = understated deduction

### BIE-013: PY vs CY Rollover — Carryforward Accuracy (HIGH)
**Rule:** CY carryforward should equal PY disallowed BIE amount.
```
CY.CfwdPrevDsallwIntExpenseAmt == PY.DisallowedBusInterestExpnsAmt
```
**Tolerance:** $1
**Fires when:** Both PY and CY are available for the same entity
**Risk:** Lost or duplicated carryforward = material misstatement
**Implementation:** Requires prior_parser (PY file). Only runs in review mode (PY available).

## Integration Points

### Registration
Add to `lab/xml_parser/engine/checks/__init__.py`:
```python
from lab.xml_parser.engine.checks.form_8990 import run_form_8990_checks

ALL_CHECKS = [
    ...existing...,
    ("section_163j", run_form_8990_checks),
]
```

### ReviewEngine
The module receives the same `CheckContext` as other checks. It uses:
- `ctx.parser` to extract IRS8990 data
- `ctx.add()` to report findings
- For BIE-013 (rollover), it needs access to a prior parser.
  **Design:** Accept optional `prior_parser` on CheckContext. If present, run rollover check.

### Dependencies
- `parser.extract_form("IRS8990")` — already works (validated above)
- `_helpers.safe_float()` — standard numeric extraction
- `CheckContext` — standard pattern
- For BIE-013: ReviewEngine already passes prior parser path; we need to get access.

## Edge Cases

1. **Entity with no BIE:** Skip quietly — many entities have Form 8990 with zero
   interest expense (just taxable income for ATI purposes).
2. **FrmFldBySpcfdGrpParentInd = true:** This is the CFC Group parent rollup form.
   Skip individual checks (it's an aggregate). Only validate consistency with children.
3. **NaN/missing fields:** Treat as zero (consistent with other check modules).
4. **CFC Group Election:** When active, the 30% ATI is computed at the group level.
   Individual entity forms may show zero for limitation. Skip BIE-002/003 for these.
5. **Safe Harbor entities:** If SafeHarborElectionInd is checked, different rules apply.
   Flag but don't fail math checks.

## Expected Findings Profile

Based on sample returns (46 entities and 16 entities):
- Most entities will pass all checks (clean math)
- BIE-013 (carryforward rollover) is the most likely to fire — common mapping gap
- BIE-002 (30% math) occasionally fires due to rounding conventions in OIT
- BIE-011 (group consistency) fires if OIT maps the election flag inconsistently

## Test Strategy

1. Create fixture `lab/tests/fixtures/sample_8990_cy.xml` with 5 entities:
   - Entity A: Clean math, no carryforward
   - Entity B: Clean with carryforward
   - Entity C: ATI negative (tests BIE-010)
   - Entity D: Math errors (BIE-001, BIE-002, BIE-003 fire)
   - Entity E: Net creditor with incorrect disallowed (BIE-012 fires)
2. Create `sample_8990_py.xml` with 4 matching entities for rollover check (BIE-013)
3. Unit tests validate each check individually
4. Integration test runs against real sample XMLs (expected findings count)

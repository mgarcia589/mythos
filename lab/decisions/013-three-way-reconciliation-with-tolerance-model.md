# ADR 013 — Three-way reconciliation with tolerance model

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/xml_parser/reconciler.py`

## Context

IRS international tax compliance requires cross-checking entity financial
data across multiple sources: the filed XML e-return, client-provided
Excel workbooks, and ONESOURCE (OIT) export data. Discrepancies between
these sources can indicate filing errors, data entry mistakes, or
legitimate differences (rounding, sign conventions, dormant entities).

A naive equality comparison produces unacceptable false positive rates.
In production, two correctly filed values can differ by $0.50 due to
rounding, by sign due to OIT's inverted convention (ADR-011), or by
presence — XML may have a value where the workbook cell is blank because
the entity is dormant and was intentionally skipped.

The reconciler must compare 2 or 3 data sources per schedule per entity,
classify every field comparison into a meaningful status, and aggregate
results into pass rates that distinguish real errors from acceptable
differences.

## Decision

Implement a `Reconciler` class with a tolerance-based comparison model
and a 12-code status taxonomy across two-way and three-way modes.

**Tolerance model:**
- Default tolerance: $1.00 (configurable per invocation).
- A field comparison passes if `abs(source_a - source_b) <= tolerance`.
- Sign-flip detection: for fields in `SIGN_FLIP_FIELDS` (5 fields where
  OIT convention commonly inverts the sign), a secondary check compares
  absolute values — `abs(abs(a) - abs(b)) <= tolerance` → `PASS_SIGN_FLIP`.
- Dormant entity handling: XML value is NaN/None but workbook is exactly
  0 → `DORMANT_OK` (not counted as a failure).

**Status taxonomy (12 codes):**

Two-way (`FieldResult`): `PASS`, `FAIL`, `DORMANT_OK`, `XML_MISSING`,
`WB_MISSING`, `TYPE_MISMATCH`.

Three-way (`ComparisonResult`): `PASS`, `FAIL_OIT_WB`, `FAIL_OIT_XML`,
`FAIL_WB_XML`, `FAIL_ALL`, `OIT_MISSING`, `WB_MISSING`, `XML_MISSING`,
`PASS_SIGN_FLIP`, `DORMANT_OK`.

The three-way codes identify *which pair* disagrees — `FAIL_OIT_XML`
means OIT and XML differ while the workbook agrees with one of them.
This precision guides the reviewer to the correct source of the error.

**Pass rate computation:** `(PASS + DORMANT_OK) / (total - XML_MISSING)`.
Missing XML fields are excluded from the denominator because they
represent schedules not filed, not reconciliation failures.

## Alternatives considered

### Alternative A — Exact equality comparison with manual exception lists

Compare values for exact equality. Maintain a per-entity, per-field
exception list for known acceptable differences.

Rejected: exception lists don't scale. A 342-entity return with 15
schedules and ~20 fields per schedule produces ~100,000 comparisons.
Maintaining manual exceptions for rounding, dormancy, and sign
convention would require constant updates and produce false confidence
when an exception masks a real error. Tolerance-based comparison handles
these cases systematically.

### Alternative B — Percentage-based tolerance (e.g. within 0.1%)

Use relative tolerance instead of absolute. A comparison passes if the
values differ by less than 0.1% of the larger value.

Rejected: percentage tolerance breaks on small values and zeros. A $1
difference on a $100 field (1%) fails, while a $10,000 difference on
a $100M field (0.01%) passes. For IRS compliance, the absolute dollar
difference matters more than the relative magnitude — a $1 rounding
difference is acceptable on any field regardless of size, while a
$10,000 difference is never acceptable regardless of how large the
field is.

## Consequences

**Positive:**

- 12-code taxonomy gives reviewers actionable information: "OIT and
  XML disagree on Schedule H line 4" is more useful than "field mismatch."
- Sign-flip detection eliminates the most common false positive class
  in OIT reconciliation (ADR-011 flips at parse time, but legacy
  workbooks may not have been normalized).
- Dormant entity handling prevents hundreds of false failures per return
  for entities that are intentionally blank in the workbook.
- Pass rate excludes missing XML fields, giving an honest completion
  metric that doesn't penalize unfiled schedules.

**Negative / accepted costs:**

- The $1 default tolerance may be too loose for some engagements or too
  tight for others. Callers can override it, but the default is a
  judgment call. Accepted: $1 was calibrated against production data
  where rounding differences are consistently sub-dollar.
- `SIGN_FLIP_FIELDS` is a hardcoded set of 5 field names. If new fields
  exhibit sign-flip behavior, they must be added manually. Accepted:
  the set is small and stable — these fields correspond to specific IRS
  schedule lines where OIT's convention inverts.
- Three-way reconciliation requires all three sources to be available.
  If only two are present, the caller must use the two-way mode, which
  has a simpler (6-code) taxonomy. Accepted: the API makes both modes
  explicit.

**Future review triggers:**

- If tolerance needs to vary per schedule or per field (e.g. stricter
  on tax amounts, looser on E&P adjustments), the model would need
  per-field tolerance maps.
- If a fourth data source is added (e.g. prior-year filed return for
  rollover reconciliation), the comparison logic would need extension
  beyond three-way.

## Related specs / ADRs

- Spec: `lab/specs/reconciler.md`
- Related: ADR-011 (OIT sign convention — reconciler's `PASS_SIGN_FLIP`
  handles residual sign differences after OIT normalization)
- Related: ADR-007 (reconciler lives in `xml_parser/`, Layer 4)
- Related: ADR-015 (MythosService façade wraps reconciler for external
  consumers)

# ADR 011 — OIT sign convention adapter

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/core/oit_parser.py` (`OITSignConvention`, `OITDataSource`)

## Context

ONESOURCE Income Tax (OIT) exports use an inverted sign convention for
financial data: **negative values represent income/profit, positive
values represent losses/deductions**. This is the opposite of both
standard accounting convention and IRS form presentation, where income
is positive and deductions are positive expenses.

Every OIT data path — Working Trial Balance CSVs, Adjustment Analysis
exports, Sourcing Workpapers — follows this inverted convention. When
OIT data is compared against IRS XML (which uses standard convention)
or client-provided workbooks (which may use either convention), sign
mismatches produce false reconciliation failures if not normalized.

Sign convention errors are the single most common source of false
positives in tax compliance reconciliation. A difference of
$(2,000,000) that is actually correct (just inverted) is
indistinguishable from a real $2M error without knowing which
convention each data source uses.

## Decision

Implement `OITSignConvention` as a dedicated adapter class that
explicitly converts OIT sign convention to tax convention (positive =
income). All OIT data must pass through this adapter before entering
any comparison, display, or export pipeline.

The adapter provides two methods:
- `to_tax_convention(value)` — flips a single scalar
- `flip_series(series)` — flips an entire pandas Series

`OITDataSource` — the schedule-shaped DataFrame builder — applies the
convention internally when constructing schedule DataFrames from OIT
CSVs. Consumers of `OITDataSource.get_schedule()` receive data already
in tax convention, making the sign flip invisible to downstream code.

The convention rule is: **negate once at the boundary, never in business
logic**. No check, report, or reconciler should contain a sign flip —
if one appears there, it's a bug.

## Alternatives considered

### Alternative A — Flip signs at comparison time in the reconciler

Keep OIT data in its native convention and apply the sign flip inside
the reconciler when comparing OIT values against XML or workbook values.

Rejected: this scatters sign-awareness across every comparison site.
The reconciler would need to know which columns come from OIT (flip
needed) vs XML (no flip) vs workbook (depends). Every new schedule
comparison would need to remember the flip, and forgetting it once
produces silent wrong results — a $2M income showing as a $2M loss.
Centralizing the flip at the data boundary eliminates this class of
bug entirely.

### Alternative B — Store a convention flag on each DataFrame and auto-flip on access

Tag each DataFrame with its source convention (`"oit"`, `"xml"`,
`"workbook"`) and build a smart accessor that auto-normalizes values
when they're read.

Rejected: adds complexity without proportional benefit. The convention
is known at parse time — OIT data is always inverted, XML data is
always standard, workbook data depends on the client but is documented.
Normalizing at the boundary (parse time) is simpler and more reliable
than runtime introspection. A convention flag that's wrong is worse
than no flag at all — it silently produces double-flipped values.

## Consequences

**Positive:**

- Sign convention is handled exactly once, at the OIT parsing boundary.
  All downstream code (reconciler, checks, reports, UI) works with
  standard tax convention unconditionally.
- New OIT schedule builders inherit the convention automatically via
  `OITDataSource`'s internal normalization — no per-schedule sign logic.
- Reconciliation false positives from sign mismatches are eliminated
  for OIT-sourced data.
- The rule is auditable: grep for `OITSignConvention` to verify that
  every OIT data path goes through the adapter. Any OIT CSV read
  without a sign flip is a visible violation.

**Negative / accepted costs:**

- If a future OIT export changes its sign convention (unlikely but
  possible with a major OIT version update), the adapter would silently
  double-flip values. Mitigation: the adapter includes no runtime
  detection of convention — it always flips. A convention change would
  require updating the adapter, not removing it.
- Client-provided workbooks that use OIT convention (because they were
  exported from OIT) but aren't processed through `OITDataSource` won't
  be auto-normalized. The consumer must know to apply
  `OITSignConvention` manually. Accepted: workbook convention is
  documented per engagement in the wiki.
- The TRC-to-schedule mapping tables (`_SCH_C_INCOME_TRCS`,
  `_SCH_F_ASSET_TRCS`, etc.) are hardcoded in `oit_parser.py`. If OIT
  changes its TRC numbering scheme, the mappings need updating.

**Future review triggers:**

- If OIT introduces a new export format (e.g. JSON API instead of CSV),
  the parser functions need updating but the sign convention adapter
  remains the same — the convention is about OIT's data model, not its
  file format.
- If the reconciler needs to handle a third convention (e.g. a non-US
  tax authority with its own sign rules), generalize
  `OITSignConvention` into a `SignConvention` protocol with
  per-source implementations.

## Related specs / ADRs

- Spec: `lab/specs/core-module.md` (OIT adapter listed as orphan, Phase 5)
- Related: ADR-007 (`oit_parser.py` lives in `core/` — shared layer)
- Related: ADR-010 (xlsx_reader is the other ONESOURCE data adapter)
- Related: ADR-013 (future — reconciler consumes normalized OIT data)

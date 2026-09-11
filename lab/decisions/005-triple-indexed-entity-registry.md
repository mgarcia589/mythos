# ADR 005 — Triple-indexed entity registry with auto-populate

**Date:** 2026-09-10
**Status:** Accepted
**Implemented:** `lab/core/entity_registry.py` (v2, commit `3c6847c`)

## Context

The entity registry existed as a static lookup table with 36 hardcoded
sample entities and O(n) linear scan for every match operation. In
production, each IRS e-file XML contains the real entities in
`SubsidiaryReturn` nodes — the hardcoded list was only useful for tests
and demos. The classifier already parsed entities from the XML but didn't
persist them; each consumer that needed registry data re-parsed or
maintained its own entity list.

The registry's `match_by_name()` and `match_by_ref_id()` iterated the
full list on every call. For a 342-entity return, enrichment during
classification made O(342 × 342) = O(n²) comparisons.

## Decision

Rewrite `EntityRegistry` with three O(1) dict indexes (`_by_ref`,
`_by_name`, `_by_code`) and a `populate_from_parser(parser)` method that
auto-loads entities from the parsed XML. The registry becomes the
canonical entity inventory for the session, populated once from the XML
and then queried by the classifier, UI, and any future consumer.

## Alternatives considered

### Alternative A — Keep hardcoded list, add entries per client

Maintain a static entity list and grow it as new clients are onboarded.
Rejected: fundamentally broken — every new engagement would require code
changes, and there's no way to keep a static list in sync with what's
actually in each XML. The XML *is* the source of truth for which entities
are in the return.

### Alternative B — Eliminate the registry entirely

Have the classifier work directly with `SubsidiaryReturn` objects from
the parser, without an intermediate registry layer. Rejected: the
registry provides value beyond the classifier — it's the place where
external enrichment data (insurance flags, DRE codes, dormancy overrides)
can be merged in before classification. It also provides O(1) lookup by
name, ref_id, or code for any consumer that needs to find an entity
without re-parsing.

## Consequences

**Positive:**

- O(1) lookups for all three access patterns (ref_id, name, entity code).
- Auto-populate eliminates the hardcoded entity problem — registry always
  reflects the actual XML content.
- `by_form_type()` enables per-form queries (e.g. "all 5471 entities")
  without filtering the full list.
- Sample entities preserved via `EntityRegistry.sample()` for backward
  compat in tests and demos.

**Negative / accepted costs:**

- The registry must be populated before the classifier can enrich from it.
  This creates an ordering dependency: parse → populate registry → classify.
  Accepted: this order is natural and enforced by the pipeline.
- Name-based matching is exact (case-insensitive, trimmed). Fuzzy matching
  (e.g. "Entity Ltd" vs "Entity Limited") is not supported.
  Accepted for now — IRS e-file entity names are consistent within a return.

**Future review triggers:**

- If multi-return analysis is needed (comparing entities across returns),
  the registry will need merge/dedup logic.
- If fuzzy name matching becomes necessary, consider adding a normalized
  name index or Levenshtein-based fallback.

## Related specs / ADRs

- Spec: `lab/specs/core-v2-upgrade.md` (Fase 2: Registry auto-populate)
- Related: ADR-002 (classifier consumes the registry for enrichment)
- Related: ADR-006 (synthetic ref IDs for entities the registry can't index by ref)

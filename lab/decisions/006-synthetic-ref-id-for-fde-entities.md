# ADR 006 — Synthetic ref IDs for FDE/partnership entities

**Date:** 2026-09-10
**Status:** Accepted
**Implemented:** `lab/core/entity_classifier.py` (`_synthesize_ref_id`)

## Context

IRS Form 8858 (FDE) and Form 8865 (partnership) entities in e-file XML
frequently have an empty `reference_id` field. In a large production
return (8.2MB, 381 subsidiary nodes), 199 out of 381 had `reference_id=''`.
These are legitimate entities with full form data — they're just not
assigned a numeric reference ID by the ONESOURCE software the way 5471
entities are.

The original classifier skipped entities without a `reference_id`
(`if not ref: continue`), which meant 55% of the return's entities were
invisible. A UI workaround attempted to fill them in by using the entity
name as the `reference_id`, which put full entity names like "Subsidiary Europe
Limited" in the Ref ID column — confusing and not a stable identifier.

## Decision

Generate a synthetic `reference_id` by extracting the suffix from the
entity's `document_id` (the unique XML element identifier assigned by
ONESOURCE). For example, `IRS8858000AL4I2` → `000AL4I2`. This is stable
(same XML always produces the same ID), compact, and unique within a
return. When no `document_id` is available, fall back to a sequential
counter (`FDE-0001`, `FDE-0002`, ...).

Deduplication by `reference_id` is applied in the classify loop
(`seen_ids` set) so that entities appearing multiple times in the XML
(common for 8858 entries) are consolidated into a single
`ClassifiedEntity`.

## Alternatives considered

### Alternative A — Use the entity name as identifier

Use `entity.name` as the `reference_id` for entities without one. Rejected:
names are long, not unique (multiple entities can share a name with
different suffixes like "- DivCon"), and placing them in the Ref ID column
is confusing in the UI. Names belong in the Entity Name column.

### Alternative B — Skip FDE entities entirely

Keep the `if not ref: continue` behavior and only classify 5471 entities
that have proper reference IDs. Rejected: this silently drops 55% of
entities in a real return. FDEs are a critical part of compliance review —
they have their own forms, schedules, and tax owner relationships that
need to be visible.

## Consequences

**Positive:**

- All entities in the XML are now classified (342 vs 182 previously for
  the production return).
- Ref IDs are compact and stable — same XML always produces the same IDs.
- FDEs correctly get `form_type="8858"` and `is_dre=True`, enabling
  proper form-type filtering and completeness scoring.
- Entity dedup eliminates the duplicate rows that appeared when the same
  entity had multiple `SubsidiaryReturn` nodes in the XML.

**Negative / accepted costs:**

- Synthetic IDs like `000AL4I2` are not human-meaningful — a reviewer
  can't tell which entity it refers to without looking at the name column.
  Accepted: the OIT locator (first 6 chars) provides correlation with
  ONESOURCE, and the name column is always visible.
- The `FDE-NNNN` fallback (no document_id) produces IDs that aren't stable
  across re-parses if entity order changes in the XML. Accepted: this
  fallback is extremely rare — ONESOURCE always assigns document IDs.

**Future review triggers:**

- If ONESOURCE changes its `document_id` format, `_synthesize_ref_id`
  will need updating.
- If cross-return entity matching is needed, synthetic IDs won't match
  across different XMLs. A name-based or EIN-based matching strategy would
  be needed at that point.

## Related specs / ADRs

- Spec: `lab/specs/core-v2-upgrade.md`
- Requires: ADR-005 (registry can't index FDEs by ref_id without synthetic IDs)
- Requires: ADR-002 (classifier pipeline is where the synthesis happens)

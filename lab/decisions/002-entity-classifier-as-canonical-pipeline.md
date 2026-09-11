# ADR 002 — EntityClassifier as the canonical entity pipeline

**Date:** 2026-09-10
**Status:** Accepted
**Implemented:** `lab/core/entity_classifier.py` (v2, commit `3c6847c`)

## Context

Before the core/ v2 upgrade, entity data was spread across six fragmented
representations: raw `SubsidiaryEntity` from the parser, schedule-specific
DataFrames indexed by `_reference_id`, `Entity` dataclass in the registry,
`EntityData` input for the tagger, `TagResult` output, and ad-hoc dicts
built in UI pages. Every consumer (UI, review engine, export) assembled its
own partial entity view by reaching into 2-3 of these sources, leading to
inconsistent data (e.g. the entities page computed tags differently from the
parsed-data tab) and O(n²) redundant parsing.

The classifier module existed but was a thin wrapper — it classified by
building entities from scratch each call without caching, and its output
wasn't treated as the single authority downstream.

## Decision

Make `EntityClassifier.classify()` the one-shot pipeline that produces
`ClassifiedEntity` as the canonical post-parse entity representation.
One parse → one classify → one list of `ClassifiedEntity` objects that carry:
identity (Page 1 fields), schedule data (prefix-stripped dicts), tags,
contradictions, completeness score, and form type. All consumers use this
list; nobody assembles entity data independently.

## Alternatives considered

### Alternative A — Enrich inside the parser itself

Make `EFileParser.parse()` return fully classified entities instead of raw
`SubsidiaryReturn` objects. Rejected: the parser's job is structural
extraction (XML → DataFrames/dataclasses), not business-level
classification. Mixing fiscal logic (tags, completeness) into the parser
would couple two concerns that change for different reasons — parser
changes when the XML schema changes, classifier changes when tax rules
change.

### Alternative B — Lazy per-entity classification on demand

Instead of classifying all entities upfront, compute `ClassifiedEntity` on
first access per entity (lazy property pattern). Rejected: the entity list
is needed in bulk for summary statistics, tag distributions, and the
entities table — lazy access would scatter O(1) indexing work across N
call sites and make caching harder. Batch classification with a single
cache key (parser path) is simpler and faster in practice.

## Consequences

**Positive:**

- Single source of truth: every consumer (UI, review engine, export, CLI)
  gets the same entity data from the same pipeline.
- O(n) indexing via `groupby()` + classification cache eliminates redundant
  parsing — second call returns in ~0.005ms instead of ~1,750ms.
- Completeness scoring, form type detection, and DRE/insurance flags are
  computed once, not reimplemented per consumer.

**Negative / accepted costs:**

- All entity data must flow through the classifier; consumers can't get
  "just the raw parsed entity" without importing the parser directly.
  Accepted: the classifier is fast enough (2.6s for 342 entities on 8.2MB
  XML) that the overhead is negligible.
- `ClassifiedEntity` is a large dataclass (~30 fields). Adding fields to it
  requires touching the classifier. Accepted: this is intentional — it
  forces entity schema changes to go through one place.

**Future review triggers:**

- If entity classification becomes async (e.g. external API enrichment),
  the batch-then-cache pattern may need to become streaming.
- If a second parser type is added (e.g. PDF-based entity extraction),
  the classifier interface will need to accept multiple parser types.

## Related specs / ADRs

- Spec: `lab/specs/core-v2-upgrade.md` (Fase 3: Classifier perf + completeness)
- Spec: `lab/specs/core-module.md` (module inventory)
- Related: ADR-003 (tagging rules consume ClassifiedEntity via `.to_entity_data()`)
- Related: ADR-005 (registry feeds enrichment into the classifier pipeline)

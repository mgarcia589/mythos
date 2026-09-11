# ADR 003 — Deterministic rule-based entity tagging

**Date:** 2026-09-10
**Status:** Accepted
**Implemented:** `lab/core/entity_tagger.py`, `lab/core/tagging_rules.py`

## Context

Mythos classifies each IRS Form 5471 entity by fiscal behavior — tested
income, tested loss, Subpart F, high-tax exclusion, dormant, etc. This
classification drives what validation rules fire, what data the reviewer
should focus on, and how the entity appears in the UI. The question was how
to implement this classification: with deterministic rules that map
schedule fields to tags, or with a scoring/ML approach.

The domain is IRS tax compliance, where every classification has a precise
statutory definition (IRC §951A, §951, §954, etc.) and the input data is
structured XML with well-defined fields. There is no ambiguity in whether
an entity has tested income — it's a numeric field in Schedule I that is
either positive, negative, or zero.

## Decision

Use a `TagRule` protocol with pure `(EntityData) → bool` functions, one per
tag. Each rule reads specific schedule fields and returns True/False.
Rules are registered in `DEFAULT_RULES` (currently 8, planned 16) and
executed by `EntityTagger` with built-in contradiction detection. Evidence
(which fields triggered each tag) is captured in `tag_metadata`.

## Alternatives considered

### Alternative A — Weighted scoring model

Assign numeric scores per indicator (e.g. +0.8 for positive tested income,
+0.3 for QBAI > 0) and classify based on threshold. Rejected: introduces
false uncertainty into a domain where classifications are binary by
statute. A "0.73 probability of tested income" is meaningless when the
field either has a positive value or doesn't. Scoring also makes
contradiction detection harder — two scores can both be above threshold
without flagging the logical impossibility.

### Alternative B — Single monolithic classify function

One big function with nested if/elif branches for all tags. Rejected:
impossible to test individual rules in isolation, adding a new tag
requires modifying a 200+ line function, and there's no way to list which
rules are active or generate evidence trails. The `TagRule` protocol
makes each rule independently testable (1 True test + 1 False test per
rule) and introspectable.

## Consequences

**Positive:**

- Each tag maps 1:1 to a statutory provision, making the classification
  auditable and explainable to tax professionals.
- Rules are individually testable — 2 tests per rule guarantees coverage.
- Contradiction detection catches logically impossible tag combinations
  (e.g. `tested_income` + `tested_loss` on the same entity).
- Adding a new tag is additive: write the function, add the `TagRule`,
  add tests. No existing code changes.

**Negative / accepted costs:**

- Rules can't express probabilistic or fuzzy classifications. If future
  needs require "likely dormant" (e.g. all fields near-zero but not exactly
  zero), this architecture doesn't support it natively. Accepted: IRS
  e-file data is precise, not fuzzy.
- 16 separate functions + 16 `TagRule` entries is more boilerplate than a
  single classifier function. Accepted: the testability and auditability
  trade-off is worth it for a compliance tool.

**Future review triggers:**

- If Mythos expands to non-US jurisdictions (Pillar Two) where
  classification rules are less binary, reconsider whether pure boolean
  rules are sufficient.
- When tag count exceeds ~25, consider grouping rules into categories
  (GILTI rules, Subpart F rules, structural rules) for maintainability.

## Related specs / ADRs

- Spec: `lab/specs/entity-tagger.md` (full tag inventory, priority, schedule mapping)
- Spec: `lab/specs/core-v2-upgrade.md` (Fase 1: Tagger 16 rules)
- Requires: ADR-002 (tags are applied inside the ClassifiedEntity pipeline)

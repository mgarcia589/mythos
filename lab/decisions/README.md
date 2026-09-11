# Architecture Decision Records (ADRs)

This folder captures the reasoning behind significant architecture decisions in
Mythos — not just *what* was decided, but *why*, what alternatives were
considered, and what tradeoffs were accepted. It exists so nobody (including
future-you) "fixes" something six months from now that's deliberately built
the way it is, for reasons that would otherwise be lost.

ADRs are the *why* layer. `lab/specs/` is the *what/how* layer, per module or
feature. An ADR can — and often should — reference the spec(s) it underlies.

## When to write one

- **Before implementing**, when the task requires an architecture decision not
  already covered by an existing ADR. Skipping this turns the decision into an
  implicit implementation detail, and the reasoning gets lost.
- **Before reversing or materially changing** a previous decision.

Day-to-day choices — naming a helper, picking a library for a one-off script,
how to structure a small component — don't need an ADR. The filter: if in
twelve months someone (probably you) might ask "why did we do it this way?"
and the answer would matter, write one.

## How to create a new ADR

```bash
cp lab/decisions/000-template.md lab/decisions/NNN-short-slug.md
```

Where `NNN` is the next available sequential number. Delete the HTML comment
block from the template, fill in every required section, start at status
`Proposed`, move to `Accepted` once you're satisfied it holds up (see gate
below).

## Numbering

- Sequential, three digits: `001`, `002`, `003`, ...
- **A number is never reused once assigned**, even if that ADR is later
  deprecated or superseded.
- Gaps are never backfilled. The sequence reflects history, not a clean
  inventory.

## Status lifecycle

`Proposed → Accepted → (Superseded by ADR-NNN | Deprecated)`

Only these four values go in `Status` — no free text appended to it.
Metadata like acceptance date, implementation status, or scope goes on its
own line below the header (`**Implemented:** ...`, `**Scope:** ...`), so
`Status` stays parseable.

- **Proposed.** Draft, not yet settled. Not a contract.
- **Accepted.** In effect. This is the canonical state for a decision in force.
- **Superseded by ADR-NNN.** A later ADR replaced this decision. Kept as a
  historical record of the earlier reasoning.
- **Deprecated.** No longer applies, and nothing replaced it. Rare.

## Immutability

Once `Accepted`, an ADR's Context / Decision / Alternatives / Consequences
don't change. If the decision changes, write a **new** ADR that supersedes
it — never edit the old one's reasoning. The superseded ADR stays as-is,
a record of what was believed and why at the time.

Allowed edits to an `Accepted` ADR:

- Flipping `Status` to `Superseded by ADR-NNN` or `Deprecated`.
- Adding a link under "Related specs / ADRs" when a new ADR interacts with it.
- A dated note under "Notes" that reconciles the document with reality
  (e.g. "as of 2026-11, this was implemented in X") **without** changing the
  Decision itself.

## Required sections

Everything in `000-template.md` except "Notes" (explicitly optional).
In particular:

- **Alternatives considered.** At least two. An ADR with no real alternative
  is suspect — if there was nothing to choose between, it probably wasn't a
  decision worth an ADR.
- **Consequences.** Both positive and negative. An ADR that only lists upside
  didn't document the tradeoff honestly enough.

**Gate before promoting to `Accepted`:** re-read the checklist above — Context,
Decision, Alternatives (≥2), Consequences (positive *and* negative), Related
specs/ADRs — all filled in. This is a solo project, so the "gate" is
self-review, not a second approver; if that changes (other contributors join),
revisit this section.

## Slug convention

`kebab-case`, descriptive. Format: `NNN-short-slug.md`
(e.g. `001-adopt-architecture-decision-records.md`).
Reference in text/commits as `ADR-NNN` (the prefix, not the filename).

## Index

| # | Slug | Status | Title |
|---|------|--------|-------|
| 001 | [adopt-architecture-decision-records](001-adopt-architecture-decision-records.md) | Accepted | Adopt Architecture Decision Records for this project |
| 002 | [entity-classifier-as-canonical-pipeline](002-entity-classifier-as-canonical-pipeline.md) | Accepted | EntityClassifier as the canonical entity pipeline |
| 003 | [deterministic-rule-based-entity-tagging](003-deterministic-rule-based-entity-tagging.md) | Accepted | Deterministic rule-based entity tagging |
| 004 | [unified-mythos-error-hierarchy](004-unified-mythos-error-hierarchy.md) | Accepted | Unified MythosError hierarchy |
| 005 | [triple-indexed-entity-registry](005-triple-indexed-entity-registry.md) | Accepted | Triple-indexed entity registry with auto-populate |
| 006 | [synthetic-ref-id-for-fde-entities](006-synthetic-ref-id-for-fde-entities.md) | Accepted | Synthetic ref IDs for FDE/partnership entities |

Keep this table updated by hand — new ADR, new row.

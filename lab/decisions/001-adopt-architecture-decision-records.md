# ADR 001 — Adopt Architecture Decision Records for this project

**Date:** 2026-09-11
**Status:** Accepted

## Context

Mythos already documents feature-level design in `lab/specs/` (framework,
strategy, and per-module specs — 14+ files as of v0.7.5), but there's no
place that captures the *why* behind cross-cutting architecture and process
decisions independent of any single spec: dependency choices, module
boundaries, why a design was picked over a competing one. As the project has
grown across several minor versions (v0.6.1 → v0.7.5: desktop UI, entity
classifier, PDF validator, reconciliation engine), that reasoning lives only
in commit messages or memory, if anywhere — and specs describe what a module
does, not why competing designs for it were rejected.

## Decision

Adopt a lightweight ADR practice under `lab/decisions/`, following the format
in `000-template.md`: sequential numbering, a closed status vocabulary
(`Proposed → Accepted → Superseded/Deprecated`), and immutability once
accepted. ADRs capture the *why* for decisions that would need explaining a
year from now; `lab/specs/` continues to capture the *what/how* per module.

## Alternatives considered

### Alternative A — Keep using commit messages / spec files as the only record

Cheapest option, zero new process. Rejected: reasoning gets scattered across
commit history and hard to find later, and specs already conflate "how this
module works" with "why it's built this way" — a decision spanning multiple
specs (e.g. why entities are classified with deterministic rules rather than
a scoring model) has no single home once the specs list grows past a
handful of files.

### Alternative B — Full governance modeled on the partner-os ADR process (principle citations, mandatory second-reviewer promotion gate, issue-tracker linking)

Rejected for now: this is a solo project. A promotion gate requiring a second
approver doesn't apply, and there's no VISION-equivalent doc here to cite
principles from. Importing the full multi-person apparatus would be process
for its own sake — revisit if the project gains other contributors (see
Future review triggers).

## Consequences

**Positive:**

- Architecture reasoning gets one findable home, separate from per-module specs.
- Changing a settled decision later requires a new ADR that references the
  old one, instead of silent drift nobody can trace.
- Cheap to run solo — a folder and a template, no new tooling or CI gate.

**Negative / accepted costs:**

- One more artifact to maintain per significant decision; without a second
  reviewer, keeping the practice honest is entirely self-discipline.
- No retroactive ADRs for decisions already made before v0.7.5 (e.g. why
  NiceGUI for the desktop UI, why the entity classifier uses 16 deterministic
  rule tags) — the record starts now, not from v0.6.1.

**Future review triggers:**

- If Mythos gains other contributors, revisit Alternative B — add an actual
  promotion gate / reviewer requirement instead of self-review.

## Related specs / ADRs

- Governance: `lab/decisions/README.md`
- Related specs: `lab/specs/mythos-framework.md`, `lab/specs/mythos-strategy.md`

## Notes

First ADR in this project — establishes the practice itself. Adapted from the
ADR methodology used in the Parso team's `partner-os` repo, scaled down from
a multi-person governance process to fit a solo project.

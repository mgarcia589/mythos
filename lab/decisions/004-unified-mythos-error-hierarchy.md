# ADR 004 — Unified MythosError hierarchy

**Date:** 2026-09-10
**Status:** Accepted
**Implemented:** `lab/xml_parser/core/exceptions.py` (commit `3c6847c`)

## Context

Two independent exception hierarchies coexisted in the project:

1. `lab/core/errors.py`: `CerebroError` base with 12 subclasses (186 LOC),
   including useful concepts — `ErrorContext` dataclass (entity, schedule,
   field, page), `Severity` enum, and `.to_log_entry()` for structured
   logging. **Zero runtime consumers** (no imports found across the entire
   project).

2. `lab/xml_parser/core/exceptions.py`: `MythosError` base with 3 subclasses
   (33 LOC), the hierarchy actually used in production by the parser,
   review engine, and service layer.

The dual hierarchy created confusion: new code had to choose which tree to
raise from, and the useful concepts (Severity, ErrorContext) were stranded
in the unused tree.

## Decision

Consolidate into a single `MythosError` tree in
`lab/xml_parser/core/exceptions.py`. Migrate the useful concepts from
`CerebroError` (ErrorContext, Severity, `.to_log_entry()`) into
`MythosError`. Expand the hierarchy with subclasses that match the project's
actual error domains (Parse → XML/PDF/Workbook, Validation → MissingField/
Inconsistency, Reconciliation → Phantom/MaterialMismatch, Export, Config →
DependencyMissing). Delete `lab/core/errors.py`.

## Alternatives considered

### Alternative A — Keep both hierarchies, wire CerebroError into runtime

Make the review engine and parser catch/raise `CerebroError` instead of
(or alongside) `MythosError`. Rejected: this means maintaining two base
classes, two import paths, and two `.to_log_entry()` implementations. The
naming itself was confusing — "Cerebro" is the second-brain project,
"Mythos" is the compliance engine. There's no reason for both to exist.

### Alternative B — Eliminate structured error metadata entirely

Delete `CerebroError` and keep `MythosError` minimal (path + reason, like
the original 33-LOC version). Rejected: `ErrorContext` and `Severity` are
genuinely useful for downstream log routing and the UI error panel. Losing
them would mean re-inventing them later when error reporting needs mature.

## Consequences

**Positive:**

- Single import path for all exceptions: `from lab.xml_parser.core.exceptions import ...`
- Structured context (entity_ref, schedule, field) available on any error.
- Severity routing enables future log-level filtering and UI triage.
- Deleted 186 LOC of dead code.

**Negative / accepted costs:**

- The exception module grew from 33 LOC to 155 LOC. More classes to know
  about, though most consumers only catch `MythosError` or `ParseError`.
- Exceptions live in `xml_parser/core/` even though they're used
  project-wide. The location is a historical artifact. Accepted: moving
  them to `lab/core/` would be another migration with no functional
  benefit, and `xml_parser/core/__init__.py` re-exports everything cleanly.

**Future review triggers:**

- If a third-party integration layer is added (e.g. API server), consider
  adding HTTP-status-aware exception subclasses.
- If `xml_parser/core/` is ever split into a standalone package, the
  exceptions should move to `lab/core/` at that point.

## Related specs / ADRs

- Spec: `lab/specs/core-v2-upgrade.md` (Fase 4: Error hierarchy cleanup)
- Re-exports: `lab/xml_parser/core/__init__.py`

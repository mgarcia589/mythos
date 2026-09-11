# ADR 015 — MythosService façade as sole entry point

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/xml_parser/api/service.py`

## Context

Mythos has multiple internal engines: `ReviewEngine` (compliance checks),
`EFileParser` (XML extraction), `Reconciler` (data comparison),
`EntityClassifier` (entity pipeline), and 4 exporters (Excel, PDF, HTML,
CSV). These engines have different constructors, return different types,
and require specific initialization sequences (e.g. parse before review,
classify before tag).

Without a façade, every consumer — the CLI, the NiceGUI UI, standalone
scripts, and future integrations — would need to know the correct
initialization order, import the right engine classes, handle errors
individually, and manage timing/progress reporting. This couples every
consumer to every engine's internal API.

## Decision

Implement `MythosService` as the sole public entry point for all Mythos
operations. All consumers (CLI, UI, scripts) instantiate `MythosService`
and call its methods instead of touching engines directly.

**API surface (12 public methods):**
- `review()` — run compliance checks, wraps `ReviewEngine`
- `list_entities()` — quick entity scan, wraps `EFileParser`
- `classify_entities()` — full entity classification, wraps `EntityClassifier`
- `tag_entities()` — entity tagging, delegates to `classify_entities`
- `reconcile()` — data comparison, wraps `Reconciler`
- `export_findings()` — export review results (Excel/CSV/JSON/PDF)
- `export_rollover()` — export rollover analysis (Excel/CSV/HTML/PDF)
- `export_parsed_data()` — export raw schedule data
- `export_full()` — combined deliverable package
- `full_review()` — end-to-end pipeline (parse + rollover + checks + export)
- `full_review_all()` — unified auto-detect mode for all form types

**Façade guarantees:**
1. Every method returns a typed `@dataclass` result (`ReviewResult`,
   `ReconcileResult`, `ExportResult`, etc.) — never raw engine output.
2. Every method wraps execution in try/except with structured error
   reporting.
3. Every method times itself with `perf_counter` and includes duration
   in the result.
4. Progress reporting via an optional `ProgressCallback` passed at
   construction — consumers get status updates without polling.
5. Lazy imports: engines are imported inside methods, not at module
   level, keeping the import footprint minimal.

## Alternatives considered

### Alternative A — Let consumers import engines directly

No façade. CLI imports `ReviewEngine`, UI imports `EFileParser` and
`Reconciler`, scripts import whatever they need.

Rejected: this worked when Mythos had one engine (parser + checks), but
with 5+ engines and 4 exporters, consumers were duplicating
initialization logic, error handling, and timing code. The UI's
`bridge.py` was becoming a second façade without the discipline — it
imported 6 engine classes and replicated try/except patterns that
belonged in a shared layer. Centralizing in `MythosService` eliminated
the duplication and gave all consumers consistent error handling and
progress reporting.

### Alternative B — Thin wrapper functions (module-level, no class)

Export top-level functions from `lab/xml_parser/api/` instead of a
class. Each function encapsulates one operation.

Rejected: the class provides two things functions can't: (1) shared
configuration via `MythosConfig` passed at construction, and (2)
a progress callback that persists across multiple method calls in the
same session. Module-level functions would need these passed as
parameters every time, or use module-level globals — which is what
the UI already had and was trying to move away from.

## Consequences

**Positive:**

- Single import, single instantiation for any consumer:
  `svc = MythosService(); result = svc.full_review(xml_path)`.
- Typed result dataclasses make it impossible to misinterpret output —
  `result.findings`, `result.duration_seconds`, `result.error` are
  explicit fields, not dict keys or tuple positions.
- Adding a new operation means adding one method to `MythosService`
  with the standard pattern (try/except, timing, progress, typed
  result). Consumers don't need to know about the new engine class.
- Progress callback works across all operations, enabling the UI to
  show a unified progress bar regardless of whether a review, export,
  or reconciliation is running.

**Negative / accepted costs:**

- The façade adds a layer of indirection. Debugging "why did review
  fail?" requires stepping through `MythosService.review()` before
  reaching `ReviewEngine`. Accepted: the indirection is one method
  deep and the error is captured in the result dataclass.
- `MythosService` grows with every new operation — it's currently 12
  methods and will expand. Accepted: the alternative (splitting into
  multiple service classes) would require consumers to know which
  service handles which operation, reintroducing the coupling the
  façade eliminates.
- Lazy imports inside methods add a small overhead on first call
  (~10ms). Accepted: negligible compared to the operations themselves
  (seconds for reviews, minutes for batch exports).

**Future review triggers:**

- If `MythosService` exceeds ~20 methods, consider splitting into
  domain-specific sub-services (`ReviewService`, `ExportService`,
  `ReconcileService`) behind a single `MythosService` that delegates.
- If Mythos adds a REST API or gRPC interface, `MythosService` is the
  natural backend — each method maps to an endpoint. The typed result
  dataclasses serialize cleanly.

## Related specs / ADRs

- Related: ADR-007 (`MythosService` is Layer 5 — the API layer between
  engines and presentation)
- Related: ADR-008 (NiceGUI UI consumes `MythosService` via `bridge.py`)
- Related: ADR-009 (check engine is one of the engines the façade wraps)
- Related: ADR-013 (reconciler is another engine behind the façade)

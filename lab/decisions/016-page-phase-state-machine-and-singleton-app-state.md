# ADR 016 — PagePhase state machine and singleton AppState

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/mythos_ui/services/xml_check_state.py` (PagePhase, XmlCheckState), `lab/mythos_ui/services/bridge.py` (AppState)

## Context

The Mythos desktop UI (ADR-008) manages a multi-step compliance review
workflow: upload files → select processing mode → run analysis →
display results across 7+ tabs (overview, issues, entities, schedules,
rollover, parsed data, forms). Each step transitions the UI between
different states — buttons enable/disable, tabs populate, progress bars
animate, error messages appear.

Without a formal state model, UI code scattered across 12+ page files
would each independently check combinations of flags (`has_report`,
`is_processing`, `has_parser`, `has_error`) to decide what to render.
This produced inconsistent states — e.g. the export button enabling
before analysis completed, or tabs showing stale data from a previous
run while a new analysis was in progress.

The UI also needs session-wide state: the current parser, review report,
rollover reports, PDF validation results, filter settings, and review
history. This state is accessed from every page and must persist across
page navigation without re-computation.

## Decision

Implement a two-layer state model:

**Layer 1: `PagePhase` enum + `XmlCheckState` dataclass** — governs the
XML check workflow lifecycle.

`PagePhase` has 7 states:
`INITIAL` → `FILES_UPLOADED` → `PROCESSING` → `COMPLETED` |
`COMPLETED_WITH_WARNINGS` | `FAILED` | `PARTIAL_SUCCESS`

`ProcessingMode` has 3 values: `PARSE_ONLY`, `ROLLOVER_ONLY`,
`FULL_REVIEW`.

`XmlCheckState` bundles the phase with all page-specific state: file
entries, active tab, parse summary, selected entity/form, view mode,
search query, filters, progress, warnings, and error messages. Its
`reset()` method returns the entire page to `INITIAL` cleanly.

UI components check `state.xml_check.phase` to decide rendering — a
single enum comparison instead of multi-flag boolean logic.

**Layer 2: `AppState` dataclass** — session-wide singleton at module
level in `bridge.py`.

Fields: `report`, `parser`, `current_xml`, `prior_xml`, `progress`,
`filters`, `history`, `rollover_reports`, `pdf_result`, and an
embedded `xml_check: XmlCheckState`.

Accessed via `get_state()` (returns the singleton) and `clear_state()`
(replaces it). The singleton is a deliberate constraint: Mythos is a
single-user desktop application (ADR-008), so one global state object
per process is correct.

The sync-to-async bridge in `bridge.py` wraps `MythosService` (ADR-015)
calls for NiceGUI's async event loop, updating `AppState` fields as
operations complete.

## Alternatives considered

### Alternative A — Per-page local state with event-driven coordination

Each page maintains its own state object. Pages communicate via
NiceGUI's event system (`ui.notify`, custom events) when state changes.

Rejected: event-driven coordination between 12+ pages produces race
conditions and ordering bugs — e.g. the entities tab receives a
"review complete" event before the overview tab, rendering with stale
data. A centralized state object that all pages read from eliminates
ordering issues — every page sees the same state at the same time.

### Alternative B — NiceGUI's built-in `app.storage` for all state

Store everything in `app.storage.user` (a persistent dict per user
session). Pages read/write named keys.

Rejected: `app.storage.user` is a string-keyed dict with no type
safety, no lifecycle management, and no reset semantics. Storing
complex objects (parser instances, DataFrames, report trees) in a
generic dict loses the structure that makes the state auditable. A
typed dataclass makes the state shape explicit and discoverable —
you can read `AppState`'s definition and know exactly what state
exists in the application.

## Consequences

**Positive:**

- `PagePhase` makes UI transitions deterministic: button
  enable/disable, tab population, and progress display are all
  driven by a single enum. Adding a new phase is a one-line enum
  addition plus the rendering logic for that phase.
- `XmlCheckState.reset()` provides a clean state reset path —
  critical for when the user uploads a new XML and expects a fresh
  analysis with no residual state from the previous run.
- The module-level singleton is simple, debuggable (one object to
  inspect), and matches the single-user constraint.
- `ProcessingMode` makes the three analysis paths (parse-only,
  rollover-only, full review) explicit rather than inferring them
  from which files are present.

**Negative / accepted costs:**

- The module-level singleton precludes multi-user support. If Mythos
  ever serves multiple concurrent users (e.g. web deployment), the
  state model needs to become per-session. Accepted: Mythos is a
  desktop tool; multi-user is not on the roadmap (ADR-008 notes
  this as a future review trigger).
- All pages depend on the same `AppState` — a change to the dataclass
  can require updates across multiple pages. Accepted: the alternative
  (per-page state) had worse coupling through implicit event
  dependencies.
- `XmlCheckState` has 15+ fields, making it a large dataclass. Some
  fields (`search_query`, `view_mode`) are UI-specific details that
  arguably don't belong in a state model. Accepted: keeping them
  here ensures they survive page navigation, which is the primary
  requirement.

**Future review triggers:**

- If Mythos moves to web deployment with concurrent users, replace
  the module-level singleton with NiceGUI's per-session storage,
  wrapping it in the same `AppState` interface.
- If the state model grows past ~25 fields, consider splitting
  `AppState` into domain sub-states (review state, export state,
  PDF state) composed into a root state.

## Related specs / ADRs

- Related: ADR-008 (NiceGUI + pywebview — the UI framework that
  dictates the async model and storage API)
- Related: ADR-015 (MythosService is consumed via the bridge's
  sync-to-async wrapper)
- Related: ADR-007 (`mythos_ui/` is Layer 6 — the presentation layer)

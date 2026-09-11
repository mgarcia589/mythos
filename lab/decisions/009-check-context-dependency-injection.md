# ADR 009 — CheckContext dependency injection for the check engine

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/xml_parser/engine/checks/_helpers.py` (CheckContext), `lab/xml_parser/engine/checks/__init__.py` (ALL_CHECKS)

## Context

The Mythos check engine runs 44+ compliance checks across 7 categories
(flow, completeness, reasonableness, rollover, cross-schedule, cross-form,
section 163j). Each check needs access to:

- The parsed return (`EFileParser`) for schedule extraction
- A pre-built DataFrame (`df`) with entity-level financial data
- An entity name resolver (`_get_entity_name`) to map entity codes to names
- Optionally, a prior-year parser for rollover comparisons
- A findings accumulator to report issues

Without a shared mechanism for providing these dependencies, each check
function would either (a) import the parser and state globally — coupling
checks to a specific runtime context and making them untestable in
isolation — or (b) accept 5+ individual parameters, producing fragile
signatures that break every time a new dependency is added.

The engine also needs a way to register which checks exist and in what
order they run. The registration mechanism determines how easy it is to
add, remove, or reorder checks.

## Decision

Introduce `CheckContext` as a dependency injection bag and `ALL_CHECKS` as
an explicit flat registry.

**CheckContext** is a dataclass that bundles all check dependencies into a
single object passed to every check function:

- `parser: EFileParser` — the current-year parsed return
- `df: pd.DataFrame` — pre-built entity financial data
- `_get_entity_name: Callable` — entity code → name resolver
- `prior_parser: Optional[EFileParser]` — prior-year return for rollover
- `_findings: list[Finding]` — accumulator with `add()` method

Each check is a plain function with signature
`(ctx: CheckContext) -> list[Finding]`. Checks call `ctx.add(...)` to
report findings and access all dependencies through the context object.

**ALL_CHECKS** is a flat list of `(category_name, callable)` tuples in
`lab/xml_parser/engine/checks/__init__.py`:

```python
ALL_CHECKS = [
    ("flow", run_flow_checks),
    ("completeness", run_completeness_checks),
    ("reasonableness", run_reasonableness_checks),
    ("rollover", run_rollover_checks),
    ("cross_schedule", run_cross_schedule_checks),
    ("cross_form", run_cross_form_checks),
    ("section_163j", run_form_8990_checks),
]
```

The review engine (`review_engine.py`) iterates this list, calls each
function with a `CheckContext`, and merges the returned findings. Each
category runner (e.g. `run_flow_checks`) internally calls individual
check functions — the engine doesn't know or care about individual checks,
only category-level runners.

## Alternatives considered

### Alternative A — Decorator-based auto-registration

Each check function is decorated with `@register_check(category="flow")`
which auto-registers it into a global registry on import. The engine
discovers checks by importing the check modules and iterating the registry.

Rejected: auto-registration via import side effects makes the check
inventory implicit — you can't see what checks run without tracing every
import chain. Check ordering depends on import order, which is fragile
and non-obvious. Debugging "why didn't check X run?" requires inspecting
the registry at runtime. The explicit `ALL_CHECKS` list is ~10 lines, is
the single source of truth for what runs and in what order, and can be
read without executing any code.

### Alternative B — Declarative check definitions (JSON/YAML DSL)

Define checks in a JSON or YAML file with rule expressions, thresholds,
and template strings. A generic runner interprets the definitions and
produces findings.

Rejected: IRS compliance checks involve complex fiscal logic that doesn't
reduce to declarative rules. Examples:

- Flow checks verify sign conventions across schedules where the expected
  sign depends on the entity's functional currency and the schedule type.
- Reasonableness checks compute ratios between fields that have schedule-
  specific extraction logic and tolerance thresholds that vary by entity
  type (5471 vs 8858).
- Cross-form checks compare values across different form types (5471 vs
  8990) with different field naming conventions.

A DSL powerful enough to express these checks would be a domain-specific
programming language — at which point Python is a better DSL with better
tooling, debugging, and type checking.

### Alternative C — Check classes with inheritance

Each check is a class inheriting from `BaseCheck` with overridable methods
(`validate()`, `get_description()`, `get_severity()`). The engine
instantiates and calls each class.

Rejected: checks are stateless functions — they read from the context,
produce findings, and have no lifecycle. Wrapping them in classes adds
`__init__`, `self`, and inheritance boilerplate for zero benefit. The
function-based approach is simpler, more testable (call the function with
a mock context), and more Pythonic.

## Consequences

**Positive:**

- Adding a new check is mechanical: write a function that takes
  `CheckContext`, add it to the appropriate category runner, done. No
  registration ceremony, no class hierarchy to navigate.
- `CheckContext` is the single point of dependency evolution. When a new
  dependency is needed by checks (e.g. FX rate lookup), it's added to
  `CheckContext` once — all checks can access it without signature changes.
- Checks are independently testable: construct a `CheckContext` with a
  test parser and DataFrame, call the function, assert on findings.
- The `ALL_CHECKS` list makes execution order explicit and greppable.
  Reordering or disabling a category is a one-line change.
- Fault tolerance is trivial: the engine wraps each category call in
  try/except, so a failing check category doesn't abort the entire review.

**Negative / accepted costs:**

- `CheckContext` is a bag, not a typed interface. A check that only needs
  the parser still receives the full context. Accepted: the overhead is
  negligible (one object reference), and a typed interface per check would
  explode the surface area for 44+ checks.
- The flat `ALL_CHECKS` list doesn't support conditional check inclusion
  (e.g. "only run 8858 checks if the return has 8858 forms") at the
  registry level. Currently, 8858-specific runners are called separately
  in the engine based on form type detection. Accepted: this works for
  2 form types (5471, 8858); if Mythos adds 5+ form types, a more
  structured dispatch (e.g. form-type → check-list mapping) would be
  cleaner.
- No dependency graph between checks. If check B depends on check A's
  findings, the ordering must be manually ensured in `ALL_CHECKS`.
  Accepted: no such dependency exists today. If it arises, the fix is a
  two-phase run (detect → cross-reference), not a dependency DAG.

**Future review triggers:**

- If the check count grows past ~100, the flat list may benefit from a
  per-form-type registry or a plugin discovery mechanism.
- If checks need to be user-configurable (enable/disable per engagement),
  the `ALL_CHECKS` list would need a wrapper that filters by configuration.
  This is planned for v1.1 but doesn't require changing the DI pattern.
- If checks start needing shared intermediate state (e.g. a pre-computed
  ownership graph), `CheckContext` gains a new field — but consider whether
  the intermediate computation belongs in the context or in a preprocessing
  step that runs before checks.

## Related specs / ADRs

- Implementation: `lab/xml_parser/engine/checks/_helpers.py` (CheckContext)
- Implementation: `lab/xml_parser/engine/checks/__init__.py` (ALL_CHECKS)
- Implementation: `lab/xml_parser/review_engine.py` (engine loop)
- Related: ADR-007 (check engine is Layer 4 in the module architecture)
- Related: ADR-004 (Finding uses the MythosError hierarchy for severity)

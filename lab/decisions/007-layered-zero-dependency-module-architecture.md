# ADR 007 — Layered zero-dependency module architecture

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/core/`, `lab/xml_parser/`, `lab/pdf_validator/`, `lab/mythos_ui/`

## Context

Mythos started as a single `xml_parser/` package (IRS e-file parser + check
engine). As the project grew — shared entity logic (`core/`), a PDF cross-
validator (`pdf_validator/`), and a desktop UI (`mythos_ui/`) — the codebase
crossed ~15k LOC across four independent packages. Without a rule governing
which packages can import which, circular dependencies and implicit coupling
accumulate fast: a change in the parser's internals breaks the UI, or the
PDF validator quietly imports a helper from the check engine that was never
meant to be public API.

The question was how to structure module boundaries so each package can evolve
independently while sharing common infrastructure.

## Decision

Organize the codebase as a 6-layer stack with strict unidirectional
dependencies and zero lateral imports between sibling packages:

```
Layer 6  Presentation   lab/mythos_ui/        (NiceGUI desktop + web UI)
Layer 5  API            lab/xml_parser/api/    (MythosService façade)
Layer 4  Engine+Reports lab/xml_parser/engine/ + lab/xml_parser/reports/
Layer 3  Export         lab/xml_parser/export/ (Excel, PDF, HTML, CSV)
Layer 2  Parser         lab/xml_parser/parser.py + lab/xml_parser/core/
Layer 1  Core           lab/core/             (shared services, zero internal deps)
```

Rules:

1. **`core/`** imports nothing from `lab/`. It is the shared base layer —
   entity classifier, registry, tagger, error hierarchy, adapters.
2. **`xml_parser/`** imports from `core/` only. Its internal layers (parser →
   export → engine → reports → api) flow upward; no downward imports.
3. **`pdf_validator/`** imports nothing from `xml_parser/`, `core/`, or
   `mythos_ui/`. It is fully isolated — its own models, its own validation
   logic.
4. **`mythos_ui/`** is the only consumer that bridges multiple packages. It
   imports from `xml_parser` (via `api/service.py` and parser) and `core/`
   (entity classifier, registry). It does so through a `services/` layer
   (`bridge.py`, `xml_check_state.py`) that keeps page code decoupled from
   implementation details.
5. **No lateral imports**: `xml_parser` never imports from `pdf_validator` or
   `mythos_ui`. `pdf_validator` never imports from `xml_parser`. If two
   packages need the same functionality, it moves to `core/`.

## Alternatives considered

### Alternative A — Monolith: everything in one package

Keep all modules in a single `lab/mythos/` package with sub-packages but no
import restrictions. Simplest structure — any file can import any other file.

Rejected: Mythos hit circular import issues at ~5k LOC when parser utilities
were imported by the check engine which was imported by the review engine
which was imported by the dashboard. The lack of boundaries made every
refactor a cascade of import fixes. As the project grew to 15k+ LOC across
four concerns (parsing, validation, UI, shared logic), a flat namespace
would make it impossible to reason about change impact.

### Alternative B — Installable sub-packages with enforced API contracts

Make each module (`core`, `xml_parser`, `pdf_validator`, `mythos_ui`) an
independently installable Python package with `setup.py`/`pyproject.toml`,
declared dependencies, and version pinning between them.

Rejected: the packaging overhead (4 build configs, version matrices,
inter-package version pins, local editable installs for development) is
not justified for a solo project. The zero-dependency convention gives
the same structural benefit — imports are directional and predictable —
without the toolchain complexity. If Mythos gains other contributors or
needs independent release cycles per module, this alternative becomes
worth revisiting.

## Consequences

**Positive:**

- Change isolation: modifying a check in `xml_parser/engine/` cannot break
  `pdf_validator/` or `core/`. The blast radius of any change is bounded by
  its layer.
- Independent testing: `pdf_validator/` has 130+ tests that run without
  importing or mocking anything from `xml_parser/`. `core/` tests run
  without a UI or parser dependency.
- Clear extension points: adding a new validator (e.g. a future
  `form_8990_validator/`) follows the same pattern — isolated package,
  imports from `core/` if needed, wired into `mythos_ui/` at the
  presentation layer.
- Import errors surface immediately as violations of the layering rule,
  not as subtle runtime bugs months later.

**Negative / accepted costs:**

- Code duplication between `xml_parser/` and `pdf_validator/` for concepts
  like form types, schedule names, and severity enums. Accepted: the
  duplication is small (~50 lines of constants), and the alternative
  (sharing via `core/`) would couple two packages that have no reason to
  depend on each other.
- `mythos_ui/` is the integration point and therefore the most fragile
  layer — it depends on both `xml_parser` and `core`, so changes in either
  can require UI updates. Accepted: this is inherent to a presentation
  layer; the `services/` sub-layer mitigates it by centralizing the bridge
  logic.
- Orphan adapters in `core/` (`oit_parser.py`, `fx_rates.py`,
  `xlsx_reader.py`) were built as shared services but currently have no
  consumers inside Mythos. They're correct according to the layer model
  (shared infra belongs in `core/`) but represent dead code until connected.

**Future review triggers:**

- If `pdf_validator/` needs to consume entity data from `core/` (e.g. to
  validate entity-specific PDF schedules), it would break its current
  full-isolation status. At that point, decide whether to add the dependency
  or move the shared logic into `core/`.
- If the project gains other contributors, revisit Alternative B — proper
  packaging with enforced boundaries becomes more valuable when multiple
  people modify the same codebase.
- If a fifth package is added (e.g. `reconciliation/`), document where it
  sits in the layer stack before writing its first import.

## Related specs / ADRs

- Spec: `lab/specs/core-module.md` (declares the zero-dependency principle)
- Spec: `lab/specs/mythos-framework.md` (layer diagram and module inventory)
- Related: ADR-008 (NiceGUI/pywebview — the presentation layer choice)
- Related: ADR-009 (CheckContext DI — operates within Layer 4)
- Related: ADR-002 (EntityClassifier lives in `core/`, consumed from Layer 6)

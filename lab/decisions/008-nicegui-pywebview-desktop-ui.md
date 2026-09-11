# ADR 008 — NiceGUI + pywebview as desktop UI framework

**Date:** 2026-07-24
**Status:** Accepted
**Implemented:** `lab/mythos_ui/` (v0.7.x, initial migration from Streamlit in v0.6→v0.7)

## Context

Mythos v0.6 shipped with a Streamlit dashboard (`lab/xml_parser/dashboard_st.py`)
for displaying review results. As the project evolved from a batch CLI tool
into an interactive compliance workstation — multi-tab review, entity drill-
down, PDF cross-validation, rollover analysis — the Streamlit model hit hard
limits:

1. **Rerun-on-interaction**: Streamlit re-executes the entire script on every
   widget interaction. A compliance review that takes 3-8 seconds to parse
   cannot re-run on every tab switch or filter change. Workarounds (`st.cache`,
   `st.session_state`) added complexity without fixing the fundamental model.
2. **No native window**: Streamlit runs exclusively in a browser tab. For a
   desktop tool used daily alongside ONESOURCE and Excel, a native window
   with taskbar presence and OS-level window management (Aero Snap, Alt-Tab)
   is a meaningful UX improvement.
3. **No multi-page without hacks**: Streamlit's multi-page support (file-based
   routing) doesn't support shared state across pages without global session
   state, and navigation between pages triggers a full rerun.
4. **Limited component library**: Data tables, modals, tabs, and expansion
   panels require community components of varying quality. No first-party
   rich component set.

The project needed a framework that supports persistent state, multi-page
navigation without reruns, a rich component library, and the option to run
as either a native desktop window or a browser app.

## Decision

Adopt NiceGUI as the UI framework with pywebview for native desktop mode.

- **NiceGUI** provides a Python-native API over the Quasar/Vue component
  library (tables, tabs, dialogs, expansion panels, notifications, icons —
  all first-party). State is persistent across interactions; no rerun model.
  Pages are Python functions decorated with `@ui.page('/path')`.
- **pywebview** wraps the system WebView (Edge WebView2 on Windows) into a
  native window. NiceGUI's `ui.run(native=True)` activates it. A `--web`
  CLI flag switches to browser mode for remote/debugging use.
- **Frameless window with Win32 resize**: `native_window.py` uses ctypes to
  find the pywebview HWND and adds `WS_THICKFRAME | WS_MAXIMIZEBOX |
  WS_MINIMIZEBOX`, enabling OS resize borders and Aero Snap on the frameless
  window. Custom SVG buttons in `layout.py` handle minimize/maximize/close.
- **Token-based theme**: `theme.py` defines DARK and LIGHT mode dictionaries
  (~40 tokens each, Radix color scale) injected as CSS custom properties.
  Mode is stored in `app.storage.user["theme_mode"]`.

## Alternatives considered

### Alternative A — Keep Streamlit and work around limitations

Continue with Streamlit, using aggressive caching, session state, and
community components to approximate a persistent multi-tab UI.

Rejected: the rerun model is architecturally incompatible with the compliance
review workflow. Every tab switch, filter change, or entity selection would
either re-trigger the parser or require complex state management to avoid it.
The workarounds were growing faster than the features. After attempting to
build the multi-tab review interface in Streamlit (v0.6.1), the state
management code exceeded the actual review display code — a signal that the
framework was fighting the use case.

### Alternative B — Electron with React or Vue frontend

Build a proper desktop app with Electron (Chromium + Node.js) and a
React/Vue frontend communicating with a Python backend via IPC or REST.

Rejected: doubles the language stack (Python + JavaScript/TypeScript), adds
a Node.js build toolchain (webpack/vite, npm, transpilation), and requires
maintaining IPC/REST contracts between frontend and backend. For a solo
developer whose expertise is tax compliance, not frontend engineering, the
added complexity and context-switching cost outweigh the richer frontend
ecosystem. NiceGUI gives access to the same Quasar components from Python.

### Alternative C — Textual (terminal UI)

Use Textual for a rich terminal-based interface. Pure Python, no browser
dependency, fast startup.

Rejected: the compliance review workflow requires rich data tables with
sortable columns, scrollable schedule previews, PDF rendering, and
potentially charts for entity completeness visualization. Terminal UIs
cannot render these — especially PDF preview and the styled HTML export
reports that Mythos already generates. The browser renderer that NiceGUI
and pywebview provide is necessary for the visual complexity of the output.

## Consequences

**Positive:**

- Persistent state eliminates the rerun overhead. Parser runs once; all
  tabs, filters, and drill-downs operate on cached data without re-execution.
- Native window via pywebview gives the tool first-class OS presence —
  taskbar icon, Aero Snap, Alt-Tab — while the `--web` flag preserves
  browser access for debugging and remote use.
- Quasar component library covers every UI pattern Mythos needs (ag-grid-
  style tables, tabs, dialogs, expansion panels, notifications, icons)
  with first-party support and consistent styling.
- Python-only stack means one language, one debugger, one package manager.
  UI code is written in the same language as the compliance logic.
- Theme system with CSS custom properties enables dark/light mode toggle
  without re-rendering components.

**Negative / accepted costs:**

- NiceGUI is a newer framework (~2023) with a smaller ecosystem than
  Streamlit or React. Breaking changes between versions are possible,
  and community resources (StackOverflow, tutorials) are limited.
  Accepted: the core API is stable for Mythos's use cases, and the
  project pins its NiceGUI version.
- pywebview on Windows uses Edge WebView2, which adds a runtime dependency
  on the WebView2 Evergreen Runtime. Most Windows 10/11 machines have it
  pre-installed; for those that don't, it's a one-time install.
- The frameless window with Win32 ctypes hack (`native_window.py`) is
  Windows-specific and fragile — a pywebview update could change the
  window class name or creation order. Accepted: the hack is isolated
  to one 40-line file and gracefully degrades (window works, just without
  OS resize borders).
- Streamlit legacy dashboard (`dashboard_st.py`) remains in the codebase
  as dead code. Accepted: it serves as a reference for the original
  feature set and will be removed when the NiceGUI UI reaches full parity.

**Future review triggers:**

- If Mythos needs to run on macOS or Linux, test pywebview's WebKit/GTK
  backends and the Win32 resize hack (which would need a platform-
  specific equivalent or removal).
- If collaborative/multi-user access is needed, NiceGUI's `--web` mode
  supports it but the current state model (`app.storage.user`) is
  single-user. A session-per-user architecture would be needed.
- If the Streamlit dashboard is still present at v1.0, remove it.

## Related specs / ADRs

- Spec: `lab/specs/mythos-framework.md` (UI architecture, component inventory)
- Spec: `lab/specs/mythos-strategy.md` (decision log entry 2026-07-24)
- Related: ADR-007 (UI is Layer 6 — the presentation layer in the stack)

## Notes

The Streamlit → NiceGUI migration happened across v0.7.0 through v0.7.5.
The Streamlit dashboard was the original UI (v0.4–v0.6.x) and is preserved
at `lab/xml_parser/dashboard_st.py` as a reference. The decision date
(2026-07-24) reflects when the migration was committed, not when the
evaluation started.

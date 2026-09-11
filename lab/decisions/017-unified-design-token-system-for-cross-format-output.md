# ADR 017 — Unified design token system for cross-format output

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/xml_parser/export/design_system.py` (DesignSystem), consumed by `excel_exporter.py`, `pdf_exporter.py`, `html_exporter.py`

## Context

Mythos exports compliance reports in four formats: Excel, PDF, HTML,
and CSV. The first three are visual — they include colors, typography,
headers, severity indicators, and branded styling. Before the design
token system, each exporter defined its own colors, fonts, and spacing
inline:

- Excel used hardcoded hex colors in format dicts
- PDF used ReportLab-specific color tuples
- HTML used inline CSS with hardcoded hex values

This produced visual inconsistency (Excel headers were a different shade
of navy than PDF headers), made brand updates tedious (change a color →
edit 3 files in 15 places), and coupled visual decisions to format-
specific code.

The UI (`mythos_ui/theme.py`) has a parallel token system for the
NiceGUI dashboard — dark/light mode dictionaries with ~40 CSS custom
properties using Radix color scales. The export and UI token systems
are intentionally separate: screen UI uses Radix scales optimized for
monitors, while print/export uses a navy/copper palette optimized for
paper and Excel readability.

## Decision

Implement `DesignSystem` as a single class-attribute token store that
is the canonical source of truth for all visual output. All three
visual exporters import it as `DS` and reference tokens by name.

**Token groups:**
- **Palette** (7): `NAVY`, `COPPER`, `SLATE`, `GRAPHITE`, `CLOUD`,
  `PEARL`, `WHITE` — the brand colors.
- **Semantic colors** (8): `SUCCESS`/`SUCCESS_BG`, `DANGER`/`DANGER_BG`,
  `WARNING`/`WARNING_BG`, `INFO`/`INFO_BG` — for findings severity.
- **Typography**: `FONT_STACK` (Inter), `FONT_MONO` (JetBrains Mono),
  `FONT_EXCEL` (Segoe UI). Size scale from `SIZE_DISPLAY` (28) through
  `SIZE_MICRO` (7).
- **Spacing** (base 4px grid): `SPACE_XS` (4) through `SPACE_XXL` (64).
- **Borders**: `BORDER_HAIRLINE` (0.5) through `BORDER_ACCENT` (2.5).
- **Page geometry**: PDF-specific margins and gutters.
- **Excel specifics**: row heights, header heights, title heights.

**Methods:** `severity_color(severity)` and `severity_bg(severity)` map
HIGH/MEDIUM/LOW to the correct color/background pair, ensuring
consistent severity rendering across all formats.

## Alternatives considered

### Alternative A — Per-exporter style definitions

Each exporter owns its visual definitions. Colors, fonts, and spacing
are defined where they're used.

Rejected: this was the previous state and produced the inconsistency
described in Context. Three exporters maintaining independent color
palettes will inevitably drift. A brand update (e.g. changing the
accent color) requires editing three files and hoping all instances
are found.

### Alternative B — CSS-based theme shared across all formats

Define tokens in a CSS file and have all exporters parse it. HTML
uses the CSS directly; PDF and Excel parsers read the CSS to extract
values.

Rejected: CSS parsing in Python adds unnecessary complexity for
non-web formats. Excel's styling API uses integers (font size),
floats (border width), and hex strings (colors) — not CSS custom
properties. Forcing PDF and Excel through a CSS abstraction would
require a translation layer for every token type. A Python class
with typed attributes is the simplest representation that all three
format-specific APIs can consume directly.

## Consequences

**Positive:**

- One change in `DesignSystem` propagates to all three export formats.
  Changing `NAVY` from `#1B2838` to a different shade updates every
  header, border, and chart element across Excel, PDF, and HTML.
- Severity colors are consistent: a HIGH finding is the same shade of
  red whether viewed in Excel, the PDF report, or the HTML dashboard.
- Token names are semantic (`NAVY`, `COPPER`, `DANGER`) rather than
  raw hex values, making exporter code readable: `DS.NAVY` instead
  of `"#1B2838"`.
- The class-attribute pattern (no instance needed) keeps the API
  minimal: `DS.NAVY`, `DS.severity_color("HIGH")`.

**Negative / accepted costs:**

- The export `DesignSystem` and the UI `theme.py` are separate token
  systems with different palettes and different color values. A "brand
  update" requires changes in both places. Accepted: the two systems
  serve different contexts (print vs. screen) and have different
  requirements (Radix scales for screen, navy/copper for print).
  Merging them would force compromises in both directions.
- No dark/light mode for exports — the design system assumes a white
  background (paper/Excel). Accepted: exported reports are typically
  printed or shared as files; dark mode for exports has no user demand.
- CSV export doesn't use the design system (no visual styling).
  Accepted: CSV is data-only by definition.

**Future review triggers:**

- If the UI theme and export design system need to share tokens
  (e.g. severity colors should be identical on screen and in exports),
  extract a shared `severity_palette` module that both consume.
- If Mythos adds a fifth export format (e.g. PowerPoint slides),
  verify that `DesignSystem`'s token types are sufficient or extend
  with presentation-specific tokens.

## Related specs / ADRs

- Spec: `lab/specs/mythos-framework.md` (mentions design system)
- Related: ADR-007 (export layer is Layer 3 in the module stack)
- Related: ADR-008 (UI theme is the screen-side counterpart)

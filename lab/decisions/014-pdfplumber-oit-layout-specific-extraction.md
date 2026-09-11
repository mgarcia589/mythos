# ADR 014 — pdfplumber with OIT-layout-specific extraction

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/pdf_validator/extractor.py`, `lab/pdf_validator/scanner.py`, `lab/pdf_validator/router.py`

## Context

Mythos needs to extract structured financial data from IRS form PDFs
for cross-validation against the XML e-file. These PDFs are generated
by ONESOURCE (OIT) and follow a consistent ruled-table layout: every
schedule is rendered as a series of bordered tables with row descriptions
in the left column and entity values in data columns.

PDF table extraction is notoriously unreliable — different libraries use
different strategies (stream-based vs. lattice-based detection, OCR vs.
text extraction), and no library works well on all PDF layouts. The
choice of library and extraction strategy is tightly coupled to the
specific PDF layout being processed.

The pdf_validator module uses a two-phase architecture:
1. **Scanner** — lightweight regex pass to inventory forms, entities,
   and schedules without full table extraction.
2. **Extractor** — full table extraction for specific schedules, producing
   per-entity dataclasses with parsed field values.
3. **Router** — batch PDF support, classifying pages from a 1000+ page
   multi-form PDF and routing them to the correct extractor.

## Decision

Use **pdfplumber** as the PDF extraction library with its default
lattice-based table detection settings. Build OIT-layout-specific
extraction logic on top of pdfplumber's primitives.

**Why pdfplumber:** OIT PDFs use ruled lines (borders around every cell)
which is the ideal case for pdfplumber's line-intersection algorithm.
pdfplumber detects table boundaries by finding intersections of
horizontal and vertical lines — this works reliably on OIT's consistent
layout without any custom `table_settings` configuration.

**OIT-layout-specific design:**
- Per-schedule entity dataclasses (`SchJEntity`, `SchFEntity`,
  `SchHEntity`, `SchI1Entity`, etc. — 12 schedule types) with typed
  `lines: dict[str, float]` matching IRS XML field names.
- Field identification via `FIELD_BY_DESCRIPTION` regex patterns that
  map OIT's row description text to XML field names.
- Multi-page schedule handling: Schedule J uses a 3-page layout per
  entity per basket (Page 1: columns a-d, Page 2: columns e, Page 3:
  Part II Recapture). The extractor knows this structure and stitches
  pages into a single entity record.
- Interleaved "m" spacer character handling in OIT text output.
- `ExtractionMetrics` tracks pages processed, tables detected, tables
  failed, and values extracted for quality monitoring.

**Scanner architecture:** Regex-based page classification (no table
extraction) that identifies form types (5471/8858/8990), schedule types
(15 patterns), entity reference IDs, and entity names from page text.
Returns a `ScanResult` inventory used by the Router to build a `PageMap`.

## Alternatives considered

### Alternative A — tabula-py (Java-based, via tabula-java wrapper)

tabula uses the same lattice detection approach but runs via a Java
subprocess. Competitive accuracy on ruled-table PDFs.

Rejected: tabula requires a JVM installation, adds ~200ms startup
overhead per extraction call (JVM boot), and provides no Python-level
access to page geometry (lines, characters, curves) that pdfplumber
exposes. The JVM dependency also complicates PyInstaller packaging for
the desktop app (ADR-008).

### Alternative B — camelot-py

camelot also uses lattice detection with OpenCV for line detection.
Often higher accuracy than pdfplumber on complex layouts.

Rejected: camelot depends on OpenCV (`cv2`) and Ghostscript — two heavy
compiled dependencies that are difficult to package and install. For
OIT's clean ruled-table layout, pdfplumber's simpler line-intersection
algorithm achieves equivalent accuracy without the dependency burden.
camelot would be worth reconsidering if Mythos needed to handle non-OIT
PDFs with more complex layouts.

### Alternative C — Generic extraction without layout-specific logic

Use pdfplumber's table extraction generically and post-process the
output to identify fields by position or pattern matching.

Rejected: generic extraction cannot handle OIT's multi-page schedules
(Schedule J spans 3 pages), schedule-specific column structures, or the
distinction between entity data rows and section headers. Without
layout-specific logic, Schedule J Page 2's columns would be
misidentified because they have different headers than Page 1.
The OIT layout is consistent enough that encoding it explicitly is more
reliable than trying to infer structure dynamically.

## Consequences

**Positive:**

- pdfplumber's default settings work on OIT PDFs without tuning —
  no custom `table_settings` needed, reducing configuration fragility.
- Per-schedule dataclasses produce typed, validated output that maps
  directly to XML field names, enabling automated reconciliation.
- Two-phase scan → extract architecture means the scanner can inventory
  a 1,070-page PDF in ~170 seconds without full table extraction,
  showing the user what's available before committing to the expensive
  extraction step.
- 264+ tests validate extraction accuracy per schedule type.

**Negative / accepted costs:**

- The extraction logic is tightly coupled to OIT's specific PDF layout.
  If OIT changes its PDF rendering (different table borders, different
  row descriptions, different multi-page structure), the extractors
  need updating. Accepted: OIT's PDF layout has been stable across
  versions, and the coupling is intentional — it's what enables
  reliable extraction.
- pdfplumber is slower than tabula on large PDFs (~170s for 1,070
  pages in scan mode). Accepted: scan runs once per PDF, and the
  result is cached. Extraction of specific schedules is ~15s per
  schedule.
- Some schedules (A, B, C, P, R) have extractors that return empty
  on certain PDF layouts — known limitation being addressed
  incrementally through layout calibration.

**Future review triggers:**

- If Mythos needs to process non-OIT PDFs (e.g. GoSystem or
  hand-prepared returns), the layout-specific approach won't work.
  A layout detection/classification layer would be needed to select
  the right extraction strategy per PDF source.
- If pdfplumber's accuracy degrades on a future OIT layout change,
  evaluate camelot as a drop-in replacement — the extractor's
  table-processing logic is library-agnostic above the
  `page.extract_tables()` call.

## Related specs / ADRs

- Spec: `lab/specs/pdf-validator.md`, `lab/specs/pdf-smart-router.md`
- Related: ADR-007 (pdf_validator is fully isolated — zero imports
  from xml_parser or core)
- Related: ADR-012 (pdf_validator uses stdlib ET, not lxml, for the
  same isolation reason)

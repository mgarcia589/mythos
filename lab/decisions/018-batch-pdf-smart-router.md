# ADR 018 — Batch PDF smart router for multi-form OIT exports

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/pdf_validator/router.py`

## Context

ONESOURCE exports a single batch PDF containing all IRS forms for all
entities in a return. A typical batch PDF is 800-1,100 pages containing
interleaved entity blocks:

```
Entity Block (Entity-001, 5471):
  Form 5471 Page 1, Schedule A, B, C, F, G, E, I, I-1, J (3pp), P, R
  → ~15-25 pages
Entity Block (Entity-001, 8990):
  Form 8990 (163j) for same entity
  → 2-3 pages
Entity Block (Entity-002, 5471):
  ...repeat...
Entity Block (Entity-050, 8858):
  Form 8858, Schedules C, F, G, H
  → 3-5 pages
```

The existing `PDFExtractor` (ADR-014) processes one schedule at a time
and expects to know which pages belong to which entity and schedule.
The existing `PDFScanner` inventories forms/entities but doesn't produce
a page-level map usable for routing. Without a router, the only way to
validate a batch PDF is to manually split it into per-schedule files —
impractical at 800+ pages.

## Decision

Implement `PDFRouter` as a page-classification-then-route pipeline that
sits on top of the existing scanner, extractor, and reconciler.

**Pipeline:** `scan → classify → route → extract → reconcile → report`

1. **Page classification** — regex-based classifier examines each page's
   text to determine form type (5471, 8858, 8990, cover, detail,
   dormant FDE) and schedule type (A through R, plus I-1 and 8858
   variants). Uses 20+ compiled regex patterns ordered from most
   specific to least specific — earliest match position wins when
   multiple patterns match a page.

2. **Entity block builder** — groups classified pages into `EntityBlock`
   objects keyed by reference ID. Each block contains the entity's
   form type, name, country, and a `schedules: dict[str, list[int]]`
   mapping each schedule to its page numbers.

3. **`PageMap` assembly** — aggregates all entity blocks into a
   `PageMap` with total page count, entity inventory, and unrecognized
   page list.

4. **Route to extractors** — for each (entity, schedule) pair in the
   `PageMap`, passes the specific page numbers to `PDFExtractor` with
   a `pages` filter parameter (added to the extractor for this purpose).

5. **Reconcile and report** — each extracted schedule is reconciled
   against the XML via `PDFReconciler`. Results are aggregated into a
   `BatchValidationResult` with per-schedule reports and an
   `EntityCompleteness` cross-check (XML entities vs PDF entities).

## Alternatives considered

### Alternative A — Pre-split the PDF into per-entity files

Use pdfplumber to split the batch PDF into individual per-entity PDFs,
then feed each to the existing single-entity extraction pipeline.

Rejected: splitting requires knowing entity boundaries, which is the
same page classification problem the router solves. Additionally,
writing 50+ temporary PDF files per run adds I/O overhead and temp
file management complexity. The page-filtered approach
(`extractor.extract(pages=[5,6,7])`) is more efficient — it reads
pages directly from the original PDF without creating intermediate
files.

### Alternative B — Process the entire PDF as a single stream

Feed the batch PDF to the extractor without page routing — have the
extractor detect entity transitions dynamically as it processes tables.

Rejected: the extractor's per-schedule logic assumes it's working
within a single entity's pages. Entity transitions mid-schedule (e.g.
Entity-001's Schedule J Page 2 followed by Entity-002's Schedule J
Page 1) would produce garbled entity records. The extractor would need
fundamental restructuring to handle interleaved entities. Routing
pages first and extracting per-entity is a cleaner separation of
concerns.

## Consequences

**Positive:**

- One-command batch validation: `PDFRouter(pdf, xml).route()` processes
  an entire 1,000+ page batch PDF and produces a consolidated result.
- The router is a layer on top of existing components — `PDFExtractor`,
  `PDFReconciler`, and `PDFScanner` are unchanged. Adding router
  support was one new file (`router.py`) plus a `pages` parameter on
  the extractor.
- `EntityCompleteness` cross-check catches entities present in XML
  but missing from the PDF (and vice versa) — a completeness gap
  that per-schedule validation alone wouldn't detect.
- Page classification is deterministic and auditable — the `PageMap`
  shows exactly which pages were assigned to which entity/schedule,
  making classification errors visible and debuggable.

**Negative / accepted costs:**

- Page classification relies on regex patterns against page text.
  If ONESOURCE changes its form/schedule header text, patterns need
  updating. Accepted: the patterns are compiled regexes in a single
  location at the top of `router.py`, and OIT's header format has
  been stable.
- Scan + route + extract + reconcile for a 1,070-page PDF takes
  ~260 seconds total. Accepted: this runs once per batch PDF, and
  the scan step (~170s) could be cached if repeated validation of
  the same PDF is needed.
- The router currently skips Form 8990 (163j) pages — they're
  classified but not extracted or reconciled. Accepted: Form 8990
  extraction is out of scope for the current pdf_validator; the
  router correctly identifies these pages so they don't pollute
  5471/8858 extraction.

**Future review triggers:**

- If extraction accuracy drops below 90% on a new OIT PDF version,
  revisit the regex classification patterns and pdfplumber table
  detection settings.
- If Form 8990 extraction becomes a requirement, add 8990-specific
  entity dataclasses and extraction logic to the extractor, then
  enable routing to them.
- If non-OIT batch PDFs need support (e.g. GoSystem exports), the
  classifier would need a layout-detection preamble to select the
  correct regex pattern set.

## Related specs / ADRs

- Spec: `lab/specs/pdf-smart-router.md` (full spec with task breakdown
  and calibration results)
- Related: ADR-014 (pdfplumber extraction strategy — the extractor
  the router feeds into)
- Related: ADR-007 (pdf_validator is fully isolated in the layer stack)
- Related: ADR-012 (router uses stdlib ET for XML entity cross-check)

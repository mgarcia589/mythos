# ADR 010 — zipfile+XML xlsx reader bypassing openpyxl

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/core/xlsx_reader.py`

## Context

Mythos needs to read client-provided Excel workbooks (.xlsx) to extract
entity data, trial balance figures, and schedule mappings. The natural
choice is openpyxl — the standard Python library for reading/writing
xlsx files.

However, production workbooks exported from ONESOURCE frequently contain
broken `definedName` entries for print titles with `#N/A` values. When
openpyxl encounters these malformed entries, it raises an unhandled
exception during workbook load — before any cell data can be read. The
defect is reproducible across openpyxl versions and affects a significant
percentage of ONESOURCE workbook exports.

The underlying problem is that openpyxl parses and validates every
defined name during `load_workbook()`, including print area and print
title definitions that Mythos doesn't use. There is no way to skip
this validation or suppress the error.

## Decision

Implement `XlsxReader` as a direct zipfile+XML reader that bypasses
openpyxl entirely. Since .xlsx files are ZIP archives containing XML
files, `XlsxReader` opens the ZIP, reads `xl/sharedStrings.xml` for
the string table, `xl/workbook.xml` + `xl/_rels/workbook.xml.rels` for
sheet metadata, and individual `xl/worksheets/sheet*.xml` for cell data.
Parsing uses `xml.etree.ElementTree.iterparse` for memory-efficient
streaming.

The reader provides:
- `read_sheet()` — raw cell data as `{row: {col: value}}`
- `read_sheet_as_df()` — pandas DataFrame with header detection
- `get_entity_columns()` — entity column extraction for ONESOURCE layouts
- `get_numeric()` — safe numeric extraction with fallback

## Alternatives considered

### Alternative A — Patch openpyxl or use a fork

Catch the openpyxl exception and strip the broken `definedName` entries
from the XML before loading. Or use a patched fork of openpyxl.

Rejected: the exception occurs deep in openpyxl's `_DefinedName` parser,
not at a point where a try/except can recover the workbook state. A
pre-processing step to strip `definedName` elements from the ZIP before
loading would work but adds complexity (unzip → modify XML → rezip →
load) for a fragile fix that breaks if openpyxl changes its internal
parsing order. A fork diverges from upstream and requires maintenance.

### Alternative B — Use xlrd or other xlsx libraries

Use xlrd (legacy xls/xlsx reader) or calamine (Rust-based, via Python
bindings) as an alternative xlsx parser.

Rejected: xlrd dropped xlsx support in version 2.0 (only reads legacy
.xls now). calamine is fast but is a compiled Rust dependency that adds
build complexity. The xlsx format is documented and simple enough that
a direct reader is fewer lines of code (~180) than managing an
alternative dependency. The direct reader also gives full control over
what gets parsed — Mythos only needs cell values, formulas, and sheet
structure, not styles, charts, or pivot tables.

## Consequences

**Positive:**

- Reads any xlsx file regardless of malformed metadata — the reader
  only parses `sharedStrings.xml`, `workbook.xml`, and `sheet*.xml`,
  completely ignoring print titles, named ranges, styles, and other
  metadata that can be corrupted.
- Zero external dependencies beyond stdlib (`zipfile`, `xml.etree`,
  `re`, `io`) plus pandas for DataFrame output.
- ~180 lines of focused code that is straightforward to debug — no
  openpyxl internals to navigate.
- Memory-efficient via `iterparse` with `elem.clear()` — handles
  large worksheets (50k+ rows) without loading the entire XML DOM.

**Negative / accepted costs:**

- Does not support xlsx features that Mythos doesn't use: conditional
  formatting, merged cells, chart data, pivot tables, images. If any
  of these become needed, the reader would need extension or a fallback
  to openpyxl for those specific features.
- Column references are letter-based (`A`, `B`, `AA`), not numeric.
  Consumers must handle letter-to-number conversion if needed
  (currently handled by position in `get_entity_columns()`).
- No write support — this is a read-only parser. Excel writing in
  Mythos uses XlsxWriter (a different library), which is unaffected
  by the openpyxl issue.

**Future review triggers:**

- If openpyxl fixes the `definedName` crash (tracked as an upstream
  issue), evaluate whether switching back simplifies the codebase.
  The direct reader is small enough that the maintenance burden is low
  either way.
- If xlsx reading needs merged cell support or conditional format
  extraction, the direct reader would need significant extension —
  at that point, reconsider openpyxl with a pre-processing sanitizer.

## Related specs / ADRs

- Spec: `lab/specs/workbook-reader.md` (if it exists)
- Related: ADR-007 (`xlsx_reader.py` lives in `core/` — the shared
  services layer, available to any consumer)
- Related: ADR-011 (OIT adapter also consumes ONESOURCE exports and
  depends on correct file reading)

## Notes

This is the highest-risk ADR in the set: without it, the most likely
"improvement" someone would attempt is replacing `XlsxReader` with
openpyxl, reintroducing the crash on production workbooks. The class's
docstring mentions the openpyxl issue but a docstring is easier to
overlook than an ADR.

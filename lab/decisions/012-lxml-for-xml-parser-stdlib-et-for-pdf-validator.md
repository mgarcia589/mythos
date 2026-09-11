# ADR 012 — lxml for xml_parser, stdlib ElementTree for pdf_validator

**Date:** 2026-09-11
**Status:** Accepted
**Implemented:** `lab/xml_parser/parser.py` (lxml), `lab/pdf_validator/reconciler.py` + `lab/pdf_validator/router.py` (stdlib ET)

## Context

Mythos has two modules that parse XML: `xml_parser/` (the primary IRS
e-file compliance engine) and `pdf_validator/` (PDF-to-XML cross-
validation). Both need to extract structured data from IRS e-file XML
returns, but their requirements differ significantly:

- **xml_parser** does deep, namespace-aware extraction across 20+
  form types and 50+ schedule subtrees. It uses XPath extensively
  to navigate the IRS namespace (`http://www.irs.gov/efile`) and
  extract fields by their full qualified path. Performance matters:
  the parser processes 8MB+ XML files with 300+ subsidiary nodes.

- **pdf_validator** does targeted lookups — given an entity reference
  ID and a schedule name, find the corresponding XML value for
  reconciliation against a PDF-extracted value. It reads a small
  subset of the XML (specific fields per entity) and never needs
  full-tree XPath traversal.

Python offers two XML parsing options: `lxml` (compiled C library
wrapping libxml2, installed via pip) and `xml.etree.ElementTree`
(stdlib, pure Python, zero dependencies).

## Decision

Use **lxml** in `xml_parser/` and **stdlib ElementTree** in
`pdf_validator/`. The two modules deliberately use different XML
libraries based on their different requirements.

**xml_parser uses lxml because:**
- lxml's XPath implementation is complete (XPath 1.0) and fast.
  `xml_parser/` uses complex XPath expressions with namespace
  prefixes (`irs:SubsidiaryReturn/irs:IRS5471/...`) across the
  entire document tree.
- lxml's `etree.parse()` with C-level parsing is ~5-10x faster
  than stdlib ET on large documents (8MB+).
- Namespace handling via a dict (`NS = {"irs": "..."}`) passed to
  `findall()` and `find()` is clean and consistent.
- lxml is already a dependency (installed for other data processing
  needs), so it adds no new compiled dependency.

**pdf_validator uses stdlib ET because:**
- The module's zero-dependency principle (ADR-007) means it should
  minimize external imports. `pdf_validator/` has no other need for
  lxml — it uses pdfplumber for PDF parsing and stdlib for XML.
- The XML lookups in the reconciler and router are simple: find a
  specific element by tag path, read its text. No complex XPath,
  no namespace-heavy traversal. stdlib ET handles this adequately.
- Keeping pdf_validator free of lxml means it can be tested and
  deployed independently without the compiled C dependency — useful
  if the validator is ever extracted as a standalone tool.

## Alternatives considered

### Alternative A — Use lxml everywhere

Standardize on lxml across both modules. Simpler to reason about
("we use lxml for XML"), one API to learn.

Rejected: adds a compiled C dependency to `pdf_validator/` for no
functional benefit. The reconciler's XML access pattern is trivial
(element lookup by path, read text value) and stdlib ET handles it
in identical code. The dependency cost isn't just the import — lxml
requires a C compiler or pre-built wheel at install time, which
complicates deployment on constrained environments.

### Alternative B — Use stdlib ElementTree everywhere

Standardize on stdlib ET. Zero external dependencies for XML parsing.

Rejected: stdlib ET's XPath support is limited to a subset of XPath
1.0 (no predicates beyond simple position, no `contains()`, no
union expressions). `xml_parser/` uses XPath patterns that stdlib
ET cannot express efficiently. The performance difference is also
material — parsing an 8MB return with 300+ subsidiaries takes ~0.3s
with lxml vs ~2.5s with stdlib ET, and this parse runs on every
review.

## Consequences

**Positive:**

- Each module uses the XML library that fits its access pattern:
  heavy XPath → lxml; simple lookups → stdlib.
- `pdf_validator/` stays free of compiled dependencies beyond
  pdfplumber, supporting its isolation principle.
- No unnecessary coupling: a lxml version bump or API change in
  `xml_parser/` cannot affect `pdf_validator/`.

**Negative / accepted costs:**

- Two different XML APIs in the same project. A developer working
  across both modules must know both interfaces (though the
  differences are minor — `find()`, `findall()`, and `.text`
  work identically).
- If `pdf_validator/` later needs namespace-aware XPath or complex
  traversal, stdlib ET may become insufficient. At that point,
  adding lxml to pdf_validator would be justified.
- The inconsistency may surprise a new contributor who greps for
  `import` patterns and finds two different XML libraries.
  Accepted: this ADR documents the deliberate choice.

**Future review triggers:**

- If `pdf_validator/` adds a feature requiring complex XPath
  (e.g. cross-entity validation within the XML), evaluate
  switching it to lxml. The migration is mechanical — the APIs
  are nearly identical for the subset pdf_validator uses.
- If Mythos drops lxml as a dependency for other reasons,
  `xml_parser/` would need to migrate to stdlib ET with
  performance workarounds (pre-indexing, manual namespace
  resolution).

## Related specs / ADRs

- Related: ADR-007 (layer architecture — pdf_validator is isolated,
  xml_parser depends on core/ only)
- Related: ADR-010 (xlsx_reader uses stdlib ET for the same reason —
  simple access, no compiled dependency needed)

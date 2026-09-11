# Project Mythos

**Automated IRS e-File Compliance Review Engine for US International Tax**

Mythos parses IRS e-file XML returns (Forms 5471, 8858, 8990) and runs 44+ automated review checks across 6 dimensions — replacing hours of manual review with a 3-second automated pass. Includes desktop UI (NiceGUI), entity classification/tagging, 2-way/3-way reconciliation, rollover reports, and multi-format export.

Current version: **v0.7.5** — Phases 1-6 complete + Entity Classifier + Desktop UI.

## What It Does

```
XML Return (current year)  ──┐
                             ├──► ReviewEngine ──► Ranked Findings
XML Return (prior year)    ──┘         │              (severity, context, delta)
                                       │
                              44+ checks across:
                              • Flow (internal math consistency)
                              • Completeness (required data present)
                              • Reasonableness (anomaly detection)
                              • Rollover (YoY continuity)
                              • Cross-Schedule (inter-schedule ties)
                              • Cross-Form (5471 ↔ 8858 ↔ 8990)

Excel Workbook  ──┐
                  ├──► Reconciler ──► Pass/Fail per field per entity
XML Return      ──┘         │
                            ├── 2-way (WB vs XML)
OIT Export      ────────────┘── 3-way (OIT vs WB vs XML)

                  ┌──────────────────────────────────┐
XML Return  ──────► EntityClassifier + EntityTagger  ├──► Tagged entities
                  │  (16 deterministic rule tags)     │    (CFC type, dormancy,
                  └──────────────────────────────────┘     tested income/loss, etc.)
```

## Quick Start

```bash
# Install
pip install -e lab/

# List entities in a return
mythos list return.xml

# Run full review (current vs prior year)
mythos review current.xml --prior prior.xml

# Run full review + rollover reports + export
mythos full-review current.xml --prior prior.xml -o output.xlsx

# Reconcile workbook vs XML
mythos reconcile workbook.xlsx current.xml

# Tag entities (auto-classify)
mythos tag return.xml

# Launch desktop UI
mythos dashboard
```

### Programmatic Usage

```python
from lab.xml_parser.api import MythosService

svc = MythosService()

# Full review pipeline
result = svc.full_review("fy25.xml", "fy24.xml", output_path="review.xlsx")
print(f"{len(result['_review_report'].findings)} findings")

# Review only
result = svc.review("fy25.xml", prior="fy24.xml")
for f in result.report.findings:
    print(f"[{f.severity}] {f.check_id}: {f.entity_name} — {f.description}")

# Entity tagging
tags = svc.tag_entities("fy25.xml")
for entity, tag_list in tags.items():
    print(f"{entity}: {', '.join(tag_list)}")

# Reconciliation
recon = svc.reconcile("fy25.xml", workbook="workbook.xlsx")
print(f"Pass rate: {recon.pass_rate:.1%}")

# Export to multiple formats
svc.export_review(result.report, path="findings.xlsx")
svc.export_review(result.report, path="findings.csv", format="csv")
svc.export_review(result.report, path="findings.json", format="json")
```

## Review Checks (44+)

### Form 5471 — 32 Checks

| Category | Count | Coverage |
|----------|-------|----------|
| Flow (FLO-001 to FLO-008) | 8 | Sch C/E/F/H/I-1 internal math |
| Completeness (CMP-001 to CMP-006) | 6 | Missing schedules, fields, indicators |
| Reasonableness (RSN-001 to RSN-007) | 7 | FX anomaly, ETR, E&P, QBAI ratios |
| Rollover (ROL-001 to ROL-011) | 11 | Sch F/J per-line, entity changes, PTEP pools |

### Cross-Schedule & Cross-Form — 12 Checks

| Category | Count | Coverage |
|----------|-------|----------|
| Cross-Schedule (XSC-001 to XSC-009) | 9 | Sch H↔J, I-1↔E, Q↔I, P↔J ties |
| Cross-Form (XFM-001 to XFM-003) | 3 | 5471↔8858, 5471↔8990 |

### Form 8858 (FDE/FB) — Dedicated checks per category

### Form 8990 — Interest limitation checks (XFM)

## Reports (7 types)

| Report | Content |
|--------|---------|
| Sch F Rollover | 16 balance sheet lines, PY EOY vs CY BOY |
| Sch J E&P Pools | 5 PTEP baskets per entity |
| Page 1 Rollover | Entity info changes (name, FC, country) |
| E&P Movement | Income composition, sign changes |
| GILTI Comparison | Tested income/loss movement |
| Entity Changes | Added/dropped/modified entities |
| Schedule G Changes | Indicator flips (P2, 163j, BEAT) |

## Entity Classification

Mythos auto-classifies entities using 16 deterministic rule-based tags:

- CFC type (tested income, tested loss, excluded)
- Dormancy detection
- DRE/hybrid status
- High-tax / low-tax jurisdiction
- Insurance / banking entity flags
- GILTI classification
- Subpart F indicators

## Reconciliation Engine

```python
from lab.xml_parser.reconciler import Reconciler

rec = Reconciler()

# 2-way: workbook vs XML
report = rec.reconcile(workbook_path, xml_path)
print(f"Pass: {report.summary.pass_count}, Fail: {report.summary.fail_count}")

# 3-way: OIT vs workbook vs XML
report = rec.reconcile_three_way(oit_path, workbook_path, xml_path)
```

Features:
- Configurable tolerance (absolute + percentage)
- Sign-flip field handling (Sch H income fields)
- Per-entity, per-schedule, per-field granularity
- Summary statistics with pass rate
- Export to Excel/CSV

## Desktop UI (NiceGUI)

Frameless desktop application with:
- Dark/light theme with glassmorphism design
- XML Check page (upload → parse → review → export)
- Entity browser with tag badges
- Findings table with severity filters
- Rollover reports viewer
- Reconciliation page
- PDF cross-check validator
- Keyboard shortcuts for power users

```bash
mythos dashboard          # Launch desktop app
python -m lab.mythos_ui   # Alternative launch
```

## Project Structure

```
lab/
├── xml_parser/              # Mythos core engine
│   ├── core/               # Foundation layer (models, config, constants)
│   ├── parser.py           # EFileParser — XML → DataFrames
│   ├── field_maps.py       # 103 mapped fields with IRS line references
│   ├── engine/checks/      # FLO, CMP, RSN, ROL, XSC, XFM + 8858 + 8990
│   ├── review_engine.py    # Orchestrator (dispatches to engine/checks/)
│   ├── reconciler.py       # 2-way and 3-way reconciliation
│   ├── workbook_reader.py  # Profile-based Excel reader
│   ├── reports/            # Rollover + movement + entity change reports
│   ├── export/             # Excel, CSV, HTML, PDF + DesignSystem tokens
│   ├── api/service.py      # MythosService — single entry point API
│   └── cli.py              # Click CLI
├── mythos_ui/               # NiceGUI desktop application
│   ├── pages/              # 9 pages (overview, xml_check, entities, etc.)
│   ├── services/           # Bridge to MythosService, parse service
│   ├── components.py       # Reusable UI components
│   ├── layout.py           # Sidebar + navigation + frameless window
│   └── theme.py            # Dark/light tokens, glassmorphism
├── core/                    # Entity classifier, tagger, tagging rules
├── specs/                   # Design specs (framework, strategy, UX plan) — the *what/how*
├── decisions/               # Architecture Decision Records — the *why* (see below)
├── tests/                   # 80+ tests (unit, integration)
│   └── fixtures/           # Synthetic XML test data (5471, 8858, 8990)
├── pyproject.toml
└── requirements.txt
```

## Architecture Decisions

Significant architecture decisions (dependency choices, module boundaries,
design tradeoffs) are recorded as ADRs in
[`lab/decisions/`](lab/decisions/README.md) — one file per decision, with the
context, alternatives considered, and consequences accepted. `lab/specs/`
covers what a module does; `lab/decisions/` covers why it's built that way
instead of another way. See [`lab/decisions/README.md`](lab/decisions/README.md)
for when to write one and how the numbering/status lifecycle works.

## Testing

```bash
# Run all tests
python -m pytest lab/tests/ -v

# Run with coverage
python -m pytest lab/tests/ --cov=lab.xml_parser --cov-report=term-missing

# Run specific module tests
python -m pytest lab/tests/test_entity_classifier.py -v
python -m pytest lab/tests/test_entity_tagger.py -v
python -m pytest lab/tests/test_integration_pipeline.py -v
```

## Dependencies

```
pandas>=2.0
lxml>=5.0
openpyxl>=3.1
click>=8.0
rich>=13.0
xlsxwriter>=3.2
reportlab>=4.0
nicegui>=1.4
plotly>=5.18
```

Dev: `pytest`, `pytest-cov`, `ruff`

Python 3.11+

## Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| v0.6.1 | 32 checks, 4 categories, CLI, dashboard | Released |
| v0.7.0 | Reports, export, cross-schedule checks, Service API | Released |
| **v0.7.5** | Desktop UI (NiceGUI), Entity Classifier/Tagger, 8990 checks, UX improvements | **Current** |
| v0.8 | Packaging + distribution (.exe, pip install, CI) | Next |
| v0.9 | Ownership graph, aggregation checks (AGG-001 to AGG-008) | Planned |
| v1.0 | Multi-year trending, dashboard polish, pattern recognition | Planned |

## License

MIT

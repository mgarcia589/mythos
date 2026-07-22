# Project Mythos

**Automated IRS e-File Compliance Review Engine for US International Tax**

Mythos parses IRS e-file XML returns (Forms 5471, 8858, 8865) and runs 32 automated review checks across 4 dimensions — replacing hours of manual review with a 3-second automated pass that catches what experienced reviewers catch, consistently.

## What It Does

```
XML Return (current year)  ──┐
                             ├──► ReviewEngine ──► Ranked Findings
XML Return (prior year)    ──┘         │              (severity, context, delta)
                                       │
                              32 checks across:
                              • Flow (internal consistency)
                              • Completeness (data present)
                              • Reasonableness (anomalies)
                              • Rollover (YoY continuity)
```

## Quick Start

```bash
# Install
pip install -e .

# List entities in a return
mythos list return.xml

# Run full review (current vs prior year)
mythos review prior.xml current.xml

# Parse and export to Excel
mythos parse return.xml -o output.xlsx

# Launch dashboard (native desktop app)
mythos dashboard
```

### Programmatic Usage

```python
from lab.xml_parser import ReviewEngine

engine = ReviewEngine()
report = engine.review("fy25.xml", "fy24.xml")

print(f"{len(report.findings)} findings")
for f in report.findings:
    print(f"[{f.severity}] {f.check_id}: {f.entity_name} — {f.description}")
```

## Review Checks (32)

### Flow Checks (8) — Internal Consistency

| ID | Check | Severity |
|----|-------|----------|
| FLO-001 | Sch C net income flows to Sch H line 1 | HIGH |
| FLO-002 | E&P: FC x FX rate = USD amount | HIGH |
| FLO-003 | Sch I-1 components reconcile to gross | HIGH |
| FLO-004 | Sch E taxes <= pre-tax income x max statutory rate (45%) | MEDIUM |
| FLO-005 | Tested loss entity has no taxes | HIGH |
| FLO-006 | Sch C income - deductions = net (arithmetic) | HIGH |
| FLO-007 | Sch F total assets >= 0 (no negative assets) | HIGH |
| FLO-008 | Sch F balance sheet balances (Assets = Liabilities + Equity) | HIGH |

### Completeness Checks (6) — Required Data Present

| ID | Check | Severity |
|----|-------|----------|
| CMP-001 | Entity in return but missing Schedule H | HIGH |
| CMP-002 | Entity missing Schedule I-1 | MEDIUM |
| CMP-003 | Has I-1 income but no Sch E taxes reported | MEDIUM |
| CMP-004 | Sch F has BOY balances but no EOY | HIGH |
| CMP-005 | No functional currency or exchange rate | MEDIUM |
| CMP-006 | Invalid or missing reference ID | LOW |

### Reasonableness Checks (7) — Anomaly Detection

| ID | Check | Severity |
|----|-------|----------|
| RSN-001 | E&P exceeds $1 billion (verify) | LOW |
| RSN-002 | FX rate outside expected range (0.0001–10000) | MEDIUM |
| RSN-003 | Implied ETR outside normal range (>50% or <0%) | MEDIUM |
| RSN-004 | Tested income = Subpart F income (potential misclassification) | MEDIUM |
| RSN-005 | All entities have same E&P sign (unusual) | LOW |
| RSN-006 | QBAI exceeds total assets (impossible) | HIGH |
| RSN-007 | Interest expense exceeds gross income | MEDIUM |

### Rollover Checks (11) — Year-over-Year Continuity

| ID | Check | Severity |
|----|-------|----------|
| ROL-001 | Sch F per-line rollover: PY EOY = CY BOY (16 BS lines, $10K materiality) | HIGH |
| ROL-002 | Entity present in PY but dropped in CY | MEDIUM |
| ROL-003 | Entity added in CY (not in PY) | MEDIUM |
| ROL-004 | E&P sign flip (positive to negative or vice versa) | MEDIUM |
| ROL-005 | FX rate changed >25% year-over-year | LOW |
| ROL-006 | Material amount disappears to zero (>$10K to $0) | HIGH |
| ROL-007 | Sch J: all 5 PTEP pools roll (PY ending = CY beginning) | HIGH |
| ROL-008 | Page 1 entity info changes (name, functional currency, country) | MEDIUM |
| ROL-009 | Sch G indicator flips (163(j), BEAT, FDII, Pillar Two) | MEDIUM |
| ROL-010 | GILTI classification flip (tested income <-> tested loss) | MEDIUM |
| ROL-011 | E&P accumulation: Sch H vs Sch J math check | HIGH |

## Test Results

### CNG FY25 (24 entities — clean, single-shareholder return)

| Metric | Result |
|--------|--------|
| Findings | 23 |
| HIGH / MEDIUM / LOW | 11 / 11 / 1 |
| Clean entities | 9/24 (38%) |
| Findings/entity | 0.96 |
| True Signal Rate | ~100% |
| Runtime | ~3 sec |

### Centerbridge FY25 (62 entities — complex, multi-portfolio)

| Metric | Result |
|--------|--------|
| Findings | 160 |
| HIGH / MEDIUM / LOW | 98 / 55 / 7 |
| Clean entities | 7/62 (11%) |
| Findings/entity | 2.58 |
| True Signal Rate | ~80% |
| Runtime | ~3 sec |

The engine discriminates between clean and complex returns — producing proportional output to actual quality issues, not just entity count.

## Architecture

```
lab/xml_parser/
├── __init__.py          # Package entry (v0.6.1)
├── __main__.py          # python -m entry point
├── parser.py            # EFileParser — XML to DataFrames
├── field_maps.py        # 103 mapped fields with form line references
├── review_engine.py     # ReviewEngine — 32 automated checks (1046 lines)
├── comparator.py        # XMLComparator — YoY diff engine
├── reconciler.py        # WB vs XML reconciliation
├── workbook_reader.py   # Profile-based workbook reader
├── dashboard.py         # NiceGUI native desktop app
├── cli.py               # Click CLI (list, parse, compare, review)
├── reports.py           # PDF/Excel report generation
├── output.py            # Rich terminal output
├── gt_output.py         # great-tables output
├── models.py            # Data models
├── pyproject.toml       # Package config
└── specs/               # Design specifications
    ├── xml-parser.md
    ├── review-engine.md (→ see lab/specs/mythos-framework.md)
    ├── reconciler.md
    ├── workbook-reader.md
    └── reports/         # Report format specs
```

## Competitive Position

| Dimension | Bolt/Alteryx | ONESOURCE Diagnostics | Manual Review | **Mythos** |
|-----------|-------------|----------------------|---------------|-----------|
| Time | 10+ min | 2 min (pre-file) | 4-8 hours | **< 3 sec** |
| Setup | Per-client Alteryx workflow | None (built-in) | N/A | **Zero-config** |
| License | Alteryx ($$$) | OIT license | N/A | **Free (Python)** |
| Review logic | None (extraction only) | Format rules only | Experience-based | **32 automated checks** |
| Rollover | None | None | Sch F + J only | **Full (11 checks, 16 BS lines, 5 pools)** |
| Entity coverage | Per-schedule | None | Selective | **Every entity, every check** |
| Anomaly detection | No | No | Experienced only | **Automated (7 checks)** |
| Audit trail | None | None | Notes/WP | **Structured findings** |

## Dependencies

```
pandas>=2.2
openpyxl>=3.1
click>=8.1
rich>=13.0
xlsxwriter>=3.2
great-tables>=0.8
reportlab>=4.0
nicegui>=3.14
```

Python 3.12+

## Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| **v0.6.1** | 32 checks, 4 categories, CLI, dashboard | Current |
| v0.7 | Ownership graph (networkx) + cross-entity aggregation (8 AGG checks) | Planned |
| v0.8 | Pattern recognition, multi-return trend analysis | Planned |
| v0.9 | ONESOURCE pre-import validation, graphBeacon config check | Planned |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check lab/xml_parser/

# Run review on test data
python -m lab.xml_parser review sources/cng/cng-fy24.xml sources/cng/cng-fy25.xml
```

## License

MIT

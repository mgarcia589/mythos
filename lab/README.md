# Cerebro Lab — R&D Toolkit

Herramientas de automatización para US International Tax Compliance.

> **RAG Registry**: Ver `lab/RAG.md` para el índice completo de proyectos con
> capability descriptions, invocation patterns, y dependency graph. Claude usa
> ese archivo para retrieval cuando el usuario pide automatización.

## Setup

```bash
pip install -r requirements.txt
```

## Projects (RAG Status)

| Project | Path | Status | Capability |
|---------|------|--------|------------|
| **Mythos** | `xml_parser/review_engine.py` | 🟢 GREEN | 32 automated review checks on XML returns |
| **XML Parser** | `xml_parser/parser.py` | 🟢 GREEN | Parse IRS e-file → DataFrames (103 fields) |
| **WorkbookReader** | `xml_parser/workbook_reader.py` | 🟢 GREEN | Profile-based xlsx → structured schedules |
| **Reconciler** | `xml_parser/reconciler.py` | 🟢 GREEN | WB vs XML field-by-field comparison |
| **Comparator** | `xml_parser/comparator.py` | 🟢 GREEN | XML YoY diff engine |
| **Dashboard** | `xml_parser/dashboard.py` | 🟡 AMBER | NiceGUI native app (functional, unpolished) |
| **Audit Engine** | `audit/` | 🟡 AMBER | Workbook formula validation |
| **Core Toolkit** | `core/` | 🟡 AMBER | OIT parser, entity registry, FX (partial) |
| **OIT Reconciliation** | `reconciliation/` | 🔴 RED | Stub only |
| **Calc Pipeline** | `pipeline/` | 🔴 RED | Stub only |

## Quick Start

```python
# Review a return (most common operation)
from lab.xml_parser.review_engine import ReviewEngine
report = ReviewEngine().review("current.xml", "prior.xml")
print(f"{len(report.findings)} findings")

# Parse XML
from lab.xml_parser.parser import EFileParser
parser = EFileParser("return.xml")
parser.parse()
df = parser.to_dataframe()

# WB vs XML reconciliation
from lab.xml_parser.workbook_reader import WorkbookReader
from lab.xml_parser.reconciler import Reconciler
wb_data = WorkbookReader("workbook.xlsx").parse()
recon = Reconciler(tolerance=15).reconcile(wb_data, parser)
```

## RAG Architecture

```
┌─────────────────────────────────────────────────────┐
│  lab/RAG.md — Retrieval Index                       │
│  (Claude reads this to know what tools exist)       │
└──────────────────────┬──────────────────────────────┘
                       │ retrieves
         ┌─────────────┼─────────────────┐
         │             │                 │
    ┌────▼────┐   ┌────▼────┐      ┌────▼────┐
    │  Specs  │   │  Code   │      │ Results │
    │lab/specs│   │lab/xml_ │      │ wiki/   │
    │         │   │ parser/ │      │projects/│
    └─────────┘   └─────────┘      └─────────┘

Specs = design intent (read before modifying code)
Code = implementation (invoke directly)
Results = findings documented (reference for context)
```

## Uso con Claude

Este toolkit está diseñado para Retrieval-Augmented Generation:
1. **RAG.md** = retrieval layer — Claude sabe qué existe sin leer código
2. **Specs** = augmentation — Claude lee specs antes de generar/modificar
3. **Code** = generation target — Claude invoca o modifica según necesidad
4. **Wiki** = accumulated knowledge — resultados alimentan futuras sesiones

## Roadmap

- [x] Phase 1: Core + Audit Engine
- [x] Phase 2: Mythos Review Engine (32 checks, 2 clients validated)
- [x] Phase 2b: Reconciler + WorkbookReader
- [x] Phase 2c: RAG Registry (this file + lab/RAG.md)
- [ ] Phase 3: OIT Reconciliation (CSV ↔ WB)
- [ ] Phase 4: Calculation Pipeline (independent E&P)
- [ ] Phase 5: Team packaging (CLI, docs, examples)

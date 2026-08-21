# UI/UX Audit — Mythos v0.7.0

**Fecha:** 2026-07-25  
**Scope:** Dashboard (NiceGUI + Streamlit), CLI, Excel/HTML/PDF exports, Design System

---

## Resumen Ejecutivo

El sistema visual de Mythos tiene una base sólida — design tokens bien definidos, jerarquía tipográfica clara, y un design system centralizado. Sin embargo, hay inconsistencias significativas entre componentes, información hardcodeada obsoleta, y gaps de funcionalidad que afectan la experiencia del usuario.

**Veredicto:** Buen 70% — necesita polish y consistencia para ser presentable a stakeholders.

---

## 1. Dashboard NiceGUI (`dashboard.py`)

### Fortalezas

- Design tokens bien organizados (zinc-based dark palette, shadcn-inspired)
- Jerarquía visual clara: metric cards → charts → table
- Filtros reactivos funcionales (severity, category, entity)
- Upload flow intuitivo con drag-and-drop
- Responsive layout con max-width constraint

### Issues Identificados

| ID | Severidad | Issue | Ubicación |
|----|-----------|-------|-----------|
| UI-001 | HIGH | **Version hardcodeada "v0.5"** en el header — debería ser dinámica desde `__init__.__version__` | Línea 207 |
| UI-002 | HIGH | **"Load Demo (Sample)"** button expone nombre de cliente real | Línea 594 |
| UI-003 | HIGH | **"28 rules" hardcodeado** en Quick Stats — actual es 71 checks | Línea 279 |
| UI-004 | MEDIUM | **Entity page no muestra entity_name** — solo entity_code, falta contexto | Línea 393-408 |
| UI-005 | MEDIUM | **No hay loading state** durante review — UI freezes sin feedback | Línea 631-643 |
| UI-006 | MEDIUM | **No hay error boundary** — si review crashea, el usuario no ve por qué | Línea 636-638 |
| UI-007 | MEDIUM | **`row_key="check_id"` en findings table** — no es unique (multiple entities can have same check_id), causa key collision en Quasar | Línea 559 |
| UI-008 | LOW | **No hay page title dinámico** — siempre "Mythos" sin indicar la página actual | Línea 673-678 |
| UI-009 | LOW | **Font loading desde CDN externo** (Google Fonts) — falla offline | Línea 195 |
| UI-010 | LOW | **No hay export HTML/PDF** desde el dashboard — solo Excel via `export_current()` | Línea 646-667 |
| UI-011 | LOW | **No hay search/filter en entity table** | Línea 426-431 |
| UI-012 | LOW | **Sidebar "DATA" section** tiene solo 2 acciones — podría incluir reconcile | Línea 225-231 |

### Recomendaciones Dashboard

1. **Versión dinámica:** `from lab.xml_parser import __version__` → mostrar en header
2. **Rename demo:** "Load Sample Data" en vez de "Load Demo (Sample)"
3. **Loading indicator:** `ui.spinner()` o progress bar durante review
4. **Error handling:** `try/except` con `ui.notify(..., type="negative")`
5. **Unique row key:** usar `f"{f.check_id}_{f.entity_code}"` como row_key

---

## 2. Dashboard Streamlit (`dashboard_st.py`)

### Issues

| ID | Severidad | Issue |
|----|-----------|-------|
| UI-013 | MEDIUM | **Duplica funcionalidad** del dashboard NiceGUI — confuso para mantenimiento |
| UI-014 | LOW | Palette distinta del NiceGUI (más purple-toned) — inconsistencia visual |
| UI-015 | LOW | No está documentado cuál es el "oficial" |

### Recomendación

Decidir cuál es el dashboard principal. Si NiceGUI es el estándar (está en `cli.py dashboard`), marcar `dashboard_st.py` como experimental o deprecarlo.

---

## 3. CLI (`cli.py`)

### Fortalezas

- Rich tables con color-coded severity
- Buen uso de `Panel.fit()` para branding consistente
- Opciones de filtro completas (`--entity`, `--check`, `--category`)
- Auto-generación de output path cuando no se especifica
- Progress indicator via `console.status()`

### Issues

| ID | Severidad | Issue | Ubicación |
|----|-----------|-------|-----------|
| UI-016 | HIGH | **`compare` command importa `XMLComparator`** — módulo que ya no existe (refactored away) | Línea 25, 146 |
| UI-017 | MEDIUM | **`review` command dice "7 automated checks"** en el help text — son 71 | Línea 271 docstring |
| UI-018 | MEDIUM | **`check` command** vs **`review` command** — confusión semántica: `check` corre ReviewEngine, `review` corre ReportEngine. Nombres invertidos. | Líneas 261-271, 418-479 |
| UI-019 | MEDIUM | **No hay `--version` flag** en el CLI group | Línea 32-34 |
| UI-020 | LOW | **`check` command escribe Excel con openpyxl+xlsxwriter** — mezcla engines, debería usar el excel_exporter del framework | Línea 476-478 |
| UI-021 | LOW | **No hay `--quiet` flag** para scripting/CI usage | — |
| UI-022 | LOW | **50 material changes cap** sin indicar al usuario cuántas se omitieron | Línea 176 |

### Recomendaciones CLI

1. **Fix import:** remover `XMLComparator` o re-implementar compare via Reconciler
2. **Rename commands:** `check` → `review` (run checks), `review` → `full-report` (run + reports + export)
3. **Add `--version`:** `@cli.command()` → `@click.version_option(version=__version__)`
4. **Usar exporters del framework** en vez de pandas directo

---

## 4. Design System (`export/design_system.py`)

### Fortalezas

- Single source of truth para todos los visual tokens
- Documentación inline de la filosofía ("generous whitespace", "strict hierarchy")
- Semantic color mapping (`severity_color()`, `severity_bg()`)
- Scale modular consistente (ratio ~1.25)
- Spacing basado en 4px grid

### Issues

| ID | Severidad | Issue |
|----|-----------|-------|
| UI-023 | MEDIUM | **Solo aplica a PDF/Excel** — dashboard tiene su propia palette (tokens `T`) completamente separada |
| UI-024 | LOW | **No hay dark mode variant** — el dashboard usa dark mode pero el DS solo tiene light |
| UI-025 | LOW | **`FONT_STACK`** incluye Inter pero Excel usa Segoe UI — mismatch potencial en HTML |

### Recomendación

Unificar en un solo archivo `tokens.py` con variantes `light` y `dark`. El dashboard importaría de ahí en vez de definir su propio `T = {...}`.

---

## 5. Excel Export (`export/excel_exporter.py`)

### Fortalezas

- XlsxWriter usado correctamente (fast, no memory issues)
- Formatos pre-creados y reutilizados (performance)
- Canvas mode (gridlines hidden), freeze panes, autofilter
- Executive Summary sheet con KPIs
- Entity grouping con accent border
- Auto-fit column widths

### Issues

| ID | Severidad | Issue | Ubicación |
|----|-----------|-------|-----------|
| UI-026 | HIGH | **"PwC US Tax LLP"** hardcodeado en footer del cover sheet | Línea 293 |
| UI-027 | HIGH | **"v0.6.1 — 32 checks"** hardcodeado en metadata | Línea 214 |
| UI-028 | MEDIUM | **No hay sheet "Summary" separada** para rollover pass/fail rates (solo el cover tiene KPIs de findings) |
| UI-029 | MEDIUM | **`client_name` puede quedar vacío** → muestra "—" en el cover en vez de pedirlo o inferirlo del XML |
| UI-030 | LOW | **Alt-row coloring** usa fixed `row % 2` — si hay entity groups, el patrón se resetea incorrectamente |
| UI-031 | LOW | **No hay conditional formatting** para cells numéricas (rojo si negativo, verde si positivo) |

---

## 6. HTML Export (`export/html_exporter.py`)

### Fortalezas

- Great-tables produce publication-quality output
- Data coloring por pass_rate (gradient)
- Responsive via percentage-based column widths
- Print-ready combined page (`full_report.html`)
- Clean semantic HTML

### Issues

| ID | Severidad | Issue | Ubicación |
|----|-----------|-------|-----------|
| UI-032 | HIGH | **"PwC US Tax LLP | Confidential"** en footer de every table | Línea 77, 290 |
| UI-033 | MEDIUM | **Combined HTML no incluye findings** — solo rollover reports (el review_report no se pasa) | Línea 282-285 |
| UI-034 | MEDIUM | **No se incluyen reports con 0 failures** (unless "Movement" in name) — pierde contexto de qué pasó clean | Línea 230-231 |
| UI-035 | LOW | **Inline CSS** sin class extraction — si se quiere theming futuro, es difícil |
| UI-036 | LOW | **No minified** — HTML files pueden ser grandes con muchas entidades |

---

## 7. PDF Export (`export/pdf_exporter.py`)

### Fortalezas

- Dual renderer (WeasyPrint primary, xhtml2pdf fallback)
- Landscape mode para tablas anchas
- Cover page con KPI cards
- CSS bien estructurado con sections lógicas
- Entity grouping en findings detail

### Issues

| ID | Severidad | Issue | Ubicación |
|----|-----------|-------|-----------|
| UI-037 | HIGH | **"PwC US Tax LLP"** en footer | Línea 539 |
| UI-038 | HIGH | **"v0.6.1 - 32 checks"** hardcodeado en cover metadata | Línea 339 |
| UI-039 | MEDIUM | **100 item cap** en rollover tables sin pagination — si hay >100 failures, se trunca silently con "... and N more" | Línea 462 |
| UI-040 | MEDIUM | **`_safe()` es limitado** — solo reemplaza un subset de chars, podría fallar con otros unicode | Línea 22-23 |
| UI-041 | LOW | **No hay page numbers** (xhtml2pdf soporta via `@page { @bottom-center { content: "Page " counter(page); } }`) |
| UI-042 | LOW | **Cover page `<3s` runtime** hardcodeado — no se mide real | Línea 323 |

---

## 8. CSV Export (`export/csv_exporter.py`)

### Fortalezas

- Limpio, simple, 83 líneas
- Column names human-readable ("Entity", "Ref ID", etc.)
- `mkdir(parents=True)` — no falla por missing directories
- Returns `None` si no hay findings (vs file vacío)

### Issues

| ID | Severidad | Issue |
|----|-----------|-------|
| UI-043 | LOW | **No metadata row** — sin header indicando client/date/source |
| UI-044 | LOW | **`Difference` es string vacío cuando es 0** — inconsistente (Excel muestra 0) |

---

## 9. `output.py` (Legacy)

### Veredicto: DEPRECATED — Candidate for Removal

| ID | Severidad | Issue |
|----|-----------|-------|
| UI-045 | HIGH | **560 líneas de código muerto** — 0% coverage, no importado por ningún módulo activo |
| UI-046 | HIGH | **PwC branding explícito** (`PWC_ORANGE_HEX = "#D04A02"`, `PWC_GREEN_HEX`, etc.) — risk si el repo es público |
| UI-047 | MEDIUM | **Materiality threshold hardcodeado** ($10) — no configurable |

**Acción:** Eliminar del repo. La funcionalidad fue reemplazada por `export/excel_exporter.py`.

---

## 10. Consistencia Cross-Component

### Version String

| Componente | Versión Mostrada | Debería Ser |
|------------|-----------------|-------------|
| Dashboard header | "v0.5" | `__version__` (0.7.0) |
| Excel cover | "v0.6.1 — 32 checks" | "v0.7.0 — 71 checks" |
| PDF cover | "v0.6.1 - 32 checks" | "v0.7.0 — 71 checks" |
| PDF footer | "v0.6.1" | `__version__` |
| CLI help | "32" (implied) | Actualizar docstrings |
| `__init__.py` | "0.7.0" | Source of truth |
| `pyproject.toml` | "0.6.1" | Sync con `__init__.py` |

### Branding/Confidentiality Strings

| Componente | String | Issue |
|------------|--------|-------|
| Excel cover footer | "PwC US Tax LLP \| Confidential" | No debería estar hardcodeado — hacer configurable |
| HTML summary | "PwC US Tax LLP \| Confidential" | Idem |
| HTML combined | "PwC US Tax LLP \| Confidential" | Idem |
| PDF footer | "PwC US Tax LLP" | Idem |

**Fix:** Mover a `MythosConfig` como `config.firm_name` y `config.confidentiality_label`, defaulting a vacío.

### Check Count

| Componente | Count Mostrada | Actual |
|------------|---------------|--------|
| Dashboard | "28 rules" | 71 |
| Excel | "32 checks" | 71 |
| PDF | "32 checks" | 71 |
| CLI `review` | "7 automated checks" | 71 |

---

## Plan de Acción Priorizado

### P0 — Fix Inmediato (Bloqueantes para demo/presentación)

1. **Remover "PwC US Tax LLP"** de todos los exports — hacer configurable via config
2. **Actualizar version strings** a 0.7.0 / 71 checks en todos los componentes
3. **Remover "Load Demo (Sample)"** del dashboard — rename a "Load Sample"
4. **Fix `compare` command** — remove broken import o deprecar comando
5. **Eliminar `output.py`** — dead code con PwC branding explícito en repo público

### P1 — Mejora Funcional

6. **Unificar design tokens** — dashboard y exports desde un solo archivo
7. **Loading states** en dashboard (spinner during review)
8. **Error handling** — try/except con notificación al usuario
9. **Unique row keys** en findings table
10. **Dashboard version dinámica** desde `__version__`
11. **CLI --version flag**
12. **Reconcile command en dashboard** (sidebar action)

### P2 — Polish

13. **Font fallback** para offline (bundle Inter.woff2 o usar system font)
14. **Page numbers en PDF**
15. **Dark mode variant** del design system
16. **CLI --quiet flag**
17. **Decidir dashboard** (NiceGUI vs Streamlit — pick one)

---

## Métricas de Calidad Visual

| Dimensión | Score | Notas |
|-----------|-------|-------|
| **Consistencia** | 4/10 | 3 palettes distintas, version strings divergentes |
| **Profesionalismo** | 7/10 | Excel/PDF output es de alta calidad, dashboard moderno |
| **Accesibilidad** | 5/10 | Dashboard dark mode OK, pero no WCAG AA contrast en todos los textos |
| **Funcionalidad** | 6/10 | Filtros y export funcionan, falta reconcile en UI, loading states |
| **Mantenibilidad** | 5/10 | Tokens centralizados pero no compartidos, hardcoded strings |
| **Ready para Demo** | 3/10 | Version incorrecta + PwC branding + client names = no presentable |

**Score Global: 5/10** — Base sólida, necesita 2-3 horas de cleanup para estar presentable.

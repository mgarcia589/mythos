# QA Action Plan — Mythos v0.7.0

**Fecha:** 2026-07-24  
**Estado:** Post-Auditoría — Items priorizados para ejecución  
**Baseline:** 445 tests passing, 35% coverage global

---

## Estado Actual por Módulo

| Módulo | Coverage | Tests | Veredicto |
|--------|----------|-------|-----------|
| core/models.py | 98% | 30+ | ✅ Production-ready |
| core/filters.py | 95% | 30 | ✅ Production-ready |
| core/config.py | 71% | 2 | ⚠️ Needs isolation tests |
| review_engine.py | 82% | 25 | ✅ Production-ready |
| engine/checks/flow.py | 67% | 3 direct | ⚠️ Individual checks untested |
| engine/checks/completeness.py | 88% | 3 direct | ⚠️ Gaps in CMP-004 to CMP-009 |
| engine/checks/reasonableness.py | 76% | 2 direct | ⚠️ RSN-001/002/004-010 untested |
| engine/checks/rollover.py | 75% | 5 direct | ⚠️ ROL-005/006/008/009/011/012 |
| engine/checks/cross_schedule.py | 67% | 0 direct | ❌ All XSC tests are indirect |
| engine/checks/cross_form.py | 79% | 0 direct | ❌ XFM-002/003 never triggered |
| parser.py | 85% | 27 | ✅ Good |
| reconciler.py | 68% | 44 | ⚠️ 3-way integration still partial |
| workbook_reader.py | 13% | 0 | ❌ CRITICAL — Zero direct tests |
| export/excel_exporter.py | 92% | 5 | ✅ Good |
| export/csv_exporter.py | 90% | 8 | ✅ Good |
| export/html_exporter.py | 9% | 0 | ❌ No tests |
| export/pdf_exporter.py | 11% | 0 | ❌ No tests |
| reports/__init__.py | 33% | 2 | ⚠️ Orchestrator untested |
| api/service.py | 82% | 9 | ✅ Good |
| cli.py | 0% | 0 | ⚠️ Thin wrapper, lower priority |
| dashboard.py | 0% | 0 | Low risk (presentation) |

---

## P0 — Bloqueantes (Atacar Primero)

### P0-001: WorkbookReader — Zero Coverage

**Riesgo:** Si el workbook se parsea mal, toda la reconciliación es inválida.  
**Ubicación:** `lab/xml_parser/workbook_reader.py` (302 líneas, 13% coverage)  
**Dependencia:** Necesita fixture `.xlsx` con datos conocidos.

**Acción requerida:**
1. Crear `lab/tests/fixtures/sample_workbook.xlsx` con:
   - Sheet "5471 Sch H - FC" con 3 entidades (E001, E002, E003)
   - Sheet "5471 Sch I-1 - FC" con las mismas 3 entidades
   - Sheet "Entity Listing" con metadata
   - Valores calculables manualmente para reconciliación
2. Crear `lab/tests/test_workbook_reader.py` con:
   - `TestWorkbookReaderInit` — context manager, file not found
   - `TestLayoutADetection` — entities-across-columns parsing
   - `TestLayoutBDetection` — entities-down-rows parsing
   - `TestProfileAutoDetect` — sample vs generic profile
   - `TestScheduleSheetMapping` — correct sheet name resolution
   - `TestDataExtraction` — values match expected for each schedule
   - `TestEdgeCases` — empty sheets, missing entities, protected files

**Criterio de éxito:** Coverage >= 70%, todas las schedules parseadas correctamente.

---

### P0-002: Reconciler Integration con Datos Reales

**Riesgo:** `reconcile()` nunca se ha probado end-to-end con WorkbookReader + Parser reales.  
**Ubicación:** `lab/xml_parser/reconciler.py` — `reconcile()` method  
**Dependencia:** P0-001 (necesita fixture de workbook)

**Acción requerida:**
1. Crear `lab/tests/test_reconciler_integration.py` con:
   - `TestTwoWayWithRealData` — sample_cy.xml vs sample_workbook.xlsx
   - Verificar que `pass_rate` >= 0.90 con datos alineados
   - Verificar que discrepancias intencionales son detectadas como FAIL
   - Test con tolerance=0 vs tolerance=100
   - Test con schedules filter (solo sch_h, solo sch_f)
2. Extender fixture de workbook con valores que matcheen XML:
   - E001 Sch H income = valor de sample_cy.xml → expect PASS
   - E002 con valor deliberadamente diferente → expect FAIL

**Criterio de éxito:** End-to-end reconcile devuelve resultados correctos.

---

### P0-003: Service.reconcile() Sin Cobertura

**Riesgo:** El endpoint de reconciliación del service layer nunca se ejecutó en tests.  
**Ubicación:** `lab/xml_parser/api/service.py` — `reconcile()` method (líneas 191-258)  
**Dependencia:** P0-001 + P0-002

**Acción requerida:**
1. Agregar a `lab/tests/test_service.py`:
   - `TestServiceReconcile.test_reconcile_success` — happy path
   - `TestServiceReconcile.test_reconcile_bad_xml` — error handling
   - `TestServiceReconcile.test_reconcile_bad_workbook` — error handling
   - `TestServiceReconcile.test_reconcile_with_export` — output file created
   - `TestServiceReconcile.test_reconcile_summary_populated`

**Criterio de éxito:** Service.reconcile() coverage > 80%.

---

## P1 — Alto Impacto (Siguiente Sprint)

### P1-001: Checks Individuales sin Test Directo

**Riesgo:** Si la lógica de un check individual cambia, no hay test que lo detecte.  
Los checks solo están cubiertos indirectamente via el baseline de 28 findings.

**Ubicación:** `lab/xml_parser/engine/checks/`

**Checks sin test individual directo:**

| Check | Módulo | Lo que valida |
|-------|--------|---------------|
| FLO-009 | flow.py | Sch H E&P math (line1 + line3 - line4 = line5a) |
| FLO-010 | flow.py | Sch F asset components = total assets |
| FLO-011 | flow.py | Sch F L+E components = total L+E |
| FLO-012 | flow.py | Sch C gross profit = receipts - returns - COGS |
| FLO-013 | flow.py | Sch I-1 exclusions sum |
| FLO-014 | flow.py | Sch I-1 tested income derivation |
| FLO-015 | flow.py | Sch F BOY balance sheet equation |
| FLO-016 | flow.py | Sch E tested tax vs Sch I-1 |
| FLO-017 | flow.py | Sch J CY E&P vs Sch H |
| FLO-018 | flow.py | Sch H basket allocation |
| FLO-019 | flow.py | Dormant entity with income |
| FLO-020 | flow.py | Sch I-1 gross decomposition |
| CMP-004 | completeness.py | Missing Sch G with >50% ownership |
| CMP-006 | completeness.py | Missing Sch I when income > threshold |
| CMP-007 | completeness.py | Missing Schedule Q |
| CMP-008 | completeness.py | Missing dormant indicator |
| CMP-009 | completeness.py | Incomplete entity address |
| RSN-001 | reasonableness.py | FX rate outside expected band |
| RSN-002 | reasonableness.py | Revenue vs assets ratio anomaly |
| RSN-004 | reasonableness.py | Negative E&P but positive distributions |
| RSN-005 | reasonableness.py | Year-over-year revenue spike |
| RSN-007 | reasonableness.py | Asset growth > 100% |
| RSN-008 | reasonableness.py | Tested income without QBAI |
| RSN-009 | reasonableness.py | Tested loss > revenue |
| RSN-010 | reasonableness.py | Zero subpart F with filer categories |
| ROL-005 | rollover.py | FX rate large swing |
| ROL-006 | rollover.py | Revenue direction change |
| ROL-008 | rollover.py | Sch F BOY != PY EOY |
| ROL-009 | rollover.py | Sch J beginning balance != PY ending |
| ROL-011 | rollover.py | E&P previously taxed total shift |
| ROL-012 | rollover.py | Distribution vs E&P available |
| XSC-001 to XSC-009 | cross_schedule.py | All cross-schedule checks |
| XFM-002 | cross_form.py | 5471 Sch C vs parent 8990 |
| XFM-003 | cross_form.py | Interest expense consistency |

**Acción requerida:**
1. Crear XML fixtures mínimas que triggeren cada check individualmente
2. Crear `lab/tests/test_checks_individual.py` con un test por check
3. Pattern: construir XML minimal → run engine → assert check_id in findings

**Criterio de éxito:** Cada check_id tiene al menos 1 test que verifica que se dispara correctamente.

---

### P1-002: HTML/PDF Export Sin Verificación

**Riesgo:** Los reportes HTML/PDF podrían renderizar datos incorrectos o crashear.  
**Ubicación:** `lab/xml_parser/export/html_exporter.py` (9%), `pdf_exporter.py` (11%)

**Acción requerida:**
1. Verificar dependencias instaladas (`great-tables`, `xhtml2pdf`)
2. Crear `lab/tests/test_export_html_pdf.py`:
   - `TestHTMLExport.test_generates_file` — archivo HTML creado
   - `TestHTMLExport.test_contains_entity_names` — spot check contenido
   - `TestHTMLExport.test_contains_all_reports` — one section per report
   - `TestPDFExport.test_generates_file` — archivo PDF creado
   - `TestPDFExport.test_not_empty` — size > 1KB
   - `TestPDFExport.test_valid_pdf_header` — starts with %PDF

**Criterio de éxito:** Al menos smoke tests para ambos formatos.

---

### P1-003: Parser — Cobertura de Ramas Faltantes

**Riesgo:** XML real puede tener estructuras no cubiertas por los fixtures.  
**Ubicación:** `lab/xml_parser/parser.py` — líneas 225-244, 295-320

**Ramas no cubiertas:**
- `to_dataframe()` con ALL multi-instance forms (línea 213-244)
- `_parse_subsidiaries()` multi-instance form key generation (línea 295-320)
- `_extract_entity_info()` category filer parsing (línea 354-359)

**Acción requerida:**
1. Agregar a `test_parser_unit.py`:
   - `test_to_dataframe_all_multi_instance` — forms=["IRS5471ScheduleJ", "IRS5471ScheduleQ"]
   - `test_parse_returns_multi_instance_form_keys` — verify form_key includes basket
   - `test_entity_category_filers` — verify category_filers list populated

**Criterio de éxito:** Parser coverage >= 90%.

---

## P2 — Mejora Continua

### P2-001: Performance Benchmarks

**Acción:** Crear `lab/tests/test_performance.py` con `@pytest.mark.slow`:
- Tiempo de parsing para 5 entidades (current fixture)
- Tiempo de review completo (target: < 2s)
- Tiempo de export Excel (target: < 1s)
- Memory footprint estimation

### P2-002: Config/Logging Coverage

**Acción:** Tests para `core/config.py` (71%) y `core/logging.py` (27%):
- `reset_config()` crea nueva instancia
- Environment variable override (`MYTHOS_OUTPUT_DIR`)
- `get_logger()` returns named logger
- Log level respects config

### P2-003: Reports Orchestrator

**Acción:** `reports/__init__.py` (33%) — test `run_all_reports()` routing:
- Verifica que los 12 reportes son generados
- Verifica que reportes con 0 items son incluidos (no filtrados)
- Test `ReportEngine` backward-compat wrapper completamente

### P2-004: Dead Code Removal

**Candidatos para eliminación:**
- `output.py` (560 líneas, 0% coverage) — legacy PwC orange format
- `gt_output.py` (2 líneas) — shim sin uso
- `gen_import_v5.py`, `gen_import_v6.py` — superseded by v7
- `dashboard_st.py` — if NiceGUI is the standard

**Acción:** Grep para imports/uso, confirmar que nada los referencia, eliminar.

### P2-005: Version Consistency

**Issue:** `__init__.py` dice 0.7.0, `pyproject.toml` dice 0.6.1, spec dice 0.7.2.  
**Acción:** Unificar en single source of truth (pyproject.toml) + importar en `__init__.py`.

---

## Bugs Identificados (No Bloqueantes)

### BUG-001: Reconciler `loc` puede retornar Series si hay índice duplicado

**Ubicación:** `reconciler.py:312`  
**Trigger:** Si `wb_df.index` tiene duplicados (e.g., entidad aparece 2 veces en workbook)  
**Impacto:** `_compare_field()` recibe Series en vez de scalar → TypeError o resultado incorrecto  
**Fix propuesto:** Agregar `.iloc[0]` o deduplicar índice antes de comparar

### BUG-002: ReviewEngine entity_count asume `_reference_id` existe

**Ubicación:** `review_engine.py:67`  
**Trigger:** XML sin subsidiaries parsea a DataFrame vacío sin `_reference_id` column  
**Impacto:** KeyError si se corre review sobre XML sin Form 5471  
**Fix propuesto:** Guard con `if "_reference_id" in df_cy.columns`

---

## Criterios de Aceptación para Release

| Criterio | Estado | Target |
|----------|--------|--------|
| 0 tests failing | ✅ 445/445 | Mantener |
| Core engine coverage > 80% | ✅ 82% | Mantener |
| Reconciler coverage > 60% | ✅ 68% | → 80% con P0-002 |
| WorkbookReader coverage > 0% | ❌ 13% | → 70% con P0-001 |
| Service.reconcile() tested | ❌ | ✅ con P0-003 |
| Export content verified | ✅ CSV/Excel | + HTML/PDF con P1-002 |
| Individual check regression | ⚠️ Parcial | ✅ con P1-001 |
| No critical bugs open | ⚠️ 2 medium | Fix BUG-001/002 |
| Performance baseline set | ❌ | P2-001 |

---

## Orden de Ejecución Recomendado

```
P0-001 (WorkbookReader fixture + tests)
  ↓
P0-002 (Reconciler integration con datos reales)
  ↓
P0-003 (Service.reconcile tests)
  ↓
P1-001 (Check individual tests — puede ser paralelo)
  ↓
P1-002 (HTML/PDF smoke tests)
  ↓
P1-003 (Parser branch coverage)
  ↓
P2-* (mejora continua)
```

Los P0 son secuenciales (cada uno depende del anterior).  
P1-001 puede ejecutarse en paralelo con los P0.

---

## Comandos de Referencia

```bash
# Run solo los tests nuevos
python -m pytest lab/tests/test_reconciler.py lab/tests/test_parser_unit.py lab/tests/test_export_content.py lab/tests/test_integration_pipeline.py -v

# Run toda la suite
python -m pytest lab/tests/ -v

# Coverage por módulo específico
python -m pytest lab/tests/ --cov=lab.xml_parser.reconciler --cov-report=term-missing

# Solo tests marcados como críticos (una vez implementados)
python -m pytest lab/tests/ -m critical

# Generar HTML coverage report
python -m pytest lab/tests/ --cov=lab.xml_parser --cov-report=html:lab/tests/htmlcov
```

# Mythos UI/UX — Plan de Mejora Integral

## A. Evaluacion General

### Que funciona bien
- La arquitectura tecnica es solida (NiceGUI + async service bridge)
- El sistema de temas dark/light con tokens CSS es robusto
- La estructura de 6 paginas cubre los flujos principales
- Las animaciones y glassmorphism dan sensacion de producto pulido
- Los shortcuts de teclado aceleran a usuarios expertos
- El progress overlay comunica estado durante procesos largos

### Que debe mejorar
- **Falta de contexto inicial:** El usuario llega a una pantalla vacia sin entender que hacer primero
- **Overview sin proposito claro:** Los KPIs se muestran post-hoc pero no guian decisiones
- **Navegacion plana:** 5 items al mismo nivel no refleja prioridad ni flujo de trabajo
- **Exceso de informacion simultanea:** Findings muestra 9 columnas + filtros sin priorizacion
- **Sin onboarding:** Ningun elemento explica que es Mythos ni como empezar
- **Sin historial:** No hay forma de ver ejecuciones previas ni comparar resultados
- **Mensajes genericos:** "No review loaded" no dice nada sobre el VALOR de cargar uno
- **Reconciliacion desconectada:** Aparece como pagina independiente sin relacion con el review

### Oportunidades
- Convertir el Overview en un "cockpit de decision" (que debo revisar AHORA?)
- Agregar un flujo guiado de primera vez (onboarding de 3 pasos)
- Unificar review + reconciliacion en un flujo secuencial coherente
- Agregar drill-down contextual (click en KPI → filtro aplicado)
- Implementar "action items" priorizados en lugar de solo hallazgos

---

## B. Definicion del Usuario

### Tipo 1: Senior Associate / Manager (usuario principal)
- **Rol:** Responsable del review de compliance para 1-5 clientes
- **Conocimiento:** Alto en US int'l tax, medio en herramientas tecnicas
- **Objetivo:** Terminar review rapido, identificar problemas criticos, documentar
- **Frustración:** Perder tiempo revisando manualmente lo que deberia ser automatico
- **Pregunta principal:** "Hay algo MAL en este return que necesite atencion?"
- **Decision:** Escalar vs resolver, flag para senior review, sign-off

### Tipo 2: Staff / Junior (usuario secundario)
- **Rol:** Ejecuta el proceso, prepara workpapers
- **Conocimiento:** Medio en tax, bajo en la herramienta al inicio
- **Objetivo:** Correr el review sin errores, entregar resultados al Senior
- **Frustración:** No saber si hizo bien el proceso o que hacer con los resultados
- **Pregunta principal:** "Lo hice bien? Que falta?"

### Tipo 3: Senior Manager / Director (usuario ocasional)
- **Rol:** Supervision, quality review
- **Conocimiento:** Alto en tax, no opera la herramienta directamente
- **Objetivo:** Ver resumen ejecutivo, confirmar que no hay riesgos
- **Pregunta principal:** "Puedo firmar esto? Hay algo que me preocupe?"

---

## C. Inventario de Funcionalidades

### Funciones principales (core value)
| Funcion | Descripcion | Visibilidad necesaria |
|---------|-------------|----------------------|
| Compliance Review | 32+ checks automaticos sobre XML | **Maxima** — es la razon de existir |
| Severity Classification | HIGH/MEDIUM/LOW prioriza atencion | Alta — guia decision del usuario |
| Entity Drill-down | Ver problemas por entidad | Alta — el trabajo se organiza por entidad |
| Export | Generar workpaper en Excel/PDF | Alta — deliverable final |

### Funciones secundarias (enablers)
| Funcion | Descripcion | Visibilidad necesaria |
|---------|-------------|----------------------|
| Reconciliacion | Workbook vs XML field-by-field | Media — flujo separado |
| Rollover comparison | CY vs PY year-over-year | Media — se activa con 2 archivos |
| Demo datasets | Prueba rapida con data real | Baja — solo onboarding/demo |
| Theme toggle | Dark/light | Baja — preferencia personal |
| Shortcuts | Navegacion por teclado | Baja — power users |

### Funciones que requieren mayor visibilidad (actualmente escondidas)
- **Action items:** Los findings HIGH deberian presentarse como "cosas que hacer", no solo datos
- **Resumen ejecutivo:** Un parrafo generado que un Manager pueda leer en 10 segundos
- **Progreso del review:** "Has revisado 40/62 entidades" (tracking de resolution)
- **Historial:** Comparar esta ejecucion vs la anterior

---

## D. Arquitectura de Informacion

### Sitemap Propuesto

```
MYTHOS
├── Home (nuevo — reemplaza Overview actual)
│   ├── Estado del review activo (o prompt para empezar)
│   ├── Action items priorizados (HIGH findings como tareas)
│   ├── Resumen ejecutivo (1 parrafo)
│   └── Quick stats (KPIs con contexto)
│
├── Review
│   ├── Iniciar / Configurar
│   │   ├── Seleccionar XML (current + prior)
│   │   ├── Opciones (tolerances, checks a excluir)
│   │   └── Ejecutar
│   ├── Resultados
│   │   ├── Hallazgos (tabla filtrable)
│   │   ├── Por entidad (cards + drill-down)
│   │   └── Por categoria (agrupacion por dimension)
│   └── Exportar
│
├── Reconciliacion
│   ├── Configurar (XML + Workbook + tolerance)
│   ├── Resultados (pass/fail por campo)
│   └── Exportar
│
├── Historial (nuevo)
│   ├── Ejecuciones anteriores
│   ├── Comparar resultados
│   └── Tendencias
│
└── Configuracion (nuevo — reemplaza About parcialmente)
    ├── Sobre Mythos
    ├── Shortcuts
    └── Preferencias (tema, tolerancias default)
```

### Justificacion de la agrupacion
- **Por flujo de trabajo** (no por tipo de dato): El usuario piensa "quiero revisar un return", no "quiero ver findings"
- **Review como modulo central:** Agrupa setup → ejecucion → resultados → export
- **Home como cockpit:** Responde "donde estoy?" y "que hago ahora?"
- **Historial separado:** Permite retrospectiva sin ensuciar el flujo activo

---

## E. User Flows

### Flow 1: Primera vez (onboarding)

```
[Abre app] → [Home: bienvenida + que es Mythos]
  → [CTA: "Iniciar primer review" o "Cargar demo"]
  → [Seleccionar XML]
  → [Preview: "62 entidades detectadas, Form 5471"]
  → [Ejecutar review]
  → [Progress overlay con contexto: "Ejecutando 32 checks..."]
  → [Resultado: Home actualizado con action items]
```

**Decisiones:** Cargar demo vs propio archivo. Prior year si/no.
**Validaciones:** XML valido, form type soportado, archivo no corrupto.
**Errores posibles:** XML invalido → mensaje especifico con solucion.

### Flow 2: Review recurrente (usuario habitual)

```
[Abre app] → [Home: muestra ultimo review o prompt]
  → [Sidebar: "Nuevo Review" o arrastrar XML]
  → [Confirmar archivos + opciones]
  → [Ejecutar] → [Progress]
  → [Home: action items actualizados]
  → [Click en action item HIGH → Entity detail]
  → [Revisar, marcar como visto/resuelto]
  → [Exportar workpaper]
```

### Flow 3: Reconciliacion

```
[Home o Nav: "Reconciliacion"]
  → [Seleccionar XML (auto-detecta si ya hay review activo)]
  → [Upload workbook]
  → [Configurar tolerancia + schedules]
  → [Ejecutar] → [Progress]
  → [Resultados: pass rate + failures table]
  → [Exportar]
```

### Flow 4: Supervision (Manager)

```
[Abre app] → [Home: resumen ejecutivo]
  → [Lee: "62 entities, 5 HIGH findings, 89% pass rate"]
  → [Click "Ver criticos"] → [Findings filtrados a HIGH]
  → [Revisa cada uno] → [Decide: escalar o aceptar]
  → [Exportar resumen para sign-off]
```

### Flow 5: Comparar con ejecucion anterior

```
[Historial] → [Seleccionar 2 ejecuciones]
  → [Vista comparativa: delta de findings]
  → ["3 nuevos findings, 2 resueltos, 5 sin cambio"]
```

---

## F. Propuesta de Pantallas

### 1. HOME (reemplaza Overview)
**Objetivo:** Responder "Donde estoy? Que debo hacer?"

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| Status banner | Estado del review activo o CTA para iniciar | P1 |
| Action items | Findings HIGH como checklist accionable | P1 |
| Resumen ejecutivo | 2-3 lineas que un Manager puede leer | P1 |
| KPIs | Entidades, findings, pass rate — CON CONTEXTO | P2 |
| Charts | Solo si ayudan a decidir (severity donut SI, category bar EVALUAR) | P3 |

### 2. REVIEW SETUP (nueva)
**Objetivo:** Configurar y lanzar un review de forma clara

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| File selector | Drag-drop o browse, muestra nombre + preview | P1 |
| Preview | Tras cargar: "62 entities, Form 5471, FY2025" | P1 |
| Options | Tolerance, checks a excluir (colapsable, default ok) | P3 |
| Execute CTA | Boton principal prominente | P1 |

### 3. FINDINGS (mejorada)
**Objetivo:** Encontrar y entender problemas especificos

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| Filtros | Severity, Category, Entity, Search — glass bar | P1 |
| Count | "Mostrando 15 de 47" dinamico | P1 |
| Tabla | Severity badge, entity, description, delta | P1 |
| Row expansion | Click para ver expected/actual/context completo | P2 |
| Bulk actions | "Exportar filtrados", "Marcar como revisados" | P3 |

### 4. ENTITIES (mejorada)
**Objetivo:** Ver estado por entidad, identificar las problematicas

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| Sort/filter | Por severidad, por nombre, solo con issues | P1 |
| Cards | Entity code, name, severity breakdown, click → detail | P1 |
| Chart | Solo si >10 entities (stacked bar top 10) | P2 |

### 5. ENTITY DETAIL (existente, mejorar)
**Objetivo:** Todo sobre UNA entidad

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| Header | Code, name, country, currency, schedules present | P1 |
| Findings | Tabla filtrada a esta entidad | P1 |
| Schedule data | Cards con datos clave de Sch H/I-1/J | P2 |
| Reconciliation status | Si se corrio, mostrar pass/fail aqui | P3 |

### 6. RECONCILIATION (existente, mejorar)
**Objetivo:** Validar workbook contra XML

(Mantener estructura actual, mejorar mensajes y estados)

### 7. HISTORY (nueva)
**Objetivo:** Ver ejecuciones pasadas, comparar

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| Lista | Fecha, cliente, entities, findings, pass rate | P1 |
| Compare | Seleccionar 2, ver delta | P2 |
| Trends | Grafico de findings over time (si hay 3+ runs) | P3 |

### 8. SETTINGS (nueva — reemplaza About)
**Objetivo:** Preferencias y documentacion

| Seccion | Contenido | Prioridad |
|---------|-----------|-----------|
| About | Que es Mythos, version, arquitectura | P2 |
| Shortcuts | Tabla de keybindings | P2 |
| Preferences | Tema, tolerancias default, export format | P3 |

---

## G. Botones y Acciones

### Acciones Principales (siempre visibles, prominentes)

| Boton | Ubicacion | Funcion | Estado disabled | Confirmacion |
|-------|-----------|---------|-----------------|--------------|
| "Run Review" | Sidebar + Setup page | Ejecutar review completo | Sin XML cargado | No |
| "Export Report" | Header/toolbar | Generar Excel/PDF | Sin review activo | No |
| "Load XML" | Home (empty state) + Sidebar | Abrir file picker | Nunca | No |

### Acciones Secundarias

| Boton | Ubicacion | Funcion | Estado disabled |
|-------|-----------|---------|-----------------|
| "Run Reconciliation" | Reconciliation page | Ejecutar comparacion | Sin XML + workbook |
| "Load Demo" | Sidebar | Cargar dataset de prueba | Nunca |
| "Compare" | History | Comparar 2 ejecuciones | <2 seleccionadas |
| "Filter: HIGH only" | Findings | Filtro rapido severity | Sin findings |

### Acciones Destructivas

| Boton | Ubicacion | Funcion | Confirmacion |
|-------|-----------|---------|--------------|
| "Clear Review" | Settings/menu | Borrar estado actual | Si — "Perdera los resultados actuales" |
| "Reset Filters" | Findings | Limpiar todos los filtros | No |

### Acciones Contextuales

| Boton | Ubicacion | Funcion |
|-------|-----------|---------|
| "View Entity" | Findings row | Ir a entity detail |
| "Export Filtered" | Findings (con filtros activos) | Exportar solo lo visible |
| "Back" | Entity detail, sub-pages | Volver al nivel anterior |
| "Re-run" | Home (con review previo) | Ejecutar de nuevo mismo XML |

### Lineamientos de naming
- Usar verbos en infinitivo: "Run", "Export", "Load", "View", "Compare"
- Incluir objeto cuando sea ambiguo: "Run Review" no solo "Run"
- Evitar: "Aceptar", "Continuar", "Procesar", "OK"
- Destructivas en rojo, principales en accent, secundarias en outline

---

## H. Dashboard Principal (Home)

### Pregunta que responde cada seccion

| Seccion | Pregunta del usuario |
|---------|---------------------|
| Status banner | "Tengo un review activo? De que cliente?" |
| Action items | "Que necesita mi atencion AHORA?" |
| KPI: Entities | "Cuantas entidades analice?" |
| KPI: Pass Rate | "En general, esta bien o mal?" |
| KPI: Critical | "Cuantos problemas serios hay?" |
| Severity donut | "Que proporcion de findings son graves?" |
| Resumen ejecutivo | "Que le digo a mi manager en 10 segundos?" |

### Elementos que NO deben estar en Home
- Category bar chart (no guia decision inmediata, va en Findings)
- Quick Summary panel (redundante con KPIs)
- Top 10 findings table (confuso — es para Findings page)
- Technical metadata (form type, run timestamp — va en header badge)

### Empty State (Home sin review)
```
┌─────────────────────────────────────────────────┐
│  ⬡ Bienvenido a Mythos                         │
│                                                 │
│  Review automatizado de compliance para         │
│  IRS Form 5471 — 32 checks en < 3 segundos     │
│                                                 │
│  [Load XML to Start]    [Try Demo Dataset]      │
│                                                 │
│  O arrastra un archivo XML aqui                 │
└─────────────────────────────────────────────────┘
```

---

## I. Experiencia de Datos

### Tablas — Reglas generales
- **Columnas visibles por default:** max 6 (severity, entity, category, description, delta, actions)
- **Columnas expandibles:** expected, actual, context, check_id — via row expansion
- **Formato numeros:** $1,234 (con signo y color: rojo positivo = discrepancia, verde = ok)
- **Formato severity:** Badge con color + texto (no solo color)
- **Ordenamiento default:** Severity DESC, luego delta DESC (lo peor primero)
- **Paginacion:** 25 rows, con opcion 50/100, mostrar "Showing 1-25 of 47"
- **Empty state:** Icono + mensaje + accion sugerida
- **Row hover:** Highlight sutil + cursor pointer si clickeable
- **Row click:** Expande detalles (no navega — expansion in-place)
- **Export:** Boton "Export visible" que respeta filtros activos

### Graficos — Cuando SI usarlos
- **Severity donut:** SI en Home — da overview instantaneo del "health"
- **Entity bar chart:** SI en Entities (>5 entities con findings) — identifica outliers
- **Reconciliation pass/fail:** SI — un numero grande basta, grafico solo si hay breakdown por schedule

### Graficos — Cuando NO usarlos
- Category bar en Home (el usuario no toma decisiones basadas en distribucion de categorias)
- Charts con <3 data points
- Charts redundantes con KPIs que ya muestran el mismo numero

### Datos criticos vs contextuales
| Nivel | Que mostrar | Como |
|-------|-------------|------|
| Critico | Severity HIGH findings | Badge rojo + lista prominente |
| Importante | Count totales, pass rate | KPI cards grandes |
| Contextual | Check ID, expected/actual | Row expansion o tooltip |
| Referencia | Entity country, currency | Header/detail page, no en tablas |

---

## J. Estados de la Aplicacion

### Inventario de estados y tratamiento

| Estado | Que ve el usuario | Mensaje | Accion disponible |
|--------|-------------------|---------|-------------------|
| Initial (sin XML) | Welcome + CTA | "Carga un archivo XML para iniciar el review" | Load XML, Try Demo |
| XML loaded (pre-run) | Preview del archivo | "62 entities detectadas. Listo para review." | Run Review, Change file |
| Running | Progress overlay | "Ejecutando check 15/32: Balance sheet integrity..." | Cancel (si posible) |
| Success (no issues) | Celebration state | "Review completo. Todas las entidades pasaron." | Export, View details |
| Success (with findings) | Home con action items | "Review completo. 5 issues requieren atencion." | View findings, Export |
| Success (HIGH findings) | Home con urgency | "3 problemas criticos detectados." | View critical, Export |
| Error (XML invalido) | Error card | "El archivo no es un return XML valido del IRS. Verifica el formato." | Try another file, View details |
| Error (parse failure) | Error card | "Error al procesar: [campo] no encontrado en Schedule H." | Retry, Report issue |
| Partial (rollover off) | Info banner | "Sin archivo de ano anterior — checks de rollover desactivados." | Add prior year |
| Reconcile: no workbook | Config panel | "Sube el workbook Excel para comparar contra el XML." | Upload |
| Reconcile: perfect match | Success card | "Todos los campos coinciden dentro de la tolerancia." | Export, Done |
| Reconcile: failures | Results table | "47 de 892 campos no coinciden (95% pass rate)." | View failures, Export |

### Principios para mensajes de estado
1. **Di QUE paso** (no solo "Error")
2. **Di POR QUE** si es posible (no solo "fallo" sino "porque falta columna X")
3. **Di QUE HACER** (accion siguiente siempre visible)
4. **Oculta detalles tecnicos** por default (expandible para debug)

---

## K. Mensajes y Microcopy

### Lineamientos

| Tipo | Regla | Ejemplo bueno | Ejemplo malo |
|------|-------|---------------|--------------|
| Titulo | Corto, descriptor | "Compliance Findings" | "All Findings Report View" |
| CTA | Verbo + objeto | "Run Review" | "Proceed" |
| Exito | Resultado + numero | "47 findings across 62 entities" | "Process completed successfully" |
| Error | Causa + solucion | "XML invalido — falta IRS5471ScheduleH" | "Error de procesamiento" |
| Empty | Contexto + accion | "Sin resultados. Carga un XML para empezar." | "No data" |
| Tooltip | 1 linea util | "Diferencia entre expected y actual value" | (sin tooltip) |
| Placeholder | Ejemplo real | "Search by entity name or check ID..." | "Search..." |
| Confirmacion | Consecuencia | "Se borraran los resultados actuales" | "Esta seguro?" |

### Microcopy especifico para Mythos

| Ubicacion | Actual | Propuesto |
|-----------|--------|-----------|
| KPI "Pass Rate" | "Pass Rate" | "Entities sin problemas" |
| KPI "Critical Issues" | "Critical Issues" | "Requieren atencion" |
| Empty findings | "No findings yet" | "Sin hallazgos — ejecuta un review para empezar" |
| Empty entities | "No entities loaded" | "Carga un return XML para ver las entidades" |
| Severity HIGH | "HIGH" | "CRITICAL" (mas urgente) |
| Severity MEDIUM | "MEDIUM" | "REVIEW" (sugiere accion) |
| Severity LOW | "LOW" | "INFO" (no requiere accion) |

---

## L. Consistencia Visual — Design System

### Paleta de colores

| Token | Dark | Light | Uso |
|-------|------|-------|-----|
| bg-main | #0f0f13 | #f8f9fc | Fondo principal |
| bg-card | #1a1a23 | #ffffff | Tarjetas y paneles |
| bg-elevated | #242430 | #f1f3f8 | Elementos elevados |
| accent | #f59e0b (amber) | #d97706 | CTAs, links, highlights |
| critical | #ef4444 (red) | #dc2626 | Errores, HIGH severity |
| warning | #f59e0b (amber) | #d97706 | Warnings, MEDIUM severity |
| success | #10b981 (green) | #059669 | Pass, clean entities |
| info | #6366f1 (indigo) | #4f46e5 | Informational, LOW severity |

### Tipografia

| Nivel | Font | Size | Weight | Uso |
|-------|------|------|--------|-----|
| H1 | Inter | 24px | 700 | Page titles |
| H2 | Inter | 18px | 600 | Section titles |
| H3 | Inter | 14px | 600 | Card titles |
| Body | Inter | 14px | 400 | Texto general |
| Small | Inter | 12px | 400 | Labels, metadata |
| Caption | Inter | 11px | 400 | Timestamps, ids |
| Mono | JetBrains Mono | 13px | 500 | Numeros, codes, entities |

### Espaciado (4px base)

| Token | Value | Uso |
|-------|-------|-----|
| xs | 4px | Dentro de chips/badges |
| sm | 8px | Entre elementos inline |
| md | 16px | Padding de cards |
| lg | 24px | Spacing entre secciones |
| xl | 32px | Page padding |
| 2xl | 48px | Separadores de zona |

### Componentes

| Componente | Variantes | Regla |
|------------|-----------|-------|
| Button | Primary (filled accent), Secondary (outline), Ghost (text only), Danger (red) | Max 1 primary per section |
| Card | Default (bg-card + border), Glass (backdrop-filter), Elevated (shadow strong) | Glass para charts, Default para data |
| Badge | Critical (red), Warning (amber), Info (indigo), Success (green), Neutral (grey) | Siempre con texto, no solo color |
| Table | Dense (findings), Comfortable (reconciliation), Expandable rows | Default: dense |
| Input | Outlined (forms), Flat (filters) | Outlined para datos, flat para filtros rapidos |
| Alert | Error (red bg), Warning (amber bg), Info (blue bg), Success (green bg) | Include icon + message + action |

---

## M. Accesibilidad

### Requerimientos minimos

| Area | Requerimiento | Estado actual | Accion |
|------|---------------|---------------|--------|
| Contraste | Texto: 4.5:1, Large text: 3:1 | OK en dark (amber on dark bg) | Verificar light mode muted text |
| Focus | Visible ring en todos los interactivos | Parcial (solo inputs) | Agregar focus ring a cards, nav items, buttons |
| Keyboard | Todas las acciones accesibles via keyboard | Si (shortcuts) | Verificar tab order logico |
| Color | No depender SOLO de color para status | Parcial (badges usan color + texto) | Agregar icono a severity badges |
| Labels | Todos los inputs con label asociado | Si | Mantener |
| Errors | Asociados al campo con aria-describedby | No | Agregar en forms de reconciliacion |
| Touch targets | Min 44x44px para mobile | N/A desktop primary | Mantener botones >40px |
| Screen readers | Estructura semantica | Parcial | Agregar aria-labels a charts |

### Severity sin depender solo de color
- HIGH/CRITICAL: Icono `error` + badge rojo + texto "CRITICAL"
- MEDIUM/REVIEW: Icono `warning` + badge amber + texto "REVIEW"
- LOW/INFO: Icono `info` + badge gris + texto "INFO"

---

## N. Responsive Design

### Estrategia: Desktop-first con breakpoints utiles

| Breakpoint | Comportamiento |
|------------|---------------|
| >1400px (default) | Full layout: sidebar + content + charts side by side |
| 1024-1400px | Sidebar se colapsa a iconos, charts stack vertically |
| 768-1024px | Sidebar se oculta (hamburger), single column |
| <768px | Not priority — mostrar "Use desktop for best experience" |

### Reglas por componente

| Componente | >1400 | 1024-1400 | 768-1024 |
|------------|-------|-----------|----------|
| Sidebar | Full (240px) | Icons only (64px) | Hidden + hamburger |
| KPI cards | 4 en fila | 2x2 grid | Stack vertical |
| Charts | 2 side by side | Stack vertical | Stack vertical |
| Table | Full columns | Hide expected/actual | Horizontal scroll |
| Entity cards | 4 per row | 3 per row | 2 per row |

---

## O. Plan de Mejoras por Fases

### Fase 1: Fundamentos de UX (1 semana)
| # | Actividad | Prioridad | Resultado |
|---|-----------|-----------|-----------|
| 1.1 | Redisenar Home como cockpit de decision | CRITICA | Home con status + action items + resumen |
| 1.2 | Mejorar empty states con CTA claros | CRITICA | Cada empty state guia al siguiente paso |
| 1.3 | Agregar onboarding para primera vez | ALTA | Welcome screen con 2 opciones claras |
| 1.4 | Renombrar severities (HIGH→CRITICAL, etc) | ALTA | Terminology mas accionable |
| 1.5 | Mejorar mensajes de error con causa+solucion | ALTA | Todos los errores son actionable |

### Fase 2: Arquitectura de Informacion (1 semana)
| # | Actividad | Prioridad | Resultado |
|---|-----------|-----------|-----------|
| 2.1 | Reorganizar nav (Home, Review, Reconcile, History) | CRITICA | Nav refleja flujo de trabajo |
| 2.2 | Mover setup a su propia pantalla | ALTA | Sidebar no sobrecargado |
| 2.3 | Implementar breadcrumbs en sub-pages | MEDIA | Usuario siempre sabe donde esta |
| 2.4 | Agregar "New Review" como accion global | ALTA | Accesible desde cualquier punto |
| 2.5 | Crear pagina Settings (merge About + prefs) | MEDIA | Limpieza de nav |

### Fase 3: Data Experience (1 semana)
| # | Actividad | Prioridad | Resultado |
|---|-----------|-----------|-----------|
| 3.1 | Implementar row expansion en findings table | CRITICA | Detalles sin overcrowded columns |
| 3.2 | Agregar "Export filtered" que respeta filtros | ALTA | Exporta solo lo que ve |
| 3.3 | KPIs clickeables (click → filtro aplicado) | ALTA | Navegacion contextual |
| 3.4 | Quitar charts innecesarios de Home | MEDIA | Home mas limpio y util |
| 3.5 | Agregar severity icon + text (no solo color) | MEDIA | Accesibilidad + claridad |

### Fase 4: Flujos Avanzados (1 semana)
| # | Actividad | Prioridad | Resultado |
|---|-----------|-----------|-----------|
| 4.1 | Implementar History page basica | MEDIA | Ver ejecuciones previas |
| 4.2 | Agregar review progress contextual | MEDIA | "Check 15/32: Balance sheet..." |
| 4.3 | Agregar resumen ejecutivo auto-generado | ALTA | 2-3 lineas para Manager review |
| 4.4 | Mejorar reconciliation con auto-detect XML | MEDIA | Menos pasos si ya hay review |
| 4.5 | Action items como checklist (mark as reviewed) | ALTA | Tracking de resolution |

### Fase 5: Polish (1 semana)
| # | Actividad | Prioridad | Resultado |
|---|-----------|-----------|-----------|
| 5.1 | Responsive breakpoints (1024/768) | MEDIA | Usable en laptop normal |
| 5.2 | Animaciones de transicion entre estados | BAJA | Feedback visual suave |
| 5.3 | Tooltips contextuales en check IDs | MEDIA | "QUE significa este check?" |
| 5.4 | Help contextual (? icon per section) | BAJA | Documentacion in-app |
| 5.5 | Final consistency audit de design system | MEDIA | Todo usa los mismos tokens |

---

## P. Backlog Priorizado

### CRITICAS (bloquean uso efectivo)
1. Home como cockpit de decision (no como data dump)
2. Empty states con CTA claros
3. Row expansion en findings table
4. Nav reorganizado por flujo de trabajo

### ALTA PRIORIDAD (impacto significativo en UX)
5. Onboarding para primera vez
6. Mensajes de error actionable
7. Renombrar severities
8. KPIs clickeables → filtro
9. "Export filtered"
10. Resumen ejecutivo auto-generado
11. Action items como checklist
12. "New Review" como accion global

### PRIORIDAD MEDIA (mejoran la experiencia)
13. Breadcrumbs en sub-pages
14. History page basica
15. Review progress contextual
16. Severity icon + text
17. Settings page unificada
18. Responsive breakpoints
19. Tooltips en check IDs
20. Consistency audit

### BAJA PRIORIDAD (nice to have)
21. Animaciones de transicion entre estados
22. Help contextual per section
23. Compare results (history)
24. Trends chart (3+ runs)
25. Configurable columns en tabla

---

## Q. Criterios de Aceptacion (por fase)

### Fase 1 esta completa cuando:
- [ ] Un usuario nuevo entiende que hacer en <10 segundos
- [ ] Cada pantalla vacia dice QUE HACER (no solo "no data")
- [ ] Los mensajes de error incluyen causa y solucion
- [ ] Las severities comunican urgencia, no solo clasificacion

### Fase 2 esta completa cuando:
- [ ] La nav refleja flujo de trabajo, no estructura tecnica
- [ ] El usuario puede iniciar un review desde cualquier pantalla
- [ ] Breadcrumbs muestran ubicacion en sub-pages
- [ ] Settings agrupa preferencias y documentacion

### Fase 3 esta completa cuando:
- [ ] Findings table muestra 6 columnas max, detalles en expansion
- [ ] Click en KPI aplica filtro automaticamente
- [ ] Export respeta filtros activos
- [ ] Severity usa icon + color + text (3 canales)

### Fase 4 esta completa cuando:
- [ ] History muestra ejecuciones previas con metadata
- [ ] Resumen ejecutivo se genera automaticamente post-review
- [ ] Action items pueden marcarse como "reviewed"
- [ ] Progress muestra nombre del check en curso

### Fase 5 esta completa cuando:
- [ ] App es usable en ventana de 1024px
- [ ] Todos los componentes usan tokens del design system
- [ ] Tooltips explican checks no obvios
- [ ] Transiciones entre estados son suaves (no flashes)

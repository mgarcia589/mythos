# Spec: Report Standards — Aplicable a Todos los Reportes

## Header Estándar

Todos los reportes (01-07+) deben incluir un header consistente al inicio con la
siguiente información en este orden:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  CLIENT:       Centerbridge Capital Partners III LP                          │
│  ENGAGEMENT:   Centerbridge FY25 International Tax Compliance                │
│  REPORT:       Schedule F Rollover                                           │
│  COMPARISON:   FY2024 (PY) vs FY2025 (CY)                                   │
│                                                                              │
│  Generated: 2026-07-20 14:35:22                                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Campos del Header

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| CLIENT | Nombre legal del cliente | "Centerbridge Capital Partners III LP" |
| ENGAGEMENT | Nombre del engagement (cliente + TY + tipo) | "Centerbridge FY25 International Tax Compliance" |
| REPORT | Nombre del reporte específico | "Schedule F Rollover", "Page 1 Static Data", etc. |
| COMPARISON | Años fiscales siendo comparados | "FY2024 (PY) vs FY2025 (CY)" |
| Generated | Fecha y hora de generación (ISO format) | "2026-07-20 14:35:22" |

### API — Parámetros de Header

Todos los reportes aceptan estos parámetros opcionales para el header:

```python
engine.sch_f_rollover(
    client_name="Centerbridge Capital Partners III LP",
    engagement="Centerbridge FY25 International Tax Compliance",
    # report_name se infiere automáticamente del tipo de reporte
    # comparison se infiere de los XML tax years
    # generated se calcula al momento de ejecutar
)
```

Si no se proveen, el header usa defaults:
- `client_name`: se extrae del XML si es posible (ReturnHeader), o "(Not specified)"
- `engagement`: "{client_name} FY{cy_year} International Tax Compliance"
- `report_name`: nombre fijo por reporte (ej: "Schedule F Rollover")
- `comparison`: "FY{py_year} (PY) vs FY{cy_year} (CY)" — extraído de los XMLs
- `generated`: `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`

### Visual por Formato

#### Excel
- Header en las primeras 6 rows del sheet (antes de la tabla de datos)
- Client name en bold 14pt, engagement en 11pt, report en 12pt bold naranja
- Fecha en gris italic
- Separador (thin orange line) antes del contenido

#### PDF
- Header en la primera página antes del contenido
- En páginas subsiguientes: header condensado en una línea (top margin):
  `CLIENT | REPORT | Page X of Y`
- Fecha en footer de cada página

#### HTML
- Header como bloque sticky-top con la información
- Background blanco con orange left-border (accent)

## Formato Tabular Estándar

Todos los reportes usan formato tabular columnar con:

1. **Columna de líneas/items** (izquierda) — siempre visible
2. **Columnas de valores** — PY XML vs CY XML
3. **Columna de diferencia/status** (derecha)

El orden de las líneas SIEMPRE sigue el orden en que aparecen en la forma IRS real
(Form 5471, 8858, etc.), no orden alfabético ni por severity.

## Materialidad Estándar

Para todos los reportes con comparación numérica:
- **Immaterial**: |diff| < $10 → Status = "OK"
- **Material**: |diff| ≥ $10 → Status = "Review"

Para reportes con comparación de texto:
- **Match** → Status = "OK"
- **Mismatch** → Status = "Review"

## Resumen Ejecutivo Estándar

Todos los reportes abren con un resumen ejecutivo DESPUÉS del header que incluye:
1. Conteo de diferencias materiales (o cambios detectados)
2. Lista de las diferencias materiales específicas (entity + field + diff)
3. Si no hay diferencias: "No material differences found."

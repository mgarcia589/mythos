"""Shared UI components — progress overlay, error boundary, loading states."""

import traceback
from functools import wraps

from nicegui import ui

from lab.mythos_ui.theme import get_theme, get_mode


LOGO_SVG_LARGE = """<svg width="56" height="64" viewBox="0 0 28 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M14 0.5L27 8.25V23.75L14 31.5L1 23.75V8.25L14 0.5Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
  <path d="M7.5 22V10L14 17L20.5 10V22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""


class ProgressOverlay:
    """Full-page glass overlay with animated progress during review execution.

    Uses a polling timer to read progress from AppState, since the review
    runs in a background thread and NiceGUI can only push UI updates from
    the async event loop.
    """

    def __init__(self):
        self.container = None
        self.progress_bar = None
        self.status_label = None
        self.pct_label = None
        self._timer = None

    def show(self):
        """Display the overlay and start polling progress from state."""
        from lab.mythos_ui.services.bridge import get_state

        t = get_theme()
        self.container = ui.element("div").classes("mythos-overlay animate-fade-in")

        with self.container:
            with ui.column().classes("items-center gap-6"):
                ui.html(LOGO_SVG_LARGE).classes("spin-slow") \
                    .style(f"color: {t['accent']};")

                ui.label("Running Compliance Review") \
                    .classes("text-lg font-semibold") \
                    .style(f"color: {t['text_primary']};")

                with ui.column().classes("w-80 gap-2"):
                    self.progress_bar = ui.linear_progress(value=0, show_value=False) \
                        .classes("progress-glow") \
                        .props("rounded size=8px")
                    self.progress_bar.style(f"border-radius: 4px;")

                    with ui.row().classes("w-full items-center justify-between"):
                        self.status_label = ui.label("Initializing...") \
                            .classes("text-xs") \
                            .style(f"color: {t['text_muted']};")
                        self.pct_label = ui.label("0%") \
                            .classes("text-xs font-semibold mythos-mono") \
                            .style(f"color: {t['accent']};")

                with ui.column().classes("w-80 gap-2 mt-4"):
                    ui.element("div").classes("shimmer").style("height: 12px; width: 100%;")
                    ui.element("div").classes("shimmer").style("height: 12px; width: 75%;")
                    ui.element("div").classes("shimmer").style("height: 12px; width: 60%;")

        def _poll():
            s = get_state()
            self.update(s.progress_msg, s.progress)

        self._timer = ui.timer(0.3, _poll)

    def update(self, msg: str, pct: float):
        """Update progress UI elements."""
        if self.progress_bar:
            self.progress_bar.value = pct
        if self.status_label and msg:
            self.status_label.text = msg
        if self.pct_label:
            self.pct_label.text = f"{int(pct * 100)}%"

    def hide(self):
        """Remove the overlay and stop polling."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self.container:
            self.container.delete()
            self.container = None


# ─── CUSTOM NOTIFICATIONS ─────────────────────────────────────────────────

def notify(message: str, level: str = "info", caption: str = ""):
    """Styled notification using the Mythos design system.

    Args:
        message: Main notification text.
        level: "success" | "warning" | "error" | "info"
        caption: Optional secondary line (smaller text).
    """
    t = get_theme()

    icon_map = {
        "success": "check_circle",
        "warning": "warning",
        "error": "error",
        "info": "info",
    }
    color_map = {
        "success": t["success"],
        "warning": t["warning"],
        "error": t["error"],
        "info": t["info"],
    }

    icon = icon_map.get(level, "info")
    accent = color_map.get(level, t["info"])

    bg = t["bg_elevated"]
    ui.notify(
        message,
        position="top-right",
        timeout=4,
        close_button="✕",
        icon=icon,
        caption=caption if caption else None,
        multi_line=bool(caption),
        options={
            "color": "dark" if get_mode() == "dark" else "white",
            "textColor": t["text_primary"],
            "iconColor": accent,
            "classes": "mythos-toast",
            "attrs": {"style": (
                f"border-left: 3px solid {accent}; "
                f"border-radius: 8px; "
                f"backdrop-filter: blur(12px); "
                f"font-family: 'Inter', sans-serif; "
                f"font-size: 0.8rem; "
                f"box-shadow: 0 4px 20px rgba(0,0,0,0.25); "
                f"min-width: 280px; max-width: 380px; "
            )},
        },
    )


def loading_skeleton(rows: int = 4):
    """Render shimmer loading placeholder cards."""
    t = get_theme()
    with ui.column().classes("w-full gap-3 animate-fade-in"):
        for _ in range(rows):
            with ui.row().classes("w-full gap-3"):
                ui.element("div").classes("shimmer") \
                    .style("height: 60px; flex: 1; border-radius: 12px;")
                ui.element("div").classes("shimmer") \
                    .style("height: 60px; flex: 2; border-radius: 12px;")
                ui.element("div").classes("shimmer") \
                    .style("height: 60px; flex: 1; border-radius: 12px;")


# ─── ERROR BOUNDARY ────────────────────────────────────────────────────────

def error_boundary(render_fn):
    """Decorator that wraps a page render function with error handling.

    If the render function raises, displays a friendly error card instead
    of crashing the entire app.
    """
    @wraps(render_fn)
    def wrapper(*args, **kwargs):
        try:
            return render_fn(*args, **kwargs)
        except Exception as exc:
            _render_error(exc)
    return wrapper


def _render_error(exc: Exception):
    """Display an actionable error card with cause + solution."""
    t = get_theme()
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    short_tb = "".join(tb[-3:])

    cause, solution = _diagnose(exc)

    with ui.column().classes("w-full items-center justify-center py-16 gap-4 animate-fade-up"):
        ui.icon("error_outline").classes("text-5xl") \
            .style(f"color: {t['error']}; opacity: 0.6;")
        ui.label("Something went wrong").classes("text-xl font-bold") \
            .style(f"color: {t['text_primary']};")

        # Cause + Solution card
        with ui.card().classes("max-w-lg w-full").style(
            f"background: {t['error']}08; border: 1px solid {t['error']}30; "
            f"border-radius: 12px; padding: 16px 20px;"
        ):
            with ui.row().classes("items-start gap-2 mb-2"):
                ui.icon("help_outline").classes("text-sm mt-0.5") \
                    .style(f"color: {t['error']};")
                ui.label(f"Cause: {cause}").classes("text-sm") \
                    .style(f"color: {t['text_primary']};")
            with ui.row().classes("items-start gap-2"):
                ui.icon("lightbulb").classes("text-sm mt-0.5") \
                    .style(f"color: {t['accent']};")
                ui.label(f"Solution: {solution}").classes("text-sm") \
                    .style(f"color: {t['text_secondary']};")

        # Expandable traceback
        with ui.expansion("Technical details", icon="code").classes("w-full max-w-2xl mt-2") \
                .style(f"color: {t['text_muted']};"):
            ui.label(str(exc)).classes("text-xs mb-2") \
                .style(f"color: {t['error']};")
            ui.code(short_tb).classes("w-full text-xs") \
                .style(f"background: {t['bg_card']}; border: 1px solid {t['border']}; "
                       f"border-radius: 8px; max-height: 300px; overflow: auto;")

        with ui.row().classes("gap-3 mt-4"):
            ui.button("Reload Page", icon="refresh",
                      on_click=lambda: ui.navigate.to(ui.context.client.page.path)) \
                .props("flat") \
                .style(f"color: {t['accent']};")
            ui.button("Go to Home", icon="home",
                      on_click=lambda: ui.navigate.to("/")) \
                .props("flat") \
                .style(f"color: {t['text_secondary']};")


def _diagnose(exc: Exception) -> tuple[str, str]:
    """Map common exceptions to user-friendly cause + solution."""
    exc_type = type(exc).__name__
    msg = str(exc).lower()

    if "no such file" in msg or "filenotfounderror" in exc_type.lower():
        return (
            "A required file was not found on disk.",
            "Verify the XML/workbook path is correct and the file hasn't been moved.",
        )
    if "permission" in msg:
        return (
            "The app doesn't have permission to read or write a file.",
            "Close any other program using the file, or check folder permissions.",
        )
    if "xml" in msg and ("parse" in msg or "syntax" in msg):
        return (
            "The XML file has invalid syntax or is not a valid e-file return.",
            "Confirm you're loading an IRS MeF XML file (not a workbook or PDF).",
        )
    if "key" in exc_type.lower() or "keyerror" in exc_type.lower():
        return (
            "Expected data was missing from the report structure.",
            "Try reloading the data or running a fresh review.",
        )
    if "attribute" in exc_type.lower():
        return (
            "The report data doesn't have the expected format.",
            "This may indicate a version mismatch. Reload the page and retry.",
        )
    if "timeout" in msg or "timed out" in msg:
        return (
            "The operation took too long and was cancelled.",
            "Try with fewer entities or a smaller file. Close other heavy applications.",
        )
    if "memory" in msg:
        return (
            "The system ran out of available memory.",
            "Close other applications and try again with a smaller dataset.",
        )

    return (
        f"An unexpected {exc_type} occurred.",
        "Reload the page. If the error persists, try restarting the application.",
    )


# ─── FILTERABLE TABLE ─────────────────────────────────────────────────────

class TableFilterStrip:
    """Compact Excel-like filter strip rendered above a ui.table.

    Usage:
        rows = [...]
        strip = TableFilterStrip(
            filterable_columns={"country": "Country", "status": "Status"},
            all_rows=rows,
        )
        strip.render(theme)   # renders the filter chips row
        table = ui.table(columns=cols, rows=strip.filtered_rows, ...)
        strip.bind(table)     # wires filter changes to table.rows update
    """

    def __init__(self, filterable_columns: dict[str, str], all_rows: list[dict],
                 on_change=None):
        """
        Args:
            filterable_columns: {field_name: display_label} for columns with filters
            all_rows: full unfiltered row list (dicts)
            on_change: optional callback(filtered_rows) called after filter changes
        """
        self._columns = filterable_columns
        self._all_rows = all_rows
        self._active_filters: dict[str, str | None] = {k: None for k in filterable_columns}
        self._table = None
        self._on_change = on_change
        self._count_label = None
        self._selects: dict[str, ui.select] = {}

    @property
    def filtered_rows(self) -> list[dict]:
        rows = self._all_rows
        for col, val in self._active_filters.items():
            if val and val != "All":
                rows = [r for r in rows if r.get(col) == val]
        return rows

    @property
    def has_active_filters(self) -> bool:
        return any(v and v != "All" for v in self._active_filters.values())

    def render(self, t: dict):
        """Render the compact filter strip. Call BEFORE creating the table."""
        options_per_col = {}
        for col in self._columns:
            vals = sorted({str(r.get(col, "")) for r in self._all_rows
                          if r.get(col) and r.get(col) != "—"})
            options_per_col[col] = ["All"] + vals

        with ui.row().classes("items-center gap-2 w-full flex-wrap mb-2") \
                .style("min-height: 32px;"):
            ui.icon("filter_list").classes("text-sm") \
                .style(f"color: {t['text_muted']}; font-size: 0.85rem;")

            for col, label in self._columns.items():
                sel = ui.select(
                    options=options_per_col.get(col, ["All"]),
                    value="All",
                    label=label,
                    on_change=lambda e, c=col: self._apply(c, e.value),
                ).classes("w-28").props("dense outlined options-dense") \
                    .style("font-size: 0.65rem;")
                self._selects[col] = sel

            self._count_label = ui.label("").classes("text-xs ml-auto") \
                .style(f"color: {t['text_muted']};")
            self._update_count_label()

            if self.has_active_filters:
                ui.button(icon="filter_list_off",
                          on_click=self._clear_all) \
                    .props("flat dense round size=xs") \
                    .tooltip("Clear all filters")

    def render_inline(self, t: dict):
        """Render filters inline (no wrapper row, no icon). For embedding in existing rows."""
        options_per_col = {}
        for col in self._columns:
            vals = sorted({str(r.get(col, "")) for r in self._all_rows
                          if r.get(col) and r.get(col) != "—"})
            options_per_col[col] = ["All"] + vals

        for col, label in self._columns.items():
            sel = ui.select(
                options=options_per_col.get(col, ["All"]),
                value="All",
                label=label,
                on_change=lambda e, c=col: self._apply(c, e.value),
            ).classes("w-24").props("dense outlined options-dense") \
                .style("font-size: 0.6rem;")
            self._selects[col] = sel

        self._count_label = ui.label("").classes("text-xs") \
            .style(f"color: {t['text_muted']};")
        self._update_count_label()

    def bind(self, table):
        """Bind this filter strip to a table so changes update rows."""
        self._table = table

    def _apply(self, col: str, value):
        self._active_filters[col] = value if value != "All" else None
        self._push_update()

    def _clear_all(self):
        for col in self._active_filters:
            self._active_filters[col] = None
            if col in self._selects:
                self._selects[col].value = "All"
        self._push_update()

    def _push_update(self):
        rows = self.filtered_rows
        if self._table:
            self._table.rows = rows
            self._table.update()
        self._update_count_label()
        if self._on_change:
            self._on_change(rows)

    def _update_count_label(self):
        if self._count_label:
            filtered = self.filtered_rows
            total = len(self._all_rows)
            if len(filtered) < total:
                self._count_label.text = f"{len(filtered)} of {total}"
            else:
                self._count_label.text = ""

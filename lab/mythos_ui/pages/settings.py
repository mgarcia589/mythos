"""Settings page — Appearance, review defaults, keyboard shortcuts, and About."""

from nicegui import app, ui

from lab.mythos_ui import __version__
from lab.mythos_ui.theme import get_theme, get_mode, toggle_theme
from lab.mythos_ui.layout import LOGO_SVG


def render():
    t = get_theme()
    mode = get_mode()

    with ui.column().classes("w-full gap-5 max-w-4xl mx-auto animate-fade-up"):
        ui.label("Settings").classes("text-2xl font-bold") \
            .style(f"color: {t['text_primary']};")

        # ── Appearance ──
        with ui.card().classes("w-full glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 20px;"
        ):
            ui.label("Appearance").classes("mythos-label mb-3")

            with ui.row().classes("items-center gap-4"):
                ui.label("Theme").classes("text-sm") \
                    .style(f"color: {t['text_secondary']}; min-width: 80px;")

                with ui.button_group().props("flat"):
                    dark_style = (
                        f"background: {t['nav_active_bg']}; color: {t['accent']}; font-weight: 600;"
                        if mode == "dark" else
                        f"color: {t['text_muted']};"
                    )
                    light_style = (
                        f"background: {t['nav_active_bg']}; color: {t['accent']}; font-weight: 600;"
                        if mode == "light" else
                        f"color: {t['text_muted']};"
                    )
                    ui.button("Dark", icon="dark_mode",
                              on_click=lambda: _set_theme("dark")) \
                        .props("flat no-caps size=sm").style(dark_style)
                    ui.button("Light", icon="light_mode",
                              on_click=lambda: _set_theme("light")) \
                        .props("flat no-caps size=sm").style(light_style)

            with ui.row().classes("items-center gap-4 mt-3"):
                ui.label("Sidebar").classes("text-sm") \
                    .style(f"color: {t['text_secondary']}; min-width: 80px;")
                collapsed = app.storage.browser.get("sidebar_collapsed", False)
                ui.switch("Collapsed by default", value=collapsed,
                          on_change=lambda e: _set_sidebar(e.value)) \
                    .style(f"color: {t['text_secondary']};")

        # ── Review Defaults ──
        with ui.card().classes("w-full glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 20px;"
        ):
            ui.label("Review Defaults").classes("mythos-label mb-3")

            with ui.row().classes("items-center gap-4"):
                ui.label("Default mode").classes("text-sm") \
                    .style(f"color: {t['text_secondary']}; min-width: 120px;")
                ui.select(
                    options=["Full Review", "Parse Only", "Rollover Only"],
                    value=app.storage.user.get("default_mode", "Full Review"),
                    on_change=lambda e: _set_pref("default_mode", e.value),
                ).classes("w-48").props("dense outlined")

            with ui.row().classes("items-center gap-4 mt-3"):
                ui.label("Tolerance ($)").classes("text-sm") \
                    .style(f"color: {t['text_secondary']}; min-width: 120px;")
                ui.number(
                    value=app.storage.user.get("tolerance", 1),
                    min=0, max=1000, step=1,
                    on_change=lambda e: _set_pref("tolerance", e.value),
                ).classes("w-32").props("dense outlined")

            with ui.row().classes("items-center gap-4 mt-3"):
                ui.label("Auto-export").classes("text-sm") \
                    .style(f"color: {t['text_secondary']}; min-width: 120px;")
                ui.switch("Generate XLSX after each review",
                          value=app.storage.user.get("auto_export", False),
                          on_change=lambda e: _set_pref("auto_export", e.value)) \
                    .style(f"color: {t['text_secondary']};")

        # ── Keyboard Shortcuts ──
        with ui.card().classes("w-full glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 20px;"
        ):
            ui.label("Keyboard Shortcuts").classes("mythos-label mb-3")

            with ui.row().classes("w-full gap-8"):
                with ui.column().classes("flex-1 gap-1"):
                    ui.label("Navigation").classes("text-xs font-semibold mb-1") \
                        .style(f"color: {t['text_secondary']};")
                    _shortcut(t, "Ctrl+1", "Home")
                    _shortcut(t, "Ctrl+2", "Review")
                    _shortcut(t, "Ctrl+3", "PDF Check")
                    _shortcut(t, "Ctrl+4", "Reconcile")
                    _shortcut(t, "Ctrl+5", "History")
                    _shortcut(t, "Ctrl+6", "Settings")
                with ui.column().classes("flex-1 gap-1"):
                    ui.label("Actions").classes("text-xs font-semibold mb-1") \
                        .style(f"color: {t['text_secondary']};")
                    _shortcut(t, "Ctrl+N", "New Review")
                    _shortcut(t, "Ctrl+E", "Export XLSX")
                    _shortcut(t, "Ctrl+D", "Toggle theme")
                    _shortcut(t, "Ctrl+R", "Re-run review")

        # ── About ──
        with ui.card().classes("w-full glass-card").style(
            f"background: {t['bg_card']}; border: 1px solid {t['border']}40; "
            f"border-radius: 10px; padding: 20px;"
        ):
            ui.label("About").classes("mythos-label mb-3")

            with ui.row().classes("items-center gap-3"):
                ui.html(LOGO_SVG.replace('width="16"', 'width="28"')
                        .replace('height="18"', 'height="32"')) \
                    .style(f"color: {t['accent']};")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label("Mythos").classes("text-lg font-bold") \
                            .style(f"color: {t['text_primary']};")
                        ui.badge(f"v{__version__}").props("outline dense") \
                            .style(f"color: {t['accent']}; border-color: {t['accent']}50; "
                                   f"font-size: 0.6rem;")
                    ui.label("Automated Compliance Engine for IRS e-file XML") \
                        .classes("text-xs") \
                        .style(f"color: {t['text_muted']};")

            ui.separator().classes("my-3").style(f"background: {t['border']}30;")

            with ui.row().classes("gap-6"):
                _about_stat(t, "71", "Checks")
                _about_stat(t, "103", "Fields")
                _about_stat(t, "< 3s", "Per entity")
                _about_stat(t, "4", "Export formats")

            ui.separator().classes("my-3").style(f"background: {t['border']}30;")

            ui.label(
                "Mythos · US International Tax Compliance Engine"
            ).classes("text-xs") \
                .style(f"color: {t['text_muted']};")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _shortcut(t: dict, key: str, desc: str):
    with ui.row().classes("items-center gap-2"):
        ui.label(key).classes("text-xs mythos-mono px-1.5 py-0.5 rounded") \
            .style(f"background: {t['bg_main']}; color: {t['text_primary']}; "
                   f"border: 1px solid {t['border']}60; font-size: 0.6rem; "
                   f"min-width: 52px; text-align: center;")
        ui.label(desc).classes("text-xs") \
            .style(f"color: {t['text_secondary']}; font-size: 0.65rem;")


def _about_stat(t: dict, value: str, label: str):
    with ui.column().classes("items-center gap-0"):
        ui.label(value).classes("text-sm font-bold mythos-mono") \
            .style(f"color: {t['accent']};")
        ui.label(label).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


def _set_theme(mode: str):
    app.storage.user["theme_mode"] = mode
    ui.navigate.to(ui.context.client.page.path)


def _set_sidebar(collapsed: bool):
    app.storage.browser["sidebar_collapsed"] = collapsed


def _set_pref(key: str, value):
    app.storage.user[key] = value

"""Keyboard shortcuts — global bindings registered on each page load."""

from nicegui import ui

from lab.mythos_ui.theme import get_theme, toggle_theme


SHORTCUTS = [
    ("1", "ctrl", "Home", "/"),
    ("2", "ctrl", "Review", "/review"),
    ("3", "ctrl", "PDF Check", "/pdf-check"),
    ("4", "ctrl", "Reconcile", "/reconciliation"),
    ("5", "ctrl", "History", "/history"),
    ("6", "ctrl", "Settings", "/settings"),
    ("d", "ctrl", "Toggle dark/light", "_toggle_theme"),
    ("e", "ctrl", "Export XLSX", "_export"),
    ("r", "ctrl", "Re-run review", "_rerun"),
    ("n", "ctrl", "New Review", "/review"),
    ("?", "shift", "Show shortcuts", "_help"),
]


def register_shortcuts():
    ui.keyboard(on_key=_handle_keypress)


def _handle_keypress(e):
    key = e.key
    ctrl = e.modifiers.ctrl if hasattr(e.modifiers, 'ctrl') else False
    shift = e.modifiers.shift if hasattr(e.modifiers, 'shift') else False

    if ctrl:
        if key == "1":
            ui.navigate.to("/")
        elif key == "2":
            ui.navigate.to("/review")
        elif key == "3":
            ui.navigate.to("/pdf-check")
        elif key == "4":
            ui.navigate.to("/reconciliation")
        elif key == "5":
            ui.navigate.to("/history")
        elif key == "6":
            ui.navigate.to("/settings")
        elif key.lower() == "d":
            toggle_theme()
            ui.navigate.to(ui.context.client.page.path)
        elif key.lower() == "e":
            _trigger_export()
        elif key.lower() == "r":
            _trigger_rerun()
        elif key.lower() == "n":
            ui.navigate.to("/review")

    if key == "?" and shift:
        _show_help_dialog()


def _trigger_export():
    import asyncio
    from lab.mythos_ui.services.bridge import run_export

    async def do_export():
        result = await run_export(fmt="excel")
        if result and result.success:
            ui.notify(f"Exported: {result.path.name}", type="positive")
        else:
            ui.notify("Nothing to export — run a review first", type="warning")

    asyncio.ensure_future(do_export())


def _trigger_rerun():
    import asyncio
    from lab.mythos_ui.services.bridge import get_state, run_review
    from lab.mythos_ui.components import ProgressOverlay

    s = get_state()
    if not s.current_xml:
        ui.notify("No XML loaded — upload a file first", type="warning")
        return

    async def do_rerun():
        overlay = ProgressOverlay()
        overlay.show()

        def on_progress(msg, pct):
            overlay.update(msg, pct)

        result = await run_review(s.current_xml, s.prior_xml, on_progress=on_progress)
        overlay.hide()

        if result.success:
            ui.notify(f"Review complete: {result.finding_count} findings", type="positive")
            ui.navigate.to("/")
        else:
            ui.notify(f"Failed: {result.message}", type="negative")

    asyncio.ensure_future(do_rerun())


def _show_help_dialog():
    t = get_theme()

    with ui.dialog() as dialog, ui.card().style(
        f"background: {t['bg_elevated']}; "
        f"border: 1px solid {t['border']}; "
        f"border-radius: 16px; padding: 28px; min-width: 420px;"
    ):
        ui.label("Keyboard Shortcuts").classes("text-lg font-bold mb-4") \
            .style(f"color: {t['text_primary']};")

        ui.label("Navigation").classes("mythos-label mb-2")
        _shortcut_row(t, "Ctrl+1", "Home")
        _shortcut_row(t, "Ctrl+2", "Review")
        _shortcut_row(t, "Ctrl+3", "PDF Check")
        _shortcut_row(t, "Ctrl+4", "Reconcile")
        _shortcut_row(t, "Ctrl+5", "History")
        _shortcut_row(t, "Ctrl+6", "Settings")

        ui.separator().classes("my-3").style(f"background: {t['border']}40;")

        ui.label("Actions").classes("mythos-label mb-2")
        _shortcut_row(t, "Ctrl+N", "New Review")
        _shortcut_row(t, "Ctrl+D", "Toggle dark/light mode")
        _shortcut_row(t, "Ctrl+E", "Export to XLSX")
        _shortcut_row(t, "Ctrl+R", "Re-run review")
        _shortcut_row(t, "Shift+?", "This help dialog")

        ui.separator().classes("my-3").style(f"background: {t['border']}40;")

        with ui.row().classes("w-full justify-end"):
            ui.button("Close", on_click=dialog.close) \
                .props("flat").style(f"color: {t['accent']};")

    dialog.open()


def _shortcut_row(t: dict, key_combo: str, description: str):
    with ui.row().classes("w-full items-center justify-between py-1.5"):
        ui.label(description).classes("text-sm") \
            .style(f"color: {t['text_secondary']};")
        ui.label(key_combo).classes("text-xs font-semibold mythos-mono px-2 py-1 rounded") \
            .style(f"background: {t['bg_card']}; color: {t['text_primary']}; "
                   f"border: 1px solid {t['border']};")

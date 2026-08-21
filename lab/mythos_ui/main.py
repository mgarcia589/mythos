"""Mythos UI — Main entry point.

Launch:
    python lab/mythos_ui/main.py          (native desktop window)
    python lab/mythos_ui/main.py --web     (browser mode, http://localhost:8080)
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from nicegui import app, ui

app.native.window_args["frameless"] = True
app.native.window_args["easy_drag"] = True

_ICON_PATH = str(Path(__file__).parent / "icon.ico")
app.native.start_args["icon"] = _ICON_PATH

from lab.mythos_ui.layout import shell
from lab.mythos_ui.pages import (
    dashboard, entities, entity_detail, findings,
    history, pdf_check, reconciliation, rollover, settings,
)
from lab.mythos_ui.pages import xml_check


# ─── PAGE ROUTES ────────────────────────────────────────────────────────────

@ui.page("/")
def page_home():
    shell(active="home", content=dashboard.render)


@ui.page("/review")
def page_review():
    shell(active="review", content=xml_check.render)


@ui.page("/reconciliation")
def page_reconciliation():
    shell(active="reconciliation", content=reconciliation.render)


@ui.page("/history")
def page_history():
    shell(active="history", content=history.render)


@ui.page("/pdf-check")
def page_pdf_check():
    shell(active="pdf_check", content=pdf_check.render)


@ui.page("/settings")
def page_settings():
    shell(active="settings", content=settings.render)


@ui.page("/entities/{code}")
def page_entity_detail(code: str):
    shell(active="review", content=lambda: entity_detail.render(code))


# ─── LEGACY REDIRECTS (bookmarks/shortcuts from v0.7) ──────────────────────

@ui.page("/xml-check")
def page_xml_check_redirect():
    ui.navigate.to("/review")




@ui.page("/findings")
def page_findings_redirect():
    ui.navigate.to("/review")


@ui.page("/entities")
def page_entities_redirect():
    ui.navigate.to("/review")


@ui.page("/rollover")
def page_rollover_redirect():
    ui.navigate.to("/review")


@ui.page("/about")
def page_about_redirect():
    ui.navigate.to("/settings")


# ─── ENTRY POINT ────────────────────────────────────────────────────────────

def start(native: bool = True):
    start_with_options(native=native, port=8080, show=True)


def start_with_options(native: bool = True, port: int = 8080, show: bool = True):
    ui.run(
        title="Mythos — Compliance Review",
        native=native,
        window_size=(1500, 950),
        reload=False,
        dark=True,
        port=port,
        show=show,
        storage_secret="mythos-ui-session-2026",
    )


if __name__ == "__main__":
    web_mode = "--web" in sys.argv
    port = 8080
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    start_with_options(native=not web_mode, port=port, show=not web_mode)

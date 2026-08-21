"""Upload panel — CY/PY cards (matching PDF Check pattern) + mode + run button."""

import tempfile
from datetime import datetime
from pathlib import Path

from nicegui import ui

from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.services.xml_check_state import PagePhase, FileEntry, ProcessingMode
from lab.mythos_ui.services.parse_service import compute_file_hash, check_duplicate
from lab.mythos_ui.components import notify


def render_upload(t: dict, s, refresh_fn=None):
    """Render the full upload section: CY card + PY card + mode + Run button."""
    xc = s.xml_check
    has_current = xc.get_current_file() is not None
    has_prior = xc.get_prior_file() is not None

    with ui.column().classes("w-full items-center justify-center py-4 gap-3"):
        # Hero — compact
        ui.icon("code").classes("text-4xl") \
            .style(f"color: {t['accent']}; opacity: 0.7;")

        ui.label("Compliance Review").classes("text-base font-bold") \
            .style(f"color: {t['text_primary']};")

        ui.label(
            "Upload IRS e-file XML returns to parse, review, and compare against prior year."
        ).classes("text-xs text-center max-w-md") \
            .style(f"color: {t['text_secondary']};")

        # Upload cards row
        with ui.row().classes("gap-3 mt-2 items-stretch"):
            _cy_upload_card(t, s, refresh_fn)
            _py_upload_card(t, s, refresh_fn)

        # Run button (visible once CY loaded)
        if has_current:
            run_label = "Run Full Review + Rollover" if has_prior else "Run Full Review"
            with ui.row().classes("gap-3 mt-3 items-center"):
                ui.button(run_label, icon="play_circle",
                          on_click=lambda: _start_processing(refresh_fn)) \
                    .props("unelevated no-caps") \
                    .style(f"background: {t['accent']}; color: #000; font-weight: 600; "
                           f"padding: 10px 28px; border-radius: 6px; font-size: 0.8rem;")

            if has_prior:
                ui.label("Includes rollover comparison (CY vs PY)") \
                    .classes("text-xs mt-1") \
                    .style(f"color: {t['success']}; opacity: 0.8;")

        # Info strip
        ui.separator().classes("w-40 my-3").style(f"background: {t['border']}30;")
        with ui.row().classes("gap-5"):
            _value_prop(t, "grid_on", "Parse", "Forms · Schedules · Entities")
            _value_prop(t, "verified", "32 checks", "Compliance review")
            _value_prop(t, "swap_vert", "Rollover", "CY vs PY comparison")


def _cy_upload_card(t: dict, s, refresh_fn):
    """Current Year upload card."""
    xc = s.xml_check
    current = xc.get_current_file()
    has_file = current is not None

    border_color = t['success'] if has_file else t['border']

    with ui.card().style(
        f"background: {t['bg_card']}; border: 1px solid {border_color}60; "
        f"border-radius: 8px; padding: 14px 16px; width: 250px; "
        f"box-shadow: {t['shadow']};"
    ):
        with ui.column().classes("w-full").style("height: 160px; display: flex; flex-direction: column;"):
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.icon("description").style(f"color: {t['success']}; font-size: 0.9rem;")
                ui.label("Current Year XML").classes("text-xs font-semibold") \
                    .style(f"color: {t['text_primary']};")
                ui.badge("Required", color="transparent").props("dense") \
                    .style(f"color: {t['error']}; border: 1px solid {t['error']}40; "
                           f"font-size: 0.5rem; padding: 1px 5px;")

            ui.label("IRS e-file XML for the current tax year.") \
                .classes("text-xs") \
                .style(f"color: {t['text_muted']};")

            # Spacer pushes upload to bottom
            ui.element("div").style("flex: 1;")

            upload = ui.upload(
                label="Drop .xml file here",
                auto_upload=True,
                on_upload=lambda e: _handle_upload(e, "current", refresh_fn),
            ).classes("mythos-upload w-full").props("accept=.xml dense flat")
            upload.style(
                f"background: {t['bg_main']}; "
                f"border: 1.5px dashed {t['success'] if has_file else t['border']}; "
                f"border-radius: 6px; min-height: 56px;"
            )

        if has_file:
            with ui.row().classes("items-center gap-1 mt-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.75rem;")
                ui.label(current.filename).classes("text-xs") \
                    .style(f"color: {t['success']};")
                ui.label(f"({_format_size(current.size_bytes)})").classes("text-xs") \
                    .style(f"color: {t['text_muted']}; font-size: 0.5rem;")


def _py_upload_card(t: dict, s, refresh_fn):
    """Prior Year upload card."""
    xc = s.xml_check
    prior = xc.get_prior_file()
    has_file = prior is not None

    border_color = t['success'] if has_file else t['border']

    with ui.card().style(
        f"background: {t['bg_card']}; border: 1px solid {border_color}40; "
        f"border-radius: 8px; padding: 14px 16px; width: 250px; "
        f"box-shadow: {t['shadow']};"
    ):
        with ui.column().classes("w-full").style("height: 160px; display: flex; flex-direction: column;"):
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.icon("history").style(f"color: {t['info']}; font-size: 0.9rem;")
                ui.label("Prior Year XML").classes("text-xs font-semibold") \
                    .style(f"color: {t['text_primary']};")
                ui.badge("Optional", color="transparent").props("dense") \
                    .style(f"color: {t['text_muted']}; border: 1px solid {t['border']}60; "
                           f"font-size: 0.5rem; padding: 1px 5px;")

            ui.label("For rollover comparison (CY vs PY).") \
                .classes("text-xs") \
                .style(f"color: {t['text_muted']};")

            # Spacer pushes upload to bottom
            ui.element("div").style("flex: 1;")

            upload = ui.upload(
                label="Drop .xml file here",
                auto_upload=True,
                on_upload=lambda e: _handle_upload(e, "prior", refresh_fn),
            ).classes("mythos-upload w-full").props("accept=.xml dense flat")
            upload.style(
                f"background: {t['bg_main']}; "
                f"border: 1.5px dashed {t['success'] if has_file else t['border']}; "
                f"border-radius: 6px; min-height: 56px;"
            )

        if has_file:
            with ui.row().classes("items-center gap-1 mt-2"):
                ui.icon("check_circle").style(f"color: {t['success']}; font-size: 0.75rem;")
                ui.label(prior.filename).classes("text-xs") \
                    .style(f"color: {t['success']};")
                ui.label(f"({_format_size(prior.size_bytes)})").classes("text-xs") \
                    .style(f"color: {t['text_muted']}; font-size: 0.5rem;")


def _value_prop(t: dict, icon: str, title: str, subtitle: str):
    with ui.column().classes("items-center gap-0"):
        ui.icon(icon).classes("text-base") \
            .style(f"color: {t['accent']}; opacity: 0.7;")
        ui.label(title).classes("text-xs font-semibold") \
            .style(f"color: {t['text_primary']};")
        ui.label(subtitle).classes("text-xs") \
            .style(f"color: {t['text_muted']}; font-size: 0.6rem;")


# ─── HANDLERS ──────────────────────────────────────────────────────────────

async def _handle_upload(e, role: str, refresh_fn):
    """Handle file upload using NiceGUI 3.14 FileUpload API."""
    s = get_state()
    xc = s.xml_check

    try:
        filename = e.file.name
        tmp = Path(tempfile.gettempdir()) / f"mythos_{role}_{filename}"
        await e.file.save(tmp)

        size = tmp.stat().st_size
        if size < 100:
            notify(f"{filename} appears empty", level="error")
            tmp.unlink(missing_ok=True)
            return

        file_hash = compute_file_hash(tmp)
        if check_duplicate(xc.files, file_hash):
            notify(f"File already loaded", level="warning", caption=filename)
            tmp.unlink(missing_ok=True)
            return

        xc.files = [f for f in xc.files if f.role != role]

        entry = FileEntry(
            path=tmp,
            filename=filename,
            role=role,
            size_bytes=size,
            upload_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            file_hash=file_hash,
        )
        xc.files.append(entry)

        if role == "current":
            s.current_xml = tmp
        else:
            s.prior_xml = tmp

        if xc.mode is None:
            xc.mode = ProcessingMode.FULL_REVIEW

        if xc.get_current_file():
            xc.phase = PagePhase.FILES_UPLOADED

        role_label = "Current Year" if role == "current" else "Prior Year"
        notify(f"{role_label} loaded", level="success", caption=filename)

    except Exception as ex:
        notify(f"Upload failed: {ex}", level="error")
        return

    if refresh_fn:
        refresh_fn()


async def _start_processing(refresh_fn):
    """Begin processing — always Full Review, rollover added if PY is present."""
    from lab.mythos_ui.pages.xml_check.processing_panel import _run_full_review

    s = get_state()
    xc = s.xml_check

    xc.mode = ProcessingMode.FULL_REVIEW

    current_file = xc.get_current_file()
    if not current_file:
        notify("Upload a Current Year XML first", level="warning")
        return

    xc.phase = PagePhase.PROCESSING
    xc.progress = 0.0
    xc.progress_msg = "Starting..."
    if refresh_fn:
        refresh_fn()

    try:
        await _run_full_review(s, current_file, refresh_fn)
    except Exception as ex:
        xc.phase = PagePhase.FAILED
        xc.error_message = str(ex)

    if refresh_fn:
        refresh_fn()


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

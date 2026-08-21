"""Mythos Layout Shell — Header, sidebar navigation, content area, footer."""

from typing import Callable

from nicegui import ui

from lab.mythos_ui.theme import get_theme, get_mode, toggle_theme, inject_css
from lab.mythos_ui.services.bridge import get_state
from lab.mythos_ui.shortcuts import register_shortcuts
from lab.mythos_ui.components import error_boundary


# ─── SVG LOGO ───────────────────────────────────────────────────────────────

LOGO_SVG = """<svg width="16" height="18" viewBox="0 0 28 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M14 0.5L27 8.25V23.75L14 31.5L1 23.75V8.25L14 0.5Z" stroke="currentColor" stroke-width="1.8" fill="none"/>
  <path d="M7.5 22V10L14 17L20.5 10V22" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""

# ─── WINDOWS 11 WINDOW CONTROL SVGs ────────────────────────────────────────
# Exact reproductions of Segoe Fluent Icons used in Windows 11 chrome buttons.
# ViewBox 10x10, stroke-width 1px, matching the native 10px icon @ 46x32 hit area.

_SVG_MINIMIZE = (
    '<svg width="10" height="10" viewBox="0 0 10 10" fill="none">'
    '<line x1="0" y1="5" x2="10" y2="5" stroke="currentColor" stroke-width="1"/>'
    '</svg>'
)

_SVG_MAXIMIZE = (
    '<svg width="10" height="10" viewBox="0 0 10 10" fill="none">'
    '<rect x="0.5" y="0.5" width="9" height="9" stroke="currentColor" stroke-width="1" fill="none" rx="0"/>'
    '</svg>'
)

_SVG_RESTORE = (
    '<svg width="10" height="10" viewBox="0 0 11 11" fill="none">'
    '<rect x="0.5" y="2.5" width="8" height="8" stroke="currentColor" stroke-width="1" fill="none"/>'
    '<polyline points="2.5,2.5 2.5,0.5 10.5,0.5 10.5,8.5 8.5,8.5" stroke="currentColor" stroke-width="1" fill="none"/>'
    '</svg>'
)

_SVG_CLOSE = (
    '<svg width="10" height="10" viewBox="0 0 10 10" fill="none">'
    '<line x1="0.5" y1="0.5" x2="9.5" y2="9.5" stroke="currentColor" stroke-width="1"/>'
    '<line x1="9.5" y1="0.5" x2="0.5" y2="9.5" stroke="currentColor" stroke-width="1"/>'
    '</svg>'
)


# ─── NAV ITEMS ──────────────────────────────────────────────────────────────

NAV_ITEMS = [
    {"key": "home", "label": "Home", "icon": "dashboard", "route": "/", "shortcut": "Ctrl+1"},
    {"key": "review", "label": "XML Review", "icon": "verified", "route": "/review", "shortcut": "Ctrl+2"},
    {"key": "pdf_check", "label": "PDF Check", "icon": "picture_as_pdf", "route": "/pdf-check", "shortcut": "Ctrl+3"},
    {"key": "reconciliation", "label": "Reconcile", "icon": "compare_arrows", "route": "/reconciliation", "shortcut": "Ctrl+4"},
    {"key": "history", "label": "History", "icon": "history", "route": "/history", "shortcut": "Ctrl+5"},
    {"key": "settings", "label": "Settings", "icon": "settings", "route": "/settings", "shortcut": "Ctrl+6"},
]


# ─── SHELL ──────────────────────────────────────────────────────────────────

def shell(active: str, content: Callable):
    """Render the full app shell with sidebar, header, and content area.

    Args:
        active: Key of the currently active nav item.
        content: Callable that renders the page content.
    """
    t = get_theme()
    mode = get_mode()
    inject_css()
    register_shortcuts()

    # ── Header (custom title bar — frameless window) ──
    with ui.header().classes("items-center justify-between py-0 glass-header mythos-titlebar") \
            .style(f"background: {t['glass_bg']}; "
                   f"backdrop-filter: blur(20px) saturate(1.6); "
                   f"border-bottom: 1px solid {t['glass_border']}; "
                   f"box-shadow: none; height: 34px; min-height: 34px; "
                   f"padding-left: 12px; padding-right: 0;"):
        # Drag zone — invisible div that fills the header for pywebview drag
        ui.html('<div class="mythos-drag-zone"></div>')

        with ui.row().classes("items-center gap-2 no-wrap").style("z-index: 2; pointer-events: none;"):
            ui.html(LOGO_SVG).classes("text-amber-500") \
                .style("line-height: 0;")
            ui.label("MYTHOS").style(
                f"color: {t['text_primary']}; font-size: 0.65rem; "
                f"font-weight: 700; letter-spacing: 0.15em;")
            ui.label("·").style(f"color: {t['border']}; font-size: 0.6rem;")
            ui.label("Compliance Review").style(
                f"color: {t['text_muted']}; font-size: 0.6rem;")

        with ui.row().classes("items-center no-wrap").style("z-index: 2; gap: 0px;"):
            # Theme toggle (separate from window controls)
            _icon = "light_mode" if mode == "dark" else "dark_mode"
            _tooltip = "Switch to light mode" if mode == "dark" else "Switch to dark mode"
            ui.button(icon=_icon, on_click=_handle_theme_toggle) \
                .props("flat round size=xs") \
                .style(f"color: {t['text_muted']}; width: 24px; height: 24px; font-size: 0.75rem;") \
                .tooltip(_tooltip)

            # Spacer between theme toggle and window controls
            ui.element("div").style("width: 8px;")

            # Window controls — Windows 11 faithful (46x34px hit area, flush right)
            _wc_style = (
                "border-radius: 0; min-width: 46px; width: 46px; height: 34px; "
                "padding: 0; margin: 0; display: inline-flex; align-items: center; "
                "justify-content: center; cursor: default;"
            )

            # Minimize
            with ui.element("div").classes("mythos-wc-btn") \
                    .style(f"{_wc_style} color: {t['text_secondary']};") \
                    .on("click", _handle_minimize):
                ui.html(_SVG_MINIMIZE)

            # Maximize / Restore (swaps via JS on state change)
            with ui.element("div").classes("mythos-wc-btn mythos-wc-max") \
                    .style(f"{_wc_style} color: {t['text_secondary']};") \
                    .on("click", _handle_maximize):
                ui.html(_SVG_MAXIMIZE).classes("mythos-max-icon")
                ui.html(_SVG_RESTORE).classes("mythos-restore-icon").style("display: none;")

            # Close
            with ui.element("div").classes("mythos-wc-close") \
                    .style(f"{_wc_style} color: {t['text_secondary']};") \
                    .on("click", _handle_close):
                ui.html(_SVG_CLOSE)

    # ── Sidebar (collapsible: 240px ↔ 72px) ──
    from nicegui import app as _app
    collapsed = _app.storage.browser.get("sidebar_collapsed", False)
    drawer_width = 72 if collapsed else 240

    drawer = ui.left_drawer(value=True, fixed=True).classes("glass-sidebar sidebar-drawer") \
        .style(f"background: {t['glass_bg']}; "
               f"backdrop-filter: blur(24px) saturate(1.3); "
               f"border-right: 1px solid {t['glass_border']}; "
               f"transition: width 0.25s cubic-bezier(0.22,1,0.36,1);")
    drawer.props(f"width={drawer_width}")

    with drawer:
        _render_sidebar(active, t, collapsed, drawer)

    # ── Footer (glass) ──
    with ui.footer().classes("py-2 px-6") \
            .style(f"background: {t['glass_bg']}; "
                   f"backdrop-filter: blur(12px); "
                   f"border-top: 1px solid {t['glass_border']};"):
        ui.label("Mythos · US International Tax Compliance Engine") \
            .classes("text-xs w-full text-center") \
            .style(f"color: {t['text_muted']};")

    # ── Main content area ──
    with ui.column().classes("w-full p-6 gap-4 page-enter mythos-content"):
        error_boundary(content)()


# ─── SIDEBAR CONTENTS ───────────────────────────────────────────────────────

def _render_sidebar(active: str, t: dict, collapsed: bool, drawer):
    """Render sidebar — full or icons-only depending on collapsed state."""
    from nicegui import app as _app
    s = get_state()
    badges = _compute_badges(s)

    padding = "p-2" if collapsed else "p-4"
    drawer.classes(replace=f"glass-sidebar sidebar-drawer {padding}")

    # ── Toggle button (top) ──
    toggle_icon = "chevron_right" if collapsed else "chevron_left"
    ui.button(icon=toggle_icon, on_click=lambda: _toggle_sidebar(drawer)) \
        .props("flat round size=sm") \
        .style(f"color: {t['text_muted']}; align-self: {'center' if collapsed else 'flex-end'};") \
        .tooltip("Expand" if collapsed else "Collapse")

    if not collapsed:
        # ── Session Badge (auto-refreshing) ──
        _render_session_badge()
        _setup_badge_auto_refresh()
        ui.separator().classes("my-3").style(f"background: {t['border']}40;")

    # ── Navigation ──
    if not collapsed:
        ui.label("Navigation").classes("mythos-label mb-2")

    for item in NAV_ITEMS:
        is_active = item["key"] == active
        badge_val = badges.get(item["key"])

        if collapsed:
            # Icon-only mode with tooltip
            btn_style = (
                f"color: {t['accent']}; background: {t['nav_active_bg']};"
                if is_active else f"color: {t['text_muted']};"
            )
            with ui.column().classes("items-center w-full my-1"):
                btn = ui.button(icon=item["icon"],
                                on_click=lambda _, r=item["route"]: ui.navigate.to(r)) \
                    .props("flat round size=md") \
                    .style(btn_style) \
                    .tooltip(item["label"])
                if badge_val is not None:
                    badge_color = "red" if item["key"] == "findings" and badges.get("_has_critical") else "grey-7"
                    ui.badge(str(badge_val), color=badge_color).props("dense floating") \
                        .style("font-size: 0.55rem; position: absolute; top: 2px; right: 2px;")
        else:
            # Full expanded mode
            classes = "nav-item active" if is_active else "nav-item"
            with ui.row().classes(f"items-center gap-3 w-full {classes}") \
                    .on("click", lambda _, r=item["route"]: ui.navigate.to(r)):
                ui.icon(item["icon"]).classes("text-lg") \
                    .style(f"color: {t['accent'] if is_active else t['text_muted']};")
                ui.label(item["label"]).classes("text-sm flex-1") \
                    .style(f"color: {t['text_primary'] if is_active else t['text_secondary']};")
                if badge_val is not None:
                    badge_color = "red" if item["key"] == "findings" and badges.get("_has_critical") else "grey-7"
                    ui.badge(str(badge_val), color=badge_color).props("dense floating") \
                        .style("font-size: 0.6rem; min-width: 18px;")
                elif item.get("shortcut"):
                    ui.label(item["shortcut"]).classes("text-xs mythos-mono") \
                        .style(f"color: {t['text_muted']}; opacity: 0.5; font-size: 0.55rem;")

    # ── Quick Actions ──
    if not collapsed:
        ui.separator().classes("my-4").style(f"background: {t['border']};")
        ui.button("New Review", icon="play_circle",
                  on_click=lambda: ui.navigate.to("/review")) \
            .classes("w-full") \
            .props("unelevated no-caps") \
            .style(f"background: {t['accent']}; color: #000; font-weight: 500; "
                   f"border-radius: 6px; font-size: 0.8rem;")

        ui.button("Export XLSX", icon="download", on_click=_handle_export) \
            .classes("w-full mt-2") \
            .props("flat dense no-caps") \
            .style(f"color: {t['text_secondary']}; font-size: 0.75rem;")
    else:
        ui.separator().classes("my-3").style(f"background: {t['border']}40;")
        ui.button(icon="play_circle",
                  on_click=lambda: ui.navigate.to("/review")) \
            .props("flat round size=md") \
            .style(f"color: {t['accent']};") \
            .tooltip("New Review")
        ui.button(icon="download", on_click=_handle_export) \
            .props("flat round size=md") \
            .style(f"color: {t['text_muted']};") \
            .tooltip("Export XLSX")


def _toggle_sidebar(drawer):
    """Toggle sidebar collapsed state and reload page."""
    from nicegui import app as _app
    current = _app.storage.browser.get("sidebar_collapsed", False)
    _app.storage.browser["sidebar_collapsed"] = not current
    ui.run_javascript("window.location.reload()")


# ─── SESSION BADGE ─────────────────────────────────────────────────────────

@ui.refreshable
def _render_session_badge():
    """Session card — tight summary of the active review."""
    t = get_theme()
    s = get_state()
    if s.report:
        client = s.report.client_name or "Unknown"
        year = s.report.tax_year
        if not year and s.xml_check and s.xml_check.parse_summary:
            year = s.xml_check.parse_summary.tax_year
        year = year or ""
        entities = s.report.entity_count
        findings = s.report.summary.get("total_findings", 0)
        high = s.report.summary.get("by_severity", {}).get("HIGH", 0)
        medium = s.report.summary.get("by_severity", {}).get("MEDIUM", 0)
        low = s.report.summary.get("by_severity", {}).get("LOW", 0)

        # Count entities per form type from schedule_inventory
        cnt_5471 = 0
        cnt_8858 = 0
        if s.xml_check and s.xml_check.parse_summary:
            for node in s.xml_check.parse_summary.schedule_inventory:
                if node.form_type == "5471":
                    cnt_5471 = node.entity_count
                elif node.form_type == "8858":
                    cnt_8858 = node.entity_count

        border_color = t["sev_high"] if high > 0 else t["success"]

        with ui.element("div").style(
            f"background: {t['bg_elevated']}; "
            f"border: 1px solid {border_color}40; "
            f"border-left: 3px solid {border_color}; "
            f"border-radius: 8px; padding: 8px 10px; "
            f"display: flex; flex-direction: column; gap: 1px;"
        ):
            # Client name
            ui.label(client).style(
                f"color: {t['text_primary']}; font-size: 0.7rem; font-weight: 700; "
                f"line-height: 1.2; word-break: break-word;")

            # FY badge (accent color, stands out)
            if year:
                ui.label(f"FY{year}").style(
                    f"color: {t['accent']}; font-size: 0.65rem; font-weight: 700;")

            # Entity breakdown by form type
            if cnt_5471 or cnt_8858:
                with ui.element("div").style("display: flex; flex-direction: column;"):
                    if cnt_5471:
                        ui.html(
                            f'<span style="color:{t["text_primary"]};font-weight:700;'
                            f'font-family:JetBrains Mono,monospace;font-size:0.6rem">{cnt_5471}</span>'
                            f'<span style="color:{t["text_muted"]};font-size:0.55rem"> · 5471</span>'
                        )
                    if cnt_8858:
                        ui.html(
                            f'<span style="color:{t["text_primary"]};font-weight:700;'
                            f'font-family:JetBrains Mono,monospace;font-size:0.6rem">{cnt_8858}</span>'
                            f'<span style="color:{t["text_muted"]};font-size:0.55rem"> · 8858</span>'
                        )
            else:
                ui.label(f"{entities} entities").style(
                    f"color: {t['text_muted']}; font-size: 0.55rem; "
                    f"font-family: 'JetBrains Mono', monospace;")

            # Separator + Findings
            ui.element("div").style(
                f"height: 1px; background: {t['border']}40; margin: 3px 0;")
            ui.html(
                f'<span style="color:{t["text_primary"]};font-size:0.75rem;font-weight:700;'
                f'font-family:JetBrains Mono,monospace">{findings}</span> '
                f'<span style="color:{t["text_muted"]};font-size:0.55rem">findings</span>'
                + (f' <span style="color:{t["sev_high"]};font-size:0.55rem;font-weight:600">'
                   f'({high} critical)</span>' if high > 0 else '')
            )

            # Severity bar
            if findings > 0:
                with ui.element("div").style(
                    "display:flex; width:100%; height:3px; border-radius:2px; "
                    "overflow:hidden; gap:1px; margin-top:2px;"
                ):
                    if high > 0:
                        ui.element("div").style(
                            f"flex:{high}; background:{t['sev_high']}; height:100%;")
                    if medium > 0:
                        ui.element("div").style(
                            f"flex:{medium}; background:{t['sev_medium']}; height:100%;")
                    if low > 0:
                        ui.element("div").style(
                            f"flex:{low}; background:{t['sev_low']}; height:100%;")

    elif s.current_xml:
        with ui.element("div").style(
            f"background: {t['bg_elevated']}; "
            f"border: 1px solid {t['accent']}40; "
            f"border-left: 3px solid {t['accent']}; "
            f"border-radius: 8px; padding: 8px 10px;"
        ):
            ui.label("XML Loaded").style(
                f"color: {t['accent']}; font-size: 0.65rem; font-weight: 700;")
            ui.label(s.current_xml.name).style(
                f"color: {t['text_secondary']}; font-size: 0.6rem; margin-top: 2px; "
                f"word-break: break-all; line-height: 1.3;")
            if s.prior_xml:
                ui.label(f"+ {s.prior_xml.name}").style(
                    f"color: {t['text_muted']}; font-size: 0.55rem; margin-top: 1px; "
                    f"word-break: break-all;")

    else:
        with ui.element("div").style(
            f"background: {t['bg_elevated']}; border: 1px solid {t['border']}40; "
            f"border-radius: 8px; padding: 8px 10px;"
        ):
            ui.label("No active session").style(
                f"color: {t['text_muted']}; font-size: 0.65rem;")
            ui.label("Upload XML to begin").style(
                f"color: {t['text_muted']}; font-size: 0.55rem; opacity: 0.6; margin-top: 1px;")


def refresh_session_badge():
    """Public API — call after state changes to update the sidebar session card."""
    _render_session_badge.refresh()


_badge_fingerprint = {"value": ""}


def _get_badge_fingerprint() -> str:
    """Compute a lightweight fingerprint of the session state."""
    s = get_state()
    if s.report:
        total = s.report.summary.get("total_findings", 0)
        return f"report:{s.report.client_name}:{s.report.tax_year}:{s.report.entity_count}:{total}"
    if s.xml_check and s.xml_check.parse_summary:
        ps = s.xml_check.parse_summary
        return f"parsed:{ps.client_name}:{ps.tax_year}:{ps.entity_count}"
    if s.current_xml:
        return f"xml:{s.current_xml.name}"
    return "empty"


def _setup_badge_auto_refresh():
    """Timer that auto-refreshes the session badge when state changes."""
    def _check():
        fp = _get_badge_fingerprint()
        if fp != _badge_fingerprint["value"]:
            _badge_fingerprint["value"] = fp
            _render_session_badge.refresh()

    ui.timer(1.0, _check)


# ─── BADGE COMPUTATION ─────────────────────────────────────────────────────

def _compute_badges(s) -> dict:
    """Compute badge counts for sidebar nav items."""
    if not s.report:
        return {}

    summary = s.report.summary
    total_findings = summary["total_findings"]
    entities_with_issues = summary["entities_with_findings"]
    has_critical = summary["by_severity"]["HIGH"] > 0

    badges = {"_has_critical": has_critical}

    if total_findings > 0:
        badges["findings"] = total_findings
    if entities_with_issues > 0:
        badges["entities"] = entities_with_issues

    return badges


# ─── WINDOW CONTROLS ───────────────────────────────────────────────────────

_is_maximized = False


async def _handle_minimize():
    """Minimize the native window."""
    from nicegui import app
    try:
        app.native.main_window.minimize()
    except Exception:
        pass


async def _handle_maximize():
    """Toggle maximize/restore (pywebview 6.x) and swap icon."""
    global _is_maximized
    from nicegui import app
    try:
        window = app.native.main_window
        if _is_maximized:
            window.restore()
            _is_maximized = False
        else:
            window.maximize()
            _is_maximized = True
    except Exception:
        try:
            app.native.main_window.toggle_fullscreen()
            _is_maximized = not _is_maximized
        except Exception:
            pass

    # Swap SVG icons to reflect current state
    if _is_maximized:
        await ui.run_javascript(
            "document.querySelector('.mythos-max-icon').style.display='none';"
            "document.querySelector('.mythos-restore-icon').style.display='';"
        )
    else:
        await ui.run_javascript(
            "document.querySelector('.mythos-max-icon').style.display='';"
            "document.querySelector('.mythos-restore-icon').style.display='none';"
        )


async def _handle_close():
    """Close the application."""
    from nicegui import app
    try:
        app.native.main_window.destroy()
    except Exception:
        try:
            app.shutdown()
        except Exception:
            pass


# ─── EVENT HANDLERS ─────────────────────────────────────────────────────────

def _handle_theme_toggle():
    """Toggle dark/light mode and refresh page."""
    toggle_theme()
    ui.navigate.to(ui.context.client.page.path)




async def _handle_export():
    """Export review to XLSX."""
    from lab.mythos_ui.services.bridge import run_export

    result = await run_export(fmt="excel")
    if result and result.success:
        ui.notify(f"Exported: {result.path.name}", type="positive")
    else:
        ui.notify("Nothing to export — run a review first", type="warning")

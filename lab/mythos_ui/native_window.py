"""Native window enhancements — resize + snap for frameless pywebview.

Adds WS_THICKFRAME to the frameless WinForms window after pywebview creates it.
This gives us native OS resize borders, Aero Snap (Win+Arrow, drag-to-edge),
and Snap Layouts (Windows 11) without any WndProc hooking.
"""

import sys
import ctypes
import logging
import threading
import time

logger = logging.getLogger("mythos.native_window")

# ── Win32 constants ──────────────────────────────────────────────────────────

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004


def _apply_thick_frame(title: str):
    """Find the pywebview window by title and add WS_THICKFRAME."""
    user32 = ctypes.windll.user32

    for _ in range(40):
        time.sleep(0.5)
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER,
            )
            logger.info(f"WS_THICKFRAME applied to HWND {hwnd:#x}")
            return

    logger.warning("Could not find native window — resize disabled")


def setup_native_window(title: str = "Mythos — Compliance Review"):
    """Spawn a background thread that waits for the window and enables resize.

    Call before ui.run(), only in native mode on Windows.
    """
    if sys.platform != "win32":
        return

    t = threading.Thread(target=_apply_thick_frame, args=(title,), daemon=True)
    t.start()

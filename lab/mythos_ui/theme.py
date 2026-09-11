"""Mythos Design System — Token-based dark/light theming with CSS custom properties."""

import plotly.graph_objects as go
from nicegui import app, ui

# ─── TOKEN DICTIONARIES ─────────────────────────────────────────────────────

DARK = {
    # Surfaces (Radix Slate Dark 1-3)
    "bg_main": "#111113",
    "bg_card": "#18191b",
    "bg_elevated": "#212225",
    "bg_sidebar": "#111113",
    # Borders (Radix Slate Dark 6-7)
    "border": "#363a3f",
    "border_hover": "#43484e",
    "border_accent": "rgba(255, 197, 61, 0.25)",
    # Text (Radix Slate Dark 9, 11, 12)
    "text_primary": "#edeef0",
    "text_secondary": "#b0b4ba",
    "text_muted": "#696e77",
    # Accent (Radix Amber Dark 9-11)
    "accent": "#ffc53d",
    "accent_hover": "#ffd60a",
    "accent_subtle": "rgba(255, 197, 61, 0.08)",
    # Semantic (Radix scale 9 — solid)
    "success": "#30a46c",
    "warning": "#ffc53d",
    "error": "#e5484d",
    "info": "#3e63dd",
    # Severity (Radix Red/Amber/Slate + dark bg from scale 3)
    "sev_high": "#e5484d",
    "sev_high_bg": "#3b1219",
    "sev_medium": "#ffc53d",
    "sev_medium_bg": "#302008",
    "sev_low": "#696e77",
    "sev_low_bg": "#212225",
    # Glass / Effects
    "glass_bg": "rgba(255, 255, 255, 0.02)",
    "glass_border": "rgba(255, 255, 255, 0.06)",
    "shadow": "0 4px 24px rgba(0, 0, 0, 0.35)",
    "shadow_strong": "0 8px 32px rgba(0, 0, 0, 0.5)",
    # Scrollbar
    "scrollbar_thumb": "rgba(255, 255, 255, 0.08)",
    # Nav
    "nav_active_bg": "rgba(255, 197, 61, 0.10)",
    "nav_hover_bg": "rgba(255, 255, 255, 0.04)",
}

LIGHT = {
    # Surfaces — warm gray base with clear card/bg separation
    "bg_main": "#eaedf1",
    "bg_card": "#ffffff",
    "bg_elevated": "#f4f5f7",
    "bg_sidebar": "#f2f3f5",
    # Borders — visible but not harsh
    "border": "#d0d3d9",
    "border_hover": "#b8bcc4",
    "border_accent": "rgba(140, 80, 0, 0.30)",
    # Text — high contrast (WCAG AAA on white)
    "text_primary": "#111318",
    "text_secondary": "#3d4149",
    "text_muted": "#6b7280",
    # Accent — darker amber for readability on light backgrounds
    "accent": "#b45309",
    "accent_hover": "#92400e",
    "accent_subtle": "rgba(180, 83, 9, 0.06)",
    # Semantic — darkened for WCAG AA on white
    "success": "#15803d",
    "warning": "#a16207",
    "error": "#dc2626",
    "info": "#2563eb",
    # Severity
    "sev_high": "#b91c1c",
    "sev_high_bg": "#fef2f2",
    "sev_medium": "#a16207",
    "sev_medium_bg": "#fefce8",
    "sev_low": "#6b7280",
    "sev_low_bg": "#f3f4f6",
    # Glass / Effects
    "glass_bg": "rgba(255, 255, 255, 0.92)",
    "glass_border": "rgba(0, 0, 0, 0.10)",
    "shadow": "0 1px 3px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.05)",
    "shadow_strong": "0 4px 12px rgba(0, 0, 0, 0.10), 0 10px 30px rgba(0, 0, 0, 0.08)",
    # Scrollbar
    "scrollbar_thumb": "rgba(0, 0, 0, 0.15)",
    # Nav
    "nav_active_bg": "rgba(180, 83, 9, 0.10)",
    "nav_hover_bg": "rgba(0, 0, 0, 0.05)",
}


# ─── THEME ACCESSORS ────────────────────────────────────────────────────────

def get_mode() -> str:
    """Get current theme mode from session storage."""
    return app.storage.user.get("theme_mode", "dark")


def get_theme() -> dict:
    """Get the active token dict based on current mode."""
    return DARK if get_mode() == "dark" else LIGHT


def toggle_theme():
    """Flip dark↔light and navigate to trigger re-render."""
    current = get_mode()
    app.storage.user["theme_mode"] = "light" if current == "dark" else "dark"


# ─── CSS INJECTION ──────────────────────────────────────────────────────────

def inject_css():
    """Inject CSS custom properties and base styles into the page head."""
    t = get_theme()
    mode = get_mode()

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

    :root {{
        --m-bg-main: {t["bg_main"]};
        --m-bg-card: {t["bg_card"]};
        --m-bg-elevated: {t["bg_elevated"]};
        --m-bg-sidebar: {t["bg_sidebar"]};
        --m-border: {t["border"]};
        --m-border-hover: {t["border_hover"]};
        --m-text-primary: {t["text_primary"]};
        --m-text-secondary: {t["text_secondary"]};
        --m-text-muted: {t["text_muted"]};
        --m-accent: {t["accent"]};
        --m-accent-hover: {t["accent_hover"]};
        --m-success: {t["success"]};
        --m-error: {t["error"]};
        --m-info: {t["info"]};
    }}

    body, .q-page, .q-layout {{
        background: var(--m-bg-main) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--m-text-primary) !important;
    }}

    .q-drawer {{
        background: var(--m-bg-sidebar) !important;
        border-right: 1px solid var(--m-border) !important;
    }}

    .q-header {{
        background: var(--m-bg-card) !important;
        border-bottom: 1px solid var(--m-border) !important;
    }}

    .q-footer {{
        background: var(--m-bg-card) !important;
        border-top: 1px solid var(--m-border) !important;
    }}

    /* Typography */
    .mythos-heading {{
        font-family: 'Inter', sans-serif;
        color: var(--m-text-primary);
        font-weight: 700;
        letter-spacing: -0.01em;
    }}

    .mythos-label {{
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--m-text-muted);
        font-weight: 600;
    }}

    .mythos-mono {{
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-variant-numeric: tabular-nums;
    }}

    /* Cards */
    .mythos-card {{
        background: var(--m-bg-card);
        border: 1px solid var(--m-border);
        border-radius: 16px;
        padding: 24px;
        box-shadow: {t["shadow"]};
        transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
    }}
    .mythos-card:hover {{
        border-color: var(--m-border-hover);
        box-shadow: {t["shadow_strong"]};
    }}

    /* Navigation items */
    .nav-item {{
        border-radius: 10px;
        padding: 10px 16px;
        transition: all 0.15s ease;
        cursor: pointer;
        color: var(--m-text-secondary);
    }}
    .nav-item:hover {{
        background: {t["nav_hover_bg"]};
        color: var(--m-text-primary);
    }}
    .nav-item.active {{
        background: {t["nav_active_bg"]};
        color: var(--m-accent);
        font-weight: 600;
    }}

    /* Severity badges */
    .sev-high {{
        background: {t["sev_high_bg"]};
        color: {t["sev_high"]};
        border: 1px solid {t["sev_high"]}40;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.6rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}
    .sev-medium {{
        background: {t["sev_medium_bg"]};
        color: {t["sev_medium"]};
        border: 1px solid {t["sev_medium"]}40;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.6rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}
    .sev-low {{
        background: {t["sev_low_bg"]};
        color: {t["sev_low"]};
        border: 1px solid {t["sev_low"]}40;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.6rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }}

    /* ─── GLASSMORPHISM ─── */
    .glass-card {{
        background: {t["bg_card"]};
        backdrop-filter: blur(16px) saturate(1.4);
        -webkit-backdrop-filter: blur(16px) saturate(1.4);
        border: 1px solid {t["glass_border"]};
        border-radius: 12px;
        box-shadow: {t["shadow"]};
        transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
    }}
    .glass-card:hover {{
        border-color: {t["border_hover"]};
        box-shadow: {t["shadow_strong"]};
        transform: translateY(-1px);
    }}

    .glass-panel {{
        background: {t["glass_bg"]};
        backdrop-filter: blur(12px) saturate(1.2);
        -webkit-backdrop-filter: blur(12px) saturate(1.2);
        border: 1px solid {t["glass_border"]};
        border-radius: 12px;
        padding: 16px 20px;
    }}

    /* Cards get subtle lift via shadow token + themed bg */
    .q-card {{
        background: {t["bg_card"]} !important;
        color: {t["text_primary"]} !important;
        box-shadow: {t["shadow"]};
        border-radius: 10px;
    }}

    /* Content area text */
    .mythos-content, .mythos-content * {{
        color: inherit;
    }}
    .mythos-content {{
        color: {t["text_primary"]};
    }}

    .glass-header {{
        background: {t["glass_bg"]} !important;
        backdrop-filter: blur(20px) saturate(1.6) !important;
        -webkit-backdrop-filter: blur(20px) saturate(1.6) !important;
    }}

    /* Custom upload zone — override Quasar's default style */
    .mythos-upload {{
        box-shadow: none !important;
    }}
    .mythos-upload .q-uploader__header {{
        background: transparent !important;
        color: {t["text_muted"]} !important;
        font-size: 0.7rem;
        min-height: 44px;
        padding: 6px 10px;
    }}
    .mythos-upload .q-uploader__title {{
        font-size: 0.65rem;
        opacity: 0.8;
    }}
    .mythos-upload .q-uploader__subtitle {{
        display: none;
    }}
    .mythos-upload .q-uploader__list {{
        display: none;
    }}
    .mythos-upload .q-btn {{
        color: {t["text_muted"]} !important;
    }}
    .mythos-upload:hover {{
        border-color: {t["accent"]} !important;
    }}

    /* ─── QUASAR FORM CONTROLS — theme-aware ─── */
    .q-field__label {{
        color: {t["text_muted"]} !important;
    }}
    .q-field__native, .q-field__input {{
        color: {t["text_primary"]} !important;
    }}
    .q-field--outlined .q-field__control {{
        border-color: {t["border"]} !important;
    }}
    .q-field--outlined .q-field__control:hover {{
        border-color: {t["border_hover"]} !important;
    }}
    .q-select__dropdown-icon {{
        color: {t["text_muted"]} !important;
    }}
    .q-menu {{
        background: {t["bg_card"]} !important;
        border: 1px solid {t["border"]} !important;
    }}
    .q-item {{
        color: {t["text_primary"]} !important;
    }}
    .q-item:hover {{
        background: {t["nav_hover_bg"]} !important;
    }}
    .q-badge {{
        font-size: 0.55rem !important;
    }}

    .glass-sidebar {{
        background: {t["glass_bg"]} !important;
        backdrop-filter: blur(24px) saturate(1.3) !important;
        -webkit-backdrop-filter: blur(24px) saturate(1.3) !important;
    }}

    /* ─── HOVER LIFT ─── */
    .hover-lift {{
        transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
    }}
    .hover-lift:hover {{
        transform: translateY(-3px);
        box-shadow: {t["shadow_strong"]};
    }}

    .hover-glow {{
        transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
    }}
    .hover-glow:hover {{
        border-color: {t["accent"]}50;
        box-shadow: 0 0 20px {t["accent"]}15, {t["shadow_strong"]};
    }}

    /* ─── GRADIENT BORDERS ─── */
    .gradient-border {{
        position: relative;
        border: none !important;
    }}
    .gradient-border::before {{
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        padding: 1px;
        background: linear-gradient(135deg, {t["accent"]}40, {t["info"]}30, {t["accent"]}20);
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        pointer-events: none;
    }}

    /* ─── ANIMATIONS ─── */
    @keyframes fade-up {{
        from {{ opacity: 0; transform: translateY(16px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .animate-fade-up {{
        animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        opacity: 0;
    }}

    @keyframes fade-in {{
        from {{ opacity: 0; }}
        to   {{ opacity: 1; }}
    }}
    .animate-fade-in {{
        animation: fade-in 0.4s ease forwards;
        opacity: 0;
    }}

    @keyframes slide-right {{
        from {{ opacity: 0; transform: translateX(-12px); }}
        to   {{ opacity: 1; transform: translateX(0); }}
    }}
    .animate-slide-right {{
        animation: slide-right 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        opacity: 0;
    }}

    @keyframes scale-in {{
        from {{ opacity: 0; transform: scale(0.92); }}
        to   {{ opacity: 1; transform: scale(1); }}
    }}
    .animate-scale-in {{
        animation: scale-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        opacity: 0;
    }}

    /* Staggered delays for child elements */
    .stagger-1 {{ animation-delay: 0.05s; }}
    .stagger-2 {{ animation-delay: 0.10s; }}
    .stagger-3 {{ animation-delay: 0.15s; }}
    .stagger-4 {{ animation-delay: 0.20s; }}
    .stagger-5 {{ animation-delay: 0.25s; }}
    .stagger-6 {{ animation-delay: 0.30s; }}
    .stagger-7 {{ animation-delay: 0.35s; }}
    .stagger-8 {{ animation-delay: 0.40s; }}

    /* ─── PULSE (for critical badges/values) ─── */
    @keyframes pulse-soft {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.7; }}
    }}
    .pulse-critical {{
        animation: pulse-soft 2s ease-in-out infinite;
    }}

    @keyframes glow-pulse {{
        0%, 100% {{ box-shadow: 0 0 4px {t["sev_high"]}30; }}
        50% {{ box-shadow: 0 0 16px {t["sev_high"]}50; }}
    }}
    .glow-critical {{
        animation: glow-pulse 2.5s ease-in-out infinite;
    }}

    /* ─── SHIMMER (loading skeleton) ─── */
    @keyframes shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}
    .shimmer {{
        background: linear-gradient(
            90deg,
            {t["bg_card"]} 25%,
            {t["bg_elevated"]} 50%,
            {t["bg_card"]} 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.8s ease-in-out infinite;
        border-radius: 8px;
    }}

    /* ─── PROGRESS OVERLAY ─── */
    .mythos-overlay {{
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: {t["bg_main"]}ee;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }}

    @keyframes spin-slow {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}
    .spin-slow {{
        animation: spin-slow 3s linear infinite;
    }}

    @keyframes progress-glow {{
        0%, 100% {{ box-shadow: 0 0 6px {t["accent"]}40; }}
        50% {{ box-shadow: 0 0 18px {t["accent"]}70; }}
    }}
    .progress-glow {{
        animation: progress-glow 2s ease-in-out infinite;
    }}

    /* ─── FOCUS RINGS ─── */
    .q-field--outlined .q-field__control:focus-within {{
        border-color: {t["accent"]} !important;
        box-shadow: 0 0 0 3px {t["accent"]}20 !important;
    }}

    /* ─── TABLES — full theme integration ─── */
    .q-table {{
        background: {t["bg_card"]} !important;
        color: {t["text_primary"]} !important;
    }}
    .q-table thead th {{
        color: {t["text_secondary"]} !important;
        font-weight: 600 !important;
        font-size: 0.65rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        background: {t["bg_elevated"]} !important;
        border-bottom: 1px solid {t["border"]} !important;
    }}
    /* Sticky table headers — data scrolls, headers stay fixed */
    .mythos-sticky-table .q-table__middle {{
        max-height: 55vh;
        overflow-y: auto;
    }}
    .mythos-sticky-table thead tr th {{
        position: sticky;
        top: 0;
        z-index: 1;
        background: {t["bg_elevated"]} !important;
    }}
    .q-table tbody td {{
        color: {t["text_primary"]} !important;
        font-size: 0.75rem !important;
        border-bottom: 1px solid {t["border"]}40 !important;
    }}
    .q-table tbody tr {{
        transition: background 0.15s ease;
    }}
    .q-table tbody tr:hover {{
        background: {t["nav_hover_bg"]} !important;
    }}
    .q-table .q-table__bottom {{
        color: {t["text_muted"]} !important;
        border-top: 1px solid {t["border"]}40 !important;
    }}
    .q-table .q-table__bottom .q-table__control {{
        color: {t["text_muted"]} !important;
    }}

    /* ─── SCROLLBAR ─── */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: {t["scrollbar_thumb"]};
        border-radius: 3px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: {t["border"]};
    }}

    /* ─── PROGRESS BAR ─── */
    .q-linear-progress__track {{
        opacity: 0.15;
    }}
    .q-linear-progress__model {{
        transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
    }}

    /* Hide NiceGUI footer link */
    .nicegui-link {{ display: none !important; }}

    /* ─── PAGE TRANSITION ─── */
    .page-enter {{
        animation: fade-up 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        opacity: 0;
    }}

    /* ─── TOAST NOTIFICATIONS ─── */
    .mythos-toast {{
        border-radius: 8px !important;
        backdrop-filter: blur(12px) !important;
        font-family: 'Inter', sans-serif !important;
    }}
    .mythos-toast .q-notification__message {{
        font-size: 0.8rem !important;
        font-weight: 500 !important;
    }}
    .mythos-toast .q-notification__caption {{
        font-size: 0.7rem !important;
        opacity: 0.7 !important;
    }}
    .mythos-toast .q-notification__icon {{
        font-size: 1.2rem !important;
    }}

    /* ─── TOOLTIP STYLE ─── */
    .q-tooltip {{
        background: {t["bg_elevated"]} !important;
        color: {t["text_primary"]} !important;
        border: 1px solid {t["border"]} !important;
        border-radius: 8px !important;
        font-size: 0.75rem !important;
        backdrop-filter: blur(8px);
    }}

    /* ─── TREE ROW HOVER (Schedule Inventory) ─── */
    .mythos-tree-row {{
        border-radius: 6px;
        transition: background 0.15s ease;
    }}
    .mythos-tree-row:hover {{
        background: {t["nav_hover_bg"]};
    }}

    /* ─── GLOBAL BUTTON REFINEMENT ─── */
    .q-btn {{
        text-transform: none;
        border-radius: 6px;
        font-weight: 500;
        letter-spacing: 0.01em;
    }}
    .q-btn:hover {{
        transform: translateY(-0.5px);
        transition: all 0.15s ease;
    }}
    .q-btn:active {{
        transform: translateY(0px) scale(0.99);
    }}

    /* ─── CUSTOM TITLE BAR (frameless window) ─── */
    .mythos-titlebar {{
        position: relative;
        user-select: none;
    }}
    .mythos-drag-zone {{
        position: absolute;
        inset: 0;
        z-index: 1;
        -webkit-app-region: drag;
        cursor: default;
    }}
    .mythos-titlebar .q-btn {{
        -webkit-app-region: no-drag;
        transition: all 0.15s ease;
        border-radius: 4px;
    }}
    .mythos-titlebar .q-btn .q-icon,
    .mythos-titlebar .q-btn .material-icons {{
        font-family: 'Material Symbols Outlined';
        font-weight: 200;
        font-size: 16px;
        font-variation-settings: 'FILL' 0, 'wght' 200, 'GRAD' -25, 'opsz' 20;
    }}
    .mythos-titlebar .q-btn:hover {{
        transform: none;
    }}
    /* Ensure SVG window controls within titlebar don't get button transform */
    .mythos-titlebar .mythos-wc-btn:hover,
    .mythos-titlebar .mythos-wc-close:hover {{
        transform: none !important;
    }}
    /* Windows 11 window control buttons — pixel-accurate */
    .mythos-wc-btn,
    .mythos-wc-close {{
        border-radius: 0 !important;
        transition: background 0.1s ease;
        -webkit-app-region: no-drag;
        user-select: none;
    }}
    .mythos-wc-btn:hover {{
        background: {t["nav_hover_bg"]} !important;
    }}
    .mythos-wc-btn:active {{
        background: {t["border"]}50 !important;
    }}
    .mythos-wc-close:hover {{
        background: #c42b1c !important;
        color: #ffffff !important;
    }}
    .mythos-wc-close:hover svg line {{
        stroke: #ffffff !important;
    }}
    .mythos-wc-close:active {{
        background: #b4271a !important;
        color: #ffffff !important;
    }}
    .mythos-wc-close:active svg line {{
        stroke: #ffffff !important;
    }}
    .mythos-wc-btn svg,
    .mythos-wc-close svg {{
        pointer-events: none;
    }}

    /* Rounded corners for frameless window (native only) */
    body {{
        border-radius: 10px;
    }}

    /* Content scrolls independently; header/footer stay fixed */
    .q-page {{
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }}
    .q-header {{
        position: fixed !important;
        top: 0 !important;
        z-index: 2000 !important;
    }}
    .q-footer {{
        position: fixed !important;
        bottom: 0 !important;
        z-index: 2000 !important;
    }}

    /* ─── RESPONSIVE: 1024px ─── */
    @media (max-width: 1024px) {{
        .q-drawer {{
            width: 200px !important;
        }}
        .q-page-container {{
            padding-left: 200px !important;
        }}
        .q-drawer .mythos-label {{
            font-size: 0.55rem;
        }}
        .mythos-content {{
            padding: 16px !important;
        }}
    }}

    /* ─── RESPONSIVE: 768px ─── */
    @media (max-width: 768px) {{
        .q-drawer {{
            width: 0 !important;
            display: none !important;
        }}
        .q-page-container {{
            padding-left: 0 !important;
        }}
        .q-header .text-sm {{
            font-size: 0.7rem;
        }}
        .mythos-content {{
            padding: 12px !important;
            gap: 12px !important;
        }}
        .q-table {{
            overflow-x: auto !important;
        }}
        .q-table th, .q-table td {{
            white-space: nowrap;
        }}
    }}
    </style>
    """
    ui.add_head_html(css)


# ─── PLOTLY TEMPLATE ────────────────────────────────────────────────────────

def plotly_template() -> go.layout.Template:
    """Return a Plotly layout template matching the current theme."""
    t = get_theme()
    return go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color=t["text_secondary"], size=12),
            xaxis=dict(gridcolor=t["border"], zerolinecolor=t["border"]),
            yaxis=dict(gridcolor=t["border"], zerolinecolor=t["border"]),
            margin=dict(t=20, b=40, l=60, r=20),
            hoverlabel=dict(
                bgcolor=t["bg_elevated"],
                bordercolor=t["border"],
                font=dict(color=t["text_primary"], family="Inter"),
            ),
        )
    )

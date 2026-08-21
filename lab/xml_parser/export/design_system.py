"""Design System — Unified visual language for Mythos report outputs.

Philosophy:
- Generous whitespace creates visual breathing room and signals sophistication
- Strict typographic hierarchy (3 levels max) guides the reader's eye
- Muted palette with strategic accent use — color earns attention, never begs for it
- Data density without clutter: hairline rules, alternating tints, aligned numerals
- Consistent across PDF and Excel: same palette, same spacing ratios, same voice
"""


class DesignSystem:
    """Single source of truth for all visual tokens used in PDF and Excel exports."""

    # ─── Primary Palette ───────────────────────────────────────────────────────
    # Inspired by premium financial reports: dark navy anchors authority,
    # warm copper provides editorial accent, neutrals handle the workload.

    NAVY = "#1B2838"           # Primary text, headers
    COPPER = "#C4622D"         # Brand accent — titles, rules, severity HIGH
    SLATE = "#4A5568"          # Secondary text, subtitles
    GRAPHITE = "#718096"       # Tertiary text, metadata, captions
    CLOUD = "#F7FAFC"          # Alternate row background, canvas tint
    PEARL = "#EDF2F7"          # Section dividers, subtle borders
    WHITE = "#FFFFFF"          # Primary background

    # ─── Semantic Colors ───────────────────────────────────────────────────────

    SUCCESS = "#276749"        # Pass, clean, OK
    SUCCESS_BG = "#F0FFF4"     # Light green tint for success cells
    DANGER = "#C53030"         # Fail, HIGH severity, review required
    DANGER_BG = "#FFF5F5"      # Light red tint for danger cells
    WARNING = "#B7791F"        # MEDIUM severity, caution
    WARNING_BG = "#FFFFF0"     # Light yellow tint
    INFO = "#2B6CB0"           # LOW severity, informational
    INFO_BG = "#EBF8FF"        # Light blue tint

    # ─── Typography ────────────────────────────────────────────────────────────
    # Inter for digital (PDF), Segoe UI as system fallback for Excel.

    FONT_STACK = "'Inter', 'Segoe UI', -apple-system, sans-serif"
    FONT_MONO = "'JetBrains Mono', 'Consolas', monospace"
    FONT_EXCEL = "Segoe UI"

    # Scale (modular, ratio ~1.25)
    SIZE_DISPLAY = 28          # Report title (PDF only)
    SIZE_H1 = 20              # Section headers
    SIZE_H2 = 14              # Sub-section headers
    SIZE_BODY = 10            # Table data, body text
    SIZE_CAPTION = 8          # Footnotes, metadata, timestamps
    SIZE_MICRO = 7            # Dense table cells (PDF wide-format)

    # ─── Spacing ───────────────────────────────────────────────────────────────
    # Base unit = 4px. All spacing is multiples of base.

    SPACE_XS = 4
    SPACE_SM = 8
    SPACE_MD = 16
    SPACE_LG = 24
    SPACE_XL = 40
    SPACE_XXL = 64

    # ─── Borders & Rules ───────────────────────────────────────────────────────

    BORDER_HAIRLINE = 0.5      # Subtle cell separators
    BORDER_LIGHT = 1.0         # Section dividers
    BORDER_ACCENT = 2.5        # Top accent rule (copper)
    BORDER_COLOR = "#E2E8F0"   # Default border (light gray)

    # ─── Page Geometry (PDF) ───────────────────────────────────────────────────

    PAGE_MARGIN_TOP = 50       # pts
    PAGE_MARGIN_BOTTOM = 40
    PAGE_MARGIN_LEFT = 45
    PAGE_MARGIN_RIGHT = 45

    # ─── Excel Specifics ───────────────────────────────────────────────────────

    EXCEL_ROW_HEIGHT = 18      # Default data row
    EXCEL_HEADER_HEIGHT = 22
    EXCEL_TITLE_HEIGHT = 30

    @classmethod
    def severity_color(cls, severity: str) -> str:
        return {
            "HIGH": cls.DANGER,
            "MEDIUM": cls.WARNING,
            "LOW": cls.INFO,
        }.get(severity, cls.GRAPHITE)

    @classmethod
    def severity_bg(cls, severity: str) -> str:
        return {
            "HIGH": cls.DANGER_BG,
            "MEDIUM": cls.WARNING_BG,
            "LOW": cls.INFO_BG,
        }.get(severity, cls.WHITE)

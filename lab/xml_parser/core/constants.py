"""Centralized constants and thresholds for the Mythos engine."""

EXPECTED_FX_RANGES: dict[str, tuple[float, float]] = {
    "GBP": (0.70, 0.90),
    "EUR": (0.85, 1.10),
    "AUD": (1.30, 1.80),
    "CAD": (1.25, 1.50),
    "JPY": (100, 160),
    "CHF": (0.80, 1.05),
    "CNY": (6.5, 7.8),
    "BRL": (4.5, 6.5),
    "INR": (75, 95),
    "KRW": (1100, 1450),
    "THB": (30, 40),
    "SEK": (9.5, 11.5),
    "TWD": (28, 35),
    "ARS": (100, 2000),
    "VND": (22000, 27000),
}

ETR_LOW = 0.0
ETR_HIGH = 0.50

BALANCE_SHEET_TOLERANCE = 1.0

QBAI_ASSET_RATIO_MAX = 1.0

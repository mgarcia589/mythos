"""Page 1 + Schedule A extraction rules and field mapping.

Maps OIT PDF content to canonical XML field names for:
  - Form 5471 Page 1: Entity identification (name, country, FC, voting %, etc.)
  - Schedule A: Stock of the Foreign Corporation (share counts by class)

Page 1 fields validated:
  Line 1b: Country of incorporation
  Line 1c: Functional currency code
  Line 3:  Voting stock owned (percentage)
  Line 2a: Principal place of business
  Line 2c: Business activity code

Schedule A fields validated (per stock class):
  Beginning of annual accounting period: share count
  End of annual accounting period: share count

For multi-class entities (e.g. COMMON A + PREFERRED), each stock class
produces separate rows keyed by "{class_desc}|{field_name}".
"""

import re
from typing import Optional


# =============================================================================
# Page 1 — Entity identification fields (numeric/validatable only)
# =============================================================================

# Fields from Page 1 that can be reconciled numerically
PAGE1_LINE_ITEMS: list[tuple[str, str, str, str, str]] = [
    # (line_number, description_regex, xml_field_name, field_type, human_description)
    ("3", r"voting\s*stock.*percent|voting\s*stock.*owned|%.*voting|direct.*percent", "VotingStockOwnedPct", "percentage", "Voting stock owned %"),
]

# Text fields we extract for display but don't reconcile numerically
PAGE1_TEXT_FIELDS: list[tuple[str, str, str, str]] = [
    # (line_number, xml_field_name, field_type, description)
    ("1a", "ForeignCorporation_BusinessName_BusinessNameLine1Txt", "text", "Name of foreign corporation"),
    ("1b", "CountryUnderWhoseLawsIncCd", "text", "Country of incorporation"),
    ("1c", "FunctionalCurrencyCd", "text", "Functional currency"),
    ("1d", "EIN", "text", "EIN"),
    ("1d(ref)", "ForeignEntityIdentificationGrp_ForeignEntityReferenceIdNum", "text", "Reference ID number"),
    ("2a", "PrincipalPlaceOfBusCountryCd", "text", "Principal place of business"),
    ("2c", "PrincipalBusinessActivityCd", "text", "Business activity code"),
]


# =============================================================================
# Schedule A — Stock of the Foreign Corporation
# =============================================================================

SCHA_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    # (line_number, description_regex, xml_field_name, human_description)
    ("a(beg)", r"begin.*(?:annual|account|period)|(?:annual|account).*begin|beg.*share|shares.*beg", "AnnualAcctPeriodBeginShareCnt", "Shares at beginning of period"),
    ("a(end)", r"end.*(?:annual|account|period)|(?:annual|account).*end|end.*share|shares.*end", "AnnualAcctPeriodEndShareCnt", "Shares at end of period"),
]

# Compiled regex for faster matching
_COMPILED_PAGE1_PATTERNS: list[tuple[re.Pattern, str, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, field_type, line_num, desc)
    for line_num, pattern, xml_field, field_type, desc in PAGE1_LINE_ITEMS
]

_COMPILED_SCHA_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, line_num, desc)
    for line_num, pattern, xml_field, desc in SCHA_LINE_ITEMS
]

# Combined flat field list for XML parsing: (xml_field, line_num, description)
ALL_PAGE1_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, _, desc in PAGE1_LINE_ITEMS
]

ALL_SCHA_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, desc in SCHA_LINE_ITEMS
]

ALL_FIELDS: list[tuple[str, str, str]] = ALL_PAGE1_FIELDS + ALL_SCHA_FIELDS

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {}
for line_num, _, xml_field, _, desc in PAGE1_LINE_ITEMS:
    FIELD_LOOKUP[xml_field] = (line_num, desc)
for line_num, _, xml_field, desc in SCHA_LINE_ITEMS:
    FIELD_LOOKUP[xml_field] = (line_num, desc)


def identify_page1_field(description: str) -> Optional[tuple[str, str, str, str]]:
    """Identify a Page 1 numeric field from PDF description text.

    Returns:
        Tuple of (xml_field_name, field_type, line_number, human_description)
        or None if not identified.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_field, field_type, line_num, human_desc in _COMPILED_PAGE1_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, field_type, line_num, human_desc)
    return None


def identify_scha_field(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule A field from PDF description text.

    Returns:
        Tuple of (xml_field_name, line_number, human_description) or None.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_field, line_num, human_desc in _COMPILED_SCHA_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name.

    Handles compound keys like "COMMON A|AnnualAcctPeriodBeginShareCnt".
    """
    if "|" in xml_field:
        stock_class, base_field = xml_field.split("|", 1)
        info = FIELD_LOOKUP.get(base_field)
        if info:
            return f"{stock_class} — {info[1]}"
        return f"{stock_class} — {base_field}"

    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"Line {info[0]}: {info[1]}"
    return xml_field


def parse_percentage(text: str) -> Optional[float]:
    """Parse a percentage value from PDF text.

    OIT formats: "0.60800", "60.8%", "60.8", ".608"
    Returns the value as-is (not multiplied/divided).
    """
    if not text or not text.strip():
        return None
    text = text.strip().rstrip("%").strip()
    try:
        return float(text)
    except ValueError:
        return None


def parse_share_count(text: str) -> Optional[float]:
    """Parse a share count from PDF text.

    OIT formats: "265,401", "265401", "8741303"
    Returns as float for consistency with the reconciliation engine.
    """
    if not text or not text.strip():
        return None
    text = text.strip().replace(",", "")
    if text in ("", "-", "—", "–", "0", "--"):
        return None
    try:
        val = float(text)
        return val if val != 0 else None
    except ValueError:
        return None

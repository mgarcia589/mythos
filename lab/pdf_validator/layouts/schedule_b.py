"""Schedule B (Shareholders) extraction rules and field mapping.

Maps OIT PDF content to canonical XML field names for:
  - Part I: U.S. Shareholders of Foreign Corporation (names + EINs)
  - Part II: Direct Shareholders of Foreign Corporation (names + stock data)

IRS Form 5471 Schedule B reports the shareholder structure:
  Part I — Each US shareholder: name, address, identifying number (EIN/SSN),
           shares held (class, begin count, end count)
  Part II — Each direct/indirect shareholder: name, address, country,
            identifying number, stock class, begin/end share counts

For reconciliation:
  Part II share counts are numeric and reconciled by:
    Key: "{shareholder_name}|{stock_class}|{xml_field}"
  Part I EINs are extracted for completeness validation.

Multi-shareholder entities produce one row per shareholder per stock class.
"""

import re
from typing import Optional


# =============================================================================
# Part I — U.S. Shareholders
# =============================================================================

# Part I fields that can be validated (EIN as text match)
PART1_FIELDS: list[tuple[str, str, str]] = [
    # (xml_field_name, line_label, description)
    ("ShareholderEIN", "Pt1", "U.S. shareholder EIN"),
]

# =============================================================================
# Part II — Direct Shareholders (stock data is numeric)
# =============================================================================

PART2_STOCK_FIELDS: list[tuple[str, str, str]] = [
    # (xml_field_name, line_label, description)
    ("AnnualAcctPeriodBeginShareCnt", "Pt2(beg)", "Shares at beginning of period"),
    ("AnnualAcctPeriodEndShareCnt", "Pt2(end)", "Shares at end of period"),
]

# Combined flat field list for XML parsing
ALL_FIELDS: list[tuple[str, str, str]] = PART1_FIELDS + PART2_STOCK_FIELDS

# Lookup: base xml_field -> (line_label, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (label, desc)
    for xml_field, label, desc in ALL_FIELDS
}

# Page detection regex patterns
SCHB_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*B", re.IGNORECASE),
    re.compile(r"Shareholder|U\.?S\.?\s+Person", re.IGNORECASE),
]

# Part detection
PART1_PATTERN = re.compile(r"Part\s*I|U\.?S\.?\s+Shareholder", re.IGNORECASE)
PART2_PATTERN = re.compile(r"Part\s*II|Direct\s+Shareholder", re.IGNORECASE)

# Table content patterns
SHARE_COUNT_HEADER = re.compile(r"begin|end|shares|stock\s*class|class.*stock", re.IGNORECASE)
EIN_PATTERN = re.compile(r"\b(\d{2}-?\d{7})\b")


def get_field_description(compound_key: str) -> str:
    """Get human-readable description for a compound field key.

    Handles keys like:
      "SAMPLE CORP|ORDINARY|AnnualAcctPeriodBeginShareCnt"
      "Acme Corp|ShareholderEIN"
    """
    parts = compound_key.split("|")

    if len(parts) == 3:
        shareholder, stock_class, base_field = parts
        info = FIELD_LOOKUP.get(base_field)
        if info:
            return f"{shareholder} / {stock_class} — {info[1]}"
        return f"{shareholder} / {stock_class} — {base_field}"

    if len(parts) == 2:
        shareholder, base_field = parts
        info = FIELD_LOOKUP.get(base_field)
        if info:
            return f"{shareholder} — {info[1]}"
        return f"{shareholder} — {base_field}"

    info = FIELD_LOOKUP.get(compound_key)
    if info:
        return f"{info[0]}: {info[1]}"
    return compound_key


def parse_ein(text: str) -> Optional[str]:
    """Parse an EIN from PDF text. Returns normalized form (digits only)."""
    if not text or not text.strip():
        return None
    m = EIN_PATTERN.search(text)
    if m:
        return m.group(1).replace("-", "")
    # Try plain 9-digit number
    digits = re.sub(r"\D", "", text.strip())
    if len(digits) == 9:
        return digits
    return None


def normalize_shareholder_name(name: str) -> str:
    """Normalize shareholder name for matching between PDF and XML.

    Uppercase, strip common suffixes, collapse whitespace.
    """
    if not name:
        return ""
    n = name.upper().strip()
    n = re.sub(r"\s+", " ", n)
    # Remove trailing punctuation
    n = n.rstrip(".,;")
    return n

"""Schedule R (Distributions) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule R — Distributions From a Foreign Corporation.

Schedule R is row-based: each distribution is a separate row with:
  - DistributionDesc: textual description of the distribution
  - DistributionDt: date of the distribution
  - DistributionFuncCurAmt: amount in functional currency
  - DistributionFromEPFuncCurAmt: portion from E&P in functional currency

Fields use compound keys: "{row_id}|{field_name}" where row_id is either
a sequential index or the distribution description text (normalized).
"""

import re
from typing import Optional

# Per-row fields: (xml_field_name, description_regex, human_description)
SCHR_ROW_FIELDS: list[tuple[str, str, str]] = [
    ("DistributionDesc", r"distribut.*desc|description|type\s*of\s*distri", "Distribution description"),
    ("DistributionDt", r"distribut.*date|date\s*of\s*distri|dist.*dt", "Distribution date"),
    ("DistributionFuncCurAmt", r"distribut.*func.*cur|amount.*func.*cur|dist.*fc\b", "Distribution (functional currency)"),
    ("DistributionFromEPFuncCurAmt", r"distribut.*from\s*e.?p|from\s*e.?p.*func|e.?p.*func.*cur|dist.*e.?p", "Distribution from E&P (functional currency)"),
]

# Column header detection patterns
SCHR_HEADER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"description|type", re.IGNORECASE), "DistributionDesc"),
    (re.compile(r"\bdate\b", re.IGNORECASE), "DistributionDt"),
    (re.compile(r"functional\s*currency\s*amount|amount.*fc|fc\s*amount", re.IGNORECASE), "DistributionFuncCurAmt"),
    (re.compile(r"from\s*e.?&?.?p|e.?p.*amount", re.IGNORECASE), "DistributionFromEPFuncCurAmt"),
]

# Compiled row field patterns
_ROW_FIELD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, desc)
    for xml_field, pattern, desc in SCHR_ROW_FIELDS
]

# Flat field list for XML parsing (base fields, without row prefix)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, "row", desc)
    for xml_field, _, desc in SCHR_ROW_FIELDS
]

# Lookup: base xml_field -> (label, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: ("row", desc)
    for xml_field, _, desc in SCHR_ROW_FIELDS
}

# Date pattern for parsing distribution dates
DATE_PATTERN = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})")

# Amount fields (numeric, reconcilable)
AMOUNT_FIELDS: list[str] = [
    "DistributionFuncCurAmt",
    "DistributionFromEPFuncCurAmt",
]

# Text/date fields (not numerically reconciled)
TEXT_FIELDS: list[str] = [
    "DistributionDesc",
    "DistributionDt",
]


def identify_column(header_text: str) -> Optional[str]:
    """Identify which Schedule R field a column header maps to.

    Args:
        header_text: Column header text from the PDF table

    Returns:
        The xml_field_name or None if not identified.
    """
    text_clean = header_text.strip().lower()
    if not text_clean:
        return None

    for pattern, xml_field in SCHR_HEADER_PATTERNS:
        if pattern.search(text_clean):
            return xml_field
    return None


def identify_field(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule R field from its PDF description text.

    Args:
        description: Text from the PDF (header or label)

    Returns:
        Tuple of (xml_field_name, line_label, human_description) or None.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_field, human_desc in _ROW_FIELD_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, "row", human_desc)
    return None


def make_compound_key(row_id: str, field_name: str) -> str:
    """Create a compound key for a specific distribution row and field.

    Args:
        row_id: Row identifier (e.g., "1", "2", or normalized description)
        field_name: Base XML field name

    Returns:
        Compound key in format "row_id|field_name"
    """
    return f"{row_id}|{field_name}"


def parse_compound_key(compound_key: str) -> tuple[str, str]:
    """Parse a compound key back into row_id and field_name.

    Args:
        compound_key: Key in format "row_id|field_name"

    Returns:
        Tuple of (row_id, field_name)
    """
    parts = compound_key.split("|", 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return ("", compound_key)


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name.

    Handles compound keys with pipe separator:
      "1|DistributionFuncCurAmt" -> "Row 1 — Distribution (functional currency)"
      "Dividend|DistributionDt" -> "Dividend — Distribution date"
    """
    if "|" in xml_field:
        row_id, base_field = parse_compound_key(xml_field)
        info = FIELD_LOOKUP.get(base_field)
        if info:
            return f"Row {row_id} — {info[1]}"
        return f"Row {row_id} — {base_field}"

    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return info[1]
    return xml_field


def normalize_distribution_desc(desc: str) -> str:
    """Normalize a distribution description for use as a row key.

    Uppercase, collapse whitespace, strip punctuation.
    """
    if not desc:
        return ""
    n = desc.upper().strip()
    n = re.sub(r"\s+", " ", n)
    n = n.rstrip(".,;:")
    return n


def parse_date(text: str) -> Optional[str]:
    """Parse a distribution date from PDF text.

    Returns ISO format YYYY-MM-DD or None.
    """
    if not text or not text.strip():
        return None
    m = DATE_PATTERN.search(text.strip())
    if m:
        month, day, year = m.group(1), m.group(2), m.group(3)
        if len(year) == 2:
            year = f"20{year}" if int(year) < 50 else f"19{year}"
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None

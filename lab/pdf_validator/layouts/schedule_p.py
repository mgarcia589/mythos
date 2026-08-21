"""Schedule P (Previously Taxed E&P) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule P — Previously Taxed Earnings and Profits
of U.S. Shareholder of Certain Foreign Corporations.

Schedule P tracks PTEP by shareholder across multiple pool groups.
Each pool has beginning balance, adjustments, total, and ending balance.

Structure:
  - SeparateCategoryCd: basket/category code
  - FC-level pools: FCReclassifiedSect965aPTEPGrp, etc.
  - US-level pools: USReclassifiedSect965aPTEPGrp, etc.
  - Within each pool: BeginningYearBalanceAmt, AdjustedBeginningBalanceAmt,
                       TotalPreviouslyTaxedEPAmt, BalanceBeginningNextYearAmt

Fields use compound keys: "{pool_group}|{field}" for nested amounts.
"""

import re
from typing import Optional

# Pool group definitions
# FC-level pools (Foreign Corporation level)
FC_POOL_GROUPS: dict[str, str] = {
    "FCReclassifiedSect965aPTEPGrp": "FC Reclassified 965(a) PTEP",
    "FCReclassifiedSect965bPTEPGrp": "FC Reclassified 965(b) PTEP",
    "FCGeneralSection959c1PTEPGrp": "FC General 959(c)(1) PTEP",
    "FCReclassifiedSect951APTEPGrp": "FC Reclassified 951A PTEP",
    "FCReclassifiedSect245AdPTEPGrp": "FC Reclassified 245A(d) PTEP",
    "FCSection965aPTEPGrp": "FC Section 965(a) PTEP",
    "FCSection965bPTEPGrp": "FC Section 965(b) PTEP",
    "FCSection951APTEPGrp": "FC Section 951A PTEP",
    "FCSection245AdPTEPGrp": "FC Section 245A(d) PTEP",
    "FCSection951a1APTEPGrp": "FC Section 951(a)(1)(A) PTEP",
    "FCTotalPTEPGrp": "FC Total PTEP",
}

# US-level pools (US Shareholder level)
US_POOL_GROUPS: dict[str, str] = {
    "USReclassifiedSect965aPTEPGrp": "US Reclassified 965(a) PTEP",
    "USReclassifiedSect965bPTEPGrp": "US Reclassified 965(b) PTEP",
    "USGeneralSection959c1PTEPGrp": "US General 959(c)(1) PTEP",
    "USReclassifiedSect951APTEPGrp": "US Reclassified 951A PTEP",
    "USReclassifiedSect245AdPTEPGrp": "US Reclassified 245A(d) PTEP",
    "USSection965aPTEPGrp": "US Section 965(a) PTEP",
    "USSection965bPTEPGrp": "US Section 965(b) PTEP",
    "USSection951APTEPGrp": "US Section 951A PTEP",
    "USSection245AdPTEPGrp": "US Section 245A(d) PTEP",
    "USSection951a1APTEPGrp": "US Section 951(a)(1)(A) PTEP",
    "USTotalPTEPGrp": "US Total PTEP",
}

# All pool groups combined
ALL_POOL_GROUPS: dict[str, str] = {**FC_POOL_GROUPS, **US_POOL_GROUPS}

# Fields within each pool group
POOL_FIELDS: list[tuple[str, str, str]] = [
    # (xml_field_name, description_regex, human_description)
    ("BeginningYearBalanceAmt", r"begin.*year.*bal|beginning\s*balance|beg.*bal|bol\b", "Beginning year balance"),
    ("AdjustedBeginningBalanceAmt", r"adjust.*begin|adj.*beg.*bal", "Adjusted beginning balance"),
    ("TotalPreviouslyTaxedEPAmt", r"total\s*prev.*taxed|total\s*ptep|total.*previously", "Total previously taxed E&P"),
    ("BalanceBeginningNextYearAmt", r"balance.*next\s*year|end.*year.*bal|ending\s*bal|eol\b|bal.*beg.*next", "Balance beginning next year"),
]

# Pool group detection patterns
# Pool patterns are ordered so that more specific patterns (reclass, 951(a)(1)(A))
# match before less specific ones (section 965(a), 951A).
_FC_POOL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"fc.*reclass.*965.*a(?!.*951)(?!.*245)", re.IGNORECASE), "FCReclassifiedSect965aPTEPGrp"),
    (re.compile(r"fc.*reclass.*965.*b", re.IGNORECASE), "FCReclassifiedSect965bPTEPGrp"),
    (re.compile(r"fc.*general.*959|fc.*gen.*c.*1", re.IGNORECASE), "FCGeneralSection959c1PTEPGrp"),
    (re.compile(r"fc.*reclass.*951\s*a", re.IGNORECASE), "FCReclassifiedSect951APTEPGrp"),
    (re.compile(r"fc.*reclass.*245\s*a", re.IGNORECASE), "FCReclassifiedSect245AdPTEPGrp"),
    (re.compile(r"fc.*951.*a.*1.*a|fc.*951\(a\)\(1\)\(a\)", re.IGNORECASE), "FCSection951a1APTEPGrp"),
    (re.compile(r"fc.*section\s*965.*a|fc.*sec.*965.*a(?!.*b)", re.IGNORECASE), "FCSection965aPTEPGrp"),
    (re.compile(r"fc.*section\s*965.*b|fc.*sec.*965.*b", re.IGNORECASE), "FCSection965bPTEPGrp"),
    (re.compile(r"fc.*section\s*951\s*a|fc.*sec.*951\s*a", re.IGNORECASE), "FCSection951APTEPGrp"),
    (re.compile(r"fc.*section\s*245|fc.*sec.*245\s*a", re.IGNORECASE), "FCSection245AdPTEPGrp"),
    (re.compile(r"fc.*total\s*ptep|fc.*total.*prev", re.IGNORECASE), "FCTotalPTEPGrp"),
]

_US_POOL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"us.*reclass.*965.*a(?!.*951)(?!.*245)", re.IGNORECASE), "USReclassifiedSect965aPTEPGrp"),
    (re.compile(r"us.*reclass.*965.*b", re.IGNORECASE), "USReclassifiedSect965bPTEPGrp"),
    (re.compile(r"us.*general.*959|us.*gen.*c.*1", re.IGNORECASE), "USGeneralSection959c1PTEPGrp"),
    (re.compile(r"us.*reclass.*951\s*a", re.IGNORECASE), "USReclassifiedSect951APTEPGrp"),
    (re.compile(r"us.*reclass.*245\s*a", re.IGNORECASE), "USReclassifiedSect245AdPTEPGrp"),
    (re.compile(r"us.*951.*a.*1.*a|us.*951\(a\)\(1\)\(a\)", re.IGNORECASE), "USSection951a1APTEPGrp"),
    (re.compile(r"us.*section\s*965.*a|us.*sec.*965.*a(?!.*b)", re.IGNORECASE), "USSection965aPTEPGrp"),
    (re.compile(r"us.*section\s*965.*b|us.*sec.*965.*b", re.IGNORECASE), "USSection965bPTEPGrp"),
    (re.compile(r"us.*section\s*951\s*a|us.*sec.*951\s*a", re.IGNORECASE), "USSection951APTEPGrp"),
    (re.compile(r"us.*section\s*245|us.*sec.*245\s*a", re.IGNORECASE), "USSection245AdPTEPGrp"),
    (re.compile(r"us.*total\s*ptep|us.*total.*prev", re.IGNORECASE), "USTotalPTEPGrp"),
]

_ALL_POOL_PATTERNS: list[tuple[re.Pattern, str]] = _FC_POOL_PATTERNS + _US_POOL_PATTERNS

# Compiled field patterns
_FIELD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, desc)
    for xml_field, pattern, desc in POOL_FIELDS
]

# Flat field list for XML parsing: (compound_key, label, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (f"{pool}|{fld}", "pool", f"{ALL_POOL_GROUPS[pool]} — {desc}")
    for pool in ALL_POOL_GROUPS
    for fld, _, desc in POOL_FIELDS
]

# Lookup: compound_key -> (label, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    compound_key: (label, desc)
    for compound_key, label, desc in ALL_FIELDS
}

# Pool group lookup: pool_xml -> human name
POOL_LOOKUP: dict[str, str] = ALL_POOL_GROUPS


def identify_line_item(description: str, pool_context: Optional[str] = None) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule P line item from its PDF description text.

    Args:
        description: Text from the PDF row (already cleaned of OIT spacers)
        pool_context: If known, the current pool group XML name
                      (e.g., "FCSection951APTEPGrp")

    Returns:
        Tuple of (compound_key, line_label, human_description) or None.
        compound_key format: "pool_group|field_name"
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    # If we have pool context, match field within that pool
    if pool_context and pool_context in ALL_POOL_GROUPS:
        for pattern, field_xml, field_desc in _FIELD_PATTERNS:
            if pattern.search(desc_clean):
                compound = f"{pool_context}|{field_xml}"
                full_desc = f"{ALL_POOL_GROUPS[pool_context]} — {field_desc}"
                return (compound, "pool", full_desc)

    # Try to detect pool group from the text itself
    detected_pool = detect_pool_context(description)
    if detected_pool:
        for pattern, field_xml, field_desc in _FIELD_PATTERNS:
            if pattern.search(desc_clean):
                compound = f"{detected_pool}|{field_xml}"
                full_desc = f"{ALL_POOL_GROUPS[detected_pool]} — {field_desc}"
                return (compound, "pool", full_desc)

    return None


def detect_pool_context(text: str) -> Optional[str]:
    """Detect which PTEP pool group section we are in based on header text.

    Returns the pool group XML name or None.
    """
    text_lower = text.strip().lower()
    if not text_lower:
        return None

    for pool_pattern, pool_xml in _ALL_POOL_PATTERNS:
        if pool_pattern.search(text_lower):
            return pool_xml
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name.

    Handles compound keys with pipe separator:
      "FCSection951APTEPGrp|BeginningYearBalanceAmt"
        -> "FC Section 951A PTEP — Beginning year balance"
    """
    # Compound key
    if "|" in xml_field:
        parts = xml_field.split("|", 1)
        pool_name = ALL_POOL_GROUPS.get(parts[0], parts[0])
        # Look up field description
        for fld, _, desc in POOL_FIELDS:
            if fld == parts[1]:
                return f"{pool_name} — {desc}"
        return f"{pool_name} — {parts[1]}"

    # Simple field (shouldn't happen often for Sch P, but handle gracefully)
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return info[1]
    return xml_field

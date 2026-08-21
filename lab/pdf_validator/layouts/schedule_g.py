"""Schedule G (Other Information) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule G — Other Information.

Schedule G is primarily Yes/No indicator questions (checkboxes) with
one amount field (163(j) carryforward). For reconciliation purposes:
  - Indicators are treated as 1.0 (Yes/X) or 0.0 (No/blank)
  - The amount field is reconciled normally

Line items (from IRS instructions):
  Line 4: Expatriated foreign subsidiary
  Line 6: Base erosion payments (BEAT)
  Line 7: Section 909 splitter arrangement
  Line 8: FDII benefits claimed
  Line 11: Reportable transaction participant
  Line 15a: Disallowed interest expense under 163(j)
  Line 15b: 163(j) carryforward amount
  Line new: Top-up tax (Pillar Two)
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_field_name, field_type, human_description)
# field_type: "indicator" (Yes/No) or "amount" (dollar value)
SCHG_LINE_ITEMS: list[tuple[str, str, str, str, str]] = [
    ("4", r"expatriat.*subsidiar|expatriated\s*foreign", "ExpatriatedFrgnSubsidiaryInd", "indicator", "Expatriated foreign subsidiary?"),
    ("6", r"base\s*erosion|beat\b", "BaseErosionPaymentBenefitInd", "indicator", "Base erosion payments (BEAT)?"),
    ("7", r"section\s*909|909\s*splitter|splitter\s*arrange", "ForeignTaxSection909Ind", "indicator", "Section 909 splitter arrangement?"),
    ("8", r"fdii|foreign.derived\s*intangible", "FDIIBenefitsClaimInd", "indicator", "FDII benefits claimed?"),
    ("11", r"reportable\s*transaction|listed\s*transaction", "ReportableTransactionPrtcptInd", "indicator", "Reportable transaction participant?"),
    ("15a", r"disallowed\s*interest|163.*j.*disallowed|interest.*limitation", "DisallowedInterestExpenseInd", "indicator", "Disallowed interest expense (163(j))?"),
    ("15b", r"carryforward.*163|163.*j.*carryforward|carryforward\s*amount", "CfwdPrevDsallwIntExpenseAmt", "amount", "163(j) carryforward amount"),
    ("new", r"top.?up\s*tax|pillar\s*two|pillar\s*2|qdmtt|globe", "PayOrAccrueTopUpTaxInd", "indicator", "Top-up tax (Pillar Two)?"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, field_type, line_num, desc)
    for line_num, pattern, xml_field, field_type, desc in SCHG_LINE_ITEMS
]

# Flat field list for XML parsing: (xml_field, line_num, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, _, desc in SCHG_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (line_num, desc)
    for line_num, _, xml_field, _, desc in SCHG_LINE_ITEMS
}

# Type lookup: xml_field -> "indicator" or "amount"
FIELD_TYPE: dict[str, str] = {
    xml_field: field_type
    for _, _, xml_field, field_type, _ in SCHG_LINE_ITEMS
}

# Indicator fields only (for special parsing)
INDICATOR_FIELDS: list[str] = [
    xml_field for _, _, xml_field, ftype, _ in SCHG_LINE_ITEMS if ftype == "indicator"
]

# Amount fields only
AMOUNT_FIELDS: list[str] = [
    xml_field for _, _, xml_field, ftype, _ in SCHG_LINE_ITEMS if ftype == "amount"
]


def identify_line_item(description: str) -> Optional[tuple[str, str, str, str]]:
    """Identify a Schedule G line item from its PDF description text.

    Args:
        description: Text from the PDF row (already cleaned of OIT spacers)

    Returns:
        Tuple of (xml_field_name, field_type, line_number, human_description)
        or None if not identified.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_field, field_type, line_num, human_desc in _COMPILED_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, field_type, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name."""
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"Line {info[0]}: {info[1]}"
    return xml_field


def parse_indicator(value: str) -> float:
    """Convert an indicator value from PDF text to numeric.

    "X", "Yes", "1", "true" → 1.0
    Everything else (blank, "No", "0") → 0.0
    """
    if not value:
        return 0.0
    v = value.strip().lower()
    if v in ("x", "yes", "1", "true", "y"):
        return 1.0
    return 0.0

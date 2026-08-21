"""Schedule E (Foreign Taxes) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule E — Income, War Profits, and Excess Profits
Taxes Paid or Accrued.

Schedule E tracks taxes paid by PTEP category. Structure:
  - Summary-level totals: total tax in functional currency & USD
  - Per income group (Subpart F, Tested Income, Residual):
    - Total tax in USD
    - Current/accumulated E&P
    - Taxes deemed paid
    - Balance taxes paid/accrued
    - Reduction other taxes not deemed paid

Fields use compound keys: "{income_group}|{field}" for nested amounts.
"""

import re
from typing import Optional

# Income group names (prefixes for compound keys)
INCOME_GROUPS: dict[str, str] = {
    "Frm5471SchESubpartFIncomeGrp": "Subpart F income",
    "Frm5471SchETestedIncomeGrp": "Tested income (GILTI)",
    "Frm5471SchEResidualIncomeGrp": "Residual income",
}

# Summary-level fields (not nested under a group)
SCHE_SUMMARY_FIELDS: list[tuple[str, str, str, str]] = [
    # (line_label, description_regex, xml_field_name, human_description)
    ("Total(FC)", r"total\s*tax.*functional|tax.*funct.*curr.*total", "TotalTaxInFunctionalCurAmt", "Total tax in functional currency"),
    ("Total(USD)", r"total\s*tax.*u\.?s\.?\s*dollar|total.*tax.*usd", "TotalTaxInUSDollarsAmt", "Total tax in USD"),
]

# Per-group fields (field within each income group)
SCHE_GROUP_FIELDS: list[tuple[str, str, str]] = [
    # (xml_field_name, description_regex, human_description)
    ("TotalTaxInUSDollarsAmt", r"total\s*tax.*usd|total\s*tax.*dollar|tax.*u\.?s", "Total tax USD"),
    ("TotalCurrentAccumulatedEPAmt", r"current.*accum.*e.?p|accum.*earnings|current\s*e.?p", "Current/accumulated E&P"),
    ("TaxesDeemedPaidAmt", r"taxes?\s*deemed\s*paid|deemed\s*paid", "Taxes deemed paid"),
    ("BalanceTxsPaidOrAccruedAmt", r"balance.*tax.*paid|balance.*accrued|bal.*paid.*accr", "Balance taxes paid/accrued"),
    ("RedOtherTxsNotDeemedPdAmt", r"reduc.*other\s*tax|other\s*tax.*not\s*deemed|red.*not\s*deemed", "Reduction other taxes"),
]

# Build compound field list: all permutations of group + field
SCHE_COMPOUND_ITEMS: list[tuple[str, str, str, str]] = []
for grp_xml, grp_desc in INCOME_GROUPS.items():
    for field_xml, field_regex, field_desc in SCHE_GROUP_FIELDS:
        compound_key = f"{grp_xml}|{field_xml}"
        compound_desc = f"{grp_desc} — {field_desc}"
        SCHE_COMPOUND_ITEMS.append(("grp", field_regex, compound_key, compound_desc))

# Full line items (summary + compound for regex matching)
SCHE_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    (label, regex, xml_field, desc)
    for label, regex, xml_field, desc in SCHE_SUMMARY_FIELDS
] + SCHE_COMPOUND_ITEMS

# Compiled regex for summary fields
_SUMMARY_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, line_num, desc)
    for line_num, pattern, xml_field, desc in SCHE_SUMMARY_FIELDS
]

# Group detection patterns (to identify which income group context we're in)
_GROUP_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"subpart\s*f", re.IGNORECASE), "Frm5471SchESubpartFIncomeGrp"),
    (re.compile(r"tested\s*income|gilti", re.IGNORECASE), "Frm5471SchETestedIncomeGrp"),
    (re.compile(r"residual", re.IGNORECASE), "Frm5471SchEResidualIncomeGrp"),
]

# Compiled regex for per-group fields
_GROUP_FIELD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, desc)
    for xml_field, pattern, desc in SCHE_GROUP_FIELDS
]

# Flat field list for XML parsing: (xml_field, line_label, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, label, desc)
    for label, _, xml_field, desc in SCHE_SUMMARY_FIELDS
] + [
    (f"{grp}|{fld}", "grp", f"{INCOME_GROUPS[grp]} — {desc}")
    for grp in INCOME_GROUPS
    for fld, _, desc in SCHE_GROUP_FIELDS
]

# Lookup: xml_field or compound_key -> (line_label, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (label, desc)
    for xml_field, label, desc in ALL_FIELDS
}


def identify_line_item(description: str, group_context: Optional[str] = None) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule E line item from its PDF description text.

    Args:
        description: Text from the PDF row (already cleaned of OIT spacers)
        group_context: If known, the current income group XML name
                       (e.g., "Frm5471SchETestedIncomeGrp")

    Returns:
        Tuple of (xml_field_name, line_label, human_description) or None.
        For group fields, xml_field_name is compound: "group|field".
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    # Try summary fields first
    for pattern, xml_field, line_num, human_desc in _SUMMARY_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, line_num, human_desc)

    # Try group-level fields (need context to assign correct group)
    if group_context and group_context in INCOME_GROUPS:
        for pattern, field_xml, field_desc in _GROUP_FIELD_PATTERNS:
            if pattern.search(desc_clean):
                compound = f"{group_context}|{field_xml}"
                full_desc = f"{INCOME_GROUPS[group_context]} — {field_desc}"
                return (compound, "grp", full_desc)

    # Without group context, try to infer group from description itself
    detected_group = None
    for grp_pattern, grp_xml in _GROUP_PATTERNS:
        if grp_pattern.search(desc_clean):
            detected_group = grp_xml
            break

    if detected_group:
        for pattern, field_xml, field_desc in _GROUP_FIELD_PATTERNS:
            if pattern.search(desc_clean):
                compound = f"{detected_group}|{field_xml}"
                full_desc = f"{INCOME_GROUPS[detected_group]} — {field_desc}"
                return (compound, "grp", full_desc)

    return None


def detect_group_context(text: str) -> Optional[str]:
    """Detect which income group section we are in based on header text.

    Returns the group XML name or None.
    """
    text_lower = text.strip().lower()
    for grp_pattern, grp_xml in _GROUP_PATTERNS:
        if grp_pattern.search(text_lower):
            return grp_xml
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name.

    Handles both simple fields and compound keys with pipe separator:
      "TotalTaxInFunctionalCurAmt" -> "Total(FC): Total tax in functional currency"
      "Frm5471SchETestedIncomeGrp|TaxesDeemedPaidAmt" -> "Tested income (GILTI) — Taxes deemed paid"
    """
    # Check compound key
    if "|" in xml_field:
        parts = xml_field.split("|", 1)
        group_name = INCOME_GROUPS.get(parts[0], parts[0])
        # Look up field description
        for fld, _, desc in SCHE_GROUP_FIELDS:
            if fld == parts[1]:
                return f"{group_name} — {desc}"
        return f"{group_name} — {parts[1]}"

    # Simple field
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"{info[0]}: {info[1]}"
    return xml_field

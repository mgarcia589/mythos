"""Schedule I (Summary of Shareholder's Income) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule I — Summary of Shareholder's Income.

Schedule I is a CFC income summary with both amount fields and indicator fields:
  Lines 1a-1f: Subpart F income categories (FPHCI, sales, services, other)
  Line 2: Earnings invested in US property
  Line 5: Section 245A eligible dividends
  Line 6: Dividends not reported
  Line 7: Exchange gain/loss on distributions
  Indicators: income blocked, income unblocked, E&D account
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_field_name, field_type, human_description)
# field_type: "amount" (dollar value) or "indicator" (Yes/No checkbox)
SCHI_LINE_ITEMS: list[tuple[str, str, str, str, str]] = [
    ("1a", r"fphci|foreign\s*personal\s*holding|subpart\s*f.*phc", "SubpartFPHCIncomeAmt", "amount", "Subpart F — FPHCI"),
    ("1b", r"sales\s*income|subpart\s*f.*sales", "SubpartFSalesIncomeAmt", "amount", "Subpart F — Sales income"),
    ("1c", r"services?\s*income|subpart\s*f.*service", "SubpartFServicesIncomeAmt", "amount", "Subpart F — Services income"),
    ("1f", r"other\s*subpart\s*f|subpart\s*f.*not\s*includ|other.*sub.*f", "OtherSubpartFNotIncludedAmt", "amount", "Other Subpart F income"),
    ("2", r"earnings\s*invested.*u\.?s|invest.*u\.?s\.?\s*prop|sec.*956", "EarningsInvestedInUSPropAmt", "amount", "Earnings invested in US property"),
    ("5", r"245.?a.*eligible|eligible.*245|sect.*245.*divid", "Sect245AEligibleDividendsAmt", "amount", "Section 245A eligible dividends"),
    ("6", r"dividends?\s*not\s*report|not\s*reported.*divid", "DividendsNotReportedAmt", "amount", "Dividends not reported"),
    ("7", r"exchange\s*gain|exchange\s*loss|gain.*loss.*distri|fx.*distri", "ExchangeGainOrLossOnDistriAmt", "amount", "Exchange gain/loss on distributions"),
    ("ind1", r"income\s*blocked|blocked\s*income", "IncomeBlockedInd", "indicator", "Income blocked?"),
    ("ind2", r"income\s*unblocked|unblocked\s*income", "IncomeUnblockedInd", "indicator", "Income unblocked?"),
    ("ind3", r"e.?&?.?d\s*account|earning.*deficit|e\s*and\s*d\s*account", "EDAccountInd", "indicator", "E&D account?"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, field_type, line_num, desc)
    for line_num, pattern, xml_field, field_type, desc in SCHI_LINE_ITEMS
]

# Flat field list for XML parsing: (xml_field, line_num, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, _, desc in SCHI_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (line_num, desc)
    for line_num, _, xml_field, _, desc in SCHI_LINE_ITEMS
}

# Type lookup: xml_field -> "indicator" or "amount"
FIELD_TYPE: dict[str, str] = {
    xml_field: field_type
    for _, _, xml_field, field_type, _ in SCHI_LINE_ITEMS
}

# Indicator fields only (for special parsing)
INDICATOR_FIELDS: list[str] = [
    xml_field for _, _, xml_field, ftype, _ in SCHI_LINE_ITEMS if ftype == "indicator"
]

# Amount fields only
AMOUNT_FIELDS: list[str] = [
    xml_field for _, _, xml_field, ftype, _ in SCHI_LINE_ITEMS if ftype == "amount"
]


def identify_line_item(description: str) -> Optional[tuple[str, str, str, str]]:
    """Identify a Schedule I line item from its PDF description text.

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

    "X", "Yes", "1", "true" -> 1.0
    Everything else (blank, "No", "0") -> 0.0
    """
    if not value:
        return 0.0
    v = value.strip().lower()
    if v in ("x", "yes", "1", "true", "y"):
        return 1.0
    return 0.0

"""Schedule F (Balance Sheet) extraction rules for Form 8858.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 8858 Schedule F — Balance Sheet of FDE/FB.

8858 Sch F uses BOY/EOY columns like 5471 Sch F but with different
XML element structure:
  <IRS8858ScheduleF>
    <CashAndOtherCurrentAssets>
      <BeginningAmt>...</BeginningAmt>
      <EndingAmt>...</EndingAmt>
    </CashAndOtherCurrentAssets>
    ...
  </IRS8858ScheduleF>

The extraction stores: "{ElementName}_{BOY|EOY}" as the field key.
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_element, human_description)
# BOY/EOY are handled as separate fields with suffix _BOY/_EOY
SCH8858F_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    # ASSETS
    ("1", r"\bcash\b|cash\s*(?:and|&)\s*other\s*current", "CashAndOtherCurrentAssets", "Cash and other current assets"),
    ("2", r"trade\s*notes|accounts?\s*receivable", "TradeNotesAcctReceivable", "Trade notes & accounts receivable"),
    ("3", r"inventor", "Inventories", "Inventories"),
    ("4", r"other\s*current\s*assets", "OtherCurrentAssets", "Other current assets"),
    ("5", r"loans?\s*to\s*(?:share|shr|owner)", "LoansToOwner", "Loans to owner"),
    ("6", r"(?:fixed\s*assets|property|plant|equip|ppe)", "FixedAssets", "Fixed assets (net)"),
    ("7", r"other\s*assets", "OtherAssetsBalanceSheet", "Other assets"),
    ("8", r"total\s*assets", "TotalAssetsBalanceSheet", "TOTAL ASSETS"),
    # LIABILITIES
    ("9", r"accounts?\s*payable", "AccountsPayable", "Accounts payable"),
    ("10", r"other\s*current\s*liab", "OtherCurrentLiabilities", "Other current liabilities"),
    ("13", r"total\s*liab.*(?:equity|owner)|total\s*(?:liab.*equity)", "TotLiabOwnerEquityBalanceSheet", "TOTAL LIABILITIES & EQUITY"),
    ("11", r"loans?\s*from\s*(?:share|shr|owner)|long.?term\s*liab|(?<!\btotal\s)liabilities", "LiabilitiesBalanceSheet", "Liabilities"),
    ("12", r"owner.?s?\s*equity|owner\s*capital|net\s*equity", "OwnerEquityBalanceSheet", "Owner's equity"),
]

_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_elem, line_num, desc)
    for line_num, pattern, xml_elem, desc in SCH8858F_LINE_ITEMS
]

ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_elem, line_num, desc)
    for line_num, _, xml_elem, desc in SCH8858F_LINE_ITEMS
]

FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_elem: (line_num, desc)
    for line_num, _, xml_elem, desc in SCH8858F_LINE_ITEMS
}


def identify_line_item(description: str) -> Optional[tuple[str, str, str, str]]:
    """Identify a Form 8858 Schedule F line item from its PDF description.

    Returns:
        Tuple of (boy_field, eoy_field, line_number, human_description) or None.
        Fields use suffix convention: "{ElementName}_BOY" and "{ElementName}_EOY".
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_elem, line_num, human_desc in _COMPILED_PATTERNS:
        if pattern.search(desc_clean):
            boy_field = f"{xml_elem}_BOY"
            eoy_field = f"{xml_elem}_EOY"
            return (boy_field, eoy_field, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for a field name."""
    base = xml_field.replace("_BOY", "").replace("_EOY", "")
    info = FIELD_LOOKUP.get(base)
    suffix = " (BOY)" if xml_field.endswith("_BOY") else " (EOY)" if xml_field.endswith("_EOY") else ""
    if info:
        return f"Line {info[0]}: {info[1]}{suffix}"
    return xml_field

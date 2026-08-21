"""Schedule F (Balance Sheet) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for both
Beginning of Year (BOY) and End of Year (EOY) columns.

IRS Form 5471 Schedule F has ~20 line items organized as:
  Assets (lines 1-12)
  Liabilities (lines 13-16)
  Equity (lines 17-20)
  Total (line 20 = sum)
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, boy_xml_field, eoy_xml_field, description)
# Regex patterns match OIT PDF descriptions (with "m" spacers already cleaned)
SCHF_LINE_ITEMS: list[tuple[str, str, str, str, str]] = [
    # ASSETS
    ("1", r"\bcash\b", "BegngAcctPrdCashAmt", "EndAcctPrdCashAmt", "Cash"),
    ("2", r"trade\s*notes|accounts?\s*receivable|receivable", "BegngAcctPrdTradeNotesAmt", "EndAcctPrdTradeNotesAmt", "Trade notes & accounts receivable"),
    ("2a", r"bad\s*debt|allowance", "BegngAcctPrdBadDebtAllwncAmt", "EndAcctPrdBadDebtAllwncAmt", "Less: bad debt allowance"),
    ("3", r"inventor", "BegngAcctPrdInventoriesAmt", "EndAcctPrdInventoriesAmt", "Inventories"),
    ("4", r"other\s*current\s*assets", "BegngAcctPrdOtherCurrAssetsAmt", "EndAcctPrdOtherCurrAssetsAmt", "Other current assets"),
    ("5", r"loans?\s*to\s*share|loans?\s*to\s*shr", "BegngAcctPrdLoansToShrAmt", "EndAcctPrdLoansToShrAmt", "Loans to shareholders"),
    ("6", r"invest.*subsidiar", "BegngAcctPrdInvstSubsidiaryAmt", "EndAcctPrdInvstSubsidiaryAmt", "Investment in subsidiaries"),
    ("7", r"other\s*invest", "BegngAcctPrdOthInvestmentsAmt", "EndAcctPrdOthInvestmentsAmt", "Other investments"),
    ("8a", r"build|depreci.*assets", "BegngAcctPrdBldgAndOtherAstAmt", "EndAcctPrdBldgAndOtherAstAmt", "Buildings & other depreciable assets"),
    ("8b", r"accum.*deprec", "BegngAcctPrdNetAccumDeprecAmt", "EndAcctPrdNetAccumDeprecAmt", "Less: accumulated depreciation"),
    ("9a", r"\bland\b", "BegngAcctPrdLandAmt", "EndAcctPrdLandAmt", "Land"),
    ("9b", r"accum.*amort", "BegngAcctPrdNetAccumAmortzAmt", "EndAcctPrdNetAccumAmortzAmt", "Less: accumulated amortization"),
    ("10a", r"patent|intangib", "BegngAcctPrdPatentsOthAstAmt", "EndAcctPrdPatentsOthAstAmt", "Intangible assets"),
    ("10b", r"goodwill", "BegngAcctPrdGoodwillAmt", "EndAcctPrdGoodwillAmt", "Goodwill"),
    ("11", r"other\s*assets", "BegngAcctPrdOtherAssetsAmt", "EndAcctPrdOtherAssetsAmt", "Other assets"),
    ("12", r"total\s*assets", "BegngAcctPrdTotalAssetsAmt", "EndAcctPrdTotalAssetsAmt", "TOTAL ASSETS"),
    # LIABILITIES
    ("13", r"accounts?\s*payable", "BegngAcctPrdAccountsPayableAmt", "EndAcctPrdAccountsPayableAmt", "Accounts payable"),
    ("14", r"other\s*current\s*liab", "BegngAcctPrdOtherCurrLiabAmt", "EndAcctPrdOtherCurrLiabAmt", "Other current liabilities"),
    ("15", r"loans?\s*from\s*share|loans?\s*from\s*shr", "BegngAcctPrdLoansFromShrAmt", "EndAcctPrdLoansFromShrAmt", "Loans from shareholders"),
    ("16", r"other\s*liab", "BegngAcctPrdOthLiabilitiesAmt", "EndAcctPrdOthLiabilitiesAmt", "Other liabilities"),
    # EQUITY
    ("17", r"capital\s*stock|common\s*stock", "BegngAcctPrdCommonStockAmt", "EndAcctPrdCommonStockAmt", "Capital stock"),
    ("18", r"paid.in|surplus|capital\s*surplus", "BegngAcctPrdPaidInOrSurplusAmt", "EndAcctPrdPaidInOrSurplusAmt", "Paid-in or capital surplus"),
    ("19", r"retain.*earn", "BegngAcctPrdRtnEarningsAmt", "EndAcctPrdRtnEarningsAmt", "Retained earnings"),
    ("20", r"total\s*liab|total.*equity|total.*shareholders", "BegngAcctPrdTotLiabShrEqtyAmt", "EndAcctPrdTotLiabShrEqtyAmt", "TOTAL LIABILITIES & EQUITY"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), boy_field, eoy_field, line_num, desc)
    for line_num, pattern, boy_field, eoy_field, desc in SCHF_LINE_ITEMS
]

# Flat field lists for XML parsing
ALL_BOY_FIELDS: list[tuple[str, str, str]] = [
    (boy_field, line_num, desc)
    for line_num, _, boy_field, _, desc in SCHF_LINE_ITEMS
]

ALL_EOY_FIELDS: list[tuple[str, str, str]] = [
    (eoy_field, line_num, desc)
    for line_num, _, _, eoy_field, desc in SCHF_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {}
for line_num, _, boy_field, eoy_field, desc in SCHF_LINE_ITEMS:
    FIELD_LOOKUP[boy_field] = (line_num, desc)
    FIELD_LOOKUP[eoy_field] = (line_num, desc)


def identify_line_item(description: str) -> Optional[tuple[str, str, str, str]]:
    """Identify a Schedule F line item from its PDF description text.

    Args:
        description: Text from the PDF row (already cleaned of OIT spacers)

    Returns:
        Tuple of (boy_xml_field, eoy_xml_field, line_number, human_description)
        or None if not identified.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, boy_field, eoy_field, line_num, human_desc in _COMPILED_PATTERNS:
        if pattern.search(desc_clean):
            return (boy_field, eoy_field, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name."""
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"Line {info[0]}: {info[1]}"
    return xml_field

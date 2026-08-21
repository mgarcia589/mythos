"""Schedule C (Income Statement) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule C — Income Statement.

Schedule C is a single-column income statement with ~17 line items:
  Lines 1a-3: Revenue (gross receipts, returns, COGS, gross profit)
  Lines 4-12: Income items (dividends, interest, rents, gains, other, total)
  Lines 13-20: Deductions (compensation, interest, taxes, depreciation, other, total)
  Line 21: Net income per books
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_field_name, human_description)
SCHC_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    ("1a", r"gross\s*receipts|gross\s*sales|receipts\s*or\s*sales", "ForeignGrossReceiptsOrSalesAmt", "Gross receipts or sales"),
    ("1b", r"returns?\s*and\s*allow|allowances", "ForeignReturnsAndAllowancesAmt", "Returns and allowances"),
    ("2", r"cost\s*of\s*goods\s*sold|cogs", "ForeignCostOfGoodsSoldAmt", "Cost of goods sold"),
    ("3", r"gross\s*profit", "ForeignGrossProfitAmt", "Gross profit"),
    ("4", r"dividend\s*income|dividends(?!\s*not)", "ForeignDividendIncomeAmt", "Dividends"),
    ("5", r"interest\s*income(?!\s*exp)", "ForeignInterestIncomeAmt", "Interest"),
    ("8", r"rent.*royalt|net\s*rent|rents\s*and\s*royalt", "ForeignNetRentRoyaltyIncomeAmt", "Rents and royalties"),
    ("9", r"net\s*gain|gain\s*or\s*loss|net\s*loss|capital\s*gain", "ForeignNetGainLossAmt", "Gain or loss"),
    ("11", r"other\s*income(?!\s*tax)", "ForeignOtherIncomeAmt", "Other income"),
    ("12", r"total\s*income", "ForeignTotalIncomeAmt", "Total income"),
    ("13", r"compensation\s*not\s*deduct|compensation(?!\s*of)", "ForeignCompensationNotDeductedAmt", "Compensation not deducted"),
    ("16", r"interest\s*expense|interest\s*deduct", "ForeignInterestExpenseAmt", "Interest expense"),
    ("17", r"(?<!interest\s)taxes(?!\s*deemed)|income\s*taxes|foreign\s*taxes", "ForeignTaxesAmt", "Taxes"),
    ("18", r"depreciation\s*not\s*deduct|depreciation(?!\s*and)", "ForeignDepreciationNotDeductedAmt", "Depreciation"),
    ("19", r"other\s*deduction", "ForeignOtherDeductionsAmt", "Other deductions"),
    ("20", r"total\s*deduction", "ForeignTotalDeductionsAmt", "Total deductions"),
    ("21", r"net\s*income\s*per\s*books|net\s*income(?!\s*(less|from))", "ForeignCYNetIncomePerBookAmt", "Net income per books"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, line_num, desc)
    for line_num, pattern, xml_field, desc in SCHC_LINE_ITEMS
]

# Flat field list for XML parsing: (xml_field, line_num, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, desc in SCHC_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (line_num, desc)
    for line_num, _, xml_field, desc in SCHC_LINE_ITEMS
}


def identify_line_item(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule C line item from its PDF description text.

    Args:
        description: Text from the PDF row (already cleaned of OIT spacers)

    Returns:
        Tuple of (xml_field_name, line_number, human_description) or None.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_field, line_num, human_desc in _COMPILED_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_field, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML field name."""
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"Line {info[0]}: {info[1]}"
    return xml_field

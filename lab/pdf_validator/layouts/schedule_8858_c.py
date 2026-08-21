"""Schedule C (Income Statement) extraction rules for Form 8858.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 8858 Schedule C — Income Statement of FDE/FB.

8858 Sch C is a dual-amount layout: each line has both a
Functional Currency column and a USD column.

XML structure:
  <IRS8858ScheduleC>
    <GrossReceiptsOrSalesIncmStmt>
      <FunctionalCurrencyAmt>...</FunctionalCurrencyAmt>
      <USDollarAmt>...</USDollarAmt>
    </GrossReceiptsOrSalesIncmStmt>
    ...
  </IRS8858ScheduleC>
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_element_name, human_description)
SCH8858C_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    ("1a", r"gross\s*receipts|gross\s*sales|receipts\s*or\s*sales", "GrossReceiptsOrSalesIncmStmt", "Gross receipts or sales"),
    ("1b", r"returns?\s*and\s*allow|allowances", "ReturnsAndAllowancesAmt", "Returns and allowances"),
    ("1c", r"net\s*(?:gross\s*)?receipts|balance.*(?:1a|subtract)", "NetGrossReceiptsAmt", "Net gross receipts (1a - 1b)"),
    ("2", r"cost\s*of\s*goods\s*sold|cogs", "CostOfGoodsSoldAmt", "Cost of goods sold"),
    ("3", r"gross\s*profit", "GrossProfitAmt", "Gross profit (1c - 2)"),
    ("4", r"dividend", "DividendIncomeAmt", "Dividends received"),
    ("5", r"interest\s*income(?!\s*exp)", "InterestIncomeAmt", "Interest income"),
    ("6", r"rents?\s*(?:and|&)?\s*royalt|net\s*rent", "NetRentRoyaltyIncomeAmt", "Rents and royalties"),
    ("7", r"net\s*gain|gain\s*or\s*loss|capital\s*gain", "NetGainLossAmt", "Gain or loss"),
    ("8", r"other\s*income(?!\s*tax)", "OtherIncomeAmt", "Other income"),
    ("9", r"total\s*income", "TotalIncomeAmt", "Total income"),
    ("10", r"total\s*deduct", "TotalDeductionsAmt", "Total deductions"),
    ("21", r"net\s*income|net\s*loss", "NetIncomeLossPerIncomeStmt", "Net income (loss)"),
]

_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_elem, line_num, desc)
    for line_num, pattern, xml_elem, desc in SCH8858C_LINE_ITEMS
]

ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_elem, line_num, desc)
    for line_num, _, xml_elem, desc in SCH8858C_LINE_ITEMS
]

FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_elem: (line_num, desc)
    for line_num, _, xml_elem, desc in SCH8858C_LINE_ITEMS
}


def identify_line_item(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Form 8858 Schedule C line item from its PDF description.

    Returns:
        Tuple of (xml_element_name, line_number, human_description) or None.
    """
    desc_clean = description.strip().lower()
    if not desc_clean:
        return None

    for pattern, xml_elem, line_num, human_desc in _COMPILED_PATTERNS:
        if pattern.search(desc_clean):
            return (xml_elem, line_num, human_desc)
    return None


def get_field_description(xml_field: str) -> str:
    """Get human-readable description for an XML element name."""
    info = FIELD_LOOKUP.get(xml_field)
    if info:
        return f"Line {info[0]}: {info[1]}"
    return xml_field

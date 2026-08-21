"""Schedule H (Current E&P) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule H — Current Earnings and Profits.

Schedule H has ~18 line items organized as:
  Line 1: CY net income per books
  Lines 2a-2i: Adjustments (capital gains, depreciation, taxes, etc.)
  Line 3: Total net additions
  Line 4: Total net subtractions
  Lines 5a-5d: Current E&P computation (local currency → USD)
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_field_name, human_description)
SCHH_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    ("1", r"net\s*income.*books|cy\s*net\s*income|income\s*per\s*books", "ForeignCYNetIncomePerBooksAmt", "CY net income per books"),
    ("2a", r"capital\s*gain|capital\s*loss", "CapitalGainsOrLossesAmt", "Capital gains or losses"),
    ("2b", r"depreciation|amortiz", "DepreciationAndAmortizationAmt", "Depreciation and amortization"),
    ("2c", r"depletion", "DepletionAmt", "Depletion"),
    ("2d", r"invest.*incentive|incentive\s*allow", "InvestmentOrIncentiveAllwncAmt", "Investment or incentive allowance"),
    ("2e", r"statutory\s*reserve|charges.*reserve", "ChargesToStatutoryReservesAmt", "Charges to statutory reserves"),
    ("2f", r"inventory\s*adjust", "InventoryAdjustmentsAmt", "Inventory adjustments"),
    ("2g", r"income\s*tax.*net\s*add|taxes.*net\s*add", "TaxesNetAddnAmt", "Income taxes (net addition)"),
    ("2h", r"foreign\s*currency|currency\s*gain|currency\s*loss", "FrgnCurrencyGainLossAddnAmt", "Foreign currency gains/losses"),
    ("2i(add)", r"other\s*adjust.*net\s*add|other.*addition", "OtherAdjustmentsNetAddnAmt", "Other adjustments (net addition)"),
    ("2i(sub)", r"other\s*adjust.*net\s*sub|other.*subtraction", "OtherAdjustmentsNetSbtrctnAmt", "Other adjustments (net subtraction)"),
    ("3", r"total\s*net\s*add", "TotalNetAdditionsAmt", "Total net additions"),
    ("4", r"total\s*net\s*sub", "TotalNetSubtractionsAmt", "Total net subtractions"),
    ("5a", r"current\s*e.?p(?!\s*in\s*u)(?!\s*after)(?!\s*plus)|current\s*earnings\s*and\s*profits(?!\s*in)", "CurrentEarningsAndProfitsAmt", "Current E&P"),
    ("5b", r"dastm", "DASTMGainOrLossAmt", "DASTM gain or loss"),
    ("5c", r"e.?p.*plus\s*dastm|e.?p.*after\s*dastm|earnings.*plus\s*dastm", "EarningAndPrftPlusDASTMGainAmt", "E&P after DASTM"),
    ("5d", r"e.?p.*in\s*u\.?s|e.?p.*usd|in\s*u\.?s\.?\s*dollar|in\s*us\s*dollar", "CurrEarnAndPrftInUSDollarsAmt", "Current E&P in USD"),
    ("5d(rate)", r"exchange\s*rate|conversion\s*rate", "ExchangeRt", "Exchange rate"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, line_num, desc)
    for line_num, pattern, xml_field, desc in SCHH_LINE_ITEMS
]

# Flat field list for XML parsing: (xml_field, line_num, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, desc in SCHH_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (line_num, desc)
    for line_num, _, xml_field, desc in SCHH_LINE_ITEMS
}


def identify_line_item(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule H line item from its PDF description text.

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

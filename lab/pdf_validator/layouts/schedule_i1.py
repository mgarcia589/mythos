"""Schedule I-1 (GILTI Information) extraction rules and field mapping.

Maps OIT PDF line descriptions to canonical XML field names for
IRS Form 5471 Schedule I-1 — Information for Global Intangible
Low-Taxed Income (GILTI).

Schedule I-1 has ~13 line items organized as:
  Line 1: Gross income
  Lines 2a-2d: Exclusions (ECI, Subpart F, high-taxed, dividends)
  Line 3: Total exclusions
  Line 4: Gross income less exclusions
  Line 5: Allocable deductions
  Line 6: Tested income / tested loss
  Line 8: QBAI
  Lines 9a, 10a: Tested interest expense/income
"""

import re
from typing import Optional

# Line items: (line_number, description_regex, xml_field_name, human_description)
SCHI1_LINE_ITEMS: list[tuple[str, str, str, str]] = [
    ("1", r"^gross\s*income$|^1\b.*gross\s*income", "GrossIncomeAmt", "Gross income"),
    ("2a", r"exclusion.*eci|effectively\s*connected|excl.*eff.*cntd", "ExclGrossIncmEffCntdFCCorpAmt", "Exclusion: ECI"),
    ("2b", r"exclusion.*subpart\s*f|subpart\s*f\s*income|excl.*sub.*f", "ExclGrossIncmSubpartFIncmAmt", "Exclusion: Subpart F income"),
    ("2c", r"exclusion.*high.?tax|high.?taxed\s*income|excl.*hgh.*txd", "ExclGrossIncmHghTxdIncmAmt", "Exclusion: High-taxed income"),
    ("2d", r"exclusion.*dividend|dividend.*received|excl.*dvd.*rcvd", "ExclGrossIncmDvdRcvdAmt", "Exclusion: Dividends received"),
    ("3", r"total\s*exclusion", "TotalExclusionsAmt", "Total exclusions"),
    ("4", r"gross\s*income.*less\s*exclusion|net\s*income.*exclusion", "GrossIncmLessExclusionsAmt", "Gross income less exclusions"),
    ("5", r"allocable.*deduct|deduction.*expense|allocable.*expn", "AllocableDedExpnssAmt", "Allocable deductions"),
    ("6(pos)", r"tested\s*income(?!\s*loss)", "TestedIncomeAmt", "Tested income"),
    ("6(neg)", r"tested\s*loss", "TestedLossAmt", "Tested loss"),
    ("8", r"\bqbai\b|qualified\s*business\s*asset", "QBAIAmt", "QBAI"),
    ("9a", r"tested\s*interest\s*expense|interest\s*expense", "TestedInterestExpenseAmt", "Tested interest expense"),
    ("10a", r"tested\s*interest\s*income|interest\s*income", "TestedInterestIncomeAmt", "Tested interest income"),
]

# Compiled regex for faster matching
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(pattern, re.IGNORECASE), xml_field, line_num, desc)
    for line_num, pattern, xml_field, desc in SCHI1_LINE_ITEMS
]

# Flat field list for XML parsing: (xml_field, line_num, description)
ALL_FIELDS: list[tuple[str, str, str]] = [
    (xml_field, line_num, desc)
    for line_num, _, xml_field, desc in SCHI1_LINE_ITEMS
]

# Lookup: xml_field -> (line_number, description)
FIELD_LOOKUP: dict[str, tuple[str, str]] = {
    xml_field: (line_num, desc)
    for line_num, _, xml_field, desc in SCHI1_LINE_ITEMS
}


def identify_line_item(description: str) -> Optional[tuple[str, str, str]]:
    """Identify a Schedule I-1 line item from its PDF description text.

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

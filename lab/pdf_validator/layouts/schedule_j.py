"""Schedule J specific extraction rules and field mapping.

Maps PDF column headers and pool identifiers to the canonical XML field names
used by the reconciler.
"""

import re
from typing import Optional

# Pool mapping: various PDF representations -> canonical XML group name
POOL_IDENTIFIERS = {
    # By column letter
    "(a)": "Post2017EPNotPrevTaxedGrp",
    "(b)": "Post2017EPPrevTaxedGrp",
    "(c)": "Section951APTEPGrp",
    "(d)": "Section245AdPTEPGrp",
    "(e)(i)": "Section951a1APTEPGrp",
    "(e)(ii)": "Section951a1BPTEPGrp",
    "(e)(iii)": "Section959c2PTEPGrp",
    "(f)": "Section965aPTEPGrp",
    "(g)": "Section965bPTEPGrp",
    "(h)": "TotalSection964AEPGrp",
    "(i)": "Post1986UndistributedEarnGrp",
    "(j)": "HoveringDeficitDedSspndTaxGrp",
}

# By description keywords (fallback when letter not found)
POOL_KEYWORDS = {
    "post-2017.*not prev": "Post2017EPNotPrevTaxedGrp",
    "post-2017.*prev taxed": "Post2017EPPrevTaxedGrp",
    "951a ptep|gilti": "Section951APTEPGrp",
    "245a.*ptep": "Section245AdPTEPGrp",
    "951.*a.*1.*a.*ptep|subpart f ptep": "Section951a1APTEPGrp",
    "951.*a.*1.*b.*ptep": "Section951a1BPTEPGrp",
    "959.*c.*2.*ptep|pre-2018": "Section959c2PTEPGrp",
    "965.*a.*ptep": "Section965aPTEPGrp",
    "965.*b.*ptep": "Section965bPTEPGrp",
    "total.*964|total section": "TotalSection964AEPGrp",
    "post-1986|undistributed": "Post1986UndistributedEarnGrp",
    "hovering|deficit.*suspend": "HoveringDeficitDedSspndTaxGrp",
}

# Column header mapping: PDF header text -> canonical field name
COLUMN_HEADERS = {
    "beg bal": "BeginningYearBalanceAmt",
    "beginning": "BeginningYearBalanceAmt",
    "begin bal": "BeginningYearBalanceAmt",
    "boy": "BeginningYearBalanceAmt",
    "adj beg": "AdjustedBeginningBalanceAmt",
    "adjusted": "AdjustedBeginningBalanceAmt",
    "cy e&p": "CurrentYearEPDeficitAmt",
    "current year": "CurrentYearEPDeficitAmt",
    "current e&p": "CurrentYearEPDeficitAmt",
    "reclass": "ReclassifiedSect959c2EPAmt",
    "reclassified": "ReclassifiedSect959c2EPAmt",
    "end bal": "BalanceBeginningNextYearAmt",
    "ending": "BalanceBeginningNextYearAmt",
    "end of year": "BalanceEndOfYearAmt",
    "eoy": "BalanceEndOfYearAmt",
    "beg next yr": "BalanceBeginningNextYearAmt",
    "boy next": "BalanceBeginningNextYearAmt",
}

# OIT's Schedule J column numbers (I through XXIII) to XML pool mapping
# These are the column numbers visible in OIT's grid view
OIT_COLUMN_NUMBERS = {
    "I": "Post2017EPNotPrevTaxedGrp",       # col (a) in IRS form
    "II": "Post2017EPPrevTaxedGrp",          # col (b)
    # III-XVII are various sub-categories not always shown
    "XVIII": "Section951APTEPGrp",           # col (c) Section 951A PTEP
    "XIX": "Section245AdPTEPGrp",            # col (d)
    "XX": "Section951a1APTEPGrp",            # col (e)(i)
    "XXI": "Section951a1BPTEPGrp",           # col (e)(ii)
    "XXII": "TotalSection964AEPGrp",         # col (h) Total
    "XXIII": "Post1986UndistributedEarnGrp", # col (i)
}


def identify_pool(field_text: str) -> Optional[str]:
    """Identify which E&P pool a PDF field represents.

    Args:
        field_text: The text from the PDF row (may contain letter, description, or both)

    Returns:
        Canonical XML group name, or None if unidentified.
    """
    text = field_text.strip()

    # Try compound letter match first: (e)(i), (e)(viii), etc.
    compound_match = re.match(r"^\(([a-j])\)\(([ivx]+)\)", text, re.IGNORECASE)
    if compound_match:
        compound = f"({compound_match.group(1)})({compound_match.group(2)})"
        if compound in POOL_IDENTIFIERS:
            return POOL_IDENTIFIERS[compound]

    # Try single letter match: (a), (b), etc.
    letter_match = re.match(r"^\(([a-j])\)", text)
    if letter_match:
        letter = f"({letter_match.group(1)})"
        if letter in POOL_IDENTIFIERS:
            return POOL_IDENTIFIERS[letter]

    # Try OIT column number (Roman numerals)
    roman_match = re.match(r"^(X{0,2}(?:IX|IV|V?I{0,3}))\b", text, re.IGNORECASE)
    if roman_match:
        numeral = roman_match.group(1).upper()
        if numeral in OIT_COLUMN_NUMBERS:
            return OIT_COLUMN_NUMBERS[numeral]

    # Fallback: keyword matching on description
    text_lower = text.lower()
    for pattern, pool_name in POOL_KEYWORDS.items():
        if re.search(pattern, text_lower):
            return pool_name

    return None


def identify_column(header_text: str) -> Optional[str]:
    """Map a PDF column header to a canonical XML field name.

    Args:
        header_text: Column header text from the PDF table

    Returns:
        Canonical XML field name, or None if unidentified.
    """
    text = header_text.strip().lower()
    for pattern, field_name in COLUMN_HEADERS.items():
        if pattern in text:
            return field_name
    return None

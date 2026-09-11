"""PDF Table Extraction — Parses OIT-generated Schedule J PDFs.

OIT generates IRS Form 5471 Schedule J as a 3-page layout per entity:
  Page 1: Columns (a)-(d) and (e)(i)-(ii) — lines 1a through 14
  Page 2: Columns (e)(iii)-(vii) and (e)(viii)-(x) + (f) Total — lines 1a through 14
  Page 3: Part II (Recapture) — usually empty

The extraction uses pdfplumber's table detection which reliably parses
OIT's ruled table format.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger(__name__)


@dataclass
class SchJEntity:
    """Extracted Schedule J data for one entity/basket."""
    entity_name: str
    reference_id: str
    basket: str
    pools: dict = field(default_factory=dict)

    @property
    def pool_count(self) -> int:
        return len(self.pools)

    @property
    def value_count(self) -> int:
        return sum(len(fields) for fields in self.pools.values())


@dataclass
class SchFEntity:
    """Extracted Schedule F (Balance Sheet) data for one entity."""
    entity_name: str
    reference_id: str
    functional_currency: str = "USD"
    # xml_field_name -> value (one entry per BOY field, one per EOY field)
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchGEntity:
    """Extracted Schedule G (Other Information) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchHEntity:
    """Extracted Schedule H (Current E&P) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchI1Entity:
    """Extracted Schedule I-1 (GILTI) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class Page1AEntity:
    """Extracted Page 1 + Schedule A data for one entity."""
    entity_name: str
    reference_id: str
    # Page 1 numeric fields (e.g. VotingStockOwnedPct)
    page1_fields: dict[str, float] = field(default_factory=dict)
    # Schedule A stock data: "{class_desc}|{xml_field}" -> value
    stock_fields: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.page1_fields) + len(self.stock_fields)


@dataclass
class SchBEntity:
    """Extracted Schedule B (Shareholders) data for one entity."""
    entity_name: str
    reference_id: str
    # Part I US shareholders: "{shareholder_name}|ShareholderEIN" -> EIN as float
    us_shareholders: dict[str, float] = field(default_factory=dict)
    # Part II Direct shareholders: "{shareholder_name}|{class}|{field}" -> share count
    direct_shareholders: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.us_shareholders) + len(self.direct_shareholders)


@dataclass
class SchCEntity:
    """Extracted Schedule C (Income Statement) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchEEntity:
    """Extracted Schedule E (Foreign Taxes) data for one entity."""
    entity_name: str
    reference_id: str
    basket: str = "GEN"
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchIEntity:
    """Extracted Schedule I (Summary of Shareholder's Income) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchPEntity:
    """Extracted Schedule P (Previously Taxed E&P) data for one entity."""
    entity_name: str
    reference_id: str
    basket: str = "GEN"
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class SchREntity:
    """Extracted Schedule R (Distributions) data for one entity."""
    entity_name: str
    reference_id: str
    lines: dict[str, float] = field(default_factory=dict)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class ExtractionMetrics:
    """Metrics from a PDF extraction run."""
    total_pages: int = 0
    pages_processed: int = 0
    entities_found: int = 0
    entities_with_data: int = 0
    tables_detected: int = 0
    tables_failed: int = 0
    values_extracted: int = 0
    warnings: list[str] = field(default_factory=list)


# Match by description keywords (after cleaning "m" spacers)
FIELD_BY_DESCRIPTION = [
    (r"balance at begin.*year.*prior|balance at begin.*year.*report|balance at begin.*year.*schedule|^1a\b.*balance", "BeginningYearBalanceAmt"),
    (r"adjusted beginning balance|^1c\b", "AdjustedBeginningBalanceAmt"),
    (r"current year e&p|deficit in e&p|^3\b.*e&p", "CurrentYearEPDeficitAmt"),
    (r"total current.*accumulated|^7\b.*total", "TotalCurrentAccumulatedEPAmt"),
    (r"reclassified to.*959.*c.*2.*from.*959.*c.*3|reclassified.*section 959.*c.*2.*e&p.*from|^8\b.*reclassified", "ReclassifiedSect959c2EPAmt"),
    (r"actual distribution|^9\b.*distribution", "ActualDistributionsAmt"),
    (r"reclassified to.*959.*c.*1.*from.*959.*c.*2|^11\b.*reclassified", "ReclassifiedTo959c1Amt"),
    (r"balance at beginning of next year|^14\b.*balance.*next", "BalanceBeginningNextYearAmt"),
]

# Page 1 column mapping (table column index -> pool name)
PAGE1_COLUMNS = {
    1: "Post2017EPNotPrevTaxedGrp",
    2: "Post1986UndistributedEarnGrp",
    3: "Pre1987EPNotPrevTaxedGrp",
    4: "HoveringDeficitDedSspndTaxGrp",
    5: "ReclassifiedSect965aPTEPGrp",
}

# Page 2 bottom section: columns (e)(viii)-(x)
PAGE2_BOTTOM_COLUMNS = {
    0: "Section951APTEPGrp",
    2: "Section245AdPTEPGrp",
    4: "Section951a1APTEPGrp",
}

PAGE2_TOTAL_COLUMN = "TotalSection964AEPGrp"

# Schedule J page detection patterns (case-insensitive)
SCHJ_PAGE1_PATTERNS = [
    re.compile(r"SCHEDULE\s*J", re.IGNORECASE),
    re.compile(r"Accumulated\s+E&?P", re.IGNORECASE),
]

SCHJ_PAGE2_INDICATORS = [
    re.compile(r"page\s*2", re.IGNORECASE),
    re.compile(r"\(viii\)", re.IGNORECASE),
    re.compile(r"951A\s+PTEP", re.IGNORECASE),
]

SCHJ_PAGE3_INDICATORS = [
    re.compile(r"Part\s+II", re.IGNORECASE),
    re.compile(r"Recapture", re.IGNORECASE),
]

# Schedule F (Balance Sheet) page detection
SCHF_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*F", re.IGNORECASE),
    re.compile(r"Balance\s+Sheet", re.IGNORECASE),
]

# Schedule G (Other Information) page detection
SCHG_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*G", re.IGNORECASE),
    re.compile(r"Other\s+Information", re.IGNORECASE),
]

# Schedule H (Current E&P) page detection
SCHH_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*H", re.IGNORECASE),
    re.compile(r"Current\s+Earnings|Earnings\s+(?:and|&)\s+Profits", re.IGNORECASE),
]

# Schedule I-1 (GILTI) page detection
SCHI1_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*I-?1", re.IGNORECASE),
    re.compile(r"Global\s+Intangible|GILTI|Tested\s+Income", re.IGNORECASE),
]

# Page 1 / Schedule A detection
PAGE1A_PAGE_PATTERNS = [
    re.compile(r"Form\s*5471|Information\s+Return", re.IGNORECASE),
    re.compile(r"Stock\s+of\s+the\s+Foreign|Schedule\s*A", re.IGNORECASE),
]

# Schedule B (Shareholders) page detection
SCHB_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*B", re.IGNORECASE),
    re.compile(r"Shareholder|U\.?S\.?\s+Person", re.IGNORECASE),
]

# Schedule C (Income Statement) page detection
SCHC_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*C", re.IGNORECASE),
    re.compile(r"Income\s+Statement", re.IGNORECASE),
]

# Schedule E (Foreign Taxes) page detection
SCHE_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*E", re.IGNORECASE),
    re.compile(r"Taxes?\s+Paid|Excess\s+Profits", re.IGNORECASE),
]

# Schedule I (Shareholder's Income) page detection
SCHI_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*I\b(?!-)", re.IGNORECASE),
    re.compile(r"Shareholder.?s\s+Income|CFC\s+Income|Subpart\s*F", re.IGNORECASE),
]

# Schedule P (Previously Taxed E&P) page detection
SCHP_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*P", re.IGNORECASE),
    re.compile(r"Previously\s+Taxed|PTEP", re.IGNORECASE),
]

# Schedule R (Distributions) page detection
SCHR_PAGE_PATTERNS = [
    re.compile(r"SCHEDULE\s*R", re.IGNORECASE),
    re.compile(r"Distribution", re.IGNORECASE),
]

# ─── Form 8858 page detection ──────────────────────────────────────────────

# 8858 Schedule C (Income Statement)
SCH8858C_PAGE_PATTERNS = [
    re.compile(r"(?:Form\s*)?8858", re.IGNORECASE),
    re.compile(r"Income\s+Statement|Schedule\s*C", re.IGNORECASE),
]

# 8858 Schedule F (Balance Sheet)
SCH8858F_PAGE_PATTERNS = [
    re.compile(r"(?:Form\s*)?8858", re.IGNORECASE),
    re.compile(r"Balance\s+Sheet|Schedule\s*F", re.IGNORECASE),
]

# 8858 Schedule H (Current E&P)
SCH8858H_PAGE_PATTERNS = [
    re.compile(r"(?:Form\s*)?8858", re.IGNORECASE),
    re.compile(r"Current\s+Earnings|Schedule\s*H", re.IGNORECASE),
]

# Disambiguation: if page matches both 5471 and 8858 patterns
FORM_8858_INDICATOR = re.compile(
    r"Form\s*8858|Disregarded\s+Entity|Foreign\s+Branch|FDE|FB", re.IGNORECASE
)

# Row offset -> field name mapping for page 2 bottom section
PAGE2_ROW_FIELD_MAP = {
    0: "BeginningYearBalanceAmt",
    2: "AdjustedBeginningBalanceAmt",
    5: "CurrentYearEPDeficitAmt",
    10: "TotalCurrentAccumulatedEPAmt",
    11: "ReclassifiedSect959c2EPAmt",
    17: "BalanceBeginningNextYearAmt",
}


def parse_number(text: str) -> Optional[float]:
    """Parse formatted number from PDF.

    Handles OIT formats:
      - Parenthesized negatives: (1,234)
      - Leading minus: -1,234
      - Comma thousands: 6,243,100
      - Trailing period: 15,272,537.
      - Dash/em-dash for zero: -, —, –
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    # Remove trailing periods (OIT artifact)
    text = text.rstrip(".")
    if not text:
        return None

    # Zero/empty indicators
    if text in ("", "-", "—", "–", "0", "--"):
        return None

    # Negative in parentheses: (1,234,567)
    m = re.match(r"^\(([\d,]+(?:\.\d+)?)\)$", text)
    if m:
        return -float(m.group(1).replace(",", ""))

    # Standard number (may have leading minus)
    m = re.match(r"^(-?)([\d,]+(?:\.\d+)?)$", text)
    if m:
        digits = m.group(2).replace(",", "")
        if not digits:
            return None
        val = float(digits)
        return -val if m.group(1) == "-" else val

    return None


class PDFExtractor:
    """Extract Schedule J data from OIT-generated PDF batch export.

    Handles the specific layout quirks of Thomson Reuters ONESOURCE:
      - Interleaved "m" spacer characters in text
      - 3-page layout per entity (main data, PTEP pools, recapture)
      - Multi-entity batch PDFs
    """

    def __init__(self, pdf_path: Path | str, schedule: str = "J"):
        if pdfplumber is None:
            raise ImportError("pdfplumber is required: pip install pdfplumber")
        self.path = Path(pdf_path)
        self.schedule = schedule.upper()
        if not self.path.exists():
            raise FileNotFoundError(f"PDF not found: {self.path}")
        self._metrics = ExtractionMetrics()
        self._page_filter: Optional[set[int]] = None

    @property
    def metrics(self) -> ExtractionMetrics:
        """Access extraction metrics from the last run."""
        return self._metrics

    def _should_process_page(self, page_index: int) -> bool:
        """Check if a page should be processed (respects page filter)."""
        if self._page_filter is None:
            return True
        return page_index in self._page_filter

    def extract(self, pages: Optional[list[int]] = None) -> pd.DataFrame:
        """Extract schedule data from PDF.

        Args:
            pages: Optional list of 0-indexed page numbers to process.
                   If None, processes all pages. Used by PDFRouter to pass
                   only the pages belonging to a specific schedule.

        Returns DataFrame with columns:
          entity_name, reference_id, basket, pool_name, field_name, value
        """
        self._page_filter = set(pages) if pages is not None else None
        if self.schedule == "A":
            entities = self._extract_page1a_entities()
            return self._page1a_to_dataframe(entities)
        if self.schedule == "B":
            entities = self._extract_schb_entities()
            return self._schb_to_dataframe(entities)
        if self.schedule == "C":
            entities = self._extract_schc_entities()
            return self._single_column_to_dataframe(entities)
        if self.schedule == "E":
            entities = self._extract_sche_entities()
            return self._basket_entity_to_dataframe(entities)
        if self.schedule == "F":
            entities = self._extract_schf_entities()
            return self._schf_to_dataframe(entities)
        if self.schedule == "G":
            entities = self._extract_schg_entities()
            return self._schg_to_dataframe(entities)
        if self.schedule == "H":
            entities = self._extract_schh_entities()
            return self._schh_to_dataframe(entities)
        if self.schedule == "I":
            entities = self._extract_schi_entities()
            return self._single_column_to_dataframe(entities)
        if self.schedule == "I1":
            entities = self._extract_schi1_entities()
            return self._schi1_to_dataframe(entities)
        if self.schedule == "P":
            entities = self._extract_schp_entities()
            return self._basket_entity_to_dataframe(entities)
        if self.schedule == "R":
            entities = self._extract_schr_entities()
            return self._single_column_to_dataframe(entities)
        if self.schedule == "8858_C":
            entities = self._extract_8858c_entities()
            return self._8858c_to_dataframe(entities)
        if self.schedule == "8858_F":
            entities = self._extract_8858f_entities()
            return self._schf_to_dataframe(entities)
        if self.schedule == "8858_H":
            entities = self._extract_8858h_entities()
            return self._schh_to_dataframe(entities)
        entities = self._extract_all_entities()
        return self._to_dataframe(entities)

    def extract_entities(self):
        """Extract and return list of entity objects."""
        if self.schedule == "A":
            return self._extract_page1a_entities()
        if self.schedule == "B":
            return self._extract_schb_entities()
        if self.schedule == "C":
            return self._extract_schc_entities()
        if self.schedule == "E":
            return self._extract_sche_entities()
        if self.schedule == "F":
            return self._extract_schf_entities()
        if self.schedule == "G":
            return self._extract_schg_entities()
        if self.schedule == "H":
            return self._extract_schh_entities()
        if self.schedule == "I":
            return self._extract_schi_entities()
        if self.schedule == "I1":
            return self._extract_schi1_entities()
        if self.schedule == "P":
            return self._extract_schp_entities()
        if self.schedule == "R":
            return self._extract_schr_entities()
        if self.schedule == "8858_C":
            return self._extract_8858c_entities()
        if self.schedule == "8858_F":
            return self._extract_8858f_entities()
        if self.schedule == "8858_H":
            return self._extract_8858h_entities()
        return self._extract_all_entities()

    def _extract_all_entities(self) -> list[SchJEntity]:
        """Scan PDF, extract all Sch J entity sections."""
        entities = []
        current_entity: Optional[SchJEntity] = None
        page_in_schj = 0

        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                page_type = self._detect_page_type(text, page_in_schj)

                if page_type == "schj_page1":
                    # Save previous entity
                    if current_entity and current_entity.pools:
                        entities.append(current_entity)
                        self._metrics.entities_with_data += 1

                    entity_name, ref_id, basket = self._parse_header(text)
                    current_entity = SchJEntity(
                        entity_name=entity_name,
                        reference_id=ref_id,
                        basket=basket,
                    )
                    self._metrics.entities_found += 1
                    page_in_schj = 1

                    if not ref_id:
                        self._metrics.warnings.append(
                            f"Page {i + 1}: Could not parse reference ID from header"
                        )

                    self._extract_page1(page, current_entity)
                    self._metrics.pages_processed += 1

                elif page_type == "schj_page2" and current_entity:
                    page_in_schj = 2
                    self._extract_page2(page, text, current_entity)
                    self._metrics.pages_processed += 1

                elif page_type == "schj_page3" and current_entity:
                    page_in_schj = 3
                    self._metrics.pages_processed += 1

                elif page_in_schj > 0:
                    if current_entity and current_entity.pools:
                        entities.append(current_entity)
                        self._metrics.entities_with_data += 1
                        current_entity = None
                    page_in_schj = 0

            # Don't forget last entity
            if current_entity and current_entity.pools:
                entities.append(current_entity)
                self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.value_count for e in entities)
        logger.info(
            "Extraction complete: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )

        return entities

    def _detect_page_type(self, text: str, current_state: int) -> str:
        """Detect what type of Schedule J page this is.

        Returns: "schj_page1", "schj_page2", "schj_page3", or "other"
        """
        first_300 = text[:300]

        # Page 1: Must have SCHEDULE J + "Accumulated" or similar indicator
        if all(p.search(text) for p in SCHJ_PAGE1_PATTERNS):
            return "schj_page1"

        # Page 2: Must be in Sch J context and have page 2 indicators
        if current_state >= 1:
            if any(p.search(first_300) for p in SCHJ_PAGE2_INDICATORS):
                return "schj_page2"

            if all(p.search(first_300) for p in SCHJ_PAGE3_INDICATORS):
                return "schj_page3"

        return "other"

    def _parse_header(self, text: str) -> tuple[str, str, str]:
        """Extract entity name, ref ID, and basket from Sch J page 1 header.

        OIT encodes ref IDs with interleaved "m" characters:
          "ALPHA TOPCO LTD m m m ... Cm0m00m2m m m" -> C0002
        """
        entity_name = ""
        ref_id = ""
        basket = "GEN"

        lines = text.split("\n")
        for i, line in enumerate(lines):
            if "Name of foreign corporation" in line:
                if i + 1 < len(lines):
                    next_line = lines[i + 1]

                    # Entity name: everything before the "m m m" spacer block
                    name_match = re.match(r"^(.+?)(?:\s+m\s+){3,}", next_line)
                    if name_match:
                        entity_name = name_match.group(1).strip()
                    elif next_line.strip():
                        # Fallback: take first word-block as entity name
                        entity_name = next_line.strip()[:60]

                    # Ref ID: split by repeated "m " spacers, find last token
                    parts = re.split(r"(?:\s*m\s*){4,}", next_line.rstrip())
                    for p in reversed(parts):
                        p = p.strip().rstrip("I").strip()
                        if p and len(p) < 20:
                            candidate = "".join(c for c in p if c.isupper() or c.isdigit())
                            if candidate and re.match(r"^[A-Z]{1,3}\d{2,5}$", candidate):
                                ref_id = candidate
                                break
                break

        # Basket: look for GEN or PAS on the Separate Category line
        for line in lines[:25]:
            if "Separate Category" in line or "separate category" in line.lower():
                line_upper = line.upper()
                if "GEN" in line_upper or "GENERAL" in line_upper:
                    basket = "GEN"
                elif "PAS" in line_upper or "PASSIVE" in line_upper:
                    basket = "PAS"
                break

        return entity_name, ref_id, basket

    def _extract_page1(self, page, entity: SchJEntity):
        """Extract columns (a)-(d) and (e)(i) from page 1 table."""
        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            logger.debug("Page 1 for %s: no tables detected, trying text fallback",
                         entity.reference_id)
            self._extract_page1_text_fallback(page, entity)
            return

        self._metrics.tables_detected += 1

        # Find the main data table (largest one with >10 rows)
        main_table = max(tables, key=lambda t: len(t))
        if len(main_table) < 10:
            self._metrics.warnings.append(
                f"{entity.reference_id} page 1: main table has only {len(main_table)} rows"
            )
            return

        # Map rows to field names by description
        for row_idx, row in enumerate(main_table):
            if not row or not row[0]:
                continue

            description = str(row[0]).replace("\n", " ").strip()
            field_name = self._identify_field(description)
            if not field_name:
                continue

            # Extract values from each column
            for col_idx, pool_name in PAGE1_COLUMNS.items():
                if col_idx < len(row):
                    val = parse_number(str(row[col_idx] or ""))
                    if val is not None:
                        entity.pools.setdefault(pool_name, {})[field_name] = val

    def _extract_page1_text_fallback(self, page, entity: SchJEntity):
        """Fallback: extract page 1 data from raw text when tables fail."""
        text = page.extract_text() or ""
        lines = text.split("\n")

        for line in lines:
            cleaned = self._clean_oit_text(line)
            field_name = self._identify_field(cleaned)
            if not field_name:
                continue

            # Extract numbers from the line
            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            # Map positionally to pools
            pool_names = list(PAGE1_COLUMNS.values())
            for idx, val in enumerate(values[:len(pool_names)]):
                entity.pools.setdefault(pool_names[idx], {})[field_name] = val

    def _extract_page2(self, page, text: str, entity: SchJEntity):
        """Extract columns (e)(viii)-(x) and (f) Total from page 2.

        Page 2 layout (table with ~39 rows):
          Rows 0-18: Top section (e)(iii)-(vii) — usually empty
          Row ~19: "(e) Previously Taxed E&P" separator
          Row ~20: Headers — "(viii) Section 951A PTEP", "(ix)", "(x)"
          Rows 21+: Data rows for lines 1a through 14
        """
        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            logger.debug("Page 2 for %s: no tables detected", entity.reference_id)
            return

        self._metrics.tables_detected += 1

        main_table = max(tables, key=lambda t: len(t))
        if len(main_table) < 20:
            self._metrics.warnings.append(
                f"{entity.reference_id} page 2: table has only {len(main_table)} rows"
            )
            return

        # Find the "(viii)" header row
        bottom_header_idx = None
        for i, row in enumerate(main_table):
            row_text = " ".join(str(c or "") for c in row)
            if "(viii)" in row_text and "951A" in row_text:
                bottom_header_idx = i
                break

        if bottom_header_idx is None:
            # Alternative detection: look for "Section 951A PTEP" text
            for i, row in enumerate(main_table):
                row_text = " ".join(str(c or "") for c in row).lower()
                if "951a" in row_text and "ptep" in row_text:
                    bottom_header_idx = i
                    break

        if bottom_header_idx is None:
            self._metrics.warnings.append(
                f"{entity.reference_id} page 2: could not find (viii) header row"
            )
            return

        # Data rows start right after the header
        data_start = bottom_header_idx + 1

        for row_offset, field_name in PAGE2_ROW_FIELD_MAP.items():
            row_idx = data_start + row_offset
            if row_idx >= len(main_table):
                break

            row = main_table[row_idx]
            for col_idx, pool_name in PAGE2_BOTTOM_COLUMNS.items():
                if col_idx < len(row):
                    val = parse_number(str(row[col_idx] or ""))
                    if val is not None:
                        entity.pools.setdefault(pool_name, {})[field_name] = val

        # Extract (f) Total Section 964(a)
        self._extract_total_column(text, entity)

    def _extract_total_column(self, text: str, entity: SchJEntity):
        """Extract (f) Total Section 964(a) column from page 2 text."""
        lines = text.split("\n")
        total_values = []
        in_total = False

        for line in lines:
            if "Total Section 964" in line or ("(f)" in line and "combine" in line.lower()):
                in_total = True
                continue
            if in_total:
                val = parse_number(line.strip())
                if val is not None:
                    total_values.append(val)
                elif re.match(r"^\d{1,2}[a-c]?$", line.strip()):
                    total_values.append(None)

        # Map (f) Total values to fields by position
        total_field_sequence = [
            "BeginningYearBalanceAmt",
            None,  # 1b
            "AdjustedBeginningBalanceAmt",
            None, None,  # 2a, 2b
            "CurrentYearEPDeficitAmt",
            None, None, None, None,  # 4-6
            "TotalCurrentAccumulatedEPAmt",
            None,  # 8
            None, None, None, None, None,  # 9-13
            "BalanceBeginningNextYearAmt",
        ]

        field_idx = 0
        for val in total_values:
            if field_idx >= len(total_field_sequence):
                break
            if val is not None and total_field_sequence[field_idx]:
                entity.pools.setdefault(PAGE2_TOTAL_COLUMN, {})[total_field_sequence[field_idx]] = val
            field_idx += 1

    def _identify_field(self, description: str) -> Optional[str]:
        """Identify XML field name from row description text.

        OIT inserts "m" characters as spacers in PDF text, so we clean them first.
        """
        desc_clean = self._clean_oit_text(description).lower()
        for pattern, field_name in FIELD_BY_DESCRIPTION:
            if re.search(pattern, desc_clean):
                return field_name
        return None

    @staticmethod
    def _clean_oit_text(text: str) -> str:
        """Remove interleaved 'm' spacers and normalize whitespace."""
        cleaned = re.sub(r"\bm\b", "", text)
        return re.sub(r"\s+", " ", cleaned).strip()

    # =========================================================================
    # Schedule F (Balance Sheet) extraction
    # =========================================================================

    def _extract_schf_entities(self) -> list[SchFEntity]:
        """Scan PDF for Schedule F pages and extract balance sheet data."""
        from lab.pdf_validator.layouts.schedule_f import identify_line_item

        entities: list[SchFEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_schf_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, fc = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule F page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchFEntity(
                    entity_name=entity_name,
                    reference_id=ref_id,
                    functional_currency=fc,
                )

                self._extract_schf_table(page, text, entity)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule F extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_schf_page(self, text: str) -> bool:
        """Check if a page is a Schedule F balance sheet page."""
        return all(p.search(text) for p in SCHF_PAGE_PATTERNS)

    def _parse_schf_header(self, text: str) -> tuple[str, str, str]:
        """Extract entity name, ref ID, and functional currency from Sch F header.

        Returns (entity_name, reference_id, functional_currency)
        """
        entity_name = ""
        ref_id = ""
        fc = "USD"

        lines = text.split("\n")

        for i, line in enumerate(lines):
            # Look for entity name / ref ID in header area
            if "Name of foreign corporation" in line or "foreign corporation" in line.lower():
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # Same OIT "m" spacer pattern as Schedule J
                    name_match = re.match(r"^(.+?)(?:\s+m\s+){3,}", next_line)
                    if name_match:
                        entity_name = name_match.group(1).strip()
                    elif next_line.strip():
                        entity_name = next_line.strip()[:60]

                    parts = re.split(r"(?:\s*m\s*){4,}", next_line.rstrip())
                    for p in reversed(parts):
                        p = p.strip().rstrip("I").strip()
                        if p and len(p) < 20:
                            candidate = "".join(c for c in p if c.isupper() or c.isdigit())
                            if candidate and re.match(r"^[A-Z]{1,3}\d{2,5}$", candidate):
                                ref_id = candidate
                                break
                break

        # Functional currency
        for line in lines[:20]:
            fc_match = re.search(r"(?:Functional\s*Currency|FC)[:\s]*([A-Z]{3})", line, re.IGNORECASE)
            if fc_match:
                fc = fc_match.group(1).upper()
                break

        # Fallback: try to find ref_id from "Reference ID" line
        if not ref_id:
            for line in lines[:15]:
                rid_match = re.search(r"Reference\s*ID[:\s]*([A-Z]{1,3}\d{2,5})", line, re.IGNORECASE)
                if rid_match:
                    ref_id = rid_match.group(1)
                    break

        return entity_name, ref_id, fc

    def _extract_schf_table(self, page, text: str, entity: SchFEntity):
        """Extract BOY and EOY values from a Schedule F table.

        OIT Schedule F layout:
          Column 0: Line number or description
          Column 1 (or -2): BOY amount (Beginning of annual accounting period)
          Column 2 (or -1): EOY amount (End of annual accounting period)
        """
        from lab.pdf_validator.layouts.schedule_f import identify_line_item

        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            logger.debug("Schedule F for %s: no tables detected, trying text fallback",
                         entity.reference_id)
            self._extract_schf_text_fallback(text, entity)
            return

        self._metrics.tables_detected += 1

        # Use the largest table
        main_table = max(tables, key=lambda t: len(t))
        if len(main_table) < 5:
            self._metrics.warnings.append(
                f"{entity.reference_id} Sch F: table has only {len(main_table)} rows"
            )
            return

        # Detect column layout: find BOY/EOY header row
        boy_col_idx, eoy_col_idx = self._detect_schf_columns(main_table)

        for row in main_table:
            if not row or not row[0]:
                continue

            description = str(row[0]).replace("\n", " ").strip()
            description_clean = self._clean_oit_text(description)

            line_info = identify_line_item(description_clean)
            if not line_info:
                continue

            boy_field, eoy_field, line_num, _ = line_info

            # Extract BOY value
            if boy_col_idx is not None and boy_col_idx < len(row):
                val = parse_number(str(row[boy_col_idx] or ""))
                if val is not None:
                    entity.lines[boy_field] = val

            # Extract EOY value
            if eoy_col_idx is not None and eoy_col_idx < len(row):
                val = parse_number(str(row[eoy_col_idx] or ""))
                if val is not None:
                    entity.lines[eoy_field] = val

    def _detect_schf_columns(self, table: list) -> tuple[Optional[int], Optional[int]]:
        """Detect which column indices contain BOY and EOY values.

        Returns (boy_column_index, eoy_column_index).
        Checks header rows for "Beginning" / "End" text.
        Fallback: assumes second-to-last = BOY, last = EOY.
        """
        for row in table[:5]:
            if not row:
                continue
            row_text = [str(c or "").lower() for c in row]
            boy_idx = None
            eoy_idx = None

            for idx, cell in enumerate(row_text):
                if "begin" in cell or "boy" in cell or "(a)" in cell:
                    boy_idx = idx
                elif "end" in cell or "eoy" in cell or "(b)" in cell:
                    eoy_idx = idx

            if boy_idx is not None or eoy_idx is not None:
                return (boy_idx, eoy_idx)

        # Fallback: assume last two numeric columns are BOY, EOY
        if table and len(table[0]) >= 3:
            return (len(table[0]) - 2, len(table[0]) - 1)

        return (None, None)

    def _extract_schf_text_fallback(self, text: str, entity: SchFEntity):
        """Fallback: extract Schedule F data from raw text lines."""
        from lab.pdf_validator.layouts.schedule_f import identify_line_item

        lines = text.split("\n")
        for line in lines:
            cleaned = self._clean_oit_text(line)
            line_info = identify_line_item(cleaned)
            if not line_info:
                continue

            boy_field, eoy_field, _, _ = line_info

            # Extract all numbers from the line
            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            if len(values) >= 2:
                entity.lines[boy_field] = values[-2]
                entity.lines[eoy_field] = values[-1]
            elif len(values) == 1:
                # Single value — assume EOY (most common request)
                entity.lines[eoy_field] = values[0]

    # =========================================================================
    # Schedule G (Other Information) extraction
    # =========================================================================

    def _extract_schg_entities(self) -> list[SchGEntity]:
        """Scan PDF for Schedule G pages and extract indicator/amount data."""
        from lab.pdf_validator.layouts.schedule_g import identify_line_item, parse_indicator, FIELD_TYPE

        entities: list[SchGEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_schg_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule G page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchGEntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_schg_from_text(text, entity)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule G extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_schg_page(self, text: str) -> bool:
        """Check if a page is a Schedule G page."""
        return all(p.search(text) for p in SCHG_PAGE_PATTERNS)

    def _extract_schg_from_text(self, text: str, entity: SchGEntity):
        """Extract Schedule G data from text.

        Schedule G is question-based (Yes/No indicators + one amount).
        OIT renders indicators as "X" for Yes or blank for No.
        """
        from lab.pdf_validator.layouts.schedule_g import identify_line_item, parse_indicator, FIELD_TYPE

        lines = text.split("\n")
        for line in lines:
            cleaned = self._clean_oit_text(line)
            line_info = identify_line_item(cleaned)
            if not line_info:
                continue

            xml_field, field_type, _, _ = line_info

            if field_type == "indicator":
                # Look for "X", "Yes", or similar in the line after the description
                indicator_match = re.search(r"\b(X|Yes|Y)\b", line, re.IGNORECASE)
                entity.lines[xml_field] = 1.0 if indicator_match else 0.0
            else:
                # Amount field — extract the last number
                numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
                parsed = [parse_number(n) for n in numbers]
                values = [v for v in parsed if v is not None]
                if values:
                    entity.lines[xml_field] = values[-1]

    # =========================================================================
    # Schedule H (Current E&P) extraction
    # =========================================================================

    def _extract_schh_entities(self) -> list[SchHEntity]:
        """Scan PDF for Schedule H pages and extract E&P calculation data."""
        from lab.pdf_validator.layouts.schedule_h import identify_line_item

        entities: list[SchHEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_schh_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule H page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchHEntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_single_column_table(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule H extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_schh_page(self, text: str) -> bool:
        """Check if a page is a Schedule H page."""
        return all(p.search(text) for p in SCHH_PAGE_PATTERNS)

    # =========================================================================
    # Schedule I-1 (GILTI) extraction
    # =========================================================================

    def _extract_schi1_entities(self) -> list[SchI1Entity]:
        """Scan PDF for Schedule I-1 pages and extract GILTI data."""
        from lab.pdf_validator.layouts.schedule_i1 import identify_line_item

        entities: list[SchI1Entity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_schi1_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule I-1 page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchI1Entity(entity_name=entity_name, reference_id=ref_id)

                self._extract_single_column_table(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule I-1 extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_schi1_page(self, text: str) -> bool:
        """Check if a page is a Schedule I-1 page."""
        return all(p.search(text) for p in SCHI1_PAGE_PATTERNS)

    # =========================================================================
    # Page 1 / Schedule A extraction
    # =========================================================================

    def _extract_page1a_entities(self) -> list[Page1AEntity]:
        """Scan PDF for Page 1 / Schedule A pages and extract entity + stock data."""
        from lab.pdf_validator.layouts.page1_schedule_a import (
            parse_percentage, parse_share_count,
        )

        entities: list[Page1AEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_page1a_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Page 1/Schedule A detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = Page1AEntity(entity_name=entity_name, reference_id=ref_id)

                # Extract voting stock % from page 1 text
                self._extract_page1_fields(text, entity, parse_percentage)

                # Extract Schedule A stock table
                self._extract_scha_stock(page, text, entity, parse_share_count)

                if entity.line_count > 0:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Page 1/Schedule A extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_page1a_page(self, text: str) -> bool:
        """Check if a page is a Form 5471 Page 1 with Schedule A."""
        return all(p.search(text) for p in PAGE1A_PAGE_PATTERNS)

    def _extract_page1_fields(self, text: str, entity: Page1AEntity, parse_pct):
        """Extract Page 1 numeric fields (voting stock %) from text."""
        lines = text.split("\n")
        for line in lines:
            cleaned = self._clean_oit_text(line)
            # Look for voting stock percentage
            if re.search(r"voting\s*stock|direct.*percent", cleaned, re.IGNORECASE):
                numbers = re.findall(r"\d+\.?\d*", line)
                for num_str in numbers:
                    val = parse_pct(num_str)
                    if val is not None and val > 0:
                        entity.page1_fields["VotingStockOwnedPct"] = val
                        break

    def _extract_scha_stock(self, page, text: str, entity: Page1AEntity, parse_cnt):
        """Extract Schedule A stock class data from table or text."""
        tables = page.extract_tables()

        # Look for the Schedule A stock table
        scha_table = None
        for table in (tables or []):
            if len(table) < 2:
                continue
            # Schedule A table typically has columns: class, begin shares, end shares
            header_text = " ".join(str(c or "") for c in (table[0] or []))
            if re.search(r"class|stock|shares|begin|end|annual", header_text, re.IGNORECASE):
                scha_table = table
                break

        if scha_table:
            self._metrics.tables_detected += 1
            self._extract_scha_from_table(scha_table, entity, parse_cnt)
        else:
            # Text fallback
            self._extract_scha_from_text(text, entity, parse_cnt)

    def _extract_scha_from_table(self, table: list, entity: Page1AEntity, parse_cnt):
        """Extract stock data from a Schedule A table."""
        # Skip header row(s)
        data_rows = table[1:] if table else []

        for row in data_rows:
            if not row or len(row) < 3:
                continue

            # First column is stock class description
            class_desc = str(row[0] or "").strip()
            class_desc = self._clean_oit_text(class_desc).upper()
            if not class_desc or class_desc.lower() in ("", "total", "none"):
                continue

            # Second column: beginning share count
            beg_str = str(row[1] or "").strip() if len(row) > 1 else ""
            beg_val = parse_cnt(beg_str)
            if beg_val is not None:
                entity.stock_fields[f"{class_desc}|AnnualAcctPeriodBeginShareCnt"] = beg_val

            # Third column (or last): end share count
            end_idx = 2 if len(row) > 2 else len(row) - 1
            end_str = str(row[end_idx] or "").strip()
            end_val = parse_cnt(end_str)
            if end_val is not None:
                entity.stock_fields[f"{class_desc}|AnnualAcctPeriodEndShareCnt"] = end_val

    def _extract_scha_from_text(self, text: str, entity: Page1AEntity, parse_cnt):
        """Fallback: extract stock data from raw text when table detection fails."""
        lines = text.split("\n")
        current_class = None

        for line in lines:
            cleaned = self._clean_oit_text(line)

            # Detect stock class description lines (all caps, short, descriptive)
            if re.match(r"^[A-Z][A-Z\s]+$", cleaned.strip()) and len(cleaned.strip()) < 40:
                candidate = cleaned.strip()
                if candidate and candidate not in ("SCHEDULE A", "STOCK", "TOTAL"):
                    current_class = candidate
                    continue

            if current_class:
                numbers = re.findall(r"[\d,]+", line)
                parsed = [parse_cnt(n) for n in numbers]
                values = [v for v in parsed if v is not None]

                if len(values) >= 2:
                    entity.stock_fields[f"{current_class}|AnnualAcctPeriodBeginShareCnt"] = values[0]
                    entity.stock_fields[f"{current_class}|AnnualAcctPeriodEndShareCnt"] = values[1]
                    current_class = None
                elif len(values) == 1:
                    if "begin" in line.lower():
                        entity.stock_fields[f"{current_class}|AnnualAcctPeriodBeginShareCnt"] = values[0]
                    elif "end" in line.lower():
                        entity.stock_fields[f"{current_class}|AnnualAcctPeriodEndShareCnt"] = values[0]

    # =========================================================================
    # Schedule B (Shareholders) extraction
    # =========================================================================

    def _extract_schb_entities(self) -> list[SchBEntity]:
        """Scan PDF for Schedule B pages and extract shareholder data."""
        from lab.pdf_validator.layouts.schedule_b import (
            normalize_shareholder_name, parse_ein,
        )
        from lab.pdf_validator.layouts.page1_schedule_a import parse_share_count

        entities: list[SchBEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not self._is_schb_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule B page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchBEntity(entity_name=entity_name, reference_id=ref_id)

                # Extract from tables
                self._extract_schb_from_page(page, text, entity,
                                             normalize_shareholder_name, parse_ein,
                                             parse_share_count)

                if entity.line_count > 0:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule B extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_schb_page(self, text: str) -> bool:
        """Check if a page is a Schedule B page."""
        return all(p.search(text) for p in SCHB_PAGE_PATTERNS)

    def _extract_schb_from_page(self, page, text: str, entity: SchBEntity,
                                normalize_name, parse_ein_fn, parse_cnt):
        """Extract Schedule B data from a page (table or text fallback)."""
        tables = page.extract_tables()

        if tables:
            self._metrics.tables_detected += 1
            for table in tables:
                if len(table) < 2:
                    continue
                self._extract_schb_from_table(table, text, entity,
                                             normalize_name, parse_ein_fn, parse_cnt)
        else:
            self._extract_schb_from_text(text, entity, normalize_name, parse_ein_fn, parse_cnt)

    def _extract_schb_from_table(self, table: list, text: str, entity: SchBEntity,
                                 normalize_name, parse_ein_fn, parse_cnt):
        """Extract shareholder data from a Schedule B table."""
        # Determine if this is Part I or Part II based on surrounding text
        # and column structure
        header_text = " ".join(str(c or "") for c in (table[0] or []))

        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            # Try to extract shareholder name (first column)
            name_raw = str(row[0] or "").strip()
            name_clean = self._clean_oit_text(name_raw)
            sh_name = normalize_name(name_clean)

            if not sh_name or sh_name in ("NONE", "TOTAL", "N/A"):
                continue

            # Check for EIN in the row
            row_text = " ".join(str(c or "") for c in row)
            ein = parse_ein_fn(row_text)
            if ein:
                entity.us_shareholders[f"{sh_name}|ShareholderEIN"] = float(ein)

            # Check for share counts (look for numeric columns with stock class)
            # Pattern: name | class | begin | end  OR  name | begin | end
            if len(row) >= 4:
                class_col = str(row[1] or "").strip()
                class_clean = self._clean_oit_text(class_col).upper()
                if class_clean and not class_clean.isdigit() and len(class_clean) < 40:
                    beg_str = str(row[2] or "").strip() if len(row) > 2 else ""
                    end_str = str(row[3] or "").strip() if len(row) > 3 else ""
                    beg = parse_cnt(beg_str)
                    end = parse_cnt(end_str)
                    if beg is not None:
                        entity.direct_shareholders[f"{sh_name}|{class_clean}|AnnualAcctPeriodBeginShareCnt"] = beg
                    if end is not None:
                        entity.direct_shareholders[f"{sh_name}|{class_clean}|AnnualAcctPeriodEndShareCnt"] = end
            elif len(row) >= 3:
                # name | begin | end (class may be in a previous row)
                beg_str = str(row[1] or "").strip()
                end_str = str(row[2] or "").strip()
                beg = parse_cnt(beg_str)
                end = parse_cnt(end_str)
                if beg is not None or end is not None:
                    stock_class = "STOCK"
                    if beg is not None:
                        entity.direct_shareholders[f"{sh_name}|{stock_class}|AnnualAcctPeriodBeginShareCnt"] = beg
                    if end is not None:
                        entity.direct_shareholders[f"{sh_name}|{stock_class}|AnnualAcctPeriodEndShareCnt"] = end

    def _extract_schb_from_text(self, text: str, entity: SchBEntity,
                                normalize_name, parse_ein_fn, parse_cnt):
        """Fallback: extract Schedule B data from raw text."""
        from lab.pdf_validator.layouts.schedule_b import EIN_PATTERN

        lines = text.split("\n")
        current_name = None

        for line in lines:
            cleaned = self._clean_oit_text(line)

            # Detect EIN pattern
            ein_match = EIN_PATTERN.search(line)
            if ein_match and current_name:
                ein_digits = ein_match.group(1).replace("-", "")
                entity.us_shareholders[f"{current_name}|ShareholderEIN"] = float(ein_digits)
                continue

            # Detect shareholder name (all caps, reasonable length)
            if re.match(r"^[A-Z][A-Z\s\d&.,]+$", cleaned.strip()) and 3 < len(cleaned.strip()) < 60:
                candidate = normalize_name(cleaned)
                if candidate and candidate not in ("SCHEDULE B", "PART I", "PART II", "NONE"):
                    current_name = candidate
                    continue

            # Look for share count numbers on lines with current_name context
            if current_name:
                numbers = re.findall(r"[\d,]+", line)
                parsed = [parse_cnt(n) for n in numbers]
                values = [v for v in parsed if v is not None]
                if len(values) >= 2:
                    entity.direct_shareholders[f"{current_name}|STOCK|AnnualAcctPeriodBeginShareCnt"] = values[0]
                    entity.direct_shareholders[f"{current_name}|STOCK|AnnualAcctPeriodEndShareCnt"] = values[1]

    # =========================================================================
    # Schedule C (Income Statement) extraction
    # =========================================================================

    def _extract_schc_entities(self) -> list[SchCEntity]:
        """Scan PDF for Schedule C pages and extract income statement data."""
        from lab.pdf_validator.layouts.schedule_c import identify_line_item

        entities: list[SchCEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not all(p.search(text) for p in SCHC_PAGE_PATTERNS):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule C page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchCEntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_single_column_table(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule C extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    # =========================================================================
    # Schedule E (Foreign Taxes) extraction
    # =========================================================================

    def _extract_sche_entities(self) -> list[SchEEntity]:
        """Scan PDF for Schedule E pages and extract tax data."""
        from lab.pdf_validator.layouts.schedule_e import (
            identify_line_item, detect_group_context,
        )

        entities: list[SchEEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not all(p.search(text) for p in SCHE_PAGE_PATTERNS):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule E page detected but no ref ID found"
                    )
                    continue

                # Detect basket from Separate Category line
                basket = "GEN"
                for line in text.split("\n")[:25]:
                    if "separate category" in line.lower():
                        if "PAS" in line.upper() or "PASSIVE" in line.upper():
                            basket = "PAS"
                        break

                self._metrics.entities_found += 1
                entity = SchEEntity(entity_name=entity_name, reference_id=ref_id, basket=basket)

                # Extract with group context tracking
                self._extract_sche_from_text(text, entity, identify_line_item, detect_group_context)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule E extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _extract_sche_from_text(self, text: str, entity: SchEEntity,
                                identify_fn, detect_group_fn):
        """Extract Schedule E data tracking income group context."""
        lines = text.split("\n")
        current_group = None

        for line in lines:
            cleaned = self._clean_oit_text(line)

            # Try to detect group header
            group = detect_group_fn(cleaned)
            if group:
                current_group = group

            # Try to identify a field
            line_info = identify_fn(cleaned, group_context=current_group)
            if not line_info:
                continue

            xml_field, _, _ = line_info

            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            if values:
                entity.lines[xml_field] = values[-1]

    # =========================================================================
    # Schedule I (Shareholder's Income) extraction
    # =========================================================================

    def _extract_schi_entities(self) -> list[SchIEntity]:
        """Scan PDF for Schedule I pages and extract CFC income summary data."""
        from lab.pdf_validator.layouts.schedule_i import identify_line_item, parse_indicator, FIELD_TYPE

        entities: list[SchIEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not all(p.search(text) for p in SCHI_PAGE_PATTERNS):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule I page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchIEntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_schi_from_text(text, entity, identify_line_item, FIELD_TYPE)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule I extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _extract_schi_from_text(self, text: str, entity: SchIEntity, identify_fn, field_types):
        """Extract Schedule I data (amounts + indicators) from text."""
        lines = text.split("\n")
        for line in lines:
            cleaned = self._clean_oit_text(line)
            line_info = identify_fn(cleaned)
            if not line_info:
                continue

            xml_field, field_type, _, _ = line_info

            if field_type == "indicator":
                indicator_match = re.search(r"\b(X|Yes|Y)\b", line, re.IGNORECASE)
                entity.lines[xml_field] = 1.0 if indicator_match else 0.0
            else:
                numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
                parsed = [parse_number(n) for n in numbers]
                values = [v for v in parsed if v is not None]
                if values:
                    entity.lines[xml_field] = values[-1]

    # =========================================================================
    # Schedule P (Previously Taxed E&P) extraction
    # =========================================================================

    def _extract_schp_entities(self) -> list[SchPEntity]:
        """Scan PDF for Schedule P pages and extract PTEP pool data."""
        from lab.pdf_validator.layouts.schedule_p import (
            identify_line_item, detect_pool_context,
        )

        entities: list[SchPEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not all(p.search(text) for p in SCHP_PAGE_PATTERNS):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule P page detected but no ref ID found"
                    )
                    continue

                # Detect basket
                basket = "GEN"
                for line in text.split("\n")[:25]:
                    if "separate category" in line.lower():
                        if "PAS" in line.upper() or "PASSIVE" in line.upper():
                            basket = "PAS"
                        break

                self._metrics.entities_found += 1
                entity = SchPEntity(entity_name=entity_name, reference_id=ref_id, basket=basket)

                self._extract_schp_from_text(text, entity, identify_line_item, detect_pool_context)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule P extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _extract_schp_from_text(self, text: str, entity: SchPEntity,
                                identify_fn, detect_pool_fn):
        """Extract Schedule P data tracking pool group context."""
        lines = text.split("\n")
        current_pool = None

        for line in lines:
            cleaned = self._clean_oit_text(line)

            # Try to detect pool header
            pool = detect_pool_fn(cleaned)
            if pool:
                current_pool = pool

            # Try to identify a field
            line_info = identify_fn(cleaned, pool_context=current_pool)
            if not line_info:
                continue

            compound_key, _, _ = line_info

            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            if values:
                entity.lines[compound_key] = values[-1]

    # =========================================================================
    # Schedule R (Distributions) extraction
    # =========================================================================

    def _extract_schr_entities(self) -> list[SchREntity]:
        """Scan PDF for Schedule R pages and extract distribution data."""
        from lab.pdf_validator.layouts.schedule_r import (
            identify_column, make_compound_key, normalize_distribution_desc,
            AMOUNT_FIELDS,
        )

        entities: list[SchREntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = page.extract_text() or ""

                if not all(p.search(text) for p in SCHR_PAGE_PATTERNS):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_schf_header(text)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: Schedule R page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchREntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_schr_from_page(page, text, entity,
                                             identify_column, make_compound_key,
                                             normalize_distribution_desc, AMOUNT_FIELDS)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "Schedule R extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _extract_schr_from_page(self, page, text: str, entity: SchREntity,
                                identify_col_fn, make_key_fn,
                                normalize_desc_fn, amount_fields):
        """Extract Schedule R distribution rows from table or text."""
        tables = page.extract_tables()

        if tables:
            self._metrics.tables_detected += 1
            for table in tables:
                if len(table) < 2:
                    continue
                self._extract_schr_from_table(table, entity, identify_col_fn,
                                             make_key_fn, normalize_desc_fn, amount_fields)
        else:
            self._extract_schr_from_text(text, entity, make_key_fn,
                                        normalize_desc_fn, amount_fields)

    def _extract_schr_from_table(self, table: list, entity: SchREntity,
                                 identify_col_fn, make_key_fn,
                                 normalize_desc_fn, amount_fields):
        """Extract Schedule R distributions from a table."""
        if not table or len(table) < 2:
            return

        # Map column indices to field names using header row
        col_map: dict[int, str] = {}
        header = table[0]
        for idx, cell in enumerate(header or []):
            if cell:
                field = identify_col_fn(str(cell))
                if field:
                    col_map[idx] = field

        # Extract data rows
        for row_idx, row in enumerate(table[1:], start=1):
            if not row:
                continue

            # Get row identifier from first column or row index
            row_id = str(row_idx)
            if row[0]:
                desc = self._clean_oit_text(str(row[0]))
                norm = normalize_desc_fn(desc)
                if norm:
                    row_id = norm

            for col_idx, field_name in col_map.items():
                if field_name not in amount_fields:
                    continue
                if col_idx < len(row) and row[col_idx]:
                    val = parse_number(str(row[col_idx]))
                    if val is not None:
                        key = make_key_fn(row_id, field_name)
                        entity.lines[key] = val

    def _extract_schr_from_text(self, text: str, entity: SchREntity,
                                make_key_fn, normalize_desc_fn, amount_fields):
        """Fallback: extract Schedule R distributions from raw text."""
        lines = text.split("\n")
        row_idx = 0

        for line in lines:
            cleaned = self._clean_oit_text(line)
            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            if len(values) >= 2:
                row_idx += 1
                row_id = str(row_idx)
                entity.lines[make_key_fn(row_id, "DistributionFuncCurAmt")] = values[0]
                if len(values) >= 2:
                    entity.lines[make_key_fn(row_id, "DistributionFromEPFuncCurAmt")] = values[1]

    # =========================================================================
    # Shared single-column extraction (H, I-1)
    # =========================================================================

    def _extract_single_column_table(self, page, text: str, entity, identify_fn):
        """Extract a single-value-column schedule (H or I-1).

        These schedules have one amount column (no BOY/EOY split).
        The identify_fn returns (xml_field, line_num, desc) or None.
        """
        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            logger.debug("Single-col schedule for %s: no tables, using text fallback",
                         entity.reference_id)
            self._extract_single_column_text_fallback(text, entity, identify_fn)
            return

        self._metrics.tables_detected += 1

        main_table = max(tables, key=lambda t: len(t))
        if len(main_table) < 3:
            self._metrics.warnings.append(
                f"{entity.reference_id}: table has only {len(main_table)} rows"
            )
            return

        # Quality check: if table has only 1 column, it's garbage (e.g. just line numbers)
        max_cols = max((len(row) for row in main_table if row), default=0)
        if max_cols < 2:
            logger.debug("Single-col schedule for %s: table is single-column garbage, text fallback",
                         entity.reference_id)
            self._extract_single_column_text_fallback(text, entity, identify_fn)
            return

        # Find the value column (last numeric column, or explicitly labeled "Amount")
        val_col_idx = self._detect_value_column(main_table)

        for row in main_table:
            if not row or not row[0]:
                continue

            description = str(row[0]).replace("\n", " ").strip()
            description_clean = self._clean_oit_text(description)

            line_info = identify_fn(description_clean)
            if not line_info:
                continue

            xml_field, _, _ = line_info

            if val_col_idx is not None and val_col_idx < len(row):
                val = parse_number(str(row[val_col_idx] or ""))
                if val is not None:
                    entity.lines[xml_field] = val

        # If table produced nothing, fall through to text fallback
        if not entity.lines:
            logger.debug("Single-col schedule for %s: table produced 0 values, text fallback",
                         entity.reference_id)
            self._extract_single_column_text_fallback(text, entity, identify_fn)

    def _detect_value_column(self, table: list) -> Optional[int]:
        """Detect which column index contains the amount values.

        For single-column schedules (H, I-1), there's typically one amount column.
        Returns the last column index (most common layout).
        """
        if table and len(table[0]) >= 2:
            return len(table[0]) - 1
        return None

    def _extract_single_column_text_fallback(self, text: str, entity, identify_fn):
        """Fallback: extract single-column schedule data from raw text."""
        lines = text.split("\n")
        for line in lines:
            cleaned = self._clean_oit_text(line)
            line_info = identify_fn(cleaned)
            if not line_info:
                continue

            xml_field, _, _ = line_info

            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [v for v in parsed if v is not None]

            # Filter out small integers that are likely IRS line numbers (1-20).
            # Keep: amounts >= 100, decimals (exchange rates), or negatives.
            significant = [
                (v, n) for v, n in zip(values, numbers)
                if abs(v) >= 100 or "." in n or v < 0
            ]
            if significant:
                entity.lines[xml_field] = significant[-1][0]

    # =========================================================================
    # DataFrame conversions
    # =========================================================================

    def _page1a_to_dataframe(self, entities: list[Page1AEntity]) -> pd.DataFrame:
        """Convert Page 1 / Schedule A entities to flat DataFrame."""
        consolidated: dict[str, Page1AEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for k, v in entity.page1_fields.items():
                    existing.page1_fields.setdefault(k, v)
                for k, v in entity.stock_fields.items():
                    existing.stock_fields.setdefault(k, v)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.page1_fields.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })
            for compound_field, value in entity.stock_fields.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": compound_field,
                    "field_name": compound_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _schb_to_dataframe(self, entities: list[SchBEntity]) -> pd.DataFrame:
        """Convert Schedule B entities to flat DataFrame."""
        consolidated: dict[str, SchBEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for k, v in entity.us_shareholders.items():
                    existing.us_shareholders.setdefault(k, v)
                for k, v in entity.direct_shareholders.items():
                    existing.direct_shareholders.setdefault(k, v)

        records = []
        for entity in consolidated.values():
            for compound_field, value in entity.us_shareholders.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": compound_field,
                    "field_name": compound_field,
                    "value": value,
                })
            for compound_field, value in entity.direct_shareholders.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": compound_field,
                    "field_name": compound_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _schg_to_dataframe(self, entities: list[SchGEntity]) -> pd.DataFrame:
        """Convert Schedule G entities to flat DataFrame."""
        consolidated: dict[str, SchGEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _schh_to_dataframe(self, entities: list[SchHEntity]) -> pd.DataFrame:
        """Convert Schedule H entities to flat DataFrame."""
        consolidated: dict[str, SchHEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _schi1_to_dataframe(self, entities: list[SchI1Entity]) -> pd.DataFrame:
        """Convert Schedule I-1 entities to flat DataFrame."""
        consolidated: dict[str, SchI1Entity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _schf_to_dataframe(self, entities: list[SchFEntity]) -> pd.DataFrame:
        """Convert Schedule F entities to flat DataFrame.

        Uses same schema as Schedule J for compatibility with reconciler:
          entity_name, reference_id, basket, pool_name, field_name, value
        """
        # Consolidate duplicates
        consolidated: dict[str, SchFEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                from lab.pdf_validator.layouts.schedule_f import get_field_description
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    # =========================================================================
    # Generic DataFrame converters for new schedules
    # =========================================================================

    def _single_column_to_dataframe(self, entities) -> pd.DataFrame:
        """Convert single-column entities (C, I, R) to flat DataFrame.

        Works for any entity with .entity_name, .reference_id, .lines dict.
        Uses basket="N/A".
        """
        consolidated: dict[str, object] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    def _basket_entity_to_dataframe(self, entities) -> pd.DataFrame:
        """Convert basket-aware entities (E, P) to flat DataFrame.

        Works for any entity with .entity_name, .reference_id, .basket, .lines dict.
        """
        consolidated: dict[tuple[str, str], object] = {}
        for entity in entities:
            key = (entity.reference_id, entity.basket)
            if key not in consolidated:
                consolidated[key] = entity
            else:
                existing = consolidated[key]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": entity.basket,
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    # =========================================================================
    # Schedule J helpers (continued)
    # =========================================================================

    def _to_dataframe(self, entities: list[SchJEntity]) -> pd.DataFrame:
        """Convert extracted entities to flat DataFrame.

        Consolidates duplicate entity/basket pairs (first occurrence wins per field).
        """
        # Consolidate duplicates
        consolidated: dict[tuple[str, str], SchJEntity] = {}
        for entity in entities:
            key = (entity.reference_id, entity.basket)
            if key not in consolidated:
                consolidated[key] = entity
            else:
                existing = consolidated[key]
                for pool, fields in entity.pools.items():
                    if pool not in existing.pools:
                        existing.pools[pool] = fields
                    else:
                        for f, v in fields.items():
                            existing.pools[pool].setdefault(f, v)

        # Flatten to records
        records = []
        for entity in consolidated.values():
            for pool_name, fields in entity.pools.items():
                for field_name, value in fields.items():
                    records.append({
                        "entity_name": entity.entity_name,
                        "reference_id": entity.reference_id,
                        "basket": entity.basket,
                        "pool_name": pool_name,
                        "field_name": field_name,
                        "value": value,
                    })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    # =========================================================================
    # Form 8858 entity context (two-pass approach)
    # =========================================================================

    def _build_8858_entity_context(self, pages_text: list[str]) -> dict[str, tuple[str, str]]:
        """First pass: build entity_name -> (ref_id, fc) mapping from main form pages.

        OIT 8858 batch PDFs have a main form page with the ref ID, followed by
        schedule continuation pages that only have entity name + EIN in the header.
        """
        context: dict[str, tuple[str, str]] = {}

        for text in pages_text:
            if "Reference ID" not in text:
                continue
            if not re.search(r"8858|Disregarded\s+Entit|Foreign\s+Branch", text, re.IGNORECASE):
                continue

            lines = text.split("\n")
            entity_name = ""
            ref_id = ""
            fc = "USD"

            # Find ref ID: it's the last token on the line after "b(2) Reference ID"
            for i, line in enumerate(lines):
                if "Reference ID" in line and "b(2)" in line:
                    # Ref ID is the last alphanumeric token on the NEXT line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        tokens = next_line.split()
                        for t in reversed(tokens):
                            candidate = t.strip().rstrip(",.")
                            if re.match(r"^[A-Z]{2,6}\d{2,6}[A-Z]{0,4}$", candidate):
                                ref_id = candidate
                                break
                    break

            # Find entity name from "1a Name and address" section
            for i, line in enumerate(lines):
                if "Name and address of FDE" in line or "1a Name" in line:
                    if i + 1 < len(lines):
                        name_line = lines[i + 1]
                        # Entity name is before the EIN (XX-XXXXXXX)
                        ein_match = re.search(r"\d{2}-\d{7}", name_line)
                        if ein_match:
                            entity_name = name_line[:ein_match.start()].strip()
                        else:
                            entity_name = name_line.strip()[:60]
                    break

            # Find functional currency — look for "j Functional currency" header
            # then FC code is the last token on the NEXT line
            for i, line in enumerate(lines):
                if re.search(r"j\s+Functional\s+currency", line, re.IGNORECASE):
                    if i + 1 < len(lines):
                        next_tokens = lines[i + 1].split()
                        if next_tokens:
                            candidate = next_tokens[-1].strip()
                            if re.match(r"^[A-Z]{3}$", candidate):
                                fc = candidate
                    break

            if entity_name and ref_id:
                # Normalize: store by canonical name (stripped)
                context[entity_name.upper()] = (ref_id, fc)

        return context

    def _parse_8858_header(self, text: str, context: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
        """Parse entity name and resolve ref_id from context for 8858 continuation pages.

        Continuation pages have first line: "ENTITY NAME   EIN" or just "ENTITY NAME"
        Returns (entity_name, ref_id, functional_currency).
        """
        lines = text.split("\n")
        if not lines:
            return "", "", "USD"

        first_line = lines[0].strip()

        # Remove EIN pattern from first line to get entity name
        ein_match = re.search(r"\s+\d{2}-\d{7}\s*$", first_line)
        if ein_match:
            entity_name = first_line[:ein_match.start()].strip()
        else:
            # Remove "Page" suffix if present
            page_match = re.search(r"\s*Page\s*\d+\s*$", first_line, re.IGNORECASE)
            if page_match:
                entity_name = first_line[:page_match.start()].strip()
            else:
                entity_name = first_line.strip()

        # Remove "Form 8858 (Rev..." prefix if present
        form_prefix = re.match(r"Form\s+8858.*?\)\s*", entity_name, re.IGNORECASE)
        if form_prefix:
            entity_name = entity_name[form_prefix.end():].strip()

        # Lookup in context
        ref_id = ""
        fc = "USD"
        lookup_key = entity_name.upper()
        if lookup_key in context:
            ref_id, fc = context[lookup_key]
        else:
            # Try substring match
            for ctx_name, (ctx_ref, ctx_fc) in context.items():
                if ctx_name in lookup_key or lookup_key in ctx_name:
                    ref_id, fc = ctx_ref, ctx_fc
                    break

        return entity_name, ref_id, fc

    # =========================================================================
    # Form 8858 Schedule C (Income Statement — dual-amount)
    # =========================================================================

    def _extract_8858c_entities(self) -> list[SchCEntity]:
        """Scan PDF for 8858 Schedule C pages and extract income statement data.

        8858 Sch C has two amount columns per line: Functional Currency and USD.
        When FC=USD, only one column is present.
        """
        from lab.pdf_validator.layouts.schedule_8858_c import identify_line_item

        entities: list[SchCEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            # First pass: build entity context
            all_texts = [page.extract_text() or "" for page in pdf.pages]
            context = self._build_8858_entity_context(all_texts)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = all_texts[i]

                if not self._is_8858c_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, fc = self._parse_8858_header(text, context)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: 8858 Schedule C page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchCEntity(entity_name=entity_name, reference_id=ref_id)

                if fc == "USD":
                    self._extract_8858c_text_fallback(text, entity, identify_line_item, fc="USD")
                else:
                    self._extract_8858c_dual_amounts(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "8858 Schedule C extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_8858c_page(self, text: str) -> bool:
        """Check if a page is a Form 8858 Schedule C page."""
        if not all(p.search(text) for p in SCH8858C_PAGE_PATTERNS):
            return False
        return bool(FORM_8858_INDICATOR.search(text))

    def _extract_8858c_dual_amounts(self, page, text: str, entity: SchCEntity, identify_fn):
        """Extract dual-amount (FC + USD) from 8858 Schedule C.

        OIT renders two amount columns per line item.
        We store: "{xml_elem}_FC" and "{xml_elem}_USD".
        """
        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            self._extract_8858c_text_fallback(text, entity, identify_fn)
            return

        self._metrics.tables_detected += 1
        main_table = max(tables, key=lambda t: len(t))

        fc_col, usd_col = self._detect_8858c_columns(main_table)

        for row in main_table:
            if not row or not row[0]:
                continue

            description = str(row[0]).replace("\n", " ").strip()
            description_clean = self._clean_oit_text(description)

            line_info = identify_fn(description_clean)
            if not line_info:
                continue

            xml_elem, _, _ = line_info

            if fc_col is not None and fc_col < len(row):
                val = parse_number(str(row[fc_col] or ""))
                if val is not None:
                    entity.lines[f"{xml_elem}_FC"] = val

            if usd_col is not None and usd_col < len(row):
                val = parse_number(str(row[usd_col] or ""))
                if val is not None:
                    entity.lines[f"{xml_elem}_USD"] = val

        # If table produced nothing, fall through to text fallback
        if not entity.lines:
            logger.debug("8858 Sch C dual for %s: table produced 0 values, text fallback",
                         entity.reference_id)
            self._extract_8858c_text_fallback(text, entity, identify_fn)

    def _detect_8858c_columns(self, table: list) -> tuple[Optional[int], Optional[int]]:
        """Detect FC and USD column indices in 8858 Sch C table."""
        for row in table[:5]:
            if not row:
                continue
            row_text = [str(c or "").lower() for c in row]
            fc_idx = None
            usd_idx = None

            for idx, cell in enumerate(row_text):
                if "functional" in cell or "fc" == cell.strip() or "(a)" in cell:
                    fc_idx = idx
                elif "u.s." in cell or "usd" in cell or "dollar" in cell or "(b)" in cell:
                    usd_idx = idx

            if fc_idx is not None or usd_idx is not None:
                return (fc_idx, usd_idx)

        if table and len(table[0]) >= 3:
            return (len(table[0]) - 2, len(table[0]) - 1)

        return (None, None)

    def _extract_8858c_text_fallback(self, text: str, entity: SchCEntity, identify_fn,
                                       fc: str = "OTHER"):
        """Fallback: extract 8858 Sch C from raw text.

        For dual-currency (fc != USD): last two significant numbers = FC, USD.
        For fc=USD: last significant number = USD only.
        Stops at Schedule C-1 boundary.
        """
        lines = text.split("\n")
        for line in lines:
            if re.search(r"Schedule\s*C-1", line):
                break

            cleaned = self._clean_oit_text(line)
            line_info = identify_fn(cleaned)
            if not line_info:
                continue

            xml_elem, _, _ = line_info
            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [(v, n) for v, n in zip(parsed, numbers)
                      if v is not None and (abs(v) >= 100 or "." in n or v < 0)]

            if fc == "USD":
                if values:
                    entity.lines[f"{xml_elem}_USD"] = values[-1][0]
            else:
                if len(values) >= 2:
                    entity.lines[f"{xml_elem}_FC"] = values[-2][0]
                    entity.lines[f"{xml_elem}_USD"] = values[-1][0]
                elif len(values) == 1:
                    entity.lines[f"{xml_elem}_USD"] = values[0][0]

    def _8858c_to_dataframe(self, entities: list[SchCEntity]) -> pd.DataFrame:
        """Convert 8858 Sch C entities to flat DataFrame."""
        consolidated: dict[str, SchCEntity] = {}
        for entity in entities:
            if entity.reference_id not in consolidated:
                consolidated[entity.reference_id] = entity
            else:
                existing = consolidated[entity.reference_id]
                for field_name, value in entity.lines.items():
                    existing.lines.setdefault(field_name, value)

        records = []
        for entity in consolidated.values():
            for xml_field, value in entity.lines.items():
                records.append({
                    "entity_name": entity.entity_name,
                    "reference_id": entity.reference_id,
                    "basket": "N/A",
                    "pool_name": xml_field,
                    "field_name": xml_field,
                    "value": value,
                })

        df = pd.DataFrame(records)
        if df.empty:
            df = pd.DataFrame(columns=[
                "entity_name", "reference_id", "basket", "pool_name", "field_name", "value"
            ])
        df.attrs["source"] = self.path.name
        return df

    # =========================================================================
    # Form 8858 Schedule F (Balance Sheet — BOY/EOY)
    # =========================================================================

    def _extract_8858f_entities(self) -> list[SchFEntity]:
        """Scan PDF for 8858 Schedule F pages and extract balance sheet data."""
        from lab.pdf_validator.layouts.schedule_8858_f import identify_line_item

        entities: list[SchFEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            all_texts = [page.extract_text() or "" for page in pdf.pages]
            context = self._build_8858_entity_context(all_texts)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = all_texts[i]

                if not self._is_8858f_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, fc = self._parse_8858_header(text, context)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: 8858 Schedule F page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchFEntity(
                    entity_name=entity_name,
                    reference_id=ref_id,
                    functional_currency=fc,
                )

                self._extract_8858f_table(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "8858 Schedule F extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_8858f_page(self, text: str) -> bool:
        """Check if a page is a Form 8858 Schedule F page."""
        if not all(p.search(text) for p in SCH8858F_PAGE_PATTERNS):
            return False
        return bool(FORM_8858_INDICATOR.search(text))

    def _extract_8858f_table(self, page, text: str, entity: SchFEntity, identify_fn):
        """Extract BOY/EOY from 8858 Schedule F.

        Reuses column detection logic from 5471 Sch F but with 8858 field mapping.
        """
        tables = page.extract_tables()
        if not tables:
            self._metrics.tables_failed += 1
            self._extract_8858f_text_fallback(text, entity, identify_fn)
            return

        self._metrics.tables_detected += 1
        main_table = max(tables, key=lambda t: len(t))
        if len(main_table) < 3:
            return

        boy_col_idx, eoy_col_idx = self._detect_schf_columns(main_table)

        for row in main_table:
            if not row or not row[0]:
                continue

            description = str(row[0]).replace("\n", " ").strip()
            description_clean = self._clean_oit_text(description)

            line_info = identify_fn(description_clean)
            if not line_info:
                continue

            boy_field, eoy_field, _, _ = line_info

            if boy_col_idx is not None and boy_col_idx < len(row):
                val = parse_number(str(row[boy_col_idx] or ""))
                if val is not None:
                    entity.lines[boy_field] = val

            if eoy_col_idx is not None and eoy_col_idx < len(row):
                val = parse_number(str(row[eoy_col_idx] or ""))
                if val is not None:
                    entity.lines[eoy_field] = val

        if not entity.lines:
            logger.debug("8858 Sch F for %s: table produced 0 values, text fallback",
                         entity.reference_id)
            self._extract_8858f_text_fallback(text, entity, identify_fn)

    def _extract_8858f_text_fallback(self, text: str, entity: SchFEntity, identify_fn):
        """Fallback: extract 8858 Sch F data from raw text.

        Filters out IRS line numbers (small integers) and stops at Schedule G boundary.
        """
        lines = text.split("\n")
        in_schf = False
        for line in lines:
            if re.search(r"Schedule\s*F\b", line):
                in_schf = True
                continue
            if re.search(r"Schedule\s*G\b", line):
                break
            if not in_schf:
                continue

            cleaned = self._clean_oit_text(line)
            line_info = identify_fn(cleaned)
            if not line_info:
                continue

            boy_field, eoy_field, _, _ = line_info
            numbers = re.findall(r"-?[\d,]+(?:\.\d+)?|\([\d,]+(?:\.\d+)?\)", line)
            parsed = [parse_number(n) for n in numbers]
            values = [(v, n) for v, n in zip(parsed, numbers)
                      if v is not None and (abs(v) >= 100 or "." in n or v < 0)]

            if len(values) >= 2:
                entity.lines[boy_field] = values[-2][0]
                entity.lines[eoy_field] = values[-1][0]
            elif len(values) == 1:
                entity.lines[eoy_field] = values[0][0]

    # =========================================================================
    # Form 8858 Schedule H (Current E&P — single column)
    # =========================================================================

    def _extract_8858h_entities(self) -> list[SchHEntity]:
        """Scan PDF for 8858 Schedule H pages and extract E&P data."""
        from lab.pdf_validator.layouts.schedule_8858_h import identify_line_item

        entities: list[SchHEntity] = []
        self._metrics = ExtractionMetrics()

        with pdfplumber.open(self.path) as pdf:
            self._metrics.total_pages = len(pdf.pages)

            all_texts = [page.extract_text() or "" for page in pdf.pages]
            context = self._build_8858_entity_context(all_texts)

            for i, page in enumerate(pdf.pages):
                if not self._should_process_page(i):
                    continue
                text = all_texts[i]

                if not self._is_8858h_page(text):
                    continue

                self._metrics.pages_processed += 1
                entity_name, ref_id, _ = self._parse_8858_header(text, context)

                if not ref_id:
                    self._metrics.warnings.append(
                        f"Page {i + 1}: 8858 Schedule H page detected but no ref ID found"
                    )
                    continue

                self._metrics.entities_found += 1
                entity = SchHEntity(entity_name=entity_name, reference_id=ref_id)

                self._extract_single_column_table(page, text, entity, identify_line_item)

                if entity.lines:
                    entities.append(entity)
                    self._metrics.entities_with_data += 1

        self._metrics.values_extracted = sum(e.line_count for e in entities)
        logger.info(
            "8858 Schedule H extraction: %d entities, %d values from %d/%d pages",
            len(entities), self._metrics.values_extracted,
            self._metrics.pages_processed, self._metrics.total_pages,
        )
        return entities

    def _is_8858h_page(self, text: str) -> bool:
        """Check if a page is a Form 8858 Schedule H page."""
        if not all(p.search(text) for p in SCH8858H_PAGE_PATTERNS):
            return False
        return bool(FORM_8858_INDICATOR.search(text))

"""PDF Scanner — Lightweight inventory of forms, schedules, and entities.

Scans an OIT-generated PDF without full data extraction, returning metadata:
form types (5471/8858), schedules present, entities found with ref IDs.
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


@dataclass
class EntityInfo:
    """Metadata for one entity detected in a PDF."""
    reference_id: str
    name: str
    country: str = ""
    form_type: str = ""
    schedules_present: list[str] = field(default_factory=list)
    page_range: tuple[int, int] = (0, 0)


@dataclass
class ScanResult:
    """Result of a lightweight PDF scan."""
    file_path: str
    total_pages: int
    form_types: set[str] = field(default_factory=set)
    schedules_detected: set[str] = field(default_factory=set)
    entities: list[EntityInfo] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    @property
    def entity_count(self) -> int:
        return len(self.entities)


# ─── Form-level detection ──────────────────────────────────────────────────

FORM_5471_PATTERNS = [
    re.compile(r"Form\s*5471", re.IGNORECASE),
    re.compile(r"Information\s+Return.*Controlled\s+Foreign", re.IGNORECASE),
]

FORM_8858_PATTERNS = [
    re.compile(r"Form\s*8858", re.IGNORECASE),
    re.compile(r"Information\s+Return.*Disregarded", re.IGNORECASE),
    re.compile(r"Foreign\s+Disregarded\s+Entity|Foreign\s+Branch", re.IGNORECASE),
]

# ─── Schedule detection (5471) ─────────────────────────────────────────────

SCH_5471_PATTERNS = {
    "J": [
        re.compile(r"SCHEDULE\s*J", re.IGNORECASE),
        re.compile(r"Accumulated\s+E(?:&P|arnings)", re.IGNORECASE),
    ],
    "F": [
        re.compile(r"SCHEDULE\s*F", re.IGNORECASE),
        re.compile(r"Balance\s+Sheet", re.IGNORECASE),
    ],
    "H": [
        re.compile(r"SCHEDULE\s*H", re.IGNORECASE),
        re.compile(r"Current\s+Earnings|Earnings\s+(?:and|&)\s+Profits", re.IGNORECASE),
    ],
    "I-1": [
        re.compile(r"SCHEDULE\s*I-?1", re.IGNORECASE),
        re.compile(r"Global\s+Intangible|GILTI|Tested\s+Income", re.IGNORECASE),
    ],
    "I": [
        re.compile(r"SCHEDULE\s*I\b(?!-)", re.IGNORECASE),
        re.compile(r"Shareholder.?s\s+Income|CFC\s+Income|Subpart\s*F", re.IGNORECASE),
    ],
    "C": [
        re.compile(r"SCHEDULE\s*C", re.IGNORECASE),
        re.compile(r"Income\s+Statement", re.IGNORECASE),
    ],
    "E": [
        re.compile(r"SCHEDULE\s*E", re.IGNORECASE),
        re.compile(r"Taxes?\s+Paid|Excess\s+Profits", re.IGNORECASE),
    ],
    "G": [
        re.compile(r"SCHEDULE\s*G", re.IGNORECASE),
        re.compile(r"Other\s+Information", re.IGNORECASE),
    ],
    "P": [
        re.compile(r"SCHEDULE\s*P", re.IGNORECASE),
        re.compile(r"Previously\s+Taxed|PTEP", re.IGNORECASE),
    ],
    "R": [
        re.compile(r"SCHEDULE\s*R", re.IGNORECASE),
        re.compile(r"Distribution", re.IGNORECASE),
    ],
    "B": [
        re.compile(r"SCHEDULE\s*B", re.IGNORECASE),
        re.compile(r"Shareholder|U\.?S\.?\s+Person", re.IGNORECASE),
    ],
    "A": [
        re.compile(r"Schedule\s*A|Stock\s+of\s+the\s+Foreign", re.IGNORECASE),
    ],
}

# ─── Schedule detection (8858) ─────────────────────────────────────────────

SCH_8858_PATTERNS = {
    "8858_C": [
        re.compile(r"(?:Form\s*8858|8858)", re.IGNORECASE),
        re.compile(r"Income\s+Statement|Schedule\s*C", re.IGNORECASE),
    ],
    "8858_F": [
        re.compile(r"(?:Form\s*8858|8858)", re.IGNORECASE),
        re.compile(r"Balance\s+Sheet|Schedule\s*F", re.IGNORECASE),
    ],
    "8858_H": [
        re.compile(r"(?:Form\s*8858|8858)", re.IGNORECASE),
        re.compile(r"Current\s+Earnings|Schedule\s*H", re.IGNORECASE),
    ],
    "8858_G": [
        re.compile(r"(?:Form\s*8858|8858)", re.IGNORECASE),
        re.compile(r"Other\s+Information|Schedule\s*G", re.IGNORECASE),
    ],
}

# ─── Entity header parsing ─────────────────────────────────────────────────

ENTITY_HEADER_RE = re.compile(
    r"(?:Name\s+of|Foreign\s+(?:Corporation|Entity|Disregarded))"
    r".*?([A-Z][A-Z0-9 &,.\-']+)",
    re.IGNORECASE,
)

REF_ID_RE = re.compile(
    r"(?:Reference\s+ID\s*(?:Number|Num|No\.?)?|Ref\.?\s*(?:ID|No))[:\s]*([A-Z0-9\-_.]+)",
    re.IGNORECASE,
)

COUNTRY_RE = re.compile(
    r"(?:Country\s+of\s+(?:Incorporation|Organization)|under\s+whose\s+laws)"
    r"[:\s]*([A-Z]{2})",
    re.IGNORECASE,
)


class PDFScanner:
    """Lightweight PDF scanner for form/entity inventory.

    Unlike PDFExtractor, this does NOT parse tables or extract numeric data.
    It only reads page text to detect forms, schedules, and entity headers.
    """

    def __init__(self, pdf_path: Path | str):
        if pdfplumber is None:
            raise ImportError("pdfplumber is required: pip install pdfplumber")
        self.path = Path(pdf_path)
        if not self.path.exists():
            raise FileNotFoundError(f"PDF not found: {self.path}")

    def scan(self) -> ScanResult:
        """Scan PDF and return inventory metadata."""
        start = time.perf_counter()

        result = ScanResult(file_path=str(self.path), total_pages=0)
        page_texts: list[str] = []

        with pdfplumber.open(self.path) as pdf:
            result.total_pages = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_texts.append(text)

        current_form_type = ""
        entity_map: dict[str, EntityInfo] = {}

        for page_idx, text in enumerate(page_texts):
            page_form = self._detect_form_type(text)
            if page_form:
                current_form_type = page_form
                result.form_types.add(page_form)

            schedules = self._detect_schedules(text, current_form_type)
            result.schedules_detected.update(schedules)

            entity = self._detect_entity(text, current_form_type)
            if entity:
                key = entity.reference_id or entity.name
                if key in entity_map:
                    existing = entity_map[key]
                    for s in schedules:
                        if s not in existing.schedules_present:
                            existing.schedules_present.append(s)
                    existing.page_range = (existing.page_range[0], page_idx + 1)
                else:
                    entity.schedules_present = list(schedules)
                    entity.page_range = (page_idx + 1, page_idx + 1)
                    entity_map[key] = entity

        result.entities = list(entity_map.values())
        result.scan_duration_ms = (time.perf_counter() - start) * 1000
        return result

    def _detect_form_type(self, text: str) -> str:
        """Detect which IRS form this page belongs to."""
        is_8858 = any(p.search(text) for p in FORM_8858_PATTERNS)
        is_5471 = any(p.search(text) for p in FORM_5471_PATTERNS)

        if is_8858 and not is_5471:
            return "8858"
        if is_5471 and not is_8858:
            return "5471"
        if is_8858 and is_5471:
            if re.search(r"Disregarded\s+Entity|Foreign\s+Branch", text, re.IGNORECASE):
                return "8858"
            return "5471"
        return ""

    def _detect_schedules(self, text: str, form_type: str) -> set[str]:
        """Detect which schedule(s) appear on this page."""
        found = set()

        if form_type == "8858":
            for sch_key, patterns in SCH_8858_PATTERNS.items():
                if all(p.search(text) for p in patterns):
                    found.add(sch_key)
        else:
            for sch_key, patterns in SCH_5471_PATTERNS.items():
                if all(p.search(text) for p in patterns):
                    found.add(sch_key)

        return found

    def _detect_entity(self, text: str, form_type: str) -> Optional[EntityInfo]:
        """Extract entity metadata from page header."""
        cleaned = re.sub(r"(?:\s*m\s*){4,}", " ", text)

        ref_match = REF_ID_RE.search(cleaned)
        if not ref_match:
            return None

        ref_id = ref_match.group(1).strip()

        name = ""
        name_match = ENTITY_HEADER_RE.search(cleaned)
        if name_match:
            name = name_match.group(1).strip()

        country = ""
        country_match = COUNTRY_RE.search(cleaned)
        if country_match:
            country = country_match.group(1).strip()

        return EntityInfo(
            reference_id=ref_id,
            name=name,
            country=country,
            form_type=form_type,
        )

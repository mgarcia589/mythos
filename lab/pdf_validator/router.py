"""PDF Smart Router — Process multi-form batch PDFs from OIT.

Routes pages from a single batch PDF (containing all forms for all entities)
to schedule-specific extractors, then reconciles each against XML.

Typical OIT batch PDF structure (per entity block):
  Page 1:  Form 5471 Page 1 + Schedule A
  Page 2:  Schedule B
  Page 3:  Schedule C
  Page 4:  Schedule F
  Pages:   Schedule G (1-2 pages)
  Pages:   Schedule E + Detail (2-4 pages)
  Pages:   Schedule I, I-1
  Pages:   Schedule J (3 pages per basket)
  Pages:   Schedule P (2+ pages per basket)
  Page:    Schedule R
  --- then Form 8990 (163j) for same entity ---
  --- then next entity block ---
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from lab.pdf_validator.models import (
    BatchValidationResult,
    EntityBlock,
    EntityCompleteness,
    PageMap,
    ProgressCallback,
    NullProgress,
)

logger = logging.getLogger(__name__)

NS = "http://www.irs.gov/efile"

# ─── Page classification patterns ────────────────────────────────────────────

# Form-level detection
_RE_5471 = re.compile(r"Form\s*5471|5471\b", re.IGNORECASE)
_RE_8858 = re.compile(r"Form\s*8858|8858\b", re.IGNORECASE)
_RE_8858_INDICATOR = re.compile(
    r"Disregarded\s+Entity|Foreign\s+Branch|FDE\b|FB\b", re.IGNORECASE
)
_RE_8990 = re.compile(r"Form\s*8990|8990\b.*163\(j\)|163\(j\)", re.IGNORECASE)
_RE_COVER = re.compile(r"Estimated\s+Values\s+Summary|NO\s+ESTIMATED\s+VALUES", re.IGNORECASE)
_RE_DETAIL = re.compile(r"(?:Form\s+(?:5471|8858)|Schedule\s+\w).*Detail|Statement\s+\d+", re.IGNORECASE)
_RE_DORMANT = re.compile(r"Dormant\s+FDE|Announcement\s+2004-?4", re.IGNORECASE)

# Schedule detection — ordered from most specific to least
_SCHEDULE_PATTERNS = [
    ("M", [re.compile(r"Schedule\s*M|Transactions\s+Between\s+Controlled", re.IGNORECASE)]),
    ("O", [re.compile(r"Schedule\s*O|Organization\s+or\s+Reorganization", re.IGNORECASE)]),
    ("Q", [re.compile(r"Schedule\s*Q|CFC\s+Income\s+by\s+CFC\s+Income\s+Groups", re.IGNORECASE)]),
    ("J_P2", [re.compile(r"Schedule\s*J.*Page\s*2|Part\s+I.*continued.*\(e\)\s*Previously", re.IGNORECASE)]),
    ("J_P3", [re.compile(r"Schedule\s*J.*Page\s*3|Part\s+II.*Recapture", re.IGNORECASE)]),
    ("J", [re.compile(r"Schedule\s*J|Accumulated\s+E&?P", re.IGNORECASE)]),
    ("I-1", [re.compile(r"Schedule\s*I-?1|Global\s+Intangible|GILTI", re.IGNORECASE)]),
    ("I", [re.compile(r"Schedule\s*I\b(?!-)|Shareholder.?s\s+Income", re.IGNORECASE)]),
    ("P", [re.compile(r"Schedule\s*P|Previously\s+Taxed.*PTEP", re.IGNORECASE)]),
    ("R", [re.compile(r"Schedule\s*R|Distributions?\s+From", re.IGNORECASE)]),
    ("E_DETAIL", [re.compile(r"Schedule\s*E\s+Detail|Sch\s*E.*Part\s+I\s+Sec", re.IGNORECASE)]),
    ("E", [re.compile(r"Schedule\s*E|Taxes?\s+Paid|Foreign\s+Tax", re.IGNORECASE)]),
    ("G", [re.compile(r"Schedule\s*G|Other\s+Information", re.IGNORECASE)]),
    ("H", [re.compile(r"Schedule\s*H|Current\s+Earnings", re.IGNORECASE)]),
    ("F", [re.compile(r"Schedule\s*F|Balance\s+Sheet", re.IGNORECASE)]),
    ("C", [re.compile(r"Schedule\s*C|Income\s+Statement", re.IGNORECASE)]),
    ("B", [re.compile(r"Schedule\s*B|Shareholders?\s+of\s+Foreign", re.IGNORECASE)]),
    ("A", [re.compile(r"Schedule\s*A|Stock\s+of\s+the\s+Foreign", re.IGNORECASE)]),
]

# Entity identification
_RE_REF_ID = re.compile(
    r"Reference\s+ID\s*(?:number|num|no\.?)?[:\s]*([A-Z]\d{3,5}[A-Z]?)\b",
    re.IGNORECASE,
)
_RE_REF_ID_8990 = re.compile(
    r"Reference\s+ID\s*(?:number)?[:\s]*([A-Z]\d{3,5}[A-Z]?)",
    re.IGNORECASE,
)
_RE_ENTITY_NAME = re.compile(
    r"Name\s+of\s+foreign\s+(?:corporation|entity)\s*\n\s*(.+)",
    re.IGNORECASE,
)
_RE_COUNTRY = re.compile(
    r"(?:Country\s+of\s+(?:incorporation|organization))[:\s]*([A-Z]{2})\b",
    re.IGNORECASE,
)

# Ref ID from the "m" spacer OIT format
_RE_REF_ID_OIT = re.compile(r"\b([A-Z]{1,3}\d{2,5})\b")

SCHEDULE_CANONICAL = {
    "J": "J", "J_P2": "J", "J_P3": "J",
    "F": "F", "H": "H", "I-1": "I1", "I": "I",
    "C": "C", "E": "E", "E_DETAIL": "E",
    "G": "G", "M": "M", "O": "O", "P": "P", "Q": "Q", "R": "R",
    "A": "A", "B": "B",
    "8858_C": "8858_C", "8858_F": "8858_F",
    "8858_H": "8858_H", "8858_G": "8858_G",
}

_5471_SCHEDULES = {"A", "B", "C", "E", "F", "G", "H", "I", "I1", "J", "P", "R"}
_8858_SCHEDULES = {"8858_C", "8858_F", "8858_G", "8858_H"}


def _classify_page(text: str) -> tuple[str, str, str, str, str]:
    """Classify a single page from its text content.

    Returns (form_type, schedule, ref_id, entity_name, country).
    form_type: "5471", "8858", "8990", "cover", "unknown"
    schedule: canonical schedule key or ""
    """
    first_500 = text[:500]

    # Cover page
    if _RE_COVER.search(first_500):
        return ("cover", "", "", "", "")

    # Detail/statement overflow pages — skip for extraction but keep entity context
    if _RE_DETAIL.search(text[:200]):
        return ("detail", "", "", "", "")

    # Dormant FDE filing (Announcement 2004-4)
    if _RE_DORMANT.search(first_500):
        return ("dormant_fde", "", "", "", "")

    # Form 8990 (163j) — detect BEFORE 5471 because 8990 pages mention "Form 5471"
    if _RE_8990.search(first_500):
        ref_id = ""
        m = _RE_REF_ID_8990.search(text)
        if m:
            ref_id = m.group(1).upper()
        name = ""
        name_m = re.search(
            r"Name\s+of\s+foreign\s+entity\s+(.+?)(?:\n|Employer)",
            text, re.IGNORECASE,
        )
        if name_m:
            name = name_m.group(1).strip()
        return ("8990", "", ref_id, name, "")

    # Form type
    is_8858 = bool(_RE_8858.search(first_500))
    is_5471 = bool(_RE_5471.search(first_500))

    if is_8858 and _RE_8858_INDICATOR.search(text[:800]):
        form_type = "8858"
    elif is_5471 and not is_8858:
        form_type = "5471"
    elif is_8858 and not is_5471:
        form_type = "8858"
    elif is_5471:
        form_type = "5471"
    else:
        form_type = "unknown"

    # Schedule detection — pick the schedule whose keyword appears earliest
    schedule = ""
    best_pos = len(text) + 1
    for sch_key, patterns in _SCHEDULE_PATTERNS:
        matches = [p.search(text) for p in patterns]
        if all(matches):
            pos = min(m.start() for m in matches)
            if pos < best_pos:
                best_pos = pos
                schedule = sch_key

    # Prefix 8858 schedules
    if form_type == "8858" and schedule in ("C", "F", "G", "H"):
        schedule = f"8858_{schedule}"

    # Entity identification — multi-strategy
    ref_id = ""
    # Strategy 1: "Reference ID number: C0002" on same line
    m = _RE_REF_ID.search(text)
    if m:
        ref_id = m.group(1).upper()

    if not ref_id:
        # Strategy 2: OIT splits "Reference ID number" and value across lines
        lines = text.split("\n")
        for idx, line in enumerate(lines[:35]):
            if "reference id" in line.lower():
                # Check same line first
                cleaned = re.sub(r"\bm\b", "", line)
                cleaned = re.sub(r"\s+", " ", cleaned)
                rid_m = _RE_REF_ID_OIT.search(cleaned)
                if rid_m:
                    ref_id = rid_m.group(1)
                    break
                # Check next line (OIT puts value on next line)
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    cleaned_next = re.sub(r"\bm\b", "", next_line)
                    cleaned_next = re.sub(r"\s+", " ", cleaned_next)
                    rid_m = _RE_REF_ID_OIT.search(cleaned_next)
                    if rid_m:
                        ref_id = rid_m.group(1)
                        break
                break

    entity_name = ""
    name_m = _RE_ENTITY_NAME.search(text[:1000])
    if name_m:
        raw_name = name_m.group(1).strip()
        raw_name = re.sub(r"(?:\s+m\s+){3,}.*", "", raw_name)
        raw_name = re.sub(r"\s+", " ", raw_name).strip()
        if len(raw_name) > 2 and raw_name.upper() not in ("N/A", "NONE"):
            entity_name = raw_name

    if not entity_name:
        first_line = (text.split("\n")[0] or "").strip()
        if first_line and len(first_line) > 3 and not re.match(
            r"^(Information|Form|Schedule|Estimated|Department|Limitation|Attach|"
            r"Filed\s+Pursuant|Final\s+Return|Return\s+of|OMB\s+No|Rev\.\s)",
            first_line, re.IGNORECASE,
        ):
            cleaned_name = re.sub(r"(?:\s+m\s+){3,}.*", "", first_line)
            cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()
            if len(cleaned_name) > 3 and len(cleaned_name) < 80:
                entity_name = cleaned_name

    country = ""
    c_m = _RE_COUNTRY.search(text[:1000])
    if c_m:
        country = c_m.group(1).upper()

    # For Page 1 with Schedule A, tag as "A" (it includes both)
    if form_type == "5471" and not schedule:
        if re.search(r"Page\s*1|Information\s+Return.*5471", first_500, re.IGNORECASE):
            schedule = "A"

    # 8858 page 1 — tag as 8858_G (main form includes general info)
    if form_type == "8858" and not schedule:
        if re.search(r"Information\s+Return|Form\s*8858", first_500, re.IGNORECASE):
            schedule = "8858_G"

    return (form_type, schedule, ref_id, entity_name, country)


class PDFRouter:
    """Route pages from a multi-form batch PDF to schedule-specific extractors.

    Takes a single OIT batch PDF containing all forms for all entities
    and produces validated results for each detected schedule.
    """

    def __init__(
        self,
        pdf_path: str | Path,
        xml_path: str | Path,
        tolerance: float = 10.0,
        schedules: Optional[list[str]] = None,
    ):
        if pdfplumber is None:
            raise ImportError("pdfplumber is required: pip install pdfplumber")
        self.pdf_path = Path(pdf_path)
        self.xml_path = Path(xml_path)
        self.tolerance = tolerance
        self.target_schedules = set(s.upper() for s in schedules) if schedules else None
        self._page_texts: dict[int, str] = {}
        self._page_map: Optional[PageMap] = None

    def scan(self, progress: Optional[ProgressCallback] = None) -> PageMap:
        """Build a page map: classify every page and group by entity/schedule."""
        cb = progress or NullProgress()
        start = time.perf_counter()

        cb("scan", 0.0, f"Opening {self.pdf_path.name}...")

        page_classifications: list[tuple[str, str, str, str, str]] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            total_pages = len(pdf.pages)
            cb("scan", 0.05, f"Scanning {total_pages} pages...")

            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                self._page_texts[i] = text

                classification = _classify_page(text)
                page_classifications.append(classification)

                if (i + 1) % 100 == 0:
                    pct = 0.05 + 0.75 * (i / total_pages)
                    cb("scan", pct, f"Classified {i + 1}/{total_pages} pages...")

        cb("scan", 0.80, "Building entity map...")

        page_map = self._build_page_map(page_classifications, total_pages)
        page_map.scan_duration_ms = (time.perf_counter() - start) * 1000

        self._page_map = page_map

        cb("scan", 0.90, f"Found {page_map.entity_count} entities, "
           f"{page_map.classified_pages} classified pages")

        logger.info(
            "Page map: %d entities, %d classified, %d skipped, %d unrecognized "
            "in %.1fs",
            page_map.entity_count, page_map.classified_pages,
            len(page_map.skipped_pages), len(page_map.unrecognized_pages),
            page_map.scan_duration_ms / 1000,
        )

        return page_map

    def _build_page_map(
        self,
        classifications: list[tuple[str, str, str, str, str]],
        total_pages: int,
    ) -> PageMap:
        """Group page classifications into entity blocks."""
        page_map = PageMap(total_pages=total_pages)

        current_ref_id = ""
        current_entity_name = ""
        current_form_type = ""
        current_country = ""

        for page_idx, (form_type, schedule, ref_id, entity_name, country) in enumerate(classifications):
            page_num = page_idx + 1  # 1-indexed

            # Skip non-extractable page types
            if form_type in ("cover", "detail", "dormant_fde"):
                page_map.skipped_pages.append(page_num)
                continue

            if form_type == "8990":
                page_map.skipped_pages.append(page_num)
                if ref_id:
                    current_ref_id = ref_id
                if entity_name:
                    current_entity_name = entity_name
                continue

            if form_type == "unknown" and not schedule:
                page_map.unrecognized_pages.append(page_num)
                continue

            # Update entity context
            if ref_id:
                current_ref_id = ref_id
            if entity_name:
                current_entity_name = entity_name
            if country:
                current_country = country
            if form_type in ("5471", "8858"):
                current_form_type = form_type

            # Must have a ref_id to assign to an entity
            if not current_ref_id:
                page_map.unrecognized_pages.append(page_num)
                continue

            # Get or create entity block
            if current_ref_id not in page_map.entities:
                page_map.entities[current_ref_id] = EntityBlock(
                    reference_id=current_ref_id,
                    entity_name=current_entity_name,
                    form_type=current_form_type or "5471",
                    country=current_country,
                )
            block = page_map.entities[current_ref_id]

            # Update entity name if we got a better one
            if entity_name and (not block.entity_name or block.entity_name == current_ref_id):
                block.entity_name = entity_name
            if country and not block.country:
                block.country = country

            # Map canonical schedule
            canonical = SCHEDULE_CANONICAL.get(schedule, schedule)
            if canonical:
                block.schedules.setdefault(canonical, []).append(page_num)
            else:
                page_map.unrecognized_pages.append(page_num)

        return page_map

    def route(self, progress: Optional[ProgressCallback] = None) -> BatchValidationResult:
        """Full pipeline: scan → extract per schedule → reconcile → report."""
        from lab.pdf_validator.extractor import PDFExtractor
        from lab.pdf_validator.reconciler import PDFReconciler

        cb = progress or NullProgress()
        started = datetime.now()
        result = BatchValidationResult(
            pdf_source=self.pdf_path.name,
            xml_source=self.xml_path.name,
            started_at=started,
        )

        # Step 1: Scan
        if self._page_map is None:
            page_map = self.scan(progress=cb)
        else:
            page_map = self._page_map

        result.page_map = page_map

        if page_map.entity_count == 0:
            result.errors.append("No entities detected in PDF")
            result.completed_at = datetime.now()
            return result

        # Determine which schedules to validate
        all_schedules: set[str] = set()
        for block in page_map.entities.values():
            all_schedules.update(block.schedules.keys())

        if self.target_schedules:
            schedules_to_validate = all_schedules & self.target_schedules
        else:
            schedules_to_validate = all_schedules

        # Step 2: Extract + Reconcile per schedule
        schedule_list = sorted(schedules_to_validate)
        for idx, schedule in enumerate(schedule_list):
            pct = 0.30 + 0.60 * (idx / max(len(schedule_list), 1))
            cb("validate", pct, f"Validating Schedule {schedule}...")

            # Collect all pages for this schedule across all entities
            all_pages = []
            for block in page_map.entities.values():
                pages = block.schedules.get(schedule, [])
                all_pages.extend(pages)

            if not all_pages:
                continue

            # Convert to 0-indexed for extractor
            page_indices = sorted(set(p - 1 for p in all_pages))

            try:
                extractor = PDFExtractor(self.pdf_path, schedule=schedule)
                pdf_data = extractor.extract(pages=page_indices)
                pdf_data.attrs["source"] = self.pdf_path.name

                if pdf_data.empty:
                    result.warnings.append(f"Schedule {schedule}: no data extracted")
                    continue

                reconciler = PDFReconciler(
                    pdf_data=pdf_data,
                    xml_path=self.xml_path,
                    schedule=schedule,
                    tolerance=self.tolerance,
                )
                report = reconciler.reconcile()
                result.schedule_reports[schedule] = report

                logger.info(
                    "Schedule %s: %d comparisons, %d discrepancies",
                    schedule, report.total_comparisons, len(report.discrepancies),
                )

            except Exception as e:
                logger.warning("Schedule %s validation failed: %s", schedule, e)
                result.warnings.append(f"Schedule {schedule} failed: {e}")

        # Step 3: Entity completeness
        cb("validate", 0.92, "Checking entity completeness...")
        result.entity_completeness = self._check_entity_completeness(page_map)

        result.completed_at = datetime.now()
        cb("complete", 1.0, result.summary)

        self._result = result
        return result

    def _check_entity_completeness(self, page_map: PageMap) -> EntityCompleteness:
        """Cross-check entities in XML vs entities in PDF."""
        completeness = EntityCompleteness()

        # PDF entities
        completeness.pdf_entities = set(page_map.entities.keys())

        # XML entities
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            for el in root.iter(f"{{{NS}}}ForeignEntityReferenceIdNum"):
                if el.text:
                    completeness.xml_entities.add(el.text.strip())
        except Exception as e:
            logger.warning("Could not parse XML for completeness check: %s", e)

        return completeness

    def to_excel(self, output_path: str | Path, **kwargs) -> Path:
        """Generate consolidated Excel report from batch validation."""
        from lab.pdf_validator.report import write_batch_report_excel

        if not hasattr(self, '_result'):
            raise RuntimeError("Call route() before to_excel()")
        return write_batch_report_excel(self._result, output_path, **kwargs)

"""Parse service — async operations for XML Check parse-only mode."""

import asyncio
import hashlib
import time
from pathlib import Path

from lab.mythos_ui.services.xml_check_state import (
    FileEntry, ParseSummary, ScheduleNode,
)


# ─── DISPLAY NAMES ─────────────────────────────────────────────────────────

FORM_DISPLAY_NAMES = {
    "IRS5471ScheduleA": "Schedule A — Stock of the Foreign Corporation",
    "IRS5471ScheduleB": "Schedule B — U.S. Shareholders",
    "IRS5471ScheduleC": "Schedule C — Income Statement",
    "IRS5471ScheduleE": "Schedule E — Income, War Profits, and Excess Profits Taxes",
    "IRS5471ScheduleF": "Schedule F — Balance Sheet",
    "IRS5471ScheduleG": "Schedule G — Other Information",
    "IRS5471ScheduleH": "Schedule H — Current E&P",
    "IRS5471ScheduleI": "Schedule I — Summary of Shareholder's Income",
    "IRS5471ScheduleI1": "Schedule I-1 — Information for GILTI",
    "IRS5471ScheduleJ": "Schedule J — Accumulated E&P",
    "IRS5471ScheduleM": "Schedule M — Transactions Between CFC and Shareholders",
    "IRS5471ScheduleO": "Schedule O — Organization or Reorganization",
    "IRS5471ScheduleP": "Schedule P — Previously Taxed E&P",
    "IRS5471ScheduleQ": "Schedule Q — CFC Income by Groups",
    "IRS5471ScheduleR": "Schedule R — Distributions From a Foreign Corporation",
    "IRS8858ScheduleC": "8858 Schedule C — Income Statement",
    "IRS8858ScheduleF": "8858 Schedule F — Balance Sheet",
    "IRS8858ScheduleG": "8858 Schedule G — Other Information",
    "IRS8858ScheduleH": "8858 Schedule H — Current E&P",
    "IRS8858": "Form 8858 — Information Return",
    "IRS5471": "Form 5471 — Information Return of U.S. Persons",
    "IRS8990": "Form 8990 — Section 163(j) Limitation",
}

MULTI_INSTANCE_FORMS = {"IRS5471ScheduleJ", "IRS5471ScheduleQ", "IRS5471ScheduleP"}


def get_display_name(form_name: str) -> str:
    """Get human-readable display name for a form/schedule."""
    return FORM_DISPLAY_NAMES.get(form_name, form_name)


# ─── FILE UTILITIES ────────────────────────────────────────────────────────

def compute_file_hash(path: Path) -> str:
    """SHA-256 hash (first 16 chars) for duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def check_duplicate(files: list[FileEntry], new_hash: str) -> bool:
    """Return True if file hash already exists in the file list."""
    return any(f.file_hash == new_hash for f in files)


# ─── PARSE OPERATIONS ──────────────────────────────────────────────────────

async def parse_xml_only(path: Path, on_progress=None) -> object:
    """Parse XML without running review checks. Returns ParsedReturn.

    Args:
        path: Path to e-file XML.
        on_progress: Callable(msg: str, pct: float) for progress updates.
    """
    from lab.xml_parser.parser import EFileParser

    def _do_parse():
        if on_progress:
            on_progress("Loading XML...", 0.1)

        parser = EFileParser(path)

        if on_progress:
            on_progress("Parsing return structure...", 0.4)

        parsed = parser.parse()

        if on_progress:
            on_progress("Building form inventory...", 0.8)

        return parser, parsed

    loop = asyncio.get_event_loop()
    parser, parsed = await loop.run_in_executor(None, _do_parse)

    if on_progress:
        on_progress("Complete", 1.0)

    return parser, parsed


async def build_parse_summary(parser, parsed) -> ParseSummary:
    """Compute ParseSummary from a ParsedReturn.

    Args:
        parser: EFileParser instance
        parsed: ParsedReturn from parser.parse()
    """
    start = time.time()

    header = parsed.header
    form_types = parser.detect_forms()

    # Build schedule tree
    schedule_tree = compute_schedule_tree(parsed)

    # Count records and fields
    total_records = 0
    total_fields = 0
    populated_fields = 0
    empty_fields = 0

    for sub in parsed.subsidiaries:
        for form_key, form_data in sub.forms.items():
            total_records += 1
            for _field_name, value in form_data.fields.items():
                total_fields += 1
                if value and str(value).strip():
                    populated_fields += 1
                else:
                    empty_fields += 1

    # Count forms and schedules
    all_form_names = set()
    for sub in parsed.subsidiaries:
        for form_key in sub.forms:
            base_name = form_key.split("_")[0] if "_" in form_key else form_key
            all_form_names.add(base_name)

    top_level_forms = {n for n in all_form_names if "Schedule" not in n}
    schedules = all_form_names - top_level_forms

    duration_ms = (time.time() - start) * 1000

    return ParseSummary(
        client_name=header.filer_name or "",
        tax_year=header.tax_year or "",
        return_type=header.return_type or "",
        entity_count=len(parsed.subsidiaries),
        form_types=form_types,
        schedule_inventory=schedule_tree,
        total_forms=len(top_level_forms),
        total_schedules=len(schedules),
        total_records=total_records,
        total_fields=total_fields,
        populated_fields=populated_fields,
        empty_fields=empty_fields,
        parse_duration_ms=duration_ms,
        software_id=header.software_id or "",
        software_version=header.software_version or "",
        return_timestamp=header.return_timestamp or "",
    )


def compute_schedule_tree(parsed) -> list[ScheduleNode]:
    """Build hierarchical tree of forms and schedules from ParsedReturn."""
    form_entities: dict[str, set[str]] = {}
    form_fields: dict[str, set[str]] = {}

    for sub in parsed.subsidiaries:
        entity_id = sub.entity.reference_id or sub.entity.name
        for form_key, form_data in sub.forms.items():
            base_name = form_key.split("_")[0] if "_" in form_key else form_key
            if base_name not in form_entities:
                form_entities[base_name] = set()
                form_fields[base_name] = set()
            form_entities[base_name].add(entity_id)
            form_fields[base_name].update(form_data.fields.keys())

    # Group by parent form
    form_5471_children: list[ScheduleNode] = []
    form_8858_children: list[ScheduleNode] = []
    form_8990_children: list[ScheduleNode] = []
    other_forms: list[ScheduleNode] = []

    for form_name in sorted(form_entities.keys()):
        if "8858" in form_name:
            form_type = "8858"
        elif "8990" in form_name:
            form_type = "8990"
        else:
            form_type = "5471"

        node = ScheduleNode(
            form_name=form_name,
            display_name=get_display_name(form_name),
            form_type=form_type,
            entity_count=len(form_entities[form_name]),
            field_count=len(form_fields[form_name]),
            has_multi_instance=form_name in MULTI_INSTANCE_FORMS,
        )

        if "5471Schedule" in form_name or form_name == "IRS5471":
            form_5471_children.append(node)
        elif "8858" in form_name:
            form_8858_children.append(node)
        elif "8990" in form_name:
            form_8990_children.append(node)
        else:
            other_forms.append(node)

    tree: list[ScheduleNode] = []

    if form_5471_children:
        tree.append(ScheduleNode(
            form_name="IRS5471",
            display_name="Form 5471 — Information Return of U.S. Persons",
            form_type="5471",
            entity_count=max((c.entity_count for c in form_5471_children), default=0),
            field_count=sum(c.field_count for c in form_5471_children),
            children=form_5471_children,
        ))

    if form_8858_children:
        tree.append(ScheduleNode(
            form_name="IRS8858",
            display_name="Form 8858 — Information Return (FDE/FB)",
            form_type="8858",
            entity_count=max((c.entity_count for c in form_8858_children), default=0),
            field_count=sum(c.field_count for c in form_8858_children),
            children=form_8858_children,
        ))

    if form_8990_children:
        tree.append(ScheduleNode(
            form_name="IRS8990",
            display_name="Form 8990 — Section 163(j) Limitation",
            form_type="8990",
            entity_count=max((c.entity_count for c in form_8990_children), default=0),
            field_count=sum(c.field_count for c in form_8990_children),
            children=form_8990_children,
        ))

    if other_forms:
        tree.append(ScheduleNode(
            form_name="Other",
            display_name="Other Attachments & Statements",
            form_type="other",
            entity_count=max((c.entity_count for c in other_forms), default=0),
            field_count=sum(c.field_count for c in other_forms),
            children=other_forms,
        ))

    return tree


async def extract_form_data(parser, form_name: str):
    """Extract one form's data as DataFrame for table display.

    Args:
        parser: EFileParser instance
        form_name: XML form name (e.g., "IRS5471ScheduleH")
    """
    import pandas as pd

    loop = asyncio.get_event_loop()

    def _extract():
        try:
            if "8858" in form_name:
                return parser.extract_form_8858(form_name)
            else:
                return parser.extract_form(form_name)
        except Exception:
            return pd.DataFrame()

    return await loop.run_in_executor(None, _extract)

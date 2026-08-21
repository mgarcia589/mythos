"""XML Check page state — all state for the multi-phase XML analysis workstation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PagePhase(Enum):
    """Page state machine phases."""
    INITIAL = "initial"
    FILES_UPLOADED = "files_uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_warnings"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class ProcessingMode(Enum):
    """What the user chose to run."""
    PARSE_ONLY = "parse_only"
    ROLLOVER_ONLY = "rollover_only"
    FULL_REVIEW = "full_review"


@dataclass
class FileEntry:
    """One uploaded XML file."""
    path: Path
    filename: str
    role: str = "current"  # "current" | "prior"
    size_bytes: int = 0
    upload_time: str = ""
    file_hash: str = ""


@dataclass
class ScheduleNode:
    """One node in the form/schedule tree."""
    form_name: str
    display_name: str
    form_type: str = "5471"
    entity_count: int = 0
    field_count: int = 0
    children: list["ScheduleNode"] = field(default_factory=list)
    has_multi_instance: bool = False


@dataclass
class ParseSummary:
    """Lightweight summary computed after parse."""
    client_name: str = ""
    tax_year: str = ""
    return_type: str = ""
    entity_count: int = 0
    form_types: set = field(default_factory=set)
    schedule_inventory: list[ScheduleNode] = field(default_factory=list)
    total_forms: int = 0
    total_schedules: int = 0
    total_records: int = 0
    total_fields: int = 0
    populated_fields: int = 0
    empty_fields: int = 0
    parse_duration_ms: float = 0.0
    software_id: str = ""
    software_version: str = ""
    return_timestamp: str = ""


@dataclass
class XmlCheckState:
    """All state for the XML Check page."""
    phase: PagePhase = field(default=PagePhase.INITIAL)
    mode: ProcessingMode | None = None
    files: list[FileEntry] = field(default_factory=list)
    active_tab: str = "overview"

    # Parse results (cached after processing)
    parse_summary: ParseSummary | None = None

    # View state
    selected_form: str | None = None
    selected_entity: str | None = None
    view_mode: str = "table"  # "table" | "form" | "raw"
    search_query: str = ""
    active_filters: dict = field(default_factory=dict)

    # Processing
    progress: float = 0.0
    progress_msg: str = ""
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None

    def get_current_file(self) -> FileEntry | None:
        """Return the file assigned as current year."""
        for f in self.files:
            if f.role == "current":
                return f
        return None

    def get_prior_file(self) -> FileEntry | None:
        """Return the file assigned as prior year."""
        for f in self.files:
            if f.role == "prior":
                return f
        return None

    def reset(self):
        """Reset to initial state."""
        self.phase = PagePhase.INITIAL
        self.mode = None
        self.files.clear()
        self.active_tab = "overview"
        self.parse_summary = None
        self.selected_form = None
        self.selected_entity = None
        self.view_mode = "table"
        self.search_query = ""
        self.active_filters.clear()
        self.progress = 0.0
        self.progress_msg = ""
        self.warnings.clear()
        self.error_message = None

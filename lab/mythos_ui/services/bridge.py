"""Service bridge — wraps MythosService for the dashboard UI layer."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from lab.xml_parser.api.service import MythosService, ReviewResult, ExportResult, ReconcileResult
from lab.xml_parser.core.config import get_config
from lab.xml_parser.core.models import ReviewReport
from lab.xml_parser.parser import EFileParser
from lab.mythos_ui.services.xml_check_state import XmlCheckState



# ─── APPLICATION STATE (module-level, single-user native app) ────────────────

@dataclass
class FilterState:
    """Persists user's filter selections across page navigations."""
    severity: str = "All"
    category: str = "All"
    entity: str = "All"
    search: str = ""


@dataclass
class HistoryEntry:
    """One completed review run."""
    timestamp: str = ""
    client_name: str = ""
    tax_year: str = ""
    entity_count: int = 0
    finding_count: int = 0
    high_count: int = 0
    xml_name: str = ""


@dataclass
class AppState:
    """Holds the current review state for the running session."""
    report: ReviewReport | None = None
    parser: EFileParser | None = None
    current_xml: Path | None = None
    prior_xml: Path | None = None
    progress: float = 0.0
    progress_msg: str = ""
    filters: FilterState = field(default_factory=FilterState)
    history: list[HistoryEntry] = field(default_factory=list)
    reviewed_items: set[str] = field(default_factory=set)
    rollover_reports: dict | None = None
    pdf_result: object | None = None
    pdf_report: object | None = None
    xml_check: XmlCheckState = field(default_factory=XmlCheckState)


# Singleton state instance
state = AppState()


def get_state() -> AppState:
    return state


def clear_state():
    global state
    state = AppState()


# ─── SERVICE OPERATIONS ─────────────────────────────────────────────────────

async def run_review(
    current_xml: Path,
    prior_xml: Path | None = None,
    on_progress=None,
) -> ReviewResult:
    """Run compliance review via MythosService.

    Args:
        current_xml: Path to current year XML.
        prior_xml: Optional path to prior year XML.
        on_progress: Callable(msg: str, pct: float) for progress updates.

    Returns:
        ReviewResult from MythosService.
    """
    def progress_callback(msg: str, pct: float):
        state.progress = pct
        state.progress_msg = msg
        if on_progress:
            on_progress(msg, pct)

    service = MythosService(config=get_config(), progress=progress_callback)

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.review(current_xml, prior=prior_xml),
    )

    if result.success:
        state.report = result.report
        state.parser = EFileParser(current_xml)
        state.current_xml = current_xml
        state.prior_xml = prior_xml
        state.progress = 1.0
        state.progress_msg = "Complete"

        # Invalidate entity classification cache from prior XML
        state._classified_entities = None
        state._classified_entities_path = None

        # Append to history
        from datetime import datetime
        state.history.append(HistoryEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            client_name=result.report.client_name,
            tax_year=result.report.tax_year,
            entity_count=result.entity_count,
            finding_count=result.finding_count,
            high_count=result.report.summary.get("by_severity", {}).get("HIGH", 0),
            xml_name=current_xml.name,
        ))
        # Reset reviewed items for new run
        state.reviewed_items = set()

    return result


async def run_export(fmt: str = "excel") -> ExportResult | None:
    """Export current review results."""
    if not state.report:
        return None

    service = MythosService(config=get_config())

    export_result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.export_review(state.report, format=fmt),
    )
    return export_result


async def run_reconcile(
    xml_path: Path,
    workbook_path: Path,
    tolerance: float = 1.0,
    schedules: list[str] | None = None,
    on_progress=None,
) -> ReconcileResult:
    """Run workbook-vs-XML reconciliation via MythosService.

    Args:
        xml_path: Path to e-file XML.
        workbook_path: Path to Excel workbook.
        tolerance: Numeric tolerance for matching.
        schedules: Optional list of specific schedules to reconcile.
        on_progress: Callable(msg, pct) for progress updates.
    """
    def progress_callback(msg: str, pct: float):
        state.progress = pct
        state.progress_msg = msg
        if on_progress:
            on_progress(msg, pct)

    service = MythosService(config=get_config(), progress=progress_callback)

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.reconcile(
            xml_path=xml_path,
            workbook_path=workbook_path,
            tolerance=tolerance,
            schedules=schedules,
        ),
    )
    return result

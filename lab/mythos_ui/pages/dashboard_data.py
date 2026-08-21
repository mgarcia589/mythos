"""Dashboard data aggregation — computes metrics from AppState for the Home dashboard."""

from dataclasses import dataclass, field


@dataclass
class ModuleStatus:
    """Status of a single Mythos module."""
    name: str
    key: str
    icon: str
    status: str  # "completed", "warning", "failed", "not_run"
    entity_count: int = 0
    issue_count: int = 0
    critical_count: int = 0
    last_run: str | None = None
    route: str = "/"


@dataclass
class DashboardData:
    """Aggregated dashboard metrics computed from AppState."""
    # Header
    client_name: str | None = None
    tax_year: str | None = None
    overall_status: str = "not_started"
    last_updated: str | None = None
    current_file: str | None = None
    prior_file: str | None = None

    # KPIs
    total_entities: int = 0
    files_processed: int = 0
    modules_completed: int = 0
    total_modules: int = 4
    total_issues: int = 0
    critical_issues: int = 0
    completion_pct: float = 0.0

    # Modules
    modules: list[ModuleStatus] = field(default_factory=list)

    # Issue distribution
    issues_by_severity: dict[str, int] = field(default_factory=dict)
    issues_by_category: dict[str, int] = field(default_factory=dict)
    top_entities: list[tuple] = field(default_factory=list)

    # Activity
    recent_history: list = field(default_factory=list)
    action_items: list[dict] = field(default_factory=list)


def compute_dashboard(s) -> DashboardData:
    """Compute all dashboard metrics from current AppState.

    Args:
        s: AppState instance from bridge.get_state()
    """
    data = DashboardData()

    # ── Files processed ──
    if s.current_xml:
        data.files_processed += 1
        data.current_file = s.current_xml.name
    if s.prior_xml:
        data.files_processed += 1
        data.prior_file = s.prior_xml.name

    # ── XML Check module ──
    xml_module = ModuleStatus(
        name="XML Check", key="xml_check", icon="upload_file", route="/review",
        status="not_run",
    )
    if s.report:
        data.client_name = s.report.client_name
        data.tax_year = s.report.tax_year
        data.last_updated = s.report.run_timestamp
        data.total_entities = s.report.entity_count

        summary = s.report.summary
        data.total_issues = summary.get("total_findings", 0)
        data.critical_issues = summary.get("by_severity", {}).get("HIGH", 0)
        data.issues_by_severity = summary.get("by_severity", {})
        data.issues_by_category = summary.get("by_category", {})

        xml_module.entity_count = s.report.entity_count
        xml_module.issue_count = data.total_issues
        xml_module.critical_count = data.critical_issues
        xml_module.last_run = s.report.run_timestamp

        if data.critical_issues > 0:
            xml_module.status = "warning"
        else:
            xml_module.status = "completed"

        # Top entities by issues
        entity_issues: dict[str, dict] = {}
        for f in s.report.findings:
            key = f.entity_code
            if key not in entity_issues:
                entity_issues[key] = {"name": f.entity_name, "total": 0, "critical": 0}
            entity_issues[key]["total"] += 1
            if f.severity == "HIGH":
                entity_issues[key]["critical"] += 1

        sorted_entities = sorted(entity_issues.items(),
                                 key=lambda x: (x[1]["critical"], x[1]["total"]),
                                 reverse=True)
        data.top_entities = [
            (code, info["name"], info["total"], info["critical"])
            for code, info in sorted_entities[:10]
        ]

    data.modules.append(xml_module)

    # ── PDF Check module ──
    pdf_module = ModuleStatus(
        name="PDF Check", key="pdf_check", icon="picture_as_pdf", route="/pdf-check",
        status="not_run",
    )
    pdf_result = getattr(s, 'pdf_result', None)
    if pdf_result and hasattr(pdf_result, 'success'):
        metrics = getattr(pdf_result, 'metrics', {}) or {}
        pdf_module.entity_count = metrics.get("entities_checked", 0)
        phantoms = metrics.get("phantom_count", 0)
        mismatches = metrics.get("mismatch_count", 0)
        missing = metrics.get("missing_count", 0)
        pdf_module.issue_count = phantoms + mismatches + missing
        pdf_module.critical_count = phantoms

        if pdf_result.success:
            pdf_module.status = "warning" if pdf_module.issue_count > 0 else "completed"
        else:
            pdf_module.status = "failed"

    data.modules.append(pdf_module)

    # ── Rollover module ──
    rollover_module = ModuleStatus(
        name="Rollover", key="rollover", icon="swap_vert", route="/rollover",
        status="not_run",
    )
    if s.rollover_reports:
        total_fail = sum(r.failed for r in s.rollover_reports.values())
        total_checks = sum(r.total_checks for r in s.rollover_reports.values())
        entities_with_issues = set()
        for r in s.rollover_reports.values():
            entities_with_issues.update(r.entities_with_issues)

        rollover_module.entity_count = len(set(
            item.reference_id
            for r in s.rollover_reports.values()
            for item in r.items
        ))
        rollover_module.issue_count = total_fail
        rollover_module.critical_count = len(entities_with_issues)
        rollover_module.status = "warning" if total_fail > 0 else "completed"

    data.modules.append(rollover_module)

    # ── Reconciliation module ──
    recon_module = ModuleStatus(
        name="Reconcile", key="reconciliation", icon="compare_arrows",
        route="/reconciliation", status="not_run",
    )
    data.modules.append(recon_module)

    # ── Compute aggregates ──
    data.modules_completed = sum(1 for m in data.modules if m.status in ("completed", "warning"))
    data.completion_pct = data.modules_completed / data.total_modules * 100

    # Overall status
    if not s.report and not s.current_xml:
        data.overall_status = "not_started"
    elif data.critical_issues > 0:
        data.overall_status = "critical"
    elif data.total_issues > 0:
        data.overall_status = "issues"
    else:
        data.overall_status = "clean"

    # ── Recent history ──
    data.recent_history = list(reversed(s.history[-5:])) if s.history else []

    # ── Action items ──
    if not s.current_xml:
        data.action_items.append({
            "icon": "upload_file",
            "text": "Load an XML e-file to start your compliance review",
            "route": "/review",
            "priority": "high",
        })
    elif not s.report:
        data.action_items.append({
            "icon": "play_circle",
            "text": "Run XML Check to analyze the loaded return",
            "route": "/review",
            "priority": "high",
        })

    if s.report and not s.prior_xml:
        data.action_items.append({
            "icon": "swap_vert",
            "text": "Upload Prior Year XML to enable rollover analysis",
            "route": "/review",
            "priority": "medium",
        })

    if s.report and not pdf_result:
        data.action_items.append({
            "icon": "picture_as_pdf",
            "text": "Run PDF Check to validate OIT print accuracy",
            "route": "/pdf-check",
            "priority": "medium",
        })

    if s.prior_xml and not s.rollover_reports:
        data.action_items.append({
            "icon": "swap_vert",
            "text": "Generate Rollover reports for year-over-year comparison",
            "route": "/review",
            "priority": "medium",
        })

    if data.critical_issues > 0:
        data.action_items.append({
            "icon": "error",
            "text": f"{data.critical_issues} critical issues require attention",
            "route": "/review",
            "priority": "high",
        })

    return data

"""CSV Exporter — Flat file output for RolloverReport data.

Generates one CSV per report with all items (pass and fail).
Useful for downstream analysis in Excel, pandas, or BI tools.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from lab.xml_parser.core.models import RolloverReport, ReviewReport


def _rollover_to_dataframe(report: RolloverReport, include_pass: bool = True) -> pd.DataFrame:
    """Convert RolloverReport to flat DataFrame."""
    records = []
    for item in report.items:
        if not include_pass and item.passes:
            continue
        records.append({
            "Entity": item.entity_name,
            "Ref ID": item.reference_id,
            "Line": item.line,
            "Description": item.field_description,
            "PY Value": item.py_value,
            "CY Value": item.cy_value,
            "Difference": item.difference if item.difference != 0 else "",
            "Status": "OK" if item.passes else "Review",
        })
    return pd.DataFrame(records) if records else pd.DataFrame()


def export_csv(
    reports: dict[str, RolloverReport],
    output_dir: str | Path,
    prefix: str = "review",
    include_pass: bool = True,
) -> list[Path]:
    """Export all reports as individual CSV files.

    Args:
        reports: Dict of report name -> RolloverReport
        output_dir: Directory to write CSVs into
        prefix: Filename prefix
        include_pass: If True, include passing items (default: True)

    Returns:
        List of created file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files_created = []
    for name, report in reports.items():
        safe_name = name.replace(" ", "_").replace("/", "-").lower()
        df = _rollover_to_dataframe(report, include_pass=include_pass)
        if not df.empty:
            path = output_dir / f"{prefix}_{safe_name}.csv"
            df.to_csv(path, index=False)
            files_created.append(path)

    return files_created


def export_findings_csv(
    report: ReviewReport,
    output_path: str | Path,
) -> Path | None:
    """Export ReviewReport findings as a single CSV.

    Returns the output path, or None if no findings.
    """
    if not report or not report.findings:
        return None

    df = report.to_dataframe()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path

"""XML Comparison Engine — compare two IRS e-file returns."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from lab.xml_parser.parser import EFileParser


@dataclass
class FieldChange:
    entity_name: str
    field: str
    old_value: str
    new_value: str
    change_type: str  # "modified", "added", "removed"
    numeric_diff: Optional[float] = None
    material: bool = False


@dataclass
class EntityChange:
    entity_name: str
    change_type: str  # "added", "removed", "modified"
    field_changes: list = field(default_factory=list)


@dataclass
class ComparisonReport:
    file_1: Path
    file_2: Path
    entities_added: list = field(default_factory=list)
    entities_removed: list = field(default_factory=list)
    entities_modified: list = field(default_factory=list)
    total_field_changes: int = 0
    material_changes: int = 0

    @property
    def summary(self) -> str:
        return (
            f"Comparison: {self.file_1.name} vs {self.file_2.name}\n"
            f"  Added entities: {len(self.entities_added)}\n"
            f"  Removed entities: {len(self.entities_removed)}\n"
            f"  Modified entities: {len(self.entities_modified)}\n"
            f"  Total field changes: {self.total_field_changes}\n"
            f"  Material changes (>{self.threshold}): {self.material_changes}"
        )

    threshold: float = 1000.0


class XMLComparator:
    """Compare two IRS e-file XML returns field-by-field."""

    def __init__(self, threshold: float = 1000.0):
        self.threshold = threshold

    def compare(
        self,
        path_1: str | Path,
        path_2: str | Path,
        forms: Optional[list[str]] = None,
    ) -> ComparisonReport:
        """Compare two XML files and generate a delta report."""
        parser_1 = EFileParser(path_1)
        parser_2 = EFileParser(path_2)

        df1 = parser_1.to_dataframe(forms)
        df2 = parser_2.to_dataframe(forms)

        report = ComparisonReport(
            file_1=Path(path_1),
            file_2=Path(path_2),
            threshold=self.threshold,
        )

        # Match entities by name (primary) or reference_id (fallback)
        entities_1 = set(df1["_entity_name"].dropna())
        entities_2 = set(df2["_entity_name"].dropna())

        report.entities_added = sorted(entities_2 - entities_1)
        report.entities_removed = sorted(entities_1 - entities_2)
        common_entities = entities_1 & entities_2

        # Compare field-by-field for common entities
        for entity in sorted(common_entities):
            row1 = df1[df1["_entity_name"] == entity].iloc[0] if len(df1[df1["_entity_name"] == entity]) > 0 else None
            row2 = df2[df2["_entity_name"] == entity].iloc[0] if len(df2[df2["_entity_name"] == entity]) > 0 else None

            if row1 is None or row2 is None:
                continue

            entity_change = EntityChange(entity_name=entity, change_type="modified")
            all_cols = set(row1.index) | set(row2.index)

            for col in sorted(all_cols):
                if col.startswith("_"):
                    continue

                val1 = str(row1.get(col, "")) if col in row1.index else ""
                val2 = str(row2.get(col, "")) if col in row2.index else ""

                if val1 == val2:
                    continue
                if val1 in ("", "nan", "None") and val2 in ("", "nan", "None"):
                    continue

                change = FieldChange(
                    entity_name=entity,
                    field=col,
                    old_value=val1,
                    new_value=val2,
                    change_type="modified",
                )

                # Check if numeric difference
                try:
                    num1 = float(val1) if val1 and val1 not in ("", "nan", "None") else 0.0
                    num2 = float(val2) if val2 and val2 not in ("", "nan", "None") else 0.0
                    change.numeric_diff = num2 - num1
                    change.material = abs(change.numeric_diff) > self.threshold
                except (ValueError, TypeError):
                    pass

                entity_change.field_changes.append(change)
                report.total_field_changes += 1
                if change.material:
                    report.material_changes += 1

            if entity_change.field_changes:
                report.entities_modified.append(entity_change)

        return report

    def to_dataframe(self, report: ComparisonReport) -> pd.DataFrame:
        """Convert comparison report to a DataFrame for Excel export."""
        records = []
        for ec in report.entities_modified:
            for fc in ec.field_changes:
                records.append({
                    "Entity": fc.entity_name,
                    "Field": fc.field,
                    "Old Value": fc.old_value,
                    "New Value": fc.new_value,
                    "Numeric Diff": fc.numeric_diff,
                    "Material": fc.material,
                })

        for entity in report.entities_added:
            records.append({"Entity": entity, "Field": "(entity added)", "Old Value": "", "New Value": "NEW", "Numeric Diff": None, "Material": True})
        for entity in report.entities_removed:
            records.append({"Entity": entity, "Field": "(entity removed)", "Old Value": "REMOVED", "New Value": "", "Numeric Diff": None, "Material": True})

        return pd.DataFrame(records)

    def to_markdown(self, report: ComparisonReport) -> str:
        """Generate markdown comparison report."""
        lines = [
            f"# XML Comparison Report",
            f"",
            f"**File 1**: {report.file_1.name}",
            f"**File 2**: {report.file_2.name}",
            f"**Threshold**: ${report.threshold:,.0f}",
            f"",
            f"## Summary",
            f"- Entities added: {len(report.entities_added)}",
            f"- Entities removed: {len(report.entities_removed)}",
            f"- Entities modified: {len(report.entities_modified)}",
            f"- Total field changes: {report.total_field_changes}",
            f"- **Material changes**: {report.material_changes}",
            f"",
        ]

        if report.entities_added:
            lines.append("## Added Entities")
            for e in report.entities_added:
                lines.append(f"- {e}")
            lines.append("")

        if report.entities_removed:
            lines.append("## Removed Entities")
            for e in report.entities_removed:
                lines.append(f"- {e}")
            lines.append("")

        if report.entities_modified:
            lines.append("## Material Changes")
            lines.append("")
            lines.append("| Entity | Field | Old | New | Diff |")
            lines.append("|--------|-------|-----|-----|------|")
            for ec in report.entities_modified:
                for fc in ec.field_changes:
                    if fc.material:
                        diff_str = f"{fc.numeric_diff:+,.0f}" if fc.numeric_diff else ""
                        lines.append(f"| {fc.entity_name[:30]} | {fc.field[:50]} | {fc.old_value[:15]} | {fc.new_value[:15]} | {diff_str} |")

        return "\n".join(lines)

"""PDF Comparator — Compare two PDFs of the same schedule (PY vs CY).

Extracts data from both PDFs via PDFExtractor and compares field-by-field,
producing a structured report of changes, new items, and dropped items.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from lab.pdf_validator.extractor import PDFExtractor


@dataclass
class ComparisonItem:
    """One field-level comparison between PY and CY PDFs."""
    entity_name: str
    reference_id: str
    basket: str
    schedule: str
    field_name: str
    pool_name: str = ""
    py_value: float = 0.0
    cy_value: float = 0.0
    delta: float = 0.0
    status: str = "UNCHANGED"  # UNCHANGED, CHANGED, NEW_IN_CY, DROPPED_FROM_PY


@dataclass
class PDFComparisonReport:
    """Result of comparing two PDFs of the same schedule."""
    schedule: str
    py_source: str
    cy_source: str
    items: list[ComparisonItem] = field(default_factory=list)
    comparison_duration_ms: float = 0.0

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def unchanged_count(self) -> int:
        return sum(1 for i in self.items if i.status == "UNCHANGED")

    @property
    def changed_count(self) -> int:
        return sum(1 for i in self.items if i.status == "CHANGED")

    @property
    def new_count(self) -> int:
        return sum(1 for i in self.items if i.status == "NEW_IN_CY")

    @property
    def dropped_count(self) -> int:
        return sum(1 for i in self.items if i.status == "DROPPED_FROM_PY")

    @property
    def changes(self) -> list[ComparisonItem]:
        return [i for i in self.items if i.status != "UNCHANGED"]

    def summary_line(self) -> str:
        return (
            f"Schedule {self.schedule}: {self.total} fields compared — "
            f"{self.unchanged_count} unchanged, {self.changed_count} changed, "
            f"{self.new_count} new in CY, {self.dropped_count} dropped from PY"
        )


class PDFComparator:
    """Compare two PDFs of the same schedule field-by-field.

    Uses PDFExtractor to get normalized DataFrames from each PDF,
    then matches rows by (reference_id, basket, pool_name, field_name).
    """

    def __init__(
        self,
        py_pdf: Path | str,
        cy_pdf: Path | str,
        schedule: str = "J",
        threshold: float = 1.0,
    ):
        self.py_path = Path(py_pdf)
        self.cy_path = Path(cy_pdf)
        self.schedule = schedule.upper()
        self.threshold = threshold

    def compare(self) -> PDFComparisonReport:
        """Extract both PDFs and compare field-by-field."""
        start = time.perf_counter()

        py_extractor = PDFExtractor(self.py_path, schedule=self.schedule)
        cy_extractor = PDFExtractor(self.cy_path, schedule=self.schedule)

        py_df = py_extractor.extract()
        cy_df = cy_extractor.extract()

        items = self._compare_dataframes(py_df, cy_df)

        report = PDFComparisonReport(
            schedule=self.schedule,
            py_source=str(self.py_path),
            cy_source=str(self.cy_path),
            items=items,
            comparison_duration_ms=(time.perf_counter() - start) * 1000,
        )
        return report

    def _compare_dataframes(
        self, py_df: pd.DataFrame, cy_df: pd.DataFrame
    ) -> list[ComparisonItem]:
        """Compare two DataFrames row-by-row using composite key."""
        key_cols = ["reference_id", "basket", "pool_name", "field_name"]

        py_indexed = self._index_dataframe(py_df, key_cols)
        cy_indexed = self._index_dataframe(cy_df, key_cols)

        all_keys = set(py_indexed.keys()) | set(cy_indexed.keys())
        items = []

        for key in sorted(all_keys):
            ref_id, basket, pool_name, field_name = key
            py_row = py_indexed.get(key)
            cy_row = cy_indexed.get(key)

            if py_row is not None and cy_row is not None:
                py_val = py_row["value"]
                cy_val = cy_row["value"]
                delta = cy_val - py_val
                status = "UNCHANGED" if abs(delta) <= self.threshold else "CHANGED"
                entity_name = cy_row.get("entity_name", "")
            elif cy_row is not None:
                py_val = 0.0
                cy_val = cy_row["value"]
                delta = cy_val
                status = "NEW_IN_CY"
                entity_name = cy_row.get("entity_name", "")
            else:
                py_val = py_row["value"]
                cy_val = 0.0
                delta = -py_val
                status = "DROPPED_FROM_PY"
                entity_name = py_row.get("entity_name", "")

            items.append(ComparisonItem(
                entity_name=entity_name,
                reference_id=ref_id,
                basket=basket,
                schedule=self.schedule,
                field_name=field_name,
                pool_name=pool_name,
                py_value=py_val,
                cy_value=cy_val,
                delta=delta,
                status=status,
            ))

        return items

    def _index_dataframe(
        self, df: pd.DataFrame, key_cols: list[str]
    ) -> dict[tuple, dict]:
        """Index a DataFrame by composite key for O(1) lookup."""
        if df.empty:
            return {}

        indexed = {}
        for _, row in df.iterrows():
            key = tuple(str(row.get(c, "")) for c in key_cols)
            indexed[key] = {
                "value": float(row.get("value", 0) or 0),
                "entity_name": str(row.get("entity_name", "")),
            }
        return indexed

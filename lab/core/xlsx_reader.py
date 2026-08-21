"""Robust xlsx reader using zipfile+XML approach.

Handles workbooks with broken print titles (#N/A) that crash openpyxl.
Reads values, formulas, and sheet structure directly from the XML.
"""

import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import iterparse

import pandas as pd


class XlsxReader:
    """Read xlsx files directly from their XML internals."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Workbook not found: {self.path}")
        self._shared_strings: list[str] = []
        self._sheets: dict[str, str] = {}
        self._load_metadata()

    def _load_metadata(self):
        with zipfile.ZipFile(self.path) as z:
            self._shared_strings = self._parse_shared_strings(z)
            self._sheets = self._parse_sheet_targets(z)

    def _parse_shared_strings(self, z: zipfile.ZipFile) -> list[str]:
        try:
            ss_data = z.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        strings = []
        current_texts = []
        for _, elem in iterparse(BytesIO(ss_data), events=["end"]):
            if elem.tag.endswith("}t"):
                if elem.text:
                    current_texts.append(elem.text)
            elif elem.tag.endswith("}si"):
                strings.append("".join(current_texts))
                current_texts = []
                elem.clear()
        return strings

    def _parse_sheet_targets(self, z: zipfile.ZipFile) -> dict[str, str]:
        wb_xml = z.read("xl/workbook.xml").decode("utf-8")
        rels_xml = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        sheets = re.findall(
            r'name="([^"]+)"[^>]*sheetId="(\d+)"[^>]*r:id="([^"]+)"', wb_xml
        )
        rels = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels_xml))
        return {name: rels.get(rid, "") for name, _, rid in sheets}

    @property
    def sheet_names(self) -> list[str]:
        return list(self._sheets.keys())

    def read_sheet(
        self, sheet_name: str, include_formulas: bool = False
    ) -> tuple[dict[int, dict[str, str]], Optional[dict[int, dict[str, str]]]]:
        """Read a sheet's values and optionally formulas.

        Returns:
            (rows_data, formulas) where each is {row_num: {col_letter: value}}
            formulas is None if include_formulas=False
        """
        target = self._sheets.get(sheet_name)
        if not target:
            raise ValueError(
                f"Sheet '{sheet_name}' not found. Available: {self.sheet_names}"
            )

        with zipfile.ZipFile(self.path) as z:
            sheet_data = z.read(f"xl/{target}")

        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        rows_data: dict[int, dict[str, str]] = {}
        formulas: dict[int, dict[str, str]] = {} if include_formulas else None

        for _, elem in iterparse(BytesIO(sheet_data), events=["end"]):
            if elem.tag == f"{ns}c":
                ref = elem.get("r", "")
                cell_type = elem.get("t", "")
                val_elem = elem.find(f"{ns}v")
                f_elem = elem.find(f"{ns}f")

                col_match = re.match(r"([A-Z]+)(\d+)", ref)
                if not col_match:
                    continue
                col, row = col_match.group(1), int(col_match.group(2))

                if val_elem is not None and val_elem.text:
                    if cell_type == "s":
                        idx = int(val_elem.text)
                        val = (
                            self._shared_strings[idx]
                            if idx < len(self._shared_strings)
                            else ""
                        )
                    else:
                        val = val_elem.text
                    rows_data.setdefault(row, {})[col] = val

                if include_formulas and f_elem is not None and f_elem.text:
                    formulas.setdefault(row, {})[col] = f_elem.text

            elif elem.tag == f"{ns}row":
                elem.clear()

        return rows_data, formulas

    def read_sheet_as_df(
        self,
        sheet_name: str,
        header_row: int = 1,
        data_start_row: Optional[int] = None,
    ) -> pd.DataFrame:
        """Read a sheet into a pandas DataFrame.

        Args:
            sheet_name: Name of the sheet
            header_row: Row number containing column headers
            data_start_row: First row of data (defaults to header_row + 1)
        """
        rows_data, _ = self.read_sheet(sheet_name)
        if not rows_data:
            return pd.DataFrame()

        if data_start_row is None:
            data_start_row = header_row + 1

        headers = rows_data.get(header_row, {})
        col_names = {col: headers.get(col, col) for col in sorted(headers.keys())}

        records = []
        for row_num in sorted(rows_data.keys()):
            if row_num < data_start_row:
                continue
            record = {"_row": row_num}
            for col, name in col_names.items():
                record[name] = rows_data[row_num].get(col, None)
            records.append(record)

        return pd.DataFrame(records)

    def get_entity_columns(
        self, sheet_name: str, code_row: int = 4, name_row: int = 5, skip_cols: int = 4
    ) -> list[dict]:
        """Extract entity column mapping from a sheet.

        Returns list of {col, code, name} for entity columns.
        """
        rows_data, _ = self.read_sheet(sheet_name)
        codes = rows_data.get(code_row, {})
        names = rows_data.get(name_row, {})

        entities = []
        skip_letters = set()
        for i, col in enumerate(sorted(codes.keys())):
            if i < skip_cols:
                skip_letters.add(col)
                continue
            entities.append(
                {
                    "col": col,
                    "code": codes.get(col, ""),
                    "name": names.get(col, "")[:40],
                }
            )
        return entities

    def get_numeric(self, rows_data: dict, row: int, col: str) -> float:
        """Safely extract a numeric value from parsed sheet data."""
        try:
            return float(rows_data.get(row, {}).get(col, 0) or 0)
        except (ValueError, TypeError):
            return 0.0

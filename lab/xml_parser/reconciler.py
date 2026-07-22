"""Reconciler — Workbook vs XML Automated Comparison Engine.

Compares WorkbookReader output against EFileParser output field-by-field
with tolerance, producing structured discrepancy reports.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import numpy as np


@dataclass
class FieldResult:
    entity_code: str
    schedule: str
    field_name: str
    line: str
    wb_value: object = None
    xml_value: object = None
    delta: float | None = None
    status: str = "PASS"  # PASS, FAIL, DORMANT_OK, XML_MISSING, WB_MISSING, TYPE_MISMATCH


@dataclass
class ReconciliationReport:
    results: list[FieldResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.results:
            return pd.DataFrame()
        records = [
            {
                "entity_code": r.entity_code,
                "schedule": r.schedule,
                "field_name": r.field_name,
                "line": r.line,
                "wb_value": r.wb_value,
                "xml_value": r.xml_value,
                "delta": r.delta,
                "status": r.status,
            }
            for r in self.results
        ]
        return pd.DataFrame(records)

    def failures_only(self) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        return df[df["status"] == "FAIL"]

    def to_excel(self, path: str | Path):
        df = self.to_dataframe()
        if df.empty:
            return
        path = Path(path)
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="All Results", index=False)
            fails = df[df["status"] == "FAIL"]
            if not fails.empty:
                fails.to_excel(writer, sheet_name="Failures", index=False)
            summary_df = pd.DataFrame([self.summary])
            summary_df.to_excel(writer, sheet_name="Summary", index=False)


# Maps workbook schedule keys to XML form keys and the column prefix
# used by EFileParser in to_dataframe() or extract_form()
SCHEDULE_MAP = {
    "sch_h_fc": {
        "xml_form": "IRS5471ScheduleH",
        "mode": "extract_form",
        "prefix": "IRS5471ScheduleH_",
    },
    "sch_i1_fc": {
        "xml_form": "IRS5471ScheduleI1",
        "mode": "extract_form",
        "prefix": "IRS5471ScheduleI1_",
    },
    "sch_i": {
        "xml_form": "IRS5471ScheduleI",
        "mode": "extract_form",
        "prefix": "IRS5471ScheduleI_",
    },
    "sch_c_fc": {
        "xml_form": "IRS5471ScheduleC",
        "mode": "main_df",
        "prefix": "IRS5471_IRS5471ScheduleC_",
    },
    "sch_f_usd": {
        "xml_form": "IRS5471ScheduleF",
        "mode": "main_df",
        "prefix": "IRS5471_IRS5471ScheduleF_",
    },
    "sch_e": {
        "xml_form": "IRS5471ScheduleE",
        "mode": "extract_form",
        "prefix": "IRS5471ScheduleE_",
    },
}


class Reconciler:
    """Compare WorkbookReader data against EFileParser data."""

    def __init__(self, tolerance: float = 1.0):
        self.tolerance = tolerance

    def reconcile(
        self,
        wb_data,
        parser,
        schedules: list[str] | None = None,
    ) -> ReconciliationReport:
        """Run full reconciliation.

        Args:
            wb_data: WorkbookData from WorkbookReader.parse()
            parser: EFileParser instance (already parsed)
            schedules: list of schedule keys to reconcile, or None for all
        """
        if schedules is None:
            schedules = [k for k in SCHEDULE_MAP if k in wb_data.schedules]

        all_results = []
        main_df = None

        for sched_key in schedules:
            if sched_key not in SCHEDULE_MAP:
                continue
            config = SCHEDULE_MAP[sched_key]

            # Get XML data
            xml_df = self._get_xml_df(parser, config, main_df)
            if xml_df is None:
                # Cache main_df on first use
                if config["mode"] == "main_df" and main_df is None:
                    main_df = parser.to_dataframe()
                    if "_reference_id" in main_df.columns:
                        main_df = main_df.set_index("_reference_id")
                    xml_df = self._get_xml_df(parser, config, main_df)

            if xml_df is None or xml_df.empty:
                continue

            # Get workbook data
            wb_df = wb_data.schedules.get(sched_key, pd.DataFrame())
            if wb_df.empty:
                continue

            # Compare
            results = self._compare_schedule(sched_key, wb_df, xml_df, config)
            all_results.extend(results)

        report = ReconciliationReport(results=all_results)
        report.summary = self._compute_summary(all_results)
        return report

    def _get_xml_df(self, parser, config, main_df) -> pd.DataFrame | None:
        """Get XML DataFrame for a schedule, indexed by entity code."""
        if config["mode"] == "extract_form":
            df = parser.extract_form(config["xml_form"])
            if df.empty:
                return None
            if "_reference_id" in df.columns:
                df = df.set_index("_reference_id")
            return df
        elif config["mode"] == "main_df":
            if main_df is None:
                return None
            return main_df
        return None

    def _compare_schedule(
        self, sched_key: str, wb_df: pd.DataFrame, xml_df: pd.DataFrame, config: dict
    ) -> list[FieldResult]:
        """Compare a single schedule between workbook and XML."""
        results = []
        prefix = config["prefix"]

        # Get comparable fields: workbook columns that have XML equivalents
        wb_fields = [c for c in wb_df.columns if c != "_entity_code" and not c.startswith("_")]

        # Build XML column map: strip prefix to get base field name
        xml_col_map = {}
        for col in xml_df.columns:
            if col.startswith(prefix):
                base_name = col[len(prefix):]
                xml_col_map[base_name] = col

        # Find overlapping entities
        wb_entities = set(wb_df.index)
        xml_entities = set(xml_df.index)

        for entity_code in sorted(wb_entities):
            if entity_code not in xml_entities:
                for field_name in wb_fields:
                    if field_name in xml_col_map:
                        results.append(FieldResult(
                            entity_code=entity_code,
                            schedule=sched_key,
                            field_name=field_name,
                            line=self._get_line(field_name),
                            wb_value=wb_df.loc[entity_code, field_name],
                            xml_value=None,
                            delta=None,
                            status="XML_MISSING",
                        ))
                continue

            for field_name in wb_fields:
                xml_col = xml_col_map.get(field_name)
                if xml_col is None:
                    continue

                wb_val = wb_df.loc[entity_code, field_name]
                try:
                    xml_val = xml_df.loc[entity_code, xml_col]
                except KeyError:
                    xml_val = None

                result = self._compare_field(
                    entity_code, sched_key, field_name, wb_val, xml_val
                )
                results.append(result)

        return results

    def _compare_field(
        self, entity_code: str, schedule: str, field_name: str,
        wb_val, xml_val
    ) -> FieldResult:
        """Compare a single field value between sources."""
        line = self._get_line(field_name)

        # Handle NaN/None cases
        wb_is_null = wb_val is None or (isinstance(wb_val, float) and np.isnan(wb_val))
        xml_is_null = xml_val is None or (isinstance(xml_val, float) and np.isnan(xml_val))

        if wb_is_null and xml_is_null:
            return FieldResult(entity_code, schedule, field_name, line,
                             wb_val, xml_val, 0.0, "PASS")

        # Dormant pattern: XML has NaN, workbook has 0
        if xml_is_null and not wb_is_null:
            try:
                if float(wb_val) == 0:
                    return FieldResult(entity_code, schedule, field_name, line,
                                     wb_val, xml_val, None, "DORMANT_OK")
            except (ValueError, TypeError):
                pass

        # Type handling
        try:
            wb_num = float(wb_val) if not wb_is_null else 0.0
            xml_num = float(xml_val) if not xml_is_null else 0.0
        except (ValueError, TypeError):
            # String comparison
            if str(wb_val).strip() == str(xml_val).strip():
                return FieldResult(entity_code, schedule, field_name, line,
                                 wb_val, xml_val, None, "PASS")
            return FieldResult(entity_code, schedule, field_name, line,
                             wb_val, xml_val, None, "TYPE_MISMATCH")

        delta = abs(wb_num - xml_num)
        status = "PASS" if delta <= self.tolerance else "FAIL"

        return FieldResult(entity_code, schedule, field_name, line,
                         wb_val, xml_val, delta, status)

    def _get_line(self, field_name: str) -> str:
        """Get the form line number for a field name from field_maps."""
        try:
            from lab.xml_parser.field_maps import FIELD_MAPS
            for form_fields in FIELD_MAPS.values():
                if field_name in form_fields:
                    return form_fields[field_name].get("line", "")
        except ImportError:
            pass
        return ""

    def _compute_summary(self, results: list[FieldResult]) -> dict:
        """Compute summary statistics from results."""
        if not results:
            return {"total": 0, "pass_count": 0, "fail_count": 0, "pass_rate": 0.0}

        total = len(results)
        pass_count = sum(1 for r in results if r.status == "PASS")
        fail_count = sum(1 for r in results if r.status == "FAIL")
        dormant_ok = sum(1 for r in results if r.status == "DORMANT_OK")
        xml_missing = sum(1 for r in results if r.status == "XML_MISSING")

        # Pass rate excludes XML_MISSING (not a real comparison)
        comparable = total - xml_missing
        pass_rate = (pass_count + dormant_ok) / comparable if comparable > 0 else 0.0

        # By schedule
        by_schedule = {}
        for r in results:
            if r.schedule not in by_schedule:
                by_schedule[r.schedule] = {"pass": 0, "fail": 0, "dormant_ok": 0, "total": 0}
            by_schedule[r.schedule]["total"] += 1
            if r.status == "PASS":
                by_schedule[r.schedule]["pass"] += 1
            elif r.status == "FAIL":
                by_schedule[r.schedule]["fail"] += 1
            elif r.status == "DORMANT_OK":
                by_schedule[r.schedule]["dormant_ok"] += 1

        return {
            "total": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "dormant_ok": dormant_ok,
            "xml_missing": xml_missing,
            "pass_rate": round(pass_rate, 4),
            "by_schedule": by_schedule,
        }

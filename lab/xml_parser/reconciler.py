"""Reconciler — Multi-Source Automated Comparison Engine.

Compares WorkbookReader, EFileParser, and OITDataSource outputs field-by-field
with tolerance. Supports two-way (WB vs XML) and three-way (OIT vs WB vs XML)
reconciliation with structured discrepancy reports.
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
class ComparisonResult:
    """Result of a three-way comparison for a single field."""
    entity_code: str
    schedule: str
    field_name: str
    line: str
    oit_value: object = None
    wb_value: object = None
    xml_value: object = None
    oit_wb_delta: float | None = None
    oit_xml_delta: float | None = None
    wb_xml_delta: float | None = None
    status: str = "PASS"
    # Statuses: PASS, FAIL_OIT_WB, FAIL_OIT_XML, FAIL_WB_XML, FAIL_ALL,
    #           OIT_MISSING, WB_MISSING, XML_MISSING, PASS_SIGN_FLIP, DORMANT_OK


@dataclass
class ThreeWayReport:
    """Report for three-way reconciliation (OIT vs WB vs XML)."""
    results: list[ComparisonResult] = field(default_factory=list)
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
                "oit_value": r.oit_value,
                "wb_value": r.wb_value,
                "xml_value": r.xml_value,
                "oit_wb_delta": r.oit_wb_delta,
                "oit_xml_delta": r.oit_xml_delta,
                "wb_xml_delta": r.wb_xml_delta,
                "status": r.status,
            }
            for r in self.results
        ]
        return pd.DataFrame(records)

    def failures_only(self) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        return df[df["status"].str.startswith("FAIL")]

    def by_schedule(self) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        return df.groupby("schedule")["status"].value_counts().unstack(fill_value=0)

    def by_entity(self) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        return df.groupby("entity_code")["status"].value_counts().unstack(fill_value=0)

    def to_excel(self, path: str | Path):
        df = self.to_dataframe()
        if df.empty:
            return
        path = Path(path)
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            summary_df = pd.DataFrame([self.summary])
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
            df.to_excel(writer, sheet_name="Three-Way Results", index=False)
            fails = self.failures_only()
            if not fails.empty:
                fails.to_excel(writer, sheet_name="Failures", index=False)
            by_sched = self.by_schedule()
            if not by_sched.empty:
                by_sched.to_excel(writer, sheet_name="By Schedule")
            by_ent = self.by_entity()
            if not by_ent.empty:
                by_ent.to_excel(writer, sheet_name="By Entity")


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


SIGN_FLIP_FIELDS = {
    "TotalNetSubtractionsAmt",
    "OtherAdjustmentsNetSbtrctnAmt",
    "TotalTaxInFunctionalCurAmt",
    "TotalTaxInUSDollarsAmt",
    "SchEIncomeSubjectToTaxAmt",
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

        if delta > self.tolerance and field_name in SIGN_FLIP_FIELDS:
            abs_delta = abs(abs(wb_num) - abs(xml_num))
            if abs_delta <= self.tolerance:
                return FieldResult(entity_code, schedule, field_name, line,
                                 wb_val, xml_val, abs_delta, "PASS_SIGN_FLIP")

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

    # ------------------------------------------------------------------
    # Three-Way Reconciliation (OIT vs WB vs XML)
    # ------------------------------------------------------------------

    def reconcile_three_way(
        self,
        oit_data,
        wb_data,
        parser,
        schedules: list[str] | None = None,
    ) -> ThreeWayReport:
        """Three-way reconciliation: OIT vs WB vs XML.

        Args:
            oit_data: OITDataSource instance (from lab.core.oit_parser)
            wb_data: WorkbookData from WorkbookReader.parse()
            parser: EFileParser instance (already parsed)
            schedules: list of schedule keys to reconcile, or None for all shared
        """
        if schedules is None:
            oit_keys = set(oit_data.schedules.keys()) if oit_data else set()
            wb_keys = set(wb_data.schedules.keys()) if wb_data else set()
            xml_keys = set(SCHEDULE_MAP.keys())
            schedules = sorted(oit_keys & (wb_keys | xml_keys))

        all_results = []
        main_df = None

        for sched_key in schedules:
            # Get OIT DataFrame
            oit_df = oit_data.get_schedule(sched_key) if oit_data else pd.DataFrame()

            # Get WB DataFrame
            wb_df = wb_data.schedules.get(sched_key, pd.DataFrame()) if wb_data else pd.DataFrame()

            # Get XML DataFrame
            xml_df = pd.DataFrame()
            if sched_key in SCHEDULE_MAP:
                config = SCHEDULE_MAP[sched_key]
                xml_df = self._get_xml_df(parser, config, main_df)
                if xml_df is None and config["mode"] == "main_df" and main_df is None:
                    main_df = parser.to_dataframe()
                    if "_reference_id" in main_df.columns:
                        main_df = main_df.set_index("_reference_id")
                    xml_df = self._get_xml_df(parser, config, main_df)
                if xml_df is None:
                    xml_df = pd.DataFrame()

            # Skip if no data at all
            if oit_df.empty and wb_df.empty and xml_df.empty:
                continue

            results = self._compare_three_way(sched_key, oit_df, wb_df, xml_df)
            all_results.extend(results)

        report = ThreeWayReport(results=all_results)
        report.summary = self._compute_three_way_summary(all_results)
        return report

    def _compare_three_way(
        self,
        sched_key: str,
        oit_df: pd.DataFrame,
        wb_df: pd.DataFrame,
        xml_df: pd.DataFrame,
    ) -> list[ComparisonResult]:
        """Compare a single schedule across three sources."""
        results = []
        config = SCHEDULE_MAP.get(sched_key, {})
        prefix = config.get("prefix", "")

        # Determine fields to compare from OIT columns (they already match XML field names)
        oit_fields = set()
        if not oit_df.empty:
            oit_fields = {c for c in oit_df.columns if not c.startswith("_")}

        wb_fields = set()
        if not wb_df.empty:
            wb_fields = {c for c in wb_df.columns if not c.startswith("_")}

        # XML fields: strip prefix
        xml_field_map = {}
        if not xml_df.empty:
            for col in xml_df.columns:
                if col.startswith(prefix):
                    base_name = col[len(prefix):]
                    xml_field_map[base_name] = col

        all_fields = sorted(oit_fields | wb_fields | set(xml_field_map.keys()))

        # Union of entities
        oit_entities = set(oit_df.index) if not oit_df.empty else set()
        wb_entities = set(wb_df.index) if not wb_df.empty else set()
        xml_entities = set(xml_df.index) if not xml_df.empty else set()
        all_entities = sorted(oit_entities | wb_entities | xml_entities)

        for entity_code in all_entities:
            for field_name in all_fields:
                oit_val = self._safe_get(oit_df, entity_code, field_name)
                wb_val = self._safe_get(wb_df, entity_code, field_name)
                xml_col = xml_field_map.get(field_name, field_name)
                xml_val = self._safe_get(xml_df, entity_code, xml_col)

                result = self._compare_three_values(
                    entity_code, sched_key, field_name, oit_val, wb_val, xml_val
                )
                results.append(result)

        return results

    def _safe_get(self, df: pd.DataFrame, entity: str, col: str):
        """Safely get a value from a DataFrame, returning None if not found."""
        if df.empty:
            return None
        if entity not in df.index:
            return None
        if col not in df.columns:
            return None
        val = df.loc[entity, col]
        if isinstance(val, float) and np.isnan(val):
            return None
        return val

    def _compare_three_values(
        self,
        entity_code: str,
        schedule: str,
        field_name: str,
        oit_val,
        wb_val,
        xml_val,
    ) -> ComparisonResult:
        """Compare a single field across three sources and determine status."""
        line = self._get_line(field_name)

        oit_null = oit_val is None
        wb_null = wb_val is None
        xml_null = xml_val is None

        # All missing
        if oit_null and wb_null and xml_null:
            return ComparisonResult(entity_code, schedule, field_name, line,
                                   status="PASS")

        # Source-missing statuses
        if oit_null and not wb_null and not xml_null:
            status = "OIT_MISSING"
        elif not oit_null and wb_null and not xml_null:
            status = "WB_MISSING"
        elif not oit_null and not wb_null and xml_null:
            status = "XML_MISSING"
        elif oit_null and wb_null and not xml_null:
            status = "OIT_MISSING"
        elif oit_null and not wb_null and xml_null:
            status = "OIT_MISSING"
        elif not oit_null and wb_null and xml_null:
            status = "WB_MISSING"
        else:
            status = None  # All three present, will compute below

        # If one or more sources missing but others have value = 0 → DORMANT_OK
        if status in ("OIT_MISSING", "WB_MISSING", "XML_MISSING"):
            present_vals = []
            if not oit_null:
                present_vals.append(oit_val)
            if not wb_null:
                present_vals.append(wb_val)
            if not xml_null:
                present_vals.append(xml_val)
            try:
                if all(float(v) == 0 for v in present_vals):
                    return ComparisonResult(entity_code, schedule, field_name, line,
                                           oit_val, wb_val, xml_val, status="DORMANT_OK")
            except (ValueError, TypeError):
                pass
            return ComparisonResult(entity_code, schedule, field_name, line,
                                   oit_val, wb_val, xml_val, status=status)

        # All three present — compute deltas
        try:
            oit_num = float(oit_val) if not oit_null else 0.0
            wb_num = float(wb_val) if not wb_null else 0.0
            xml_num = float(xml_val) if not xml_null else 0.0
        except (ValueError, TypeError):
            return ComparisonResult(entity_code, schedule, field_name, line,
                                   oit_val, wb_val, xml_val, status="TYPE_MISMATCH")

        oit_wb_delta = abs(oit_num - wb_num)
        oit_xml_delta = abs(oit_num - xml_num)
        wb_xml_delta = abs(wb_num - xml_num)

        # Check sign flip
        if field_name in SIGN_FLIP_FIELDS:
            oit_wb_delta = abs(abs(oit_num) - abs(wb_num))
            oit_xml_delta = abs(abs(oit_num) - abs(xml_num))
            wb_xml_delta = abs(abs(wb_num) - abs(xml_num))

        oit_wb_pass = oit_wb_delta <= self.tolerance
        oit_xml_pass = oit_xml_delta <= self.tolerance
        wb_xml_pass = wb_xml_delta <= self.tolerance

        if oit_wb_pass and oit_xml_pass and wb_xml_pass:
            final_status = "PASS"
            if field_name in SIGN_FLIP_FIELDS:
                # Check if any original sign differs
                signs_differ = (
                    (oit_num > 0 and wb_num < 0) or (oit_num < 0 and wb_num > 0) or
                    (oit_num > 0 and xml_num < 0) or (oit_num < 0 and xml_num > 0)
                )
                if signs_differ:
                    final_status = "PASS_SIGN_FLIP"
        elif not oit_wb_pass and not oit_xml_pass and not wb_xml_pass:
            final_status = "FAIL_ALL"
        elif not oit_wb_pass and oit_xml_pass:
            final_status = "FAIL_OIT_WB"
        elif not oit_xml_pass and oit_wb_pass:
            final_status = "FAIL_OIT_XML"
        elif not wb_xml_pass and oit_wb_pass:
            final_status = "FAIL_WB_XML"
        else:
            final_status = "FAIL_ALL"

        return ComparisonResult(
            entity_code=entity_code,
            schedule=schedule,
            field_name=field_name,
            line=line,
            oit_value=oit_val,
            wb_value=wb_val,
            xml_value=xml_val,
            oit_wb_delta=oit_wb_delta,
            oit_xml_delta=oit_xml_delta,
            wb_xml_delta=wb_xml_delta,
            status=final_status,
        )

    def _compute_three_way_summary(self, results: list[ComparisonResult]) -> dict:
        """Compute summary statistics for three-way results."""
        if not results:
            return {"total": 0, "pass_count": 0, "fail_count": 0, "pass_rate": 0.0}

        total = len(results)
        pass_count = sum(1 for r in results if r.status in ("PASS", "PASS_SIGN_FLIP"))
        dormant_ok = sum(1 for r in results if r.status == "DORMANT_OK")
        fail_all = sum(1 for r in results if r.status == "FAIL_ALL")
        fail_oit_wb = sum(1 for r in results if r.status == "FAIL_OIT_WB")
        fail_oit_xml = sum(1 for r in results if r.status == "FAIL_OIT_XML")
        fail_wb_xml = sum(1 for r in results if r.status == "FAIL_WB_XML")
        oit_missing = sum(1 for r in results if r.status == "OIT_MISSING")
        wb_missing = sum(1 for r in results if r.status == "WB_MISSING")
        xml_missing = sum(1 for r in results if r.status == "XML_MISSING")

        comparable = total - oit_missing - wb_missing - xml_missing
        pass_rate = (pass_count + dormant_ok) / comparable if comparable > 0 else 0.0

        return {
            "total": total,
            "pass_count": pass_count,
            "fail_count": fail_all + fail_oit_wb + fail_oit_xml + fail_wb_xml,
            "dormant_ok": dormant_ok,
            "fail_all": fail_all,
            "fail_oit_wb": fail_oit_wb,
            "fail_oit_xml": fail_oit_xml,
            "fail_wb_xml": fail_wb_xml,
            "oit_missing": oit_missing,
            "wb_missing": wb_missing,
            "xml_missing": xml_missing,
            "pass_rate": round(pass_rate, 4),
        }

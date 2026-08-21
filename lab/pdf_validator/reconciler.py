"""PDF vs XML Reconciliation Engine.

Compares structured data extracted from OIT PDFs against XML-parsed values.
Classifies discrepancies by type: PHANTOM, MISSING, MISMATCH.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

NS = "http://www.irs.gov/efile"

# All Schedule J pools with IRS column letter and description
ALL_POOLS = [
    ("Post2017EPNotPrevTaxedGrp", "(a)", "Post-2017 E&P Not Prev Taxed"),
    ("Post1986UndistributedEarnGrp", "(b)", "Post-1986 Undistributed Earnings"),
    ("Pre1987EPNotPrevTaxedGrp", "(c)", "Pre-1987 E&P Not Previously Taxed"),
    ("HoveringDeficitDedSspndTaxGrp", "(d)", "Hovering Deficit"),
    ("ReclassifiedSect965aPTEPGrp", "(e)(i)", "Reclassified Sec 965(a) PTEP"),
    ("ReclassifiedSect965bPTEPGrp", "(e)(ii)", "Reclassified Sec 965(b) PTEP"),
    ("GeneralSection959c1PTEPGrp", "(e)(iii)", "General Sec 959(c)(1) PTEP"),
    ("ReclassifiedSect951APTEPGrp", "(e)(iv)", "Reclassified Sec 951A PTEP"),
    ("ReclassifiedSect245AdPTEPGrp", "(e)(v)", "Reclassified Sec 245A(d) PTEP"),
    ("Section965aPTEPGrp", "(e)(vi)", "Sec 965(a) PTEP"),
    ("Section965bPTEPGrp", "(e)(vii)", "Sec 965(b) PTEP"),
    ("Section951APTEPGrp", "(e)(viii)", "Sec 951A PTEP (GILTI)"),
    ("Section245AdPTEPGrp", "(e)(ix)", "Sec 245A(d) PTEP"),
    ("Section951a1APTEPGrp", "(e)(x)", "Sec 951(a)(1)(A) PTEP (SubF)"),
    ("TotalSection964AEPGrp", "(f)", "Total Sec 964(a) E&P"),
]

POOL_LOOKUP = {name: (col, desc) for name, col, desc in ALL_POOLS}

# Pools typically skipped during reconciliation (computed totals or rarely-used)
SKIP_POOLS = frozenset({
    "TotalSection964AEPGrp",
    "Pre1987EPNotPrevTaxedGrp",
    "ReclassifiedSect965aPTEPGrp",
    "ReclassifiedSect965bPTEPGrp",
    "GeneralSection959c1PTEPGrp",
    "ReclassifiedSect951APTEPGrp",
    "ReclassifiedSect245AdPTEPGrp",
})


@dataclass
class PDFDiscrepancy:
    """A single discrepancy between PDF and XML values."""
    entity_name: str
    reference_id: str
    basket: str
    schedule: str
    field: str
    field_description: str
    pdf_value: float
    xml_value: float
    delta: float
    status: str       # "OK", "PHANTOM", "MISSING", "MISMATCH"
    severity: str     # "HIGH", "MEDIUM", "LOW"

    @property
    def is_issue(self) -> bool:
        return self.status != "OK"


@dataclass
class PDFValidationReport:
    """Complete validation report from PDF vs XML reconciliation."""
    schedule: str
    pdf_source: str
    xml_source: str
    items: list[PDFDiscrepancy] = field(default_factory=list)

    @property
    def total_comparisons(self) -> int:
        return len(self.items)

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.status == "OK")

    @property
    def phantom_count(self) -> int:
        return sum(1 for i in self.items if i.status == "PHANTOM")

    @property
    def missing_count(self) -> int:
        return sum(1 for i in self.items if i.status == "MISSING")

    @property
    def mismatch_count(self) -> int:
        return sum(1 for i in self.items if i.status == "MISMATCH")

    @property
    def entities_checked(self) -> int:
        return len(set(i.reference_id for i in self.items))

    @property
    def entities_with_issues(self) -> list[str]:
        return sorted(set(i.reference_id for i in self.items if i.is_issue))

    @property
    def discrepancies(self) -> list[PDFDiscrepancy]:
        return [i for i in self.items if i.is_issue]

    @property
    def summary(self) -> str:
        if not self.items:
            return "No comparisons performed."
        issues = self.phantom_count + self.missing_count + self.mismatch_count
        if issues == 0:
            return (f"Schedule {self.schedule} PDF vs XML: {self.total_comparisons} checks, "
                    f"ALL OK across {self.entities_checked} entities.")
        return (f"Schedule {self.schedule} PDF vs XML: {self.total_comparisons} checks | "
                f"{self.ok_count} OK | {self.phantom_count} PHANTOM | "
                f"{self.missing_count} MISSING | {self.mismatch_count} MISMATCH | "
                f"{len(self.entities_with_issues)} entities with issues")


class PDFReconciler:
    """Compare PDF-extracted data against XML-parsed data for Schedule J.

    Builds an indexed lookup from PDF data on init to enable O(1) access
    during reconciliation instead of repeated DataFrame scans.
    """

    DEFAULT_TOLERANCE = 10.0  # $10 materiality threshold

    def __init__(self, pdf_data: pd.DataFrame, xml_path: Optional[Path | str] = None,
                 schedule: str = "J", xml_field: str = "BeginningYearBalanceAmt",
                 tolerance: float = DEFAULT_TOLERANCE,
                 skip_pools: Optional[set[str]] = None):
        """
        Args:
            pdf_data: DataFrame from PDFExtractor.extract() with columns:
                      entity_name, reference_id, basket, pool_name, field_name, value
            xml_path: Path to XML file to compare against
            schedule: Which schedule ("J", "F", "H", "I1")
            xml_field: Which XML field to compare (default: beginning balance)
            tolerance: Materiality threshold in dollars (default: $10)
            skip_pools: Pool names to exclude from reconciliation (uses SKIP_POOLS if None)
        """
        self.pdf_data = pdf_data
        self.xml_path = Path(xml_path) if xml_path else None
        self.schedule = schedule
        self.xml_field = xml_field
        self.tolerance = tolerance
        self.skip_pools = skip_pools if skip_pools is not None else SKIP_POOLS
        self._xml_data: Optional[dict] = None
        self._pdf_index: Optional[dict] = None
        self._entity_names: dict[str, str] = {}

    def reconcile(self) -> PDFValidationReport:
        """Run full reconciliation: compare every PDF value against XML.

        Returns PDFValidationReport with all comparisons classified.
        """
        if self.xml_path is None:
            raise ValueError("xml_path is required for reconcile() — use reconcile_against_values() for pre-parsed data")

        xml_data = self._parse_xml()
        return self._run_reconciliation(xml_data)

    def reconcile_against_values(self, xml_values: dict) -> PDFValidationReport:
        """Reconcile PDF data against pre-parsed XML values.

        Args:
            xml_values: {(ref_id, basket, pool_name): value} from external parsing

        Useful when XML is already parsed by ReportEngine or another module.
        """
        return self._run_reconciliation(xml_values)

    def _run_reconciliation(self, xml_data: dict) -> PDFValidationReport:
        """Core reconciliation logic — shared between reconcile() and reconcile_against_values()."""
        pdf_index = self._build_pdf_index()
        report = PDFValidationReport(
            schedule=self.schedule,
            pdf_source=str(self.pdf_data.attrs.get("source", "PDF")),
            xml_source=self.xml_path.name if self.xml_path else "pre-parsed",
        )

        pdf_keys = set(pdf_index.keys())
        xml_keys = set(xml_data.keys())

        # Filter out skip_pools from both sides (only applies to Sch J)
        if self.schedule == "J":
            pdf_keys = {k for k in pdf_keys if k[2] not in self.skip_pools}
            xml_keys = {k for k in xml_keys if k[2] not in self.skip_pools}

        all_keys = pdf_keys | xml_keys

        for ref_id, basket, pool_name in sorted(all_keys):
            col, desc = self._get_field_display(pool_name)
            entity_name = self._get_entity_name(ref_id)

            pdf_val = pdf_index.get((ref_id, basket, pool_name))
            xml_val = xml_data.get((ref_id, basket, pool_name), 0.0)

            delta = (pdf_val or 0.0) - (xml_val or 0.0)
            status, severity = self._classify(pdf_val, xml_val, delta)

            report.items.append(PDFDiscrepancy(
                entity_name=entity_name,
                reference_id=ref_id,
                basket=basket,
                schedule=self.schedule,
                field=f"{col} {pool_name}" if col != "?" else pool_name,
                field_description=desc,
                pdf_value=pdf_val or 0.0,
                xml_value=xml_val or 0.0,
                delta=delta,
                status=status,
                severity=severity,
            ))

        return report

    def _get_field_display(self, pool_name: str) -> tuple[str, str]:
        """Get column letter and description for a field.

        Routes to schedule-specific lookup.
        """
        if self.schedule == "A":
            from lab.pdf_validator.layouts.page1_schedule_a import FIELD_LOOKUP as P1A_LOOKUP, get_field_description
            if "|" in pool_name:
                return ("SchA", get_field_description(pool_name))
            info = P1A_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "B":
            from lab.pdf_validator.layouts.schedule_b import get_field_description as schb_desc
            if "|" in pool_name:
                parts = pool_name.split("|")
                label = "Pt2" if len(parts) == 3 else "Pt1"
                return (label, schb_desc(pool_name))
            return ("?", pool_name)
        if self.schedule == "F":
            from lab.pdf_validator.layouts.schedule_f import FIELD_LOOKUP as SCHF_LOOKUP
            info = SCHF_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "G":
            from lab.pdf_validator.layouts.schedule_g import FIELD_LOOKUP as SCHG_LOOKUP
            info = SCHG_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "H":
            from lab.pdf_validator.layouts.schedule_h import FIELD_LOOKUP as SCHH_LOOKUP
            info = SCHH_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "I1":
            from lab.pdf_validator.layouts.schedule_i1 import FIELD_LOOKUP as SCHI1_LOOKUP
            info = SCHI1_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "C":
            from lab.pdf_validator.layouts.schedule_c import FIELD_LOOKUP as SCHC_LOOKUP
            info = SCHC_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "E":
            from lab.pdf_validator.layouts.schedule_e import get_field_description as sche_desc
            if "|" in pool_name:
                return ("SchE", sche_desc(pool_name))
            return ("SchE", sche_desc(pool_name))
        if self.schedule == "I":
            from lab.pdf_validator.layouts.schedule_i import FIELD_LOOKUP as SCHI_LOOKUP
            info = SCHI_LOOKUP.get(pool_name)
            if info:
                return (f"L{info[0]}", info[1])
            return ("?", pool_name)
        if self.schedule == "P":
            from lab.pdf_validator.layouts.schedule_p import get_field_description as schp_desc
            if "|" in pool_name:
                return ("SchP", schp_desc(pool_name))
            return ("SchP", schp_desc(pool_name))
        if self.schedule == "R":
            from lab.pdf_validator.layouts.schedule_r import get_field_description as schr_desc
            if "|" in pool_name:
                return ("SchR", schr_desc(pool_name))
            return ("SchR", schr_desc(pool_name))
        return POOL_LOOKUP.get(pool_name, ("?", pool_name))

    def _classify(self, pdf_val: Optional[float], xml_val: Optional[float],
                  delta: float) -> tuple[str, str]:
        """Classify a comparison into status and severity."""
        pdf_v = pdf_val or 0.0
        xml_v = xml_val or 0.0

        if abs(delta) < self.tolerance:
            return ("OK", "NONE")

        if abs(pdf_v) >= self.tolerance and abs(xml_v) < 1.0:
            return ("PHANTOM", "HIGH")

        if abs(xml_v) >= self.tolerance and abs(pdf_v) < 1.0:
            return ("MISSING", "HIGH")

        return ("MISMATCH", "MEDIUM")

    def _build_pdf_index(self) -> dict[tuple[str, str, str], float]:
        """Build indexed lookup: {(ref_id, basket, pool_name): value}.

        For Schedule J: Uses pool_name column, filters to target xml_field.
        For Schedule F: Each row is already a distinct field (pool_name = xml_field_name).
        """
        if self._pdf_index is not None:
            return self._pdf_index

        index: dict[tuple[str, str, str], float] = {}
        if self.pdf_data.empty:
            self._pdf_index = index
            return index

        if self.schedule == "F":
            # Schedule F: no field filtering — each row is a distinct balance sheet field
            source = self.pdf_data
        else:
            # Schedule J: filter to target xml_field (e.g. BeginningYearBalanceAmt)
            mask = self.pdf_data["field_name"] == self.xml_field
            source = self.pdf_data[mask] if mask.any() else self.pdf_data

        for _, row in source.iterrows():
            ref_id = row.get("reference_id", "")
            basket = row.get("basket", "GEN")
            pool_name = row.get("pool_name", "")
            value = row.get("value")

            if not ref_id or not pool_name:
                continue

            key = (ref_id, basket, pool_name)
            if key not in index and value is not None:
                index[key] = float(value)

            entity_name = row.get("entity_name", "")
            if entity_name and ref_id not in self._entity_names:
                self._entity_names[ref_id] = entity_name

        self._pdf_index = index
        return index

    def _parse_xml(self) -> dict:
        """Parse XML into {(ref_id, basket, field_name): value}.

        Routes to schedule-specific parser.
        """
        if self._xml_data is not None:
            return self._xml_data

        if self.schedule == "A":
            self._xml_data = self._parse_xml_page1a()
        elif self.schedule == "B":
            self._xml_data = self._parse_xml_schb()
        elif self.schedule == "C":
            self._xml_data = self._parse_xml_schc()
        elif self.schedule == "E":
            self._xml_data = self._parse_xml_sche()
        elif self.schedule == "F":
            self._xml_data = self._parse_xml_schf()
        elif self.schedule == "G":
            self._xml_data = self._parse_xml_schg()
        elif self.schedule == "H":
            self._xml_data = self._parse_xml_schh()
        elif self.schedule == "I":
            self._xml_data = self._parse_xml_schi()
        elif self.schedule == "I1":
            self._xml_data = self._parse_xml_schi1()
        elif self.schedule == "P":
            self._xml_data = self._parse_xml_schp()
        elif self.schedule == "R":
            self._xml_data = self._parse_xml_schr()
        else:
            self._xml_data = self._parse_xml_schj()

        return self._xml_data

    def _parse_xml_schj(self) -> dict:
        """Parse Schedule J from XML into {(ref_id, basket, pool): value}."""
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schj in root.iter(f"{{{NS}}}IRS5471ScheduleJ"):
            ref_el = schj.find(f".//{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
            if ref_el is None or not ref_el.text:
                continue
            ref_id = ref_el.text.strip()

            name_el = schj.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            sep_el = schj.find(f"{{{NS}}}SeparateCategoryCd")
            basket = sep_el.text.strip() if sep_el is not None else "GEN"
            if basket == "TOTAL":
                continue

            for pool_name, _, _ in ALL_POOLS:
                pool_el = schj.find(f"{{{NS}}}{pool_name}")
                if pool_el is not None:
                    field_el = pool_el.find(f"{{{NS}}}{self.xml_field}")
                    if field_el is not None and field_el.text:
                        try:
                            data[(ref_id, basket, pool_name)] = float(field_el.text)
                        except ValueError:
                            continue

        return data

    def _parse_xml_page1a(self) -> dict:
        """Parse Page 1 + Schedule A from XML.

        Returns {(ref_id, "N/A", field_key): value}.
        Page 1: VotingStockOwnedPct as decimal (e.g. 0.608)
        Schedule A: "{CLASS_DESC}|AnnualAcctPeriodBeginShareCnt" -> count
        """
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for irs5471 in root.iter(f"{{{NS}}}IRS5471"):
            ref_el = irs5471.find(f".//{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
            if ref_el is None or not ref_el.text:
                continue
            ref_id = ref_el.text.strip()

            # Cache entity name
            name_el = irs5471.find(f".//{{{NS}}}ForeignCorporation/{{{NS}}}BusinessName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            # Page 1: Voting stock %
            voting_el = irs5471.find(f"{{{NS}}}VotingStockOwnedPct")
            if voting_el is not None and voting_el.text:
                try:
                    data[(ref_id, "N/A", "VotingStockOwnedPct")] = float(voting_el.text)
                except ValueError:
                    pass

            # Schedule A: Stock classes
            scha = irs5471.find(f"{{{NS}}}IRS5471ScheduleA")
            if scha is None:
                continue

            for stock_grp in scha.findall(f"{{{NS}}}StockOfTheForeignCorporation"):
                class_el = stock_grp.find(f"{{{NS}}}StockClassDesc")
                class_desc = (class_el.text.strip().upper() if class_el is not None and class_el.text else "UNKNOWN")

                beg_el = stock_grp.find(f"{{{NS}}}AnnualAcctPeriodBeginShareCnt")
                if beg_el is not None and beg_el.text:
                    try:
                        data[(ref_id, "N/A", f"{class_desc}|AnnualAcctPeriodBeginShareCnt")] = float(beg_el.text)
                    except ValueError:
                        pass

                end_el = stock_grp.find(f"{{{NS}}}AnnualAcctPeriodEndShareCnt")
                if end_el is not None and end_el.text:
                    try:
                        data[(ref_id, "N/A", f"{class_desc}|AnnualAcctPeriodEndShareCnt")] = float(end_el.text)
                    except ValueError:
                        pass

        return data

    def _parse_xml_schb(self) -> dict:
        """Parse Schedule B (Shareholders) from XML.

        Returns {(ref_id, "N/A", compound_key): value}.
        Part I: "{SHAREHOLDER_NAME}|ShareholderEIN" -> EIN as float
        Part II: "{SHAREHOLDER_NAME}|{STOCK_CLASS}|{field}" -> share count
        """
        from lab.pdf_validator.layouts.schedule_b import normalize_shareholder_name

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for irs5471 in root.iter(f"{{{NS}}}IRS5471"):
            ref_el = irs5471.find(f".//{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
            if ref_el is None or not ref_el.text:
                continue
            ref_id = ref_el.text.strip()

            # Cache entity name
            name_el = irs5471.find(f".//{{{NS}}}ForeignCorporation/{{{NS}}}BusinessName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            schb = irs5471.find(f"{{{NS}}}IRS5471ScheduleB")
            if schb is None:
                continue

            # Part I: US Shareholders
            for us_sh in schb.findall(f"{{{NS}}}USShareholdersOfForeignCorp"):
                sh_name_el = us_sh.find(f"{{{NS}}}BusinessName/{{{NS}}}BusinessNameLine1Txt")
                if sh_name_el is None or not sh_name_el.text:
                    continue
                sh_name = normalize_shareholder_name(sh_name_el.text)
                if sh_name in ("NONE", "N/A", ""):
                    continue

                ein_el = us_sh.find(f"{{{NS}}}ShareholderEIN")
                if ein_el is not None and ein_el.text:
                    ein_digits = ein_el.text.strip().replace("-", "")
                    try:
                        data[(ref_id, "N/A", f"{sh_name}|ShareholderEIN")] = float(ein_digits)
                    except ValueError:
                        pass

            # Part II: Direct Shareholders
            for direct_sh in schb.findall(f"{{{NS}}}DirectShareholdersForeignCorp"):
                sh_name_el = direct_sh.find(f"{{{NS}}}BusinessName/{{{NS}}}BusinessNameLine1Txt")
                if sh_name_el is None or not sh_name_el.text:
                    continue
                sh_name = normalize_shareholder_name(sh_name_el.text)
                if sh_name in ("NONE", "N/A", ""):
                    continue

                # EIN (may be on direct shareholders too)
                ein_el = direct_sh.find(f"{{{NS}}}ShareholderEIN")
                if ein_el is not None and ein_el.text:
                    ein_digits = ein_el.text.strip().replace("-", "")
                    try:
                        data[(ref_id, "N/A", f"{sh_name}|ShareholderEIN")] = float(ein_digits)
                    except ValueError:
                        pass

                # Stock data
                for stock_grp in direct_sh.findall(f"{{{NS}}}ForeignCorporationStocks"):
                    class_el = stock_grp.find(f"{{{NS}}}StockClassDesc")
                    stock_class = (class_el.text.strip().upper()
                                   if class_el is not None and class_el.text else "STOCK")

                    beg_el = stock_grp.find(f"{{{NS}}}AnnualAcctPeriodBeginShareCnt")
                    if beg_el is not None and beg_el.text:
                        try:
                            data[(ref_id, "N/A", f"{sh_name}|{stock_class}|AnnualAcctPeriodBeginShareCnt")] = float(beg_el.text)
                        except ValueError:
                            pass

                    end_el = stock_grp.find(f"{{{NS}}}AnnualAcctPeriodEndShareCnt")
                    if end_el is not None and end_el.text:
                        try:
                            data[(ref_id, "N/A", f"{sh_name}|{stock_class}|AnnualAcctPeriodEndShareCnt")] = float(end_el.text)
                        except ValueError:
                            pass

        return data

    def _parse_xml_schf(self) -> dict:
        """Parse Schedule F (Balance Sheet) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value} for all BOY and EOY fields.
        """
        from lab.pdf_validator.layouts.schedule_f import ALL_BOY_FIELDS, ALL_EOY_FIELDS

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        all_fields = [(f, ln, d) for f, ln, d in ALL_BOY_FIELDS] + \
                     [(f, ln, d) for f, ln, d in ALL_EOY_FIELDS]

        for schf in root.iter(f"{{{NS}}}IRS5471ScheduleF"):
            # Get ref_id — may be on the parent IRS5471 element or within SchF
            ref_id = self._find_ref_id_for_schedule(schf, root)
            if not ref_id:
                continue

            # Cache entity name
            name_el = schf.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in all_fields:
                field_el = schf.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    try:
                        data[(ref_id, "N/A", field_name)] = float(field_el.text)
                    except ValueError:
                        continue

        return data

    def _parse_xml_schg(self) -> dict:
        """Parse Schedule G (Other Information) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value}.
        Indicators: 1.0 for present/true, 0.0 for absent.
        Amounts: numeric value.
        """
        from lab.pdf_validator.layouts.schedule_g import ALL_FIELDS, FIELD_TYPE

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schg in root.iter(f"{{{NS}}}IRS5471ScheduleG"):
            ref_id = self._find_ref_id_for_schedule(schg, root)
            if not ref_id:
                continue

            name_el = schg.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in ALL_FIELDS:
                field_el = schg.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    ftype = FIELD_TYPE.get(field_name, "indicator")
                    if ftype == "amount":
                        try:
                            data[(ref_id, "N/A", field_name)] = float(field_el.text)
                        except ValueError:
                            continue
                    else:
                        # Indicator: "X", "1", "true" → 1.0
                        val = field_el.text.strip().lower()
                        data[(ref_id, "N/A", field_name)] = 1.0 if val in ("x", "1", "true", "yes") else 0.0

        return data

    def _parse_xml_schh(self) -> dict:
        """Parse Schedule H (Current E&P) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value}.
        """
        from lab.pdf_validator.layouts.schedule_h import ALL_FIELDS

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schh in root.iter(f"{{{NS}}}IRS5471ScheduleH"):
            ref_id = self._find_ref_id_for_schedule(schh, root)
            if not ref_id:
                continue

            name_el = schh.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in ALL_FIELDS:
                field_el = schh.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    try:
                        data[(ref_id, "N/A", field_name)] = float(field_el.text)
                    except ValueError:
                        continue

        return data

    def _parse_xml_schi1(self) -> dict:
        """Parse Schedule I-1 (GILTI) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value}.
        """
        from lab.pdf_validator.layouts.schedule_i1 import ALL_FIELDS

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schi1 in root.iter(f"{{{NS}}}IRS5471ScheduleI1"):
            ref_id = self._find_ref_id_for_schedule(schi1, root)
            if not ref_id:
                continue

            name_el = schi1.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in ALL_FIELDS:
                field_el = schi1.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    try:
                        data[(ref_id, "N/A", field_name)] = float(field_el.text)
                    except ValueError:
                        continue

        return data

    def _parse_xml_schc(self) -> dict:
        """Parse Schedule C (Income Statement) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value}.
        """
        from lab.pdf_validator.layouts.schedule_c import ALL_FIELDS

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schc in root.iter(f"{{{NS}}}IRS5471ScheduleC"):
            ref_id = self._find_ref_id_for_schedule(schc, root)
            if not ref_id:
                continue

            name_el = schc.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in ALL_FIELDS:
                field_el = schc.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    try:
                        data[(ref_id, "N/A", field_name)] = float(field_el.text)
                    except ValueError:
                        continue

        return data

    def _parse_xml_sche(self) -> dict:
        """Parse Schedule E (Foreign Taxes) from XML.

        Returns {(ref_id, basket, compound_key): value}.
        Compound keys: "group|field" for per-group amounts.
        """
        from lab.pdf_validator.layouts.schedule_e import (
            INCOME_GROUPS, SCHE_GROUP_FIELDS, SCHE_SUMMARY_FIELDS,
        )

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for sche in root.iter(f"{{{NS}}}IRS5471ScheduleE"):
            ref_id = self._find_ref_id_for_schedule(sche, root)
            if not ref_id:
                continue

            name_el = sche.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            sep_el = sche.find(f"{{{NS}}}SeparateCategoryCd")
            basket = sep_el.text.strip() if sep_el is not None and sep_el.text else "GEN"

            # Summary fields (direct children)
            for _, _, field_name, _ in SCHE_SUMMARY_FIELDS:
                field_el = sche.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    try:
                        data[(ref_id, basket, field_name)] = float(field_el.text)
                    except ValueError:
                        continue

            # Per-group fields
            for grp_xml in INCOME_GROUPS:
                grp_el = sche.find(f"{{{NS}}}{grp_xml}")
                if grp_el is None:
                    continue
                for field_xml, _, _ in SCHE_GROUP_FIELDS:
                    field_el = grp_el.find(f"{{{NS}}}{field_xml}")
                    if field_el is not None and field_el.text:
                        try:
                            data[(ref_id, basket, f"{grp_xml}|{field_xml}")] = float(field_el.text)
                        except ValueError:
                            continue

        return data

    def _parse_xml_schi(self) -> dict:
        """Parse Schedule I (Summary of Shareholder's Income) from XML.

        Returns {(ref_id, "N/A", xml_field_name): value}.
        Indicators stored as 1.0/0.0.
        """
        from lab.pdf_validator.layouts.schedule_i import ALL_FIELDS, FIELD_TYPE

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schi in root.iter(f"{{{NS}}}IRS5471ScheduleI"):
            ref_id = self._find_ref_id_for_schedule(schi, root)
            if not ref_id:
                continue

            name_el = schi.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for field_name, _, _ in ALL_FIELDS:
                field_el = schi.find(f"{{{NS}}}{field_name}")
                if field_el is not None and field_el.text:
                    ftype = FIELD_TYPE.get(field_name, "amount")
                    if ftype == "indicator":
                        val = field_el.text.strip().lower()
                        data[(ref_id, "N/A", field_name)] = 1.0 if val in ("x", "1", "true", "yes") else 0.0
                    else:
                        try:
                            data[(ref_id, "N/A", field_name)] = float(field_el.text)
                        except ValueError:
                            continue

        return data

    def _parse_xml_schp(self) -> dict:
        """Parse Schedule P (Previously Taxed E&P) from XML.

        Returns {(ref_id, basket, compound_key): value}.
        Compound keys: "pool_group|field" (e.g. "FCSection951APTEPGrp|BeginningYearBalanceAmt").
        """
        from lab.pdf_validator.layouts.schedule_p import ALL_POOL_GROUPS, POOL_FIELDS

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schp in root.iter(f"{{{NS}}}IRS5471ScheduleP"):
            ref_id = self._find_ref_id_for_schedule(schp, root)
            if not ref_id:
                continue

            name_el = schp.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            sep_el = schp.find(f"{{{NS}}}SeparateCategoryCd")
            basket = sep_el.text.strip() if sep_el is not None and sep_el.text else "GEN"

            for pool_xml in ALL_POOL_GROUPS:
                pool_el = schp.find(f"{{{NS}}}{pool_xml}")
                if pool_el is None:
                    continue
                for field_xml, _, _ in POOL_FIELDS:
                    field_el = pool_el.find(f"{{{NS}}}{field_xml}")
                    if field_el is not None and field_el.text:
                        try:
                            data[(ref_id, basket, f"{pool_xml}|{field_xml}")] = float(field_el.text)
                        except ValueError:
                            continue

        return data

    def _parse_xml_schr(self) -> dict:
        """Parse Schedule R (Distributions) from XML.

        Returns {(ref_id, "N/A", compound_key): value}.
        Compound keys: "row_id|field" (row_id = sequential index).
        Only amount fields are included.
        """
        from lab.pdf_validator.layouts.schedule_r import (
            make_compound_key, normalize_distribution_desc, AMOUNT_FIELDS,
        )

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        data = {}

        for schr in root.iter(f"{{{NS}}}IRS5471ScheduleR"):
            ref_id = self._find_ref_id_for_schedule(schr, root)
            if not ref_id:
                continue

            name_el = schr.find(f".//{{{NS}}}ForeignCorporationName/{{{NS}}}BusinessNameLine1Txt")
            if name_el is not None and name_el.text:
                self._entity_names.setdefault(ref_id, name_el.text.strip())

            for row_idx, dist_grp in enumerate(schr.findall(f"{{{NS}}}DistributionsFromFrgnCorpGrp"), start=1):
                # Use RowId if available, otherwise sequential index
                row_id_el = dist_grp.find(f"{{{NS}}}RowId")
                desc_el = dist_grp.find(f"{{{NS}}}DistributionDesc")

                if row_id_el is not None and row_id_el.text:
                    row_id = row_id_el.text.strip()
                elif desc_el is not None and desc_el.text:
                    row_id = normalize_distribution_desc(desc_el.text)
                else:
                    row_id = str(row_idx)

                for field_name in AMOUNT_FIELDS:
                    field_el = dist_grp.find(f"{{{NS}}}{field_name}")
                    if field_el is not None and field_el.text:
                        try:
                            key = make_compound_key(row_id, field_name)
                            data[(ref_id, "N/A", key)] = float(field_el.text)
                        except ValueError:
                            continue

        return data

    def _find_ref_id_for_schedule(self, schedule_el, root) -> Optional[str]:
        """Find the reference ID for a schedule element.

        Tries: within the element, then its parent IRS5471, then by document ID.
        """
        # Try within the schedule element itself
        ref_el = schedule_el.find(f".//{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
        if ref_el is not None and ref_el.text:
            return ref_el.text.strip()

        # Try by matching documentId to parent IRS5471
        doc_id = schedule_el.get("documentId", "")
        if doc_id:
            # Pattern: "SchF-E001" -> look for IRS5471 with same entity
            entity_code = doc_id.split("-")[-1] if "-" in doc_id else ""
            if entity_code:
                for irs5471 in root.iter(f"{{{NS}}}IRS5471"):
                    ref_el = irs5471.find(f".//{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
                    if ref_el is not None and ref_el.text:
                        if entity_code in ref_el.text:
                            return ref_el.text.strip()

        # Try: Schedule F is a direct child of an element that has a ref_id
        parent = schedule_el
        for _ in range(3):
            parent_ref = parent.find(f"{{{NS}}}ForeignEntityIdentificationGrp/{{{NS}}}ForeignEntityReferenceIdNum")
            if parent_ref is not None and parent_ref.text:
                return parent_ref.text.strip()
            # Can't walk up in ElementTree, so this is limited
            break

        return None

    def _get_entity_name(self, ref_id: str) -> str:
        """Get entity name from cached names, falling back to ref_id."""
        return self._entity_names.get(ref_id, ref_id)

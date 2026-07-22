"""Review Engine — XML-First Automated Compliance Review.

Performs multi-dimensional quality checks against IRS e-file XML returns
without requiring workbook access. Surfaces anomalies, inconsistencies,
and review points ranked by severity.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from lab.xml_parser.parser import EFileParser


@dataclass
class Finding:
    check_id: str
    severity: str
    category: str
    entity_code: str
    entity_name: str
    description: str
    expected: str | None = None
    actual: str | None = None
    delta: float | None = None
    context: str | None = None


@dataclass
class ReviewReport:
    client_name: str = ""
    tax_year: str = ""
    entity_count: int = 0
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    run_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def high_severity(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "HIGH"]

    def by_entity(self, code: str) -> list[Finding]:
        return [f for f in self.findings if f.entity_code == code]

    def by_category(self, cat: str) -> list[Finding]:
        return [f for f in self.findings if f.category == cat]

    def to_dataframe(self) -> pd.DataFrame:
        if not self.findings:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "check_id": f.check_id,
                "severity": f.severity,
                "category": f.category,
                "entity_code": f.entity_code,
                "entity_name": f.entity_name,
                "description": f.description,
                "expected": f.expected,
                "actual": f.actual,
                "delta": f.delta,
                "context": f.context,
            }
            for f in self.findings
        ])

    def compute_summary(self):
        self.summary = {
            "total_findings": len(self.findings),
            "by_severity": {
                "HIGH": sum(1 for f in self.findings if f.severity == "HIGH"),
                "MEDIUM": sum(1 for f in self.findings if f.severity == "MEDIUM"),
                "LOW": sum(1 for f in self.findings if f.severity == "LOW"),
            },
            "by_category": {},
            "entities_with_findings": len(set(f.entity_code for f in self.findings)),
            "clean_entities": self.entity_count - len(set(f.entity_code for f in self.findings)),
        }
        for f in self.findings:
            cat = f.category
            if cat not in self.summary["by_category"]:
                self.summary["by_category"][cat] = 0
            self.summary["by_category"][cat] += 1


# Known FX rates (approximate annual averages) for reasonableness checks
EXPECTED_FX_RANGES = {
    "GBP": (0.70, 0.90),
    "EUR": (0.85, 1.10),
    "AUD": (1.30, 1.80),
    "CAD": (1.25, 1.50),
    "JPY": (100, 160),
    "CHF": (0.80, 1.05),
    "CNY": (6.5, 7.8),
    "BRL": (4.5, 6.5),
    "INR": (75, 95),
    "KRW": (1100, 1450),
    "THB": (30, 40),
    "SEK": (9.5, 11.5),
    "TWD": (28, 35),
    "ARS": (100, 2000),
    "VND": (22000, 27000),
}


class ReviewEngine:
    """Automated compliance review engine for IRS e-file XML returns."""

    def __init__(self):
        self._findings: list[Finding] = []

    def review(
        self,
        current_xml: str | Path,
        prior_xml: str | Path | None = None,
    ) -> ReviewReport:
        """Run full review on one or two XML returns.

        Args:
            current_xml: Path to current year XML
            prior_xml: Optional path to prior year XML (enables rollover checks)
        """
        self._findings = []

        parser_cy = EFileParser(Path(current_xml))
        df_cy = parser_cy.to_dataframe()

        report = ReviewReport()
        report.client_name = self._get_client_name(df_cy)
        report.tax_year = self._get_tax_year(df_cy)
        report.entity_count = len(df_cy["_reference_id"].unique()) - (1 if "" in df_cy["_reference_id"].values else 0)

        # Single-year checks
        self._check_flow(parser_cy, df_cy)
        self._check_completeness(parser_cy, df_cy)
        self._check_reasonableness(parser_cy, df_cy)

        # Rollover checks (if prior year available)
        if prior_xml:
            parser_py = EFileParser(Path(prior_xml))
            df_py = parser_py.to_dataframe()
            self._check_rollover(parser_cy, df_cy, parser_py, df_py)

        report.findings = sorted(
            self._findings,
            key=lambda f: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[f.severity], f.check_id),
        )
        report.compute_summary()
        return report

    def _get_client_name(self, df: pd.DataFrame) -> str:
        name_cols = [c for c in df.columns if "BusinessNameLine1" in c and "Foreign" not in c]
        if name_cols:
            vals = df[name_cols[0]].dropna().unique()
            if len(vals) > 0:
                return str(vals[0])
        return "Unknown"

    def _get_tax_year(self, df: pd.DataFrame) -> str:
        if "_tax_year" in df.columns:
            vals = df["_tax_year"].dropna().unique()
            if len(vals) > 0:
                return str(vals[0])
        return ""

    def _get_entity_name(self, df: pd.DataFrame, code: str) -> str:
        if "_entity_name" in df.columns:
            match = df[df["_reference_id"] == code]["_entity_name"]
            if not match.empty:
                return str(match.iloc[0])
        return code

    def _add(self, **kwargs):
        self._findings.append(Finding(**kwargs))

    # ─── FLOW CHECKS ────────────────────────────────────────────────────────

    def _check_flow(self, parser: EFileParser, df: pd.DataFrame):
        """Internal consistency checks within a single year."""
        sch_h = parser.extract_form("IRS5471ScheduleH")
        sch_i1 = parser.extract_form("IRS5471ScheduleI1")
        sch_e = parser.extract_form("IRS5471ScheduleE")
        sch_c = parser.extract_form("IRS5471ScheduleC")
        sch_f = parser.extract_form("IRS5471ScheduleF")

        if sch_h.empty:
            return

        sch_h = sch_h.set_index("_reference_id")
        if not sch_i1.empty:
            sch_i1 = sch_i1.set_index("_reference_id")
        if not sch_e.empty:
            sch_e = sch_e.set_index("_reference_id")
        if not sch_c.empty:
            sch_c = sch_c.set_index("_reference_id")
        if not sch_f.empty:
            sch_f = sch_f.set_index("_reference_id")

        for code in sch_h.index:
            if code == "":
                continue
            name = self._get_entity_name(df, code)
            self._check_flow_entity(code, name, sch_h, sch_i1, sch_e, sch_c, sch_f)

    def _check_flow_entity(self, code, name, sch_h, sch_i1, sch_e, sch_c, sch_f):
        """Flow checks for a single entity."""
        h = sch_h.loc[code] if code in sch_h.index else None
        if h is None:
            return

        # FLO-001: Sch H net income should flow from Sch C line 21
        net_income_h = self._safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
        if not sch_c.empty and code in sch_c.index:
            c = sch_c.loc[code]
            net_income_c = self._safe_float(c, "IRS5471ScheduleC_ForeignCYNetIncomePerBookAmt")
            if net_income_h is not None and net_income_c is not None:
                delta = abs(net_income_h - net_income_c)
                if delta > max(1, abs(net_income_h) * 0.001):
                    self._add(
                        check_id="FLO-001", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch H net income != Sch C line 21 (delta {delta:,.0f} FC)",
                        expected=f"Sch C: {net_income_c:,.0f}",
                        actual=f"Sch H: {net_income_h:,.0f}",
                        delta=delta,
                        context="Sch H line 1 should equal Sch C line 21 (net income per books)",
                    )

        # FLO-002: E&P FC x FX = USD (within tolerance)
        ep_fc = self._safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")
        ep_usd = self._safe_float(h, "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt")
        fx_rate = self._safe_float(h, "IRS5471ScheduleH_ExchangeRt")

        if ep_fc is not None and fx_rate is not None and fx_rate > 0 and ep_usd is not None:
            expected_usd = ep_fc / fx_rate
            delta = abs(expected_usd - ep_usd)
            if delta > max(10, abs(ep_usd) * 0.01):
                self._add(
                    check_id="FLO-002", severity="MEDIUM", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"E&P FC/FX rate != USD amount (delta ${delta:,.0f})",
                    expected=f"${expected_usd:,.0f} (FC {ep_fc:,.0f} / {fx_rate:.4f})",
                    actual=f"${ep_usd:,.0f}",
                    delta=delta,
                )

        # FLO-004: Sch E taxes should be <= pre-tax income x max statutory rate
        if not sch_e.empty and code in sch_e.index:
            e = sch_e.loc[code]
            total_tax = self._safe_float(e, "IRS5471ScheduleE_TotalTaxInFunctionalCurAmt")
            if total_tax is not None and net_income_h is not None and net_income_h > 0:
                max_reasonable_tax = net_income_h * 0.45
                if total_tax > max_reasonable_tax and total_tax > 10000:
                    self._add(
                        check_id="FLO-004", severity="MEDIUM", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch E taxes ({total_tax:,.0f} FC) exceed 45% of pre-tax income ({net_income_h:,.0f} FC)",
                        expected=f"Tax <= {max_reasonable_tax:,.0f} FC (45% cap)",
                        actual=f"Tax = {total_tax:,.0f} FC ({total_tax/net_income_h:.0%})",
                        delta=total_tax - max_reasonable_tax,
                        context="Taxes exceeding maximum statutory rate suggest data error or prior-year adjustments included",
                    )

        # FLO-005: Tested loss entities should not have tested foreign taxes
        if not sch_i1.empty and code in sch_i1.index:
            i1 = sch_i1.loc[code]
            tested_usd_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt"
            tested_fc_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_FunctionalCurrencyAmt"
            tax_col = "IRS5471ScheduleI1_TestedForeignIncomeTaxesGrp_USDollarAmt"

            tested = self._safe_float(i1, tested_usd_col) or self._safe_float(i1, tested_fc_col)
            taxes = self._safe_float(i1, tax_col)

            if tested is not None and tested < 0 and taxes is not None and taxes > 0:
                self._add(
                    check_id="FLO-005", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description="Tested loss entity has positive tested foreign taxes",
                    expected="No taxes for tested loss entity",
                    actual=f"Tested income: ${tested:,.0f}, Taxes: ${taxes:,.0f}",
                    context="Tested foreign taxes should only be claimed by tested income entities",
                )

            # FLO-003: tested income + HTE + SubF ~= gross income
            gross_col = "IRS5471ScheduleI1_GrossIncomeAmt"
            hte_col = "IRS5471ScheduleI1_HighTaxExceptionIncomeAmt"
            subf_col = "IRS5471ScheduleI1_SubpartFIncomeAmt"

            gross = self._safe_float(i1, gross_col)
            hte = self._safe_float(i1, hte_col) or 0
            subf = self._safe_float(i1, subf_col) or 0
            tested_val = tested or 0

            if gross is not None and gross != 0:
                allocable_col = "IRS5471ScheduleI1_AllocableDeductionAmt"
                allocable = self._safe_float(i1, allocable_col) or 0
                reconstructed = tested_val + hte + subf + allocable
                flow_delta = abs(gross - reconstructed)
                if flow_delta > max(1000, abs(gross) * 0.05):
                    self._add(
                        check_id="FLO-003", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch I-1 income components don't reconcile to gross (delta ${flow_delta:,.0f})",
                        expected=f"Gross ${gross:,.0f} ~= Tested {tested_val:,.0f} + HTE {hte:,.0f} + SubF {subf:,.0f} + Deductions {allocable:,.0f}",
                        actual=f"Sum = ${reconstructed:,.0f}",
                        delta=flow_delta,
                    )

        # FLO-006: Sch C total income should flow correctly (deductions check)
        if not sch_c.empty and code in sch_c.index:
            c = sch_c.loc[code]
            total_income = self._safe_float(c, "IRS5471ScheduleC_ForeignTotalIncomeAmt")
            total_deductions = self._safe_float(c, "IRS5471ScheduleC_ForeignTotalDeductionsAmt")
            net_income_c = self._safe_float(c, "IRS5471ScheduleC_ForeignCYNetIncomePerBookAmt")
            if total_income is not None and total_deductions is not None and net_income_c is not None:
                expected_net = total_income - total_deductions
                d = abs(expected_net - net_income_c)
                if d > 1:
                    self._add(
                        check_id="FLO-006", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch C: income ({total_income:,.0f}) - deductions ({total_deductions:,.0f}) != net ({net_income_c:,.0f})",
                        expected=f"Net = {expected_net:,.0f}",
                        actual=f"Net = {net_income_c:,.0f}",
                        delta=d,
                        context="Sch C line 12 - line 20 should equal line 21",
                    )

        # FLO-007: Sch F total assets must be >= 0
        if not sch_f.empty and code in sch_f.index:
            f = sch_f.loc[code]
            eoy_assets = self._safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
            boy_assets = self._safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt")

            if eoy_assets is not None and eoy_assets < 0:
                self._add(
                    check_id="FLO-007", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F EOY total assets is negative ({eoy_assets:,.0f})",
                    expected="Total assets >= 0",
                    actual=f"{eoy_assets:,.0f}",
                    context="Negative total assets on balance sheet is impossible — likely data entry error",
                )

            if boy_assets is not None and boy_assets < 0:
                self._add(
                    check_id="FLO-007", severity="HIGH", category="flow",
                    entity_code=code, entity_name=name,
                    description=f"Sch F BOY total assets is negative ({boy_assets:,.0f})",
                    expected="Total assets >= 0",
                    actual=f"{boy_assets:,.0f}",
                    context="Negative total assets on balance sheet is impossible — likely data entry error",
                )

            # FLO-008: Sch F assets = liabilities + equity (BS must balance)
            eoy_liab_eq = self._safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotLiabShrEqtyAmt")
            if eoy_assets is not None and eoy_liab_eq is not None:
                bs_delta = abs(eoy_assets - eoy_liab_eq)
                if bs_delta > 1:
                    self._add(
                        check_id="FLO-008", severity="HIGH", category="flow",
                        entity_code=code, entity_name=name,
                        description=f"Sch F balance sheet does not balance (delta {bs_delta:,.0f})",
                        expected=f"Assets ({eoy_assets:,.0f}) = L+E ({eoy_liab_eq:,.0f})",
                        actual=f"Difference: {bs_delta:,.0f}",
                        delta=bs_delta,
                        context="Total assets must equal total liabilities + shareholders equity",
                    )

    # ─── COMPLETENESS CHECKS ────────────────────────────────────────────────

    def _check_completeness(self, parser: EFileParser, df: pd.DataFrame):
        """Check that required schedules are present for each entity."""
        sch_h = parser.extract_form("IRS5471ScheduleH")
        sch_i1 = parser.extract_form("IRS5471ScheduleI1")
        sch_e = parser.extract_form("IRS5471ScheduleE")
        sch_f = parser.extract_form("IRS5471ScheduleF")

        entities_in_return = set(df["_reference_id"].unique()) - {""}
        h_entities = set(sch_h["_reference_id"].unique()) - {""} if not sch_h.empty else set()
        i1_entities = set(sch_i1["_reference_id"].unique()) - {""} if not sch_i1.empty else set()
        e_entities = set(sch_e["_reference_id"].unique()) - {""} if not sch_e.empty else set()
        f_entities = set(sch_f["_reference_id"].unique()) - {""} if not sch_f.empty else set()

        if not sch_h.empty:
            sch_h_idx = sch_h.set_index("_reference_id")
        if not sch_i1.empty:
            sch_i1_idx = sch_i1.set_index("_reference_id")
        if not sch_f.empty:
            sch_f_idx = sch_f.set_index("_reference_id")

        for code in entities_in_return:
            name = self._get_entity_name(df, code)

            # CMP-001: Entity in return but no Sch H
            if code not in h_entities:
                self._add(
                    check_id="CMP-001", severity="HIGH", category="completeness",
                    entity_code=code, entity_name=name,
                    description="Entity in return but missing Schedule H (E&P computation)",
                    context="Every 5471 entity should have current year E&P computed",
                )

            # CMP-002: Has Sch H but no Sch I-1
            if code in h_entities and code not in i1_entities:
                self._add(
                    check_id="CMP-002", severity="MEDIUM", category="completeness",
                    entity_code=code, entity_name=name,
                    description="Entity has Sch H but no Sch I-1 (GILTI classification missing)",
                    context="GILTI requires classification of income as tested/HTE/SubF for all CFCs",
                )

            # CMP-003: Has Sch I-1 tested income but no Sch E taxes
            if code in i1_entities and code not in e_entities:
                i1 = sch_i1_idx.loc[code]
                tested = self._safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
                if tested is not None and tested > 0:
                    self._add(
                        check_id="CMP-003", severity="MEDIUM", category="completeness",
                        entity_code=code, entity_name=name,
                        description=f"Entity has tested income (${tested:,.0f}) but no Sch E (foreign taxes)",
                        context="Tested income entities typically have foreign taxes to report on Sch E",
                    )

            # CMP-004: Sch F has BOY amounts but no EOY
            if code in f_entities:
                f = sch_f_idx.loc[code]
                boy_assets = self._safe_float(f, "IRS5471ScheduleF_BegngAcctPrdTotalAssetsAmt")
                eoy_assets = self._safe_float(f, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
                if boy_assets is not None and boy_assets != 0 and (eoy_assets is None or eoy_assets == 0):
                    self._add(
                        check_id="CMP-004", severity="HIGH", category="completeness",
                        entity_code=code, entity_name=name,
                        description=f"Sch F has BOY assets ({boy_assets:,.0f}) but EOY is zero/missing",
                        expected="EOY amounts should be populated",
                        actual="EOY total assets = 0 or missing",
                        context="Incomplete balance sheet — entity likely still active if it has BOY",
                    )

            # CMP-005: No functional currency or exchange rate
            if code in h_entities:
                h_row = sch_h_idx.loc[code]
                fx = self._safe_float(h_row, "IRS5471ScheduleH_ExchangeRt")
                if fx is None or fx == 0:
                    self._add(
                        check_id="CMP-005", severity="MEDIUM", category="completeness",
                        entity_code=code, entity_name=name,
                        description="No exchange rate on Sch H (cannot convert FC to USD)",
                        context="Exchange rate is required for FC-to-USD translation of E&P",
                    )

            # CMP-006: Reference ID check
            if not code or len(code.strip()) < 3:
                self._add(
                    check_id="CMP-006", severity="HIGH", category="completeness",
                    entity_code=code, entity_name=name,
                    description="Invalid or missing reference ID",
                )

    # ─── REASONABLENESS CHECKS ──────────────────────────────────────────────

    def _check_reasonableness(self, parser: EFileParser, df: pd.DataFrame):
        """Flag unusual or anomalous values."""
        sch_h = parser.extract_form("IRS5471ScheduleH")
        sch_i1 = parser.extract_form("IRS5471ScheduleI1")
        sch_f = parser.extract_form("IRS5471ScheduleF")

        if sch_h.empty:
            return
        sch_h = sch_h.set_index("_reference_id")
        if not sch_i1.empty:
            sch_i1 = sch_i1.set_index("_reference_id")
        if not sch_f.empty:
            sch_f = sch_f.set_index("_reference_id")

        for code in sch_h.index:
            if code == "":
                continue
            name = self._get_entity_name(df, code)
            h = sch_h.loc[code]

            # RSN-001: E&P > $1B
            ep_usd = self._safe_float(h, "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt")
            if ep_usd is not None and abs(ep_usd) > 1_000_000_000:
                self._add(
                    check_id="RSN-001", severity="LOW", category="reasonableness",
                    entity_code=code, entity_name=name,
                    description=f"E&P exceeds $1B (${ep_usd:,.0f}) — verify this is correct",
                    actual=f"${ep_usd:,.0f}",
                )

            # RSN-002: FX rate outside expected range
            fx_rate = self._safe_float(h, "IRS5471ScheduleH_ExchangeRt")
            if fx_rate is not None and fx_rate > 0:
                self._check_fx_reasonableness(code, name, fx_rate)

            # RSN-003: Effective tax rate anomaly
            ep_fc = self._safe_float(h, "IRS5471ScheduleH_CurrentEarningsAndProfitsAmt")
            net_income = self._safe_float(h, "IRS5471ScheduleH_ForeignCYNetIncomePerBooksAmt")
            if ep_fc is not None and net_income is not None and net_income != 0:
                implied_tax = net_income - ep_fc
                etr = implied_tax / net_income if net_income != 0 else 0
                if etr > 0.50 or etr < -0.10:
                    self._add(
                        check_id="RSN-003", severity="MEDIUM", category="reasonableness",
                        entity_code=code, entity_name=name,
                        description=f"Implied ETR of {etr:.0%} is outside normal range (0-50%)",
                        expected="0% to 50%",
                        actual=f"{etr:.1%} (income {net_income:,.0f}, E&P {ep_fc:,.0f})",
                        context="High ETR may indicate adjustments; negative may indicate refunds or errors",
                    )

            # RSN-004: Tested income exactly equals Subpart F income (possible misclass)
            if not sch_i1.empty and code in sch_i1.index:
                i1 = sch_i1.loc[code]
                tested = self._safe_float(i1, "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt")
                subf = self._safe_float(i1, "IRS5471ScheduleI1_SubpartFIncomeAmt")
                if (tested is not None and subf is not None
                        and tested > 0 and subf > 0
                        and abs(tested - subf) < 1):
                    self._add(
                        check_id="RSN-004", severity="LOW", category="reasonableness",
                        entity_code=code, entity_name=name,
                        description=f"Tested income (${tested:,.0f}) exactly equals SubF income — possible misclassification",
                        expected="Different amounts unless coincidence",
                        actual=f"Tested = SubF = ${tested:,.0f}",
                        context="Same amount in both categories may indicate double-counting or misallocation",
                    )

            # RSN-006: QBAI > total assets (impossible)
            if not sch_i1.empty and code in sch_i1.index:
                i1 = sch_i1.loc[code]
                qbai = self._safe_float(i1, "IRS5471ScheduleI1_QBAIAmt")
                if not sch_f.empty and code in sch_f.index:
                    f_row = sch_f.loc[code]
                    total_assets = self._safe_float(f_row, "IRS5471ScheduleF_EndAcctPrdTotalAssetsAmt")
                    if qbai is not None and total_assets is not None and qbai > total_assets and qbai > 0:
                        self._add(
                            check_id="RSN-006", severity="HIGH", category="reasonableness",
                            entity_code=code, entity_name=name,
                            description=f"QBAI (${qbai:,.0f}) exceeds total assets (${total_assets:,.0f}) — impossible",
                            expected=f"QBAI <= Total assets (${total_assets:,.0f})",
                            actual=f"QBAI = ${qbai:,.0f}",
                            delta=qbai - total_assets,
                            context="QBAI is a subset of tangible assets; it cannot exceed total assets on Sch F",
                        )

            # RSN-007: Interest expense > gross income (leverage anomaly)
            if not sch_i1.empty and code in sch_i1.index:
                i1 = sch_i1.loc[code]
                gross = self._safe_float(i1, "IRS5471ScheduleI1_GrossIncomeAmt")
                interest = self._safe_float(i1, "IRS5471ScheduleI1_InterestExpenseAmt")
                if (gross is not None and interest is not None
                        and interest > 0 and gross > 0
                        and interest > gross):
                    self._add(
                        check_id="RSN-007", severity="MEDIUM", category="reasonableness",
                        entity_code=code, entity_name=name,
                        description=f"Interest expense (${interest:,.0f}) exceeds gross income (${gross:,.0f})",
                        expected="Interest < gross income for operating entities",
                        actual=f"Interest/Income = {interest/gross:.0%}",
                        context="Extremely high leverage — verify holding company or inter-company debt structure",
                    )

        # RSN-005: All entities same E&P sign
        ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
        if ep_col in sch_h.columns:
            ep_values = pd.to_numeric(sch_h[ep_col], errors="coerce").dropna()
            if len(ep_values) >= 5:
                positive = (ep_values > 0).sum()
                negative = (ep_values < 0).sum()
                if positive == 0 or negative == 0:
                    sign = "positive" if positive > 0 else "negative"
                    self._add(
                        check_id="RSN-005", severity="LOW", category="reasonableness",
                        entity_code="ALL", entity_name="(all entities)",
                        description=f"All {len(ep_values)} entities have {sign} E&P — unusual for diversified group",
                        context="Most multinational groups have a mix of profitable and loss-making entities",
                    )

    def _check_fx_reasonableness(self, code: str, name: str, fx_rate: float):
        """Check if FX rate is within expected range for known currencies."""
        for currency, (low, high) in EXPECTED_FX_RANGES.items():
            if low * 0.7 <= fx_rate <= high * 1.3:
                if fx_rate < low * 0.85 or fx_rate > high * 1.15:
                    self._add(
                        check_id="RSN-002", severity="MEDIUM", category="reasonableness",
                        entity_code=code, entity_name=name,
                        description=f"FX rate {fx_rate:.4f} near boundary of expected range for {currency} ({low}-{high})",
                        expected=f"{low} to {high}",
                        actual=f"{fx_rate:.4f}",
                        context="Verify rate is correct — may be stale or incorrectly entered",
                    )
                return

    # ─── ROLLOVER CHECKS ────────────────────────────────────────────────────

    def _check_rollover(self, parser_cy, df_cy, parser_py, df_py):
        """Year-over-year consistency checks — comprehensive rollover review."""
        cy_entities = set(df_cy["_reference_id"].unique()) - {""}
        py_entities = set(df_py["_reference_id"].unique()) - {""}

        # ROL-002: Entity in PY but not CY
        for code in py_entities - cy_entities:
            name = self._get_entity_name(df_py, code)
            self._add(
                check_id="ROL-002", severity="MEDIUM", category="rollover",
                entity_code=code, entity_name=name,
                description="Entity present in prior year but absent in current year",
                context="Verify: was this entity liquidated, sold, or merged? Check Sch O.",
            )

        # ROL-003: Entity in CY but not PY
        for code in cy_entities - py_entities:
            name = self._get_entity_name(df_cy, code)
            self._add(
                check_id="ROL-003", severity="MEDIUM", category="rollover",
                entity_code=code, entity_name=name,
                description="Entity present in current year but not in prior year (new)",
                context="Verify: was this entity acquired, incorporated, or reclassified? Check Sch O.",
            )

        # ROL-001: Sch F per-line rollover (16 BS lines)
        self._check_balance_sheet_rollover(parser_cy, df_cy, parser_py, df_py)

        # ROL-004: E&P sign flip
        sch_h_cy = parser_cy.extract_form("IRS5471ScheduleH")
        sch_h_py = parser_py.extract_form("IRS5471ScheduleH")
        if not sch_h_cy.empty and not sch_h_py.empty:
            self._check_ep_sign_flip(sch_h_cy, sch_h_py, df_cy)

        # ROL-005: FX rate change > 25% YoY
        if not sch_h_cy.empty and not sch_h_py.empty:
            self._check_fx_rate_change(sch_h_cy, sch_h_py, df_cy)

        # ROL-006: Material amount disappears
        if not sch_h_cy.empty and not sch_h_py.empty:
            self._check_material_disappearance(sch_h_cy, sch_h_py, df_cy)

        # ROL-007: Accumulated E&P rollover (Sch J — all pools)
        sch_j_cy = parser_cy.extract_form("IRS5471ScheduleJ")
        sch_j_py = parser_py.extract_form("IRS5471ScheduleJ")
        if not sch_j_cy.empty and not sch_j_py.empty:
            self._check_accumulated_ep_rollover(sch_j_cy, sch_j_py, df_cy)

        # ROL-008: Page 1 static field changes (entity info)
        self._check_page1_rollover(parser_cy, df_cy, parser_py, df_py)

        # ROL-009: Sch G indicator flips
        self._check_schg_indicator_flips(parser_cy, df_cy, parser_py, df_py)

        # ROL-010: GILTI classification change (tested income -> tested loss or vice versa)
        sch_i1_cy = parser_cy.extract_form("IRS5471ScheduleI1")
        sch_i1_py = parser_py.extract_form("IRS5471ScheduleI1")
        if not sch_i1_cy.empty and not sch_i1_py.empty:
            self._check_gilti_classification_change(sch_i1_cy, sch_i1_py, df_cy)

        # ROL-011: Sch H accumulated E&P math (BOY + current = EOY)
        if not sch_h_cy.empty:
            self._check_ep_accumulation_math(sch_h_cy, sch_j_cy, df_cy)

    # 16 balance sheet line pairs: (PY EOY field suffix, CY BOY field suffix, description)
    _SCH_F_ROLLOVER_LINES = [
        ("EndAcctPrdCashAmt", "BegngAcctPrdCashAmt", "Cash"),
        ("EndAcctPrdTradeNotesAmt", "BegngAcctPrdTradeNotesAmt", "Trade notes & AR"),
        ("EndAcctPrdInventoriesAmt", "BegngAcctPrdInventoriesAmt", "Inventories"),
        ("EndAcctPrdInvstSubsidiaryAmt", "BegngAcctPrdInvstSubsidiaryAmt", "Investment in subs"),
        ("EndAcctPrdBldgAndOtherAstAmt", "BegngAcctPrdBldgAndOtherAstAmt", "Buildings & depreciable"),
        ("EndAcctPrdLandAmt", "BegngAcctPrdLandAmt", "Land"),
        ("EndAcctPrdPatentsOthAstAmt", "BegngAcctPrdPatentsOthAstAmt", "Intangibles"),
        ("EndAcctPrdOtherAssetsAmt", "BegngAcctPrdOtherAssetsAmt", "Other assets"),
        ("EndAcctPrdTotalAssetsAmt", "BegngAcctPrdTotalAssetsAmt", "Total assets"),
        ("EndAcctPrdAccountsPayableAmt", "BegngAcctPrdAccountsPayableAmt", "Accounts payable"),
        ("EndAcctPrdOtherCurrLiabAmt", "BegngAcctPrdOtherCurrLiabAmt", "Other current liabilities"),
        ("EndAcctPrdOthLiabilitiesAmt", "BegngAcctPrdOthLiabilitiesAmt", "Other liabilities"),
        ("EndAcctPrdCommonStockAmt", "BegngAcctPrdCommonStockAmt", "Capital stock"),
        ("EndAcctPrdPaidInOrSurplusAmt", "BegngAcctPrdPaidInOrSurplusAmt", "Paid-in surplus"),
        ("EndAcctPrdRtnEarningsAmt", "BegngAcctPrdRtnEarningsAmt", "Retained earnings"),
        ("EndAcctPrdTotLiabShrEqtyAmt", "BegngAcctPrdTotLiabShrEqtyAmt", "Total L+E"),
    ]

    def _check_balance_sheet_rollover(self, parser_cy, df_cy, parser_py, df_py):
        """ROL-001: PY EOY should equal CY BOY for all 16 BS lines per entity."""
        sch_f_cy = parser_cy.extract_form("IRS5471ScheduleF")
        sch_f_py = parser_py.extract_form("IRS5471ScheduleF")

        if sch_f_cy.empty or sch_f_py.empty:
            return

        f_cy = sch_f_cy.set_index("_reference_id")
        f_py = sch_f_py.set_index("_reference_id")

        common = set(f_cy.index) & set(f_py.index) - {""}

        for code in common:
            name = self._get_entity_name(df_cy, code)
            cy_row = f_cy.loc[code]
            py_row = f_py.loc[code]

            for py_eoy_suffix, cy_boy_suffix, desc in self._SCH_F_ROLLOVER_LINES:
                py_col = f"IRS5471ScheduleF_{py_eoy_suffix}"
                cy_col = f"IRS5471ScheduleF_{cy_boy_suffix}"

                py_eoy = self._safe_float(py_row, py_col)
                cy_boy = self._safe_float(cy_row, cy_col)

                if py_eoy is None and cy_boy is None:
                    continue
                py_eoy = py_eoy or 0
                cy_boy = cy_boy or 0

                delta = abs(cy_boy - py_eoy)
                # Materiality: flag if delta > $10K and > 0.1% of the amount
                if delta > 10000 and delta > max(1, abs(py_eoy) * 0.001):
                    severity = "HIGH" if "Total" in desc else "MEDIUM"
                    self._add(
                        check_id="ROL-001", severity=severity, category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"Sch F {desc}: CY BOY ({cy_boy:,.0f}) != PY EOY ({py_eoy:,.0f})",
                        expected=f"CY BOY = PY EOY ({py_eoy:,.0f})",
                        actual=f"CY BOY = {cy_boy:,.0f} (delta {delta:,.0f})",
                        delta=delta,
                        context="Balance sheet must roll forward. FX retranslation may explain small diffs.",
                    )

    def _check_ep_sign_flip(self, sch_h_cy, sch_h_py, df_cy):
        """ROL-004: E&P sign flip without material transaction."""
        ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
        sch_h_cy = sch_h_cy.set_index("_reference_id")
        sch_h_py = sch_h_py.set_index("_reference_id")

        if ep_col not in sch_h_cy.columns or ep_col not in sch_h_py.columns:
            return

        common = set(sch_h_cy.index) & set(sch_h_py.index) - {""}
        for code in common:
            cy_ep = self._safe_float(sch_h_cy.loc[code], ep_col)
            py_ep = self._safe_float(sch_h_py.loc[code], ep_col)

            if cy_ep is not None and py_ep is not None:
                if (cy_ep > 50000 and py_ep < -50000) or (cy_ep < -50000 and py_ep > 50000):
                    name = self._get_entity_name(df_cy, code)
                    self._add(
                        check_id="ROL-004", severity="MEDIUM", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"E&P sign flip: PY ${py_ep:,.0f} to CY ${cy_ep:,.0f}",
                        expected="Sign consistency unless material transaction occurred",
                        actual=f"PY: ${py_ep:,.0f}, CY: ${cy_ep:,.0f}",
                        context="Verify: acquisition, disposition, or large one-time item?",
                    )

    def _check_material_disappearance(self, sch_h_cy, sch_h_py, df_cy):
        """ROL-006: Material amount disappears to zero."""
        ep_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
        sch_h_cy = sch_h_cy.set_index("_reference_id") if "_reference_id" in sch_h_cy.columns else sch_h_cy
        sch_h_py = sch_h_py.set_index("_reference_id") if "_reference_id" in sch_h_py.columns else sch_h_py

        if ep_col not in sch_h_cy.columns or ep_col not in sch_h_py.columns:
            return

        common = set(sch_h_cy.index) & set(sch_h_py.index) - {""}
        for code in common:
            py_ep = self._safe_float(sch_h_py.loc[code], ep_col)
            cy_ep = self._safe_float(sch_h_cy.loc[code], ep_col)

            if py_ep is not None and abs(py_ep) > 100000 and (cy_ep is None or cy_ep == 0):
                name = self._get_entity_name(df_cy, code)
                self._add(
                    check_id="ROL-006", severity="HIGH", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Material E&P (${py_ep:,.0f}) in PY dropped to zero in CY",
                    expected="Non-zero E&P unless entity disposed/liquidated",
                    actual="$0 in current year",
                    delta=abs(py_ep),
                    context="Check for liquidation, disposition, or data omission",
                )

    def _check_fx_rate_change(self, sch_h_cy, sch_h_py, df_cy):
        """ROL-005: FX rate change > 25% YoY (potential data entry error)."""
        fx_col = "IRS5471ScheduleH_ExchangeRt"
        h_cy = sch_h_cy.set_index("_reference_id")
        h_py = sch_h_py.set_index("_reference_id")

        if fx_col not in h_cy.columns or fx_col not in h_py.columns:
            return

        common = set(h_cy.index) & set(h_py.index) - {""}
        for code in common:
            cy_fx = self._safe_float(h_cy.loc[code], fx_col)
            py_fx = self._safe_float(h_py.loc[code], fx_col)

            if cy_fx is not None and py_fx is not None and py_fx > 0 and cy_fx > 0:
                pct_change = abs(cy_fx - py_fx) / py_fx
                if pct_change > 0.25:
                    name = self._get_entity_name(df_cy, code)
                    self._add(
                        check_id="ROL-005", severity="LOW", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"FX rate changed {pct_change:.0%} YoY (PY: {py_fx:.4f}, CY: {cy_fx:.4f})",
                        expected="Change < 25% unless currency devaluation occurred",
                        actual=f"PY: {py_fx:.4f}, CY: {cy_fx:.4f} ({pct_change:.0%} change)",
                        context="Large FX swings may be correct (e.g. ARS, TRY) or indicate wrong rate entry",
                    )

    # Sch J PTEP pools to check rollover
    _SCH_J_POOLS = [
        ("Post2017EPNotPrevTaxedGrp", "Post-2017 E&P Not Previously Taxed"),
        ("TotalSection964AEPGrp", "Total Section 964(a) E&P"),
        ("Post1986UndistributedEarnGrp", "Post-1986 Undistributed Earnings"),
        ("HoveringDeficitDedSspndTaxGrp", "Hovering Deficit"),
        ("Section951APTEPGrp", "Section 951A PTEP (GILTI)"),
    ]

    def _check_accumulated_ep_rollover(self, sch_j_cy, sch_j_py, df_cy):
        """ROL-007: PY Sch J ending balance should equal CY beginning for ALL pools."""
        j_cy = sch_j_cy.set_index("_reference_id")
        j_py = sch_j_py.set_index("_reference_id")
        common = set(j_cy.index) & set(j_py.index) - {""}

        for pool_name, pool_desc in self._SCH_J_POOLS:
            boy_col = f"IRS5471ScheduleJ_{pool_name}_BeginningYearBalanceAmt"
            eoy_col = f"IRS5471ScheduleJ_{pool_name}_BalanceBeginningNextYearAmt"

            if boy_col not in j_cy.columns or eoy_col not in j_py.columns:
                continue

            for code in common:
                cy_boy = self._safe_float(j_cy.loc[code], boy_col)
                py_eoy = self._safe_float(j_py.loc[code], eoy_col)

                if cy_boy is None and py_eoy is None:
                    continue
                cy_boy = cy_boy or 0
                py_eoy = py_eoy or 0

                delta = abs(cy_boy - py_eoy)
                if delta > max(1, abs(py_eoy) * 0.001) and delta > 100:
                    name = self._get_entity_name(df_cy, code)
                    self._add(
                        check_id="ROL-007", severity="HIGH", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"Sch J {pool_desc}: CY BOY (${cy_boy:,.0f}) != PY EOY (${py_eoy:,.0f})",
                        expected=f"CY beginning = PY ending (${py_eoy:,.0f})",
                        actual=f"CY BOY = ${cy_boy:,.0f} (delta ${delta:,.0f})",
                        delta=delta,
                        context="E&P pool must roll forward. Gap = missed distribution, inclusion, reclassification, or data error.",
                    )

    def _check_page1_rollover(self, parser_cy, df_cy, parser_py, df_py):
        """ROL-008: Entity identification fields should not change PY to CY."""
        cy_main = parser_cy.to_dataframe().set_index("_reference_id")
        py_main = parser_py.to_dataframe().set_index("_reference_id")
        common = set(cy_main.index) & set(py_main.index) - {""}

        static_fields = [
            ("_entity_name", "Entity name"),
            ("IRS5471_CountryUnderWhoseLawsIncCd", "Country of incorporation"),
            ("IRS5471_FunctionalCurrencyCd", "Functional currency"),
            ("IRS5471_PrincipalPlaceOfBusCountryCd", "Principal place of business"),
        ]

        for code in common:
            name = self._get_entity_name(df_cy, code)
            for col, desc in static_fields:
                if col not in cy_main.columns or col not in py_main.columns:
                    continue
                try:
                    cy_val = str(cy_main.loc[code, col] or "").strip().upper()
                    py_val = str(py_main.loc[code, col] or "").strip().upper()
                except (KeyError, TypeError):
                    continue

                if not py_val or not cy_val:
                    continue
                if py_val == "NAN" or cy_val == "NAN":
                    continue

                if py_val != cy_val:
                    severity = "HIGH" if "currency" in desc.lower() else "MEDIUM"
                    self._add(
                        check_id="ROL-008", severity=severity, category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"{desc} changed: '{py_val}' -> '{cy_val}'",
                        expected=f"Unchanged (PY: {py_val})",
                        actual=f"CY: {cy_val}",
                        context="Static entity info should not change unless reclassification, re-domiciliation, or error.",
                    )

    def _check_schg_indicator_flips(self, parser_cy, df_cy, parser_py, df_py):
        """ROL-009: Sch G Yes/No indicator flips between PY and CY."""
        cy_main = parser_cy.to_dataframe().set_index("_reference_id")
        py_main = parser_py.to_dataframe().set_index("_reference_id")
        common = set(cy_main.index) & set(py_main.index) - {""}

        indicators = [
            ("IRS5471_IRS5471ScheduleG_DisallowedInterestExpenseInd", "163(j) disallowed interest"),
            ("IRS5471_IRS5471ScheduleG_BaseErosionPaymentBenefitInd", "Base erosion payments (BEAT)"),
            ("IRS5471_IRS5471ScheduleG_FDIIBenefitsClaimInd", "FDII benefits claimed"),
            ("IRS5471_IRS5471ScheduleG_PayOrAccrueTopUpTaxInd", "Top-up tax (Pillar Two)"),
        ]

        for code in common:
            name = self._get_entity_name(df_cy, code)
            for col, desc in indicators:
                if col not in cy_main.columns or col not in py_main.columns:
                    continue
                try:
                    cy_val = str(cy_main.loc[code, col] or "").strip().upper()
                    py_val = str(py_main.loc[code, col] or "").strip().upper()
                except (KeyError, TypeError):
                    continue

                if py_val == cy_val:
                    continue
                if py_val in ("", "NAN") and cy_val in ("", "NAN"):
                    continue

                direction = f"{'Yes' if py_val in ('1','TRUE','Y','YES') else 'No'} -> {'Yes' if cy_val in ('1','TRUE','Y','YES') else 'No'}"
                self._add(
                    check_id="ROL-009", severity="MEDIUM", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"Sch G indicator flip: {desc} ({direction})",
                    expected=f"PY: {py_val or 'blank'}",
                    actual=f"CY: {cy_val or 'blank'}",
                    context="Indicator changes may trigger new compliance requirements or affect calculations.",
                )

    def _check_gilti_classification_change(self, sch_i1_cy, sch_i1_py, df_cy):
        """ROL-010: GILTI tested income/loss classification flip."""
        tested_col = "IRS5471ScheduleI1_TestedIncomeLossGrp_USDollarAmt"
        i1_cy = sch_i1_cy.set_index("_reference_id")
        i1_py = sch_i1_py.set_index("_reference_id")

        if tested_col not in i1_cy.columns or tested_col not in i1_py.columns:
            return

        common = set(i1_cy.index) & set(i1_py.index) - {""}
        for code in common:
            cy_tested = self._safe_float(i1_cy.loc[code], tested_col)
            py_tested = self._safe_float(i1_py.loc[code], tested_col)

            if cy_tested is None or py_tested is None:
                continue

            # Tested income to tested loss (or vice versa) with material amounts
            if py_tested > 10000 and cy_tested < -10000:
                name = self._get_entity_name(df_cy, code)
                self._add(
                    check_id="ROL-010", severity="MEDIUM", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"GILTI classification flip: tested income (${py_tested:,.0f}) -> tested loss (${cy_tested:,.0f})",
                    expected="Consistent classification unless material business change",
                    actual=f"PY: ${py_tested:,.0f}, CY: ${cy_tested:,.0f}",
                    context="Entity moved from GILTI inclusion contributor to loss entity. Verify business deterioration or restructuring.",
                )
            elif py_tested < -10000 and cy_tested > 10000:
                name = self._get_entity_name(df_cy, code)
                self._add(
                    check_id="ROL-010", severity="LOW", category="rollover",
                    entity_code=code, entity_name=name,
                    description=f"GILTI classification flip: tested loss (${py_tested:,.0f}) -> tested income (${cy_tested:,.0f})",
                    expected="Consistent classification unless recovery",
                    actual=f"PY: ${py_tested:,.0f}, CY: ${cy_tested:,.0f}",
                    context="Entity recovered from loss to income. Verify turnaround or one-time item.",
                )

    def _check_ep_accumulation_math(self, sch_h_cy, sch_j_cy, df_cy):
        """ROL-011: Sch J EOY should = BOY + Sch H current year E&P (simplified check)."""
        if sch_j_cy.empty:
            return

        h_cy = sch_h_cy.set_index("_reference_id")
        j_cy = sch_j_cy.set_index("_reference_id")

        ep_usd_col = "IRS5471ScheduleH_CurrEarnAndPrftInUSDollarsAmt"
        boy_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_BeginningYearBalanceAmt"
        cy_ep_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_CurrentYearEPAmt"
        eoy_col = "IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_BalanceBeginningNextYearAmt"

        if ep_usd_col not in h_cy.columns:
            return
        if boy_col not in j_cy.columns or eoy_col not in j_cy.columns:
            return

        common = set(h_cy.index) & set(j_cy.index) - {""}
        for code in common:
            boy = self._safe_float(j_cy.loc[code], boy_col)
            cy_ep_j = self._safe_float(j_cy.loc[code], cy_ep_col)
            eoy = self._safe_float(j_cy.loc[code], eoy_col)
            cy_ep_h = self._safe_float(h_cy.loc[code], ep_usd_col)

            # Check 1: Sch J CY E&P column should match Sch H current E&P (USD)
            if cy_ep_j is not None and cy_ep_h is not None:
                delta = abs(cy_ep_j - cy_ep_h)
                if delta > max(100, abs(cy_ep_h) * 0.01) and delta > 1000:
                    name = self._get_entity_name(df_cy, code)
                    self._add(
                        check_id="ROL-011", severity="HIGH", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"Sch J CY E&P (${cy_ep_j:,.0f}) != Sch H current E&P USD (${cy_ep_h:,.0f})",
                        expected=f"Sch J col ii = Sch H line 5d (${cy_ep_h:,.0f})",
                        actual=f"Sch J = ${cy_ep_j:,.0f} (delta ${delta:,.0f})",
                        delta=delta,
                        context="Current year E&P on Sch J must tie to Sch H. Mismatch = Sch J not updated or wrong pool.",
                    )

            # Check 2: BOY + movements should approximate EOY
            if boy is not None and eoy is not None and cy_ep_j is not None:
                # Simplified: BOY + CY E&P should be close to EOY
                # (ignoring distributions, reclassifications which reduce it)
                # Only flag if EOY > BOY + CY E&P (impossible without other additions)
                expected_min = boy + cy_ep_j
                if eoy > expected_min + max(1000, abs(expected_min) * 0.05):
                    overage = eoy - expected_min
                    name = self._get_entity_name(df_cy, code)
                    self._add(
                        check_id="ROL-011", severity="MEDIUM", category="rollover",
                        entity_code=code, entity_name=name,
                        description=f"Sch J EOY (${eoy:,.0f}) > BOY + CY E&P (${expected_min:,.0f}) by ${overage:,.0f}",
                        expected=f"EOY <= BOY ({boy:,.0f}) + CY E&P ({cy_ep_j:,.0f}) unless reclassification in",
                        actual=f"EOY = ${eoy:,.0f} (overage ${overage:,.0f})",
                        delta=overage,
                        context="E&P pool grew more than current year earnings explain. Check reclassifications or data entry.",
                    )

    # ─── HELPERS ────────────────────────────────────────────────────────────

    def _safe_float(self, row, col: str) -> float | None:
        try:
            val = row[col] if col in row.index else None
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            return float(val)
        except (ValueError, TypeError, KeyError):
            return None

    def _safe_float_df(self, df, idx, col: str) -> float | None:
        try:
            val = df.loc[idx, col]
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            return float(val)
        except (ValueError, TypeError, KeyError):
            return None

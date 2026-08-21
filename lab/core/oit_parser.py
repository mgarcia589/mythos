"""ONESOURCE Income Tax CSV/XLSX parsers with sign convention handling.

Includes:
- Low-level CSV parsers (Working TB, Adjustment Analysis, Sourcing WP)
- OITDataSource class for producing schedule-shaped DataFrames compatible
  with the Reconciler's three-way comparison mode.
"""

from pathlib import Path

import numpy as np
import pandas as pd


class OITSignConvention:
    """Handle OIT's sign convention where negative = income/profit."""

    @staticmethod
    def to_tax_convention(value: float) -> float:
        """Convert OIT sign (neg=income) to tax convention (pos=income)."""
        return -value

    @staticmethod
    def flip_series(s: pd.Series) -> pd.Series:
        return -s


def parse_working_trial_balance(path: str | Path) -> pd.DataFrame:
    """Parse OIT Current Working Trial Balance CSV.

    Returns DataFrame with columns normalized and numeric values parsed.
    """
    df = pd.read_csv(path, thousands=",")
    numeric_cols = [
        c
        for c in df.columns
        if "Balance" in c or "Adjustments" in c or "FC" in c or "LC" in c
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def parse_adjustment_analysis(path: str | Path) -> pd.DataFrame:
    """Parse OIT Current Adjustment Analysis CSV."""
    df = pd.read_csv(path, thousands=",")
    for col in ["Net P&L Impact (Dr/Cr)", "Net P&L Impact FC (Dr/Cr)", "Net P&L Impact LC (Dr/Cr)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def parse_tb_with_detail(path: str | Path) -> pd.DataFrame:
    """Parse OIT Working TB with Adjustment Detail CSV."""
    df = pd.read_csv(path, thousands=",")
    numeric_cols = [
        c
        for c in df.columns
        if "Balance" in c or "Adjustments" in c
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def extract_entity_ep(tb_df: pd.DataFrame, binder_year: int = 2025) -> pd.DataFrame:
    """Extract E&P-relevant data per entity from Working TB.

    Filters to income statement accounts (TRC 30-41) for the specified binder year.
    Returns pivoted DataFrame: entity × account → USD balance.
    """
    mask = (
        (tb_df["Binder Year"] == binder_year)
        & (tb_df["Account Number"].str.match(r"^(3[0-9]|4[0-1])-"))
    )
    is_df = tb_df[mask].copy()

    pivot = is_df.pivot_table(
        index="Company Number",
        columns="Account Number",
        values="Adjusted Tax Balance USD",
        aggfunc="sum",
        fill_value=0,
    )
    return pivot


def get_entities_by_deal(tb_df: pd.DataFrame) -> dict[str, list[str]]:
    """Categorize entities by deal based on company number prefix."""
    entities = tb_df["Company Number"].unique()
    deals = {"Portfolio-A": [], "Portfolio-B": [], "Portfolio-C": [], "Other": []}
    for e in entities:
        if e.startswith("C0") or e.endswith("_DC"):
            deals["Portfolio-A"].append(e)
        elif e.startswith("SS"):
            deals["Portfolio-B"].append(e)
        elif e.startswith("AM"):
            deals["Portfolio-C"].append(e)
        else:
            deals["Other"].append(e)
    return deals


def parse_sourcing_workpaper(path: str | Path) -> pd.DataFrame:
    """Parse OIT Sourcing Workpaper (VI.A) CSV.

    Returns DataFrame with numeric Sourced Amount and TAS Trial Balance Amount.
    Key columns: Company Number, Source Code, Sourced Amount,
    International Account Number, International Account Description.
    """
    df = pd.read_csv(path, thousands=",")
    for col in ["Sourced Amount", "TAS Trial Balance Amount", "Trial Balance Override Amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "Source Code" in df.columns:
        df["Source Code"] = pd.to_numeric(df["Source Code"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# TRC-to-Schedule Mapping
# ---------------------------------------------------------------------------

# OIT TRC ranges that map to Schedule C (Income Statement)
_SCH_C_INCOME_TRCS = {"30-100", "30-200", "30-300", "30-400", "30-500",
                      "30-600", "30-700", "30-800", "30-900",
                      "31-100", "31-200", "31-300", "31-400", "31-500",
                      "31-600", "31-700", "31-800", "31-900"}
_SCH_C_DEDUCTION_TRCS = {"41-100", "41-200", "41-260", "41-300", "41-400",
                         "41-500", "41-600", "41-700", "41-800", "41-900"}

# OIT TRC ranges that map to Schedule F (Balance Sheet)
_SCH_F_ASSET_TRCS = {"10-100", "10-200", "10-300", "10-400", "10-500",
                     "10-600", "10-700", "10-800", "10-900",
                     "11-100", "11-200", "11-300", "11-400"}
_SCH_F_LIAB_EQUITY_TRCS = {"20-100", "20-200", "20-300", "20-400", "20-500",
                           "20-600", "20-700", "20-800", "20-900",
                           "21-100", "21-200", "21-300",
                           "22-100", "22-200", "22-300", "22-400",
                           "22-500", "22-600", "22-700", "22-800", "22-900"}

# E&P Adjustment types from Adjustment Analysis
_EP_ADDITION_TYPES = {"Tax", "Depreciation", "Amortization", "Meals",
                      "Fines", "Life Insurance", "Other Additions"}
_EP_SUBTRACTION_TYPES = {"Tax-Exempt", "Life Ins Proceeds",
                         "Other Subtractions", "Distributions"}


# ---------------------------------------------------------------------------
# OITDataSource — Schedule-shaped DataFrames for Reconciler
# ---------------------------------------------------------------------------

class OITDataSource:
    """Transform OIT CSV exports into schedule-shaped DataFrames for reconciliation.

    Produces DataFrames indexed by entity_code with columns named to match
    XML field names, making them directly comparable via the Reconciler.

    Usage:
        oit = OITDataSource(
            tb_path="sources/oit-current-working-trial-balance.csv",
            adj_path="sources/oit-current-adjustment-analysis.csv",
            sourcing_path="sources/oit-sourcing-workpaper.csv",
        )
        sch_h = oit.get_schedule("sch_h_fc")
        # Returns DataFrame with columns like CurrEarnAndPrftInFuncCurAmt, etc.
    """

    def __init__(
        self,
        tb_path: str | Path | None = None,
        adj_path: str | Path | None = None,
        sourcing_path: str | Path | None = None,
        tb_detail_path: str | Path | None = None,
        binder_year: int = 2024,
    ):
        self._tb_df = parse_working_trial_balance(tb_path) if tb_path else None
        self._adj_df = parse_adjustment_analysis(adj_path) if adj_path else None
        self._sourcing_df = parse_sourcing_workpaper(sourcing_path) if sourcing_path else None
        self._tb_detail_df = parse_tb_with_detail(tb_detail_path) if tb_detail_path else None
        self._binder_year = binder_year
        self._cache: dict[str, pd.DataFrame] = {}

    @property
    def entities(self) -> list[str]:
        """All entity codes found across OIT data."""
        entity_sets: list[set] = []
        if self._tb_df is not None:
            entity_sets.append(set(self._tb_df["Company Number"].unique()))
        if self._adj_df is not None:
            entity_sets.append(set(self._adj_df["Company Number"].unique()))
        if self._sourcing_df is not None:
            entity_sets.append(set(self._sourcing_df["Company Number"].unique()))
        if not entity_sets:
            return []
        return sorted(set.union(*entity_sets))

    @property
    def schedules(self) -> dict[str, pd.DataFrame]:
        """All available schedule DataFrames (lazy-built, cached)."""
        available = []
        if self._tb_df is not None:
            available.extend(["sch_c_fc", "sch_f_usd"])
        if self._adj_df is not None:
            available.append("sch_h_fc")
        if self._sourcing_df is not None:
            available.append("subf_sourcing")
        return {k: self.get_schedule(k) for k in available}

    def get_schedule(self, schedule_key: str) -> pd.DataFrame:
        """Return schedule DataFrame indexed by entity_code."""
        if schedule_key in self._cache:
            return self._cache[schedule_key]

        builders = {
            "sch_c_fc": self._build_sch_c,
            "sch_h_fc": self._build_sch_h,
            "sch_f_usd": self._build_sch_f,
            "sch_e": self._build_sch_e,
            "subf_sourcing": self._build_subf_sourcing,
        }
        builder = builders.get(schedule_key)
        if builder is None:
            return pd.DataFrame()

        df = builder()
        self._cache[schedule_key] = df
        return df

    # ------------------------------------------------------------------
    # Schedule Builders
    # ------------------------------------------------------------------

    def _filter_tb(self) -> pd.DataFrame:
        """Filter Working TB to the relevant binder year."""
        if self._tb_df is None:
            return pd.DataFrame()
        mask = self._tb_df["Binder Year"] == self._binder_year
        return self._tb_df[mask].copy()

    def _build_sch_c(self) -> pd.DataFrame:
        """Build Schedule C (Income Statement) from Working TB.

        Aggregates income (TRC 30-*) and deduction (TRC 41-*) accounts by entity.
        Columns named to match XML field names for IRS5471ScheduleC.
        """
        tb = self._filter_tb()
        if tb.empty:
            return pd.DataFrame()

        tb["_trc_base"] = tb["Account Number"].str.split(".").str[0]

        income_mask = tb["_trc_base"].isin(_SCH_C_INCOME_TRCS)
        deduction_mask = tb["_trc_base"].isin(_SCH_C_DEDUCTION_TRCS)

        income_by_entity = (
            tb[income_mask]
            .groupby("Company Number")["Adjusted Tax Balance FC"]
            .sum()
        )
        deductions_by_entity = (
            tb[deduction_mask]
            .groupby("Company Number")["Adjusted Tax Balance FC"]
            .sum()
        )

        result = pd.DataFrame(index=income_by_entity.index.union(deductions_by_entity.index))
        result["ForeignGrossIncomeAmt"] = income_by_entity.reindex(result.index, fill_value=0)
        result["ForeignTotalDeductionsAmt"] = deductions_by_entity.reindex(result.index, fill_value=0).abs()
        result["ForeignCYNetIncomePerBooksAmt"] = (
            result["ForeignGrossIncomeAmt"] - result["ForeignTotalDeductionsAmt"]
        )
        result.index.name = "_entity_code"
        return result

    def _build_sch_h(self) -> pd.DataFrame:
        """Build Schedule H (Current E&P) from Adjustment Analysis.

        Aggregates E&P additions and subtractions per entity.
        Line 1 (net income) comes from Sch C; lines 2-3 from adjustments.
        """
        if self._adj_df is None:
            return pd.DataFrame()

        adj = self._adj_df.copy()
        if "Binder Year" in adj.columns:
            adj = adj[adj["Binder Year"] == self._binder_year]

        # Classify adjustments
        adj["_is_addition"] = adj["Adjustment Type"].isin(_EP_ADDITION_TYPES)
        adj["_is_subtraction"] = adj["Adjustment Type"].isin(_EP_SUBTRACTION_TYPES)

        # For adjustments not matching either set, use sign: positive = addition, negative = subtraction
        unclassified = ~adj["_is_addition"] & ~adj["_is_subtraction"]
        adj.loc[unclassified & (adj["Net P&L Impact FC (Dr/Cr)"] >= 0), "_is_addition"] = True
        adj.loc[unclassified & (adj["Net P&L Impact FC (Dr/Cr)"] < 0), "_is_subtraction"] = True

        additions = (
            adj[adj["_is_addition"]]
            .groupby("Company Number")["Net P&L Impact FC (Dr/Cr)"]
            .sum()
        )
        subtractions = (
            adj[adj["_is_subtraction"]]
            .groupby("Company Number")["Net P&L Impact FC (Dr/Cr)"]
            .sum()
        )

        # Get Sch C net income from TB (Line 1 of Sch H)
        sch_c = self._build_sch_c()
        net_income = sch_c["ForeignCYNetIncomePerBooksAmt"] if not sch_c.empty else pd.Series(dtype=float)

        all_entities = set()
        all_entities.update(additions.index)
        all_entities.update(subtractions.index)
        if not net_income.empty:
            all_entities.update(net_income.index)

        idx = pd.Index(sorted(all_entities), name="_entity_code")
        result = pd.DataFrame(index=idx)
        result["NetIncomeLossPerIncomeStmtAmt"] = net_income.reindex(idx, fill_value=0)
        result["OtherAdjustmentsNetAddsAmt"] = additions.reindex(idx, fill_value=0)
        result["TotalNetSubtractionsAmt"] = subtractions.reindex(idx, fill_value=0).abs()

        # Current E&P in FC = Line 1 + Additions - Subtractions
        result["CurrEarnAndPrftInFuncCurAmt"] = (
            result["NetIncomeLossPerIncomeStmtAmt"]
            + result["OtherAdjustmentsNetAddsAmt"]
            - result["TotalNetSubtractionsAmt"]
        )

        # USD conversion requires FX rates — not available here, leave as NaN
        result["CurrEarnAndPrftInUSDollarsAmt"] = np.nan

        return result

    def _build_sch_f(self) -> pd.DataFrame:
        """Build Schedule F (Balance Sheet) from Working TB.

        Aggregates asset and liability accounts by entity in USD.
        """
        tb = self._filter_tb()
        if tb.empty:
            return pd.DataFrame()

        tb["_trc_base"] = tb["Account Number"].str.split(".").str[0]

        asset_mask = tb["_trc_base"].isin(_SCH_F_ASSET_TRCS)
        liab_mask = tb["_trc_base"].isin(_SCH_F_LIAB_EQUITY_TRCS)

        assets_by_entity = (
            tb[asset_mask]
            .groupby("Company Number")["Adjusted Tax Balance USD"]
            .sum()
        )
        liabs_by_entity = (
            tb[liab_mask]
            .groupby("Company Number")["Adjusted Tax Balance USD"]
            .sum()
        )

        idx = assets_by_entity.index.union(liabs_by_entity.index)
        result = pd.DataFrame(index=idx)
        result["TotalAssetsAmt"] = assets_by_entity.reindex(idx, fill_value=0)
        result["TotalLiabilitiesAmt"] = liabs_by_entity.reindex(idx, fill_value=0)
        result.index.name = "_entity_code"
        return result

    def _build_sch_e(self) -> pd.DataFrame:
        """Build Schedule E (Taxes) from Adjustment Analysis.

        Extracts tax-type adjustments as foreign taxes paid.
        """
        if self._adj_df is None:
            return pd.DataFrame()

        adj = self._adj_df.copy()
        if "Binder Year" in adj.columns:
            adj = adj[adj["Binder Year"] == self._binder_year]

        tax_adj = adj[adj["Adjustment Type"] == "Tax"]

        taxes_fc = tax_adj.groupby("Company Number")["Net P&L Impact FC (Dr/Cr)"].sum()
        taxes_usd = tax_adj.groupby("Company Number")["Net P&L Impact (Dr/Cr)"].sum()

        idx = taxes_fc.index.union(taxes_usd.index)
        result = pd.DataFrame(index=idx)
        result["TotalTaxInFunctionalCurAmt"] = taxes_fc.reindex(idx, fill_value=0).abs()
        result["TotalTaxInUSDollarsAmt"] = taxes_usd.reindex(idx, fill_value=0).abs()
        result.index.name = "_entity_code"
        return result

    def _build_subf_sourcing(self) -> pd.DataFrame:
        """Build SubF income totals from Sourcing Workpaper.

        Source Code 61 = Passive FPHCI (SubF income)
        Source Code 21 = General Limitation (tested income)
        """
        if self._sourcing_df is None:
            return pd.DataFrame()

        sw = self._sourcing_df.copy()

        # Filter to income accounts only (sourced amounts)
        sc61 = sw[sw["Source Code"] == 61].groupby("Company Number")["Sourced Amount"].sum()
        sc21 = sw[sw["Source Code"] == 21].groupby("Company Number")["Sourced Amount"].sum()

        idx = sc61.index.union(sc21.index)
        result = pd.DataFrame(index=idx)
        result["SubpartFIncome_SC61"] = sc61.reindex(idx, fill_value=0)
        result["GeneralLimitation_SC21"] = sc21.reindex(idx, fill_value=0)
        result["TotalSourcedIncome"] = result["SubpartFIncome_SC61"] + result["GeneralLimitation_SC21"]
        result.index.name = "_entity_code"
        return result

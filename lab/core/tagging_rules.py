"""Tagging Rules — Deterministic classification rules for CFC entities.

Each rule is a pure function: (EntityData) -> bool.
Rules never crash on missing data — they return False.
"""

from __future__ import annotations

from lab.core.entity_tagger import EntityData, TagRule


# ─── GILTI CLASSIFICATION ─────────────────────────────────────────────────────

def _is_tested_income(e: EntityData) -> bool:
    amt = e.get("i1", "TestedIncomeAmt")
    if amt > 0:
        return True
    usd = e.get("i1", "TestedIncomeLossGrp_USDollarAmt")
    if usd > 0:
        return True
    fc = e.get("i1", "TestedIncomeLossGrp_FunctionalCurrencyAmt")
    return fc > 0


def _is_tested_loss(e: EntityData) -> bool:
    amt = e.get("i1", "TestedLossAmt")
    if amt > 0:
        return True
    usd = e.get("i1", "TestedIncomeLossGrp_USDollarAmt")
    if usd < 0:
        return True
    fc = e.get("i1", "TestedIncomeLossGrp_FunctionalCurrencyAmt")
    return fc < 0


def _has_high_tax_exclusion(e: EntityData) -> bool:
    if e.get("i1", "ExclGrossIncmHghTxdIncmAmt") > 0:
        return True
    return e.get("i1", "HighTaxExclusionElectionAmt") > 0


def _has_interest_expense(e: EntityData) -> bool:
    if e.get("i1", "TestedInterestExpenseAmt") > 0:
        return True
    return e.get("i1", "TestedInterestExpenseGrp_USDollarAmt") > 0


# ─── SUBPART F ────────────────────────────────────────────────────────────────

def _has_subpart_f(e: EntityData) -> bool:
    fields = [
        "SubpartFPHCIncomeAmt",
        "SubpartFSalesIncomeAmt",
        "SubpartFServicesIncomeAmt",
        "OtherSubpartFNotIncludedAmt",
        "SubpartFIncomeAmt",
    ]
    total = sum(e.get("i", f) for f in fields)
    return total > 0


def _is_de_minimis(e: EntityData) -> bool:
    """IRC 954(b)(3): SubF < lesser of $1M or 5% of gross income."""
    subf_fields = [
        "SubpartFPHCIncomeAmt",
        "SubpartFSalesIncomeAmt",
        "SubpartFServicesIncomeAmt",
        "OtherSubpartFNotIncludedAmt",
        "SubpartFIncomeAmt",
    ]
    total_subf = sum(e.get("i", f) for f in subf_fields)
    if total_subf <= 0:
        return False

    gross_income = e.get("c", "ForeignGrossIncomeAmt")
    if gross_income <= 0:
        gross_income = e.get("c", "GrossReceiptsOrSalesAmt")

    threshold = min(1_000_000, 0.05 * gross_income) if gross_income > 0 else 1_000_000
    return total_subf < threshold


# ─── E&P / INCOME ────────────────────────────────────────────────────────────

def _has_negative_ep(e: EntityData) -> bool:
    return e.get("h", "CurrentEarningsAndProfitsAmt") < 0


# ─── GILTI FULL INCLUSION ────────────────────────────────────────────────────

def _is_full_inclusion(e: EntityData) -> bool:
    """Full inclusion: tested income equals pro-rata share (no minority haircut)."""
    tested = e.get("i1", "TestedIncomeAmt")
    if tested <= 0:
        usd = e.get("i1", "TestedIncomeLossGrp_USDollarAmt")
        if usd <= 0:
            return False
    if e.voting_stock_pct is not None:
        return e.voting_stock_pct >= 1.0
    return False


# ─── RULE REGISTRY ───────────────────────────────────────────────────────────

DEFAULT_RULES: list[TagRule] = [
    TagRule(
        tag_name="tested_income",
        description="Entity has tested income (Sch I-1 positive)",
        evaluate=_is_tested_income,
        category="classification",
        priority=10,
        xml_fields=[
            ("i1", "TestedIncomeAmt"),
            ("i1", "TestedIncomeLossGrp_USDollarAmt"),
            ("i1", "TestedIncomeLossGrp_FunctionalCurrencyAmt"),
        ],
    ),
    TagRule(
        tag_name="tested_loss",
        description="Entity has tested loss (Sch I-1 negative)",
        evaluate=_is_tested_loss,
        category="classification",
        priority=10,
        xml_fields=[
            ("i1", "TestedLossAmt"),
            ("i1", "TestedIncomeLossGrp_USDollarAmt"),
            ("i1", "TestedIncomeLossGrp_FunctionalCurrencyAmt"),
        ],
    ),
    TagRule(
        tag_name="high_tax_exclusion",
        description="Entity elected high-tax exclusion (Sch I-1)",
        evaluate=_has_high_tax_exclusion,
        category="classification",
        priority=5,
        xml_fields=[
            ("i1", "ExclGrossIncmHghTxdIncmAmt"),
            ("i1", "HighTaxExclusionElectionAmt"),
        ],
    ),
    TagRule(
        tag_name="subpart_f",
        description="Entity has Subpart F income (Sch I aggregated)",
        evaluate=_has_subpart_f,
        category="classification",
        priority=8,
        xml_fields=[
            ("i", "SubpartFPHCIncomeAmt"),
            ("i", "SubpartFSalesIncomeAmt"),
            ("i", "SubpartFServicesIncomeAmt"),
            ("i", "OtherSubpartFNotIncludedAmt"),
            ("i", "SubpartFIncomeAmt"),
        ],
    ),
    TagRule(
        tag_name="de_minimis",
        description="SubF below de minimis threshold — IRC 954(b)(3)",
        evaluate=_is_de_minimis,
        category="classification",
        priority=7,
        xml_fields=[
            ("i", "SubpartFIncomeAmt"),
            ("c", "ForeignGrossIncomeAmt"),
            ("c", "GrossReceiptsOrSalesAmt"),
        ],
    ),
    TagRule(
        tag_name="full_inclusion",
        description="Tested income entity with 100% inclusion (no pro-rata reduction)",
        evaluate=_is_full_inclusion,
        category="classification",
        priority=3,
        xml_fields=[
            ("i1", "TestedIncomeAmt"),
            ("i1", "TestedIncomeLossGrp_USDollarAmt"),
        ],
    ),
    TagRule(
        tag_name="interest_expense",
        description="Tested interest expense > 0 (Sch I-1)",
        evaluate=_has_interest_expense,
        category="classification",
        priority=3,
        xml_fields=[
            ("i1", "TestedInterestExpenseAmt"),
            ("i1", "TestedInterestExpenseGrp_USDollarAmt"),
        ],
    ),
    TagRule(
        tag_name="negative_ep",
        description="Current E&P is negative (Sch H)",
        evaluate=_has_negative_ep,
        category="risk",
        priority=5,
        xml_fields=[
            ("h", "CurrentEarningsAndProfitsAmt"),
        ],
    ),
]

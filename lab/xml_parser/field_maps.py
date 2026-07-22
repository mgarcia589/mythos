"""Field mappings — translate XML paths to human-readable form line references.

Maps IRS e-file XML element names to:
- Form line numbers (as they appear on the printed form)
- Human-readable descriptions
- Data types (amount, text, date, percentage, indicator)
- Sign convention (negative=income in XML)
"""

# Schedule H — Earnings & Profits (Form 5471)
SCHEDULE_H_FIELDS = {
    "ForeignCYNetIncomePerBooksAmt": {
        "line": "1",
        "description": "Current year net income per books",
        "type": "amount",
        "sign": "negative_is_income",
    },
    "CapitalGainsOrLossesAmt": {
        "line": "2a",
        "description": "Capital gains or losses",
        "type": "amount",
    },
    "DepreciationAndAmortizationAmt": {
        "line": "2b",
        "description": "Depreciation and amortization",
        "type": "amount",
    },
    "DepletionAmt": {
        "line": "2c",
        "description": "Depletion",
        "type": "amount",
    },
    "InvestmentOrIncentiveAllwncAmt": {
        "line": "2d",
        "description": "Investment or incentive allowance",
        "type": "amount",
    },
    "ChargesToStatutoryReservesAmt": {
        "line": "2e",
        "description": "Charges to statutory reserves",
        "type": "amount",
    },
    "InventoryAdjustmentsAmt": {
        "line": "2f",
        "description": "Inventory adjustments",
        "type": "amount",
    },
    "TaxesNetAddnAmt": {
        "line": "2g",
        "description": "Income taxes (net addition)",
        "type": "amount",
    },
    "FrgnCurrencyGainLossAddnAmt": {
        "line": "2h",
        "description": "Foreign currency gains/losses",
        "type": "amount",
    },
    "OtherAdjustmentsNetAddnAmt": {
        "line": "2i(add)",
        "description": "Other adjustments (net addition)",
        "type": "amount",
    },
    "OtherAdjustmentsNetSbtrctnAmt": {
        "line": "2i(sub)",
        "description": "Other adjustments (net subtraction)",
        "type": "amount",
    },
    "TotalNetAdditionsAmt": {
        "line": "3",
        "description": "Total net additions",
        "type": "amount",
    },
    "TotalNetSubtractionsAmt": {
        "line": "4",
        "description": "Total net subtractions",
        "type": "amount",
    },
    "CurrentEarningsAndProfitsAmt": {
        "line": "5a",
        "description": "Current E&P",
        "type": "amount",
        "sign": "negative_is_income",
    },
    "DASTMGainOrLossAmt": {
        "line": "5b",
        "description": "DASTM gain or loss",
        "type": "amount",
    },
    "EarningAndPrftPlusDASTMGainAmt": {
        "line": "5c",
        "description": "Current E&P after DASTM",
        "type": "amount",
        "sign": "negative_is_income",
    },
    "CurrEarnAndPrftInUSDollarsAmt": {
        "line": "5d",
        "description": "Current E&P in USD",
        "type": "amount",
        "sign": "negative_is_income",
    },
    "ExchangeRt": {
        "line": "5d(rate)",
        "description": "Exchange rate (FC to USD)",
        "type": "rate",
    },
    "EPDASTMPassiveCatIncmAmt": {
        "line": "5c(PAS)",
        "description": "E&P — Passive category",
        "type": "amount",
        "sign": "negative_is_income",
    },
    "EPDASTMGeneralCatIncmAmt": {
        "line": "5c(GEN)",
        "description": "E&P — General category",
        "type": "amount",
        "sign": "negative_is_income",
    },
}

# Schedule I-1 — GILTI Information
SCHEDULE_I1_FIELDS = {
    "GrossIncomeAmt": {
        "line": "1",
        "description": "Gross income",
        "type": "amount",
    },
    "ExclGrossIncmEffCntdFCCorpAmt": {
        "line": "2a",
        "description": "Exclusion: ECI",
        "type": "amount",
    },
    "ExclGrossIncmSubpartFIncmAmt": {
        "line": "2b",
        "description": "Exclusion: Subpart F income",
        "type": "amount",
    },
    "ExclGrossIncmHghTxdIncmAmt": {
        "line": "2c",
        "description": "Exclusion: High-taxed income",
        "type": "amount",
    },
    "ExclGrossIncmDvdRcvdAmt": {
        "line": "2d",
        "description": "Exclusion: Dividends received",
        "type": "amount",
    },
    "TotalExclusionsAmt": {
        "line": "3",
        "description": "Total exclusions",
        "type": "amount",
    },
    "GrossIncmLessExclusionsAmt": {
        "line": "4",
        "description": "Gross income less exclusions",
        "type": "amount",
    },
    "AllocableDedExpnssAmt": {
        "line": "5",
        "description": "Allocable deductions",
        "type": "amount",
    },
    "TestedIncomeAmt": {
        "line": "6(pos)",
        "description": "Tested income",
        "type": "amount",
    },
    "TestedLossAmt": {
        "line": "6(neg)",
        "description": "Tested loss",
        "type": "amount",
    },
    "QBAIAmt": {
        "line": "8",
        "description": "QBAI",
        "type": "amount",
    },
    "TestedInterestExpenseAmt": {
        "line": "9a",
        "description": "Tested interest expense",
        "type": "amount",
    },
    "TestedInterestIncomeAmt": {
        "line": "10a",
        "description": "Tested interest income",
        "type": "amount",
    },
}

# Schedule C — Income Statement (Form 5471)
SCHEDULE_C_FIELDS = {
    "ForeignGrossReceiptsOrSalesAmt": {
        "line": "1a",
        "description": "Gross receipts or sales",
        "type": "amount",
    },
    "ForeignReturnsAndAllowancesAmt": {
        "line": "1b",
        "description": "Returns and allowances",
        "type": "amount",
    },
    "ForeignCostOfGoodsSoldAmt": {
        "line": "2",
        "description": "Cost of goods sold",
        "type": "amount",
    },
    "ForeignGrossProfitAmt": {
        "line": "3",
        "description": "Gross profit",
        "type": "amount",
    },
    "ForeignDividendIncomeAmt": {
        "line": "4",
        "description": "Dividends",
        "type": "amount",
    },
    "ForeignInterestIncomeAmt": {
        "line": "5",
        "description": "Interest",
        "type": "amount",
    },
    "ForeignNetRentRoyaltyIncomeAmt": {
        "line": "8",
        "description": "Rents and royalties",
        "type": "amount",
    },
    "ForeignNetGainLossAmt": {
        "line": "9",
        "description": "Gain or loss",
        "type": "amount",
    },
    "ForeignOtherIncomeAmt": {
        "line": "11",
        "description": "Other income",
        "type": "amount",
    },
    "ForeignTotalIncomeAmt": {
        "line": "12",
        "description": "Total income",
        "type": "amount",
    },
    "ForeignCompensationNotDeductedAmt": {
        "line": "13",
        "description": "Compensation not deducted",
        "type": "amount",
    },
    "ForeignInterestExpenseAmt": {
        "line": "16",
        "description": "Interest",
        "type": "amount",
    },
    "ForeignTaxesAmt": {
        "line": "17",
        "description": "Taxes (exclude income tax)",
        "type": "amount",
    },
    "ForeignDepreciationNotDeductedAmt": {
        "line": "18",
        "description": "Depreciation not deducted elsewhere",
        "type": "amount",
    },
    "ForeignOtherDeductionsAmt": {
        "line": "19",
        "description": "Other deductions",
        "type": "amount",
    },
    "ForeignTotalDeductionsAmt": {
        "line": "20",
        "description": "Total deductions",
        "type": "amount",
    },
    "ForeignCYNetIncomePerBookAmt": {
        "line": "21",
        "description": "Net income per books",
        "type": "amount",
    },
}

# Schedule F — Balance Sheet (Form 5471)
# Beginning of accounting period fields
SCHEDULE_F_BEGIN_FIELDS = {
    "BegngAcctPrdCashAmt": {
        "line": "1(a)",
        "description": "Cash",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdTradeNotesAmt": {
        "line": "2(a)",
        "description": "Trade notes & accounts receivable",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdInventoriesAmt": {
        "line": "3(a)",
        "description": "Inventories",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdInvstSubsidiaryAmt": {
        "line": "4(a)",
        "description": "Investment in subsidiaries",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdBldgAndOtherAstAmt": {
        "line": "5(a)",
        "description": "Buildings & other depreciable assets",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdLandAmt": {
        "line": "6(a)",
        "description": "Land",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdPatentsOthAstAmt": {
        "line": "7(a)",
        "description": "Intangible assets",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdOtherAssetsAmt": {
        "line": "8(a)",
        "description": "Other assets",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdTotalAssetsAmt": {
        "line": "9(a)",
        "description": "Total assets",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdAccountsPayableAmt": {
        "line": "10(a)",
        "description": "Accounts payable",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdOtherCurrLiabAmt": {
        "line": "11(a)",
        "description": "Other current liabilities",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdOthLiabilitiesAmt": {
        "line": "12(a)",
        "description": "Other liabilities",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdCommonStockAmt": {
        "line": "13(a)",
        "description": "Capital stock",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdPaidInOrSurplusAmt": {
        "line": "14(a)",
        "description": "Paid-in or capital surplus",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdRtnEarningsAmt": {
        "line": "15(a)",
        "description": "Retained earnings",
        "type": "amount",
        "period": "beginning",
    },
    "BegngAcctPrdTotLiabShrEqtyAmt": {
        "line": "16(a)",
        "description": "Total liabilities & shareholders equity",
        "type": "amount",
        "period": "beginning",
    },
}

# End of accounting period fields
SCHEDULE_F_END_FIELDS = {
    "EndAcctPrdCashAmt": {
        "line": "1(b)",
        "description": "Cash",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdTradeNotesAmt": {
        "line": "2(b)",
        "description": "Trade notes & accounts receivable",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdInventoriesAmt": {
        "line": "3(b)",
        "description": "Inventories",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdInvstSubsidiaryAmt": {
        "line": "4(b)",
        "description": "Investment in subsidiaries",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdBldgAndOtherAstAmt": {
        "line": "5(b)",
        "description": "Buildings & other depreciable assets",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdLandAmt": {
        "line": "6(b)",
        "description": "Land",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdPatentsOthAstAmt": {
        "line": "7(b)",
        "description": "Intangible assets",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdOtherAssetsAmt": {
        "line": "8(b)",
        "description": "Other assets",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdTotalAssetsAmt": {
        "line": "9(b)",
        "description": "Total assets",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdAccountsPayableAmt": {
        "line": "10(b)",
        "description": "Accounts payable",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdOtherCurrLiabAmt": {
        "line": "11(b)",
        "description": "Other current liabilities",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdOthLiabilitiesAmt": {
        "line": "12(b)",
        "description": "Other liabilities",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdCommonStockAmt": {
        "line": "13(b)",
        "description": "Capital stock",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdPaidInOrSurplusAmt": {
        "line": "14(b)",
        "description": "Paid-in or capital surplus",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdRtnEarningsAmt": {
        "line": "15(b)",
        "description": "Retained earnings",
        "type": "amount",
        "period": "end",
    },
    "EndAcctPrdTotLiabShrEqtyAmt": {
        "line": "16(b)",
        "description": "Total liabilities & shareholders equity",
        "type": "amount",
        "period": "end",
    },
}

# Combined Schedule F (both periods)
SCHEDULE_F_FIELDS = {**SCHEDULE_F_BEGIN_FIELDS, **SCHEDULE_F_END_FIELDS}

# Schedule E — Foreign Taxes (Form 5471)
SCHEDULE_E_FIELDS = {
    "TotalTaxInFunctionalCurAmt": {
        "line": "total(FC)",
        "description": "Total tax in functional currency",
        "type": "amount",
    },
    "TotalTaxInUSDollarsAmt": {
        "line": "total(USD)",
        "description": "Total tax in USD",
        "type": "amount",
    },
    "Frm5471SchETestedIncomeGrp_TotalTaxInUSDollarsAmt": {
        "line": "tested(USD)",
        "description": "Tested income tax (USD)",
        "type": "amount",
    },
    "Frm5471SchESubpartFIncomeGrp_TotalTaxInUSDollarsAmt": {
        "line": "subF(USD)",
        "description": "Subpart F income tax (USD)",
        "type": "amount",
    },
}

# Schedule G — Other Information (Form 5471)
SCHEDULE_G_FIELDS = {
    "DisallowedInterestExpenseInd": {
        "line": "15a",
        "description": "Disallowed interest expense (163(j))?",
        "type": "indicator",
    },
    "CfwdPrevDsallwIntExpenseAmt": {
        "line": "15b",
        "description": "163(j) carryforward amount",
        "type": "amount",
    },
    "BaseErosionPaymentBenefitInd": {
        "line": "6",
        "description": "Base erosion payments?",
        "type": "indicator",
    },
    "FDIIBenefitsClaimInd": {
        "line": "8",
        "description": "FDII benefits claimed?",
        "type": "indicator",
    },
    "PayOrAccrueTopUpTaxInd": {
        "line": "new",
        "description": "Pay or accrue top-up tax (Pillar Two)?",
        "type": "indicator",
    },
}

# Schedule J — Accumulated E&P (Form 5471)
# Each group has: BeginningYearBalanceAmt, current year columns, BalanceBeginningNextYearAmt
# Groups represent PTEP pools and total E&P categories
SCHEDULE_J_FIELDS = {
    # ── Post-2017 E&P Not Previously Taxed ──
    "Post2017EPNotPrevTaxedGrp_BeginningYearBalanceAmt": {
        "line": "1(i)",
        "description": "Post-2017 E&P not prev taxed — BOY",
        "type": "amount",
        "group": "Post2017EPNotPrevTaxed",
    },
    "Post2017EPNotPrevTaxedGrp_CurrentYearEPAmt": {
        "line": "1(ii)",
        "description": "Post-2017 E&P not prev taxed — CY E&P",
        "type": "amount",
        "group": "Post2017EPNotPrevTaxed",
    },
    "Post2017EPNotPrevTaxedGrp_BalanceBeginningNextYearAmt": {
        "line": "1(viii)",
        "description": "Post-2017 E&P not prev taxed — EOY",
        "type": "amount",
        "group": "Post2017EPNotPrevTaxed",
    },
    # ── Section 951A PTEP (GILTI inclusions) ──
    "Section951APTEPGrp_BeginningYearBalanceAmt": {
        "line": "2(i)",
        "description": "Section 951A PTEP (GILTI) — BOY",
        "type": "amount",
        "group": "Section951APTEP",
    },
    "Section951APTEPGrp_CurrentYearEPAmt": {
        "line": "2(ii)",
        "description": "Section 951A PTEP (GILTI) — CY E&P",
        "type": "amount",
        "group": "Section951APTEP",
    },
    "Section951APTEPGrp_ReclassifiedSect959c2Amt": {
        "line": "2(v)",
        "description": "Section 951A PTEP — Reclassified to 959(c)(2)",
        "type": "amount",
        "group": "Section951APTEP",
    },
    "Section951APTEPGrp_BalanceBeginningNextYearAmt": {
        "line": "2(viii)",
        "description": "Section 951A PTEP (GILTI) — EOY",
        "type": "amount",
        "group": "Section951APTEP",
    },
    # ── Section 245A(e)(2) PTEP ──
    "Section245Ae2PTEPGrp_BeginningYearBalanceAmt": {
        "line": "3(i)",
        "description": "Section 245A(e)(2) PTEP — BOY",
        "type": "amount",
        "group": "Section245Ae2PTEP",
    },
    "Section245Ae2PTEPGrp_BalanceBeginningNextYearAmt": {
        "line": "3(viii)",
        "description": "Section 245A(e)(2) PTEP — EOY",
        "type": "amount",
        "group": "Section245Ae2PTEP",
    },
    # ── Section 951(a)(1)(A) PTEP (Subpart F inclusions) ──
    "Section951a1APTEPGrp_BeginningYearBalanceAmt": {
        "line": "4(i)",
        "description": "Section 951(a)(1)(A) PTEP (Sub F) — BOY",
        "type": "amount",
        "group": "Section951a1APTEP",
    },
    "Section951a1APTEPGrp_CurrentYearEPAmt": {
        "line": "4(ii)",
        "description": "Section 951(a)(1)(A) PTEP (Sub F) — CY E&P",
        "type": "amount",
        "group": "Section951a1APTEP",
    },
    "Section951a1APTEPGrp_BalanceBeginningNextYearAmt": {
        "line": "4(viii)",
        "description": "Section 951(a)(1)(A) PTEP (Sub F) — EOY",
        "type": "amount",
        "group": "Section951a1APTEP",
    },
    # ── Section 965(a) PTEP ──
    "Section965aPTEPGrp_BeginningYearBalanceAmt": {
        "line": "5a(i)",
        "description": "Section 965(a) PTEP — BOY",
        "type": "amount",
        "group": "Section965aPTEP",
    },
    "Section965aPTEPGrp_BalanceBeginningNextYearAmt": {
        "line": "5a(viii)",
        "description": "Section 965(a) PTEP — EOY",
        "type": "amount",
        "group": "Section965aPTEP",
    },
    # ── Section 965(b) PTEP ──
    "Section965bPTEPGrp_BeginningYearBalanceAmt": {
        "line": "5b(i)",
        "description": "Section 965(b) PTEP — BOY",
        "type": "amount",
        "group": "Section965bPTEP",
    },
    "Section965bPTEPGrp_BalanceBeginningNextYearAmt": {
        "line": "5b(viii)",
        "description": "Section 965(b) PTEP — EOY",
        "type": "amount",
        "group": "Section965bPTEP",
    },
    # ── Total Section 964(a) E&P ──
    "TotalSection964AEPGrp_BeginningYearBalanceAmt": {
        "line": "6(i)",
        "description": "Total Section 964(a) E&P — BOY",
        "type": "amount",
        "group": "TotalSection964AEP",
    },
    "TotalSection964AEPGrp_CurrentYearEPAmt": {
        "line": "6(ii)",
        "description": "Total Section 964(a) E&P — CY E&P",
        "type": "amount",
        "group": "TotalSection964AEP",
    },
    "TotalSection964AEPGrp_BalanceBeginningNextYearAmt": {
        "line": "6(viii)",
        "description": "Total Section 964(a) E&P — EOY",
        "type": "amount",
        "group": "TotalSection964AEP",
    },
    # ── Post-1986 Undistributed Earnings ──
    "Post1986UndistributedEarnGrp_BeginningYearBalanceAmt": {
        "line": "7(i)",
        "description": "Post-1986 undistributed earnings — BOY",
        "type": "amount",
        "group": "Post1986UndistributedEarn",
    },
    "Post1986UndistributedEarnGrp_CurrentYearEPAmt": {
        "line": "7(ii)",
        "description": "Post-1986 undistributed earnings — CY E&P",
        "type": "amount",
        "group": "Post1986UndistributedEarn",
    },
    "Post1986UndistributedEarnGrp_BalanceBeginningNextYearAmt": {
        "line": "7(viii)",
        "description": "Post-1986 undistributed earnings — EOY",
        "type": "amount",
        "group": "Post1986UndistributedEarn",
    },
    # ── Pre-1987 E&P ──
    "Pre1987EPNotPrevTaxedGrp_BeginningYearBalanceAmt": {
        "line": "8(i)",
        "description": "Pre-1987 E&P not prev taxed — BOY",
        "type": "amount",
        "group": "Pre1987EPNotPrevTaxed",
    },
    "Pre1987EPNotPrevTaxedGrp_BalanceBeginningNextYearAmt": {
        "line": "8(viii)",
        "description": "Pre-1987 E&P not prev taxed — EOY",
        "type": "amount",
        "group": "Pre1987EPNotPrevTaxed",
    },
    # ── Hovering Deficit ──
    "HoveringDeficitDedSspndTaxGrp_BeginningYearBalanceAmt": {
        "line": "9(i)",
        "description": "Hovering deficit — BOY",
        "type": "amount",
        "group": "HoveringDeficit",
    },
    "HoveringDeficitDedSspndTaxGrp_BalanceBeginningNextYearAmt": {
        "line": "9(viii)",
        "description": "Hovering deficit — EOY",
        "type": "amount",
        "group": "HoveringDeficit",
    },
    # ── Separate Category Code ──
    "SeparateCategoryCd": {
        "line": "header",
        "description": "Separate category (basket)",
        "type": "text",
    },
}

# Schedule I — Summary of Shareholder's Income (Form 5471)
SCHEDULE_I_FIELDS = {
    "SubpartFPHCIncomeAmt": {
        "line": "1a",
        "description": "Subpart F — FPHCI",
        "type": "amount",
    },
    "OtherSubpartFNotIncludedAmt": {
        "line": "1f",
        "description": "Other Subpart F income",
        "type": "amount",
    },
}

# IRS5471 Main Form — Entity Information
FORM_5471_FIELDS = {
    "ForeignCorporation_BusinessName_BusinessNameLine1Txt": {
        "line": "1a",
        "description": "Name of foreign corporation",
        "type": "text",
    },
    "CountryUnderWhoseLawsIncCd": {
        "line": "1b",
        "description": "Country of incorporation",
        "type": "text",
    },
    "FunctionalCurrencyCd": {
        "line": "1c",
        "description": "Functional currency",
        "type": "text",
    },
    "EIN": {
        "line": "1d",
        "description": "EIN",
        "type": "text",
    },
    "ForeignEntityIdentificationGrp_ForeignEntityReferenceIdNum": {
        "line": "1d(ref)",
        "description": "Reference ID number",
        "type": "text",
    },
    "VotingStockOwnedPct": {
        "line": "3",
        "description": "Voting stock owned %",
        "type": "percentage",
    },
    "IncorporationDt": {
        "line": "2b",
        "description": "Date of incorporation",
        "type": "date",
    },
    "PrincipalPlaceOfBusCountryCd": {
        "line": "2a",
        "description": "Principal place of business",
        "type": "text",
    },
    "PrincipalBusinessActivityCd": {
        "line": "2c",
        "description": "Principal business activity code",
        "type": "text",
    },
    "PrincipalBusinessActivityDesc": {
        "line": "2c(desc)",
        "description": "Principal business activity",
        "type": "text",
    },
}

# All field maps indexed by form
FIELD_MAPS = {
    "IRS5471": FORM_5471_FIELDS,
    "IRS5471ScheduleC": SCHEDULE_C_FIELDS,
    "IRS5471ScheduleE": SCHEDULE_E_FIELDS,
    "IRS5471ScheduleF": SCHEDULE_F_FIELDS,
    "IRS5471ScheduleG": SCHEDULE_G_FIELDS,
    "IRS5471ScheduleH": SCHEDULE_H_FIELDS,
    "IRS5471ScheduleI": SCHEDULE_I_FIELDS,
    "IRS5471ScheduleI1": SCHEDULE_I1_FIELDS,
    "IRS5471ScheduleJ": SCHEDULE_J_FIELDS,
}

# Mapping of balance sheet lines for rollover checks (PY End -> CY Begin)
SCHEDULE_F_ROLLOVER_PAIRS = [
    ("EndAcctPrdCashAmt", "BegngAcctPrdCashAmt", "Cash"),
    ("EndAcctPrdTradeNotesAmt", "BegngAcctPrdTradeNotesAmt", "Trade notes & accounts receivable"),
    ("EndAcctPrdInventoriesAmt", "BegngAcctPrdInventoriesAmt", "Inventories"),
    ("EndAcctPrdInvstSubsidiaryAmt", "BegngAcctPrdInvstSubsidiaryAmt", "Investment in subsidiaries"),
    ("EndAcctPrdBldgAndOtherAstAmt", "BegngAcctPrdBldgAndOtherAstAmt", "Buildings & other depreciable assets"),
    ("EndAcctPrdLandAmt", "BegngAcctPrdLandAmt", "Land"),
    ("EndAcctPrdPatentsOthAstAmt", "BegngAcctPrdPatentsOthAstAmt", "Intangible assets"),
    ("EndAcctPrdOtherAssetsAmt", "BegngAcctPrdOtherAssetsAmt", "Other assets"),
    ("EndAcctPrdTotalAssetsAmt", "BegngAcctPrdTotalAssetsAmt", "Total assets"),
    ("EndAcctPrdAccountsPayableAmt", "BegngAcctPrdAccountsPayableAmt", "Accounts payable"),
    ("EndAcctPrdOtherCurrLiabAmt", "BegngAcctPrdOtherCurrLiabAmt", "Other current liabilities"),
    ("EndAcctPrdOthLiabilitiesAmt", "BegngAcctPrdOthLiabilitiesAmt", "Other liabilities"),
    ("EndAcctPrdCommonStockAmt", "BegngAcctPrdCommonStockAmt", "Capital stock"),
    ("EndAcctPrdPaidInOrSurplusAmt", "BegngAcctPrdPaidInOrSurplusAmt", "Paid-in or capital surplus"),
    ("EndAcctPrdRtnEarningsAmt", "BegngAcctPrdRtnEarningsAmt", "Retained earnings"),
    ("EndAcctPrdTotLiabShrEqtyAmt", "BegngAcctPrdTotLiabShrEqtyAmt", "Total liabilities & shareholders equity"),
]


def get_field_info(form_name: str, xml_field: str) -> dict:
    """Look up human-readable info for an XML field."""
    form_map = FIELD_MAPS.get(form_name, {})
    # Strip the form prefix from the field name
    short_field = xml_field.replace(f"{form_name}_", "")
    return form_map.get(short_field, {"line": "?", "description": short_field, "type": "unknown"})


def format_value(value: str, field_info: dict) -> str:
    """Format a value based on its type and sign convention."""
    if not value or value in ("", "nan", "None"):
        return "—"

    if field_info.get("type") == "amount":
        try:
            num = float(value)
            if field_info.get("sign") == "negative_is_income":
                num = -num  # flip to positive=income convention
            if abs(num) >= 1e6:
                return f"${num/1e6:,.2f}M"
            elif abs(num) >= 1000:
                return f"${num/1e3:,.1f}K"
            return f"${num:,.0f}"
        except ValueError:
            return value

    if field_info.get("type") == "indicator":
        if value in ("X", "1", "true", "True", "Y", "Yes"):
            return "Yes"
        elif value in ("", "0", "false", "False", "N", "No"):
            return "No"
        return value

    if field_info.get("type") == "percentage":
        try:
            return f"{float(value)*100:.2f}%"
        except ValueError:
            return value

    if field_info.get("type") == "rate":
        try:
            return f"{float(value):.7f}"
        except ValueError:
            return value

    return value

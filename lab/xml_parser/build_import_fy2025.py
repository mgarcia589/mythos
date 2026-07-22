"""
Build OIT Beginning Balance Import for FY2025.

Takes the OIT Post-86 E&P Ending Balances export (FY2024) and adjusts
the 2024 CY layer so that total per entity/basket/pool = XML FY24 ending balance.
This ensures Schedule J line 1a (Beginning Balance) in FY2025 matches exactly.
"""
import pandas as pd
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

# === CONFIG ===
BASE = r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Cerebro'
OIT_EXPORT = BASE + r'\sources\oit-post86-ep-ending-balances-fy2024.xlsx'
XML_FY24 = BASE + r'\sources\xml-parser\cb-fy24.xml'
NAME_MAP_SRC = BASE + r'\sources\oit-schj-report-fy2124.xlsx'
OUTPUT = BASE + r'\lab\xml_parser\output\oit-import-beg-bal-fy2025.xlsx'

# XML pool -> primary OIT adjustment column
XML_POOL_TO_ADJ_COL = {
    'Post2017EPNotPrevTaxedGrp': '959(c)(3) Foreign Source E&P (FC)',
    'Section951APTEPGrp': '959(c)(2) OWN GILTI E&P (FC)',
    'Section951a1APTEPGrp': '959(c)(2) OWN Subpart F E&P (FC)',
    'HoveringDeficitDedSspndTaxGrp': 'Hovering Deficit Adjustment',
}

# OIT columns that sum to each XML pool
OIT_COLS_PER_POOL = {
    'Post2017EPNotPrevTaxedGrp': [
        '959(c)(3) Foreign Source E&P (FC)',
        '959(c)(3) U.S. Source E&P (FC)',
    ],
    'Section951APTEPGrp': [
        '959(c)(2) OWN GILTI E&P (FC)',
        '959(c)(2) SUB GILTI E&P (FC)',
    ],
    'Section951a1APTEPGrp': [
        '959(c)(2) OWN Subpart F E&P (FC)',
        '959(c)(2) SUB Subpart F E&P (FC)',
        '959(c)(1)(A) OWN Subpart F E&P (FC)',
        '959(c)(1)(A) SUB Subpart F E&P (FC)',
    ],
    'HoveringDeficitDedSspndTaxGrp': [
        'Hovering Deficit Adjustment',
    ],
}

# === 1. LOAD OIT EXPORT ===
print("Loading OIT export...")
oit = pd.read_excel(OIT_EXPORT, sheet_name='Post86_EP_TaxesEndingBalances', header=6)
oit = oit[oit['Entity Number'].notna() & oit['Entity Number'].str.match(r'^[A-Z]', na=False)].copy()
oit = oit.reset_index(drop=True)
numeric_cols = list(oit.columns[11:])
for col in numeric_cols:
    oit[col] = pd.to_numeric(oit[col], errors='coerce').fillna(0)

print(f"  Rows: {len(oit)}, Entities: {oit['Entity Number'].nunique()}")

# === 2. PARSE XML FY24 ENDING BALANCES ===
print("Parsing XML FY24...")
ns = 'http://www.irs.gov/efile'
tree = ET.parse(XML_FY24)
root = tree.getroot()

xml_targets = {}
for schj in root.iter(f'{{{ns}}}IRS5471ScheduleJ'):
    fcn = schj.find(f'{{{ns}}}ForeignCorporationName')
    if fcn is None:
        continue
    name_el = fcn.find(f'{{{ns}}}BusinessNameLine1Txt')
    name = name_el.text.strip().upper() if name_el is not None else 'UNKNOWN'
    sep_cat = schj.find(f'{{{ns}}}SeparateCategoryCd')
    basket = sep_cat.text.strip() if sep_cat is not None else 'GEN'
    if basket == 'TOTAL':
        continue
    basket_key = '21-General Limitation Income' if basket == 'GEN' else '3-Passive Income'
    key = (name, basket_key)
    if key not in xml_targets:
        xml_targets[key] = {}
    for pool in XML_POOL_TO_ADJ_COL.keys():
        pool_el = schj.find(f'{{{ns}}}{pool}')
        if pool_el is not None:
            end_el = pool_el.find(f'{{{ns}}}BalanceBeginningNextYearAmt')
            if end_el is not None and end_el.text:
                xml_targets[key][pool] = float(end_el.text)

print(f"  XML targets: {len(xml_targets)} entity-basket pairs")

# === 3. NAME MAPPING ===
print("Building name map...")
df_map = pd.read_excel(NAME_MAP_SRC, sheet_name='Table1', header=0)
code_to_name = {
    str(row['Company Number']).strip(): str(row['Entity Name']).strip().upper()
    for _, row in df_map.drop_duplicates('Company Number').iterrows()
}

xml_names = set(k[0] for k in xml_targets.keys())
name_to_xml = {}
for code, oit_name in code_to_name.items():
    if oit_name in xml_names:
        name_to_xml[oit_name] = oit_name
    else:
        nc = oit_name.split('(FKA')[0].strip().rstrip('.')
        best_s, best_n = 0, None
        for xn in xml_names:
            xc = xn.split('(FKA')[0].strip().rstrip('.')
            s = SequenceMatcher(None, nc, xc).ratio()
            if s > best_s:
                best_s, best_n = s, xn
        if best_s > 0.85:
            name_to_xml[oit_name] = best_n

print(f"  Matched: {len(name_to_xml)} entities")

# === 4. APPLY ADJUSTMENTS TO 2024 LAYER ===
print("Applying adjustments...")
import_df = oit.copy()
adj_log = []

for code in import_df['Entity Number'].unique():
    oit_name = code_to_name.get(code, code)
    xml_name = name_to_xml.get(oit_name)
    if xml_name is None:
        continue

    # Check ALL baskets that have XML targets for this entity
    entity_baskets = set(import_df[import_df['Entity Number'] == code]['Basket Name'].unique())
    xml_baskets = [k[1] for k in xml_targets.keys() if k[0] == xml_name]
    all_baskets = entity_baskets | set(xml_baskets)

    for basket in all_baskets:
        key = (xml_name, basket)
        targets = xml_targets.get(key, {})
        if not targets:
            continue

        # Find 2024 EarningsProfitTaxes row — create if missing
        ep2024_mask = (
            (import_df['Entity Number'] == code) &
            (import_df['Basket Name'] == basket) &
            (import_df['Tax Year'] == 2024) &
            (import_df['Activity Type'] == 'EarningsProfitTaxes')
        )
        ep2024_idx = import_df[ep2024_mask].index.tolist()
        if not ep2024_idx:
            # Create a new 2024 EP row
            existing = import_df[
                (import_df['Entity Number'] == code) & (import_df['Basket Name'] == basket)
            ]
            if len(existing) > 0:
                template_row = existing.iloc[-1].copy()
            else:
                # No rows in this basket at all — use any row from this entity
                template_row = import_df[import_df['Entity Number'] == code].iloc[-1].copy()
                template_row['Basket Name'] = basket
                basket_num = '21' if 'General' in basket else '3'
                template_row['Basket Number'] = basket_num
            template_row['Tax Year'] = 2024
            template_row['Made in Tax Year'] = 2024
            template_row['Activity Type'] = 'EarningsProfitTaxes'
            template_row['Tax Year Begin'] = '01/01/2024'
            template_row['Tax Year End'] = '12/31/2024'
            template_row['Made in Year Begin'] = '01/01/2024'
            template_row['Made in Year End'] = '12/31/2024'
            template_row['Adjustment Description'] = ''
            template_row['Adjustment Made in Current Year'] = 0
            for col in numeric_cols:
                template_row[col] = 0
            import_df = pd.concat([import_df, template_row.to_frame().T], ignore_index=True)
            ep2024_i = import_df.index[-1]
        else:
            ep2024_i = ep2024_idx[0]

        # All rows for this entity/basket
        eb_mask = (import_df['Entity Number'] == code) & (import_df['Basket Name'] == basket)

        for pool, target_val in targets.items():
            oit_cols = OIT_COLS_PER_POOL.get(pool, [])
            if not oit_cols:
                continue

            current_total = sum(
                import_df.loc[eb_mask, c].sum()
                for c in oit_cols if c in import_df.columns
            )
            delta = target_val - current_total
            if abs(delta) < 0.5:
                continue

            adj_col = XML_POOL_TO_ADJ_COL[pool]
            if adj_col not in import_df.columns:
                continue

            old_val = import_df.at[ep2024_i, adj_col]
            new_val = old_val + delta
            import_df.at[ep2024_i, adj_col] = new_val

            adj_log.append({
                'Entity Code': code,
                'Entity Name': oit_name,
                'Basket': basket,
                'XML Pool': pool,
                'Column Adjusted': adj_col,
                'Old Value': old_val,
                'Delta': delta,
                'New Value': new_val,
                'XML Target': target_val,
            })

print(f"  Adjustments: {len(adj_log)}")
print(f"  Entities affected: {len(set(a['Entity Code'] for a in adj_log))}")

# === 5. VERIFY ===
print("Verifying...")
verify_ok = 0
verify_total = 0
verify_fails = []

for code in import_df['Entity Number'].unique():
    oit_name = code_to_name.get(code, code)
    xml_name = name_to_xml.get(oit_name)
    if xml_name is None:
        continue
    for basket in import_df[import_df['Entity Number'] == code]['Basket Name'].unique():
        key = (xml_name, basket)
        targets = xml_targets.get(key, {})
        eb_rows = import_df[(import_df['Entity Number'] == code) & (import_df['Basket Name'] == basket)]
        for pool, target_val in targets.items():
            oit_cols = OIT_COLS_PER_POOL.get(pool, [])
            if not oit_cols:
                continue
            new_total = sum(eb_rows[c].sum() for c in oit_cols if c in eb_rows.columns)
            verify_total += 1
            if abs(new_total - target_val) < 1:
                verify_ok += 1
            else:
                verify_fails.append(f"  {code} {pool}: got {new_total:,.0f}, want {target_val:,.0f}")

print(f"  PASS: {verify_ok}/{verify_total} ({verify_ok/verify_total*100:.0f}%)")
if verify_fails:
    print(f"  FAILS ({len(verify_fails)}):")
    for f in verify_fails[:10]:
        print(f)

# === 6. WRITE OUTPUT ===
print(f"Writing {OUTPUT}...")
with pd.ExcelWriter(OUTPUT, engine='openpyxl') as writer:
    import_df.to_excel(writer, sheet_name='Post86_EP_Import', index=False)
    pd.DataFrame(adj_log).to_excel(writer, sheet_name='Adjustments', index=False)

print(f"\nDONE. Import file ready: {OUTPUT}")
print(f"  {len(import_df)} rows, {import_df['Entity Number'].nunique()} entities")
print(f"  Load via: Batch > Batch Process > Import > Intl > Beg. E&P - Post-86")

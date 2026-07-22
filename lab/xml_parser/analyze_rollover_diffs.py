"""Analyze Schedule J rollover differences by category."""
import pandas as pd
import sys
sys.path.insert(0, r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Cerebro')
from lab.xml_parser.parser import EFileParser

BASE = r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Cerebro'
fy24 = EFileParser(BASE + r'\sources\xml-parser\cb-fy24.xml')
fy25 = EFileParser(BASE + r'\sources\xml-parser\cb-fy25-v2.xml')

df24 = fy24.extract_form('IRS5471ScheduleJ')
df25 = fy25.extract_form('IRS5471ScheduleJ')

POOLS = {
    'Post2017EPNotPrevTaxedGrp': '(a) Post-2017 Untaxed',
    'Section951APTEPGrp': '(c) 951A PTEP (GILTI)',
    'Section951a1APTEPGrp': '(e) 951(a)(1)(A) PTEP (SubF)',
    'Post1986UndistributedEarnGrp': '(i) Post-86 Undistributed',
    'HoveringDeficitDedSspndTaxGrp': '(j) Hovering Deficit',
}

results = []
for _, row24 in df24.iterrows():
    ref_id = row24.get('_reference_id', '')
    entity = row24.get('_entity_name', '')
    basket = row24.get('_basket', '')
    if basket == 'TOTAL':
        continue
    match = df25[(df25['_reference_id'] == ref_id) & (df25['_basket'] == basket)]
    if match.empty:
        continue
    row25 = match.iloc[0]
    for grp, desc in POOLS.items():
        py_col = 'IRS5471ScheduleJ_' + grp + '_BalanceBeginningNextYearAmt'
        cy_col = 'IRS5471ScheduleJ_' + grp + '_BeginningYearBalanceAmt'
        py_val = pd.to_numeric(row24.get(py_col, None), errors='coerce')
        cy_val = pd.to_numeric(row25.get(cy_col, None), errors='coerce')
        py_val = 0.0 if pd.isna(py_val) else float(py_val)
        cy_val = 0.0 if pd.isna(cy_val) else float(cy_val)
        diff = cy_val - py_val
        if abs(diff) >= 10:
            results.append({
                'entity': entity[:35],
                'ref_id': ref_id,
                'basket': basket,
                'pool': desc,
                'pool_grp': grp,
                'py_ending': py_val,
                'cy_beginning': cy_val,
                'diff': diff,
            })

df = pd.DataFrame(results)
print("Total differences (excl Total pool): %d" % len(df))
print("Entities with diffs: %d" % df['ref_id'].nunique())
print()

# Categorize
new_ptep = df[(df['pool'].str.contains('951')) & (df['py_ending'] == 0)]
pool_a_diffs = df[df['pool'] == '(a) Post-2017 Untaxed']
pool_i_diffs = df[df['pool'] == '(i) Post-86 Undistributed']

print('=== CATEGORY 1: New PTEP (PY ending=0, appeared in CY beginning) ===')
print("Count: %d entries in %d entities" % (len(new_ptep), new_ptep['ref_id'].nunique()))
print("Total amount: $%s" % '{:,.0f}'.format(new_ptep['diff'].sum()))
print()
for _, r in new_ptep.sort_values('diff', ascending=False).iterrows():
    print("  %-8s %-30s %-4s %-28s CY beg: %15s" % (
        r['ref_id'], r['entity'][:30], r['basket'], r['pool'],
        '{:,.0f}'.format(r['cy_beginning'])))
print()

print('=== CATEGORY 2: Pool (a) Post-2017 Untaxed changes ===')
print("Count: %d entries in %d entities" % (len(pool_a_diffs), pool_a_diffs['ref_id'].nunique()))
print()
for _, r in pool_a_diffs.sort_values('diff', key=abs, ascending=False).iterrows():
    print("  %-8s %-25s %-4s PY: %15s  CY: %15s  Diff: %12s" % (
        r['ref_id'], r['entity'][:25], r['basket'],
        '{:,.0f}'.format(r['py_ending']),
        '{:,.0f}'.format(r['cy_beginning']),
        '{:,.0f}'.format(r['diff'])))
print()

print('=== CATEGORY 3: Pool (i) Post-86 Undistributed ===')
if len(pool_i_diffs) > 0:
    for _, r in pool_i_diffs.iterrows():
        print("  %-8s %-25s %-4s PY: %15s  CY: %15s  Diff: %12s" % (
            r['ref_id'], r['entity'][:25], r['basket'],
            '{:,.0f}'.format(r['py_ending']),
            '{:,.0f}'.format(r['cy_beginning']),
            '{:,.0f}'.format(r['diff'])))
else:
    print("  None")
print()

print('=== CROSS-CHECK: Does Pool(a) decrease = PTEP increase? ===')
print("If net=0, OIT is reclassing CY inclusion into beginning balance (WRONG)")
print("If net!=0, there's a genuine rollover gap")
print()
for ref_id in pool_a_diffs['ref_id'].unique():
    a_diff = pool_a_diffs[pool_a_diffs['ref_id'] == ref_id]['diff'].sum()
    c_rows = new_ptep[(new_ptep['ref_id'] == ref_id) & (new_ptep['pool'].str.contains('GILTI'))]
    c_diff = c_rows['diff'].sum() if not c_rows.empty else 0
    e_rows = new_ptep[(new_ptep['ref_id'] == ref_id) & (new_ptep['pool'].str.contains('SubF'))]
    e_diff = e_rows['diff'].sum() if not e_rows.empty else 0
    net = a_diff + c_diff + e_diff
    entity = pool_a_diffs[pool_a_diffs['ref_id'] == ref_id].iloc[0]['entity']
    print("  %-8s %-25s Pool(a): %12s  PTEP(c): %12s  PTEP(e): %12s  Net: %12s  %s" % (
        ref_id, entity[:25],
        '{:,.0f}'.format(a_diff),
        '{:,.0f}'.format(c_diff),
        '{:,.0f}'.format(e_diff),
        '{:,.0f}'.format(net),
        "OK-reclass" if abs(net) < 100 else "GAP"))

print()
print("=== ENTITIES WITH GENUINE GAPS (net != 0 after removing PTEP reclass) ===")
gaps = []
for ref_id in df['ref_id'].unique():
    entity_diffs = df[df['ref_id'] == ref_id]
    # Sum all non-derived pool diffs
    a_diff = entity_diffs[entity_diffs['pool'] == '(a) Post-2017 Untaxed']['diff'].sum()
    c_diff = entity_diffs[entity_diffs['pool'] == '(c) 951A PTEP (GILTI)']['diff'].sum()
    e_diff = entity_diffs[entity_diffs['pool'] == '(e) 951(a)(1)(A) PTEP (SubF)']['diff'].sum()
    i_diff = entity_diffs[entity_diffs['pool'] == '(i) Post-86 Undistributed']['diff'].sum()
    j_diff = entity_diffs[entity_diffs['pool'] == '(j) Hovering Deficit']['diff'].sum()
    # Pool (a) + (c) + (e) should net to 0 if it's just PTEP reclass
    reclass_net = a_diff + c_diff + e_diff
    entity = entity_diffs.iloc[0]['entity']
    if abs(reclass_net) >= 100 or abs(i_diff) >= 10 or abs(j_diff) >= 10:
        gaps.append({
            'ref_id': ref_id,
            'entity': entity,
            'pool_a': a_diff,
            'ptep_c': c_diff,
            'ptep_e': e_diff,
            'net_reclass': reclass_net,
            'pool_i': i_diff,
            'pool_j': j_diff,
        })
        print("  %-8s %-25s  a:%12s c:%12s e:%12s net:%12s  i:%12s j:%12s" % (
            ref_id, entity[:25],
            '{:,.0f}'.format(a_diff),
            '{:,.0f}'.format(c_diff),
            '{:,.0f}'.format(e_diff),
            '{:,.0f}'.format(reclass_net),
            '{:,.0f}'.format(i_diff),
            '{:,.0f}'.format(j_diff)))

if not gaps:
    print("  NONE - all differences are explained by CY PTEP reclassification")

print()
print("SUMMARY:")
print("  Total diffs: %d (in %d entities)" % (len(df), df['ref_id'].nunique()))
ptep_only = df['ref_id'].nunique() - len(gaps)
print("  Explained by PTEP reclass: %d entities" % ptep_only)
print("  Genuine gaps: %d entities" % len(gaps))

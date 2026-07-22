"""Compare E&P (workbook) to Schedule J Line 3 (XML) to trace the flow.

Key finding: OIT Schedule J Line 3 in this XML = -(Current E&P in FC)
NOT in USD. The USD conversion happens later when FX rates are loaded.
"""
import sys, pandas as pd
from pathlib import Path
sys.path.insert(0, r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Cerebro')
from lab.xml_parser.parser import EFileParser

# XML Line 3 (TOTAL basket) - sign convention: negative = positive E&P
parser = EFileParser(r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Cerebro\sources\xml-parser\cb-fy25-v3.xml')
dfj = parser.extract_form('IRS5471ScheduleJ')
line3_col = 'IRS5471ScheduleJ_Post2017EPNotPrevTaxedGrp_CurrentYearEPDeficitAmt'

xml_line3 = {}
for _, row in dfj[dfj['_basket'] == 'TOTAL'].iterrows():
    ref = row.get('_reference_id', '')
    val = pd.to_numeric(row.get(line3_col, None), errors='coerce')
    if pd.notna(val):
        xml_line3[ref] = float(val)

# Workbook E&P in FC (Col M) and USD (Col N)
path = list(Path(r'C:\Users\mgarcia241\OneDrive - PwC\Desktop\Ingest').glob('2025 5471*'))[0]
df_adj = pd.read_excel(path, sheet_name='FY25 E&P Adjs Summary', header=None, engine='calamine')

wb_ep_fc = {}
wb_ep_usd = {}
wb_fc = {}
for i in range(5, len(df_adj)):
    code = df_adj.iloc[i, 0]
    if pd.notna(code) and (str(code).strip().startswith('C') or str(code).strip().startswith('SS')):
        code = str(code).strip()
        m_val = pd.to_numeric(df_adj.iloc[i, 12], errors='coerce')
        n_val = pd.to_numeric(df_adj.iloc[i, 13], errors='coerce')
        fc = str(df_adj.iloc[i, 3]).strip() if pd.notna(df_adj.iloc[i, 3]) else ''
        if pd.notna(m_val):
            wb_ep_fc[code] = float(m_val)
        if pd.notna(n_val):
            wb_ep_usd[code] = float(n_val)
        wb_fc[code] = fc

# Compare: XML Line 3 should = -(WB E&P FC)
all_codes = sorted(set(xml_line3.keys()) & set(wb_ep_fc.keys()))
print('E&P to Schedule J Line 3 Comparison')
print('XML v3 (post-TB import) vs Workbook E&P Adjustments Summary')
print('Hypothesis: XML Line 3 = -(Current E&P in FC)')
print()
print('%-8s %-25s %-4s %16s %16s %12s' % ('Code', 'Entity', 'FC', 'XML Line3', 'WB EP(FC)', 'Diff'))
print('-' * 85)
diffs = []
matches = 0
for code in all_codes:
    xml_v = xml_line3[code]
    wb_fc_v = wb_ep_fc[code]
    fc = wb_fc.get(code, 'USD')
    # XML should = -(WB EP FC) if our hypothesis is correct
    expected_xml = -wb_fc_v
    diff = xml_v - expected_xml
    ent_name = ''
    for _, row in dfj[dfj['_reference_id'] == code].iterrows():
        ent_name = str(row.get('_entity_name', ''))[:25]
        break
    status = 'OK' if abs(diff) < 500 else '{:,.0f}'.format(diff)
    if abs(diff) < 500:
        matches += 1
    else:
        diffs.append((code, ent_name, fc, diff, xml_v, wb_fc_v))
    print('%-8s %-25s %-4s %16s %16s %12s' % (
        code, ent_name, fc,
        '{:,.0f}'.format(xml_v),
        '{:,.0f}'.format(wb_fc_v),
        status))

print()
print('Results: %d match (<500 diff), %d with differences' % (matches, len(diffs)))
if diffs:
    print()
    print('Entities with differences (Line 3 != -(EP FC)):')
    for code, name, fc, d, xml_v, wb_v in sorted(diffs, key=lambda x: abs(x[3]), reverse=True):
        print('  %-8s %-25s %-4s XML: %16s  WB_FC: %16s  Diff: %12s' % (
            code, name, fc, '{:,.0f}'.format(xml_v), '{:,.0f}'.format(wb_v), '{:,.0f}'.format(d)))

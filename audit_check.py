#!/usr/bin/env python
"""Data integrity audit for Crypto Cycle Correlation Framework."""
import csv
import re
from datetime import datetime

today = datetime(2026, 8, 6)
min_date = datetime(2010, 7, 17)
findings = []

def F(severity, file, loc, observed, expected, note=""):
    findings.append((severity, file, loc, observed, expected, note))

# ============================================================
# 1. btc_cycle_metrics: date integrity, drawdown, mult
# ============================================================
with open('data/processed/btc_cycle_metrics.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cid = row['cycle_id']
        halv = datetime.strptime(row['halving_date'], '%Y-%m-%d')
        pre_b = row.get('pre_halving_bottom_date', '')
        top_d = row.get('final_top_date', '')
        next_b = row.get('next_bear_bottom_date', '')

        if pre_b:
            pre_b_d = datetime.strptime(pre_b, '%Y-%m-%d')
            if pre_b_d >= halv:
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/pre_halving_bottom_date',
                  pre_b, row['halving_date'], 'bottom >= halving')
        if top_d:
            top_dt = datetime.strptime(top_d, '%Y-%m-%d')
            if top_dt <= halv:
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/final_top_date',
                  top_d, row['halving_date'], 'top <= halving')
            if top_dt > today:
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/final_top_date',
                  top_d, 'today', 'top in future')
        if next_b and top_d:
            next_b_d = datetime.strptime(next_b, '%Y-%m-%d')
            top_dt = datetime.strptime(top_d, '%Y-%m-%d')
            if next_b_d <= top_dt:
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/next_bear_bottom_date',
                  next_b, top_d, 'bottom <= top')
        dd = row.get('drawdown_pct', '')
        if dd:
            ddf = float(dd)
            if not (0 <= ddf <= 1):
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/drawdown_pct', ddf, '[0,1]')
        mult = row.get('mult_bottom_to_top', '')
        if mult:
            mf = float(mult)
            if mf < 1:
                F('CRITICAL', 'btc_cycle_metrics', f'{cid}/mult_bottom_to_top', mf, '>1')

# ============================================================
# 2. events.csv: date integrity
# ============================================================
halvings = {}
events_prices = {}
with open('data/events.csv') as f:
    for row in csv.DictReader(f):
        et = row['event_type']
        label = row['label']
        date_str = row['date']
        if not date_str:
            continue
        d = datetime.strptime(date_str, '%Y-%m-%d')
        if d > today:
            F('CRITICAL', 'events', f'{et}/{label}/date', date_str, 'today')
        if et == 'halving':
            halvings[label] = d
        if et == 'top' and label in halvings:
            if d <= halvings[label]:
                F('CRITICAL', 'events', f'{et}/{label}/date',
                  date_str, halvings[label].strftime('%Y-%m-%d'), 'top <= halving')
        if row['price_usd']:
            events_prices[f'{et}_{label}'] = float(row['price_usd'])

# ============================================================
# 3. btc_cycle_metrics vs events.csv price/date consistency
# ============================================================
with open('data/processed/btc_cycle_metrics.csv') as f:
    for row in csv.DictReader(f):
        cid = row['cycle_id']
        num = int(cid[1])
        bp_key = f'bottom_B{num-1}'
        if bp_key in events_prices:
            m = float(row['pre_halving_bottom_price'])
            e = events_prices[bp_key]
            if abs(m - e) > 0.01:
                F('HIGH', 'btc_cycle_metrics', f'{cid}/pre_halving_bottom_price',
                  m, e, 'mismatch vs events.csv')
        tp_key = f'top_{cid}'
        if tp_key in events_prices:
            m = float(row['final_top_price'])
            e = events_prices[tp_key]
            if abs(m - e) > 1:
                F('HIGH', 'btc_cycle_metrics', f'{cid}/final_top_price',
                  m, e, 'mismatch vs events.csv (source: bitstamp_raw vs coingecko)')
        # top date
        top_d = row.get('final_top_date', '')
        if cid == 'C2' and top_d == '2017-12-16':
            F('HIGH', 'btc_cycle_metrics', f'{cid}/final_top_date', top_d,
              '2017-12-17 (events.csv)', '1-day gap; Rule T vs CoinGecko')
        if cid == 'C3' and top_d == '2021-11-08':
            F('HIGH', 'btc_cycle_metrics', f'{cid}/final_top_date', top_d,
              '2021-11-10 (events.csv)', '2-day gap; Rule T vs CoinGecko')

# ============================================================
# 4. forward_ranges: LOOCO spot-check
# ============================================================
with open('data/processed/forward_ranges.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        stat = row['statistic']
        n = int(row['n'])
        mean = float(row['mean'])
        mn, mx = float(row['min']), float(row['max'])
        if not (mn <= mean <= mx):
            F('CRITICAL', 'forward_ranges', f'{stat}/mean', mean, f'[{mn},{mx}]')
        med = float(row['median'])
        if not (mn <= med <= mx):
            F('CRITICAL', 'forward_ranges', f'{stat}/median', med, f'[{mn},{mx}]')

# Spot-check D_halving_to_top LOOCO (n=4: C1=371, C2=525, C3=546, C4=534)
btc_vals = [371.0, 525.0, 546.0, 534.0]  # from btc_cycle_metrics
expected_looco = {}
for i, label in enumerate(['C1', 'C2', 'C3', 'C4']):
    remaining = [v for j, v in enumerate(btc_vals) if j != i]
    expected_looco[f'looco_{label}_mean'] = sum(remaining) / len(remaining)

with open('data/processed/forward_ranges.csv') as f:
    for row in csv.DictReader(f):
        if row['statistic'] == 'D_halving_to_top':
            for k, exp_val in expected_looco.items():
                actual = float(row[k])
                if abs(actual - exp_val) > 0.01:
                    F('CRITICAL', 'forward_ranges', f'D_halving_to_top/{k}',
                      actual, exp_val, 'LOOCO mismatch')

# Spot-check D_top_to_next_bottom LOOCO (n=3: C1=406, C2=364, C3=378)
# (C4 incomplete, n=3)
btt_vals = [406.0, 364.0, 378.0]
# But the file has n=3 and still has looco_C4 columns? Let's check
with open('data/processed/forward_ranges.csv') as f:
    for row in csv.DictReader(f):
        if row['statistic'] == 'D_top_to_next_bottom':
            n_actual = int(row['n'])
            # LOOCO only for n>=3
            if n_actual >= 3:
                for i, label in enumerate(['C1', 'C2', 'C3']):
                    remaining = [v for j, v in enumerate(btt_vals) if j != i]
                    exp = sum(remaining) / len(remaining)
                    col = f'looco_{label}_mean'
                    actual_s = row.get(col, '')
                    if actual_s:
                        actual = float(actual_s)
                        if abs(actual - exp) > 0.01:
                            F('CRITICAL', 'forward_ranges', f'D_top_to_next_bottom/{col}',
                              actual, exp, 'LOOCO mismatch')
            # looco_C4 should be empty (only 3 cycles)
            c4 = row.get('looco_C4_mean', '')
            if c4:
                F('MEDIUM', 'forward_ranges', 'D_top_to_next_bottom/looco_C4_mean',
                  c4, 'empty', 'C4 not yet complete, LOOCO_C4 should be blank')

# ============================================================
# 5. next_cycle_zones: B4 in band, zone ordering
# ============================================================
with open('data/processed/next_cycle_zones.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        zone = row['zone']
        pl_s, ph_s = row['price_low'], row['price_high']
        if not pl_s or not ph_s or pl_s == '' or ph_s == '':
            continue  # price-free zone (accumulation)
        pl, ph = float(pl_s), float(ph_s)
        if pl > 0 and ph > 0 and pl > ph:
            F('CRITICAL', 'next_cycle_zones', f'{zone}/price', f'{pl}>{ph}', 'low<high')
        if zone == 'bear_bottom':
            b4 = float(row['anchor_price'])
            if not (pl <= b4 <= ph):
                F('CRITICAL', 'next_cycle_zones', f'{zone}/B4_in_band',
                  b4, f'[{pl},{ph}]', 'B4 outside band')
        # accumulation zones have no price (price-free)

# ============================================================
# 6. alt_next_cycle_zones: zone ordering, cross-check
# ============================================================
with open('data/processed/alt_next_cycle_zones.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        a, z = row['asset'], row['zone']
        pl_s, ph_s = row.get('price_low', ''), row.get('price_high', '')
        if pl_s and ph_s and pl_s != '' and ph_s != '':
            try:
                pl_f, ph_f = float(pl_s), float(ph_s)
                if pl_f > ph_f:
                    F('CRITICAL', 'alt_next_cycle_zones', f'{a}/{z}/price',
                      f'{pl_f}>{ph_f}', 'low<high')
            except ValueError:
                pass
        cc = row.get('cross_check_ok', '')
        if cc == 'False':
            F('HIGH', 'alt_next_cycle_zones', f'{a}/{z}/cross_check', 'False', 'True')

# ============================================================
# 7. BTC 2-stage projection values
# ============================================================
with open('data/processed/next_cycle_zones.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['zone'] == 'bear_bottom':
            b4 = float(row['anchor_price'])
            if abs(b4 - 43081) > 1:
                F('CRITICAL', 'next_cycle_zones', 'bear_bottom/B4',
                  b4, 43081, 'AGENTS.md says B4=$43,081')
            pl, ph = float(row['price_low']), float(row['price_high'])
            if abs(pl - 29596) > 1 or abs(ph - 53673) > 1:
                F('CRITICAL', 'next_cycle_zones', 'bear_bottom/band',
                  f'[{pl},{ph}]', '[29596,53673]', 'AGENTS.md band mismatch')
        if row['zone'] == 'distribution':
            note = row['compression_fit_note']
            m = re.search(r'rel_diff=([+-]?[\d.]+)%', note)
            if m:
                rd = float(m.group(1))
                if abs(rd - 45.6) > 0.1:
                    F('CRITICAL', 'next_cycle_zones', 'distribution/cross_check_rel_diff',
                      rd, 45.6, 'AGENTS.md says FAIL @ +45.6%')

# ============================================================
# 8. Gold support band
# ============================================================
with open('data/processed/alt_next_cycle_zones.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['asset'] == 'gold' and row['zone'] == 'bear_bottom':
            sbl = row.get('support_band_low', '')
            sbh = row.get('support_band_high', '')
            if sbl and sbh:
                sbl_f, sbh_f = float(sbl), float(sbh)
                pl, ph = float(row['price_low']), float(row['price_high'])
                if ph < sbl_f:
                    F('HIGH', 'alt_next_cycle_zones', 'gold/bear_bottom/B4_below_support',
                      f'B4 high {ph}', f'support low {sbl_f}',
                      'B4 projects below bull-support band')

# ============================================================
# 9. Gold C1 multiplier < 1
# ============================================================
with open('data/processed/alt_cycle_metrics.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['asset'] == 'gold' and row['cycle_id'] == 'C1':
            mult = float(row['mult_asset_bottom_to_top'])
            if mult < 1:
                F('HIGH', 'alt_cycle_metrics', 'gold/C1/mult',
                  mult, '>1', 'Gold C1 top < bottom (bear-market for gold)')

# ============================================================
# 10. Correlation range [-1,1]
# ============================================================
with open('data/processed/correlations_phase.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        p = float(row['pearson'])
        s = float(row['spearman'])
        if not (-1 <= p <= 1):
            F('CRITICAL', 'correlations_phase',
              f'{row["phase"]}/{row["asset"]}/pearson', p, '[-1,1]')
        if not (-1 <= s <= 1):
            F('CRITICAL', 'correlations_phase',
              f'{row["phase"]}/{row["asset"]}/spearman', s, '[-1,1]')

with open('data/processed/correlations_rolling.csv') as f:
    reader = csv.DictReader(f)
    n_out = 0
    n_tot = 0
    for row in reader:
        r = float(row['rolling_r_90d'])
        n_tot += 1
        if not (-1 <= r <= 1):
            n_out += 1
    if n_out:
        F('CRITICAL', 'correlations_rolling', 'range_check',
          f'{n_out}/{n_tot}', '0', 'values outside [-1,1]')

# ============================================================
# 11. DESIGN.md missing columns
# ============================================================
with open('data/processed/btc_cycle_metrics.csv') as f:
    headers = set(f.readline().strip().split(','))
design_promised = {'D_halving_to_next_bottom', 'mult_top_to_bottom'}
missing = design_promised - headers
if missing:
    F('MEDIUM', 'btc_cycle_metrics', 'schema', str(missing),
      'columns promised by DESIGN.md 5.1', 'not in CSV header')

# ============================================================
# 12. Backtest predicted_in_outer consistency
# ============================================================
with open('data/processed/backtest_by_cycle.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        pm = float(row['predicted_mean'])
        omin = float(row['outer_range_min'])
        omax = float(row['outer_range_max'])
        flag = row['predicted_in_outer_mean']
        actual = omin <= pm <= omax
        if (flag == 'True') != actual:
            F('CRITICAL', 'backtest',
              f'{row["statistic"]}/{row["leave_out_cycle"]}',
              f'flag={flag}', f'actual={actual}',
              f'pred_mean={pm}, range=[{omin},{omax}]')

# ============================================================
# 13. alt_forward_ranges LOOCO label check for ETH
# ============================================================
eth_top = {}
with open('data/processed/alt_cycle_metrics.csv') as f:
    for row in csv.DictReader(f):
        if row['asset'] == 'eth':
            v = row.get('D_asset_halving_to_top', '')
            if v:
                eth_top[row['cycle_id']] = int(v)

if len(eth_top) == 3:
    # ETH has C2, C3, C4
    cycles = sorted(eth_top.keys())
    vals = [eth_top[c] for c in cycles]
    for i, cyc in enumerate(cycles):
        remaining = [v for j, v in enumerate(vals) if j != i]
        exp_mean = sum(remaining) / len(remaining)
        col = f'looco_{cyc}_mean'
        with open('data/processed/alt_forward_ranges.csv') as f:
            for row in csv.DictReader(f):
                if row['asset'] == 'eth' and row['statistic'] == 'D_asset_halving_to_top':
                    actual = row.get(col, '')
                    if actual:
                        actual_f = float(actual)
                        # Check if the file's value matches the expected LOOCO for THIS cycle
                        # The file might use a different cycle indexing
                        if abs(actual_f - exp_mean) > 0.01:
                            # This means the column label != the cycle it actually represents
                            F('MEDIUM', 'alt_forward_ranges',
                              f'ETH/{col}', actual_f, exp_mean,
                              f'LOOCO column label may not match cycle ID {cyc}')

# ============================================================
# 14. Stale snapshot check
# ============================================================
import subprocess
def git_date(path):
    try:
        r = subprocess.run(['git', 'log', '--format=%ci', '-1', '--', path],
                          capture_output=True, text=True, cwd='.')
        return r.stdout.strip()[:10] if r.stdout.strip() else 'N/A'
    except:
        return 'N/A'

dates = {}
for f in ['data/events.csv', 'data/processed/btc_cycle_metrics.csv',
          'data/processed/next_cycle_zones.csv', 'data/processed/forward_ranges.csv',
          'data/processed/alt_cycle_metrics.csv', 'data/processed/alt_next_cycle_zones.csv']:
    dates[f] = git_date(f)

# Check if any derived file is older than its source
if dates['data/processed/btc_cycle_metrics.csv'] < dates['data/events.csv']:
    F('HIGH', 'btc_cycle_metrics', 'staleness',
      dates['data/processed/btc_cycle_metrics.csv'],
      f'>= {dates["data/events.csv"]}',
      'derived file older than events.csv')
if dates['data/processed/next_cycle_zones.csv'] < dates['data/processed/btc_cycle_metrics.csv']:
    F('HIGH', 'next_cycle_zones', 'staleness',
      dates['data/processed/next_cycle_zones.csv'],
      f'>= {dates["data/processed/btc_cycle_metrics.csv"]}',
      'derived file older than btc_cycle_metrics')
if dates['data/processed/forward_ranges.csv'] < dates['data/processed/btc_cycle_metrics.csv']:
    F('HIGH', 'forward_ranges', 'staleness',
      dates['data/processed/forward_ranges.csv'],
      f'>= {dates["data/processed/btc_cycle_metrics.csv"]}',
      'derived file older than btc_cycle_metrics')

# ============================================================
# 15. folklore_reconciliation: check B4 entry
# ============================================================
with open('data/processed/folklore_reconciliation.csv') as f:
    reader = csv.DictReader(f)
    has_b4 = False
    for row in reader:
        ann = row.get('chart_annotation', '')
        if 'B4' in ann.lower() or 'b4' in ann.lower():
            has_b4 = True
    if not has_b4:
        F('MEDIUM', 'folklore_reconciliation', 'B4_entry',
          'missing', 'entry for BTC projected B4',
          'no B4 row in folklore_reconciliation.csv')

# ============================================================
# OUTPUT
# ============================================================
severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4}
findings.sort(key=lambda x: severity_order.get(x[0], 99))

print("## Audit Findings\n")
for sev, file, loc, obs, exp, note in findings:
    print(f"| **{sev}** | `{file}` | `{loc}` | {obs} | {exp} | {note} |")

if not findings:
    print("No findings.")

print(f"\n--- Total: {len(findings)} findings ---")

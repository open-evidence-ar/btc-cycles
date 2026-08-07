import pandas as pd
import numpy as np
from pathlib import Path

ASSETS = ['btc', 'eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
NON_BTC_ASSETS = [a for a in ASSETS if a != 'btc']

# Phase definitions (days_from_halving bounds, per DESIGN.md §5.2)
# P4 upper bound is cycle-specific (next halving date); use +1500 as fallback
PHASE_DEFS = [
    ('P1', -540, 0),
    ('P2', 0, 270),
    ('P3', 270, 540),
]

# Load events.csv to compute P4 upper bound per cycle
events = pd.read_csv('data/events.csv')
halving_dates = {}
for _, row in events.iterrows():
    if row['event_type'] == 'halving':
        halving_dates[row['cycle_id']] = pd.to_datetime(row['date'])

# Build cycle ordering and compute days_from_halving to next halving
cycle_ids = ['C1', 'C2', 'C3', 'C4']
halving_order = ['H1', 'H2', 'H3', 'H4', 'H5']
p4_upper = {}
for i, cid in enumerate(cycle_ids):
    this_h_id = halving_order[i]
    next_h_id = halving_order[i + 1]
    if this_h_id in halving_dates and next_h_id in halving_dates:
        this_h = halving_dates[this_h_id]
        next_h = halving_dates[next_h_id]
        p4_upper[cid] = (next_h - this_h).days
    else:
        p4_upper[cid] = 1500

# Load returns_aligned.csv
df = pd.read_csv('data/processed/returns_aligned.csv')
df['date'] = pd.to_datetime(df['date'])

# Assign phase to each row
def assign_phase(row):
    d = row['days_from_halving']
    cid = row['cycle_id']
    for pname, lo, hi in PHASE_DEFS:
        if lo < d <= hi:
            return pname
    # P4: (540, next_halving)
    if d > 540 and d <= p4_upper.get(cid, 1500):
        return 'P4'
    return None

df['phase'] = df.apply(assign_phase, axis=1)

# Compute correlations: for each phase, pool rows across all cycles,
# then compute Pearson and Spearman of BTC log_return vs each asset.
results = []
for phase in ['P1', 'P2', 'P3', 'P4']:
    phase_df = df[df['phase'] == phase].copy()
    if len(phase_df) == 0:
        continue

    btc_lr = f'btc_log_return_w7d'

    for asset in NON_BTC_ASSETS:
        asset_lr = f'{asset}_log_return_w7d'

        # Pairwise dropna: keep rows where both BTC and asset have non-NaN log returns
        valid = phase_df[[btc_lr, asset_lr]].dropna()
        n = len(valid)

        if n < 10:
            # Insufficient data for reliable correlation
            results.append({
                'phase': phase,
                'asset': asset,
                'pearson': np.nan,
                'spearman': np.nan,
                'n_obs': n,
            })
            continue

        pearson_r = valid[btc_lr].corr(valid[asset_lr], method='pearson')
        # Spearman = Pearson of ranks (avoids scipy dependency)
        ranked_btc = valid[btc_lr].rank()
        ranked_asset = valid[asset_lr].rank()
        spearman_r = ranked_btc.corr(ranked_asset, method='pearson')

        results.append({
            'phase': phase,
            'asset': asset,
            'pearson': pearson_r,
            'spearman': spearman_r,
            'n_obs': n,
        })

result_df = pd.DataFrame(results)

# Ensure output directory exists
output_path = Path('data/processed')
output_path.mkdir(exist_ok=True)

result_df.to_csv(output_path / 'correlations_phase.csv', index=False)
print(f"Wrote {len(result_df)} rows to data/processed/correlations_phase.csv")
print(result_df.pivot(index='asset', columns='phase', values='pearson').to_string())

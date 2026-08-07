import pandas as pd
import numpy as np
from pathlib import Path

ASSETS = ['btc', 'eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
NON_BTC_ASSETS = [a for a in ASSETS if a != 'btc']
MACRO_ASSETS = ['dxy', 'tlt']
ROLLING_WINDOW = 365  # 1-year rolling window for regime classification

# Phase definitions (days_from_halving bounds, per DESIGN.md §5.2)
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

cycle_ids = ['C1', 'C2', 'C3', 'C4']
halving_order = ['H1', 'H2', 'H3', 'H4', 'H5']
p4_upper = {}
for i, cid in enumerate(cycle_ids):
    this_h_id = halving_order[i]
    next_h_id = halving_order[i + 1]
    if this_h_id in halving_dates and next_h_id in halving_dates:
        p4_upper[cid] = (halving_dates[next_h_id] - halving_dates[this_h_id]).days
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
    if d > 540 and d <= p4_upper.get(cid, 1500):
        return 'P4'
    return None

df['phase'] = df.apply(assign_phase, axis=1)

# For each macro asset, classify regime based on rolling z-score
results = []

for macro in MACRO_ASSETS:
    close_col = f'{macro}_close'

    # Compute rolling mean and std across all cycles combined
    # (sort by date first for proper rolling)
    df_sorted = df.sort_values('date').copy()
    rolling_mean = df_sorted[close_col].rolling(window=ROLLING_WINDOW, min_periods=180).mean()
    rolling_std = df_sorted[close_col].rolling(window=ROLLING_WINDOW, min_periods=180).std()

    # Assign back to original df
    df_sorted['rolling_mean'] = rolling_mean
    df_sorted['rolling_std'] = rolling_std
    df_sorted['z_score'] = (df_sorted[close_col] - rolling_mean) / rolling_std

    # Classify regimes
    df_sorted['regime'] = 'normal'
    df_sorted.loc[df_sorted['z_score'] > 1.0, 'regime'] = 'high'
    df_sorted.loc[df_sorted['z_score'] < -1.0, 'regime'] = 'low'

    # For each regime, compute phase-conditional correlations
    for regime in ['high', 'low']:
        regime_df = df_sorted[df_sorted['regime'] == regime]

        for phase in ['P1', 'P2', 'P3', 'P4']:
            phase_df = regime_df[regime_df['phase'] == phase]
            if len(phase_df) < 10:
                continue

            btc_lr = 'btc_log_return_w7d'

            for asset in NON_BTC_ASSETS:
                if asset == macro:
                    continue  # skip macro vs itself
                asset_lr = f'{asset}_log_return_w7d'
                valid = phase_df[[btc_lr, asset_lr]].dropna()

                if len(valid) < 10:
                    continue

                pearson_r = valid[btc_lr].corr(valid[asset_lr], method='pearson')

                results.append({
                    'macro_asset': macro,
                    'regime': regime,
                    'phase': phase,
                    'asset': asset,
                    'pearson': pearson_r,
                    'n_obs': len(valid),
                })

result_df = pd.DataFrame(results)

# Load full-sample correlations for comparison
full_corr = pd.read_csv('data/processed/correlations_phase.csv')
full_corr = full_corr.rename(columns={'pearson': 'full_pearson'})

# Merge to compare sign
if len(result_df) > 0:
    merged = result_df.merge(
        full_corr[['phase', 'asset', 'full_pearson']],
        on=['phase', 'asset'],
        how='left',
    )
    merged['sign_flip'] = (
        (merged['pearson'] > 0) != (merged['full_pearson'] > 0)
    ) & merged['full_pearson'].notna() & merged['pearson'].notna()

    # Count sign flips per (macro_asset, regime)
    flip_summary = merged.groupby(['macro_asset', 'regime']).agg(
        n_phases=('phase', 'nunique'),
        n_sign_flips=('sign_flip', 'sum'),
    ).reset_index()

    print("Sign flip summary:")
    print(flip_summary.to_string(index=False))
else:
    merged = result_df
    print("No results to merge")

# Ensure output directory exists
output_path = Path('data/processed')
output_path.mkdir(exist_ok=True)

merged.to_csv(output_path / 'correlations_BY_regime.csv', index=False)
print(f"\nWrote {len(merged)} rows to correlations_BY_regime.csv")

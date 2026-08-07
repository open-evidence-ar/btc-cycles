import pandas as pd
import numpy as np
from pathlib import Path

ASSETS = ['btc', 'eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
NON_BTC_ASSETS = [a for a in ASSETS if a != 'btc']
ROLLING_WINDOW = 90
CROSS_LAG_RANGE = 60  # [-60, +60]

# Load returns_aligned.csv
df = pd.read_csv('data/processed/returns_aligned.csv')
df['date'] = pd.to_datetime(df['date'])

# --- Part 1: Rolling 90-day Pearson correlation ---
rolling_rows = []
for cycle_id in sorted(df['cycle_id'].unique()):
    cyc = df[df['cycle_id'] == cycle_id].sort_values('days_from_halving').copy()
    btc_lr = cyc['btc_log_return_w7d'].to_numpy(dtype=float)

    for asset in NON_BTC_ASSETS:
        asset_lr = cyc[f'{asset}_log_return_w7d'].to_numpy(dtype=float)

        # Compute rolling correlation using pandas for NaN handling
        s_btc = pd.Series(btc_lr, index=cyc['days_from_halving'])
        s_asset = pd.Series(asset_lr, index=cyc['days_from_halving'])

        rolling_r = s_btc.rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW).corr(s_asset)

        # Drop the first ROLLING_WINDOW-1 rows (NaN by construction)
        valid = rolling_r.dropna()
        for d, r in valid.items():
            date_val = cyc.loc[cyc['days_from_halving'] == d, 'date'].iloc[0]
            rolling_rows.append({
                'cycle_id': cycle_id,
                'days_from_halving': int(d),
                'date': date_val,
                'asset': asset,
                'rolling_r_90d': r,
            })

rolling_df = pd.DataFrame(rolling_rows)
rolling_df.to_csv('data/processed/correlations_rolling.csv', index=False)
print(f"Wrote {len(rolling_df)} rows to correlations_rolling.csv")

# --- Part 2: Cross-correlation lag [-60, +60] ---
cross_lag_rows = []
for cycle_id in sorted(df['cycle_id'].unique()):
    cyc = df[df['cycle_id'] == cycle_id].sort_values('days_from_halving').copy()
    btc_lr = cyc['btc_log_return_w7d'].to_numpy(dtype=float)

    for asset in NON_BTC_ASSETS:
        asset_lr = cyc[f'{asset}_log_return_w7d'].to_numpy(dtype=float)

        for lag in range(-CROSS_LAG_RANGE, CROSS_LAG_RANGE + 1):
            if lag >= 0:
                btc_part = btc_lr[:-lag] if lag > 0 else btc_lr
                asset_part = asset_lr[lag:] if lag > 0 else asset_lr
            else:
                abs_lag = -lag
                btc_part = btc_lr[abs_lag:]
                asset_part = asset_lr[:len(btc_part)]

            # Pairwise drop NaN
            mask = np.isfinite(btc_part) & np.isfinite(asset_part)
            b, a = btc_part[mask], asset_part[mask]

            if len(b) < 10:
                cross_lag_rows.append({
                    'cycle_id': cycle_id,
                    'asset': asset,
                    'lag': lag,
                    'cross_corr': np.nan,
                })
            else:
                cross_r = np.corrcoef(b, a)[0, 1]
                cross_lag_rows.append({
                    'cycle_id': cycle_id,
                    'asset': asset,
                    'lag': lag,
                    'cross_corr': cross_r,
                })

cross_lag_df = pd.DataFrame(cross_lag_rows)
cross_lag_df.to_csv('data/processed/cross_lag.csv', index=False)
print(f"Wrote {len(cross_lag_df)} rows to cross_lag.csv")

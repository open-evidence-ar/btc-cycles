import pandas as pd
import numpy as np
from pathlib import Path

ASSETS = ['btc', 'eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
CYCLES = [('C1', '2012-11-28'), ('C2', '2016-07-09'), ('C3', '2020-05-11'), ('C4', '2024-04-20')]
DAYS_MIN, DAYS_MAX = -1500, 1500
LOGRET_LAG = 7  # days

# Load each asset's latest snapshot (discover via manifest or glob)
# Build per-asset daily close: date(MM-DD-YYYY) -> close
ASSET_CLOSES = {}
manifest_path = Path('data/raw/manifest.txt')
if manifest_path.exists():
    manifest = pd.read_csv(manifest_path, sep='\t')
    for _, row in manifest.iterrows():
        symbol = row['symbol']
        filename = row['filename']
        if symbol in ASSETS:
            df = pd.read_csv(f"data/raw/{filename}", parse_dates=['date'])
            # Create a mapping from date to close price (format: YYYY-MM-DD as string for consistency)
            date_to_close = dict(zip(df['date'].dt.strftime('%Y-%m-%d'), df['close']))
            ASSET_CLOSES[symbol] = date_to_close

# Pre-allocate list for all cycle blocks
all_blocks = []

for cycle_id, halving_date_str in CYCLES:
    # Parse halving date
    halving_date = pd.to_datetime(halving_date_str)
    
    # Initialize rows for this cycle
    cycle_rows = []
    
    # Generate dates for this cycle
    for d in range(DAYS_MIN, DAYS_MAX + 1):
        cal_date = halving_date + pd.Timedelta(days=d)
        date_str = cal_date.strftime('%Y-%m-%d')
        
        # Build row for this day
        row = {'cycle_id': cycle_id, 'days_from_halving': d, 'date': date_str}
        
        # Get close prices for all assets
        closes = {}
        log_returns = {}

        for symbol in ASSETS:
            asset_map = ASSET_CLOSES.get(symbol, {})
            close = asset_map.get(date_str)
            closes[symbol] = close
            row[f'{symbol}_close'] = close

        # Compute log returns after we have all close prices for this date
        for symbol in ASSETS:
            close = closes[symbol]
            
            # Compute log return as log(close[t] / close[t-7 CALENDAR days])
            # Lookup the asset's close at calendar date d-7, even if that's before the cycle window.
            # (log_return must be defined for the very first rows of a cycle's [-1500, +1500]
            #  window if the asset was trading before the window start.)
            lag_cal_date = cal_date - pd.Timedelta(days=LOGRET_LAG)
            lag_date_str = lag_cal_date.strftime('%Y-%m-%d')
            lag_map = ASSET_CLOSES.get(symbol, {})
            lag_close = lag_map.get(lag_date_str)
            
            if close is not None and lag_close is not None and lag_close > 0 and close > 0:
                log_return = np.log(close / lag_close)
            else:
                log_return = None
                
            row[f'{symbol}_log_return_w7d'] = log_return
        
        cycle_rows.append(row)
    
    # Convert to DataFrame
    cycle_df = pd.DataFrame(cycle_rows)
    
    # Sort by days_from_halving for consistency
    cycle_df = cycle_df.sort_values('days_from_halving')
    
    # Add to all blocks
    all_blocks.append(cycle_df)

# Concat all cycle blocks
result_df = pd.concat(all_blocks, ignore_index=True)

# Sort final result for consistency
result_df = result_df.sort_values(['cycle_id', 'days_from_halving'])

# Forward-fill close prices within each cycle so that weekends/holidays
# (macro assets only trade on business days) carry the last available
# trading-day close.  This is standard financial practice and ensures
# log_returns can be computed on every calendar day.
for cycle_id in result_df['cycle_id'].unique():
    mask = result_df['cycle_id'] == cycle_id
    for symbol in ASSETS:
        col = f'{symbol}_close'
        result_df.loc[mask, col] = result_df.loc[mask, col].ffill()

# Recompute log_returns using the forward-filled closes
for cycle_id in result_df['cycle_id'].unique():
    mask = result_df['cycle_id'] == cycle_id
    for symbol in ASSETS:
        col = f'{symbol}_close'
        lr_col = f'{symbol}_log_return_w7d'
        close_arr = result_df.loc[mask, col].to_numpy(dtype=float)
        shifted = pd.Series(close_arr).shift(LOGRET_LAG).to_numpy(dtype=float)
        valid = np.isfinite(close_arr) & np.isfinite(shifted) & (shifted > 0) & (close_arr > 0)
        log_ret = np.where(valid, np.log(close_arr / shifted), np.nan)
        result_df.loc[mask, lr_col] = log_ret

# Ensure directory exists
output_path = Path('data/processed')
output_path.mkdir(exist_ok=True)

# Write to CSV
result_df.to_csv(output_path / 'returns_aligned.csv', index=False)

print(f"Created {len(result_df)} rows in data/processed/returns_aligned.csv")
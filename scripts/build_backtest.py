import pandas as pd
import numpy as np
from pathlib import Path

# Load data
metrics = pd.read_csv('data/processed/btc_cycle_metrics.csv')
fwd = pd.read_csv('data/processed/forward_ranges.csv')

# Statistics with LOOCO backtest
STATS = ['D_halving_to_top', 'D_top_to_next_bottom']
CYCLES_WITH_DATA = ['C1', 'C2', 'C3']  # C4 has no top/bottom yet

results = []

for stat in STATS:
    # Get the forward range for this stat
    fwd_row = fwd[fwd['statistic'] == stat].iloc[0]
    outer_min = fwd_row['min']
    outer_max = fwd_row['max']

    for leave_out in CYCLES_WITH_DATA:
        # Get values for remaining cycles
        remaining_vals = []
        actual_val = None
        halving_date = None

        for _, row in metrics.iterrows():
            cid = row['cycle_id']
            val = row[stat]
            if pd.notna(val):
                if cid == leave_out:
                    actual_val = float(val)
                    halving_date = pd.to_datetime(row['halving_date'])
                else:
                    remaining_vals.append(float(val))

        if actual_val is None or len(remaining_vals) == 0:
            continue

        # Predict from remaining cycles (use mean and median)
        pred_mean = float(np.mean(remaining_vals))
        pred_median = float(np.median(remaining_vals))

        # Date errors (in days)
        date_error_mean = abs(pred_mean - actual_val)
        date_error_median = abs(pred_median - actual_val)

        # Check if predicted date falls within outer range
        predicted_in_outer_mean = outer_min <= pred_mean <= outer_max
        predicted_in_outer_median = outer_min <= pred_median <= outer_max

        results.append({
            'statistic': stat,
            'leave_out_cycle': leave_out,
            'actual_value': actual_val,
            'predicted_mean': pred_mean,
            'predicted_median': pred_median,
            'date_error_mean': date_error_mean,
            'date_error_median': date_error_median,
            'outer_range_min': outer_min,
            'outer_range_max': outer_max,
            'predicted_in_outer_mean': predicted_in_outer_mean,
            'predicted_in_outer_median': predicted_in_outer_median,
        })

result_df = pd.DataFrame(results)

# Ensure output directory exists
output_path = Path('data/processed')
output_path.mkdir(exist_ok=True)

result_df.to_csv(output_path / 'backtest_by_cycle.csv', index=False)
print(f"Wrote {len(result_df)} rows to backtest_by_cycle.csv")
print(result_df[['statistic', 'leave_out_cycle', 'actual_value',
                  'date_error_mean', 'date_error_median',
                  'predicted_in_outer_mean']].to_string())

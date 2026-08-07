import pandas as pd
import numpy as np
from pathlib import Path

# Statistics to aggregate (from DESIGN.md A5.3)
STATS = [
    'D_prev_bottom_to_halving',
    'D_halving_to_top',
    'D_top_to_next_bottom',
    'mult_bottom_to_top',
    'drawdown_pct',
]

# Derived cross-cycle statistic (2026-07-23 addition): the full bull duration,
# from a cycle's bear bottom to the NEXT cycle's top. Folklore "1,064-day bull"
# pattern (user-validated 2026-07-23) matches our 3 historical transitions
# (1050, 1059, 1067 days) tightly (range 17d, ~1.6% of mean). Used as a
# cross-check on the H5-anchored C5 projection: B4 + IQR(D_bottom_to_next_top)
# gives an independent C5 top date that should agree with the halving-path
# projection if the bull rhythm holds.
DERIVED_STATS = ['D_bottom_to_next_top']

CYCLES = ['C1', 'C2', 'C3', 'C4']
ALL_CYCLES = CYCLES.copy()

# Load cycle metrics
metrics = pd.read_csv('data/processed/btc_cycle_metrics.csv')

# Compute forward ranges and LOOCO
rows = []
for stat in STATS:
    # Get values for each cycle (NaN if missing)
    vals = {}
    for c in CYCLES:
        row = metrics[metrics['cycle_id'] == c]
        if len(row) > 0 and pd.notna(row[stat].iloc[0]):
            vals[c] = float(row[stat].iloc[0])

    n = len(vals)
    if n == 0:
        continue

    values = np.array(list(vals.values()))

    # Full-sample stats
    mean_val = float(np.mean(values))
    median_val = float(np.median(values))
    min_val = float(np.min(values))
    max_val = float(np.max(values))
    q25 = float(np.percentile(values, 25))
    q75 = float(np.percentile(values, 75))

    # LOOCO
    looco_means = {}
    looco_deltas = {}
    for k in vals:
        looco_vals = [v for c, v in vals.items() if c != k]
        looco_mean = float(np.mean(looco_vals))
        looco_means[k] = looco_mean
        looco_deltas[k] = looco_mean - mean_val

    # Check sensitivity: |delta| > 20% of mean
    is_sensitive = False
    if mean_val != 0:
        for k, delta in looco_deltas.items():
            if abs(delta) > 0.20 * abs(mean_val):
                is_sensitive = True
                break

    row_data = {
        'statistic': stat,
        'n': n,
        'mean': mean_val,
        'median': median_val,
        'min': min_val,
        'max': max_val,
        'q25': q25,
        'q75': q75,
        'is_sensitive': is_sensitive,
    }

    # Add LOOCO columns for each cycle
    for c in ALL_CYCLES:
        if c in looco_means:
            row_data[f'looco_{c}_mean'] = looco_means[c]
            row_data[f'looco_{c}_delta'] = looco_deltas[c]
        else:
            row_data[f'looco_{c}_mean'] = ''
            row_data[f'looco_{c}_delta'] = ''

    rows.append(row_data)

result_df = pd.DataFrame(rows)

# --- Derived cross-cycle statistic: D_bottom_to_next_top ---
# For each cycle C_n with a bear bottom AND a successor C_{n+1} with a top,
# compute days(C_{n+1}.final_top - C_n.next_bear_bottom).
# This is the full bull duration: from one cycle's bear bottom to the next
# cycle's local top. Folklore "1,064-day bull" pattern.
metrics_sorted = metrics.sort_values('cycle_id').reset_index(drop=True)
derived_vals = {}
for i in range(len(metrics_sorted) - 1):
    cur = metrics_sorted.iloc[i]
    nxt = metrics_sorted.iloc[i + 1]
    cur_bot = cur.get('next_bear_bottom_date', '')
    nxt_top = nxt.get('final_top_date', '')
    cur_cycle_col = cur.get('cycle_id', '')
    nxt_cycle_col = nxt.get('cycle_id', '')
    if cur_bot and nxt_top and pd.notna(cur_bot) and pd.notna(nxt_top):
        try:
            d = (pd.to_datetime(nxt_top) - pd.to_datetime(cur_bot)).days
            # Key from "source cycle -> target cycle" so user can see
            # what each value measures (e.g. "C2->C3" = 1059d)
            derived_vals[f"{cur_cycle_col}->{nxt_cycle_col}"] = float(d)
        except Exception:
            pass

if derived_vals:
    d_values = np.array(list(derived_vals.values()), dtype=float)
    d_n = len(d_values)
    d_mean = float(np.mean(d_values))
    d_median = float(np.median(d_values))
    d_min = float(np.min(d_values))
    d_max = float(np.max(d_values))
    d_q25 = float(np.percentile(d_values, 25))
    d_q75 = float(np.percentile(d_values, 75))
    d_looco_means = {}
    d_looco_deltas = {}
    if d_n >= 2:
        for k in derived_vals:
            looco_v = [v for c, v in derived_vals.items() if c != k]
            lm = float(np.mean(looco_v))
            d_looco_means[k] = lm
            d_looco_deltas[k] = lm - d_mean
    d_is_sensitive = False
    if d_mean != 0 and d_n >= 2:
        for d in d_looco_deltas.values():
            if abs(d) > 0.20 * abs(d_mean):
                d_is_sensitive = True
                break

    d_row = {
        'statistic': 'D_bottom_to_next_top',
        'n': d_n,
        'mean': d_mean,
        'median': d_median,
        'min': d_min,
        'max': d_max,
        'q25': d_q25,
        'q75': d_q75,
        'is_sensitive': d_is_sensitive,
    }
    # LOOCO columns inherit the same "C1->C2" keying bucket. The LOOCO
    # columns in the table are keyed by cycle (looco_C1_mean...); since our
    # derived stat values are per-pair not per-cycle, we map each pair back
    # to its SOURCE cycle for LOOCO column placement.
    for c in ALL_CYCLES:
        key = next((k for k in derived_vals if k.startswith(c + '->')), None)
        if key and key in d_looco_means:
            d_row[f'looco_{c}_mean'] = d_looco_means[key]
            d_row[f'looco_{c}_delta'] = d_looco_deltas[key]
        else:
            d_row[f'looco_{c}_mean'] = ''
            d_row[f'looco_{c}_delta'] = ''

    result_df = pd.concat([result_df, pd.DataFrame([d_row])], ignore_index=True)

# Ensure output directory exists
output_path = Path('data/processed')
output_path.mkdir(exist_ok=True)

result_df.to_csv(output_path / 'forward_ranges.csv', index=False)
print(f"Wrote {len(result_df)} rows to forward_ranges.csv")
print(result_df[['statistic', 'n', 'mean', 'median', 'min', 'max', 'is_sensitive']].to_string())

#!/usr/bin/env python
"""Additional audit checks."""
import csv
from datetime import datetime

# Find the out-of-range rolling correlation value
print("=== Rolling correlation out-of-range value ===")
with open('data/processed/correlations_rolling.csv') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames
    print(f"Columns: {headers}")
    out_count = 0
    for row in reader:
        r = float(row['rolling_r_90d'])
        if r < -1 or r > 1:
            out_count += 1
            print(f"  OUT-OF-RANGE: cycle={row.get('cycle_id','?')}, asset={row.get('asset','?')}, "
                  f"date={row.get('date','?')}, r={r}")
            if out_count >= 5:
                break

# Gold C1 details
print("\n=== Gold C1 cycle metrics ===")
with open('data/processed/alt_cycle_metrics.csv') as f:
    for row in csv.DictReader(f):
        if row['asset'] == 'gold' and row['cycle_id'] == 'C1':
            for k, v in row.items():
                print(f"  {k}: {v}")

# Gold zones detail
print("\n=== Gold next-cycle zones ===")
with open('data/processed/alt_next_cycle_zones.csv') as f:
    for row in csv.DictReader(f):
        if row['asset'] == 'gold':
            print(f"  zone={row['zone']}, low={row['price_low']}, high={row['price_high']}, "
                  f"anchor={row.get('anchor_price','N/A')}, support_low={row.get('support_band_low','')}, "
                  f"support_high={row.get('support_band_high','')}, cross_check={row.get('cross_check_ok','')}")

# btc_cycle_metrics schema check
print("\n=== btc_cycle_metrics columns ===")
with open('data/processed/btc_cycle_metrics.csv') as f:
    headers = f.readline().strip().split(',')
    for h in headers:
        print(f"  {h}")

# H5 event context
print("\n=== events.csv H5 entry ===")
with open('data/events.csv') as f:
    for row in csv.DictReader(f):
        if row['label'] == 'H5':
            print(f"  {row}")

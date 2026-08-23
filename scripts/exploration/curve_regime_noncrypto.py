#!/usr/bin/env python3
"""
exploration/curve_regime_noncrypto.py  —  Pure exploration, no model change.

Questions:
1. What is the current curve_shape_state (2026-08-10)?
2. How have SPX/NDX/TLT/GOLD historically performed in each state?
3. Does conditioning on curve-shape state sharpen non-crypto forward ranges?

No increment proposed. No model change. Just look at the data.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
EXP_DIR = ROOT / "data" / "raw" / "exploration"
DERIVED = ROOT / "data" / "processed" / "exploration_eu_proxies.csv"

# Load derived curve-shape series
derived = pd.read_csv(DERIVED, parse_dates=["date"])
derived = derived.set_index("date").sort_index()
print(f"Loaded derived series: {len(derived)} rows, {derived.index.min().date()}..{derived.index.max().date()}")

# Load non-crypto assets from existing Yahoo snapshots
ASSET_FILES = {
    "spx":  sorted((ROOT / "data" / "raw").glob("spx_yahoo_*.csv"))[-1],
    "ndx":  sorted((ROOT / "data" / "raw").glob("ndx_yahoo_*.csv"))[-1],
    "tlt":  sorted((ROOT / "data" / "raw").glob("tlt_yahoo_*.csv"))[-1],
    "dxy":  sorted((ROOT / "data" / "raw").glob("dxy_yahoo_*.csv"))[-1],
    "gold": sorted((ROOT / "data" / "raw").glob("gold_yahoo_*.csv"))[-1],
}
assets = {}
for name, f in ASSET_FILES.items():
    df = pd.read_csv(f, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    assets[name] = df["close"]
    print(f"  {name}: {f.name} ({len(df)} rows, {df.index.min().date()}..{df.index.max().date()})")

# Merge
# Drop existing dxy/tlt from derived (we'll re-join fresh from ASSET_FILES)
for col in ["dxy", "tlt", "btc_close", "data_source_flag"]:
    if col in derived.columns:
        derived.drop(columns=[col], inplace=True)
df = derived[["curve_shape_state", "curve_slope_10_5", "slope_180d_delta", "y10", "y5", "y13w"]].copy()
for name, s in assets.items():
    df = df.join(s.rename(name), how="left")

# Forward returns (20d, 60d, 120d) for each asset
for name in assets:
    for horizon in [20, 60, 120]:
        df[f"{name}_fwd{horizon}d"] = df[name].pct_change(horizon).shift(-horizon)

# Drop rows with no state
df = df[df["curve_shape_state"] != "unclassified"].copy()
print(f"\nAnalysis sample: {len(df)} rows with valid state")

# ------------------------------------------------------------------
# Q1: Current state
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q1: CURRENT CURVE-SHAPE STATE")
print("=" * 60)
latest = df.iloc[-1]
print(f"Date: {df.index[-1].date()}")
print(f"  curve_shape_state: {latest['curve_shape_state']}")
print(f"  curve_slope_10_5:  {latest['curve_slope_10_5']:.2f} (10y-5y, %)")
print(f"  slope_180d_delta:  {latest['slope_180d_delta']:.2f} (180d change, %)")
print(f"  ^TNX (10y):        {df['y10'].iloc[-1]:.2f}%")
print(f"  ^FVX (5y):         {df['y5'].iloc[-1]:.2f}%")

# State distribution
print(f"\nState distribution (full history):")
print(df["curve_shape_state"].value_counts().to_string())

# ------------------------------------------------------------------
# Q2: Forward returns conditioned on state
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q2: FORWARD RETURNS CONDITIONED ON CURVE-SHAPE STATE")
print("=" * 60)
fwd_cols = [c for c in df.columns if c.startswith(tuple(assets.keys())) and "_fwd" in c]
results = []
for state in ["inverted_flat", "bear_steep", "bull_steep", "normal"]:
    sub = df[df["curve_shape_state"] == state]
    if len(sub) < 30:
        continue
    row = {"state": state, "n_days": len(sub)}
    for col in fwd_cols:
        valid = sub[col].dropna()
        row[f"{col}_mean"] = valid.mean() * 100  # pct
        row[f"{col}_median"] = valid.median() * 100
        row[f"{col}_std"] = valid.std() * 100
    results.append(row)

res_df = pd.DataFrame(results)
print(res_df.to_string(index=False, float_format=lambda x: f"{x:8.3f}"))

# ------------------------------------------------------------------
# Q3: Does conditioning sharpen non-crypto forward ranges?
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q3: CONDITIONING ON STATE vs UNCONDITIONAL (full history)")
print("=" * 60)
for name in assets:
    print(f"\n{name.upper()}:")
    fwd = df[f"{name}_fwd60d"].dropna()
    if fwd.empty:
        continue
    print(f"  Unconditional 60d: mean={fwd.mean()*100:.2f}% median={fwd.median()*100:.2f}% std={fwd.std()*100:.2f}%")
    for state in ["inverted_flat", "bear_steep", "bull_steep"]:
        sub = df[df["curve_shape_state"] == state][f"{name}_fwd60d"].dropna()
        if len(sub) < 20:
            continue
        print(f"  {state:15s} 60d: mean={sub.mean()*100:.2f}% median={sub.median()*100:.2f}% std={sub.std()*100:.2f}% (n={len(sub)})")

# ------------------------------------------------------------------
# Q4: Transition matrix (state persistence)
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q4: STATE PERSISTION (1-day transition probabilities)")
print("=" * 60)
states = df["curve_shape_state"]
trans = pd.crosstab(states.shift(1), states, normalize="index")
print(trans.round(3).to_string())

# ------------------------------------------------------------------
# Q5: How long do states last?
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q5: AVERAGE STATE DURATION (days)")
print("=" * 60)
df["state_change"] = df["curve_shape_state"] != df["curve_shape_state"].shift(1)
df["state_id"] = df["state_change"].cumsum()
durations = df.groupby(["state_id", "curve_shape_state"]).size().reset_index(name="duration")
dur_summary = durations.groupby("curve_shape_state")["duration"].agg(["mean", "median", "max", "count"])
print(dur_summary.to_string(float_format=lambda x: f"{x:.1f}"))

# ------------------------------------------------------------------
# Q6: Current state + recent history
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("Q6: RECENT STATE HISTORY (last 252 trading days ~ 1 year)")
print("=" * 60)
recent = df.tail(252)
print(recent["curve_shape_state"].value_counts().to_string())
print(f"\nCurrent state entered: {df[df['curve_shape_state'] != df['curve_shape_state'].shift(1)].iloc[-1].name.date()}")
print(f"Days in current state: {(df['curve_shape_state'] == df['curve_shape_state'].iloc[-1]).sum()}")

print("\n" + "=" * 60)
print("EXPLORATION COMPLETE — no model changes made")
print("=" * 60)

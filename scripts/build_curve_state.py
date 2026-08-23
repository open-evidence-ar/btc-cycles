#!/usr/bin/env python3
"""I-21.2/I-21.3: Build the daily curve-state + gated regime series.

Inputs (data/raw/, manifest-tracked):
    y10  <- y10_yield_yahoo_*.csv    (^TNX, 10y par yield %)
    y2   <- y2_eco3min_*.csv         (Eco3min mirror of FRED DGS2, 2y %)

Derivation (matches I-21 exploration §4.1, now on the PROPER 10y-2y gauge
instead of the round-1 10y-5y substitute):
    curve_slope_10_2  = y10 - y2
    slope_180d_delta  = diff(curve_slope_10_2, 180 rows)
    curve_shape_state = classify_curve(slope, delta)   [pre-committed §4.1]

The classifier thresholds are slope-agnostic (slope <= 0, delta > +40bps,
delta < -40bps) so upgrading the gauge from 10y-5y to 10y-2y does NOT
retune them (documented in docs/blockers/I-21-eurodollar-proxies-exploration.md
§3.4 honest-limits; resolved in I-21.1 source discovery).

I-21.3 gate: regime_state is the persistence-filtered version of
curve_shape_state. A candidate state must be observed for GATE_STREAK
(5) consecutive classified days before it replaces the current regime;
unclassified days break the persistence run. prev_regime_state records
the regime that the current one replaced; regime_state_days counts how
long the current regime has been in effect.

Output: data/processed/curve_state.csv  (bit-identical on re-run -> the
I-21.2 determinism gate).

Regime states are ordinal-encoded elsewhere (normal=0, bear_steep=1,
inverted_flat=2, bull_steep=3) per round-2 tooling.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "curve_state.csv"

GATE_STREAK = 5  # I-21.3 persistence filter (user decision: 5 consecutive days)

STATE_ORDER = ["normal", "bear_steep", "bull_steep", "inverted_flat"]


def classify_curve(slope: float, dslop: float) -> str:
    """Pre-committed thresholds from I-21 blocker doc §4.1.

    Committed on the 10y-5y substitute, applied UNCHANGED to the proper
    10y-2y slope (thresholds depend only on slope sign and delta size).
    """
    if pd.isna(slope) or pd.isna(dslop):
        return "unclassified"
    # inverted_flat: slope <= 0 AND |180d delta| <= 20bps
    if slope <= 0.0 and abs(dslop) <= 0.20:
        return "inverted_flat"
    # bear_steep:  slope > 0 AND 180d delta > +40bps  (slope rising fast)
    if slope > 0.0 and dslop > 0.40:
        return "bear_steep"
    # bull_steep:  180d delta < -40bps (shorts falling fast)
    if dslop < -0.40:
        return "bull_steep"
    return "normal"


def load_raw(key: str, pattern: str) -> pd.DataFrame:
    """Load + merge all snapshots for one raw series (latest wins)."""
    files = sorted(RAW_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No raw file for {key} under {pattern}")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        frames.append(df[["date", "close"]].rename(columns={"close": key}))
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return merged.sort_values("date").reset_index(drop=True)


def build_curve_state() -> pd.DataFrame:
    """Derive the full curve-state + gated-regime daily series."""
    y10 = load_raw("y10", "y10_yield_yahoo_*.csv")
    y2 = load_raw("y2", "y2_eco3min_*.csv")
    df = y10.merge(y2, on="date", how="inner").sort_values("date").reset_index(drop=True)

    df["curve_slope_10_2"] = df["y10"] - df["y2"]
    # 180-row diff matches the round-1 definition (exploration §4.1).
    df["slope_180d_delta"] = df["curve_slope_10_2"].diff(180)
    df["curve_shape_state"] = df.apply(
        lambda r: classify_curve(r["curve_slope_10_2"], r["slope_180d_delta"]),
        axis=1,
    )

    # --- I-21.3 persistence gate ---------------------------------------
    regime: str | None = None
    prev_regime: str | None = None
    candidate: str | None = None
    candidate_streak = 0
    regime_days = 0
    reg_series: list[str] = []
    prev_series: list[str] = []
    days_series: list[int] = []

    for raw in df["curve_shape_state"]:
        if raw == "unclassified":
            # unclassified breaks a persistence run
            candidate = None
            candidate_streak = 0
            if regime is None:
                reg_series.append("unclassified")
                prev_series.append("")
                days_series.append(0)
            else:
                reg_series.append(regime)
                prev_series.append(prev_regime or "")
                days_series.append(regime_days)
            continue

        if regime is None:
            regime = raw
            prev_regime = None
            regime_days = 1
            candidate = None
            candidate_streak = 0
        elif raw == regime:
            regime_days += 1
            candidate = None
            candidate_streak = 0
        else:
            if candidate == raw:
                candidate_streak += 1
            else:
                candidate = raw
                candidate_streak = 1
            regime_days += 1
            if candidate_streak >= GATE_STREAK:
                prev_regime = regime
                regime = raw
                regime_days = 1
                candidate = None
                candidate_streak = 0

        reg_series.append(regime)
        prev_series.append(prev_regime or "")
        days_series.append(regime_days)

    df["regime_state"] = reg_series
    df["prev_regime_state"] = prev_series
    df["regime_state_days"] = days_series

    cols = [
        "date", "y10", "y2", "curve_slope_10_2", "slope_180d_delta",
        "curve_shape_state", "regime_state", "prev_regime_state",
        "regime_state_days",
    ]
    return df[cols]


def main(argv: list[str] | None = None) -> int:
    df = build_curve_state()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    # Summary
    n_class = df["curve_shape_state"].isin(STATE_ORDER).sum()
    print(f"Wrote {OUT}  ({len(df)} rows, {df['date'].iloc[0].date()}..{df['date'].iloc[-1].date()})")
    print("\nCurve-shape state distribution:")
    for st in STATE_ORDER:
        print(f"  {st:15s}: {int((df['curve_shape_state'] == st).sum())}")
    print(f"  unclassified   : {int((df['curve_shape_state'] == 'unclassified').sum())}")
    print(f"  classified     : {n_class}")
    print("\nRegime (gated, 5-day persistence) distribution:")
    for st in STATE_ORDER + ["unclassified"]:
        print(f"  {st:15s}: {int((df['regime_state'] == st).sum())}")

    latest = df.iloc[-1]
    print("\nLatest row:")
    print(f"  date               : {latest['date'].date()}")
    print(f"  curve_slope_10_2   : {latest['curve_slope_10_2']:.3f} (10y-2y, %)")
    print(f"  slope_180d_delta   : {latest['slope_180d_delta']:.3f}")
    print(f"  curve_shape_state  : {latest['curve_shape_state']}")
    print(f"  regime_state       : {latest['regime_state']}  ({latest['regime_state_days']} days, "
          f"prev={latest['prev_regime_state'] or 'n/a'})")

    # Regime transition count (for the no-thrash narrative)
    transitions = int((df["regime_state"].shift(1) != df["regime_state"]).sum())
    print(f"\n  regime transitions: {transitions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
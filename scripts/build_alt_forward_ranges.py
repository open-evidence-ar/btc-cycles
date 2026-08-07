"""I-17.2: Build per-asset forward ranges with LOOCO.

Mirrors `build_forward_ranges.py` (I-09 BTC version) but applied to each
of the 7 non-BTC panel assets using `alt_cycle_metrics.csv` from I-17.1.

For SOL (n_actual=1, n_with_proxy=3), we report:
  - `n_actual`: cycles with cycle_source="actual" or "actual_C4_open"
  - `n_with_proxy`: cycles with cycle_source in ("actual", "actual_C4_open", "ETH_proxy_*")
  - Per-statistic stats (mean/median/etc.) computed on the n_with_proxy set
  - LOOCO columns only populated when n_with_proxy >= 3
  - `n_with_proxy_explanatory_note`: text flag

For macro assets (SPX/NDX/DXY/TLT) which have n=4 (all cycles actual),
LOOCO is fully populated. For ETH n=3 (C2, C3 actual + C4 open).

Output: data/processed/alt_forward_ranges.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "processed" / "alt_cycle_metrics.csv"
INPUT_BTC = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
OUTPUT = ROOT / "data" / "processed" / "alt_forward_ranges.csv"

STATS = [
    "D_asset_prev_bottom_to_halving",
    "D_asset_halving_to_top",
    "D_asset_top_to_next_bottom",
    "mult_asset_bottom_to_top",
    "drawdown_asset_pct",
]

CYCLES = ["C1", "C2", "C3", "C4"]
ASSETS = ["eth", "xrp", "sol", "mstr", "wgmi", "spx", "ndx", "dxy", "tlt", "gold"]

# Rows with these cycle_source values count as "actually observed"
# (vs proxy or missing).
ACTUAL_SOURCES = {"actual", "actual_C4_open"}
PROXY_SOURCES = {"ETH_proxy_C1", "ETH_proxy_C2"}
USABLE_SOURCES = ACTUAL_SOURCES | PROXY_SOURCES  # for n_with_proxy

# Market-cap hierarchy (highest to lowest): BTC -> ETH -> XRP -> SOL
# For timing borrow: when an alt has <3 actual D_top_to_next_bottom samples,
# use median(BTC + next-higher-cap alt) per user choice "Median of MCap-higher
# alt + BTC" (2026-07-23 session).
#   SOL borrows from BTC + XRP (next-higher-cap alt)
#   XRP borrows from BTC + ETH (next-higher-cap alt)
#   ETH has n=3, no borrowing needed
CAP_HIERARCHY = {"sol": "xrp", "xrp": "eth", "eth": None, "btc": None}
TIMING_BORROW_MIN_SAMPLES = 2  # borrow only when n_actual < 2 (i.e. n=0 or 1)
# Was 3 (borrow when n<3). Lowered to 2 (2026-07-23): when the asset has >= 2
# own actual D_top_to_next_bottom values, using its OWN median + IQR is more
# honest than borrowing from BTC + next-higher-cap alt -- the asset's own
# spread captures its genuine cycle length (e.g. SOL bottoms 418-504d after
# its top vs BTC's 364-406d). The borrow now only triggers when there are
# fewer than 2 own samples (n=0 or 1), in which case the asset's own data
# truly tells us nothing about timing spread.
#
# NOTE (2026-07-23 revision): The forward-range D_top_to_next_bottom borrow
# logic above is KEPT for archival/forward-range completeness, but the B4
# zone in build_alt_next_cycle_zones.py now uses a DIFFERENT model:
#   - timing: anchored on BTC's projected B4 date +/- alt's own historical
#     lag-vs-BTC-bottom (BTC drives the market; alts follow BTC).
#   - price: drawn from the asset's own prior-cycle drawdowns applied to
#     the observed C4 top (not borrowed from BTC).
# See build_alt_next_cycle_zones.py _alt_b4_zone() docstring for the new
# model.


def _load_timing_borrow_values() -> dict[str, list[float]]:
    """Load BTC and alt D_top_to_next_bottom values for timing borrow.

    Returns {asset: [cycle_values]} for BTC and all alts with actual data.
    """
    btc_df = pd.read_csv(INPUT_BTC, keep_default_na=False)
    alt_df = pd.read_csv(INPUT, keep_default_na=False)

    result: dict[str, list[float]] = {}

    # BTC values (always use actual)
    btc_vals = []
    for _, r in btc_df.iterrows():
        v = r.get("D_top_to_next_bottom")
        if v == "" or pd.isna(v):
            continue
        try:
            btc_vals.append(float(v))
        except (ValueError, TypeError):
            continue
    result["btc"] = btc_vals

    # Alt values (only actual sources)
    for asset in ["eth", "xrp", "sol"]:
        vals = []
        for _, r in alt_df[alt_df["asset"] == asset].iterrows():
            src = r["cycle_source"]
            if src not in ACTUAL_SOURCES:
                continue
            v = r.get("D_asset_top_to_next_bottom")
            if v == "" or pd.isna(v):
                continue
            try:
                vals.append(float(v))
            except (ValueError, TypeError):
                continue
        result[asset] = vals

    return result


def _borrowed_timing_median(
    asset: str,
    timing_values: dict[str, list[float]],
) -> float | None:
    """Compute borrowed median for D_top_to_next_bottom when n_actual < 3.

    Per user choice: median of (BTC values) + (next-higher-cap alt values).
    Hierarchy: SOL borrows from BTC+XRP, XRP borrows from BTC+ETH.
    """
    higher_cap = CAP_HIERARCHY.get(asset)
    if higher_cap is None:
        return None  # BTC doesn't borrow

    btc_vals = timing_values.get("btc", [])
    higher_vals = timing_values.get(higher_cap, [])
    combined = btc_vals + higher_vals
    if not combined:
        return None
    return float(np.median(combined))


def main() -> None:
    metrics = pd.read_csv(INPUT, keep_default_na=False)

    # Pre-load timing values for borrow logic
    timing_values = _load_timing_borrow_values()

    rows = []

    for asset in ASSETS:
        asset_rows = metrics[metrics["asset"] == asset]
        for stat in STATS:
            vals = {}      # cycle_id -> value
            sources = {}   # cycle_id -> cycle_source
            for _, r in asset_rows.iterrows():
                src = r["cycle_source"]
                if src == "missing":
                    continue
                v = r.get(stat)
                if v == "" or pd.isna(v):
                    continue
                try:
                    vals[r["cycle_id"]] = float(v)
                    sources[r["cycle_id"]] = src
                except (ValueError, TypeError):
                    continue

            n_actual = sum(1 for c in vals if sources[c] in ACTUAL_SOURCES)
            n_with_proxy = sum(1 for c in vals if sources[c] in USABLE_SOURCES)
            n = len(vals)
            # n is the count of populated values (with proxy if applicable)
            if n == 0:
                # Statistic has no data for this asset (e.g., D_asset_top_to_next_bottom
                # for ETH C4 which is still open). Emit an empty row for transparency.
                row_data = {
                    "asset": asset,
                    "statistic": stat,
                    "n_actual": 0,
                    "n_with_proxy": 0,
                    "mean": "",
                    "median": "",
                    "min": "",
                    "max": "",
                    "q25": "",
                    "q75": "",
                    "is_sensitive": False,
                    "n_with_proxy_note": "no data",
                }
                for c in CYCLES:
                    row_data[f"looco_{c}_mean"] = ""
                    row_data[f"looco_{c}_delta"] = ""
                rows.append(row_data)
                continue

            values = np.array(list(vals.values()), dtype=float)

            mean_val = float(np.mean(values))
            median_val = float(np.median(values))
            min_val = float(np.min(values))
            max_val = float(np.max(values))
            q25 = float(np.percentile(values, 25)) if n >= 2 else min_val
            q75 = float(np.percentile(values, 75)) if n >= 2 else max_val

            # Timing borrow for D_asset_top_to_next_bottom: when n_actual < 3,
            # override median with borrowed value from BTC + next-higher-cap alt.
            timing_borrowed = False
            timing_borrow_note = ""
            if (stat == "D_asset_top_to_next_bottom"
                    and n_actual < TIMING_BORROW_MIN_SAMPLES
                    and asset in CAP_HIERARCHY
                    and CAP_HIERARCHY[asset] is not None):
                borrowed = _borrowed_timing_median(asset, timing_values)
                if borrowed is not None:
                    median_val = borrowed
                    timing_borrowed = True
                    timing_borrow_note = (
                        f"; timing borrowed from BTC+{CAP_HIERARCHY[asset].upper()} "
                        f"(n_actual={n_actual} < {TIMING_BORROW_MIN_SAMPLES})"
                    )

            # LOOCO only when n >= 3 (per DESIGN.md §9.5.4 — small-sample rule)
            looco_means = {}
            looco_deltas = {}
            if n >= 3:
                for k in vals:
                    looco_vals = [v for c, v in vals.items() if c != k]
                    looco_mean = float(np.mean(looco_vals))
                    looco_means[k] = looco_mean
                    looco_deltas[k] = looco_mean - mean_val

            # Sensitivity flag: any LOOCO delta > 20% of |mean|
            is_sensitive = False
            if mean_val != 0 and n >= 3:
                for k, delta in looco_deltas.items():
                    if abs(delta) > 0.20 * abs(mean_val):
                        is_sensitive = True
                        break

            # Note for SOL/low-coverage cases
            if n_actual < 3 and n_with_proxy != n_actual:
                note = (f"n_actual={n_actual} augmented with ETH proxy to "
                        f"n_with_proxy={n_with_proxy}; projection exploratory"
                        f"{timing_borrow_note}")
            elif n_actual < 2:
                note = f"n_actual={n_actual}; projection not meaningful{timing_borrow_note}"
            elif n < 3:
                note = f"n={n} < 3; LOOCO unavailable{timing_borrow_note}"
            else:
                note = timing_borrow_note.lstrip("; ") if timing_borrow_note else ""

            row_data = {
                "asset": asset,
                "statistic": stat,
                "n_actual": n_actual,
                "n_with_proxy": n_with_proxy,
                "mean": mean_val,
                "median": median_val,
                "min": min_val,
                "max": max_val,
                "q25": q25,
                "q75": q75,
                "is_sensitive": is_sensitive,
                "n_with_proxy_note": note,
            }
            for c in CYCLES:
                if c in looco_means:
                    row_data[f"looco_{c}_mean"] = looco_means[c]
                    row_data[f"looco_{c}_delta"] = looco_deltas[c]
                else:
                    row_data[f"looco_{c}_mean"] = ""
                    row_data[f"looco_{c}_delta"] = ""
            rows.append(row_data)

    out = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)
    print(f"Wrote {OUTPUT} ({len(out)} rows)")
    # Print compact view
    print()
    print(out[["asset", "statistic", "n_actual", "n_with_proxy",
               "mean", "median", "min", "max",
               "is_sensitive", "n_with_proxy_note"]].to_string(index=False))


if __name__ == "__main__":
    main()

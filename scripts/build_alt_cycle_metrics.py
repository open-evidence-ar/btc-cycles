"""I-17.1: Build per-asset halving-cycle timing metrics.

Uses BTC's halving dates (H1-H4) as canonical cycle anchors and applies the
same Rule T / Rule B extrema detection to each of the 7 non-BTC panel assets
(ETH, SOL, XRP, SPX, NDX, DXY, TLT) within each BTC cycle's window.

For assets missing data in a given BTC cycle, the metric row is recorded
with `cycle_source="missing"` and empty values. For SOL (C2, C3) we apply
the ETH sequential-aging proxy per DESIGN.md §9.5.3:
  - SOL-C2 ← ETH-C1 (ETH's first-cycle, mult ~526)
  - SOL-C3 ← ETH-C2 (ETH's second-cycle, mult ~112)

Output: data/processed/alt_cycle_metrics.csv with one row per (asset x cycle)
combination where the asset has either actual data, a proxy, or is explicitly
recorded as missing.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

# Make scripts/ importable so we can reuse rule_t / rule_b
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_cycle_metrics import rule_t, rule_b  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
BTC_METRICS = PROCESSED_DIR / "btc_cycle_metrics.csv"
OUTPUT = PROCESSED_DIR / "alt_cycle_metrics.csv"

# Asset -> list of raw filename globs (tried in order; results merged).
# Crypto alts have both CDD (early data, frozen Oct 2025) and Yahoo (fresh
# through current date). We load both and keep the widest date range so that
# early cycle extrema (e.g. ETH-C2 pre-halving bottom Apr 2016 from CDD) and
# recent data (C4 top from Yahoo) are both available.
ASSET_FILES = {
    "eth": ["eth_cdd_*.csv", "eth_yahoo_*.csv"],
    "xrp": ["xrp_cdd_*.csv", "xrp_yahoo_*.csv"],
    "sol": ["sol_cdd_*.csv", "sol_yahoo_*.csv"],
    "mstr": ["mstr_yahoo_*.csv"],
    "wgmi": ["wgmi_yahoo_*.csv"],
    "riot": ["riot_yahoo_*.csv"],
    "mara": ["mara_yahoo_*.csv"],
    "spx": ["spx_yahoo_*.csv"],
    "ndx": ["ndx_yahoo_*.csv"],
    "dxy": ["dxy_yahoo_*.csv"],
    "tlt": ["tlt_yahoo_*.csv"],
    "gold": ["gold_yahoo_*.csv"],
}

# SOL proxy mapping: SOL-C2 inherits ETH-C1 timing; SOL-C3 inherits ETH-C2.
# Keyed by (asset, cycle_id) -> (proxy_asset, proxy_cycle_id)
PROXY_MAP = {
    ("sol", "C2"): ("eth", "C1"),
    ("sol", "C3"): ("eth", "C2"),
    ("wgmi", "C1"): ("mara", "C1"),
    ("wgmi", "C2"): ("mara", "C2"),
    ("wgmi", "C3"): ("mara", "C3"),
}

# Cycles to exclude per asset. MSTR pre-Aug-2020 (treasury pivot) history is
# NOT BTC-correlated, so C1 and C2 cycle metrics are garbage. Only C3 (post-
# pivot) and C4 are meaningful.
EXCLUDE_CYCLES = {
    "mstr": {"C1", "C2"},
}


def load_asset(asset: str) -> pd.DataFrame:
    """Return DataFrame with date (pd.Timestamp) + close (float), sorted asc.

    Loads from all matching glob patterns in ASSET_FILES[asset] and merges
    them.  When the same date appears in multiple sources, the row from the
    later-listed source wins (Yahoo overrides CDD) so that the freshest
    close prices are used while CDD's earlier rows fill historical gaps.
    """
    patterns = ASSET_FILES[asset]
    frames: list[pd.DataFrame] = []
    for pat in patterns:
        files = sorted(RAW_DIR.glob(pat))
        for f in files:
            df = pd.read_csv(f)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["date", "close"])
            frames.append(df[["date", "close"]])
    if not frames:
        raise FileNotFoundError(f"No raw file for {asset} under any pattern in {patterns}")
    merged = pd.concat(frames, ignore_index=True)
    # Deduplicate: later source wins on same date
    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def btc_halving_dates() -> dict[str, pd.Timestamp]:
    """Pull the 4 BTC halving dates from events.csv (canonical)."""
    events = pd.read_csv(ROOT / "data" / "events.csv", dtype=str)
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    out: dict[str, pd.Timestamp] = {}
    halvings = events[events["event_type"] == "halving"]
    for _, row in halvings.iterrows():
        cid_raw = str(row.get("cycle_id") or "")
        # cycle_id is like "H1" or "H2"; map to H1..H5
        if cid_raw.startswith("H"):
            out[cid_raw] = row["date"]
    return out


def detect_asset_cycle_extrema(
    asset_df: pd.DataFrame,
    h_date: pd.Timestamp,
    next_h_date: pd.Timestamp | None,
    cycle_id: str,
) -> dict | None:
    """Run Rule T + Rule B on the asset's data within the BTC cycle window.

    Returns None if asset has no data covering any part of the window.
    Returns dict with asset_local_top_date, asset_local_top_price,
    asset_next_bear_bottom_date, asset_next_bear_bottom_price,
    D_asset_prev_bottom_to_halving, D_asset_halving_to_top,
    D_asset_top_to_next_bottom, mult_asset_bottom_to_top,
    drawdown_asset_pct.
    All values None if undetermined.
    """
    # Check if the asset has any data within the cycle's relevant range
    # (halving-540d .. next_halving-30d roughly):
    search_start = h_date - timedelta(days=540)
    if next_h_date is not None:
        search_end = next_h_date - timedelta(days=30)
    else:
        search_end = h_date + timedelta(days=1500)
    covering = asset_df[(asset_df["date"] >= search_start) & (asset_df["date"] <= search_end)]
    if covering.empty:
        return None

    # Pre-halving bottom: min close in [search_start, h_date]
    pre_window = asset_df[(asset_df["date"] >= search_start) & (asset_df["date"] <= h_date)]
    if pre_window.empty:
        return None
    pre_b_idx = pre_window["close"].idxmin()
    pre_b_date = asset_df.loc[pre_b_idx, "date"]
    pre_b_price = float(asset_df.loc[pre_b_idx, "close"])

    # Local top via Rule T (uses next_halving as upper bound)
    t_res = rule_t(asset_df, h_date, next_h_date)
    if t_res is None:
        return None
    t_date, t_price, _, _ = t_res

    # Next bear bottom via Rule B
    b_res = rule_b(asset_df, t_date, next_h_date)
    if b_res is None:
        # C4 (open cycle) — bottom TBD; record top only
        nbb_date = None
        nbb_price = None
    else:
        nbb_date, nbb_price, _, _ = b_res
        # Plausibility check: if the data window extends well past the Rule B
        # pick (>= 90 days after) AND the bottom is implausibly shallow for a
        # cycle bear (drawdown < 65% passed the catastrophic-bear threshold),
        # treat it as a local low rather than the eventual cycle bottom.
        # Historical bottoms (B1-B3) all came >= 350 days after the top with
        # >= 76% drawdown. The memo's framework explicitly warns against
        # treating early-summer interim lows as cycle lows in the C4 context.
        # We apply a soft "not yet observed" filter to C4 only; C1-C3 bottoms
        # are canonical events so we keep Rule B's pick without re-litigating.
        if cycle_id == "C4":
            elapsed = (nbb_date - t_date).days
            if elapsed < 270:
                # Insufficient elapsed time for a cycle bottom; treated as
                # local-low only and flagged as open.
                nbb_date = None
                nbb_price = None

    def _d(a, b):
        if a is None or b is None:
            return None
        if pd.isna(a) or pd.isna(b):
            return None
        return int((a - b).days)

    d_pbh = _d(h_date, pre_b_date)
    d_ht = _d(t_date, h_date)
    d_tnb = _d(nbb_date, t_date) if nbb_date is not None else None

    mult = float(t_price / pre_b_price) if pre_b_price > 0 else None
    dd = float(1.0 - nbb_price / t_price) if (nbb_price is not None and t_price > 0) else None

    return {
        "asset_pre_halving_bottom_date": pre_b_date.strftime("%Y-%m-%d"),
        "asset_pre_halving_bottom_price": pre_b_price,
        "asset_local_top_date": t_date.strftime("%Y-%m-%d"),
        "asset_local_top_price": float(t_price),
        "asset_next_bear_bottom_date": nbb_date.strftime("%Y-%m-%d") if nbb_date is not None else "",
        "asset_next_bear_bottom_price": nbb_price if nbb_price is not None else "",
        "D_asset_prev_bottom_to_halving": d_pbh,
        "D_asset_halving_to_top": d_ht,
        "D_asset_top_to_next_bottom": d_tnb if d_tnb is not None else "",
        "mult_asset_bottom_to_top": mult,
        "drawdown_asset_pct": dd if dd is not None else "",
    }


def _fmt_dt(d):
    return d.strftime("%Y-%m-%d") if d is not None and pd.notna(d) else ""


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Load BTC halving dates
    h_dates = btc_halving_dates()

    # Load BTC cycle metrics for halving_date + pre_halving_bottom_date columns
    btc_m = pd.read_csv(BTC_METRICS, dtype={"halving_date": str})

    cycles = ["C1", "C2", "C3", "C4"]
    rows = []

    # Pre-load all asset dataframes (cached per asset)
    asset_dfs: dict[str, pd.DataFrame] = {}
    for asset in ASSET_FILES:
        asset_dfs[asset] = load_asset(asset)

    # Compute actual extrema for each (asset x cycle) — store in a lookup dict
    actual_results: dict[tuple[str, str], dict | None] = {}
    for asset in ASSET_FILES:
        df = asset_dfs[asset]
        for cid in cycles:
            # Map BTC cycle id to halving id: C1->H1, C2->H2, etc.
            h_id = f"H{int(cid[1:])}"
            h_date = h_dates.get(h_id)
            next_h_id = f"H{int(cid[1:]) + 1}"
            next_h_date = h_dates.get(next_h_id)
            if h_date is None:
                continue
            actual_results[(asset, cid)] = detect_asset_cycle_extrema(
                df, h_date, next_h_date, cid
            )

    # Now emit rows, applying proxy for SOL where actuals are missing
    for asset in ASSET_FILES:
        for cid in cycles:
            halving_id = f"H{int(cid[1:])}"
            h_date = h_dates.get(halving_id)
            next_halving_id = f"H{int(cid[1:]) + 1}"
            next_h_date = h_dates.get(next_halving_id)

            if h_date is None:
                continue

            # Skip excluded cycles (e.g. MSTR C1/C2 pre-treasury-pivot)
            if cid in EXCLUDE_CYCLES.get(asset, set()):
                continue

            actual = actual_results.get((asset, cid))
            proxy_key = (asset, cid)
            cycle_source = "actual"
            row_data = actual

            if actual is None and proxy_key in PROXY_MAP:
                proxy_asset, proxy_cycle = PROXY_MAP[proxy_key]
                proxy_actual = actual_results.get((proxy_asset, proxy_cycle))
                if proxy_actual is not None:
                    cycle_source = f"{proxy_asset}_proxy_{proxy_cycle}"
                    row_data = proxy_actual
                else:
                    cycle_source = "missing"

            if row_data is None:
                # Asset has no data and no proxy
                rows.append({
                    "asset": asset,
                    "cycle_id": cid,
                    "halving_date": _fmt_dt(h_date),
                    "next_halving_date": _fmt_dt(next_h_date),
                    "asset_first_data_date": _fmt_dt(asset_dfs[asset]["date"].min()),
                    "asset_last_data_date": _fmt_dt(asset_dfs[asset]["date"].max()),
                    "cycle_source": "missing",
                    "asset_pre_halving_bottom_date": "",
                    "asset_pre_halving_bottom_price": "",
                    "asset_local_top_date": "",
                    "asset_local_top_price": "",
                    "asset_next_bear_bottom_date": "",
                    "asset_next_bear_bottom_price": "",
                    "D_asset_prev_bottom_to_halving": "",
                    "D_asset_halving_to_top": "",
                    "D_asset_top_to_next_bottom": "",
                    "mult_asset_bottom_to_top": "",
                    "drawdown_asset_pct": "",
                })
                continue

            # For C4 actuals the bottom is open; mark accordingly
            if cid == "C4" and cycle_source == "actual":
                if row_data.get("asset_next_bear_bottom_date") == "":
                    cycle_source = "actual_C4_open"

            rows.append({
                "asset": asset,
                "cycle_id": cid,
                "halving_date": _fmt_dt(h_date),
                "next_halving_date": _fmt_dt(next_h_date),
                "asset_first_data_date": _fmt_dt(asset_dfs[asset]["date"].min()),
                "asset_last_data_date": _fmt_dt(asset_dfs[asset]["date"].max()),
                "cycle_source": cycle_source,
                **row_data,
            })

    out_df = pd.DataFrame(rows)

    # Ensure stable column order
    cols = [
        "asset", "cycle_id", "halving_date", "next_halving_date",
        "asset_first_data_date", "asset_last_data_date",
        "cycle_source",
        "asset_pre_halving_bottom_date", "asset_pre_halving_bottom_price",
        "asset_local_top_date", "asset_local_top_price",
        "asset_next_bear_bottom_date", "asset_next_bear_bottom_price",
        "D_asset_prev_bottom_to_halving", "D_asset_halving_to_top",
        "D_asset_top_to_next_bottom",
        "mult_asset_bottom_to_top", "drawdown_asset_pct",
    ]
    out_df = out_df[cols]
    out_df.to_csv(OUTPUT, index=False)
    print(f"Wrote {OUTPUT} ({len(out_df)} rows)")
    print()
    print("Coverage summary by asset:")
    summary = out_df.groupby("asset")["cycle_source"].apply(
        lambda s: ", ".join(f"{c}={n}" for c, n in s.value_counts().items())
    )
    for asset, line in summary.items():
        print(f"  {asset}: {line}")


if __name__ == "__main__":
    main()

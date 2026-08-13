"""I-17.3: Per-asset next-cycle zone map for BTC's C5 (anchored on H5=2028-04-01).

For each of the 7 non-BTC panel assets, compute:
  - Accumulation zone: anchored on H5 - D_asset_prev_bottom_to_halving (median),
                        IQR/min-max outer band.
  - Distribution zone: H5 + q25/q75 of D_asset_halving_to_top.
  - Exit zone: H5 + median(D_asset_halving_to_top) + q25/q75 of
                D_asset_top_to_next_bottom.

Price-band projection (the **2-stage projection model**):

  Stage 1 -- project the asset's NEXT bear bottom (asset-B4-equivalent,
             i.e. the post-C4-top bear bottom that anchors C5) from the
             asset's bear-bottom-to-bear-bottom price ratio series.
             Requires n_bear_bottoms >= 4 (n_ratios >= 3).
  Stage 2 -- project C5 top from the projected bear bottom using the asset's
             bottom-to-top multiplier power-law fit. Cross-check: B4 is also
             derivable via C4_top * (1 - drawdown_C4); disagreement > 15%
             between Stage 1 and Stage 2 cross-check triggers the flag column
             `cross_check_ok = False` and the band is widened to contain both.

  Fallback hierarchy when Stage 1 inapplicable (e.g. XRP with n<4 bottoms):
    1) Anchor C5 top on the asset's most recent observed bear bottom price
       directly (Stage 2 only) and tag the row accordingly in
       `compression_fit_used = 'stage2_only_anchored_on_observed_b'`.
    2) If multipliers also insufficient (n<3), use naive median across
       available cycles, marked `naive_median` in `compression_fit_used`.

This explicit policy means the published C5 projection for ETH (n_rbottoms=3,
n_mults=3) is a true 2-stage fit; for SOL (own dd/mult series dominated by its
C3 first-cycle monster, mult=502x) the projection borrows ETH's per-cycle
ratios aligned by asset-cycle ordinal (`borrowed_2_stage_from_ETH`) so the
row carries that mode tag and the reader can see exactly which assumption
was made.

Output: data/processed/alt_next_cycle_zones.csv (>=6 assets x 3 zones=18 rows,
      typically 21 rows = 7 assets x 3 zones; SOL when n_with_proxy < 2 for
      required stats: explicit note).
"""

import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_charts import (
    two_stage_cycle_projection,
    two_stage_projection_with_observed_c4,
    two_stage_with_observed_c4_borrowed,
    fit_cycle_compression,
    project_bear_bottom,
)

# Parent asset's relative shape used when an alt has insufficient own history.
# Source: data/processed/btc_cycle_metrics.csv (mult/dd at C1, C2, C3).
# Hierarchy by market cap (smaller alt borrows from larger): SOL->XRP->ETH->BTC.
# All crypto assets that follow BTC's halving-cycle thesis can borrow from BTC's
# fit since BTC has the deepest, cleanest cycle history.
BTC_PARENT_DDS = [0.848579, 0.834293, 0.766634]
BTC_PARENT_MULTS = [526.516279, 112.20924, 21.639654]
BTC_PARENT_LABEL = 'BTC'

INPUT_METRICS = ROOT / "data" / "processed" / "alt_cycle_metrics.csv"
INPUT_FWD = ROOT / "data" / "processed" / "alt_forward_ranges.csv"
INPUT_EVENTS = ROOT / "data" / "events.csv"
OUTPUT = ROOT / "data" / "processed" / "alt_next_cycle_zones.csv"
RAW_DIR = ROOT / "data" / "raw"

H5_DATE = None  # set inside main() from events.csv
_GOLD_SUPPORT_BAND = None  # set inside main() from latest gold raw snapshot

ASSETS = ["eth", "xrp", "sol", "mstr", "wgmi", "spx", "ndx", "dxy", "tlt", "gold"]
MACRO_ASSETS = {"spx", "ndx", "dxy", "tlt", "gold"}
# Assets forced into the borrowed-2-stage-from-BTC path, regardless of how
# many own bear-bottoms the detector finds. MSTR pre-Aug-2020 (treasury pivot)
# history is NOT BTC-correlated, so its "own" bear-bottom chain is garbage
# for cycle fitting. Treat it like SOL/XRP: borrow BTC's shape, anchor on
# own observed C4 top.
# NOTE (2026-08-04): MSTR removed from this set — it now uses the
# naive_median_own_dd path above (n_dds=2, n_mults=2) since BTC's borrowed
# drawdown compression curve is too shallow for MSTR's higher observed
# drawdowns (C3 89.3%, C4 82.6% vs BTC projected 76.3%), producing a B4
# band above the actual price action. Only WGMI remains (its multiplier
# series [5.1, 1.6, 190.2] is non-monotonic and the 190.2x outlier
# dominates the median; borrowed shape is still less broken than own-data
# median for WGMI until a better filter is built).
FORCE_BORROW_ASSETS = {"wgmi"}
STATS_REQUIRED = {
    "D_asset_prev_bottom_to_halving",
    "D_asset_halving_to_top",
    "D_asset_top_to_next_bottom",
    "mult_asset_bottom_to_top",
    "drawdown_asset_pct",
}


def _get_fwd_row(fwd_df, asset, stat):
    sel = fwd_df[(fwd_df["asset"] == asset) & (fwd_df["statistic"] == stat)]
    if sel.empty:
        return None
    return sel.iloc[0]


def _num(v):
    if v is None or pd.isna(v) or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _load_btc_projected_b4_center():
    """Load BTC's projected B4 date (center of bear_bottom base band) from
    next_cycle_zones.csv. This is the BTC driver timing — alts should lag
    BTC by their own historical alt-vs-BTC lag to derive their B4 date.

    Returns:
        pd.Timestamp or None
    """
    btc_zones_path = ROOT / "data" / "processed" / "next_cycle_zones.csv"
    if not btc_zones_path.exists():
        return None
    df = pd.read_csv(btc_zones_path, keep_default_na=False)
    bb = df[df["zone"] == "bear_bottom"]
    if bb.empty:
        return None
    bs = bb.iloc[0].get("base_start", "")
    be = bb.iloc[0].get("base_end", "")
    if not bs or not be:
        return None
    try:
        return pd.to_datetime(bs) + (pd.to_datetime(be) - pd.to_datetime(bs)) / 2
    except Exception:
        return None


def _load_btc_b4_price():
    """Load BTC's projected B4 price (center + band) from next_cycle_zones.csv.

    Returns a dict with keys: 'b4_center', 'b4_low', 'b4_high', 'b3_observed',
    'b4_b3_ratio', 'b4_b3_ratio_low', 'b4_b3_ratio_high', or None.
    """
    btc_zones_path = ROOT / "data" / "processed" / "next_cycle_zones.csv"
    if not btc_zones_path.exists():
        return None
    df = pd.read_csv(btc_zones_path, keep_default_na=False)
    bb = df[df["zone"] == "bear_bottom"]
    if bb.empty:
        return None
    row = bb.iloc[0]
    try:
        b4_center = float(row.get("anchor_price") or row.get("projected_b4_stage1"))
        b4_low = float(row.get("price_low"))
        b4_high = float(row.get("price_high"))
    except (KeyError, ValueError, TypeError):
        return None
    # Load BTC B3 (last confirmed bear bottom) from btc_cycle_metrics.csv
    btc_metrics_path = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
    if not btc_metrics_path.exists():
        return None
    btc = pd.read_csv(btc_metrics_path, keep_default_na=False)
    # B3 is the post-C3 bottom = BTC next_bear_bottom_price at cycle C3
    c3_row = btc[btc["cycle_id"] == "C3"]
    if c3_row.empty:
        return None
    b3 = _num(c3_row.iloc[0].get("next_bear_bottom_price"))
    if b3 is None or b3 <= 0:
        return None
    out = {
        'b4_center': b4_center,
        'b4_low': b4_low,
        'b4_high': b4_high,
        'b3_observed': float(b3),
        'b4_b3_ratio': b4_center / b3,
        'b4_b3_ratio_low': b4_low / b3,
        'b4_b3_ratio_high': b4_high / b3,
    }
    return out
 

def _gold_support_band():
    """Compute gold's bull market support band: 20-month SMA + 21-month EMA
    on monthly closes, evaluated on the most recent monthly close available.

    This is the gold-specific valuation cross-check from docs/gold_seasonality.md
    (validated against local gold data: 2026-07-31 20-mo SMA = $3,813.13,
    21-mo EMA = $3,829.66). Unlike SPX/NDX/DXY/TLT which use drawdown
    power-laws for B4, gold's empirical floor is the SMA/EMA band — it gets
    its own two columns (support_band_low, support_band_high) in
    alt_next_cycle_zones.csv for the bear_bottom row only.

    Returns:
        dict with 'band_low' (min of SMA/EMA), 'band_high' (max), 'date',
        or None if no gold raw snapshot exists.
    """
    cands = sorted(RAW_DIR.glob("gold_yahoo_*.csv"))
    if not cands:
        return None
    df = pd.read_csv(cands[-1])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    if df.empty:
        return None
    # Monthly resample: month-end close
    monthly = df.set_index("date")["close"].resample("ME").last().dropna()
    if len(monthly) < 21:
        return None
    sma20 = monthly.tail(20).mean()
    ema21 = monthly.ewm(span=21, adjust=False).mean().iloc[-1]
    last_date = monthly.index[-1].strftime("%Y-%m-%d")
    return {
        "band_low": float(min(sma20, ema21)),
        "band_high": float(max(sma20, ema21)),
        "sma20": float(sma20),
        "ema21": float(ema21),
        "date": last_date,
    }


def _alt_vs_btc_lag_days(metrics_df, asset):
    """Compute the alt's historical lag vs BTC's bear bottom (in days).

    For each cycle where both the alt and BTC have a detected bear bottom,
    lag = alt_bottom_date - btc_bottom_date. A negative lag means the alt
    bottomed BEFORE BTC (the C3 pattern: ETH/XRP -156d, SOL +38d).

    Returns:
        list[float]: lag in days for each cycle with data (>= 1 sample)
    """
    btc_path = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
    if not btc_path.exists():
        return []
    btc = pd.read_csv(btc_path, keep_default_na=False)
    lags = []
    alt_rows = metrics_df[metrics_df["asset"] == asset]
    for _, alt_row in alt_rows.iterrows():
        alt_bot = alt_row.get("asset_next_bear_bottom_date", "")
        cycle = alt_row.get("cycle_id", "")
        if not alt_bot:
            continue
        btc_row = btc[btc["cycle_id"] == cycle]
        if btc_row.empty:
            continue
        btc_bot = btc_row.iloc[0].get("next_bear_bottom_date", "")
        if not btc_bot:
            continue
        try:
            lag = (pd.to_datetime(alt_bot) - pd.to_datetime(btc_bot)).days
            lags.append(float(lag))
        except Exception:
            continue
    return lags


def _alt_prior_drawdowns(metrics_df, asset):
    """Return list of the alt's own historical drawdowns (as fraction, 0..1)
    from each cycle where the bear bottom was detected. Excludes the current
    C4 cycle (whose bottom is what we're projecting in B4).

    Used for the alt B4 price-band model: B4 price = C4 top * (1 - dd_n),
    where dd_n is fit from the asset's own prior drawdowns (power-law if >= 3
    samples; min-max envelope if 1-2 samples).
    """
    rows = metrics_df[metrics_df["asset"] == asset]
    dds = []
    for _, r in rows.iterrows():
        if r.get("cycle_id") == "C4":  # exclude current cycle
            continue
        dd = r.get("drawdown_asset_pct", "")
        v = _num(dd)
        if v is not None and math.isfinite(v) and v > 0:
            dds.append(float(v))
    return dds


def _project_alt_b4_price(c4_top_price, own_drawdowns, borrowed_btc_drawdowns):
    """Project alt B4 USD price band from drawdowns applied to C4 top.

    Two paths:
    (a) If len(own_drawdowns) >= 2: use own historical drawdowns as the band
        envelope. center = median of own drawdowns, low = min(dd)*C4top
        (deepest drawdown => lowest price), high = max(dd)*C4top (shallowest
        drawdown => highest price).
    (b) If len(own_drawdowns) < 2: fall back to BTC's own historical drawdowns
        (the parent driver shape) to get a reasonable envelope.

    Args:
        c4_top_price: observed C4 top price for this alt (USD)
        own_drawdowns: list of alt's own prior-cycle drawdowns (fractions)
        borrowed_btc_drawdowns: BTC's own historical drawdowns (fallback)

    Returns:
        dict with b4_center, b4_price_low, b4_price_high, model_note
    """
    if c4_top_price is None or c4_top_price <= 0:
        return None

    use_own = len(own_drawdowns) >= 2
    draws = own_drawdowns if use_own else borrowed_btc_drawdowns
    src_label = "own" if use_own else "BTC (fallback)"

    if not draws:
        return None

    # Drawdown envelope: deepest (max dd) -> lowest price, shallowest (min dd) ->
    # highest price. Center = median drawdown.
    dd_min = min(draws)  # shallowest drawdown -> highest price
    dd_max = max(draws)  # deepest drawdown -> lowest price
    dd_med = float(np.median(draws))

    b4_price_high = c4_top_price * (1.0 - dd_min)  # shallowest -> highest
    b4_price_low = c4_top_price * (1.0 - dd_max)   # deepest -> lowest
    b4_center = c4_top_price * (1.0 - dd_med)

    # Sanity: low >= 0, high >= low, both below C4 top
    b4_price_low = max(0.0, min(b4_price_low, b4_price_high))
    b4_price_high = max(b4_price_low, min(b4_price_high, c4_top_price))

    return {
        "b4_center": float(b4_center),
        "b4_price_low": float(b4_price_low),
        "b4_price_high": float(b4_price_high),
        "dd_min": float(dd_min),
        "dd_max": float(dd_max),
        "dd_med": float(dd_med),
        "src": src_label,
        "n_drawdowns": len(draws),
    }


def _fmt_usd(v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "N/A"
    if v >= 1e6:
        return "$%.2fM" % (v / 1e6)
    if v >= 1e3:
        return "$%.1fk" % (v / 1e3)
    return "$%.2f" % v


def _extract_bear_bottom_chain(metrics_df, asset, exclude_last_cycle_post=False):
    """Extract the per-asset series of consecutive BTC-cycle-aligned
    bear bottoms: [pre_H1_bottom, post_H1_bottom (=pre_H2_bottom),
    post_H2_bottom (=pre_H3_bottom), ...].

    For each cycle, asset_pre_halving_bottom_price is the bear bottom
    entering that cycle, and asset_next_bear_bottom_price is the bear
    bottom exiting it. Conceptually they chain:
        pre_C1 -> post_C1 == pre_C2 -> post_C2 == pre_C3 -> ...
    In practice the metrics CSV sometimes records pre_C4 != post_C3
    (e.g. ETH: post_C3 = $995.26 in June 2022, pre_C4 = $1,102.6 in
    Nov 2022 -- a different and slightly higher low). When this happens,
    BOTH are included in the chain so the Stage 1 ratio fit can see the
    extra observation.

    Proxies (e.g. SOL-C3 with ETH_proxy_C2) are excluded -- the chain
    must represent the asset's own observed bottoms.

    If ``exclude_last_cycle_post`` is True, the post-bottom of the LAST
    cycle in the data is excluded.  This is used for ETH, whose C4
    post-bottom (post-cycle-4 bear low) is still unconfirmed in the
    user's framework -- the metrics CSV may contain a detected local
    low, but it should NOT be treated as the definitive B4 bottom.
    """
    rows = metrics_df[(metrics_df["asset"] == asset) &
                      (metrics_df["cycle_source"] != "missing")]
    rows = rows.sort_values("cycle_id")
    # Build a list of (cycle_id, pre_bottom, post_bottom) excluding proxies.
    triple = []
    for _, r in rows.iterrows():
        if "proxy" in r["cycle_source"]:
            continue
        pre = _num(r.get("asset_pre_halving_bottom_price"))
        post = _num(r.get("asset_next_bear_bottom_price"))
        triple.append((r["cycle_id"], pre, post))

    if not triple:
        return [], []

    # Optionally exclude the post-bottom of the last cycle (unconfirmed).
    if exclude_last_cycle_post and triple:
        last_cid = triple[-1][0]
        triple[-1] = (last_cid, triple[-1][1], None)

    # Stitch bottoms in chronological order, deduping consecutive duplicates.
    # For each cycle in order: emit pre_bottom (if non-null), then post_bottom
    # (if non-null AND distinct from the immediately preceding emitted price).
    seen = []
    for cid, pre, post in triple:
        if pre is not None and pre > 0:
            if not seen or abs(seen[-1][0] - pre) / max(pre, 1e-9) > 1e-6:
                seen.append((pre, cid))
        if post is not None and post > 0:
            if not seen or abs(seen[-1][0] - post) / max(post, 1e-9) > 1e-6:
                seen.append((post, cid))

    bottoms = [s[0] for s in seen]
    cycles = [s[1] for s in seen]
    return bottoms, cycles


def _extract_btc_bear_bottom_chain():
    """Extract BTC's confirmed post-bottom chain from btc_cycle_metrics.csv.

    Returns a dict keyed by cycle_id ('C1','C2','C3') -> post-bottom price.
    C4 is excluded (its post-bottom B4 is what we're projecting).
    """
    btc_metrics_path = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
    if not btc_metrics_path.exists():
        return {}
    btc = pd.read_csv(btc_metrics_path, keep_default_na=False)
    out = {}
    for _, r in btc.iterrows():
        cid = r.get("cycle_id", "")
        if not cid.startswith("C") or cid == "C4":
            continue
        post = _num(r.get("next_bear_bottom_price"))
        if post is not None and post > 0:
            out[cid] = float(post)
    return out


def _project_eth_btc_ror(metrics_df, btc_b4_info, ror_cycle='C2'):
    """Project ETH's B4 bear bottom via the ETH/BTC ratio-of-ratios method.

    Background:  ETH's own bear-bottom ratio series is non-monotonic and
    includes an unconfirmed C4 post-bottom, making a direct power-law fit
    degenerate.  Instead we:
      1. For each shared cycle where both ETH and BTC have a confirmed
         post-bottom, compute the per-cycle ratio = post_bottom / pre_bottom
         (where pre_bottom is the asset's pre_halving_bottom_price, i.e. the
         bottom at the START of that cycle, and post_bottom is the bottom at
         the END of that cycle).
      2. The ratio-of-ratios (ETH_ratio / BTC_ratio) at each cycle measures
         ETH's relative ratio-strength vs BTC.
      3. Apply BTC's projected B4/B3 ratio (from next_cycle_zones.csv, fit on
         BTC's clean 3-ratio series) scaled by the chosen ror.

    Inputs:
      metrics_df:      alt_cycle_metrics.csv as DataFrame
      btc_b4_info:     dict from _load_btc_b4_price() with BTC B4 + B3 data
      ror_cycle:       which cycle's ratio-of-ratios to use as the multiplier
                       ('C2' = conservative, ~$1,716; 'C3' = aggressive, ~$6,448)

    Returns:
      dict with available, mode, projected_b4, b4_band_low, b4_band_high,
      ror_used, ror_cycle_label, fit_note, and the underlying stats.
    """
    # ETH per-cycle pre/post bottoms (C4 post excluded as unconfirmed)
    eth_rows = metrics_df[(metrics_df["asset"] == "eth") &
                          (~metrics_df["cycle_source"].str.contains("proxy", na=False)) &
                          (metrics_df["cycle_source"] != "missing")].sort_values("cycle_id")
    # Build cycle -> (pre_bottom, post_bottom) for ETH
    eth_cycle_data = {}
    for _, r in eth_rows.iterrows():
        cid = r.get("cycle_id", "")
        pre = _num(r.get("asset_pre_halving_bottom_price"))
        post = _num(r.get("asset_next_bear_bottom_price"))
        if cid == "C4":
            post = None  # exclude unconfirmed C4 post-bottom
        eth_cycle_data[cid] = (pre, post)

    # BTC per-cycle pre/post bottoms (C4 post excluded)
    btc_metrics_path = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
    if not btc_metrics_path.exists():
        return {'available': False, 'mode': 'no_btc_metrics',
                'fit_note': 'btc_cycle_metrics.csv not found.'}
    btc = pd.read_csv(btc_metrics_path, keep_default_na=False)
    btc_cycle_data = {}
    for _, r in btc.iterrows():
        cid = r.get("cycle_id", "")
        pre = _num(r.get("pre_halving_bottom_price"))
        post = _num(r.get("next_bear_bottom_price"))
        if cid == "C4":
            post = None
        btc_cycle_data[cid] = (pre, post)

    # Compute per-cycle ratio = post / pre for ETH and BTC, and ror = ETH/BTC
    ror_values = {}
    eth_ratios = {}
    btc_ratios = {}
    for cn in ["C1", "C2", "C3", "C4"]:
        eth_pre, eth_post = eth_cycle_data.get(cn, (None, None))
        btc_pre, btc_post = btc_cycle_data.get(cn, (None, None))
        if eth_pre and eth_post and btc_pre and btc_post:
            er = eth_post / eth_pre
            br = btc_post / btc_pre
            eth_ratios[cn] = er
            btc_ratios[cn] = br
            if br > 0:
                ror_values[cn] = er / br

    if ror_cycle not in ror_values:
        if not ror_values:
            return {'available': False, 'mode': 'no_ror_data',
                    'fit_note': 'No aligned ETH/BTC ratio-of-ratios data.'}
        # Fall back to the earliest available
        ror_cycle = sorted(ror_values.keys())[0]

    ror = ror_values[ror_cycle]

    # ETH last confirmed post-bottom = C3 post-bottom
    eth_c3_pre, eth_c3_post = eth_cycle_data.get("C3", (None, None))
    eth_last = eth_c3_post
    if eth_last is None:
        # Fallback: take the last confirmed post bottom available
        for cn in ["C4", "C3", "C2", "C1"]:
            _, p = eth_cycle_data.get(cn, (None, None))
            if p:
                eth_last = p
                break
    if eth_last is None:
        return {'available': False, 'mode': 'no_eth_bottom',
                'fit_note': 'No confirmed ETH post-bottom.'}

    # Project ETH B4 via BTC B4/B3 ratio * ror
    btc_b4_ratio = btc_b4_info['b4_b3_ratio']
    btc_b4_ratio_low = btc_b4_info['b4_b3_ratio_low']
    btc_b4_ratio_high = btc_b4_info['b4_b3_ratio_high']

    eth_b4_ratio = btc_b4_ratio * ror
    eth_b4_ratio_low = btc_b4_ratio_low * ror
    eth_b4_ratio_high = btc_b4_ratio_high * ror

    b4_center = eth_last * eth_b4_ratio
    b4_band_low = eth_last * eth_b4_ratio_low
    b4_band_high = eth_last * eth_b4_ratio_high

    # Fit note
    eth_chain_str = "[" + ", ".join(
        f"{cn}:pre={_fmt_usd(eth_cycle_data[cn][0]) if eth_cycle_data[cn][0] else 'NA'},"
        f"post={_fmt_usd(eth_cycle_data[cn][1]) if eth_cycle_data[cn][1] else 'NA'}"
        for cn in sorted(eth_cycle_data.keys())) + "]"
    btc_chain_str = "[" + ", ".join(
        f"{cn}:pre={_fmt_usd(btc_cycle_data[cn][0]) if btc_cycle_data[cn][0] else 'NA'},"
        f"post={_fmt_usd(btc_cycle_data[cn][1]) if btc_cycle_data[cn][1] else 'NA'}"
        for cn in sorted(btc_cycle_data.keys())) + "]"
    ror_str = ", ".join(
        f"{cn}: {eth_ratios.get(cn, 0):.2f}/{btc_ratios.get(cn, 0):.2f}={ror_values.get(cn, 0):.3f}"
        for cn in sorted(ror_values.keys()))

    fit_note = (
        f"mode=btc_ratio_of_ratios; "
        f"ETH per-cycle (pre,post): {eth_chain_str}. "
        f"BTC per-cycle (pre,post): {btc_chain_str}. "
        f"Per-cycle ratios (ETH/BTC): {ror_str}. "
        f"Using ror at {ror_cycle} = {ror:.3f}. "
        f"BTC B4/B3 ratio = {btc_b4_ratio:.2f}x "
        f"(band {btc_b4_ratio_low:.2f}x-{btc_b4_ratio_high:.2f}x from next_cycle_zones.csv). "
        f"ETH B4 = ETH_C3 ({_fmt_usd(eth_last)}) * {btc_b4_ratio:.2f} * {ror:.3f} "
        f"= {_fmt_usd(b4_center)} "
        f"(band {_fmt_usd(b4_band_low)} - {_fmt_usd(b4_band_high)})."
    )

    return {
        'available': True,
        'mode': 'btc_ratio_of_ratios',
        'projected_b4': b4_center,
        'b4_band_low': b4_band_low,
        'b4_band_high': b4_band_high,
        'b4_b3_ratio_used': eth_b4_ratio,
        'ror_used': ror,
        'ror_cycle_label': ror_cycle,
        'eth_ratios': eth_ratios,
        'btc_ratios': btc_ratios,
        'ror_values': ror_values,
        'eth_c3_bottom': eth_last,
        'btc_b4_ratio': btc_b4_ratio,
        'fit_note': fit_note,
    }


def _extract_multiplier_series(metrics_df, asset):
    """Extract the per-asset per-cycle bottom-to-top multiplier series.

    Returns (values, cycle_indices) for cycles where cycle_source != 'missing'
    and the multiplier is non-null. Proxies are excluded (the model fits the
    asset's own bottom-to-top behavior, not an asset-proxy's).
    """
    rows = metrics_df[(metrics_df["asset"] == asset) &
                      (metrics_df["cycle_source"] != "missing")]
    rows = rows.sort_values("cycle_id")
    mults = []
    idxs = []
    for _, r in rows.iterrows():
        if "proxy" in r["cycle_source"]:
            continue
        m = _num(r.get("mult_asset_bottom_to_top"))
        if m is not None and m > 0:
            mults.append(m)
            idxs.append(int(r["cycle_id"][1:]))
    return mults, idxs


def _extract_drawdown_series(metrics_df, asset):
    rows = metrics_df[(metrics_df["asset"] == asset) &
                      (metrics_df["cycle_source"] != "missing")]
    rows = rows.sort_values("cycle_id")
    dds = []
    idxs = []
    for _, r in rows.iterrows():
        if "proxy" in r["cycle_source"]:
            continue
        d = _num(r.get("drawdown_asset_pct"))
        if d is not None and d > 0:
            dds.append(d)
            idxs.append(int(r["cycle_id"][1:]))
    return dds, idxs


def _project_asset_chain(metrics_df, asset, is_macro):
    """Run the 2-stage projection for one asset and return a dict.

    For crypto (is_macro=False):
      Uses the observed-C4-top variant. The asset's C4 top is read from
      alt_cycle_metrics.csv and treated as canonical per the user's framework
      ("C4 is already in for all cryptos by time range").
      Returns:
        mode = '2_stage_with_observed_c4'   when Stage 1 fit succeeds + cross-check
        mode = 'stage2_only_observed_c4'    when Stage 1 fail / n_bear_bottoms<4,
                                            anchored on observed C4 top -> B4
                                            via drawdown path
        mode = 'naive_median'               when multipliers also insufficient

    For macro (is_macro=True) -- I-19 revision:
      Macros DO pivot around BTC halving events (every observed macro top
      falls 0-3 years after each halving; see docs/blockers/I-19-macro-2stage.md
      for the historical evidence). They are now routed through the SAME
      2-stage borrowed-shape machinery as crypto alts with insufficient own
      history. The asset's own observed C4 top is the anchor; the relative
      shape (drawdown depth at C4, multiplier at C5) is fit on the macro's
      OWN dd/mult series (n=3 from C1-C3, since C4 bottoms are still open
      for SPX/NDX/TLT). Economic floors are relaxed to macro-appropriate
      values (dd_floor=0.05, mult_floor=1.05) since macros drawdown 8-50%
      and multiply 1.1x-2.8x, NOT the crypto 50%+/2x+.
      Returns:
        mode = 'macro_2_stage_own_shape'  (shape fit on macro's own series)
        mode = 'macro_not_cycle_tied'     (no-data fallback: no C4 top or
                                           no own dd/mult samples)
    """
    bottoms, _ = _extract_bear_bottom_chain(metrics_df, asset)
    mults, _ = _extract_multiplier_series(metrics_df, asset)
    dds, _ = _extract_drawdown_series(metrics_df, asset)

    # Pull the asset's observed C4 top from alt_cycle_metrics.csv rows
    # where cycle_id == 'C4'.
    c4_rows = metrics_df[(metrics_df["asset"] == asset)
                          & (metrics_df["cycle_id"] == "C4")
                          & (metrics_df["cycle_source"] != "missing")]
    observed_c4_top_price = None
    observed_c4_top_date = None
    if not c4_rows.empty:
        r = c4_rows.iloc[0]
        p = _num(r.get("asset_local_top_price"))
        d = r.get("asset_local_top_date") or ""
        if p is not None and d:
            observed_c4_top_price = p
            observed_c4_top_date = d

    # ==================== SOL: BORROW ETH SHAPE, ORDINAL-ALIGNED ====================
    # (2026-08-11) SOL's own dd/mult series are dominated by its first-cycle
    # monster move (C3 mult = 502x), so its own naive-median path publishes an
    # absurd C5 band ($264 - $31,252 -- the "wild multiplier spread [502, 27]"
    # problem). Per the user's framework SOL should borrow ETH's per-cycle
    # ratios ALIGNED BY ASSET-CYCLE ORDINAL, not by BTC cycle number:
    #   SOL C3 (its 1st real cycle)  ~ ETH C2 (its 1st real cycle)
    #   SOL C4 (its 2nd real cycle)  ~ ETH C3 (its 2nd)
    #   SOL C5 (its 3rd, to project) ~ ETH C4 (its 3rd, observed)
    # So we evaluate ETH's fitted dd/mult curves at ordinal idx=3 (ETH's own
    # 3rd-cycle ratios: dd=0.6873, mult=7.12) rather than extrapolating to
    # SOL's own noisy series. Anchor stays SOL's observed C4 top ($261.82).
    if (asset == "sol" and not is_macro
            and observed_c4_top_price is not None):
        eth_dds, _ = _extract_drawdown_series(metrics_df, "eth")
        eth_mults, _ = _extract_multiplier_series(metrics_df, "eth")
        if len(eth_dds) >= 3 and len(eth_mults) >= 3:
            proj = two_stage_with_observed_c4_borrowed(
                observed_c4_top_price=observed_c4_top_price,
                observed_c4_top_date=observed_c4_top_date,
                parent_dds=eth_dds,
                parent_mults=eth_mults,
                parent_label="ETH",
                dd_project_to_idx=3,
                mult_project_to_idx=3,
                dd_c5_project_to_idx=3,
            )
            fit_note = (
                f"mode=borrowed_2_stage_from_ETH; "
                f"SOL's own dd/mult series are dominated by its C3 first-cycle "
                f"monster (mult=502x), so own naive-median would publish an "
                f"absurd C5 band. Borrowed ETH's per-cycle shape aligned by "
                f"ASSET-CYCLE ORDINAL (not BTC cycle number): SOL C3~ETH C2, "
                f"SOL C4~ETH C3, SOL C5(projected)~ETH C4 (observed). "
                f"Parent ETH dds=[" + ", ".join("%.3f" % d for d in eth_dds) + "], "
                f"mults=[" + ", ".join("%.2f" % m for m in eth_mults) + "]. "
                f"Projected dd at ordinal 3 = {proj['c4_dd']:.3f} "
                f"-> B4 = {_fmt_usd(proj['b4_stage1'])} "
                f"(band {_fmt_usd(proj['b4_band_low'])} - {_fmt_usd(proj['b4_band_high'])}). "
                f"Projected C5 multiplier = {proj['mult_c5']:.2f} -> "
                f"C5 top = {_fmt_usd(proj['c5_top'])} "
                f"(band {_fmt_usd(proj['c5_top_band_low'])} - "
                f"{_fmt_usd(proj['c5_top_band_high'])}). "
                f"B5 (post-C5 bottom) = {_fmt_usd(proj['b5_center'])} "
                f"(band {_fmt_usd(proj['b5_band_low'])} - {_fmt_usd(proj['b5_band_high'])})."
            )
            return {
                'available': True,
                'mode': 'borrowed_2_stage_from_ETH',
                'mult_proj': proj['mult_c5'],
                'mult_band_low': proj['mult_c5_band_low'],
                'mult_band_high': proj['mult_c5_band_high'],
                'dd_proj': proj['c4_dd'],
                'used_anchor_price': proj['b4_stage1'],  # B4 is the dist-zone anchor
                'anchor_kind': 'projected_B4_via_drawdown',
                'projected_b4': proj['b4_stage1'],
                'proj': {
                    'b4_stage1': proj['b4_stage1'],
                    'b4_stage1_origin': proj['b4_stage1_origin'],
                    'b4_via_drawdown': proj['b4_via_drawdown'],
                    'b4_band_low': proj['b4_band_low'],
                    'b4_band_high': proj['b4_band_high'],
                    'cross_check_ok': None,
                    'cross_check_rel_diff': float('nan'),
                    'mult_c5': proj['mult_c5'],
                    'b5_band_low': proj['b5_band_low'],
                    'b5_band_high': proj['b5_band_high'],
                    'b5_center': proj['b5_center'],
                    'shape_source': proj['shape_source'],
                },
                'mult_fit': proj['mult_fit'],
                'dd_fit': proj['dd_fit'],
                'fit_note': fit_note,
                'observed_c4_top_price': observed_c4_top_price,
                'observed_c4_top_date': observed_c4_top_date,
                'dist_price_low': proj['c5_top_band_low'],
                'dist_price_high': proj['c5_top_band_high'],
            }

    # ==================== OWN-NAIVE-MEDIAN PATH (>= 2 own dds + >= 2 own mults) ====================
    # NEW (2026-08-04): When an asset has at least 2 own drawdown observations
    # AND at least 2 own multiplier observations AND an observed C4 top, use
    # the asset's own [min, median, max] for both dd and mult — directly
    # anchored on the observed C4 top. This avoids the structural flaw in
    # borrowed-BTC-shape for high-beta assets (e.g. MSTR) where BTC's
    # compressing dd curve is too shallow for the asset's observed volatility.
    #
    # Trigger: ONLY for crypto alts that would otherwise fall to the BORROWED
    # path (n_bottoms<4 OR n_mults<3 OR n_dds<3). Macros are excluded: they
    # route through the macro 2-stage path with their own fitted shape (I-19).
    # ETH (n>=4/n>=3/n>=3) continues to use 2_stage_with_observed_c4. SOL is
    # intercepted earlier by the SOL-borrow-ETH branch. XRP with < 2 dds or
    # < 2 mults falls through to the existing naive_median_own_dd path.
    #
    # Math:
    #   dd_med = median(own_dds); band = [min(own_dds), max(own_dds)]
    #   B4 = c4_top * (1 - dd_med);  B4 band = c4_top * (1 - [dd_max, dd_min])
    #     (deeper dd -> lower price; shallower dd -> higher price)
    #   mult_med = median(own_mults); band = [min(own_mults), max(own_mults)]
    #   C5 = B4_med * mult_med;  C5 band = B4_low * mult_min..B4_high * mult_max
    #   B5 = C5_med * (1 - dd_med); B5 band = C5_low*(1-dd_max)..C5_high*(1-dd_min)
    #
    # This path is honest about n=2 / n=3 small samples: the band IS the
    # empirical envelope, no power-law extrapolation, no residual std fudge.
    own_median_floor_dds = 2
    own_median_floor_mults = 2
    own_data_insufficient = (len(bottoms) < 4 or len(mults) < 3 or len(dds) < 3)
    if (not is_macro
            and observed_c4_top_price is not None
            and own_data_insufficient
            and len(dds) >= own_median_floor_dds
            and len(mults) >= own_median_floor_mults
            and asset not in FORCE_BORROW_ASSETS):
        dd_med = float(np.median(dds))
        dd_min = float(np.min(dds))
        dd_max = float(np.max(dds))
        mult_med = float(np.median(mults))
        mult_min = float(np.min(mults))
        mult_max = float(np.max(mults))

        c4 = float(observed_c4_top_price)
        b4_center = c4 * (1.0 - dd_med)
        b4_low = c4 * (1.0 - dd_max)   # deepest dd -> lowest B4
        b4_high = c4 * (1.0 - dd_min)  # shallowest dd -> highest B4
        # Apply economic floor (B4 must be positive and below C4 top)
        b4_low = max(b4_low, 0.01)
        b4_high = max(min(b4_high, c4 * 0.95), b4_low)

        c5_center = b4_center * mult_med
        c5_low = b4_low * mult_min
        c5_high = b4_high * mult_max
        # Sanity: C5 must be above B4
        if c5_center <= b4_center:
            c5_center = b4_center * mult_med

        # B5 (post-C5 bear bottom) via own dd median applied to C5
        b5_center = c5_center * (1.0 - dd_med)
        b5_low = c5_low * (1.0 - dd_max)
        b5_high = c5_high * (1.0 - dd_min)

        chain_dds_str = "[" + ", ".join("%.3f" % d for d in dds) + "]"
        chain_mults_str = "[" + ", ".join("%.3f" % m for m in mults) + "]"
        fit_note = (
            f"mode=naive_median_own_dd; n_dds={len(dds)} (>= 2), "
            f"n_mults={len(mults)} (>= 2). "
            f"Asset's own drawdowns={chain_dds_str} and multipliers={chain_mults_str} "
            f"used directly (no borrowed BTC shape, no power-law extrapolation). "
            f"Anchor: own observed C4 top {observed_c4_top_date} @ "
            f"{_fmt_usd(observed_c4_top_price)}. "
            f"Drawdown median={dd_med:.3f} (band {dd_min:.3f}-{dd_max:.3f}) "
            f"-> B4 center={_fmt_usd(b4_center)} "
            f"(band {_fmt_usd(b4_low)} - {_fmt_usd(b4_high)}). "
            f"Multiplier median={mult_med:.2f} (band {mult_min:.2f}-{mult_max:.2f}) "
            f"-> C5 center={_fmt_usd(c5_center)} "
            f"(band {_fmt_usd(c5_low)} - {_fmt_usd(c5_high)}). "
            f"B5 (post-C5 bottom)={_fmt_usd(b5_center)} "
            f"(band {_fmt_usd(b5_low)} - {_fmt_usd(b5_high)})."
        )
        return {
            'available': True,
            'mode': 'naive_median_own_dd',
            'mult_proj': mult_med,
            'mult_band_low': mult_min,
            'mult_band_high': mult_max,
            'dd_proj': dd_med,
            'used_anchor_price': b4_center,
            'anchor_kind': 'naive_median_own_dd',
            'projected_b4': b4_center,
            'proj': {
                'b4_stage1': b4_center,
                'b4_stage1_origin': 'naive_median_own_dd',
                'b4_via_drawdown': b4_center,
                'b4_band_low': b4_low,
                'b4_band_high': b4_high,
                'cross_check_ok': None,
                'cross_check_rel_diff': float('nan'),
                'mult_c5': mult_med,
                'c5_top': c5_center,
                'c5_top_band_low': c5_low,
                'c5_top_band_high': c5_high,
                'b5_band_low': b5_low,
                'b5_band_high': b5_high,
                'b5_center': b5_center,
                'shape_source': 'own_naive_median',
            },
            'mult_fit': None,
            'dd_fit': None,
            'fit_note': fit_note,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
            'dist_price_low': c5_low,
            'dist_price_high': c5_high,
        }

    # ==================== BORROWED PATH (insufficient own history) ====================
    # If the asset doesn't have enough own observed data for a meaningful
    # 2-stage fit, borrow the relative shape (drawdown depth at C4, multiplier
    # at C5) from BTC's fit. Anchor stays the asset's own observed C4 top.
    # Hierarchy by market cap -> next higher cap: SOL -> BTC, XRP -> BTC,
    # ETH -> BTC. All crypto alts that follow BTC's halving-cycle thesis
    # can borrow from BTC's fit (cleanest dataset, n_mults = n_dds = 3).
    #
    # Trigger conditions (any of the below):
    #   - n_own_bear_bottoms < 4  (Stage 1 ratio fit needs >= 4 prices)
    #   - n_own_multipliers < 3   (Stage 2 mult fit needs >= 3 points)
    #   - n_own_drawdowns < 3     (cross-check needs >= 3 drawdowns)
    if (observed_c4_top_price is not None
            and (asset in FORCE_BORROW_ASSETS
                 or len(bottoms) < 4 or len(mults) < 3 or len(dds) < 3)):
        proj = two_stage_with_observed_c4_borrowed(
            observed_c4_top_price=observed_c4_top_price,
            observed_c4_top_date=observed_c4_top_date,
            parent_dds=BTC_PARENT_DDS,
            parent_mults=BTC_PARENT_MULTS,
            parent_label=BTC_PARENT_LABEL,
        )
        # If sanity-check (B4 below C4) fails inside the borrowed function,
        # it self-corrects to a conservative 66% drawdown. We still record
        # what was used so the chart can note "borrowed shape" + n_own.
        fit_note = (
            f"mode=borrowed_2_stage_from_{BTC_PARENT_LABEL}; "
            f"Insufficient own history: n_own_bear_bottoms={len(bottoms)} "
            f"(< 4 for Stage 1 ratio fit), n_own_mults={len(mults)} "
            f"(< 3 for Stage 2 power-law fit). "
            f"Borrowed relative shape from {BTC_PARENT_LABEL} "
            f"(drawdowns={BTC_PARENT_DDS}, mults={BTC_PARENT_MULTS}). "
            f"Anchor: own observed C4 top "
            f"{observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)}. "
            f"Projected drawdown at C4 = {proj['c4_dd']:.3f} "
            f"-> B4 = {_fmt_usd(proj['b4_stage1'])} "
            f"(band {_fmt_usd(proj['b4_band_low'])} - {_fmt_usd(proj['b4_band_high'])}). "
            f"Projected C5 multiplier = {proj['mult_c5']:.2f} -> "
            f"C5 top = {_fmt_usd(proj['c5_top'])} "
            f"(band {_fmt_usd(proj['c5_top_band_low'])} - "
            f"{_fmt_usd(proj['c5_top_band_high'])}). "
            f"B5 (post-C5 bottom) = {_fmt_usd(proj['b5_center'])} "
            f"(band {_fmt_usd(proj['b5_band_low'])} - {_fmt_usd(proj['b5_band_high'])})."
        )
        return {
            'available': True,
            'mode': f'borrowed_2_stage_from_{BTC_PARENT_LABEL}',
            'mult_proj': proj['mult_c5'],
            'mult_band_low': proj['mult_c5_band_low'],
            'mult_band_high': proj['mult_c5_band_high'],
            'dd_proj': proj['c4_dd'],
            'used_anchor_price': proj['b4_stage1'],  # B4 is the dist-zone anchor
            'anchor_kind': 'projected_B4_via_drawdown',
            'projected_b4': proj['b4_stage1'],
            'proj': {
                'b4_stage1': proj['b4_stage1'],
                'b4_stage1_origin': proj['b4_stage1_origin'],
                'b4_via_drawdown': proj['b4_via_drawdown'],
                'b4_band_low': proj['b4_band_low'],
                'b4_band_high': proj['b4_band_high'],
                'cross_check_ok': None,
                'cross_check_rel_diff': float('nan'),
                'mult_c5': proj['mult_c5'],
                'b5_band_low': proj['b5_band_low'],
                'b5_band_high': proj['b5_band_high'],
                'b5_center': proj['b5_center'],
                'shape_source': proj['shape_source'],
            },
            'mult_fit': proj['mult_fit'],
            'dd_fit': proj['dd_fit'],
            'fit_note': fit_note,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
            'dist_price_low': proj['c5_top_band_low'],
            'dist_price_high': proj['c5_top_band_high'],
        }

    if is_macro:
        # I-19: route macros through the same borrowed-shape machinery as
        # crypto alts with insufficient own history. Macros DO pivot around
        # BTC halvings (all observed macro tops fall 0-3 years after each
        # halving; see docs/blockers/I-19-macro-2stage.md). The fit uses
        # the macro's OWN dd/mult series (n=3 from C1-C3) so the relative
        # shape matches the asset's observed behaviour, NOT BTC's much
        # deeper/larger crypto shape. Economic floors are macro-appropriate
        # (drawdowns 8-50%, multipliers 1.1x-2.8x for SPX/NDX/DXY/TLT).
        if (observed_c4_top_price is not None
                and (len(mults) >= 1 or len(dds) >= 1)):
            macro_dd_floor = 0.05
            macro_mult_floor = 1.05
            proj = two_stage_with_observed_c4_borrowed(
                observed_c4_top_price=observed_c4_top_price,
                observed_c4_top_date=observed_c4_top_date,
                parent_dds=dds,
                parent_mults=mults,
                parent_label='self_macro',
                dd_floor=macro_dd_floor,
                mult_floor=macro_mult_floor,
            )
            # The borrowed-shape function's B4 band is derived from a power-
            # law extrapolation of the macro dd series (n=3), which can inflate
            # the implied drawdown toward BTC-like depths (up to 0.95) and
            # produce absurd B4 floors (e.g. TLT B4 low = $9.55 vs historic >$82).
            # Clamp the B4 band to the macro's OWN observed drawdown range so
            # only empirically-sensible depths apply. Cap = min(max_dd * 1.5,
            # 0.60). b4_stage1 (the anchor / center) is untouched.
            dd_cap = min(max(dds) * 1.5, 0.60) if dds else 0.60
            b4_dd_low = 1.0 - (proj['b4_band_low'] / observed_c4_top_price) if observed_c4_top_price > 0 else 0.0
            if b4_dd_low > dd_cap:
                proj['b4_band_low'] = observed_c4_top_price * (1.0 - dd_cap)
            chain_dds = "[" + ", ".join("%.3f" % d for d in dds) + "]"
            chain_mults = "[" + ", ".join("%.3f" % m for m in mults) + "]"
            fit_note = (
                "mode=macro_2_stage_own_shape; "
                "macro assets (SPX/NDX/DXY/TLT) DO pivot around BTC halvings "
                "(I-19 revision; see docs/blockers/I-19-macro-2stage.md). "
                "Anchor = own observed C4 top "
                f"{observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)}; "
                f"shape fit on macro's own series (dds={chain_dds} n={len(dds)}, "
                f"mults={chain_mults} n={len(mults)}). "
                f"Projected drawdown at C4 = {proj['c4_dd']:.3f} "
                f"-> B4 = {_fmt_usd(proj['b4_stage1'])} "
                f"(band {_fmt_usd(proj['b4_band_low'])} - "
                f"{_fmt_usd(proj['b4_band_high'])}). "
                f"Projected C5 multiplier = {proj['mult_c5']:.2f} -> "
                f"C5 top = {_fmt_usd(proj['c5_top'])} "
                f"(band {_fmt_usd(proj['c5_top_band_low'])} - "
                f"{_fmt_usd(proj['c5_top_band_high'])})."
            )
            return {
                'available': True,
                'mode': 'macro_2_stage_own_shape',
                'mult_proj': proj['mult_c5'],
                'mult_band_low': proj['mult_c5_band_low'],
                'mult_band_high': proj['mult_c5_band_high'],
                'dd_proj': proj['c4_dd'],
                'used_anchor_price': proj['b4_stage1'],
                'anchor_kind': 'projected_B4_via_drawdown',
                'projected_b4': proj['b4_stage1'],
                'proj': {
                    'b4_stage1': proj['b4_stage1'],
                    'b4_stage1_origin': proj['b4_stage1_origin'],
                    'b4_via_drawdown': proj['b4_via_drawdown'],
                    'b4_band_low': proj['b4_band_low'],
                    'b4_band_high': proj['b4_band_high'],
                    'cross_check_ok': None,
                    'cross_check_rel_diff': float('nan'),
                    'mult_c5': proj['mult_c5'],
                    'b5_band_low': proj['b5_band_low'],
                    'b5_band_high': proj['b5_band_high'],
                    'b5_center': proj['b5_center'],
                    'shape_source': proj['shape_source'],
                },
                'mult_fit': proj['mult_fit'],
                'dd_fit': proj['dd_fit'],
                'fit_note': fit_note,
                'observed_c4_top_price': observed_c4_top_price,
                'observed_c4_top_date': observed_c4_top_date,
                'dist_price_low': proj['c5_top_band_low'],
                'dist_price_high': proj['c5_top_band_high'],
            }
        # Macro with no observed C4 top or no dd/mult data at all: fall
        # through to the historical envelope (no power-law projection).
        if bottoms:
            hist_low = float(min(bottoms))
            hist_high = float(max(bottoms))
            anchor_price = float(bottoms[-1])
        else:
            hist_low = hist_high = anchor_price = None
        chain_str = "[" + ", ".join(_fmt_usd(b) for b in bottoms) + "]"
        fit_note = (
            "mode=macro_not_cycle_tied; "
            "macro asset had no observed C4 top or no own drawdown/multiplier "
            "samples -- no power-law projection possible. "
            "Price band = historical [min, max] of asset's bear bottoms "
            f"({chain_str} if available)."
        )
        return {
            'available': True,
            'mode': 'macro_not_cycle_tied',
            'mult_proj': None, 'mult_band_low': None, 'mult_band_high': None,
            'dd_proj': None,
            'used_anchor_price': anchor_price,
            'anchor_kind': 'historical_envelope',
            'projected_b4': None,
            'proj': None, 'mult_fit': None, 'dd_fit': None,
            'dist_price_low': hist_low,
            'dist_price_high': hist_high,
            'fit_note': fit_note,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
        }

    # ==================== CRYPTO PATH ====================
    mult_floor = 2.0
    dd_floor = 0.50

    # Need at least 3 multipliers for a power-law Stage 2 fit.
    mult_stage2_ok = len(mults) >= 3
    if not mult_stage2_ok:
        if mults:
            m_proj = float(np.median(mults))
            m_low = float(np.min(mults))
            m_high = float(np.max(mults))
            dd_proj = float(np.median(dds)) if dds else None
            anchor_price = float(bottoms[-1]) if bottoms else None
            fit_note = (
                "mode=naive_median; n_mults=%d (< 3) insufficient for "
                "power-law. Anchored on last observed bear bottom %s. "
                "Observed C4 top: %s @ %s." % (
                    len(mults), _fmt_usd(anchor_price),
                    observed_c4_top_date, _fmt_usd(observed_c4_top_price),
                )
            )
            return {
                'available': True, 'mode': 'naive_median',
                'mult_proj': m_proj, 'mult_band_low': m_low,
                'mult_band_high': m_high, 'dd_proj': dd_proj,
                'used_anchor_price': anchor_price,
                'anchor_kind': 'observed_last_bottom',
                'fit_note': fit_note,
                'projected_b4': None, 'mult_fit': None, 'dd_fit': None,
                'proj': None,
                'observed_c4_top_price': observed_c4_top_price,
                'observed_c4_top_date': observed_c4_top_date,
                'dist_price_low': anchor_price * m_low if anchor_price else None,
                'dist_price_high': anchor_price * m_high if anchor_price else None,
            }
        return {
            'available': False, 'mode': 'no_data',
            'fit_note': 'no multiplier data',
        }

    # Stage 2 power-law fit on multipliers (just to extract fit_a, fit_b)
    mult_fit = fit_cycle_compression(
        mults,
        list(range(1, len(mults) + 1)),
        project_to_idx=5, floor=mult_floor,
    )
    if mult_fit['fit_a'] is None or mult_fit['fit_b'] is None:
        # Stage 2 power-law fit failed; naive fallback
        m_proj = float(np.median(mults))
        m_low = float(np.min(mults))
        m_high = float(np.max(mults))
        dd_proj = float(np.median(dds)) if dds else None
        anchor_price = float(bottoms[-1]) if bottoms else None
        fit_note = (
            "mode=naive_median; power-law Stage 2 fit failed "
            f"({mult_fit.get('fallback_reason','')}). "
            "Anchored on observed last bear bottom. "
            f"Observed C4 top: {observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)}."
        )
        return {
            'available': True, 'mode': 'naive_median',
            'mult_proj': m_proj, 'mult_band_low': m_low,
            'mult_band_high': m_high, 'dd_proj': dd_proj,
            'used_anchor_price': anchor_price,
            'anchor_kind': 'observed_last_bottom',
            'fit_note': fit_note,
            'projected_b4': None, 'mult_fit': mult_fit, 'dd_fit': None, 'proj': None,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
            'dist_price_low': anchor_price * m_low if anchor_price else None,
            'dist_price_high': anchor_price * m_high if anchor_price else None,
        }

    mult_c5 = max(mult_fit['fit_a'] * (5.0 ** mult_fit['fit_b']), mult_floor)

    # Stage 2 path: project B4 from observed C4 top * (1 - dd_C4)
    if len(dds) >= 3:
        dd_fit = fit_cycle_compression(
            dds, list(range(1, len(dds) + 1)),
            project_to_idx=4, floor=dd_floor,
        )
        if dd_fit['fit_a'] is not None and dd_fit['fit_b'] is not None:
            dd_c4 = max(dd_fit['fit_a'] * (4.0 ** dd_fit['fit_b']), dd_floor)
        else:
            dd_c4 = dd_fit.get('projected_value', float(np.median(dds)))
    elif dds:
        dd_fit = None
        dd_c4 = float(np.median(dds))
    else:
        dd_fit = None
        dd_c4 = None

    # Stage 1 path: project B4 from the bear-bottom ratio series.
    # Requires n_bear_bottoms >= 4.
    # project_idx = len(chain) projects the next forward ratio. For assets
    # like BTC (4 prices -> idx=4 = B4/B3) this is the next unobserved
    # ratio. For assets like ETH (5 prices including the observed post-C4
    # bottom -> idx=5 = B5/B4) this projects the following forward ratio.
    # Using len(bottoms) rather than hard-coded 4 ensures the projection
    # is genuinely forward, not re-projecting an already-observed point.
    stage1 = None
    if len(bottoms) >= 4:
        stage1 = project_bear_bottom(bottoms, project_idx=len(bottoms), floor_ratio=1.0)

    # Decide: 2-stage (both paths available) vs stage2_only (no Stage 1)
    if observed_c4_top_price is not None and dd_c4 is not None:
        b4_stage2 = observed_c4_top_price * (1.0 - dd_c4)
    else:
        b4_stage2 = None

    if stage1 is not None and math.isfinite(stage1['projected_price']):
        b4_stage1 = stage1['projected_price']
        s1_low, s1_high = stage1['price_band_low'], stage1['price_band_high']
        if b4_stage2 is not None and math.isfinite(b4_stage2):
            # Cross-check
            rel_diff = (b4_stage1 - b4_stage2) / b4_stage2
            cross_check_ok = abs(rel_diff) <= 0.15
        else:
            rel_diff = float('nan')
            cross_check_ok = False
        # Combined B4 band: union of the two estimates.
        b4_low = min(s1_low, b4_stage2) if b4_stage2 is not None and math.isfinite(b4_stage2) else s1_low
        b4_high = max(s1_high, b4_stage2) if b4_stage2 is not None and math.isfinite(b4_stage2) else s1_high
        used_anchor = b4_stage1
        ck_str = "OK" if cross_check_ok else "FAIL"
        # Format the bear-bottoms chain for display
        chain_str = "[" + ", ".join(_fmt_usd(b) for b in bottoms) + "]"
        dd_str = "%.2f" % dd_fit['fit_a'] if (dd_fit and dd_fit.get('fit_a') is not None) else "NA"
        dd_b_str = "%.3f" % dd_fit['fit_b'] if (dd_fit and dd_fit.get('fit_b') is not None) else "NA"
        dd_r2_str = "%.2f" % dd_fit['r_squared'] if (dd_fit and dd_fit.get('r_squared') is not None) else "NA"
        dd_proj_str = "%.3f" % dd_c4 if dd_c4 is not None else "NA"
        fit_note = (
            "mode=2_stage_with_observed_c4; "
            f"Observed C4 top: {observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)}. "
            f"Stage 1: bear-bottom chain {chain_str} "
            f"-> ratio_n = {stage1['fit_a']:.2f}*idx^{stage1['fit_b']:.2f} "
            f"(R2={stage1['r_squared']:.2f}) -> B4 = {_fmt_usd(b4_stage1)} "
            f"(band {_fmt_usd(s1_low)} - {_fmt_usd(s1_high)}). "
            f"Stage 2 cross-check: dd_n={dd_str}*idx^{dd_b_str} (R2={dd_r2_str}) "
            f"-> C4 dd={dd_proj_str}, B4_via_dd={_fmt_usd(b4_stage2)}. "
            f"Cross-check: rel_diff=%+.1f%% (%s). C5 mult=%.2f, C5 top=%s (band %s - %s)." % (
                rel_diff * 100 if math.isfinite(rel_diff) else float('nan'),
                ck_str, mult_c5,
                _fmt_usd(used_anchor * mult_c5),
                _fmt_usd(b4_low * mult_c5),
                _fmt_usd(b4_high * mult_c5),
            )
        )
        return {
            'available': True, 'mode': '2_stage_with_observed_c4',
            'mult_proj': mult_c5, 'mult_band_low': mult_fit['band_low'],
            'mult_band_high': mult_fit['band_high'],
            'dd_proj': dd_c4,
            'used_anchor_price': used_anchor,
            'anchor_kind': 'projected_B4',
            'projected_b4': b4_stage1,
            'proj': {
                'b4_stage1': b4_stage1, 'b4_via_drawdown': b4_stage2,
                'b4_band_low': b4_low, 'b4_band_high': b4_high,
                'cross_check_ok': cross_check_ok,
                'cross_check_rel_diff': rel_diff,
                'mult_c5': mult_c5,
            },
            'mult_fit': mult_fit, 'dd_fit': dd_fit,
            'fit_note': fit_note,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
            'dist_price_low': b4_low * mult_c5,
            'dist_price_high': b4_high * mult_c5,
        }
    elif b4_stage2 is not None and math.isfinite(b4_stage2):
        # Stage 2 only: anchor C5 on Stage 2's B4 (drawdown path from observed C4 top)
        # No cross-check possible (Stage 1 unavailable).
        dd_proj_str = "%.3f" % dd_c4 if dd_c4 is not None else "NA"
        fit_note = (
            "mode=stage2_only_observed_c4_via_drawdown; "
            f"Stage 1 inapplicable (n_bear_bottoms=%d < 4). "
            f"Observed C4 top: {observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)}. "
            f"Projecting B4 via drawdown path: B4 = C4_top * (1 - dd_C4=%s) = %s. "
            f"C5 mult=%.2f, C5 top = %s." % (
                dd_proj_str, _fmt_usd(b4_stage2), mult_c5,
                _fmt_usd(b4_stage2 * mult_c5),
            )
        )
        # Use a band: the Stage 2 cross-check provides only a point estimate;
        # produce a band by applying min/max of historical drawdowns to the
        # observed C4 top.
        if dds:
            dd_low = min(dds)
            dd_high = max(dds)
            b_low_alt = observed_c4_top_price * (1.0 - dd_high)
            b_high_alt = observed_c4_top_price * (1.0 - dd_low)
        else:
            b_low_alt = b_high_alt = b4_stage2
        return {
            'available': True, 'mode': 'stage2_only_observed_c4_via_drawdown',
            'mult_proj': mult_c5, 'mult_band_low': mult_fit['band_low'],
            'mult_band_high': mult_fit['band_high'],
            'dd_proj': dd_c4,
            'used_anchor_price': b4_stage2,
            'anchor_kind': 'projected_B4_via_drawdown',
            'projected_b4': b4_stage2,
            'proj': {
                'b4_stage1': None, 'b4_via_drawdown': b4_stage2,
                'b4_band_low': b_low_alt, 'b4_band_high': b_high_alt,
                'cross_check_ok': None,  # unknown
                'cross_check_rel_diff': float('nan'),
                'mult_c5': mult_c5,
            },
            'mult_fit': mult_fit, 'dd_fit': dd_fit,
            'fit_note': fit_note,
            'observed_c4_top_price': observed_c4_top_price,
            'observed_c4_top_date': observed_c4_top_date,
            'dist_price_low': b_low_alt * mult_c5,
            'dist_price_high': b_high_alt * mult_c5,
        }
    else:
        # Insufficient data: Stage 1 missing and Stage 2 has no dd
        return {
            'available': False, 'mode': 'no_data',
            'fit_note': 'insufficient Stage 1 (n_bear_bottoms<4) and Stage 2 '
                       '(no drawdown data) for 2-stage projection',
        }


def main() -> None:
    global H5_DATE, _GOLD_SUPPORT_BAND
    metrics_df = pd.read_csv(INPUT_METRICS, keep_default_na=False)
    fwd_df = pd.read_csv(INPUT_FWD, keep_default_na=False)

    # Load H5 date from events.csv (canonical source)
    events_df = pd.read_csv(INPUT_EVENTS)
    h5_row = events_df[(events_df['event_type'] == 'halving') & (events_df['cycle_id'] == 'H5')]
    if not h5_row.empty:
        H5_DATE = pd.to_datetime(h5_row.iloc[0]['date'])
    else:
        H5_DATE = pd.to_datetime("2028-04-01")  # fallback

    # Gold bull market support band (20-mo SMA + 21-mo EMA) — gold-specific
    # cross-check on the drawdown-projected B4. See docs/gold_seasonality.md.
    _GOLD_SUPPORT_BAND = _gold_support_band()

    zone_rows = []

    for asset in ASSETS:
        # Gold bull support band lookup is computed once per run (cheap) and
        # used for the gold bear_bottom cross-check + chart overlay.
        gold_band = _GOLD_SUPPORT_BAND if asset == "gold" else None
        d_pvbh = _get_fwd_row(fwd_df, asset, "D_asset_prev_bottom_to_halving")
        d_ht   = _get_fwd_row(fwd_df, asset, "D_asset_halving_to_top")
        d_tnb  = _get_fwd_row(fwd_df, asset, "D_asset_top_to_next_bottom")

        if (d_pvbh is None or d_ht is None or d_tnb is None
                or int(d_pvbh["n_with_proxy"]) < 1
                or int(d_ht["n_with_proxy"]) < 1
                or int(d_tnb["n_with_proxy"]) < 1) and asset not in FORCE_BORROW_ASSETS:
            for zone in ["bear_bottom", "accumulation", "distribution", "exit"]:
                zone_rows.append({
                    "asset": asset, "zone": zone,
                    "base_start": "", "base_end": "",
                    "outer_start": "", "outer_end": "",
                    "price_low": "", "price_high": "",
                    "anchor_event": "", "anchor_price": "",
                    "compression_fit_used": "no_data",
                    "support_band_low": "",
                    "support_band_high": "",
                    "compression_fit_note": "insufficient data (n<1 on required stats)",
                })
            continue

        # --- Build the projection ---
        proj_out = _project_asset_chain(metrics_df, asset,
                                        is_macro=(asset in MACRO_ASSETS))

        # --- B4 Bear-bottom zone (only for crypto where C4 top observed) ---
        #
        # New model (2026-07-23 revision): BTC-drives-market thesis +
        # asset's own prior drawdowns.
        #
        # Timing: anchored on BTC's projected B4 date (median of BTC's
        #   bear_bottom base band in next_cycle_zones.csv) +/- the alt's
        #   own historical lag-vs-BTC-bottom for the same cycle. So the alt
        #   B4 timing follows BTC events, not intra-cycle durations from
        #   the alt itself. When the alt has >= 2 lag samples (e.g. ETH
        #   has C2=-1d, C3=-156d), the band is Q25-Q75 / min-max. When < 2,
        #   a wide default window (+-90d base, +-180d outer) around BTC B4.
        #
        # Price: drawn from the asset's OWN prior-cycle drawdowns applied
        #   to the observed C4 top. Drawdown envelope: deepest observed
        #   drawdown -> lowest price; shallowest -> highest price; median
        #   -> anchor. Falls back to BTC's own drawdowns [85%, 83%, 77%]
        #   only when the alt has < 2 own drawdown samples.
        #
        # For macro and insufficient-data paths: row is emitted with empty
        #   dates and a `no_data` note so the test_alts fixture stays a
        #   clean 7 assets x 4 zones = 28 rows; the section text will
        #   explain the macro omission.
        obs_c4_date = proj_out.get('observed_c4_top_date') if proj_out.get('available') else None
        obs_c4_price = proj_out.get('observed_c4_top_price') if proj_out.get('available') else None
        b4_proj = proj_out.get('proj') if proj_out.get('available') else None
        # Crypto modes (and macro-2-stage since I-19) that use the new
        # BTC-anchored B4 design (any path with an observed C4 top -- the
        # 2-stage, borrowed-2-stage, macro-2-stage, and naive-median-own-dd
        # modes all have C4 tops; the new B4 design replaces the old
        # Stage 1 B4 price path). The naive_median_own_dd mode (2026-08-04)
        # uses the asset's own dd/mult series directly instead of borrowing
        # BTC's shape — applies to MSTR (n_dds=2, n_mults=2).
        crypto_with_proj = (
            proj_out.get('available')
            and obs_c4_date is not None
            and proj_out.get('mode') in
                ('2_stage_with_observed_c4', 'borrowed_2_stage_from_BTC',
                 'borrowed_2_stage_from_ETH', 'macro_2_stage_own_shape',
                 'naive_median_own_dd')
        )
        if crypto_with_proj and obs_c4_price is not None and obs_c4_date is not None:
            # --- New B4 design (2026-07-23) ---
            #
            # TIMING: anchored on BTC's projected B4 date +/- the alt's own
            #   historical lag-vs-BTC-bottom (BTC drives the market; alts follow
            #   BTC by their characteristic lead/lag). When the alt has >= 2
            #   own lag samples, use Q25-Q75 / min-max envelope; when < 2,
            #   use a wide minimum-uncertainty window of +-60d / +-120d around
            #   the BTC B4 date (alts can lead BTC by 1-5 months per C3 history).
            #
            # PRICE: drawn from the asset's OWN prior-cycle drawdowns applied to
            #   the observed C4 top (NOT borrowed from BTC unless the alt has
            #   < 2 own drawdown samples). Drawdown envelope: deepest observed
            #   drawdown -> lowest price; shallowest -> highest price. Anchor =
            #   median drawdown.
            #
            # This replaces the prior "Stage 1 power-law fit on bear bottom
            # ratios" path, which was mathematically attractive but required
            # n>=4 bear bottoms and borrowed BTC shape for most alts. The new
            # model is simpler, anchored on real cycle events (BTC B4 + alt
            # drawdown history), and produces honest uncertainty bands.
            btc_b4_center = _load_btc_projected_b4_center()
            alt_lags = _alt_vs_btc_lag_days(metrics_df, asset)
            alt_dds = _alt_prior_drawdowns(metrics_df, asset)
            btc_dds = BTC_PARENT_DDS  # [0.848579, 0.834293, 0.766634] (BTC's own)
            b4_price_proj = _project_alt_b4_price(
                obs_c4_price, alt_dds, btc_dds)

            # ETH-specific: BTC ratio-of-ratios path.  ETH's own ratio
            # series is non-monotonic + includes an unconfirmed C4 bottom,
            # so we project ETH B4 from BTC's clean B4/B3 ratio scaled by
            # the ETH/BTC ratio-of-ratios at the C2 cycle (conservative).
            # See govs/agreements: ror=C2 -> B4 ~$1,716.
            eth_ror_proj = None
            if asset == "eth":
                btc_b4_info = _load_btc_b4_price()
                if btc_b4_info is not None:
                    eth_ror_proj = _project_eth_btc_ror(
                        metrics_df, btc_b4_info, ror_cycle='C2')

            # Timing zone: BTC B4 +/- alt's own historical lag
            if btc_b4_center is not None and alt_lags:
                lags = np.array(alt_lags, dtype=float)
                lag_med = float(np.median(lags))
                if len(lags) >= 2 and (max(lags) - min(lags)) >= 1:
                    lag_q25 = float(np.percentile(lags, 25))
                    lag_q75 = float(np.percentile(lags, 75))
                    lag_min = float(min(lags))
                    lag_max = float(max(lags))
                else:
                    # 1 sample: minimum-uncertainty window +-60d / +-120d
                    lag_med_v = float(lags[0])
                    lag_q25 = lag_med_v - 60
                    lag_q75 = lag_med_v + 60
                    lag_min = lag_med_v - 120
                    lag_max = lag_med_v + 120
                b4_base_start = (btc_b4_center + timedelta(days=int(lag_q25))).strftime("%Y-%m-%d")
                b4_base_end = (btc_b4_center + timedelta(days=int(lag_q75))).strftime("%Y-%m-%d")
                b4_outer_start = (btc_b4_center + timedelta(days=int(lag_min))).strftime("%Y-%m-%d")
                b4_outer_end = (btc_b4_center + timedelta(days=int(lag_max))).strftime("%Y-%m-%d")
                timing_src = f"BTC B4 {btc_b4_center.strftime('%Y-%m-%d')} + alt lag (n={len(lags)}, median={lag_med:+.0f}d)"
            elif btc_b4_center is not None:
                # No alt lag history: assume alts lead BTC by ~30-150d (C3
                # pattern). Wide +-90d / +-180d window around BTC B4.
                b4_base_start = (btc_b4_center - timedelta(days=90)).strftime("%Y-%m-%d")
                b4_base_end = (btc_b4_center + timedelta(days=90)).strftime("%Y-%m-%d")
                b4_outer_start = (btc_b4_center - timedelta(days=180)).strftime("%Y-%m-%d")
                b4_outer_end = (btc_b4_center + timedelta(days=180)).strftime("%Y-%m-%d")
                timing_src = f"BTC B4 {btc_b4_center.strftime('%Y-%m-%d')} + default +-90d window (no alt lag data)"
            else:
                b4_base_start = b4_base_end = b4_outer_start = b4_outer_end = ""
                timing_src = "no BTC B4 data"

            # Price band: prefer ETH ror path when available (ETH only).
            # Then Stage 1 ratio-path band, then drawdown envelope.
            n_dd = b4_price_proj["n_drawdowns"] if b4_price_proj else 0
            dd_src = b4_price_proj["src"] if b4_price_proj else "n/a"
            dd_min = b4_price_proj["dd_min"] if b4_price_proj else None
            dd_max = b4_price_proj["dd_max"] if b4_price_proj else None
            dd_med = b4_price_proj["dd_med"] if b4_price_proj else None
            dd_price_low = b4_price_proj["b4_price_low"] if b4_price_proj else None
            dd_price_high = b4_price_proj["b4_price_high"] if b4_price_proj else None
            dd_center = b4_price_proj["b4_center"] if b4_price_proj else None
            price_note_dd = (f"drawdowns src={dd_src} (n={n_dd}); "
                             f"dd_min={dd_min:.3f} dd_max={dd_max:.3f} "
                             f"dd_med={dd_med:.3f}") if b4_price_proj else "no drawdown data"

            if (eth_ror_proj is not None
                    and eth_ror_proj.get('available')):
                # ETH ratio-of-ratios path (primary for ETH)
                b4_price_low = eth_ror_proj['b4_band_low']
                b4_price_high = eth_ror_proj['b4_band_high']
                b4_anchor_price = eth_ror_proj['projected_b4']
                price_note = (f"BTC ratio-of-ratios (ror={eth_ror_proj['ror_used']:.3f} at "
                              f"{eth_ror_proj['ror_cycle_label']}); "
                              f"drawdown cross-check: {price_note_dd}")
            elif (b4_proj is not None
                    and b4_proj.get('b4_band_low') is not None
                    and math.isfinite(b4_proj['b4_band_low'])):
                # Stage 1 available: use its band for displayed columns.
                b4_price_low = b4_proj['b4_band_low']
                b4_price_high = b4_proj['b4_band_high']
                b4_anchor_price = b4_proj['b4_stage1']
                price_note = (f"Stage 1 ratio-path (band {_fmt_usd(b4_price_low)} - "
                              f"{_fmt_usd(b4_price_high)}); drawdown cross-check: "
                              f"{price_note_dd}")
            elif b4_price_proj is not None:
                # Stage 1 unavailable: fall back to drawdown envelope
                b4_price_low = dd_price_low
                b4_price_high = dd_price_high
                b4_anchor_price = dd_center
                price_note = price_note_dd
            else:
                b4_price_low = b4_price_high = None
                b4_anchor_price = None
                price_note = "no drawdown data"

            b4_cross_ok = ''
            b4_cross_rd = ''
            if (eth_ror_proj is not None and eth_ror_proj.get('available')):
                b4_fit_note = (
                    f"B4 (post-C4-top bear bottom). Timing: {timing_src}. "
                    f"Price: {eth_ror_proj.get('fit_note', price_note)}."
                )
            else:
                b4_fit_note = (
                    f"B4 (post-C4-top bear bottom). Timing: {timing_src}. "
                    f"Price: {price_note}. Anchor=[observed C4 top {obs_c4_date} "
                    f"@ {_fmt_usd(obs_c4_price)}] x (1 - dd_proj)."
                )
            # Gold-only: append SMA/EMA bull-support-band cross-check on B4.
            # Per docs/gold_seasonality.md the 20-mo SMA / 21-mo EMA band has
            # held every gold correction since 2015 and is the empirical
            # floor the projected drawdown B4 must respect.
            if asset == "gold" and gold_band is not None:
                sb_lo = gold_band["band_low"]
                sb_hi = gold_band["band_high"]
                sb_status = "OK (B4 sits on the band)"
                if b4_price_low is not None and b4_price_high is not None:
                    if b4_price_low < sb_lo * 0.95:
                        sb_status = "WARN (B4 projects below band -> bull-support invalidation risk)"
                    elif b4_price_high > sb_hi * 1.10:
                        sb_status = "OK (B4 projects above band -> shallower drawdown than SMA floor)"
                b4_fit_note += (
                    f" Gold support band (20-mo SMA ${gold_band['sma20']:.2f} / "
                    f"21-mo EMA ${gold_band['ema21']:.2f} @ {gold_band['date']}): "
                    f"{sb_status}."
                )
        elif proj_out.get('available') and proj_out.get('mode') == 'macro_not_cycle_tied':
            # Macro: no crypto C4 top, so no B4 event zone (per design, macro
            # is not cycle-tied). Emit a placeholder row with no dates/prices.
            b4_base_start = b4_base_end = b4_outer_start = b4_outer_end = ""
            b4_price_low = b4_price_high = None
            b4_anchor_price = None
            b4_cross_ok = b4_cross_rd = ""
            b4_fit_note = ("B4 (post-C4-top bear bottom): macro asset, "
                           "not cycle-tied -- no B4 zone.")
        else:
            # Insufficient-data path (XRP with naive_median; macro not_cycle_tied): emit a
            # placeholder B4 row.
            b4_base_start = b4_base_end = b4_outer_start = b4_outer_end = ""
            b4_price_low = b4_price_high = None
            b4_anchor_price = None
            b4_cross_ok = b4_cross_rd = ""
            b4_fit_note = ("B4 (post-C4-top bear bottom): insufficient data "
                           "for 2-stage projection -- no B4 zone.")

        # Gold-specific: bull market support band (20-mo SMA / 21-mo EMA)
        # cross-check on the drawdown-projected B4 (docs/gold_seasonality.md).
        # Populated ONLY for gold's bear_bottom row -- empty for all others.
        # gold_band is already computed at the top of the per-asset loop.
        sb_low = ""
        sb_high = ""
        if gold_band is not None:
            sb_low = "%.4f" % gold_band["band_low"]
            sb_high = "%.4f" % gold_band["band_high"]

        zone_rows.append({
            "asset": asset, "zone": "bear_bottom",
            "base_start": b4_base_start, "base_end": b4_base_end,
            "outer_start": b4_outer_start, "outer_end": b4_outer_end,
            "price_low": "" if b4_price_low is None or not math.isfinite(b4_price_low) else "%.4f" % b4_price_low,
            "price_high": "" if b4_price_high is None or not math.isfinite(b4_price_high) else "%.4f" % b4_price_high,
            "anchor_event":
                "BTC ratio-of-ratios B4" if (crypto_with_proj and eth_ror_proj is not None and eth_ror_proj.get('available')) else
                "Stage 1 ratio-path B4" if (crypto_with_proj and b4_proj is not None and b4_proj.get('b4_band_low') is not None and math.isfinite(b4_proj.get('b4_band_low', float('nan')))) else
                "Drawdown envelope B4" if crypto_with_proj else "",
            "anchor_price":
                "" if b4_anchor_price is None or not math.isfinite(b4_anchor_price) else "%.4f" % b4_anchor_price,
            "observed_c4_top_price":
                "" if obs_c4_price is None else "%.4f" % obs_c4_price,
            "observed_c4_top_date":
                "" if obs_c4_date is None else obs_c4_date,
            "compression_fit_used": proj_out.get('mode', 'no_data'),
            "support_band_low": sb_low,
            "support_band_high": sb_high,
            "cross_check_ok": b4_cross_ok,
            "cross_check_rel_diff": b4_cross_rd,
            "compression_fit_note": b4_fit_note,
        })

        pvbh_median = _num(d_pvbh["median"])
        pvbh_min = _num(d_pvbh["min"])
        pvbh_max = _num(d_pvbh["max"])
        acc_base_start = H5_DATE - timedelta(days=int(pvbh_median))
        acc_base_end = H5_DATE
        acc_outer_start = H5_DATE - timedelta(days=int(pvbh_max))
        acc_outer_end = H5_DATE

        # Ensure accumulation starts strictly AFTER B4 outer_end (when
        # a B4 zone is present) to satisfy the no-overlap test and the
        # test_alt_next_cycle_zones_base_within_outer test (base >= outer).
        if crypto_with_proj and b4_outer_end:
            b4_oe = pd.to_datetime(b4_outer_end)
            acc_floor = b4_oe + timedelta(days=1)
            if acc_outer_start < acc_floor:
                acc_outer_start = acc_floor
            if acc_base_start < acc_floor:
                acc_base_start = acc_floor
            if acc_base_start < acc_outer_start:
                acc_base_start = acc_outer_start

        # Accumulation zone: starts right after the B4 event, runs to H5.
        # Price-free (the B4 zone above IS the accumulation-entry bottom).
        zone_rows.append({
            "asset": asset, "zone": "accumulation",
            "base_start": acc_base_start.strftime("%Y-%m-%d"),
            "base_end": acc_base_end.strftime("%Y-%m-%d"),
            "outer_start": acc_outer_start.strftime("%Y-%m-%d"),
            "outer_end": acc_outer_end.strftime("%Y-%m-%d"),
            "price_low": "", "price_high": "",
            "anchor_event": "H5", "anchor_price": "",
            "observed_c4_top_price":
                "" if obs_c4_price is None else "%.4f" % obs_c4_price,
            "observed_c4_top_date":
                "" if obs_c4_date is None else obs_c4_date,
            "compression_fit_used": proj_out.get('mode', 'no_data'),
            "support_band_low": "",
            "support_band_high": "",
            "cross_check_ok": b4_cross_ok,
            "cross_check_rel_diff": b4_cross_rd,
            "compression_fit_note":
                "acc: starts after B4 event; price-free (entry price = B4 zone). "
                + proj_out.get('fit_note', ''),
        })

        # --- Distribution zone (C5 TOP) ---
        dist_base_start = H5_DATE + timedelta(days=int(d_ht["q25"]))
        dist_base_end = H5_DATE + timedelta(days=int(d_ht["q75"]))
        dist_outer_start = H5_DATE + timedelta(days=int(_num(d_ht["min"])))
        dist_outer_end = H5_DATE + timedelta(days=int(_num(d_ht["max"])))
        ht_median = _num(d_ht["median"])

        # The new _project_asset_chain returns pre-computed dist_price_low/high
        # (these come from the 2-stage model: projected_B4 * mult_c5 with band,
        #  or the historical envelope for macro, or naive med-band for the
        #  insufficient-data path).
        if proj_out['available']:
            anchor_price = proj_out.get('used_anchor_price')
            dist_price_low = proj_out.get('dist_price_low')
            dist_price_high = proj_out.get('dist_price_high')
            anchor_event = proj_out.get('anchor_kind', '')
        else:
            anchor_price = None
            dist_price_low = dist_price_high = None
            anchor_event = ""

        note = proj_out.get('fit_note', 'no data')
        zone_rows.append({
            "asset": asset, "zone": "distribution",
            "base_start": dist_base_start.strftime("%Y-%m-%d"),
            "base_end": dist_base_end.strftime("%Y-%m-%d"),
            "outer_start": dist_outer_start.strftime("%Y-%m-%d"),
            "outer_end": dist_outer_end.strftime("%Y-%m-%d"),
            "price_low": "" if dist_price_low is None else "%.4f" % dist_price_low,
            "price_high": "" if dist_price_high is None else "%.4f" % dist_price_high,
            "anchor_event": anchor_event,
            "anchor_price": "" if anchor_price is None else "%.4f" % anchor_price,
            "compression_fit_used": proj_out.get('mode', 'no_data'),
            "support_band_low": "",
            "support_band_high": "",
            "cross_check_ok": (
                "" if not proj_out.get('proj')
                else str(proj_out['proj'].get('cross_check_ok', ''))
            ),
            "cross_check_rel_diff": (
                "" if not proj_out.get('proj')
                else "%.4f" % proj_out['proj'].get('cross_check_rel_diff', float('nan'))
            ),
            "compression_fit_note": note,
        })

        # --- Exit zone (post-C5 TOP bear bottom = asset B5) ---
        exit_base_start = H5_DATE + timedelta(days=int(ht_median) + int(d_tnb["q25"]))
        exit_base_end = H5_DATE + timedelta(days=int(ht_median) + int(d_tnb["q75"]))
        exit_outer_start = H5_DATE + timedelta(days=int(_num(d_ht["min"])) + int(_num(d_tnb["min"])))
        exit_outer_end = H5_DATE + timedelta(days=int(_num(d_ht["max"])) + int(_num(d_tnb["max"])))

        # Exit price band: post-C5-top bear bottom (= asset B5).
        # For crypto with a 2-stage fit:
        #   B5 (Stage 1 via ratio series  idx=5) if stage1_b5 available;
        #   else approximate via B5 = C5_top * (1 - dd_C5) where dd_C5 is
        #   projected drawdown at idx=5 from the dd power-law fit.
        # For macro without data (mode='macro_not_cycle_tied'): same
        #   historical envelope (no forward projection possible).
        # For macro with data (mode='macro_2_stage_own_shape', I-19): falls
        #   through to the crypto 2-stage branch -- B5 = C5_top * (1 - dd_C5)
        #   using the macro's own projected drawdown at idx=5.
        if (proj_out['available'] and proj_out.get('mode') == 'macro_not_cycle_tied'):
            # Macro without own C4 top or own dd/mult samples: use the
            # historical envelope (no forward projection possible).
            exit_price_low = proj_out.get('dist_price_low')
            exit_price_high = proj_out.get('dist_price_high')
            exit_anchor_kind = 'historical_envelope'
            anchor_price_for_exit = proj_out.get('used_anchor_price')
            exit_anchor_price = anchor_price_for_exit
        elif (proj_out['available'] and proj_out.get('proj')
              and proj_out['proj'].get('mult_c5') is not None):
            # Crypto 2-stage AND macro 2-stage (I-19): estimate B5 via dd on C5
            # (or another Stage 1 ratio extrapolation -- skipped here for
            # simplicity).
            dd_proj = proj_out.get('dd_proj')
            if (dist_price_low is not None and dist_price_high is not None
                    and dd_proj is not None):
                exit_price_low = dist_price_low * (1.0 - dd_proj)
                exit_price_high = dist_price_high * (1.0 - dd_proj)
                exit_anchor_kind = 'dd_x_c5top'
                anchor_price_for_exit = proj_out.get('used_anchor_price')
                exit_anchor_price = (anchor_price_for_exit * (1.0 - dd_proj)
                                     if anchor_price_for_exit is not None else None)
            else:
                exit_price_low = exit_price_high = None
                exit_anchor_kind = exit_anchor_price = None
        else:
            exit_price_low = exit_price_high = None
            exit_anchor_kind = exit_anchor_price = None

        zone_rows.append({
            "asset": asset, "zone": "exit",
            "base_start": exit_base_start.strftime("%Y-%m-%d"),
            "base_end": exit_base_end.strftime("%Y-%m-%d"),
            "outer_start": exit_outer_start.strftime("%Y-%m-%d"),
            "outer_end": exit_outer_end.strftime("%Y-%m-%d"),
            "price_low": "" if exit_price_low is None else "%.4f" % exit_price_low,
            "price_high": "" if exit_price_high is None else "%.4f" % exit_price_high,
            "anchor_event": exit_anchor_kind or "",
            "anchor_price": "" if exit_anchor_price is None else "%.4f" % exit_anchor_price,
            "compression_fit_used": proj_out.get('mode', 'no_data'),
            "support_band_low": "",
            "support_band_high": "",
            "cross_check_ok": (
                "" if not proj_out.get('proj')
                else str(proj_out['proj'].get('cross_check_ok', ''))
            ),
            "cross_check_rel_diff": (
                "" if not proj_out.get('proj')
                else "%.4f" % proj_out['proj'].get('cross_check_rel_diff', float('nan'))
            ),
            "compression_fit_note": (
                "exit: " + proj_out.get('fit_note', 'no data')
            ),
        })

    out = pd.DataFrame(zone_rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)
    print(f"Wrote {OUTPUT} ({len(out)} rows)")
    print()
    print(out[["asset", "zone", "base_start", "base_end",
              "price_low", "price_high", "anchor_event",
              "compression_fit_used"]].to_string(index=False))


if __name__ == "__main__":
    main()

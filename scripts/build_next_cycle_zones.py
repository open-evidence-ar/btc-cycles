"""I-10: BTC next-cycle (C5) zone map, anchored on H5 = 2028-04-01.

Produces ``data/processed/next_cycle_zones.csv`` with three calendar zones
(accumulation / distribution / exit) and, since the 2-stage projection
update (per DESIGN.md 9.4 reconciliation entry), also populates price bands
for the distribution and exit zones using a **2-stage projection model**:

  Stage 1 -- project B4 (post-C4-top bear bottom, the C5 anchor) from the
             bear-bottom-to-bear-bottom ratio series [B0..B3].
  Stage 2 -- project C5 top from B4 using the multiplier power-law fit.
             Cross-check: B4 is also derivable as C4_top * (1 - drawdown_C4);
             disagreement > 15% between Stage 1 and Stage 2 cross-check
             triggers the flag column ``cross_check_ok = False``.
             Cross-check uses the literal C4 top projection (Stage 2a:
             B3 * multiplier(idx=4)) -- both Stage 1 and Stage 2 derive
             from independent inputs (bear-ratio series vs multipliers),
             so their agreement is genuine evidence of model coherence.

Inputs:
  events.csv                            -- canonical cycle anchors (B0..B3 prices)
  data/processed/btc_cycle_metrics.csv  -- per-cycle multipliers + drawdowns
  data/processed/forward_ranges.csv     -- D_* timing distributions

Output:
  data/processed/next_cycle_zones.csv   -- 3 calendar zones + price bands +
                                           derivation columns:
    price_low, price_high              -- USD band per zone
    anchor_event, anchor_price          -- the date/USD anchor used (e.g.
                                          the projected B4 for distribution
                                          and exit; blank for accumulation)
    projected_c4_top_price             -- Stage 2a auxiliary
    projected_b4_stage1, projected_b4_via_drawdown, cross_check_ok
    compression_fit_note               -- human-readable derivation chain
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
)

INPUT_EVENTS = ROOT / "data" / "events.csv"
INPUT_METRICS = ROOT / "data" / "processed" / "btc_cycle_metrics.csv"
INPUT_FWD = ROOT / "data" / "processed" / "forward_ranges.csv"
OUTPUT = ROOT / "data" / "processed" / "next_cycle_zones.csv"

H5_DATE = None  # set inside main() from events.csv


def get_stat_fwd(fwd_df, stat_name):
    row = fwd_df[fwd_df['statistic'] == stat_name].iloc[0]
    return {
        'mean': row['mean'], 'median': row['median'],
        'min': row['min'], 'max': row['max'],
        'q25': row['q25'], 'q75': row['q75'],
    }


def _fmt_usd(v):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return ""
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    if v >= 1e3:
        return f"${v/1e3:.1f}k"
    return f"${v:.0f}"


def main():
    global H5_DATE
    fwd_df = pd.read_csv(INPUT_FWD)
    events = pd.read_csv(INPUT_EVENTS)

    # Load H5 date from events.csv (canonical source)
    h5_row = events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H5')]
    if not h5_row.empty:
        H5_DATE = pd.to_datetime(h5_row.iloc[0]['date'])
    else:
        H5_DATE = pd.to_datetime("2028-04-01")  # fallback

    d_pvbh = get_stat_fwd(fwd_df, 'D_prev_bottom_to_halving')
    d_ht   = get_stat_fwd(fwd_df, 'D_halving_to_top')
    d_tnb  = get_stat_fwd(fwd_df, 'D_top_to_next_bottom')

    # --- Observed C4 top (raw BTC peak since H4) ---
    # The framework assumes C4 is observed for crypto (per time-range argument
    # in the design). For BTC, events.csv may still mark C4 as "not_yet_observed"
    # (Rule T confirmation pending), so we read the peak from raw BTC data:
    btc_raw = pd.read_csv(ROOT / 'data' / 'raw' / 'btc_bitstamp_2026-07-20.csv',
                          parse_dates=['date'])
    btc_post_h4 = btc_raw[btc_raw['date'] >= '2024-04-20'].reset_index(drop=True)
    peak_idx = btc_post_h4['close'].idxmax()
    observed_c4_top_price = float(btc_post_h4.loc[peak_idx, 'close'])
    observed_c4_top_date = btc_post_h4.loc[peak_idx, 'date'].strftime('%Y-%m-%d')

    # --- 2-stage projection (BTC) anchored on the observed C4 top ---
    bear_rows = events[(events['event_type'] == 'bottom')
                       & (events['cycle_id'].isin(['B0', 'B1', 'B2', 'B3']))]
    bear_rows = bear_rows.sort_values('cycle_id')
    bear_prices = bear_rows['price_usd'].astype(float).tolist()

    metrics = pd.read_csv(INPUT_METRICS).set_index('cycle_id')
    # Multipliers per historical cycle: B_{n-1} -> C_n top
    top_rows = events[(events['event_type'] == 'top')
                      & (events['reason_code'] == 'canonical')
                      & (events['cycle_id'].isin(['C1', 'C2', 'C3']))]
    top_rows = top_rows.sort_values('cycle_id').drop_duplicates('cycle_id', keep='last')
    top_prices = top_rows['price_usd'].astype(float).tolist()
    multipliers = [top_prices[i] / bear_prices[i] for i in range(len(top_prices))]
    drawdowns = [float(metrics.loc[c, 'drawdown_pct']) for c in ['C1', 'C2', 'C3']]

    proj = two_stage_projection_with_observed_c4(
        bear_prices, multipliers, drawdowns,
        observed_c4_top_price=observed_c4_top_price,
        observed_c4_top_date=observed_c4_top_date,
        mult_floor=2.0,
    )

    if not proj.get('available'):
        b4 = b4_low = b4_high = c5_top = c5_low = c5_high = None
        c4_dd = None
        cross_check_ok = False
        cross_check_rel_diff = float('nan')
        fit_note = "2-stage projection unavailable: " + proj.get('reason', '?')
    else:
        c4_dd = proj['c4_dd']
        b4 = proj['b4_stage1']
        b4_low = proj['b4_band_low']
        b4_high = proj['b4_band_high']
        c5_top = proj['c5_top']
        c5_low = proj['c5_top_band_low']
        c5_high = proj['c5_top_band_high']
        cross_check_ok = proj['cross_check_ok']
        cross_check_rel_diff = proj['cross_check_rel_diff']
        mult_a = proj['mult_fit']['fit_a']
        mult_b = proj['mult_fit']['fit_b']
        mult_r2 = proj['mult_fit']['r_squared']
        dd_a = proj['dd_fit'].get('fit_a')
        dd_b = proj['dd_fit'].get('fit_b')
        dd_r2 = proj['dd_fit'].get('r_squared')
        ratio_a = proj['stage1']['fit_a']
        ratio_b = proj['stage1']['fit_b']
        ratio_r2 = proj['stage1']['r_squared']
        cross_check_str = "OK" if cross_check_ok else "FAIL"
        dd_a_s = "%.2f" % dd_a if dd_a is not None else "NA"
        dd_b_s = "%.3f" % dd_b if dd_b is not None else "NA"
        dd_r2_s = "%.2f" % dd_r2 if dd_r2 is not None else "NA"
        c4_dd_s = "%.1f%%" % (c4_dd * 100) if c4_dd is not None and math.isfinite(c4_dd) else "NA"
        fit_note = (
            f"Observed C4 top: {observed_c4_top_date} @ {_fmt_usd(observed_c4_top_price)} "
            f"(raw BTC peak since H4). "
            f"Stage 1: bear-bottom ratio series {bear_prices} "
            f"-> ratio_n = {ratio_a:.1f}*idx^{ratio_b:.2f} "
            f"(R2={ratio_r2:.2f}) -> B4/B3 = {proj['stage1']['projected_ratio']:.2f}, "
            f"B4 = {_fmt_usd(b4)}. "
            f"Stage 2: mult_n = {mult_a:.1f}*idx^{mult_b:.2f} "
            f"(R2={mult_r2:.2f}) -> C5 mult={proj['mult_c5']:.2f}; "
            f"dd_n = {dd_a_s}*idx^{dd_b_s} (R2={dd_r2_s}) -> "
            f"C4 dd={c4_dd_s}, B4_via_dd={_fmt_usd(proj['b4_via_drawdown'])}. "
            f"Cross-check: rel_diff={cross_check_rel_diff:+.1%} "
            f"({cross_check_str}). "
            f"C5 top = {_fmt_usd(c5_top)} (band {_fmt_usd(c5_low)} - {_fmt_usd(c5_high)})."
        )

    # --- Build zone rows ---
    # Cycle ordering for the BTC C4 -> C5 transition window:
    #   C4 top (observed: 2025-10-06) -> B4 (bear bottom) -> H5 -> C5 top -> B5
    # The map below is published in chronological order. Each zone has a
    # date band (base = q25..q75, outer = min..max of the relevant duration
    # statistic from forward_ranges.csv) and, where the 2-stage projection
    # supports it, a USD price band.
    zones = []

    # 1) Bear-bottom zone (B4) -- the post-C4-top bear bottom that sits
    #    between the observed C4 top and the projected H5 halving. This is a
    #    first-class event in the cycle chain, not an intermediate: it is
    #    where the 2-stage C5 projection is anchored.
    #    Timing band uses forward-range IQR (same convention as C5
    #    distribution and B5 exit zones): base=Q25-Q75, outer=min-max of
    #    D_top_to_next_bottom. BTC's D_tnb = [364, 378, 406] -> base 371-392d
    #    (21d wide), outer 364-406d (42d wide). This is structurally wider
    #    than the original +-3d/+-7d convention but is consistent with the
    #    other zones and honestly reflects the 3-cycle timing spread.
    if proj.get('available') and b4 is not None:
        tn_q25 = d_tnb.get('q25')
        tn_q75 = d_tnb.get('q75')
        tn_min = d_tnb.get('min')
        tn_max = d_tnb.get('max')
        tn_med = d_tnb['median']
        if (tn_q25 is not None and tn_q75 is not None
                and tn_min is not None and tn_max is not None
                and float(tn_q75) > float(tn_q25)):
            c4_dt = pd.to_datetime(observed_c4_top_date)
            b4_base_start = (c4_dt + timedelta(days=int(float(tn_q25)))).strftime('%Y-%m-%d')
            b4_base_end = (c4_dt + timedelta(days=int(float(tn_q75)))).strftime('%Y-%m-%d')
            b4_outer_start = (c4_dt + timedelta(days=int(float(tn_min)))).strftime('%Y-%m-%d')
            b4_outer_end = (c4_dt + timedelta(days=int(float(tn_max)))).strftime('%Y-%m-%d')
        else:
            b4_center = pd.to_datetime(observed_c4_top_date) + timedelta(days=int(tn_med))
            b4_base_start = (b4_center - timedelta(days=3)).strftime('%Y-%m-%d')
            b4_base_end = (b4_center + timedelta(days=3)).strftime('%Y-%m-%d')
            b4_outer_start = (b4_center - timedelta(days=7)).strftime('%Y-%m-%d')
            b4_outer_end = (b4_center + timedelta(days=7)).strftime('%Y-%m-%d')
        b4_price_low_s = "" if b4_low is None else f"{b4_low:.0f}"
        b4_price_high_s = "" if b4_high is None else f"{b4_high:.0f}"
        cross_check_rel_diff_s = (
            "%.1f%%" % (cross_check_rel_diff * 100)
            if cross_check_rel_diff is not None
            and math.isfinite(cross_check_rel_diff) else "NA"
        )
        b4_fit_note = (
            f"B4 (post-C4-top bear bottom). "
            f"Stage 1: bear-bottom ratio series {bear_prices} "
            f"-> ratio_n = {proj['stage1']['fit_a']:.1f}*idx^{proj['stage1']['fit_b']:.2f} "
            f"(R2={proj['stage1']['r_squared']:.2f}) -> "
            f"B4/B3 = {proj['stage1']['projected_ratio']:.2f}, "
            f"B4 = {_fmt_usd(b4)} "
            f"(band {_fmt_usd(b4_low)} - {_fmt_usd(b4_high)}). "
            f"Cross-check B4_via_dd = {_fmt_usd(proj['b4_via_drawdown'])} "
            f"(rel_diff={cross_check_rel_diff_s}, "
            f"{'OK' if cross_check_ok else 'FAIL'})."
        )
    else:
        # 2-stage projection unavailable
        b4_base_start = b4_base_end = ""
        b4_outer_start = b4_outer_end = ""
        b4_price_low_s = b4_price_high_s = ""
        b4_fit_note = "B4 projection unavailable: " + proj.get('reason', '?')

    # --- Qualitative cross-reference: B4-anchored C5 top vs H5-anchored ---
    # Per the "365-day bear / 1064-day bull" folk narrative: the historical
    # "bottom -> next top" duration is 1050-1067 days across C1->C2, C2->C3,
    # C3->C4 transitions (n=3, median=1059). NOTE: D_bottom_to_next_top is a
    # near-arithmetic identity (equals the next cycle's
    # D_prev_bottom_to_halving + D_halving_to_top), so its tight spread is a
    # decomposition property, NOT an independent rhythm. We surface the
    # B4-anchored projection as a qualitative cross-reference with the folk
    # narrative, not as independent statistical validation. The note is
    # appended to fit_note (which becomes the distribution zone's
    # compression_fit_note).
    if proj.get('available') and b4 is not None and b4_base_start:
        d_bnt_row = fwd_df[fwd_df['statistic'] == 'D_bottom_to_next_top']
        if (not d_bnt_row.empty
                and pd.notna(d_bnt_row.iloc[0].get('median'))):
            d_bnt = d_bnt_row.iloc[0]
            bnt_med = float(d_bnt['median'])
            bnt_q25 = float(d_bnt['q25'])
            bnt_q75 = float(d_bnt['q75'])
            bnt_min = float(d_bnt['min'])
            bnt_max = float(d_bnt['max'])
            bnt_n = int(d_bnt['n'])
            # B4 date: center of base band
            b4_dt_start = pd.to_datetime(b4_base_start)
            b4_dt_end = pd.to_datetime(b4_base_end)
            b4_center_dt = b4_dt_start + (b4_dt_end - b4_dt_start) / 2
            b4_outer_start_dt = pd.to_datetime(b4_outer_start)
            b4_outer_end_dt = pd.to_datetime(b4_outer_end)
            # B4-anchored C5 top dates
            b4_c5_center = (b4_center_dt + timedelta(days=int(bnt_med))).strftime('%Y-%m-%d')
            b4_c5_base_start = (b4_center_dt + timedelta(days=int(bnt_q25))).strftime('%Y-%m-%d')
            b4_c5_base_end = (b4_center_dt + timedelta(days=int(bnt_q75))).strftime('%Y-%m-%d')
            b4_c5_outer_start = (b4_outer_start_dt + timedelta(days=int(bnt_min))).strftime('%Y-%m-%d')
            b4_c5_outer_end = (b4_outer_end_dt + timedelta(days=int(bnt_max))).strftime('%Y-%m-%d')
            # H5-anchored C5 top center
            h5_c5_center = H5_DATE + timedelta(days=int(d_ht['median']))
            # Difference (days) between the two paths' central projections
            try:
                paths_diff_days = (pd.to_datetime(b4_c5_center) - h5_c5_center).days
            except Exception:
                paths_diff_days = None
            diff_str = (f"{paths_diff_days:+d}d" if paths_diff_days is not None else "NA")
            fit_note += (
                f" [Qualitative cross-reference: BTC folk rhythm '365-day bear / "
                f"1064-day bull'. Historical D_bottom_to_next_top n={bnt_n}, "
                f"min={int(bnt_min)}d, max={int(bnt_max)}d, med={int(bnt_med)}d "
                f"(decomposition diagnostic: equals next cycle's "
                f"D_prev_bottom_to_halving + D_halving_to_top; not an "
                f"independent rhythm). "
                f"B4-anchored C5 top: {b4_c5_center} "
                f"(base {b4_c5_base_start}..{b4_c5_base_end}, "
                f"outer {b4_c5_outer_start}..{b4_c5_outer_end}). "
                f"H5-anchored C5 top: {h5_c5_center.strftime('%Y-%m-%d')} "
                f"(base "
                f"{(H5_DATE + timedelta(days=int(d_ht['q25']))).strftime('%Y-%m-%d')}.."
                f"{(H5_DATE + timedelta(days=int(d_ht['q75']))).strftime('%Y-%m-%d')}). "
                f"Centers differ by {diff_str}; B4-anchored band is "
                f"{int(bnt_q75 - bnt_q25)}d wide vs H5-anchored "
                f"{int(float(d_ht['q75']) - float(d_ht['q25']))}d wide.]"
            )

    zones.append({
        'zone': 'bear_bottom',
        'base_start': b4_base_start,
        'base_end': b4_base_end,
        'outer_start': b4_outer_start,
        'outer_end': b4_outer_end,
        'price_low': b4_price_low_s,
        'price_high': b4_price_high_s,
        'anchor_event': "Stage 1 projected B4",
        'anchor_price': "" if b4 is None else f"{b4:.0f}",
        'observed_c4_top_price': f"{observed_c4_top_price:.0f}",
        'observed_c4_top_date': observed_c4_top_date,
        'projected_b4_stage1': "" if b4 is None else f"{b4:.0f}",
        'projected_b4_via_drawdown':
            "" if not proj.get('available') or not math.isfinite(proj.get('b4_via_drawdown', float('nan')))
            else f"{proj['b4_via_drawdown']:.0f}",
        'cross_check_ok': str(cross_check_ok),
        'compression_fit_note': b4_fit_note,
    })

    # 2) Accumulation zone: from B4 to H5 -- the "buy and hold" window.
    #    Base/outer dates anchored on H5 using D_prev_bottom_to_halving
    #    (historical B-to-next-H spacing), but bounded below by B4 outer_end
    #    + 1 day so the B4 event and the accumulation phase do not overlap
    #    on the calendar axis.
    acc_base_start = (H5_DATE - timedelta(days=int(d_pvbh['median'])))
    acc_outer_start = (H5_DATE - timedelta(days=int(d_pvbh['max'])))
    acc_base_end = H5_DATE
    acc_outer_end = H5_DATE
    if proj.get('available') and b4 is not None:
        # Ensure accumulation starts strictly AFTER B4 outer_end
        b4_oe = pd.to_datetime(b4_outer_end)
        if acc_outer_start < b4_oe + timedelta(days=1):
            acc_outer_start = b4_oe + timedelta(days=1)
        # base_start must stay >= outer_start (test_base_within_outer) and
        # must follow B4 base_end (no B4/accumulation overlap).
        acc_outer_start_floor = b4_oe + timedelta(days=1)
        if acc_base_start < acc_outer_start_floor:
            acc_base_start = acc_outer_start_floor
        if acc_base_start < acc_outer_start:
            acc_base_start = acc_outer_start
    zones.append({
        'zone': 'accumulation',
        'base_start': acc_base_start.strftime('%Y-%m-%d'),
        'base_end': acc_base_end.strftime('%Y-%m-%d'),
        'outer_start': acc_outer_start.strftime('%Y-%m-%d'),
        'outer_end': acc_outer_end.strftime('%Y-%m-%d'),
        'price_low': "",
        'price_high': "",
        'anchor_event': "H5",
        'anchor_price': "",
        'observed_c4_top_price': f"{observed_c4_top_price:.0f}",
        'observed_c4_top_date': observed_c4_top_date,
        'projected_b4_stage1': "" if b4 is None else f"{b4:.0f}",
        'projected_b4_via_drawdown':
            "" if not proj.get('available') or not math.isfinite(proj.get('b4_via_drawdown', float('nan')))
            else f"{proj['b4_via_drawdown']:.0f}",
        'cross_check_ok': str(cross_check_ok),
        'compression_fit_note': "acc: starts after B4 event; price-free (entry price = B4 zone).",
    })

    # Distribution zone = C5 TOP window:
    # price band: [C5_top_band_low, C5_top_band_high]
    zones.append({
        'zone': 'distribution',
        'base_start': (H5_DATE + timedelta(days=int(d_ht['q25']))).strftime('%Y-%m-%d'),
        'base_end': (H5_DATE + timedelta(days=int(d_ht['q75']))).strftime('%Y-%m-%d'),
        'outer_start': (H5_DATE + timedelta(days=int(d_ht['min']))).strftime('%Y-%m-%d'),
        'outer_end': (H5_DATE + timedelta(days=int(d_ht['max']))).strftime('%Y-%m-%d'),
        'price_low': "" if c5_low is None else f"{c5_low:.0f}",
        'price_high': "" if c5_high is None else f"{c5_high:.0f}",
        'anchor_event': "projected B4",
        'anchor_price': "" if b4 is None else f"{b4:.0f}",
        'observed_c4_top_price': f"{observed_c4_top_price:.0f}",
        'observed_c4_top_date': observed_c4_top_date,
        'projected_b4_stage1': "" if b4 is None else f"{b4:.0f}",
        'projected_b4_via_drawdown':
            "" if not proj.get('available') or not math.isfinite(proj.get('b4_via_drawdown', float('nan')))
            else f"{proj['b4_via_drawdown']:.0f}",
        'cross_check_ok': str(cross_check_ok),
        'compression_fit_note': fit_note,
    })

    # Exit zone = C5 TOP -> next bear bottom (B5) window:
    # price band: post-C5-top bear bottom (B5), expressed in USD as
    # B5 = B4 * projected_ratio(idx=5)
    if proj.get('available'):
        dd_fit = proj['dd_fit']
        if dd_fit.get('fit_a') is not None and dd_fit.get('fit_b') is not None:
            dd_c5 = max(dd_fit['fit_a'] * (5.0 ** dd_fit['fit_b']), 0.50)
        else:
            dd_c5 = dd_fit.get('projected_value', float('nan'))
        # Stage 1 ratio(idx=5) for B5 -> price level
        try:
            stage1_b5 = proj.get('stage1_b5')
            if stage1_b5 is not None and stage1_b5['used'] == 'power_law_fit':
                b5_low = stage1_b5['price_band_low']
                b5_high = stage1_b5['price_band_high']
            elif stage1_b5 is not None and math.isfinite(stage1_b5.get('projected_price', float('nan'))):
                b5_low = b5_high = stage1_b5['projected_price']
            else:
                # Fallback: use dd on C5
                b5_low = b5_high = c5_top * (1.0 - dd_c5) if c5_top is not None and math.isfinite(dd_c5) else None
        except Exception:
            b5_low = b5_high = c5_top * (1.0 - dd_c5) if c5_top is not None and math.isfinite(dd_c5) else None
    else:
        b5_low = b5_high = None
        dd_c5 = None

    zones.append({
        'zone': 'exit',
        'base_start': (H5_DATE + timedelta(days=int(d_ht['median']) + int(d_tnb['q25']))).strftime('%Y-%m-%d'),
        'base_end': (H5_DATE + timedelta(days=int(d_ht['median']) + int(d_tnb['q75']))).strftime('%Y-%m-%d'),
        'outer_start': (H5_DATE + timedelta(days=int(d_ht['min']) + int(d_tnb['min']))).strftime('%Y-%m-%d'),
        'outer_end': (H5_DATE + timedelta(days=int(d_ht['max']) + int(d_tnb['max']))).strftime('%Y-%m-%d'),
        'price_low': "" if b5_low is None else f"{b5_low:.0f}",
        'price_high': "" if b5_high is None else f"{b5_high:.0f}",
        'anchor_event': "projected B5",
        'anchor_price': "" if b5_low is None or b5_high is None
                          else f"{(b5_low + b5_high) / 2:.0f}",
        'observed_c4_top_price': f"{observed_c4_top_price:.0f}",
        'observed_c4_top_date': observed_c4_top_date,
        'projected_b4_stage1': "" if b4 is None else f"{b4:.0f}",
        'projected_b4_via_drawdown':
            "" if not proj.get('available') or not math.isfinite(proj.get('b4_via_drawdown', float('nan')))
            else f"{proj['b4_via_drawdown']:.0f}",
        'cross_check_ok': str(cross_check_ok),
        'compression_fit_note': (
            "exit: B5 (post-C5-top) projected from Stage-1 ratio(idx=5) = "
            + _fmt_usd(b5_low) + " - " + _fmt_usd(b5_high) + ". "
            + (f"(C5 dd projection = {dd_c5:.1%}.)" if dd_c5 is not None else "(C5 dd NA.)")
        ),
    })

    out = pd.DataFrame(zones)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(out)} rows to {OUTPUT}")
    print()
    print(out[['zone', 'base_start', 'base_end', 'price_low', 'price_high',
              'anchor_event', 'anchor_price']].to_string(index=False))
    print()
    print("Compression-fit note (distribution zone):")
    print("  " + (fit_note if proj.get('available') else "N/A"))


if __name__ == '__main__':
    main()

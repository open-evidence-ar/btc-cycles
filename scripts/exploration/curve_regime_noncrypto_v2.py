#!/usr/bin/env python3
"""
exploration/curve_regime_noncrypto_v2.py  -  Exploration-2 (I-21 round-2).
Reads round-1 derived curve-shape series; tests H7..H10 per the pre-committed
rubric in docs/blockers/I-21-eurodollar-proxies-exploration-2.md (BLOCKER doc
written separately, see below).

Hypotheses (committed in advance, per the discipline established in round-1):
  H7  Non-crypto asset extrema align with curve_shape_state transitions.
      Rubric: per-asset, per-extremum predictions (OR-patterns allowed).
      Scoring: strict (any day of predicted state in +/-120d = match, else 0).
      Threshold: >=2/3 extrema per asset survives for >=4/5 assets.

  H8  Dominant curve-state at asset's cycle top correlates with subsequent
      drawdown_pct. Ordinal encoding: normal=0, bear_steep=1,
      inverted_flat=2, bull_steep=3.
      Threshold: |Spearman rho| >= 0.4 across pooled (asset x cycle) sample.

  H9  Pre-extremum curve-state distribution (250 trading days before
      extremum) differs from unconditional distribution.
      Threshold: JS divergence >= 0.1 for >=3/5 assets.

  H10 BTC's 60-day forward return at each non-crypto asset's extremum,
      conditioned on curve-state (nominal encoding, no ordinal ranking).
      Threshold: BTC forward-return sign diverges across >=2 state pairs.

Promotion rule (committed in advance):
  If H7 AND (H8 OR H9) survive -> a proper I-21 increment becomes justified,
  scoped as Option A (descriptive overlay only).
  Else (only H7, only H10, or none) -> close as published mixed/negative.

No model change. No framework artifacts touched. Outputs only:
  - data/processed/exploration_eu_proxies_v2.csv (mutable)
  - stdout verdict block
  - separate blocker note docs/blockers/I-21-eurodollar-proxies-exploration-2.md
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent

# ------------------------------------------------------------------
# Inputs (read-only)
# ------------------------------------------------------------------
ROUND1_DERIVED = ROOT / "data" / "processed" / "exploration_eu_proxies.csv"
ALT_METRICS    = ROOT / "data" / "processed" / "alt_cycle_metrics.csv"
BTC_RAW        = sorted((ROOT / "data" / "raw").glob("btc_bitstamp_*.csv"))[-1]

OUT_PATH = ROOT / "data" / "processed" / "exploration_eu_proxies_v2.csv"

# ------------------------------------------------------------------
# Pre-committed rubric (LOCKED before running)
#   Predictions use OR-patterns; scoring: any day of predicted state in
#   +/-120d window = 1, else 0. See blocker doc round-2 for full reasoning.
# ------------------------------------------------------------------
H7_RUBRIC = {
    # (asset, event_kind): set of predicted states appearing in +/-120d window
    ("spx",  "top"):    {"inverted_flat", "bull_steep"},  # NOT normal, NOT bear_steep
    ("spx",  "bottom"): {"bear_steep", "normal"},         # recovery / benign
    ("ndx",  "top"):    {"inverted_flat", "bull_steep"},
    ("ndx",  "bottom"): {"bear_steep", "normal"},
    ("dxy",  "top"):    {"inverted_flat"},                # strong-dollar = restrictive only
    ("dxy",  "bottom"): {"bull_steep", "bear_steep"},     # un-inverting pressure
    ("tlt",  "top"):    {"bull_steep", "inverted_flat"},  # duration-peak regimes
    ("tlt",  "bottom"): {"bear_steep", "normal"},         # long-yields-rising / normalized
    ("gold", "top"):    {"bull_steep", "inverted_flat"},  # risk-off / cut-cycle exhaustion
    ("gold", "bottom"): {"bear_steep", "normal"},        # growth-pricing / benign
}

ASSETS = ["spx", "ndx", "dxy", "tlt", "gold"]

# Curve-state ordinal encoding for H8 (LOCKED; see blocker doc)
STATE_ORDINAL = {"normal": 0, "bear_steep": 1, "inverted_flat": 2, "bull_steep": 3}

# Unconditional curve-state distribution (round-1, for H9 reference)
UNCONDITIONAL_DIST = {  # from round-1 curve_shape_state value_counts / 9007
    "normal":        7508 / 9007,
    "bull_steep":     608 / 9007,
    "bear_steep":     535 / 9007,
    "inverted_flat":  356 / 9007,
}

WINDOW_DAYS = 120   # H7 scoring window
PRE_WIN_DAYS = 250  # H9 pre-extremum lookback
BTC_FWD_HORIZON = 60  # H10 forward-return horizon in days


def load_round1_derived():
    """Load round-1 daily derived curve-shape series."""
    df = pd.read_csv(ROUND1_DERIVED, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    # Drop the appended placeholder row from round-1 skeleton if present
    df = df[df["curve_shape_state"].notna()]
    df = df[df["curve_shape_state"] != "UNCOMPUTED (DGS10/DGS2 MISSING)"]
    df = df[df["curve_shape_state"] != "UNCLASSIFIED (see blocker I-21, A5 verdicts)"]
    df = df[df["curve_shape_state"] != "unclassified"]
    # Also drop NaNs
    df = df[df["curve_shape_state"].isin(["normal", "bear_steep", "bull_steep", "inverted_flat"])]
    return df[["curve_shape_state"]]


def load_asset_extrema():
    """Load per-asset per-cycle top/bottom dates from alt_cycle_metrics.csv."""
    df = pd.read_csv(ALT_METRICS)
    # Keep only the 5 non-crypto assets
    df = df[df["asset"].isin(ASSETS)].copy()
    # Keep only cycles with actual data (drop missing/proxy rows that lack dates)
    df = df[df["cycle_source"].isin(["actual", "actual_C4_open"])].copy()
    rows = []
    for _, r in df.iterrows():
        # Top event
        if pd.notna(r["asset_local_top_date"]):
            rows.append({
                "asset": r["asset"],
                "cycle_id": r["cycle_id"],
                "event_kind": "top",
                "date": pd.to_datetime(r["asset_local_top_date"]),
                "drawdown_pct": r["drawdown_asset_pct"] if pd.notna(r["drawdown_asset_pct"]) else np.nan,
            })
        # Bottom event
        if pd.notna(r["asset_next_bear_bottom_date"]):
            rows.append({
                "asset": r["asset"],
                "cycle_id": r["cycle_id"],
                "event_kind": "bottom",
                "date": pd.to_datetime(r["asset_next_bear_bottom_date"]),
                "drawdown_pct": np.nan,  # bottom event has no "subsequent drawdown"
            })
    return pd.DataFrame(rows).sort_values(["asset", "date"]).reset_index(drop=True)


def load_btc():
    """Load BTC close for H10 forward returns."""
    df = pd.read_csv(BTC_RAW, parse_dates=["date"])
    return df.set_index("date").sort_index()[["close"]].rename(columns={"close": "btc"})


def states_in_window(state_series, center_date, half_window=WINDOW_DAYS):
    """Return set of unique curve_shape_state values in +/- half_window days."""
    if isinstance(state_series, pd.DataFrame):
        s = state_series.iloc[:, 0]
    else:
        s = state_series
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    center = pd.Timestamp(center_date)
    lo = center - pd.Timedelta(days=half_window)
    hi = center + pd.Timedelta(days=half_window)
    sub = s[(s.index >= lo) & (s.index <= hi)]
    return set(sub.unique())


# ------------------------------------------------------------------
# H7: per-asset, per-extremum prediction scoring
# ------------------------------------------------------------------
def score_h7(state_series, extrema_df):
    results = []
    for _, r in extrema_df.iterrows():
        key = (r["asset"], r["event_kind"])
        predicted = H7_RUBRIC.get(key, set())
        observed = states_in_window(state_series, r["date"], WINDOW_DAYS)
        if not observed:
            match = None
            observed_str = "NO_DATA"
        else:
            match = int(bool(predicted & observed))
            observed_str = ",".join(sorted(observed))
        results.append({
            "asset": r["asset"],
            "cycle_id": r["cycle_id"],
            "event_kind": r["event_kind"],
            "date": r["date"].strftime("%Y-%m-%d"),
            "predicted": ",".join(sorted(predicted)),
            "observed": observed_str,
            "match": match,
        })
    res_df = pd.DataFrame(results)

    # Per-asset score
    print("\nH7 per-extremum scoring:")
    for _, r in res_df.iterrows():
        m = "/" if r["match"] is None else str(r["match"])
        print(f"  {r['asset']:5s} {r['cycle_id']} {r['event_kind']:6s} {r['date']} "
              f"predicted={r['predicted']:30s} observed={r['observed']:45s} match={m}")

    per_asset = res_df[res_df["match"].notna()].groupby("asset").agg(
        n_extrema=("match", "count"),
        n_match=("match", "sum"),
    )
    per_asset["fraction"] = per_asset["n_match"] / per_asset["n_extrema"]
    print("\nH7 per-asset survival (threshold: >=2/3 extrema match):")
    for asset, row in per_asset.iterrows():
        survived = row["fraction"] >= 2/3
        print(f"  {asset:5s}: {int(row['n_match'])}/{int(row['n_extrema'])} = {row['fraction']:.2f} "
              f"({'PASS' if survived else 'fail'})")
    n_assets_passing = (per_asset["fraction"] >= 2/3).sum()
    h7_passed = n_assets_passing >= 4  # threshold >=4/5
    print(f"\nH7 verdict: {'PASS' if h7_passed else 'REJECTED'}  "
          f"{n_assets_passing}/5 assets meet >=2/3 threshold (need >=4/5)")
    return h7_passed, res_df, per_asset


# ------------------------------------------------------------------
# H8: state-ordinal vs drawdown correlation
# ------------------------------------------------------------------
def score_h8(state_series, extrema_df):
    """Use the CURVE STATE AT each asset's TOP (only top events have subsequent
    drawdown). Encode state via STATE_ORDINAL, compute Spearman vs drawdown_pct."""
    tops = extrema_df[(extrema_df["event_kind"] == "top") & extrema_df["drawdown_pct"].notna()].copy()
    if state_series.index.tz is not None:
        state_series.index = state_series.index.tz_localize(None)
    # Find state at center date; if NaN, fallback to most-common state in +/-30d
    def state_at(date):
        if pd.Timestamp(date) in state_series.index:
            return state_series.loc[pd.Timestamp(date)]
        lo = pd.Timestamp(date) - pd.Timedelta(days=30)
        hi = pd.Timestamp(date) + pd.Timedelta(days=30)
        sub = state_series[(state_series.index >= lo) & (state_series.index <= hi)]
        if sub.empty:
            return np.nan
        return sub.mode().iloc[0]
    tops["state_at_top"] = tops["date"].apply(state_at)
    tops["state_ordinal"] = tops["state_at_top"].map(STATE_ORDINAL)
    tops = tops.dropna(subset=["state_ordinal", "drawdown_pct"])

    print("\nH8 state-at-top vs drawdown:")
    for _, r in tops.iterrows():
        print(f"  {r['asset']:5s} {r['cycle_id']} top={r['date'].strftime('%Y-%m-%d')} "
              f"state={r['state_at_top']:15s} ord={int(r['state_ordinal'])} "
              f"drawdown={r['drawdown_pct']*100:.1f}%")

    if len(tops) < 5:
        print(f"\nH8: only {len(tops)} valid samples - insufficient for Spearman")
        return False, tops

    # Manual Spearman: rank both columns, compute Pearson on ranks
    # (scipy not available in this env, so use pure numpy/pandas)
    def manual_spearman(a, b):
        a = pd.Series(a); b = pd.Series(b)
        joint = pd.concat([a, b], axis=1).dropna()
        if len(joint) < 5:
            return np.nan
        ra = joint.iloc[:, 0].rank()
        rb = joint.iloc[:, 1].rank()
        return ra.corr(rb, method="pearson")
    rho = manual_spearman(tops["state_ordinal"], tops["drawdown_pct"])
    h8_passed = abs(rho) >= 0.4
    print(f"\nH8 verdict: {'PASS' if h8_passed else 'REJECTED'}  "
          f"Spearman rho={rho:.3f} (threshold |rho| >= 0.4, n={len(tops)})")
    return h8_passed, tops


# ------------------------------------------------------------------
# H9: pre-extremum state distribution vs unconditional
# ------------------------------------------------------------------
def js_divergence(p_dist, q_dist):
    """Jensen-Shannon divergence between two probability distributions
    (dicts of state -> prob). Symmetric; bounded by ln(2) ~= 0.693."""
    states = set(p_dist) | set(q_dist)
    p = np.array([p_dist.get(s, 0.0) for s in states])
    q = np.array([q_dist.get(s, 0.0) for s in states])
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q
    m = 0.5 * (p + q)
    # KL with 0*log(0) := 0
    def kl(x, y):
        mask = x > 0
        return np.sum(x[mask] * np.log2(x[mask] / y[mask]))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def score_h9(state_series, extrema_df):
    """For each asset's extremum, compute state distribution over the
    PRE_WIN_DAYS trading days BEFORE the event. Compare to unconditional
    via JS divergence. Asset passes if mean JS divergence across its
    extrema >= 0.1."""
    if state_series.index.tz is not None:
        state_series.index = state_series.index.tz_localize(None)
    # Empirical lookback: PRE_WIN_DAYS trading days = roughly PRE_WIN_DAYS
    # calendar days * (5/7), but easier to just take the nearest PRE_WIN_DAYS
    # rows before the event (trading-day basis). Since state_series has
    # daily crypto-calendar rows (7d/week), we take PRE_WIN_DAYS calendar days.
    results = []
    for _, r in extrema_df.iterrows():
        center = pd.Timestamp(r["date"])
        # Use calendar-day window in crypto calendar (7d/week)
        lo = center - pd.Timedelta(days=PRE_WIN_DAYS)
        sub = state_series[(state_series.index < center) & (state_series.index >= lo)]
        if sub.empty:
            results.append({"asset": r["asset"], "date": r["date"],
                            "event_kind": r["event_kind"], "js": np.nan,
                            "dist": "NO_DATA"})
            continue
        # State distribution: count occurrences
        counts = sub.value_counts()
        total = counts.sum()
        dist = {state: counts.get(state, 0) / total for state in ["normal", "bear_steep", "bull_steep", "inverted_flat"]}
        js = js_divergence(dist, UNCONDITIONAL_DIST)
        results.append({
            "asset": r["asset"], "date": r["date"], "event_kind": r["event_kind"],
            "js": js, "dist": "  ".join(f"{k}={v:.2f}" for k, v in dist.items()),
        })
    res_df = pd.DataFrame(results)

    print("\nH9 pre-extremum JS divergence from unconditional (threshold per-asset mean >= 0.1):")
    for _, r in res_df.iterrows():
        if pd.isna(r["js"]):
            print(f"  {r['asset']:5s} {r['date'].strftime('%Y-%m-%d')} JS=NO_DATA  ({r['event_kind']})")
        else:
            print(f"  {r['asset']:5s} {r['date'].strftime('%Y-%m-%d')} JS={r['js']:.4f}  ({r['event_kind']})  [{r['dist']}]")

    # Per-asset: average JS across its extrema
    per_asset_js = res_df.dropna(subset=["js"]).groupby("asset")["js"].mean()
    print("\nH9 per-asset mean JS divergence (threshold >= 0.1):")
    for asset, mu in per_asset_js.items():
        survived = mu >= 0.1
        print(f"  {asset:5s}: mean JS={mu:.4f}  ({'PASS' if survived else 'fail'})")
    n_passing = (per_asset_js >= 0.1).sum()
    h9_passed = n_passing >= 3  # threshold >=3/5
    print(f"\nH9 verdict: {'PASS' if h9_passed else 'REJECTED'}  "
          f"{n_passing}/5 assets meet >=0.1 JS threshold (need >=3/5)")
    return h9_passed, res_df, per_asset_js


# ------------------------------------------------------------------
# H10: BTC forward returns at non-crypto extrema, conditioned on state
# ------------------------------------------------------------------
def score_h10(state_series, extrema_df, btc):
    """At each non-crypto asset's extremum, compute BTC's 60-day forward
    return. Tag with the curve_shape_state at the extremum date. Test:
    sign of mean BTC forward-return differs across state pairs.
    Survival: >=2 state pairs show opposite signs."""
    if state_series.index.tz is not None:
        state_series.index = state_series.index.tz_localize(None)
    # Align BTC to date index
    btc = btc.copy()
    if btc.index.tz is not None:
        btc.index = btc.index.tz_localize(None)
    btc = btc[~btc.index.duplicated(keep="first")].sort_index()

    # 60-day forward return: ratio of close t+60 to close t
    btc_fwd = btc["btc"].shift(-BTC_FWD_HORIZON) / btc["btc"] - 1.0
    btc_fwd.name = "btc_fwd60d"

    # State on each date
    state_aligned = state_series.reindex(btc.index, method="nearest")
    df = pd.concat([btc, btc_fwd, state_aligned], axis=1)

    # For each extremum, capture (state, btc_fwd60d)
    rows = []
    for _, r in extrema_df.iterrows():
        center = pd.Timestamp(r["date"])
        # find nearest row
        idx_loc = df.index.get_indexer([center], method="nearest")[0]
        if idx_loc < 0 or idx_loc >= len(df):
            continue
        row = df.iloc[idx_loc]
        rows.append({
            "asset": r["asset"], "cycle_id": r["cycle_id"], "event_kind": r["event_kind"],
            "date": r["date"].strftime("%Y-%m-%d"),
            "state_at": row["curve_shape_state"],
            "btc_fwd60d": row["btc_fwd60d"],
        })
    res_df = pd.DataFrame(rows).dropna(subset=["state_at", "btc_fwd60d"])

    print("\nH10 BTC 60-day forward return at each non-crypto extremum, tagged by state:")
    for _, r in res_df.iterrows():
        print(f"  {r['asset']:5s} {r['cycle_id']} {r['event_kind']:6s} {r['date']} "
              f"state={r['state_at']:15s} btc_fwd60d={r['btc_fwd60d']*100:+.2f}%")

    # Group by state and compute mean / sign
    state_means = res_df.groupby("state_at")["btc_fwd60d"].agg(["mean", "count"])
    print("\nH10 BTC forward-return by state:")
    for state, row in state_means.iterrows():
        print(f"  {state:15s}: mean={row['mean']*100:+.2f}%  n={int(row['count'])}")

    # Pairwise sign test: count state pairs where means have opposite signs
    state_list = state_means.index.tolist()
    opposite_sign_pairs = 0
    total_pairs = 0
    pair_details = []
    for i in range(len(state_list)):
        for j in range(i + 1, len(state_list)):
            total_pairs += 1
            m1 = state_means.loc[state_list[i], "mean"]
            m2 = state_means.loc[state_list[j], "mean"]
            opp = (np.sign(m1) != np.sign(m2)) and (np.sign(m1) != 0) and (np.sign(m2) != 0)
            if opp:
                opposite_sign_pairs += 1
            pair_details.append(f"    {state_list[i]:15s} ({m1*100:+.2f}%) vs "
                                f"{state_list[j]:15s} ({m2*100:+.2f}%) -> {'OPP' if opp else 'same'}")
    print("\nH10 state-pair sign comparison:")
    for line in pair_details:
        print(line)

    h10_passed = opposite_sign_pairs >= 2
    print(f"\nH10 verdict: {'PASS' if h10_passed else 'REJECTED'}  "
          f"{opposite_sign_pairs}/{total_pairs} state pairs show opposite-sign BTC fwd returns (need >=2)")
    return h10_passed, res_df, state_means


def main():
    print("Loading round-1 derived curve-state series...")
    state_series = load_round1_derived()
    print(f"  round-1 series: {len(state_series)} rows, {state_series.index.min().date()}..{state_series.index.max().date()}")

    print("\nLoading per-asset extrema from alt_cycle_metrics.csv...")
    extrema = load_asset_extrema()
    print(f"  loaded {len(extrema)} extrema across {extrema['asset'].nunique()} assets")
    print(extrema.groupby(["asset", "event_kind"]).size().to_string())

    print("\nLoading BTC for H10...")
    btc = load_btc()
    print(f"  BTC: {len(btc)} rows, {btc.index.min().date()}..{btc.index.max().date()}")

    # ------------------------------------------------------------------
    # Run all four hypotheses
    # ------------------------------------------------------------------
    print("\n" + "=" * 64)
    print("RUNNING H7 -- per-asset extrema alignment with curve-shape state")
    print("=" * 64)
    h7_passed, h7_results, h7_per_asset = score_h7(state_series, extrema)

    print("\n" + "=" * 64)
    print("RUNNING H8 -- state-ordinal vs drawdown correlation")
    print("=" * 64)
    h8_passed, h8_results = score_h8(state_series, extrema)

    print("\n" + "=" * 64)
    print("RUNNING H9 -- pre-extremum state divergence from unconditional")
    print("=" * 64)
    h9_passed, h9_results, h9_per_asset = score_h9(state_series, extrema)

    print("\n" + "=" * 64)
    print("RUNNING H10 -- BTC fwd return at non-crypto extrema, conditioned on state")
    print("=" * 64)
    h10_passed, h10_results, h10_state_means = score_h10(state_series, extrema, btc)

    # ------------------------------------------------------------------
    # Write consolidated mutable CSV (for the blocker doc to reference)
    # ------------------------------------------------------------------
    out = extrema.copy()
    out["date_str"] = out["date"].dt.strftime("%Y-%m-%d")
    out["observed_states"] = out.apply(
        lambda r: ",".join(sorted(states_in_window(state_series, r["date"], WINDOW_DAYS))),
        axis=1
    )
    out["predicted_states"] = out.apply(
        lambda r: ",".join(sorted(H7_RUBRIC.get((r["asset"], r["event_kind"]), set()))),
        axis=1
    )
    out["h7_match"] = out.apply(
        lambda r: int(bool(set(r["predicted_states"].split(",")) & set(r["observed_states"].split(",")))),
        axis=1
    ) if (out["observed_states"].str.len() > 0).any() else np.nan
    out.to_csv(OUT_PATH, index=False)
    print(f"\nWrote consolidated artifact: {OUT_PATH.relative_to(ROOT)}  ({len(out)} rows)")

    # ------------------------------------------------------------------
    # FINAL VERDICT and promotion rule
    # ------------------------------------------------------------------
    print("\n" + "=" * 64)
    print("FINAL VERDICTS (round-2)")
    print("=" * 64)
    print(f"H7: {'PASS' if h7_passed else 'REJECTED'}  (per-asset extrema alignment)")
    print(f"H8: {'PASS' if h8_passed else 'REJECTED'}  (state-drawdown correlation)")
    print(f"H9: {'PASS' if h9_passed else 'REJECTED'}  (pre-extremum distribution divergence)")
    print(f"H10: {'PASS' if h10_passed else 'REJECTED'}  (BTC fwd-return conditioned on state)")

    promotion = h7_passed and (h8_passed or h9_passed)
    print("\n" + "=" * 64)
    print("PROMOTION DECISION")
    print("=" * 64)
    print("Rule committed in advance: H7 AND (H8 OR H9) -> I-21 proper justified (Option A descriptive overlay)")
    if promotion:
        print(f"  H7={h7_passed}, H8={h8_passed}, H9={h9_passed}, H10={h10_passed}")
        print("  PROMOTION TRIGGERED: open I-21 proper increment (descriptive overlay only)")
    else:
        reasons = []
        if not h7_passed:
            reasons.append("H7 rejected (per-asset extrema do not align with rubric)")
        if not (h8_passed or h9_passed):
            reasons.append("neither H8 nor H9 passed")
        print(f"  H7={h7_passed}, H8={h8_passed}, H9={h9_passed}, H10={h10_passed}")
        print("  NOT TRIGGERED: " + "; ".join(reasons))
        print("  -> exploration closes as published mixed/negative finding")
        if h10_passed and h7_passed:
            print("  NOTE: H7 + H10 both passed but H8/H9 did not - partial signal worth recording")
        elif h10_passed:
            print("  NOTE: only H10 passed - BTC behavior at macro landmarks is regime-dependent,")
            print("        but macro extrema themselves do not align with curve-shape transitions")
        elif h7_passed:
            print("  NOTE: only H7 passed - macro extrema align with curve-shape transitions,")
            print("        but no downstream projection conditioning is justified")


if __name__ == "__main__":
    main()

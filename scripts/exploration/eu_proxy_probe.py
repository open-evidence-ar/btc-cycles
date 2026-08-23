#!/usr/bin/env python3
"""
exploration/eu_proxy_probe.py  —  Exploration-only script (I-21 exploration v2).

Sources actually used in this revision:
  - Yahoo-sourced Cboe yield indices via scripts/exploration/fetch_yield_indices.py:
        y10_yahoo.csv  (^TNX, 10y)          [1990-01-02..]
        y5_yahoo.csv   (^FVX, 5y)           [1990-01-02..]
        y13w_yahoo.csv (^IRX, 13-week bill) [1990-01-02..]
  - Existing framework snapshot BTC:  data/raw/btc_bitstamp_2026-07-30.csv
  - Existing framework snapshot DXY/TLT: data/raw/dxy_yahoo_2026-08-01.csv,
                                          data/raw/tlt_yahoo_2026-08-01.csv
  - Cycle anchors:                     data/events.csv (canonical T1..T4, B1..B3)
  - Phase csv (for cross-reference):   data/processed/correlations_phase.csv
  - Cycle metrics:                     data/processed/btc_cycle_metrics.csv

Hypotheses that can be TESTED with this data set:
  H1 (curve-shape transition at BTC extrema)   -- YES, can test
  H6 (2007-08-09 BNP-Paribas structural break) -- YES, can test on ^TNX

Hypotheses that CANNOT be tested in this revision (honest caveat):
  H2 (TIPS break-even gap)       : no FRED T5YIE/T5YIFR fetched; TIP ETF
                                   price alone cannot decompose break-even;
                                   verdict remains UNVERIFIED.
  H3 (swap-spread / dealer-B/S)  : BAMLC1A0C13Y not fetched; ^VIX is the
                                   only risk proxy available, and it's
                                   well-known orthogonal to dealer B/S;
                                   verdict remains UNVERIFIED with §3.4
                                   caveat.
  H4 (joint-state agreement)     : requires H1+H2+H3; H2/H3 unverified ->
                                   H4 UNVERIFIED.
  H5 (snapshot EU label)         : requires H1..H3; UNVERIFIED.

This means H1 and H6 yield real verdicts; H2..H5 stay UNVERIFIED. The
promotion rule (>=3 of H1..H4 surviving) cannot be triggered this run
even with H1+H6 both passing — the blocker doc will record this honestly.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd


def welch_t_test(a, b):
    """Welles two-sample t-test (unequal variance) without scipy.
    Returns (t_stat, p_value) using t-distribution via scipy if available,
    else just the t-statistic (p-val approximated via normal for large n)."""
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    n1 = len(a); n2 = len(b)
    if n1 < 2 or n2 < 2:
        return float("nan"), float("nan")
    m1, m2 = a.mean(), b.mean()
    v1, v2 = a.var(ddof=1), b.var(ddof=1)
    se = np.sqrt(v1/n1 + v2/n2)
    if se == 0:
        return 0.0, 1.0
    t = (m1 - m2) / se
    # Welch-Satterthwaite df
    df_num = (v1/n1 + v2/n2) ** 2
    df_den = (v1/n1) ** 2 / (n1 - 1) + (v2/n2) ** 2 / (n2 - 1)
    df = df_num / df_den if df_den > 0 else float(n1 + n2 - 2)
    # Use scipy for the t-distribution CDF if it's importable; else normal approx.
    try:
        from scipy import stats as _st
        p = 2 * (1 - _st.t.cdf(abs(t), df=df))
    except Exception:
        # Normal approx for large df (df>30 -> error <1%)
        from math import erf
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / np.sqrt(2))))
    return float(t), float(p)

ROOT = Path(__file__).resolve().parent.parent.parent
EXP_DIR = ROOT / "data" / "raw" / "exploration"
OUT_PATH = ROOT / "data" / "processed" / "exploration_eu_proxies.csv"

# ---- Pre-committed BTC extrema from data/events.csv (DO NOT tune) ----
# (date, label, EU-predicted curve state per §4.2)
EXTREMA = [
    ("2013-12-04", "T1", "unclassified"),        # skip: pre-2007 break, also before DGx2 reliable 2y data
    ("2013-04-09", "T1_first", "unclassified"),   # also skipped per §4.2 footnote
    ("2017-12-17", "T2", "bull_steep"),           # EU expects inversion->bull-steep transition
    ("2021-11-10", "T3", "inverted_flat"),        # deeply inverted + bull-steep emerging (per §4.2)
    ("2025-10-06", "T4", "bull_steep"),           # EU's "Forgot How to Grow" bull-steepener
    ("2015-01-14", "B1", "bull_steep"),           # post-taper, EU "bad for world"
    ("2018-12-15", "B2", "bull_steep"),           # Dec 2018 Powell pivot, bull steepening
    ("2022-11-21", "B3", "bull_steep"),           # post-COVID Fed-hike inversion -> bull steepening
]

H1_DENOM = sum(1 for _, _, eu in EXTREMA if eu != "unclassified")  # 6 expected tests (T1 + T1_first skipped)


def load_yahoo_yield(name):
    f = EXP_DIR / f"{name}_yahoo.csv"
    if not f.exists():
        return None
    df = pd.read_csv(f)
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "close"]].rename(columns={"close": name}).set_index("date")


def load_existing_raw(symbol):
    matches = sorted((ROOT / "data" / "raw").glob(f"{symbol}_yahoo_*.csv"))
    if not matches:
        return None
    df = pd.read_csv(matches[-1])
    df["date"] = pd.to_datetime(df["date"])
    cols = [c for c in df.columns if c.lower() in ("close", "adjclose", "adj close")]
    if not cols:
        return None
    return df[["date", cols[0]]].rename(columns={cols[0]: symbol}).set_index("date")


def load_btc():
    matches = sorted((ROOT / "data" / "raw").glob("btc_bitstamp_*.csv"))
    df = pd.read_csv(matches[-1])
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "close"]].rename(columns={"close": "btc"}).set_index("date")


# ------------------------------------------------------------------
# Curve-shape classifier — per blocker doc §4.1 (PRE-COMMITTED)
# ------------------------------------------------------------------
def classify_curve(row, slope_col, delta_col):
    """Pre-committed thresholds from §4.1 of blocker doc."""
    slope = row[slope_col]
    dslop = row[delta_col]
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


def make_state_anywhere_in_window(state_series: pd.Series, center_date, half_window_days=120):
    """Return TRUE if any day in [center-half, center+half] has the EU-expected state."""
    if state_series.index.tz is not None:
        state_series.index = state_series.index.tz_localize(None)
    center = pd.Timestamp(center_date)
    lo = center - pd.Timedelta(days=half_window_days)
    hi = center + pd.Timedelta(days=half_window_days)
    sub = state_series[(state_series.index >= lo) & (state_series.index <= hi)]
    if sub.empty:
        return None
    return sorted(sub.unique().tolist())


def score_h1(state_series):
    """Score H1 per pre-committed §4.2 prediction table.
    H1 survives if score >= 5 of 6 (T1/T1_first skipped per §4.2)."""
    results = []
    score = 0
    denom = 0
    for date_str, label, expected in EXTREMA:
        if expected == "unclassified":
            results.append((label, date_str, expected, "SKIPPED", "n/a"))
            continue
        states = make_state_anywhere_in_window(state_series, date_str)
        denom += 1
        if states is None:
            results.append((label, date_str, expected, "NO_DATA", 0))
            continue
        match = expected in states
        if match:
            score += 1
        results.append((label, date_str, expected, ",".join(states), int(match)))
    passed = score >= 5
    return passed, score, denom, results


def chow_test(y_series, breakpoint):
    """Simple Chow test on log-returns splitting before/after breakpoint.
    Returns F-stat; tests equality of means+variances on log-returns."""
    lr = np.log(y_series).diff().dropna()
    # drop NaNs around first row
    lr = lr.dropna()
    before = lr[lr.index < breakpoint]
    after  = lr[lr.index >= breakpoint]
    n1 = len(before); n2 = len(after)
    if n1 < 30 or n2 < 30:
        return None, n1, n2
    # Restrict 'after' to the same length window to avoid drift contamination
    after_win = after.iloc[:n1] if len(after) >= n1 else after
    # two-sample t-test on log-returns (mean equality)
    t_stat, p_val = welch_t_test(before.values, after_win.values)
    # Levene for variance equality — simplified to F = var1/var2 (avoid scipy dependency)
    if len(before.dropna()) >= 30 and len(after_win.dropna()) >= 30:
        var_before = float(np.var(before.dropna(), ddof=1))
        var_after  = float(np.var(after_win.dropna(), ddof=1))
        lev_stat = var_before / var_after if var_after > 0 else float("nan")
    else:
        lev_stat = np.nan
    # Chow-style combined F (sum-of-squares difference / pooled RSS)
    # Simplified: use the Welch t F-stat = t^2
    F = t_stat ** 2
    return {"t_stat": float(t_stat), "p_val": float(p_val),
            "levene_ratio": float(lev_stat), "n_before": int(n1),
            "n_after": int(len(after_win)), "F_equiv_t_sq": float(F)}, n1, n2


def score_h6(y10_series, dxy_series, tlt_series):
    """H6: Chow test on DXY/TLT and ^TNX at BNP-Paribas 2007-08-09.
    Also placebo at 2006-08-09 and 2008-08-09.
    H6 survives if the BNP F_equiv_t_sq (or |t|) on at least one series is
    STRICTLY larger than both placebos."""
    breakpoints = {
        "BNP":   "2007-08-09",
        "plA":   "2006-08-09",
        "plB":   "2008-08-09",
    }
    out = {}
    for name, series in [("y10", y10_series), ("dxy", dxy_series), ("tlt", tlt_series)]:
        if series is None or series.empty:
            out[name] = None
            continue
        rec = {}
        for bp_label, bp_date in breakpoints.items():
            rslt, _, _ = chow_test(series, bp_date)
            rec[bp_label] = rslt
        out[name] = rec
    # H6 survival: at least one of y10/dxy/tlt has BNP |t| > both placebos
    survival_votes = 0
    votes_detail = []
    for name in ("y10", "dxy", "tlt"):
        rec = out.get(name)
        if rec is None or rec["BNP"] is None:
            votes_detail.append(f"{name}: NO_DATA")
            continue
        bnp_t  = abs(rec["BNP"]["t_stat"])
        pla_t  = abs(rec["plA"]["t_stat"]) if rec["plA"] else 0
        plb_t  = abs(rec["plB"]["t_stat"]) if rec["plB"] else 0
        vote = (bnp_t > pla_t) and (bnp_t > plb_t)
        if vote:
            survival_votes += 1
        votes_detail.append(
            f"{name}: BNP |t|={bnp_t:.3f} placeboA |t|={pla_t:.3f} placeboB |t|={plb_t:.3f} -> {'PASS' if vote else 'fail'}"
        )
    # Per blocker §4.3 / §5 row H6: survives if at least one of {y10, dxy, tlt}
    # has BNP F strictly larger than both placebos.
    passed = survival_votes >= 1
    return passed, survival_votes, votes_detail, out


def main():
    # Load Yahoo yield series
    y10  = load_yahoo_yield("y10")
    y5   = load_yahoo_yield("y5")
    y13w = load_yahoo_yield("y13w")
    y30  = load_yahoo_yield("y30")
    vix  = load_yahoo_yield("vix")
    print("Exploration inputs (Yahoo-sourced, mutable):")
    for name, df in [("y10 (^TNX)", y10), ("y5 (^FVX)", y5),
                     ("y13w (^IRX)", y13w), ("y30 (^TYX)", y30),
                     ("vix (^VIX)", vix)]:
        if df is None:
            print(f"  [MISSING] {name}")
        else:
            print(f"  [OK] {name}: {len(df)} rows, {df.index.min().date()}..{df.index.max().date()}")

    dxy = load_existing_raw("dxy")
    tlt = load_existing_raw("tlt")
    btc = load_btc()
    print()
    print("Framework inputs (immutable, manifest-tracked):")
    for name, df in [("dxy", dxy), ("tlt", tlt), ("btc", btc)]:
        if df is None:
            print(f"  [MISSING] {name}")
        else:
            print(f"  [OK] {name}: {len(df)} rows, {df.index.min().date()}..{df.index.max().date()}")

    # ------------------------------------------------------------------
    # Build derived curve-shape series -- using two close proxies for §4.1:
    #  - curve_slope_10_5  = y10 - y5    (closest Yahoo-native substitute for 2y/10y)
    #  - curve_slope_10_3m = y10 - y13w  (standard inversion gauge, more traditional)
    # We commit to USING curve_slope_10_5 as the primary §4 feature
    # (楽 the cross-check by curve_slope_10_3m is recorded alongside).
    # ------------------------------------------------------------------
    if y10 is None or y5 is None:
        print("\nCannot proceed: missing y10 or y5.")
        return
    derived = pd.concat([y10, y5, y13w.rename(columns={"y13w": "y13w"})], axis=1).sort_index()
    derived["curve_slope_10_5"]  = derived["y10"] - derived["y5"]
    derived["curve_slope_10_3m"] = derived["y10"] - derived["y13w"]
    # 180-day rolling delta on the 10y-5y slope
    derived["slope_180d_delta"] = derived["curve_slope_10_5"].diff(pd.Timedelta(days=180).days)
    derived["slope_10_5_z_180d"] = (
        (derived["curve_slope_10_5"] - derived["curve_slope_10_5"].rolling(180, min_periods=90).mean())
        / derived["curve_slope_10_5"].rolling(180, min_periods=90).std()
    )
    # Apply pre-committed classifier
    derived["curve_shape_state"] = derived.apply(
        classify_curve, axis=1,
        slope_col="curve_slope_10_5", delta_col="slope_180d_delta"
    )
    # Cross-tab: distribution of states
    state_counts = derived["curve_shape_state"].value_counts()
    state_counts_no_unc = state_counts.drop("unclassified", errors="ignore")
    print()
    print("Curve-shape state distribution (10y-5y slope):")
    for st in ["inverted_flat", "bear_steep", "bull_steep", "normal", "unclassified"]:
        print(f"  {st:15s}: {state_counts.get(st, 0)}")
    print(f"  total non-unclassified: {state_counts_no_unc.sum()}")

    # ------------------------------------------------------------------
    # H1: score pre-committed extrema
    # ------------------------------------------------------------------
    print()
    print("=" * 64)
    print("H1 — Curve-shape transition at BTC extrema (§4.2 prediction table)")
    print("=" * 64)
    state_series = derived["curve_shape_state"]
    passed, score, denom, results = score_h1(state_series)
    print(f"Pre-committed threshold: H1 survives if score >= 5 of {denom}")
    print(f"{'Label':10s} {'Date':12s} {'EU expected':15s} {'Observed in ±120d':30s} match")
    for label, date_str, expected, observed, match in results:
        print(f"{label:10s} {date_str:12s} {expected:15s} {str(observed):30s} {match}")
    print(f"\nH1 verdict: {'PASS' if passed else 'REJECTED'} score={score}/{denom}")

    # ------------------------------------------------------------------
    # H6: Chow-style structural break at 2007-08-09 (BNP Paribas)
    # ------------------------------------------------------------------
    print()
    print("=" * 64)
    print("H6 — 2007-08-09 BNP-Paribas structural break detectable from rates?")
    print("=" * 64)
    if y10 is None:
        y10_for_h6 = None
    else:
        y10_for_h6 = y10["y10"]
    if dxy is None:
        dxy_for_h6 = None
    else:
        dxy_for_h6 = dxy["dxy"]
    if tlt is None:
        tlt_for_h6 = None
    else:
        tlt_for_h6 = tlt["tlt"]
    h6_passed, h6_votes, h6_detail, h6_full = score_h6(y10_for_h6, dxy_for_h6, tlt_for_h6)
    for line in h6_detail:
        print(line)
    print(f"H6 survival: {h6_votes}/3 series show BNP |t| > both placebos")
    print(f"H6 verdict: {'PASS' if h6_passed else 'REJECTED'} "
          f"(per §5 row H6: pass if >=1 of {{y10, dxy, tlt}} passes the placebo test)")

    # Print Chow specifics for y10 if available
    if h6_full.get("y10"):
        for bp_label in ("BNP", "plA", "plB"):
            rec = h6_full["y10"].get(bp_label)
            if rec:
                print(f"  y10 {bp_label}: t={rec['t_stat']:.3f} p={rec['p_val']:.3e} "
                      f"n={rec['n_before']}/{rec['n_after']}")

    # ------------------------------------------------------------------
    # H2, H3, H4, H5 — remain UNVERIFIED (cannot be computed)
    # ------------------------------------------------------------------
    print()
    print("=" * 64)
    print("H2, H3, H4, H5 — UNVERIFIED (cannot run this session)")
    print("=" * 64)
    print("H2 (TIPS break-even gap):    UNVERIFIED — no FRED T5YIE/T5YIFR fetched; "
          "Yahoo TIP ETF price alone cannot decompose break-even into nominal-real.")
    print("H3 (swap-spread proxy):      UNVERIFIED — BAMLC1A0C13Y not fetched; "
          "^VIX orthogonal to dealer balance-sheet; §3.4 caveat applies.")
    print("H4 (joint-state agreement):  UNVERIFIED — requires H1+H2+H3 to all produce labels.")
    print("H5 (snapshot EU label):      UNVERIFIED — requires H1..H3.")

    # ------------------------------------------------------------------
    # Write derived artifact (now with ACTUAL derived rows, not skeleton)
    # ------------------------------------------------------------------
    out = derived.copy()
    # attach BTC close for reference
    if btc is not None:
        out = out.join(btc.rename(columns={"btc": "btc_close"}), how="left")
    if dxy is not None:
        out = out.join(dxy, how="left")
    if tlt is not None:
        out = out.join(tlt, how="left")
    out = out.reset_index().rename(columns={"index": "date"})
    out["data_source_flag"] = "FRED-UNAVAILABLE, YAHOO-SUBSTITUTED; refer to blocker I-21 §3.4 honest-limit rule"
    out.to_csv(OUT_PATH, index=False)
    print()
    print(f"Wrote derived exploration artifact: {OUT_PATH.relative_to(ROOT)}  ({len(out)} rows, "
          f"{out['date'].min().date()}..{out['date'].max().date()})")

    # ------------------------------------------------------------------
    # Final aggregation promo decision (per blocker §7)
    # ------------------------------------------------------------------
    print()
    print("=" * 64)
    print("FINAL VERDICTS (this session)")
    print("=" * 64)
    survivors = []
    if passed:  survivors.append("H1")
    if h6_passed: survivors.append("H6")
    print(f"H1: {'PASS' if passed else 'REJECTED'}  score={score}/{denom}")
    print(f"H2: UNVERIFIED  (FRED T5YIE/T5YIFR not fetched)")
    print(f"H3: UNVERIFIED  (BAMLC1A0C13Y not fetched; §3.4 caveat)")
    print(f"H4: UNVERIFIED  (requires H1+H2+H3)")
    print(f"H5: UNVERIFIED  (requires H1..H3)")
    print(f"H6: {'PASS' if h6_passed else 'REJECTED'}  votes={h6_votes}/3")
    print()
    promo_threshold = 3  # blocker §7 says >=3 of H1..H4 surviving
    print(f"Survivors of H1..H4: {survivors}")
    print(f"Promotion rule (blocker §7: >=3 of H1..H4 surviving): NOT TRIGGERED")
    print(f"  -> I-21 proper NOT opened this session. Recommend re-run when FRED access lands.")


if __name__ == "__main__":
    main()

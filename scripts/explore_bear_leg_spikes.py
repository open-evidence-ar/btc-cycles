#!/usr/bin/env python3
"""Phase A exploration, perspective 2: the bear leg's dominant volume spike.

Perspective 1 (explore_volume_spikes.py) asked "is there ANY spike near the
bottom" and found no stable relationship.  The user's follow-up reframes it
the way the model's windows of attention actually work:

  In the down move (cycle top -> final bottom), is there a SINGLE CLEARLY
  DOMINANT volume spike?  And if so, does the final bottom land at a stable
  distance from it -- two weeks, one month, +- some percent of the leg?

So instead of nearest-spike-to-bottom, this script finds the bear leg's
dominant spike first, then measures where the bottom sits relative to it:

  lag          bottom_date - spike_date in days (positive = spike BEFORE
               the bottom: the flush prints first, the low follows later)
  lag_pct      same lag as % of the top->bottom leg length
  dominance    top1/top2: the leg's best day vs its best day outside a +-3d
               neighbourhood of the winner -- is the spike "clearly one"?
  magnitude    spike-day volume / trailing 90d baseline median (z and climax
               detectors)

Dominant spike is picked three ways (conclusion must survive the choice):
  dmax    highest raw volume day in the leg
  dz      highest raw-volume z day in the leg (baseline-aware)
  dclim   highest climax (volume x |return|) day in the leg

Legs: cycle top -> bottom(+60d prolong; open provisional lows extend to the
last data date because the leg is still running and the low can only fall).
Coverage and source-seam rules are inherited from perspective 1; a leg is
excluded if a >2x source transition sits inside it or within +-30d of its
bottom (fabricated-spike risk).

Chance baseline: 10,000 uniform random days inside each leg; the fraction
whose distance to the bottom is within +/-14/30d is what randomness gives --
the observed "bottom within +-k of the dominant spike" rate has to beat it.

Read-only; prints a report.  The verdict memo lives in docs/volume_spikes.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore_volume_spikes import (  # noqa: E402
    ALT_METRICS, ASSETS, ASSET_FILES, BTC_METRICS, RAW, ROOT,
    SEAM_FACTOR_EXCLUDE, add_detectors, load_series,
)

PROLONG_CONFIRMED = 60      # days past a confirmed bottom the leg may run
PROVISIONAL_TO_END = True   # open legs run to the last data date
NEIGHBOURHOOD_DAYS = 3      # dominance suppression window around the winner
WINDOWS = (14, 30, 60)      # "how far is the bottom from the spike", days
N_PERM = 10_000
SEED = 42
MIN_LEG_DAYS = 30           # a leg shorter than this is not analysable
HISTORY_BEFORE_LEG = 90     # volume history required before the leg starts

DETECTORS = ("dmax", "dz", "dclim")


def load_pairs(series: dict[str, pd.DataFrame]):
    """(top, bottom) pairs from the canonical metrics CSVs, no re-detection."""
    pairs = []
    btc = pd.read_csv(BTC_METRICS, keep_default_na=False)
    for _, r in btc.iterrows():
        top = pd.to_datetime(r["final_top_date"]) if r["final_top_date"] else None
        bot_status = r["bottom_status"]
        bdate = (pd.to_datetime(r["next_bear_bottom_date"])
                 if bot_status == "confirmed" and r["next_bear_bottom_date"]
                 else pd.to_datetime(r["b4_low_to_date"])
                 if r["b4_low_to_date"] else None)
        if top is None or pd.isna(top) or bdate is None or pd.isna(bdate):
            continue
        pairs.append(("btc", r["cycle_id"],
                      "confirmed" if bot_status == "confirmed" else "observed_ruleT",
                      top, bdate, bot_status))
    alt = pd.read_csv(ALT_METRICS, keep_default_na=False)
    for _, r in alt.iterrows():
        if r["asset"] not in ASSETS:
            continue
        s = series[r["asset"]]
        top = (pd.to_datetime(r["asset_local_top_date"])
               if r["asset_local_top_date"] else None)
        status = r["bottom_status"]
        bdate = None
        if status == "confirmed" and r["asset_next_bear_bottom_date"]:
            bdate = pd.to_datetime(r["asset_next_bear_bottom_date"])
        elif status == "provisional_low_to_date" and r["b4_low_to_date"]:
            bdate = pd.to_datetime(r["b4_low_to_date"])
        if top is None or pd.isna(top) or bdate is None or pd.isna(bdate) or not (top < bdate):
            continue
        pairs.append((r["asset"], r["cycle_id"],
                      "confirmed" if status == "confirmed" else "observed",
                      top, bdate, status))
    return pairs


def leg_bounds(s: pd.DataFrame, top: pd.Timestamp, bottom: pd.Timestamp,
               status: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    last = s["date"].iloc[-1]
    end = last if (PROVISIONAL_TO_END and status != "confirmed") \
        else min(bottom + pd.Timedelta(days=PROLONG_CONFIRMED), last)
    return (top, end)


def transitions_for(asset: str):
    _, t = load_series(asset)
    return t


def leg_has_bad_seam(transitions, top, bottom, leg_end) -> str | None:
    for t, factor in transitions:
        inside = top <= t <= leg_end
        near_bottom = abs((t - bottom).days) <= 30
        if (inside or near_bottom) and factor > SEAM_FACTOR_EXCLUDE:
            return f"source transition {t.date()} x{factor:,.0f}"
    return None


def dominant_spike(s: pd.DataFrame, lo: int, hi: int, detector: str) -> dict | None:
    """Best day of the leg under one detector + its dominance ratio."""
    seg = s.iloc[lo:hi + 1]
    if len(seg) < MIN_LEG_DAYS:
        return None
    if detector == "dmax":
        metric = seg["volume"].to_numpy(dtype=float)
    elif detector == "dz":
        metric = seg["z_raw"].to_numpy(dtype=float)
    else:
        metric = seg["climax_z"].to_numpy(dtype=float)
    if np.all(~np.isfinite(metric)):
        return None
    i_local = int(np.nanargmax(metric))
    dates = seg["date"].to_numpy()
    t1 = np.datetime64(dates[i_local])
    # best day OUTSIDE +-NEIGHBOURHOOD_DAYS of the winner = runner-up
    outside = np.abs((dates - t1).astype("timedelta64[D]").astype(int)) > NEIGHBOURHOOD_DAYS
    m2 = float(np.nanmax(metric[outside])) if outside.any() else np.nan
    rel_pos = int(np.flatnonzero(s.index == seg.index[i_local])[0])
    base = s["baseline_med"].iloc[rel_pos]
    return {
        "date": pd.Timestamp(dates[i_local]),
        "metric": float(metric[i_local]),
        "dominance": (metric[i_local] / m2) if np.isfinite(m2) and m2 > 0 else np.inf,
        "magnitude": (float(s["volume"].iloc[rel_pos]) / float(base))
        if detector != "dmax" and pd.notna(base) and base > 0 else np.nan,
    }


def main() -> int:
    np.random.seed(SEED)
    loaded = {a: load_series(a) for a in ASSETS}
    series = {a: add_detectors(s) for a, (s, _) in loaded.items()}
    seams = {a: t for a, (_, t) in loaded.items()}
    pairs = load_pairs(series)

    print("=" * 78)
    print("BEAR-LEG DOMINANT SPIKE EXPLORATION (perspective 2 -- read-only)")
    print("=" * 78)

    legs = []
    excluded = []
    for asset, cyc, top_status, top, bottom, bot_status in pairs:
        s = series[asset]
        first = s["date"].iloc[0]
        if not (first <= top <= s["date"].iloc[-1]):
            excluded.append(f"{asset} {cyc}: top outside volume series")
            continue
        if (top - first).days < HISTORY_BEFORE_LEG:
            excluded.append(f"{asset} {cyc}: <90d volume history before leg")
            continue
        lb = leg_bounds(s, top, bottom, bot_status)
        seam = leg_has_bad_seam(seams[asset], top, bottom, lb[1])
        if seam:
            excluded.append(f"{asset} {cyc}: {seam}")
            continue
        legs.append((asset, cyc, top_status, top, bottom, bot_status, lb[0], lb[1], s))
    if excluded:
        print("\n-- excluded legs ------------------------------------------------")
        for x in excluded:
            print(f"    {x}")

    print("\n-- per-leg dominant spike, detector dmax (highest raw volume) ----")
    hdr = (f"  {'asset':5s} {'cyc':4s} {'top':10s} {'bottom':10s} {'status':24s} "
           f"{'spike':10s} {'lag_d':>6s} {'lag_%':>6s} {'domin':>6s}")
    print(hdr)
    rows_by_detector: dict[str, list[dict]] = {d: [] for d in DETECTORS}
    for (asset, cyc, top_status, top, bottom, bot_status,
         leg_start, leg_end, s) in legs:
        lo = int(np.searchsorted(s["date"].values, np.datetime64(leg_start)))
        hi = int(np.searchsorted(s["date"].values, np.datetime64(leg_end),
                                 side="right")) - 1
        leg_len = max((bottom - top).days, 1)
        for d in DETECTORS:
            sp = dominant_spike(s, lo, hi, d)
            if sp is None:
                continue
            lag = (bottom - sp["date"]).days
            rows_by_detector[d].append({
                "asset": asset, "cyc": cyc, "top_status": top_status,
                "bot_status": bot_status, "leg_len": leg_len, "lag": lag,
                "lag_pct": lag / leg_len * 100, "dominance": sp["dominance"],
                "magnitude": sp["magnitude"], "date": sp["date"],
            })
        sp = dominant_spike(s, lo, hi, "dmax")
        lag = (bottom - sp["date"]).days
        print(f"  {asset:5s} {cyc:4s} {top.date().isoformat():10s} "
              f"{bottom.date().isoformat():10s} {bot_status:24s} "
              f"{sp['date'].date().isoformat():10s} {lag:+6d} "
              f"{lag / leg_len * 100:6.0f} {sp['dominance']:6.2f}")

    for det, title in (("dz", "baseline-aware z"), ("dclim", "climax vol x |ret|")):
        print(f"\n-- per-leg dominant spike, detector {det} ({title}) ---------")
        print(f"  {'asset':5s} {'cyc':4s} {'status':24s} {'spike':10s} "
              f"{'lag_d':>6s} {'lag_%':>6s} {'domin':>6s} {'mag':>6s}")
        for r in rows_by_detector[det]:
            mag = (f"{r['magnitude']:.1f}x"
                   if np.isfinite(r["magnitude"]) else "   --")
            print(f"  {r['asset']:5s} {r['cyc']:4s} {r['bot_status']:24s} "
                  f"{r['date'].date().isoformat():10s} {r['lag']:+6d} "
                  f"{r['lag_pct']:6.0f} {r['dominance']:6.2f} {mag:>6s}")

    print("\n-- stability of spike->bottom distance --------------------------")
    print(f"  {'detector':8s} {'status':24s} {'n':>3s} {'lag med':>8s} "
          f"{'lag IQR':>11s} {'spread':>7s} {'b4spike%':>8s} "
          f"{'in14':>5s} {'in30':>5s} {'rnd14':>6s} {'rnd30':>6s}")
    rng = np.random.default_rng(SEED)
    for d in DETECTORS:
        for status in ("confirmed", "provisional_low_to_date"):
            rows = [r for r in rows_by_detector[d] if r["bot_status"] == status]
            if not rows:
                continue
            lags = [r["lag"] for r in rows]
            med = int(np.median(lags))
            iqr = (f"{int(np.percentile(lags, 25))}..{int(np.percentile(lags, 75))}"
                   if len(lags) >= 4 else "--")
            spread = max(lags) - min(lags)
            pre = sum(1 for L in lags if L > 0) / len(lags)
            rnd14, rnd30 = _random_rate(legs, status, rng)
            hits = {k: sum(1 for L in lags if abs(L) <= k) / len(lags)
                    for k in WINDOWS}
            print(f"  {d:8s} {status:24s} {len(rows):3d} {med:+8d} {iqr:>11s} "
                  f"{spread:7d} {pre:8.0%} {hits[14]:5.0%} {hits[30]:5.0%} "
                  f"{rnd14:6.0%} {rnd30:6.0%}")

    print("\n-- same view, per asset (detector dmax, all statuses) -----------")
    for asset in ASSETS:
        rows = [r for r in rows_by_detector["dmax"] if r["asset"] == asset]
        if not rows:
            continue
        lags = [r["lag"] for r in rows]
        print(f"  {asset:5s} n={len(rows)}  lags={', '.join(f'{L:+d}' for L in lags)}"
              f"  median={int(np.median(lags)):+d}  spread={max(lags) - min(lags)}d")

    print("\n-- permutation check (confirmed legs): hit rate vs chance -------")
    legs_by_key = {(a, c): leg for leg in legs
                   for (a, c) in [(leg[0], leg[1])]}
    prng = np.random.default_rng(SEED)
    for d in DETECTORS:
        rows = [r for r in rows_by_detector[d] if r["bot_status"] == "confirmed"]
        if not rows:
            continue
        parts = []
        for k in (30, 60):
            p, obs, n = perm_p_hits(legs_by_key, rows, k, prng)
            parts.append(f"{obs}/{n}@{k}d p={p:.3f}")
        print(f"  {d:8s} " + "  ".join(parts))

    print("\n-- verdict ------------------------------------------------------")
    for d in DETECTORS:
        conf = [r for r in rows_by_detector[d] if r["bot_status"] == "confirmed"]
        prov = [r for r in rows_by_detector[d] if r["bot_status"] == "provisional_low_to_date"]
        if conf:
            p30, obs30, _ = perm_p_hits(legs_by_key, conf, 30, prng)
            p60, obs60, _ = perm_p_hits(legs_by_key, conf, 60, prng)
            lags = [r["lag"] for r in conf]
            label = ("CONFIRMED" if p60 < 0.01 or p30 < 0.05 else
                     "WEAK" if p60 < 0.10 or p30 < 0.10 else "ABSENT")
            print(f"  {d:6s} confirmed bottoms: {label}  "
                  f"({obs30}/{len(conf)}@30d p={p30:.3f}, {obs60}/{len(conf)}@60d p={p60:.3f}, "
                  f"lag med {int(np.median(lags)):+d}d)")
        if prov:
            print(f"  {d:6s} open legs: not evaluable (final bottom unknown; "
                  f"low-to-date can only fall)")
    print("    note: the +-60d hit domain includes the +60d post-bottom tail the")
    print("    leg search allows, so the fair comparison is the permutation p,")
    print("    not the raw hit rate. Provisional legs are structurally untestable.")
    return 0


def _leg_rate(s: pd.DataFrame, leg_start: pd.Timestamp, leg_end: pd.Timestamp,
              bottom: pd.Timestamp, k: int, rng) -> float:
    """P(|bottom - random leg day| <= k) for one leg."""
    d = s["date"].values
    lo = int(np.searchsorted(d, np.datetime64(leg_start)))
    hi = int(np.searchsorted(d, np.datetime64(leg_end), side="right"))
    n = hi - lo
    if n <= 0:
        return 0.0
    r = rng.integers(0, n, N_PERM)
    days = d[lo:hi][r]
    lag = (np.datetime64(bottom) - days).astype("timedelta64[D]").astype(int)
    return float((np.abs(lag) <= k).mean())


def perm_p_hits(legs_by_key: dict, rows: list[dict], k: int,
                rng) -> tuple[float, int, int]:
    """P(random-day hit count >= observed) for 'bottom within +/-k of spike'."""
    obs = sum(1 for r in rows if abs(r["lag"]) <= k)
    probs = []
    for r in rows:
        leg = legs_by_key[(r["asset"], r["cyc"])]
        probs.append(_leg_rate(leg[8], leg[6], leg[7], leg[4], k, rng))
    sims = np.zeros(N_PERM)
    for e in probs:
        sims += rng.random(N_PERM) < e
    return float((sims >= obs).mean()), obs, len(rows)


def _random_rate(legs, status: str, rng) -> tuple[float, float]:
    """Average over qualifying legs of P(|bottom - random leg day| <= k)."""
    rng = np.random.default_rng(SEED)
    e14 = e30 = n_legs = 0.0
    for (asset, cyc, _ts, top, bottom, bot_status, leg_start, leg_end, s) in legs:
        if status != "all" and bot_status != status:
            continue
        d = s["date"].values
        lo = int(np.searchsorted(d, np.datetime64(leg_start)))
        hi = int(np.searchsorted(d, np.datetime64(leg_end), side="right"))
        n = hi - lo
        if n <= 0:
            continue
        r = rng.integers(0, n, N_PERM)
        days = d[lo:hi][r]
        lag = (np.datetime64(bottom) - days).astype("timedelta64[D]").astype(int)
        e14 += float((np.abs(lag) <= 14).mean())
        e30 += float((np.abs(lag) <= 30).mean())
        n_legs += 1
    if n_legs == 0:
        return 0.0, 0.0
    return e14 / n_legs, e30 / n_legs


if __name__ == "__main__":
    sys.exit(main())

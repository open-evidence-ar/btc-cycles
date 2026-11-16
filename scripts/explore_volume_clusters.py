#!/usr/bin/env python3
"""Phase A exploration, perspective 3: the flush CLUSTER rule, stated plainly.

User's proposed rule (2026-11-15): "From the top to the bottom, is there a
stable 3+ days of volume concentration, and does the bottom occur at a stable
X days from the event with a +- range in time?"

Operational definition tested here (and varied in a sensitivity grid):

  qualifying day   daily volume z >= z_thr (raw volume, trailing 90d
                   baseline excluding the day itself)
  cluster          >= min_days qualifying days with gaps <= max_gap days
  event end        last qualifying day of the cluster
  leg              cycle top -> bottom (+60d tail; open legs run to the last
                   data date)

The operative cluster for the timing rule is the LAST cluster in the leg --
that is what a real-time monitor would act on (you cannot know a later cluster
will not come), and on closed legs it is usually the capitulation flush.  For
transparency each leg also reports where the leg's PEAK cluster sits, so a
top-era cluster outranking the end cluster is visible, not hidden.

Measured per closed leg: cluster presence near the bottom, lag from event END
to the bottom (positive = bottom AFTER the event), lag as % of leg length.
Stability = lag median/IQR/spread across legs + permutation p against uniform
random days inside the same leg domain (the +60d tail makes raw hit rates
partly mechanical; only the p is citable).

Read-only.  Verdict memo: docs/volume_spikes.md.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore_bear_leg_spikes import (  # noqa: E402
    HISTORY_BEFORE_LEG, MIN_LEG_DAYS, SEED, _leg_rate, leg_bounds,
    leg_has_bad_seam, load_pairs,
)
from explore_volume_spikes import (  # noqa: E402
    ASSETS, add_detectors, load_series,
)

N_PERM = 10_000

#: primary definition
Z_THR = 3.0
MIN_DAYS = 3
MAX_GAP = 2

#: sensitivity grid
GRID_Z = (2.0, 3.0, 4.0)
GRID_MIN_DAYS = (3, 4)
GRID_GAP = (1, 2)


def find_clusters(s: pd.DataFrame, lo: int, hi: int, z_thr: float,
                  min_days: int, max_gap: int) -> list[dict]:
    d = s["date"].values[lo:hi + 1]
    z = s["z_raw"].values[lo:hi + 1]
    q = np.flatnonzero(np.isfinite(z) & (z >= z_thr))
    if len(q) == 0:
        return []
    groups: list[list[int]] = [[int(q[0])]]
    for i in q[1:]:
        gap = (np.datetime64(d[i]) - np.datetime64(d[groups[-1][-1]])
               ).astype("timedelta64[D]").astype(int)
        if gap <= max_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [{"start": pd.Timestamp(d[g[0]]), "end": pd.Timestamp(d[g[-1]]),
             "days": len(g), "peak": float(np.nanmax(z[g])),
             "sum": float(np.nansum(z[g]))}
            for g in groups if len(g) >= min_days]


def legs_build(series):
    legs, excluded = [], []
    for asset, cyc, top_status, top, bottom, bot_status in load_pairs(series):
        s = series[asset]
        first = s["date"].iloc[0]
        if not (first <= top <= s["date"].iloc[-1]):
            excluded.append(f"{asset} {cyc}: top outside volume series")
            continue
        if (top - first).days < HISTORY_BEFORE_LEG:
            excluded.append(f"{asset} {cyc}: <90d history before leg")
            continue
        lo_date, hi_date = leg_bounds(s, top, bottom, bot_status)
        _, trans = load_series(asset)
        seam = leg_has_bad_seam(trans, top, bottom, hi_date)
        if seam:
            excluded.append(f"{asset} {cyc}: {seam}")
            continue
        legs.append({"asset": asset, "cyc": cyc, "top": top, "bottom": bottom,
                     "status": bot_status, "start": lo_date, "end": hi_date,
                     "series": s})
    return legs, excluded


def leg_slices(leg):
    s = leg["series"]
    lo = int(np.searchsorted(s["date"].values, np.datetime64(leg["start"])))
    hi = int(np.searchsorted(s["date"].values, np.datetime64(leg["end"]),
                             side="right")) - 1
    return lo, hi


def last_and_peak_clusters(leg, z_thr, min_days, max_gap):
    lo, hi = leg_slices(leg)
    cl = find_clusters(leg["series"], lo, hi, z_thr, min_days, max_gap)
    if not cl:
        return None, None
    last = max(cl, key=lambda c: c["end"])
    peak = max(cl, key=lambda c: (c["peak"], c["sum"]))
    return last, peak


def stats_for(legs, z_thr, min_days, max_gap):
    """Timing stats over closed legs under one cluster definition."""
    rows = []
    for leg in legs:
        if leg["status"] != "confirmed":
            continue
        last, peak = last_and_peak_clusters(leg, z_thr, min_days, max_gap)
        if last is None:
            continue
        lag_end = (leg["bottom"] - last["end"]).days
        rows.append({"asset": leg["asset"], "cyc": leg["cyc"],
                     "lag_end": lag_end,
                     "lag_pct": lag_end / max((leg["bottom"] - leg["top"]).days, 1) * 100,
                     "days": last["days"], "peak": last["peak"],
                     "peak_is_last": peak is not None
                     and peak["end"] == last["end"]})
    return rows


def perm_p(legs_closed, rows, k):
    rng = np.random.default_rng(SEED)
    obs = sum(1 for r in rows if abs(r["lag_end"]) <= k)
    if not rows:
        return float("nan"), 0, 0
    sims = np.zeros(N_PERM)
    for r in rows:
        leg = next(L for L in legs_closed
                   if L["asset"] == r["asset"] and L["cyc"] == r["cyc"])
        e = _leg_rate(leg["series"], leg["start"], leg["end"], leg["bottom"],
                      k, rng)
        sims += rng.random(N_PERM) < e
    return float((sims >= obs).mean()), obs, len(rows)


def main() -> int:
    loaded = {a: load_series(a) for a in ASSETS}
    series = {a: add_detectors(s) for a, (s, _) in loaded.items()}
    legs, excluded = legs_build(series)
    closed = [L for L in legs if L["status"] == "confirmed"]
    open_ = [L for L in legs if L["status"] != "confirmed"]

    print("=" * 78)
    print("FLUSH-CLUSTER RULE EXPLORATION (perspective 3 -- read-only)")
    print(f"primary definition: z>={Z_THR:.0f}, >={MIN_DAYS} days, gaps<={MAX_GAP}d")
    print("=" * 78)
    if excluded:
        print("-- excluded legs ------------------------------------------------")
        for x in excluded:
            print(f"    {x}")

    print("\n-- per closed leg: last cluster vs peak cluster ------------------")
    print(f"  {'asset':5s} {'cyc':4s} {'cluster (start..end)':26s} {'d':>2s} "
          f"{'peak_z':>6s} {'lag_end':>8s} {'lag_%':>6s} {'peak@top?':>9s}")
    rows = stats_for(legs, Z_THR, MIN_DAYS, MAX_GAP)
    for r in rows:
        leg = next(L for L in closed
                   if L["asset"] == r["asset"] and L["cyc"] == r["cyc"])
        last, peak = last_and_peak_clusters(leg, Z_THR, MIN_DAYS, MAX_GAP)
        span = f"{last['start'].date().isoformat()}..{last['end'].date().isoformat()}"
        print(f"  {r['asset']:5s} {r['cyc']:4s} {span:26s} {last['days']:2d} "
              f"{last['peak']:6.1f} {r['lag_end']:+8d} {r['lag_pct']:6.0f} "
              f"{'YES' if not r['peak_is_last'] else 'no':>9s}")
    missing = [L for L in closed
               if not any(r["asset"] == L["asset"] and r["cyc"] == L["cyc"]
                          for r in rows)]
    for L in missing:
        print(f"  {L['asset']:5s} {L['cyc']:4s} -- no qualifying cluster in leg --")

    print("\n-- timing stability (closed legs, event END -> bottom) ----------")
    if rows:
        lags = [r["lag_end"] for r in rows]
        pos = sum(1 for L in lags if L > 0) / len(lags)
        p30, obs30, n = perm_p(closed, rows, 30)
        p60, obs60, _ = perm_p(closed, rows, 60)
        rng = np.random.default_rng(SEED)
        rnd30 = float(np.mean([_leg_rate(L["series"], L["start"], L["end"],
                                         L["bottom"], 30, rng) for L in closed]))
        iqr = (f"{int(np.percentile(lags, 25))}..{int(np.percentile(lags, 75))}"
               if len(lags) >= 4 else "--")
        near60 = sum(1 for L in lags if abs(L) <= 60) / len(lags)
        print(f"  legs with a cluster: {len(rows)}/{len(closed)}"
              f"   end within +-60d of bottom: {near60:.0%}")
        print(f"  lag_end: median {int(np.median(lags)):+d}d  IQR {iqr}  "
              f"spread {max(lags) - min(lags)}d  positive(=bottom after) {pos:.0%}")
        print(f"  hits: {obs30}/{n}@30d p={p30:.3f}   {obs60}/{n}@60d p={p60:.3f}"
              f"   (random-day rate @30d {rnd30:.0%})")
        lps = [r["lag_pct"] for r in rows]
        print(f"  lag as % of leg: median {np.median(lps):+.0f}%  "
              f"range {min(lps):+.0f}%..{max(lps):+.0f}%")

    print("\n-- open legs (presence only; final bottom unknown) --------------")
    for L in open_:
        last, _ = last_and_peak_clusters(L, Z_THR, MIN_DAYS, MAX_GAP)
        last2, _ = last_and_peak_clusters(L, 2.0, 3, 2)
        if last2 is None:
            print(f"  {L['asset']:5s} {L['cyc']:4s} no z>=2 cluster yet")
            continue
        lag2 = (L["bottom"] - last2["end"]).days
        note = (f"z>=3: none" if last is None
                else f"z>=3 cluster ended {last['end'].date().isoformat()} "
                     f"({(L['bottom'] - last['end']).days:+d}d)")
        print(f"  {L['asset']:5s} {L['cyc']:4s} last z>=2 cluster ended "
              f"{last2['end'].date().isoformat()} ({last2['days']}d, "
              f"peak z {last2['peak']:.1f}); low-to-date {lag2:+d}d later  [{note}]")

    print("\n-- sensitivity grid (closed legs): does the rule survive the "
          "definition? ---")
    print(f"  {'z':>3s} {'min_d':>5s} {'gap':>3s} {'legs':>5s} {'in60':>5s} "
          f"{'lag med':>8s} {'IQR':>11s} {'p@30':>6s} {'p@60':>6s}")
    for z_thr, min_d, gap in itertools.product(GRID_Z, GRID_MIN_DAYS, GRID_GAP):
        rs = stats_for(legs, z_thr, min_d, gap)
        if not rs:
            print(f"  {z_thr:3.0f} {min_d:5d} {gap:3d} {0:5d} {'--':>5s}")
            continue
        lgs = [r["lag_end"] for r in rs]
        p30, o30, n_ = perm_p(closed, rs, 30)
        p60, o60, _ = perm_p(closed, rs, 60)
        iqr = (f"{int(np.percentile(lgs, 25))}..{int(np.percentile(lgs, 75))}"
               if len(lgs) >= 4 else "--")
        print(f"  {z_thr:3.0f} {min_d:5d} {gap:3d} {len(rs):5d} "
              f"{sum(1 for L in lgs if abs(L) <= 60) / len(lgs):5.0%} "
              f"{int(np.median(lgs)):+8d} {iqr:>11s} {p30:6.3f} {p60:6.3f}")

    print("\n-- plain-English rule check (primary definition) -----------------")
    if rows:
        lags = [r["lag_end"] for r in rows]
        pos_lags = [L for L in lags if L > 0]
        if len(pos_lags) == len(lags) and max(lags) - min(lags) <= 60:
            w = (max(lags) - min(lags)) // 2
            print(f"  Rule holds: after a {MIN_DAYS}+ day z>={Z_THR:.0f} cluster ends,"
                  f" the final bottom came {min(lags)}..{max(lags)}d later")
            print(f"  in all {len(lags)} closed legs (median {int(np.median(lags))}d, "
                  f"window ~{int(np.median(lags))}+/-{w}d).")
        else:
            print(f"  Rule does NOT hold cleanly: lags {sorted(lags)} "
                  f"(median {int(np.median(lags)):+d}d); "
                  f"see p-values above for how much better than chance this is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

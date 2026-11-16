#!/usr/bin/env python3
"""Phase A reanalysis, perspective 5: does the volume pattern survive the
August-2026 mislabel?

Trigger (2026-11-15, user's TradingView chart): the leg's visually dominant
volume peaks (Feb, Jun 2026) dwarf the burst the cluster rule had picked
(Aug 2026).  Down-day conditioning then showed the Aug 19-21 cluster is
0/3 DOWN days -- rally volume, not capitulation.  This script re-scores the
whole pattern book under a scenario grid so the I-23 definition is chosen
from evidence, not from the first framing that worked.

Scenarios = detector x direction:

  detectors (what makes a DAY "high volume")
    z2        relative: volume z >= 2 vs trailing 90d baseline (std-based)
    x2        relative: volume >= 2x the trailing 90d mean (mean-multiple)
    abs_top   absolute: volume >= 98th pct of the asset's ALL-history days

  directions (what makes a DAY "sell-side")
    any       no return condition (the original definition)
    down      qualifying day must close red
    mixed     cluster-level: >= half of the cluster's days are red

  clusters: >= 3 qualifying days, gaps <= 2d (primary); the down direction
  also gets a 2-day variant because 3-day red clusters proved rare.

Legs: cycle top -> bottom (+60d tail; open legs run to the last data date).
Closed legs score presence, lag (bottom - last-cluster END), and two nulls:
  p_day  -- bottom within +-60d of a RANDOM day in the leg (mechanical floor)
  p_end  -- within +-60d of a RANDOM cluster end (fair null; degenerate to
            1.0 when every leg has exactly one cluster -- reported as such)
Open legs report the last cluster + its direction mix, lag to low-to-date.

Read-only.  Verdict memo: docs/volume_spikes.md (Result 5).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore_bear_leg_spikes import SEED, _leg_rate  # noqa: E402
from explore_volume_clusters import legs_build, leg_slices  # noqa: E402
from explore_volume_spikes import ASSETS, add_detectors, load_series  # noqa: E402

N_PERM = 10_000
K = 60          # +-window for the nulls, days
MIN_DAYS = 3
MAX_GAP = 2

ABS_PCT = 0.98  # "absolute spike" = top 2% of the asset's own history


def build_series():
    loaded = {a: load_series(a) for a in ASSETS}
    out = {}
    for a, (s, _) in loaded.items():
        s = add_detectors(s)
        v = s["volume"].astype(float)
        s = s.copy()
        s["x2"] = v >= 2.0 * v.rolling(90).mean().shift(1)
        s["abs_top"] = v >= v.quantile(ABS_PCT)
        out[a] = s
    return out


def clusters_in(leg, qual, min_days=MIN_DAYS):
    """Clusters of qualifying days inside the leg slice.

    qual: callable(slice_df) -> boolean Series.  Returns list of dicts with
    start, end, days, down (red-day count), total volume.
    """
    lo, hi = leg_slices(leg)
    s = leg["series"].iloc[lo:hi + 1].reset_index(drop=True)
    ret = s["close"].astype(float).pct_change()
    mask = qual(s).fillna(False)
    idx = list(s.index[mask])
    out = []
    for i in idx:
        if out and (s["date"].iloc[i] - out[-1]["end"]).days <= MAX_GAP:
            out[-1]["end"] = s["date"].iloc[i]
            out[-1]["days"] += 1
            out[-1]["down"] += int(ret.iloc[i] < 0)
            out[-1]["idx"].append(i)
        else:
            out.append({"start": s["date"].iloc[i], "end": s["date"].iloc[i],
                        "days": 1, "down": int(ret.iloc[i] < 0),
                        "idx": [i]})
    return [c for c in out if c["days"] >= min_days]


def direction_filter(cl, direction):
    if direction == "any":
        return cl
    if direction == "mixed":
        return [c for c in cl if c["down"] * 2 >= c["days"]]
    raise ValueError(direction)


def qual_for(det, direction):
    """Day-level qualifier for a detector x direction scenario.

    'down' filters at the DAY level (red close required); 'mixed' filters at
    the CLUSTER level afterwards (>= half the cluster's days red).
    """
    base = DETECTORS[det]
    if direction == "down":
        def q(s):
            ret = s["close"].astype(float).pct_change()
            return base(s).fillna(False) & (ret < 0)
        return q
    return base


def cluster_sets(leg, det, direction, min_days=MIN_DAYS):
    cl = clusters_in(leg, qual_for(det, direction), min_days)
    if direction == "mixed":
        cl = [c for c in cl if c["down"] * 2 >= c["days"]]
    return cl


DETECTORS = {
    "z2": lambda s: s["z_raw"].notna() & (s["z_raw"] >= 2.0),
    "x2": lambda s: s["x2"].fillna(False),
    "abs_top": lambda s: s["abs_top"].fillna(False),
}


def scenario_legs(legs, det, direction, min_days=MIN_DAYS):
    """{leg_key: last cluster} under one scenario; None where absent."""
    res = {}
    for L in legs:
        cl = cluster_sets(L, det, direction, min_days)
        res[(L["asset"], L["cyc"])] = (max(cl, key=lambda c: c["end"])
                                       if cl else None)
    return res


def closed_stats(legs_closed, res):
    rows = []
    for L in legs_closed:
        last = res[(L["asset"], L["cyc"])]
        if last is None:
            continue
        lag = (L["bottom"] - last["end"]).days
        rows.append({"key": (L["asset"], L["cyc"]), "lag": lag,
                     "leg": L, "cl": last})
    return rows


def p_day(legs_closed, rows, k=K):
    rng = np.random.default_rng(SEED)
    if not rows:
        return float("nan")
    obs = sum(1 for r in rows if abs(r["lag"]) <= k)
    sims = np.zeros(N_PERM)
    for r in rows:
        L = r["leg"]
        sims += rng.random(N_PERM) < _leg_rate(L["series"], L["start"],
                                               L["end"], L["bottom"], k, rng)
    return float((sims >= obs).mean())


def main() -> int:
    series = build_series()
    legs, excluded = legs_build(series)
    closed = [L for L in legs if L["status"] == "confirmed"]
    open_ = [L for L in legs if L["status"] != "confirmed"]

    print("=" * 78)
    print("VOLUME PATTERN REANALYSIS (perspective 5 -- read-only)")
    print(f"cluster: >={MIN_DAYS} days, gaps<={MAX_GAP}d; window +-{K}d")
    print("=" * 78)
    if excluded:
        print("excluded legs:")
        for x in excluded:
            print(f"    {x}")

    scenarios = [("z2", "any"), ("z2", "down"), ("z2", "mixed"),
                 ("x2", "any"), ("x2", "down"), ("x2", "mixed"),
                 ("abs_top", "any"), ("abs_top", "down"),
                 ("abs_top", "mixed")]

    print("\n-- closed-leg grid (last cluster -> bottom) ---------------------")
    print(f"  {'detector':8s} {'dir':6s} {'legs':>4s} {'in60':>5s} "
          f"{'lag med':>8s} {'env':>13s} {'p_day@60':>8s} {'p_end@60':>8s}")
    grid = {}
    for det, direction in scenarios:
        res = scenario_legs(legs, det, direction)
        rows = closed_stats(closed, res)
        grid[(det, direction)] = (res, rows)
        if not rows:
            print(f"  {det:8s} {direction:6s} {0:4d}")
            continue
        lags = [r["lag"] for r in rows]
        pd_ = p_day(closed, rows)
        # fair null over random cluster ends (recomputed inline)
        rng = np.random.default_rng(SEED)
        obs = sum(1 for r in rows if abs(r["lag"]) <= K)
        sims = np.zeros(N_PERM)
        n_clusters_total = 0
        for r in rows:
            cl_all = cluster_sets(r["leg"], det, direction)
            ends = [c["end"] for c in cl_all]
            n_clusters_total += len(ends)
            pick = rng.integers(0, len(ends), N_PERM)
            ends_s = pd.Series(pd.Timestamp(e) for e in ends)
            diff = (pd.Timestamp(r["leg"]["bottom"])
                    - ends_s.iloc[pick]).dt.days.to_numpy()
            sims += np.abs(diff) <= K
        pe = (float((sims >= obs).mean())
              if n_clusters_total > len(rows) else None)
        pe_s = f"{pe:8.3f}" if pe is not None else "  degen."
        env = (f"{min(lags):+d}..{max(lags):+d}" if len(lags) > 1
               else f"{lags[0]:+d}")
        print(f"  {det:8s} {direction:6s} {len(rows):4d} "
              f"{sum(1 for L in lags if abs(L) <= K) / len(lags):5.0%} "
              f"{int(np.median(lags)):+8d} {env:>13s} {pd_:8.3f} {pe_s}")

    print("\n-- which closed legs hold, per scenario (P=present) -------------")
    hdr = "  {:6s} {:8s} {}".format("det", "dir", "  ".join(
        f"{L['asset']}-{L['cyc']}" for L in closed))
    print(hdr)
    for det, direction in scenarios:
        res, _ = grid[(det, direction)]
        cells = []
        for L in closed:
            c = res[(L["asset"], L["cyc"])]
            if c is None:
                cells.append("  .  ")
            else:
                cells.append(f"{c['down']}/{c['days']}d")
        print(f"  {det:6s} {direction:8s} " + "  ".join(cells))

    print("\n-- 2-day red-cluster rescue attempt (z2/down, min_days=2) --------")
    for L in closed:
        cl = cluster_sets(L, "z2", "down", min_days=2)
        if not cl:
            print(f"  {L['asset']:5s} {L['cyc']:4s} none")
            continue
        last = max(cl, key=lambda c: c["end"])
        lag = (L["bottom"] - last["end"]).days
        print(f"  {L['asset']:5s} {L['cyc']:4s} {last['start'].date()}.."
              f"{last['end'].date()} {last['days']}d lag {lag:+d}d")

    print("\n-- open C4 legs: last cluster per scenario ----------------------")
    for det, direction in scenarios:
        res, _ = grid[(det, direction)]
        parts = []
        for L in open_:
            c = res[(L["asset"], L["cyc"])]
            if c is None:
                parts.append(f"{L['asset']}:none")
            else:
                lag = (L["bottom"] - c["end"]).days
                parts.append(f"{L['asset']}:{c['end'].date()} "
                             f"{c['down']}/{c['days']}dn {lag:+d}d")
        print(f"  {det:8s} {direction:6s} " + " | ".join(parts))

    print("\n-- absolute vs relative, the three 2026 bursts (btc C4) ---------")
    s = series["btc"]
    leg = s[s["date"] >= pd.Timestamp("2025-10-06")]
    for label, d in [("Feb", "2026-02-04"), ("June", "2026-06-05"),
                     ("Aug", "2026-08-19")]:
        dt = pd.Timestamp(d)
        w = s[(s["date"] >= dt - pd.Timedelta(days=90)) & (s["date"] < dt)]
        m = (leg["date"] >= dt) & (leg["date"] <= dt + pd.Timedelta(days=6))
        seg = leg[m]
        print(f"  {label:5s} base90 {float(w['volume'].mean()):8,.0f} "
              f"best-day {int(seg['volume'].max()):6d} "
              f"z {float(seg['z_raw'].max()):4.1f} "
              f"x2 {bool(seg['x2'].any())!s:5s} "
              f"abs_top {bool(seg['abs_top'].any())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

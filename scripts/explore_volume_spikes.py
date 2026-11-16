#!/usr/bin/env python3
"""Phase A exploration: do volume spikes cluster near cycle tops and bottoms?

Claim under test (user hypothesis, 2026-11-15): a volume spike occurs close to
cycle tops (and bottoms), and the proximity / magnitude / duration of that
spike is stable enough across cycles to serve as a timing confirmation signal.

This is an EXPLORATION, not an increment. It writes nothing into the pipeline:
it reads the canonical extrema already published in btc_cycle_metrics.csv and
alt_cycle_metrics.csv (no re-detection -- testing volume proximity against
price-defined tops keeps the analysis non-circular), builds volume series from
the same raw snapshots the price series uses, and measures:

  proximity   signed lag in days from spike peak to extremum
              (positive = spike BEFORE the extremum)
  magnitude   spike-day volume / trailing 90d baseline median
  duration    count of spike days within +/-30d of the extremum

Stability is assessed three ways because n is tiny (about 14 tops and 14
bottoms across six assets -- see the coverage table the script prints):

  hit rate    fraction of extrema with a spike within +/-7/14/30d
  chance      permutation baseline: random days inside the SAME cycle window,
              same detector, same window -- is the observed clustering better
              than luck?
  spread      cross-cycle spread of the lags (IQR), the same eyeball test the
              I-21 cycle_tie audit used

Three detector families so no conclusion can be an artefact of one definition:

  z-raw       volume z-score vs trailing 90-calendar-day baseline (excl. self),
              thresholds 2/3/4
  z-log       same z on log1p(volume) -- heavy-tailed volumes make raw z
              brittle; this is the more robust sibling
  z-climax    z on volume x |daily return| (climax/capitulation proxy)
  pct-cycle   day's volume in the top 1% / 2% of its own cycle window

Anchors and coverage rules:

  - C4 extrema are included and FLAGGED: tops 'observed_ruleT', bottoms
    'provisional_low_to_date' (a running minimum that can only fall).
  - riot/mara excluded (proxy sources, per AGENTS.md).
  - An extremum is testable only where the asset's own volume series covers it
    with >=90d of baseline history; WGMI's C1-C3 are MARA proxy extrema that
    predate WGMI's 2022 volume series and drop out on this rule automatically.

Outputs: console report only. A memo with the verdict goes to docs/ by hand
after the numbers are read -- this script asserts nothing.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
BTC_METRICS = ROOT / "data/processed/btc_cycle_metrics.csv"
ALT_METRICS = ROOT / "data/processed/alt_cycle_metrics.csv"

ASSETS = ["btc", "eth", "xrp", "sol", "mstr", "wgmi"]

# Later-listed pattern wins on a shared date (same rule as
# build_alt_cycle_metrics.load_asset: CDD fills history, Yahoo carries recency).
ASSET_FILES = {
    "btc": ["btc_bitstamp_*.csv"],
    "eth": ["eth_cdd_*.csv", "eth_yahoo_*.csv"],
    "xrp": ["xrp_cdd_*.csv", "xrp_yahoo_*.csv"],
    "sol": ["sol_cdd_*.csv", "sol_yahoo_*.csv"],
    "mstr": ["mstr_yahoo_*.csv"],
    "wgmi": ["wgmi_yahoo_*.csv"],
}

BASELINE_DAYS = "90D"       # trailing calendar window for baselines
MIN_BASELINE_OBS = 20       # min observations for a valid baseline
Z_THRESHOLDS = (2.0, 3.0, 4.0)
PCT_QUANTILES = (0.99, 0.98)  # top 1% / 2% of the cycle's own volume
WINDOWS = (7, 14, 30)       # hit-rate windows, days
CLUSTER_WINDOW = 30         # duration window, days
N_PERM = 10_000
SEED = 42

BOTTOM_PROLONG_DAYS = 60    # bottoms may print their flush at/after the low
SEAM_FACTOR_EXCLUDE = 2.0   # min source-transition scale step to exclude around


@dataclass
class Extremum:
    asset: str
    cycle: str
    kind: str                 # "top" | "bottom"
    status: str               # confirmed | observed_ruleT | provisional_low_to_date
    date: pd.Timestamp
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    series: pd.DataFrame = field(repr=False)  # the asset's full series


def load_series(asset: str) -> tuple[pd.DataFrame, list[tuple[pd.Timestamp, float]]]:
    """Merge every snapshot for asset into date/close/volume, later source wins.

    Same merge contract as build_alt_cycle_metrics.load_asset (stable sort is
    REQUIRED so 'later source wins' is deterministic), keeping volume.

    Also returns the source TRANSITIONS of the merged series: every date where
    the winning source changes, paired with the median-volume scale step across
    it (30d before vs 30d after).  CDD vs Yahoo magnitudes are NOT comparable
    (measured: ETH ratio drifts 100x over 8y -- CDD's late-era volume is a
    shrinking subset), so a large step at a transition means z-scores near it
    are contaminated and extrema within +/-30d must be excluded rather than
    trusted.
    """
    per_source: list[pd.DataFrame] = []
    for pat in ASSET_FILES[asset]:
        frames: list[pd.DataFrame] = []
        for f in sorted(RAW.glob(pat)):
            df = pd.read_csv(f)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            for col in ("close", "volume"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["date", "close", "volume"])
            frames.append(df[["date", "close", "volume"]])
        if frames:
            m = pd.concat(frames, ignore_index=True)
            m = m.sort_values("date", kind="stable").drop_duplicates(
                subset=["date"], keep="last"
            )
            per_source.append(m)
    if not per_source:
        raise FileNotFoundError(f"no raw files for {asset}")

    merged = pd.concat(per_source, ignore_index=True)
    merged = merged.sort_values("date", kind="stable").drop_duplicates(
        subset=["date"], keep="last"
    )
    merged = merged.sort_values("date").reset_index(drop=True)

    transitions: list[tuple[pd.Timestamp, float]] = []
    if len(per_source) > 1:
        # winner per date = highest-priority source providing it
        keys = pd.concat(
            [f.assign(_src=i) for i, f in enumerate(per_source)], ignore_index=True
        ).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
        keys = keys.sort_values("date").reset_index(drop=True)
        src = keys["_src"].to_numpy()
        change = np.flatnonzero(src[1:] != src[:-1]) + 1
        for i in change:
            t = keys["date"].iloc[i]
            pre = merged["volume"][(merged["date"] >= t - pd.Timedelta(days=30))
                                   & (merged["date"] < t)].median()
            post = merged["volume"][(merged["date"] >= t)
                                    & (merged["date"] < t + pd.Timedelta(days=30))].median()
            if pre and pre > 0 and pd.notna(post):
                transitions.append((t, float(post / pre)))
    return merged, transitions


def add_detectors(s: pd.DataFrame) -> pd.DataFrame:
    """Attach trailing-baseline detector columns to a series.

    Baselines are computed on the volume series shifted by one day so a day's
    own volume never enters its own baseline.
    """
    v = s["volume"].astype(float)
    ret = s["close"].astype(float).pct_change().clip(-0.5, 0.5).fillna(0.0)
    idx = pd.DatetimeIndex(s["date"].values)

    lag_v = pd.Series(v.shift(1).values, index=idx)
    mean_v = lag_v.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).mean()
    std_v = lag_v.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).std()
    med_v = lag_v.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).median()

    log_v = pd.Series(np.log1p(v.shift(1).values), index=idx)
    mean_l = log_v.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).mean()
    std_l = log_v.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).std()

    climax = pd.Series((v * ret.abs()).shift(1).values, index=idx)
    mean_c = climax.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).mean()
    std_c = climax.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE_OBS).std()

    out = s.copy()
    out["baseline_med"] = pd.Series(med_v.values, index=s.index)

    with np.errstate(invalid="ignore", divide="ignore"):
        z_raw = (v.values - mean_v.values) / std_v.values
        z_log = (np.log1p(v.values) - mean_l.values) / std_l.values
        z_clim = ((v * ret.abs()).values - mean_c.values) / std_c.values

    for thr in Z_THRESHOLDS:
        out[f"z{int(thr)}"] = np.where(std_v.values > 0, z_raw, np.nan) >= thr
        out[f"lz{int(thr)}"] = np.where(std_l.values > 0, z_log, np.nan) >= thr
        out[f"cl{int(thr)}"] = np.where(std_c.values > 0, z_clim, np.nan) >= thr
    # numeric values (used by the bear-leg perspective to locate the dominant
    # z/climax day, not just flags)
    out["z_raw"] = z_raw
    out["z_log"] = z_log
    out["climax_z"] = z_clim
    return out


def pct_cycle_flags(s: pd.DataFrame, e: Extremum, q: float) -> np.ndarray:
    """Top-q volume days INSIDE the extremum's cycle window (False outside).

    Bottom windows are prolonged past the low (capitulation can print at the
    low or in the days right after it); tops are capped at the next bottom.
    """
    flags = np.zeros(len(s), dtype=bool)
    lo = s.index[s["date"] >= e.window_start][0]
    hi_cap = e.window_end
    if e.kind == "bottom":
        hi_cap = min(e.window_end, e.date + pd.Timedelta(days=BOTTOM_PROLONG_DAYS))
    hi = s.index[s["date"] <= hi_cap][-1]
    win = s.iloc[lo : hi + 1]
    if len(win) < 10:
        return flags
    thr = win["volume"].quantile(q)
    flags[lo : hi + 1] = (win["volume"] >= thr).values
    return flags


def load_extrema(series: dict[str, pd.DataFrame]) -> list[Extremum]:
    """Canonical extrema from the two metrics CSVs; no re-detection.

    ``series`` must be the detector-enhanced frames from ``add_detectors``.
    """
    out: list[Extremum] = []

    btc = pd.read_csv(BTC_METRICS, keep_default_na=False)
    for _, r in btc.iterrows():
        s = series["btc"]
        top = pd.to_datetime(r["final_top_date"])
        if pd.notna(top):
            out.append(Extremum("btc", r["cycle_id"], "top",
                                "observed_ruleT" if r["bottom_status"] != "confirmed"
                                else "confirmed", top,
                                pd.to_datetime(r["pre_halving_bottom_date"]),
                                pd.to_datetime(r["next_bear_bottom_date"])
                                if r["bottom_status"] == "confirmed"
                                else s["date"].iloc[-1], s))
        bot_status = r["bottom_status"]
        if bot_status == "confirmed":
            bdate = pd.to_datetime(r["next_bear_bottom_date"])
        else:
            bdate = pd.to_datetime(r["b4_low_to_date"]) if r["b4_low_to_date"] else None
        if bdate is not None and pd.notna(bdate):
            out.append(Extremum("btc", "B" + r["cycle_id"][1:], "bottom",
                                bot_status, bdate,
                                pd.to_datetime(r["pre_halving_bottom_date"]),
                                pd.to_datetime(r["next_bear_bottom_date"])
                                if bot_status == "confirmed"
                                else s["date"].iloc[-1], s))

    alt = pd.read_csv(ALT_METRICS, keep_default_na=False)
    for _, r in alt.iterrows():
        a = r["asset"]
        if a not in ASSETS:
            continue
        s = series[a]
        top = pd.to_datetime(r["asset_local_top_date"]) if r["asset_local_top_date"] else None
        if top is not None and pd.notna(top):
            confirmed = r["bottom_status"] == "confirmed"
            out.append(Extremum(a, r["cycle_id"], "top",
                                "confirmed" if confirmed else "observed",
                                top,
                                pd.to_datetime(r["asset_pre_halving_bottom_date"]),
                                pd.to_datetime(r["asset_next_bear_bottom_date"])
                                if confirmed else s["date"].iloc[-1], s))
        status = r["bottom_status"]
        bdate = None
        if status == "confirmed" and r["asset_next_bear_bottom_date"]:
            bdate = pd.to_datetime(r["asset_next_bear_bottom_date"])
        elif status == "provisional_low_to_date" and r["b4_low_to_date"]:
            bdate = pd.to_datetime(r["b4_low_to_date"])
        if bdate is not None and pd.notna(bdate):
            out.append(Extremum(a, "B" + r["cycle_id"][1:], "bottom", status, bdate,
                                pd.to_datetime(r["asset_pre_halving_bottom_date"]),
                                pd.to_datetime(r["asset_next_bear_bottom_date"])
                                if status == "confirmed" else s["date"].iloc[-1], s))
    return out


def coverage_check(e: Extremum, detectors: list[str],
                   transitions: list[tuple[pd.Timestamp, float]]) -> str | None:
    """Return an exclusion reason, or None if testable."""
    s = e.series
    first, last = s["date"].iloc[0], s["date"].iloc[-1]
    if not (first <= e.date <= last):
        return f"outside volume series ({first.date()}..{last.date()})"
    hist = (e.date - first).days
    if hist < 90 and any(d.startswith(("z", "lz", "cl")) for d in detectors):
        return f"only {hist}d of volume history (90d baseline unavailable)"
    for t, factor in transitions:
        if abs((t - e.date).days) <= CLUSTER_WINDOW and factor > SEAM_FACTOR_EXCLUDE:
            return (f"source transition {t.date()} x{factor:.0f} within "
                    f"+/-{CLUSTER_WINDOW}d (fabricated-spike risk)")
    return None


def detector_flags(s: pd.DataFrame, e: Extremum, detector: str) -> np.ndarray:
    """Boolean spike flags for one extremum under one detector."""
    if detector.startswith("pct99"):
        return pct_cycle_flags(s, e, PCT_QUANTILES[0])
    if detector.startswith("pct98"):
        return pct_cycle_flags(s, e, PCT_QUANTILES[1])
    return s[detector].values.astype(bool)


def spikes_within(s: pd.DataFrame, flags: np.ndarray, day: pd.Timestamp,
                  k: int) -> np.ndarray:
    """Indices of spike days within +/-k CALENDAR days of day.

    Calendar days, not rows: MSTR/WGMI trade ~252d/yr while crypto prints 7d/wk,
    so row windows would silently widen for the equities and make the mixed
    sample unfair.
    """
    d = s["date"].values
    lo = np.datetime64(day - pd.Timedelta(days=k))
    hi = np.datetime64(day + pd.Timedelta(days=k))
    return np.flatnonzero(flags & (d >= lo) & (d <= hi))


def evaluate(e: Extremum, detector: str) -> dict:
    """Nearest-spike metrics for one extremum under one detector."""
    s = e.series
    flags = detector_flags(s, e, detector)
    res: dict = {f"hit{k}": bool(len(spikes_within(s, flags, e.date, k)))
                 for k in WINDOWS}
    for k in WINDOWS:  # tightest window that hit carries the metrics
        if not res[f"hit{k}"]:
            continue
        idxs = spikes_within(s, flags, e.date, k)
        nearest = idxs[np.argmin(np.abs(
            (s["date"].values[idxs] - np.datetime64(e.date)).astype("timedelta64[D]")
            .astype(int)))]
        base = s["baseline_med"].iloc[nearest]
        res["lag"] = int((e.date - pd.Timestamp(s["date"].iloc[nearest])).days)
        res["magnitude"] = (float(s["volume"].iloc[nearest]) / float(base)
                            if pd.notna(base) and base > 0 else np.nan)
        res["elev30"] = int(len(spikes_within(s, flags, e.date, CLUSTER_WINDOW)))
        break
    return res


def permutation_p(extrema: list[tuple[Extremum, dict]], detector: str,
                  k: int) -> tuple[float, int, int]:
    """P(random-day hit count >= observed) under the same windows.

    For each extremum, draw a uniform random day from its own cycle window and
    ask whether a spike day falls within +/-k CALENDAR days of it.  Repeats
    N_PERM times with a fixed seed (same draws for every detector, so
    detector-to-detector comparisons are paired).
    """
    rng = np.random.default_rng(SEED)
    obs_hits = sum(1 for _, r in extrema if r[f"hit{k}"])
    counts = np.zeros(N_PERM, dtype=int)
    for e, _ in extrema:
        s = e.series
        flags = detector_flags(s, e, detector)
        lo = int(np.searchsorted(s["date"].values, np.datetime64(e.window_start)))
        hi = int(np.searchsorted(s["date"].values, np.datetime64(e.window_end),
                                 side="right"))
        hi = min(hi, len(s))
        if hi <= lo:
            lo = max(0, lo - 1)
        wd = s["date"].values[lo:hi]
        pf = np.concatenate([[0], np.cumsum(flags[lo:hi])])
        r = rng.integers(0, len(wd), N_PERM)
        days = wd[r]
        a = np.searchsorted(wd, days - np.timedelta64(k, "D"), side="left")
        b = np.searchsorted(wd, days + np.timedelta64(k, "D"), side="right")
        counts += (pf[b] - pf[a]) > 0
    return float((counts >= obs_hits).mean()), obs_hits, len(extrema)


DETECTORS = ([f"z{int(t)}" for t in Z_THRESHOLDS]
             + [f"lz{int(t)}" for t in Z_THRESHOLDS]
             + [f"cl{int(t)}" for t in Z_THRESHOLDS]
             + ["pct99", "pct98"])
DETECTOR_LABEL = {
    "z2": "z-raw >=2", "z3": "z-raw >=3", "z4": "z-raw >=4",
    "lz2": "z-log >=2", "lz3": "z-log >=3", "lz4": "z-log >=4",
    "cl2": "climax >=2", "cl3": "climax >=3", "cl4": "climax >=4",
    "pct99": "top 1% of cycle", "pct98": "top 2% of cycle",
}


def main() -> int:
    np.random.seed(SEED)
    loaded = {a: load_series(a) for a in ASSETS}
    series = {a: add_detectors(s) for a, (s, _) in loaded.items()}
    transitions = {a: t for a, (_, t) in loaded.items()}
    extrema = load_extrema(series)

    print("=" * 78)
    print("VOLUME-SPIKE PROXIMITY EXPLORATION (Phase A -- read-only)")
    print("=" * 78)

    print("\n-- coverage -----------------------------------------------------")
    testable: list[tuple[Extremum, dict]] = []  # (extremum, per-detector results)
    excluded: list[str] = []
    for e in extrema:
        reason = coverage_check(e, DETECTORS, transitions[e.asset])
        if reason:
            excluded.append(f"{e.asset} {e.cycle} {e.kind} {e.date.date()}: {reason}")
            continue
        per = {d: evaluate(e, d) for d in DETECTORS}
        testable.append((e, per))
    for a in ASSETS:
        s = series[a]
        n = sum(1 for e, _ in testable if e.asset == a)
        seams = ", ".join(f"{t.date()} x{f:,.0f}" for t, f in transitions[a]) or "none"
        print(f"  {a:5s} volume {s['date'].iloc[0].date()}..{s['date'].iloc[-1].date()}"
              f"  ({len(s)} rows)  testable extrema: {n}")
        print(f"        source transitions: {seams}")
    if excluded:
        print("  excluded:")
        for x in excluded:
            print(f"    {x}")

    kinds = ("top", "bottom")
    primary = "z3"
    print("\n-- per-extremum hits under the primary detector"
          f" ({DETECTOR_LABEL[primary]}) ----------------")
    hdr = f"  {'asset':5s} {'cycle':4s} {'kind':6s} {'status':24s} {'date':10s} " \
          f"{'lag':>5s} {'mag':>7s} {'elev30':>6s}"
    print(hdr)
    for e, per in testable:
        r = per[primary]
        lag = f"{r['lag']:+d}" if r.get("hit30") else "  --"
        mag = f"{r['magnitude']:.1f}x" if r.get("hit30") and np.isfinite(r.get("magnitude", np.nan)) else "   --"
        elev = f"{r['elev30']}" if r.get("hit30") else "--"
        print(f"  {e.asset:5s} {e.cycle:4s} {e.kind:6s} {e.status:24s} "
              f"{e.date.date().isoformat():10s} {lag:>5s} {mag:>7s} {elev:>6s}")

    print("\n-- summary: hit rates / chance baseline / lag+magnitude stats ---")
    print(f"  {'detector':16s} {'kind':6s} {'n':>3s} {'h@7':>5s} {'h@14':>5s} "
          f"{'h@30':>5s} {'rnd@14':>6s} {'p@14':>6s} {'p@30':>6s} "
          f"{'lag med':>8s} {'lag IQR':>9s} {'mag med':>8s}")
    verdicts: dict[str, dict[str, str]] = {}
    for d in DETECTORS:
        for kind in kinds:
            rows = [(e, per[d]) for e, per in testable if e.kind == kind]
            if not rows:
                continue
            n = len(rows)
            hr = {k: sum(1 for _, r in rows if r[f"hit{k}"]) / n for k in WINDOWS}
            p14, obs14, _ = permutation_p(rows, d, 14)
            p30, obs30, _ = permutation_p(rows, d, 30)
            # random-day hit probability at k=14 for context
            rnd14 = 1.0 - (1.0 - _day_rate(rows, d)) ** (2 * 14 + 1)
            lags = [r["lag"] for _, r in rows if r.get("hit30")]
            mags = [r["magnitude"] for _, r in rows if r.get("hit30")
                    and np.isfinite(r.get("magnitude", np.nan))]
            lag_med = int(np.median(lags)) if lags else None
            lag_iqr = (f"{int(np.percentile(lags, 25))}..{int(np.percentile(lags, 75))}"
                       if len(lags) >= 4 else "--")
            mag_med = f"{np.median(mags):.1f}x" if mags else "--"
            print(f"  {DETECTOR_LABEL[d]:16s} {kind:6s} {n:3d} {hr[7]:5.0%} "
                  f"{hr[14]:5.0%} {hr[30]:5.0%} {rnd14:6.0%} {p14:6.3f} {p30:6.3f} "
                  f"{str(lag_med):>8s} {lag_iqr:>9s} {mag_med:>8s}"
                  + (f"  obs {obs14}/{n}@14d" if d == primary else ""))
            verdicts.setdefault(kind, {})[d] = {
                "hit14": hr[14], "hit30": hr[30], "p14": p14, "p30": p30}

    print("\n-- verdict (primary detector z-raw>=3, cross-checked) -----------")
    for kind in kinds:
        v = verdicts[kind][primary]
        strong = v["hit14"] >= 0.7 and v["p14"] < 0.05
        weak = v["hit14"] >= 0.5 and v["p14"] < 0.20
        label = "CONFIRMED" if strong else ("WEAK" if weak else "ABSENT")
        print(f"  {kind:6s}: {label}  (hit@14 {v['hit14']:.0%}, p@14 {v['p14']:.3f};"
              f" hit@30 {v['hit30']:.0%}, p@30 {v['p30']:.3f})")
        agree = [d for d in DETECTORS
                 if verdicts[kind][d]["p14"] < 0.10 or verdicts[kind][d]["p30"] < 0.10]
        print(f"           detectors with p<0.10 at 14d or 30d: {', '.join(agree) or 'none'}")
    print("\n  NOTE: n is tiny (see coverage). Any CONFIRMED here means")
    print("  'consistent across ~14 observations and better than chance',")
    print("  not statistical robustness. C4 bottoms are provisional lows.")
    return 0


def _day_rate(rows: list[tuple[Extremum, dict]], detector: str) -> float:
    """Unconditional spike-day rate inside the windows (for context only)."""
    tot = hit = 0
    for e, _ in rows:
        s = e.series
        flags = detector_flags(s, e, detector)
        lo = int(np.searchsorted(s["date"].values, np.datetime64(e.window_start)))
        hi = int(np.searchsorted(s["date"].values, np.datetime64(e.window_end),
                                 side="right"))
        hi = min(hi, len(s))
        tot += max(hi - lo, 1)
        hit += int(flags[lo:hi].sum())
    return hit / max(tot, 1)


if __name__ == "__main__":
    sys.exit(main())

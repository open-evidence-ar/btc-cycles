#!/usr/bin/env python3
"""Measure whether the BTC-halving -> macro-top premise (I-19) actually holds.

I-19 anchors macro projections on BTC halving events, justified in the chart
footer as "macros pivot around BTC halving events (all 4 macro tops fall 0-3y
after each halving)". That justification does not survive inspection.

Halvings are ~4 years apart and macro cycles are ~4 years, so *every* macro
necessarily records a top somewhere in 0-3y after a halving. The window is
uninformative. What would carry information is the lag being STABLE across
cycles -- which is exactly how BTC's own cycle works (~500-560d after each
halving, stable to ~60d).

Measured (days from the cycle's halving to that cycle's local top):

    BTC   ~500-560d   spread ~0.2y   stable
    SPX   602-1112d   spread  1.4y   NO RELATIONSHIP
    NDX   557-1112d   spread  1.5y   NO RELATIONSHIP
    DXY   180-869d    spread  1.9y   NO RELATIONSHIP
    TLT   193-1132d   spread  2.6y   NO RELATIONSHIP
    GOLD  272-1132d   spread  2.4y   NO RELATIONSHIP

No macro has a stable halving lag. TLT -- long-duration Treasuries, whose cycle
is driven by policy and inflation rather than by crypto supply shocks -- is the
worst, and it is the asset whose projection implies a 30y yield near 7%, above
its all-time high.

This script turns the premise into a measurement so it cannot be asserted
silently again. It writes ``_data/cycle_tie.json`` and reports per asset.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data/events.csv"
METRICS = ROOT / "data/processed/alt_cycle_metrics.csv"
OUT = ROOT / "_data/cycle_tie.json"

CYCLES = ["C1", "C2", "C3", "C4"]

#: Max lag spread (years) for a halving-anchored cycle to be considered real.
#: BTC itself runs ~0.2y, so 0.75y leaves generous headroom while still
#: separating "coupled to the halving" from "both series are ~4y periodic".
MAX_SPREAD_YEARS = 0.75

#: How an asset relates to the halving clock. Three categories, because
#: "spread too wide" and "not coupled at all" are different diagnoses and the
#: fix differs:
#:
#:   tied            -- lag is stable, so the halving anchors the cycle.
#:   coupled_loose   -- genuinely BTC-linked (miners move with BTC) but the lag
#:                      is unstable, so the halving is a weak anchor and the
#:                      wide outer window is the honest representation.
#:   not_coupled     -- no usable relationship; date the zones from the asset's
#:                      own history instead.
#:
#: Miners sit in the middle: WGMI's cycle history IS MARA's (identical C1-C3
#: tops and bottoms), and both show the same ~1.5-1.6y lag spread. They are
#: economically coupled to BTC, unlike TLT, but their cycle tops are set by
#: equity beta and mining economics as much as by BTC, so the lag wanders.
TIED = {"eth", "mstr", "xrp", "sol"}
COUPLED_LOOSE = {"wgmi"}
NOT_COUPLED = {"spx", "ndx", "dxy", "tlt", "gold"}

#: Proxy DATA SOURCES, not projected assets. MARA and RIOT have zero rows in
#: alt_next_cycle_zones.csv and are absent from ASSET_DISPLAY: they are never
#: projected, charted or shown in the banner -- they exist only to supply WGMI
#: with pre-launch cycle history (WGMI, the CoinShares miners ETF, launched
#: 2022).
#:
#: They are deliberately NOT classified above. WGMI's C1-C3 history *is*
#: MARA's, so the two measure nearly the same lag spread (1.61y vs 1.52y) by
#: construction. Classifying the proxy alongside the thing it proxies for
#: double-counts a single observation and reads as independent corroboration.
#: They are reported for traceability and gated to have no projection rows.
PROXY_SOURCES = {"mara", "riot"}

CLASSIFICATION = {**{a: "tied" for a in TIED},
                  **{a: "coupled_loose" for a in COUPLED_LOOSE},
                  **{a: "not_coupled" for a in NOT_COUPLED}}

#: Assets currently failing the stability test. Pinned so the suite is green
#: while the violation stays on the record; a NEW failure fails the gate. See
#: tests/test_cycle_tie.py.
UNPROVEN_ASSETS = COUPLED_LOOSE | NOT_COUPLED


def measure() -> dict:
    ev = pd.read_csv(EVENTS, parse_dates=["date"])
    halv = (ev[(ev.event_type == "halving") & (ev.cycle_id.isin(["H1", "H2", "H3", "H4"]))]
            .sort_values("cycle_id").set_index("cycle_id")["date"])
    m = pd.read_csv(METRICS, keep_default_na=False)

    out: dict = {"generated_for": "I-19 halving-anchor premise audit",
                 "max_spread_years": MAX_SPREAD_YEARS, "assets": {}}
    for asset in sorted(set(m["asset"])):
        rows = m[(m.asset == asset) & (m.cycle_id.isin(CYCLES))]
        lags = {}
        for _, r in rows.iterrows():
            h = halv.get("H" + str(r.cycle_id)[1:])
            top = str(r.get("asset_local_top_date", "") or "")
            if h is None or not top or top == "nan":
                continue
            lags[str(r.cycle_id)] = int((pd.to_datetime(top) - h).days)
        if len(lags) < 2:
            continue
        vals = list(lags.values())
        spread_y = (max(vals) - min(vals)) / 365.25
        out["assets"][asset] = {
            "lags_days": lags,
            "spread_years": round(spread_y, 2),
            "halving_tie_supported": bool(spread_y <= MAX_SPREAD_YEARS),
        }
    return out


def main() -> int:
    res = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from csv_io import atomic_write_json
    atomic_write_json(OUT, res, indent=2)

    print(f"  halving-anchor premise (spread threshold "
          f"{res['max_spread_years']}y), as of {date.today().isoformat()}:")
    loose, none_ = [], []
    for asset, d in sorted(res["assets"].items()):
        if asset in PROXY_SOURCES:
            print(f"    {asset:5s} spread {d['spread_years']:>5.2f}y  "
                  f"n/a         proxy source (not projected; feeds WGMI)")
            continue
        cls = CLASSIFICATION.get(asset, "unclassified")
        flag = "stable" if d["halving_tie_supported"] else "unstable"
        print(f"    {asset:5s} spread {d['spread_years']:>5.2f}y  {flag:10s} "
              f"{cls}")
        if not d["halving_tie_supported"]:
            (none_ if cls == "not_coupled" else loose).append(asset)
    if loose:
        print(f"    -> coupled but loose-lag (weak anchor, wide window): {', '.join(loose)}")
    if none_:
        print(f"    -> not coupled (zones dated from OWN history): {', '.join(none_)}")
    print("    (mara/riot are proxy sources for WGMI's pre-launch cycles, "
          "not projected assets; they are not classified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# I-20 (banner view-layer fixes) — WGMI pre-history constraint

**Increment:** I-20 (per-asset banner pivot — view-layer follow-up)
**Date:** 2026-08-05
**Status:** Mitigated by launch-date footnote + ~10y timeline cap
**Rule tuned:** Per DESIGN.md §9.4 (rule tuned, reconciliation entry written)

## Background / constraint

WGMI (CoinShares Bitcoin Miners ETF) launched **2022-02-08**. Yahoo Finance
returns daily OHLCV back to the ETF listing date, no earlier. So
`data/raw/wgmi_yahoo_*.csv` genuinely starts at 2022-02-08 — the 1,121 daily
rows are not a fetcher-gap or snapshot-window artefact; they are the entire
public history of the instrument.

Compared against the other 5 banner assets (BTC / ETH / SOL / XRP / MSTR),
all of which have raw yahoo/bitstamp history extending much further back:

| Asset | First hist date | Source | Public history span |
|---|---|---|---|
| BTC | 2011-08-18 | bitstamp | ~14 y (banner samples from 2022-09-01) |
| ETH | 2017-11-09 | yahoo | ~8.6 y (banner samples from 2022-01-01) |
| XRP | ~2017      | cdd/yahoo | (banner samples from 2022-01-01) |
| SOL | 2020-04-11 | yahoo | ~6 y (banner samples from 2022-01-01) |
| MSTR | 1998-06-11 | yahoo | ~28 y (banner samples from 2022-01-01) |
| WGMI | 2022-02-08 | yahoo | **~4.4 y — full life of the ETF** |

The 4.4 y span is by construction (no proxy data used in the banner, in
contrast to the C8f prediction chart which uses MARA history for WGMI's
pre-launch cycles C1-C3 — see `build_c8_wgmi` in `scripts/build_charts.py`).

## Symptom (pre-mitigation)

With the original banner's `tlStart = lastMs` (2026-06-18, the observed WGMI
C4 top) and `tlEnd = furthest window outer_end` (2033-07-21, the B5 exit),
the visible WGMI timeline spanned ~7.1 y (2026-06 → 2033-07). The full
4.4 y of price history all sat to the LEFT of `tlStart` → clipped at the
left edge of the SVG plot area → the visible WGMI line compressed into a
thin vertical band on the left side of the strip. Other assets, whose
`tlStart` anchor (their C4 top) is comparable in date to WGMI's, did not
show the same compression because their `tlEnd` lies earlier (e.g. BTC
B5 exit outer_end = 2030-11-09). WGMI's exit window extends much further
right (2033-07-21) because WGMI's projected C5 cycle is later and the
exit zone is wider.

## Mitigation applied (view-layer only; no backend change)

**1.** `drawStrip()` in `_includes/now-stamp.html` now sets
`tlStart = min(lastMs, firstHistMs)` so the entire observed price line
fits inside the strip — no left-edge clipping for any asset.

**2.** Timeline `tlEnd` capped at `tlStart + 10y`. For WGMI this means
`tlStart = 2022-02-08` → cap at 2032-02-03. The actual published window
end (2033-07-21) exceeds the cap by ~1.45 y. A small `→ +1.4y`
continuation marker (vertical dashed line + label at the right edge)
indicates the published windows extend further than the cap allows.

**3.** When the first `price_history` point arrives noticeably later than
the timeline start (the only case is WGMI's 2022-02-08 launch where
`tlStart` equals `firstHistMs` exactly — so this clause does NOT fire for
WGMI under the current data, but would fire for any future asset whose
first hist point is more than 30 days later than `tlStart`), a small
italic footnote "history from YYYY-MM-DD" is rendered near the lower-left
corner of the strip.

Net effect across the 6 banner pills:

| Asset | tlStart (now) | tlEnd (now) | Span | Overshoot marker? |
|---|---|---|---|---|
| BTC  | 2022-09-01 | 2030-11+~3w (pad) | ~8.2 y | no |
| XRP  | 2022-01-01 | 2030-09+~2w (pad) | ~8.7 y | no |
| ETH  | 2022-01-01 | 2030-09+~2w (pad) | ~8.7 y | no |
| SOL  | 2022-01-01 | 2031-03+~2w (pad) | ~9.2 y | no |
| MSTR | 2022-01-03 | 2030-11+~2w (pad) | ~8.9 y | no |
| WGMI | 2022-02-08 | 2032-02+~2w (cap) | ~10.0 y | **yes, +1.45y** |

WGMI now occupies the full visible width (~10 y) of the strip, with all
~4.4 y of history visible from the left edge and ~5.6 y of projected
windows visible to the right edge (capped, with the continuation marker).

## Why not proxy-pad WGMI with MARA history (the C8f approach)?

The C8f prediction chart (`build_c8_wgmi` in `scripts/build_charts.py`)
borrows MARA history for WGMI's pre-launch C1/C2/C3 cycle anchors because
MARA is the largest full-cycle-history miner in the WGMI basket. That
borrowing is a **modelling** decision (it directly affects the projectable
drawdown/multiplier series — needs the same source data shape).

The banner is a **view-layer context strip**, not a model artefact.
Mixing MARA-proxy pre-2022 with true WGMI OHLCV post-2022 in a single
continuous price line in the banner would be misleading (it would imply
WGMI traded at MARA's prices for ~4 years before it existed). The cap +
footnote approach preserves data integrity while making the genuine
short history readable.

## Validation

- `pytest -q tests/` → 182 passed (no test asserts on the banner's
  WGMI visualisation layer).
- `bundle exec jekyll build` → 0.33s, clean.
- Hand-simulated per-asset projection walks via `render_test.py` confirm
  WGMI's projection range ($17–$139) and timeline span (10 y + 1.45 y
  overshoot) look reasonable against the other 5 assets.

## Scope

This reconciliation note documents the WGMI timing-data constraint
intrinsic to the ETF, and the chosen view-layer mitigation. No backend
change to `build_cycle_status.py` for this note (separate view-layer
follow-up bug fix to the C5/B5 price-center extraction IS in
`build_cycle_status.py::_zone_center()` — documented inline there).

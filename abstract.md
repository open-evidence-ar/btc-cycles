---
layout: default
title: Abstract
permalink: /abstract/
---

<a id="disclaimer" aria-label="Disclaimer"></a>

> **DISCLAIMER.** This site is research, not financial advice. The
> framework documents patterns in historical Bitcoin cycle data and projects
> uncertainty bands for the next cycle. It does not allocate capital, place
> orders, or recommend any specific trade.

## Thesis

Bitcoin's supply schedule produces a deterministic supply-shock approximately
every four years (the "halving"). Historically each halving has been
followed by a parabolic price expansion and a subsequent bear-market reset.
We test whether the **calendar durations** (days from halving to top,
halving to bottom, top to next bottom) and **price magnitudes** (multiplier
from cycle bottom to top, peak-to-trough drawdown) form a recognizable
pattern across completed cycles, and use the empirical distribution of
those statistics to forecast forward time ranges and price bands for the
**next cycle**.

The forecast is published as **uncertainty bands, not point estimates** —
because the dataset is small (n = 3 or 4 completed cycles) and because each
cycle's price magnitudes have varied widely. The framework's primary
contribution is not a specific number but a **transparent, reproducible
pipeline** that any reader can re-run against fresh data.

An econophysics cross-check asks: could the way the BTC cycle holds its
shape be explained the same way nature explains flocks? [Appendix E]
Two things match: (1) **Polarisation in BTC stays strong even as the
crowd grows** -- exactly what real bird flocks show (order parameter
~0.96 across 120-4,000+ starlings); (2) **The calendar repeats inside 4%**
across completely different market-cap sizes (C2-C4), same way Kuramoto
phase-locking in nature is N-independent. A third line (each cycle's
bubble-size shrinking) is numerically reliable but has no confirmed
mechanism beyond the price series itself. No new prediction is claimed --
the work is *interpretation only* [Appendix E]. [context, not forecast].

## How to read this document

Decision-useful reference, not an abstract research note. The bands are a
calendar-and-price context to hold alongside your own process — scheduled
attention windows, not instructions to transact at a specific level.

Every exhibit on this site is labelled inline as one of:

- **Model input** — feeds a number in the zone map (e.g. `forward_ranges.csv`,
  the 2-stage projection chain). Move the published band.
- **Decision overlay** — does not change the number; identifies *when in the
  band to pay most attention* (SMA floors, folklore rhythm).
- **Model input modifier** — does not introduce a new number, but *adjusts the
  tolerance* of an existing model input (e.g. `top_character` widening the
  B4 cross-check band when the cycle top prints apathetic rather than euphoric).
  A modifier changes how much to trust a band, not the band's center.
- **Context, not forecast** — correlations and regime robustness describe
  the environment the forecast lives in; they do not move the B4 / C5 numbers.

Full definitions of each role and their labelled exhibits in
[Appendix A — Methodology](#methodology).

## Date format convention

Tabular data on this site uses ISO `YYYY-MM-DD` throughout. The sticky
banner at the top of each page uses `Mon YYYY` for brevity (e.g.
`Oct 2026` for the B4 attention window center). Both refer to the same
calendar dates — cross-references resolve to the *day*, not the *month*.
Narrative prose may use either format depending on context; tables and
zone-map cells always use ISO.

## What this site covers

1. The four Bitcoin halving cycles (C1, C2, C3 — completed; C4 — nearing
   completion), with explicit per-cycle event tables (bottoms, halvings,
   tops, next bottoms) and the **structural marker** each top printed
   (euphoric blow-off vs apathy).
2. Cross-asset phase-conditioned correlation between BTC and **ETH, SOL,
   XRP**, plus **SPX, NDX, DXY, TLT** — measured separately in each of
   four cycle phases (accumulation, early bull, late bull, bear). Used as
   **context** for reading the BTC bands and as input to the per-asset
   timing extension in (5).
3. A leave-one-cycle-out (LOOCO) backtest that hides one cycle's top
   and bottom from the fit and reports the error of the prediction — the
   honest error bar attached to the headline numbers in (4).
4. **Forward zone estimates** (accumulation / distribution / exit) for the
   next BTC cycle — the load-bearing **decision windows** that follow from
   (1) + (3). Each published as a base-case interquartile band overlaid on
   a wider historical envelope, with a stated cross-check status.
5. Per-asset timing extensions of (4) for the same cross-section from (2),
   so the reader sees the same *attention windows* translated to ETH / SOL /
   XRP calendars (where the data permits) and the explicit envelope-only
   treatment for SPX / NDX / DXY / TLT, which are **not** cycle-tied.

## Source-of-truth files

The framework's reproducibility rests on three files:

| File | Role | Updated by |
|---|---|---|
| `DESIGN.md` | Inputs, procedure, deliverables — never point estimates | humans |
| `data/raw/manifest.txt` | SHA-256 of every raw CSV snapshot | ingest scripts |
| `data/processed/*.csv` | Cycle metrics, returns, correlations, ranges | analysis scripts |

All numbers published on this site are **outputs of increment-gated scripts**
that read from those files. If a snapshot is re-fetched, the analysis is
re-run, the gates are re-evaluated and the published page regenerates.

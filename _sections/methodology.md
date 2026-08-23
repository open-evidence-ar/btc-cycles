---
layout: default
title: A. Methodology
permalink: /methodology/
weight: 60
---
> **HEADS UP.** This page is a forward-reference to [`DESIGN.md` §5](https://github.com/{{ site.github.owner_name }}/{{ site.github.repository_name }}/blob/main/DESIGN.md#5-methodology).

## How the pieces fit

The framework is built in five layers. Each layer has an explicit role in
producing the published numbers — the role is what the reader needs to know
when reading them back. Three roles recur throughout (see
[Abstract — How to read this document](#abstract)):

- **[model input]** — feeds a published number in the zone map.
- **[decision overlay]** — does not change the number; identifies *when to
  pay attention* within the band.
- **[context, not forecast]** — describes the environment the forecast
  lives in; does not move the bands.

## Sections

1. **Cycle anatomy extraction** *(model input)* — Rule T (top detection)
   and Rule B (bottom detection) with reproducibly-defined neighborhoods.
   Produces the event dates in `btc_cycle_metrics.csv` that anchor every
   calendar duration downstream.
2. **Halving-day alignment** *(model input)* — every panel asset indexed on
   BTC-days-from-halving coordinate. Lets the same forward-range method run
   on BTC and on the alt cross-section uniformly.
3. **Phase-conditioned correlation** *(context — feeds I-12 robustness, not
   the zone map)* — Pearson + Spearman + rolling + cross-lag, computed in
   each of four cycle phases. **Role:** characterise the BTC-vs-macro and
   BTC-vs-alt environment per phase, so the reader can discount the BTC
   bands when a known sign-flip regime is active. Does **not** feed the B4
   / C5 numbers in `next_cycle_zones.csv`.
4. **Forward range estimation** *(model input)* — mean / median / min-max /
   IQR envelopes per cycle statistic, with mandatory LOOCO sensitivity
   reporting. Feeds the zone map directly.
5. **Validation** *(context — confidence discount for the zone map)* —
   backtest-by-cycle + macro-regime subsample robustness. Reports the
   honest error bars attached to (4) and the regime sensitivity attached to
   (3); neither moves the published bands, both inform how much trust to
   place in them per cycle.

## Decision overlays (descriptive, not load-bearing)

Two artefacts in this framework are computed and charted but **do not feed
the zone map**. They are published because they identify *where in a band
to pay the most attention* — and are labelled explicitly so the reader
knows not to wait for them to change a number:

- **SMA valuation floors** (`C-SMA`, 50w / 200w): a long-horizon valuation
  overlay that historically clusters near bear-cycle bottoms. See
  [`cycle-anatomy.md` §"SMA Valuation Floors"](#cycle-anatomy). A weekly
  close + reclaim pattern inside the B4 window is treated as a *confirmation
  signal* on the bottom, not as a model input that tightens the band.
- **`top_character` column** (`btc_cycle_metrics.csv`): euphoric vs
  apathetic top classification. A descriptive corroboration of the Cowen
  memo's "top on apathy" claim for C4. Does not change the C5 multiplier
  fit; published so the reader can see that the cross-check FAIL on B4
  coincides with an apathetic top, which is exactly the regime that
  widens rather than tightens the band.

## Phase definitions

| Phase | Window (days from halving) | Label | Narrative role |
|---|---|---|---|
| P1 | (-540, 0) | Accumulation — pre-halving bottom → halving | *Where to look for the bear bottom* (B4 lives here) |
| P2 | (0, +270) | Early bull — halving → first parabolic expansion | *Confirmation window* — break of 50w + first lower-high |
| P3 | (+270, +540) | Late bull / blow-off — expansion → cycle top | *Where to look for the top* (C5 lives here) |
| P4 | (+540, next halving) | Bear / re-accumulation — top → next-cycle bottom | *Exit window* — distribution → re-accumulation |

The phase bounds are the same regardless of which role an artefact plays —
they're the calendar the whole site is laid out against.

## 2-stage projection (the math behind The Prediction's windows)

This is the technical derivation that produces the four BTC decision windows
in [The Prediction (BTC)](#predictive-ranges). Executive readers can skip
this entire section. Full fit equations, residual std, and cross-check
formula are recorded per-cycle in the `compression_fit_note` column of
`next_cycle_zones.csv`; what follows is the structural summary.

### Why two stages

Each halving cycle chains bottom-to-bottom (B4 = post-C4 bear bottom; B5 =
post-C5 bear bottom). The C5 top projection must therefore be anchored on
the projected B4, not on the observed B3. Two power-law fits chain the
projection.

### Stage fits

- **Stage 1** `ratio_n = a * idx^b` — fits the bear-bottom price ratio series
  (`[B0,B1,B2,B3]` → `B4/B3 = 2.75`, B4 = $43,081). Slope t-test at one-sided
  α=0.20 with `df_resid=2`.
- **Stage 2** `mult_n = a * idx^b` — fits the bottom→top multiplier series;
  C5 mult = Stage2( idx=5 ). Optional 2.0× floor.
- **Cross-check** — independent B4 from `observed_C4_top * (1 - dd_C4)`.
  PASS if within 15% relative; FAIL otherwise. BTC today: **FAIL @ +45.6%**
  (Stage 2 path prints B4 at $29,596, Stage 1 prints $43,081).

### Caveats

Each stage fits n=3-4 observations with a 2-parameter power-law. R² is
high (>0.95) by construction; the residual std gives the prediction band
width and is the meaningful uncertainty. The cross-check FAIL on B4 is a
**published finding**, not a fix — C4's apathetic top printed below the
euphoric-cycle expectation, and the B4 band widens to the union of both
estimates ($29,596 – $53,673) rather than silently inheriting euphoric
assumptions. Full derivation in `DESIGN.md` §9.4 (R-4 / R-5).

## Forward-range statistics (the raw distributions that feed the zone map)

The four published BTC decision windows (in
[The Prediction (BTC)](#predictive-ranges)) are derived from the
forward-range statistics in `data/processed/forward_ranges.csv`
(n=3-4 cycles, **LOOCO** sensitivity column below).

| Statistic | n | Mean | Median | Min | Max | Sensitive? |
|---|---|---|---|---|---|---|
| D_prev_bottom_to_halving | 4 | 488 | 515 | 380 | 542 | No |
| D_halving_to_top | 4 | 494 | 530 | 371 | 546 | No |
| D_top_to_next_bottom | 3 | 383 | 378 | 364 | 406 | No |
| mult_bottom_to_top | 4 | 167 | 67 | 8 | 527 | Yes |
| drawdown_pct | 3 | 0.82 | 0.83 | 0.77 | 0.85 | No |
| D_bottom_to_next_top (folklore cross-check) | 3 | 1058.7 | 1059 | 1050 | 1067 | No |

> **Note on sample sizes:** `D_halving_to_top` and `mult_bottom_to_top`
> now use C4 data (n=4), while `D_top_to_next_bottom` and `drawdown_pct`
> remain n=3 (C4 top is observed but B5 has not yet bottomed). The
> updated n=4 rows shift the mean and median; the outer min-max range
> for `mult_bottom_to_top` widens to 8–527× reflecting C4's apathetic
> multiplier (7.97×) at the low end.

Cross-reference: `D_top_to_next_bottom` → B4 window; `mult_bottom_to_top` → C5 multiplier; etc.

## LOOCO backtest

Leave-one-cycle-out (LOOCO) predictions vs actual `D_halving_to_top`,
using the other 3 cycles' mean as the prediction for the held-out cycle:

{% include chart.html id="C7" caption="C7 — Leave-one-cycle-out predictions vs actual D_halving_to_top. Perfect prediction = diagonal." %}

| Leave-out | Actual | Predicted (mean) | Date error | Within outer range? |
|---|---|---|---|---|
| C1 | 371d | 536d | 164.5d | ✓ |
| C2 | 525d | 459d | 66.5d | ✓ |
| C3 | 546d | 448d | 98.0d | ✓ |

All three LOOCO predictions fall within the historical min-max envelope;
all date errors < 200 days. The B4 / C5 bands in
[The Prediction (BTC)](#predictive-ranges) are quoted as median ±
IQR (base band) and min-max (outer band). That median/IQR structure **is**
the LOOCO error structure propagated forward. C3's ~98d prediction
error on `D_halving_to_top` is the *wide* end of the family — using the
outer envelope rather than the IQR is the appropriate response when
your own process expects a C3-analogue cycle. For a multi-year decision
window centred on Oct-2026 (B4) or Sep-2029 (C5), 100-day prediction
error is small relative to the use case — the platform is the cycle, not
the session.

## Macro-regime robustness

Phase-conditional correlation sign-flip counts under DXY ±1σ and
TLT ±1σ regimes (per `data/processed/correlations_BY_regime.csv`):

| Macro Asset | Regime | Sign flips (of 4 phases) |
|---|---|---|
| DXY | High | 3 |
| DXY | Low | 2 |
| TLT | High | 2 |
| TLT | Low | 4 |

**Reading this for the actionable confidence level.** DXY-high and TLT-low
regimes (>2 sign flips of 4 phases) flag the macro backdrops under which
BTC-vs-macro correlation has historically been most unstable. The BTC
bands are anchored on the BTC *cycle*, not on BTC-vs-macro correlation,
and the cycle survives regime switches — the framework deliberately
publishes bands that work **across** regimes rather than fitting a single
regime. A regime switch **during** the B4 attention window historically
coincides with a deeper drawdown-on-the-band.

**Caveat:** DXY-high and TLT-low regimes show elevated sign-flip counts
(>2), indicating that BTC-macro correlations are regime-sensitive. This is a
published finding, not a methodology failure.

## Historical BTC cycle visualizations

### BTC Price with Cycle Overlays

{% include chart.html id="C1" caption="C1 — BTC log price with halving (green), top (red), and bottom (blue) markers." %}

### Cycles Aligned by Days from Halving

{% include chart.html id="C2" caption="C2 — BTC cycles aligned on halving day (x-axis = days from halving, ±1500d)." %}

### Per-Cycle Duration Metrics

{% include chart.html id="C3" caption="C3 — Days from bottom → halving, halving → top, and top → next bottom for each cycle (C1–C3 with measured durations; C4 bar pending)." %}

## Per-asset projection modes

Per-asset projection modes were moved here (Aug 2026 reorg) from the
"Per-Asset Decision Windows" page so that the decision-page itself reads
as a tight trader-actionable ledger. The mode is recorded in the
`compression_fit_used` column of `data/processed/alt_next_cycle_zones.csv`.
Statistical safeguards (slope t-test α=0.20, economic floor 2.0× for
crypto / 1.05× for macros, ± log_residual_std prediction band, median
fallback, cross-check widens to union on >15% disagreement) are the same
as BTC's Stage-1/Stage-2 — see §"2-stage projection" above.

| Mode | Asset(s) | Why |
|---|---|---|
| `2_stage_with_observed_c4` | **ETH** | Asset-native Stage-1 fit on `[B0,B1,B2,B3]`. Cross-check vs dd-path. ETH FAILs @ +15.3% (C4 below euphoric expectation; n_drawdowns=2 makes the dd power-law admittedly weak). |
| `borrowed_2_stage_from_BTC` | **XRP, MSTR, WGMI** | Only 0-2 observed bear bottoms (XRP, WGMI) or insufficient full-cycle coverage (MSTR: only post-Aug-2020 treasury-pivot data is BTC-correlated) — too few for asset-native ratio fit. Borrow BTC's projected B4 timing anchor (BTC B4 center Oct-22-2026), shift by asset's own lag-vs-BTC-bottom; B4 *price* from asset's own prior-cycle drawdowns on observed C4 top. |
| `borrowed_2_stage_from_ETH` | **SOL** | (2026-08-11) SOL's own dd/mult series are dominated by its C3 first-cycle monster (mult=502x, dd=0.963), so its own naive-median publishes an absurd C5 band. Borrow ETH's per-cycle ratios aligned by asset-cycle ordinal (SOL C3~ETH C2, SOL C4~ETH C3, SOL C5~ETH C4), evaluating ETH's fitted dd/mult curves at ordinal 3 (dd=0.687, mult=7.11). Anchor = SOL's observed C4 top ($261.82). |
| `macro_2_stage_own_shape` | **SPX, NDX, DXY, TLT, GOLD** | I-19 / I-19b: anchors = own observed C4 top; shape (drawdown depth, bottom-to-top multiplier) fit on the macro's OWN dd/mult series (n=3 from C1-C3 since C4 bottoms are still open for the macros). Economic floors relaxed (dd_floor=0.05, mult_floor=1.05); B4 band drawdown clamped to the macro's observed dd range. Gold additionally carries the validated 20-mo SMA / 21-mo EMA bull-support-band cross-check ($3,813-$3,830 @ 2026-07-31, see `docs/gold_seasonality.md`). See `docs/blockers/I-19-macro-2stage.md` for full methodology. |

### Per-asset extrema + forward ranges

Full per-cycle local-top dates + day-counts from BTC halving: see
`data/processed/alt_cycle_metrics.csv`. Per-asset LOOCO-sample
sensitivity on `D_asset_halving_to_top` (7 rows, n=2-4): see
`data/processed/alt_forward_ranges.csv`.

**Observation across the cross-section:** high-beta alts tend to top
*just before* or within ±10 days of the BTC cycle top. ETH C3 =
2021-11-08 (546d from H3, matches BTC's own 546d almost exactly). SOL
C3 = 2021-11-06 — two days before ETH, four before BTC.

### SOL data-coverage note

SOL launched 2020-04 with Bitfinex SOLUSD daily data available from
2021-12-08 forward — one complete BTC halving cycle (C4) plus a
partial C3 window starting late 2021. In an earlier build SOL's missing
C3 was **proxied** from ETH-C2 under a sequential-aging hypothesis;
that proxy is now **retired** — Bitfinex SOLUSD history back to
2021-11-06 lets us extract an *actual* SOL C3 local top at
2021-11-06 (544d from H3), two days before ETH and four before BTC.

SOL's next-cycle zone map borrows from **ETH** (`borrowed_2_stage_from_ETH`,
ordinal-aligned) rather than from BTC: two observed bear bottoms is not
enough to power-law-fit an asset-native ratio series, and SOL's own
dd/mult series are dominated by its C3 first-cycle monster (mult=502x)
which would otherwise publish an absurd C5 band. ETH's per-cycle ratios
are borrowed aligned by asset-cycle ordinal (SOL C3~ETH C2, SOL C4~ETH C3,
SOL C5~ETH C4), evaluating ETH's fitted curves at ordinal 3. The B4
*timing* is still borrowed from BTC's projected B4 and shifted by SOL's
own historical lag-vs-BTC-bottom; the B4 *price* = SOL's observed C4 top
× (1 − ETH-ordinal-3 drawdown). Once SOL completes its own C5 cycle
(post-2028), a third observed bear bottom will permit an asset-native
Stage 1 fit and retire the borrowed-shape model.

### Coverage matrix

| asset | C1 | C2 | C3 | C4 |
|---|---|---|---|---|
| ETH | missing | actual | actual | actual_C4_open |
| XRP | missing | missing | actual | actual_C4_open |
| SOL | missing | missing | actual | actual |
| MSTR | excluded | excluded | actual | actual_C4_open |
| WGMI | mara_proxy_C1 | mara_proxy_C2 | mara_proxy_C3 | actual_C4_open |
| SPX | actual | actual | actual | actual_C4_open |
| NDX | actual | actual | actual | actual |
| DXY | actual | actual | actual | actual |
| TLT | actual | actual | actual | actual |
| GOLD | actual | actual | actual | actual_C4_open |

(`actual_C4_open` means the asset has C4 live data but the bear bottom
hasn't been observed yet — the metric is provisional.)

## Appendix — I-21 curve-regime mechanism (reference)

**Action summary lives on the decision pages.** The rule in one line:
when the gated US yield-curve regime at the projection anchor has a
*computed* multiplier for an asset (n ≥ 3 observed drawdowns onsetting
in that regime), that asset's published B4 corridor **is automatically**
the regime-adjusted band — the numbers you read everywhere already
include it, and charts mark it (`×mult applied`, dotted gray = what it
would have been unadjusted). When every cell is `fallback` (today), no
corridor changes and nothing is displayed on decision surfaces.

This appendix carries the mechanism detail so the timing pages stay clean.

### Sensitivity table (all counterfactuals)

{% include regime-sensitivity.html %}

### Signal dashboard (C8h)

{% include chart.html id="C8h" height="760px" caption="C8h (appendix) — US yield-curve regime dashboard: 10y−2y slope with classifier trigger levels, raw daily classification, gated regime ribbon (5-day persistence) with every asset's drawdown-onset markers and the current-regime anchor." %}

---
*Data snapshots: `data/raw/manifest.txt` · Cycle metrics: `data/processed/btc_cycle_metrics.csv`*
*Canonical event table `data/events.csv` SHA-256: `be24b84859d71ea8598c6a0fc16ebf2262291cd20b87e691090243e717e6289a`*
*Source-of-truth: I-01 gate `tests/test_events_schema.py`*
*2-stage projection helpers: `two_stage_projection_with_observed_c4` in `scripts/build_charts.py`*
*Methodology correction: `DESIGN.md` &sect;9.4*

---
layout: default
title: The Prediction (BTC)
permalink: /predictive-ranges/
weight: 10
---
> **Role:** [model input -- the load-bearing decision windows].
> The rows below are the published attention windows for the next BTC
> cycle -- read each row as a *when* to look, not what to buy.
> Pair with the 200w SMA overlay [Appendix B](#cycle-anatomy) inside
> the B4 window and the folklore cross-check on C5.

## The four BTC decision windows

The framework prints one **attention window** per calendar event in the
next BTC cycle. Each published as a base case (interquartile) inside a
wider outer envelope (min-max). The full forward-range statistics - including **LOOCO
sample sensitivity** - are in
[Appendix A - Methodology](#methodology); the four headline windows are
all a decision-oriented reader needs.

> **Cross-check status: FAIL (+45.6%).** Stage 1 vs Stage 2 B4 paths
> disagree by +45.6%; the published band is the **union** of both
> ($29,596 – $53,673). C4's apathetic top widened rather than silently
> inheriting euphoric-cycle expectation — see [Appendix A — Methodology](#methodology).

| # | Zone | Window (base / outer) | Price corridor (base) | **Decision rule (falsifiable)** |
|---|---|---|---|---|
| 1 | **Bear bottom (B4)** | 2026-10-12 → 2026-11-02 / 2026-10-05 → 2026-11-16 | $29,596 – $53,673 (center $43,081) | **If** 200w break + reclaim (`C-SMA`, Appendix B) prints **inside** this window → bottom structurally confirmed, upgrade confidence. **If** 200w reclaim prints *before* window and *fails* → false signal (C3 pattern), stand down. **If** 200w reclaim prints after window closes → late signal, mark B4 as already-in at the prior base window. |
| 2 | **Accumulation** | 2026-11-04 → 2028-04-01 | (no price band — not a price event) | **Patience window.** Do not chase. Model's primary signal (B4) has already printed; next event (C5) is 2+ years out. No decision rule here — accumulate per your own DCA within the B4 corridor. |
| 3 | **Distribution (C5 TOP)** | 2029-07-31 → 2029-09-20 / (outer 2029-04-07 → 2029-09-29) | $186,863 – $338,883 (center $272,004) | **If** both Stage-2 distribution window **AND** B4-anchored folklore window (Sep-15-2029, ±4d) print together → strongest published attention peak, route to exit. **If** price tags $200k+ but no band overlap → watch for fade but don't exit on tag alone. **If** folklore window closes with no local top → resist exit, downgrade folklore line for C6. |
| 4 | **Exit (B5 post-C5)** | 2030-09-18 → 2030-10-09 / 2030-04-06 → 2030-11-09 | $58,447 – $79,759 (center $69,103) | **If** weekly close prints inside this band after the C5 top → mark B5 active, attention re-peaks. A watchpoint, not a continuous hold-to-date instruction. Same rule as B4 applied one cycle later. |

> **Confluence — strongest published attention peak in the framework.**
> The Stage-2 distribution window (2029-07-31 → 2029-09-20, base) and the
> B4-anchored folklore window (2029-09-15 ±4d) both point at
> the *same week of September 2029*. The H5-anchored and B4-anchored
> centers differ by only **+3 days** center-to-center; the folklore band
> alone is **~6× tighter on IQR** than the H5-anchored band (8d vs 50d
> interquartile), and **~10× tighter on the outer min-max envelope** (53d
> vs 546d). When a halving-cycle power-law fit and the folklore
> cross-check agree on a single September-2029 week, that *is* the
> published distribution signal — every other reader's exit logic needs
> to triangulate *against* that week, not in place of it. (Caveat: the
> folklore band is a qualitative cross-reference — see Appendix B — not
> an independent source; it tightens where two framework-derived paths
> already agree.)

## Underlying statistics

The 2-stage projection chain (B3- C4- B4- C5- B5) and the underlying
forward-range statistics table (n=3-4 cycles, **LOOCO** sensitivity) are
fully documented in [Appendix A - Methodology](#methodology).
The chart below renders the published windows.

{% include chart.html id="C6" height="1000px" caption="C6 — BTC next-cycle (C5) price predictions, 2-stage model anchored on observed C4 top. Single tall log-scale panel: BTC price line 2022-09 to 2031-06 with zone shading (ACC/DIST/EXIT), event markers (B3, H4, observed C4 top, projected B4, H5), and prediction bands. C5 TOP band (orange): $187k–$339k during distribution window. B5 BOTTOM band (blue): $58k–$80k during exit window. The translucent **purple** folklore band marks the B4-anchored C5 top of 2029-09-15 (see Appendix B). Muted dotted 50w/200w SMA floor overlays (gray) cross-reference the B4 in-band confirmation rule (see decision table row 1). Bands narrowed (0.75x residual std)." %}


---
*Forward ranges: `data/processed/forward_ranges.csv`*
*Zone map + derivation: `data/processed/next_cycle_zones.csv`*
*Methodology + 2-stage fits + cross-check formula: [Appendix A — Methodology](#methodology)*
*2-stage projection helpers: `two_stage_projection_with_observed_c4` in `scripts/build_charts.py`*

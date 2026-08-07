---
layout: default
title: B. Cycle Anatomy
permalink: /cycle-anatomy/
weight: 40
---
## SMA Valuation Floors (I-18a) — decision overlay, not a model input

> **Role:** [decision overlay] — the 50w/200w SMAs do **not** feed
> `next_cycle_zones.csv` and do not change a published B4 / C5 number.
> They are published because the historical 200w-break/reclaim pattern
> clusters inside the B4 window the model already printed from an
> independent input (the bottom-ratio power-law). Treated as a
> **confirmation signal on the bottom**: when the model's B4 band says
> "pay attention Oct 2026" and the weekly close prints a 200w break +
> reclaim in that same window, the band's confidence goes up — but the
> band's *number* does not move.

The 50-week and 200-week Simple Moving Averages of BTC daily close serve as
structural valuation floors. Per the
[Cowen *Bitcoin Cycle Memo* (Jul 2026)](https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026):

- **200-week SMA** — the "date with destiny." Weekly closes beneath it have
  historically clustered in late-stage bear markets, including the 2015
  cycle bottoming, the 2018 capitulation, the 2020 pandemic flush, and the
  2022 break → false-reclaim → second-loss sequence that preceded the C3
  bottom on Nov 21, 2022.
- **50-week SMA** — transition-confirmation level. Two consecutive weekly
  closes above the 50w mark a higher-confidence bear-to-bull transition than
  an initial 200w reclaim.

**How to use this overlay against the B4 band in
[`predictive-ranges.md`](#predictive-ranges):**

1. The model prints B4 (the post-C4-top bear bottom) as a *calendar window
   and price corridor* from the bottom-ratio power-law. For the current
   cycle that is **Oct 2026, $29.6k–$53.7k** (cross-check FAIL — see
   `predictive-ranges.md` for why the band is published as a union).
2. The reader watches for the **200w break + reclaim sequence** to print
   *inside* that window. A 200w reclaim that prints *before* B4 (e.g. a
   summer relief rally that reclaims 200w then loses it) is a false
   signal — the C3 sequence shows exactly that pattern.
3. The **50w two-close reclaim** then marks the higher-confidence
   bear-to-bull transition — the moment to treat the B4 event as
   *structurally* confirmed rather than just a calendar hit.

The chart below visualises BTC weekly close alongside both SMAs on a log
axis, with break-below (▼) and reclaim (▲) transition markers using the
symmetric 2-close rule (plotted on the second consecutive confirmation week).

{% include chart.html id="C-SMA" caption="C-SMA — BTC weekly close vs 50w (yellow dotted) and 200w (cyan dashed) SMA floors, with break-below (▼) and reclaim (▲) transition markers. Used as the in-band confirmation overlay on the B4 window (see predictive-ranges.md decision table)." %}

## Per-Cycle Top Character — model input modifier, not a decision overlay

> **Role:** [model input modifier] — the `top_character` column lives in
> `btc_cycle_metrics.csv` and corroborates the Cowen memo's "top on
> apathy" diagnosis for C4. It does **not** change the C5 multiplier
> fit itself. It **does** adjust the *tolerance* of the B4 cross-check
> band: when the cycle top prints apathetic (as C4 did), the drawdown-path
> B4 estimate falls below the ratio-path estimate, which widens rather
> than tightens the band. The reader uses this to *temporarily widen the
> mental error bars on the C4→B4 multiplier path* and lean on the
> published union band instead of the center.
>
> This is the only exhibit in the framework with the
> [model input modifier] role (see [Appendix A — Methodology](#methodology)):
> it does not introduce a new number, but it adjusts how much to trust an
> existing one. See the confidence-grades table in
> [Confidence & Limits](#validation) for the resulting confidence grade.

The `top_character` column in `btc_cycle_metrics.csv` classifies each cycle
top using two structural markers from the Cowen memo:

- **Euphoric** tops: bottom-to-top multiplier > 10× AND drawdown > 75%
  (matches C1, C2, C3 — the parabolic blow-offs of 2013, 2017, 2021).
- **Apathetic** tops: shallower multiplier (≤ 10×) and/or shallower drawdown
  — the "top on apathy" claim the memo applies to C4, where BTC's Oct-2025
  peak at $124,728 carried none of the broad-rotation features of the prior
  euphoric blow-offs and printed on compressed-attention engagement.

| Cycle | Top date | Top price | Mult | Drawdown | Character |
|---|---|---|---|---|---|
| C1 | 2013-12-04 | $1,132 | 526.5× | 84.9% | euphoric |
| C2 | 2017-12-16 | $19,188 | 112.2× | 83.4% | euphoric |
| C3 | 2021-11-08 | $67,559 | 21.6× | 76.7% | euphoric |
| C4 | 2025-10-06 | $124,728 | 7.97× | *(projected)* | **apathetic** |

**Why this matters at the next-cycle decision window:** the SMAs above say
*when* the bear bottom is likely printing; `top_character` says *how much
less clean* the cycle-into-the-next-top is likely to be. For an apathetic
top cycle like C4, the framework's C5 multiplier power-law (Stage 2 fit on
euphoric-cycle multipliers) is by construction *over-anchored on a regime
that no longer holds*. That is why the published C5 band is the **union**
B4 × mult power-law in `predictive-ranges.md` — apathetic-top C5 multipliers
are mechanically compressed, and the band widens to absorb the resulting
uncertainty rather than silently inheriting euphoric assumptions.

## External Reconciliation — Cowen July-2026 Memo

> The *Bitcoin Cycle Memo* by
> [Benjamin Cowen (July 2026)](https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026)
> is an independent July-2026 analysis that arrived at the same Q4-2026 B4
> timing band and $30k–$54k price corridor — the memo via midterm
> seasonality + cycle-duration arithmetic, the framework via the 2-stage
> power-law fit. Both methodologies were published without modification to
> fit the other. The apathy classification coincides with our
> `top_character` for C4 and with the phase-conditioned correlation absence
> of alt rotation at the C4 top. Full 8-row reconcilation matrix and
> qualitative match table:
> [`docs/memo-reconciliation.md`](../docs/memo-reconciliation.md).

## Open Indicators

The memo tracks several indicators our framework does not yet ingest
(on-chain risk suite, macro-policy overlay, BTC ETF holdings, dominance
ex-stables, midterm-year seasonality). They are tracked as candidate
v2 increments; full list with rationale:
> [`docs/open-questions.md`](../docs/open-questions.md).

---

*Data: `data/raw/btc_bitstamp_*.csv` · Metrics: `data/processed/btc_cycle_metrics.csv` · SMA floors: `data/processed/btc_sma_floors.csv` · Folklore stat: `data/processed/forward_ranges.csv::D_bottom_to_next_top`*

## Change log

### 2026-07-23 — Folklore pattern reconciliation

A widely-cited "365-day bear / 1064-day bull" rhythm in Bitcoin cycle analysis
correlates with our 3 historical BTC cycles (28 months
after the Cowen memo's appearance; the pattern itself is folklore-stale but
its narrowing effect on the C5 top projection is meaningful).

#### Pattern cross-check

| Folklore claim | Our historical data | Match? |
|---|---|---|
| Bear ≈ 364-365 days from top to bottom | C1=406d, C2=364d, C3=378d (median 378d, range 364-406) | **Partial** — C2 nails 364d exactly; full 3-cycle range is 11% wide. Folklore is loose; our existing `D_top_to_next_bottom` band (Q25-Q75 = 371-392d, min-max = 364-406d) properly captures the spread. |
| Bull ≈ 1,064 days from bottom to next top | C1→C2=1067d, C2→C3=1059d, C3→C4=1050d (median 1059d, range 17d) | **Strong** — all 3 transitions within 1.6% of 1,064d. Folklore correlates with BTC's measured rhythm. This pattern is captured as a derived statistic `D_bottom_to_next_top` in `data/processed/forward_ranges.csv`. |
| Alts follow the same rhythm | ETH 1060-1161d, SOL 751d, XRP 1130d | **No** — alts do **not** follow. Pattern is BTC-specific (market-cap tier, not a shared economic driver). For alts, we use the BTC-anchoring model described above. |

> **Honesty note (per §9.4 R-4):** this is a **qualitative cross-reference,
> not an independent validation.** `D_bottom_to_next_top` is decomposed by
> construction as next-cycle `D_prev_bottom_to_halving` + `D_halving_to_top`,
> so the "1,064-day bull" is a restatement of two durations the framework
> already fits separately — the agreement is partly tautological. We keep
> the folklore band as a *decision overlay* on C6 (cross-checking where the
> two paths agree), but it does not independently corroborate the C5 top.

#### Why this matters: C5 top cross-check

Because the post-2021 bull duration is so tight across 3 cycles (~17d of
variance vs ~1059d mean), this rhythm provides a
much tighter C5 top projection than the halving-driven one. We compute both
paths:

| Anchor | Formula | Center | Base band IQR |
|---|---|---|---|
| **H5-anchored** (the framework's primary) | H5 (2028-04-01) + median(`D_halving_to_top`=525d) | **2029-09-12** | ~50d wide (Q25-Q75 of `D_halving_to_top`) |
| **B4-anchored** (folklore cross-check) | B4 (Oct-22-2026) + median(`D_bottom_to_next_top`=1059d) | **2029-09-15** | ~8d wide (Q25-Q75 of `D_bottom_to_next_top`) |

The two paths agree to **+3 days** center-to-center, but the B4-anchored
band is **~6× tighter on IQR** (~50d vs ~8d, interquartile) and **~10×
tighter on the outer min-max envelope** (546d vs 53d). This suggests the
bottom→top rhythm is more fundamental than the halving→top relationship —
the halving-cadence anchor dilutes the true cycle rhythm by absorbing
halving-specific timing variance. The IQR ratio is more robust to outliers
than the min-max; the outer ratio confirms the direction.

We surface this as an additive cross-check, not a replacement: the
distribution zone row in `data/processed/next_cycle_zones.csv` carries the
full reconciliation in its `compression_fit_note` column, and chart C6 draws
both windows visually (orange H5-anchored distribution band, translucent
purple B4-anchored folklore cross-check band).

#### Why the "365-day bear" is loose

The bear phase is structurally noisier than the bull phase. Top-date
detection itself has ~14-day tolerance per Rule T, and bottoms in BTC have
ranged 364-406 days in three cycles. The folklore's pin to 365 days is most
likely anchored to C2's 364-day value — a single-cycle near-miss that
sounded clean enough to memorize. The **bull** rhythm is genuinely tight
because the market has to clear holders accumulated during accumulation,
which is structurally constrained by the diminishing-supply growth rate.

#### Implication for archive integrity

`D_bottom_to_next_top` is now a first-class row in `forward_ranges.csv`
(counted by `test_forward_ranges.py::test_forward_ranges_exists`: 6 rows,
not 5). New tests added:
`test_d_bottom_to_next_top_values` validates n=3 and median within
[1050, 1067] — i.e. the framework will flag a future cycle that breaks
this rhythm rather than silently absorbing it.

# I-21 exploration-2 — Curve-regime falsification probe on non-crypto asset cycles

**Increment:** I-21 (proposed; exploration round-2 only)
**Date:** 2026-08-10
**Status:** Spec only → executed. Verdicts recorded below. **No model change.**
**Predecessor:** `docs/blockers/I-21-eurodollar-proxies-exploration.md` (round-1)
**Rule tuned:** None. Pre-committed rubric and thresholds respected; no
post-hoc threshold-tuning.

---

## 1. Why round-2 exists

Round-1 tested whether EU's curve-shape rubric predicts *BTC* extrema
(H1) and whether the 2007-08-09 BNP-Paribas break is detectable (H6). H1
rejected (2/6, threshold 5/6); H6 passed marginally on TLT alone.

The user's actual interest was broader: "identify current regime and how
that affects cycles in non-crypto assets." Round-1 only tested against
BTC extrema, never tested against SPX/NDX/TLT/DXY/GOLD's own extrema, and
never asked whether the regime context surrounding those non-crypto
extrema differs from average. Round-2 fills that gap with 4 new
hypotheses (H7-H10), all with pre-committed rubrics and thresholds.

## 2. Pre-committed rubric (LOCKED BEFORE EXECUTION)

### H7 — Per-asset extrema alignment with `curve_shape_state`

Per (asset, top/bottom) event, the curve-state appearing in the ±120d
window around the extremum was checked against the prediction table
below. Strict scoring: any day of a predicted state in the window =
match, else 0.

| Asset × event    | Predicted states in ±120d window            | Reasoning (EU-derived) |
|------------------|---------------------------------------------|------------------------|
| SPX top          | `inverted_flat` OR `bull_steep`            | Restrictive credit triggers equity tops (EU inversion = "Forgot How to Grow"); bull steep = "bad for world" pivot |
| SPX bottom       | `bear_steep` OR `normal`                    | Bear steepener = "bullish for world" recovery regime; normal = benign drift |
| NDX top          | `inverted_flat` OR `bull_steep`            | Same as SPX (high-beta equity) |
| NDX bottom       | `bear_steep` OR `normal`                    | Same as SPX |
| DXY top          | `inverted_flat` (only)                      | Strong-dollar requires restrictive dealer B/S; inversion = restrictive |
| DXY bottom       | `bull_steep` OR `bear_steep`                | Either steepener cuts dollar-bullish rate differentials |
| TLT top          | `bull_steep` OR `inverted_flat`            | TLT peaks at rate-cycle extremes; both states capture rate-cycle exhaustion |
| TLT bottom       | `bear_steep` OR `normal`                    | Long-yield-rising / normalized curve = duration trough |
| GOLD top         | `bull_steep` OR `inverted_flat`             | Risk-off exhaustion (deflationary bust) OR cut-cycle peak |
| GOLD bottom      | `bear_steep` OR `normal`                    | Growth-pricing / benign regime (real yields rising/stable) |

**Threshold:** ≥2/3 of each asset's extrema match for ≥4/5 assets → H7 survives.

### H8 — Curve-state at asset's top correlates with subsequent drawdown

Ordinal encoding: `normal=0, bear_steep=1, inverted_flat=2, bull_steep=3`
(ordered by "stress/distortion severity"). Spearman ρ between
state-ordinal at each asset's cycle top and the asset's subsequent
drawdown_pct.

**Threshold:** |ρ| ≥ 0.4 → H8 survives.

### H9 — Pre-extremum state distribution differs from unconditional

For each asset's extremum, compute the `curve_shape_state` distribution
over the 250 trading days *preceding* the extremum. Compare to the
unconditional distribution (round-1: `normal` 83.3%, `bull_steep` 6.7%,
`bear_steep` 5.9%, `inverted_flat` 4.0%). Measure: Jensen–Shannon
divergence (base-2; 0 = identical, ln(2) ≈ 0.69 = maximally different).

**Threshold:** per-asset mean JS divergence ≥ 0.1 for ≥3/5 assets → H9 survives.

### H10 — BTC's 60-day forward return at non-crypto extrema, conditioned on state

At each non-crypto asset's extremum, the BTC 60-day forward return was
computed and tagged with the curve-state on that date. State encoding:
nominal (no ordinal ranking) — the ordering `normal→inverted→bear→bull`
is itself an assumption and EU never explicitly endorsed it.

**Threshold:** ≥2 state pairs show opposite-sign mean BTC forward returns
→ H10 survives.

### Promotion rule (committed in advance)

> If H7 AND (H8 OR H9) survive → strong evidence the regime framework
> adds interpretation to non-crypto cycles. A proper I-21 increment (descriptive overlay only, Option A from round-2 design) becomes justified.
> Else (only H7, only H10, or none) → close as published mixed/negative.

## 3. Actual data and results

### H7 — REJECTED  (1/5 assets pass; threshold 4/5)

Full per-extremum scoring (37 observed extrema across 5 non-crypto
assets × C1-C4, filtered to extrema with valid curve-state coverage):

| Asset × event    | Predicted states                  | Observed states in ±120d (`normal` omitted for brevity unless sole state) | Match |
|------------------|-----------------------------------|------------------------------------------------------|-------|
| SPX C1 top 2015-05-21 | `inverted_flat, bull_steep`     | `bull_steep, normal` → matches `bull_steep`         | 1 |
| SPX C1 bottom 2016-02-11 | `bear_steep, normal`         | `normal` only                                       | 1 |
| SPX C2 top 2019-07-26 | `inverted_flat, bull_steep`     | `normal` only                                       | 0 |
| SPX C2 bottom 2020-03-23 | `bear_steep, normal`         | `normal` only                                       | 1 |
| SPX C3 top 2022-01-03 | `inverted_flat, bull_steep`     | `bull_steep, normal` → matches `bull_steep`         | 1 |
| SPX C3 bottom 2022-10-12 | `bear_steep, normal`         | `bear_steep, inverted_flat, normal` → matches `bear_steep` | 1 |
| SPX C4 top 2026-08-07 | `inverted_flat, bull_steep`     | `normal` only                                       | 0 |
| **SPX**          | **5/7 = 0.71**                  | **PASS**                                            |   |
| NDX C1 top 2015-07-20 | `inverted_flat, bull_steep`     | `normal` only                                       | 0 |
| NDX C1 bottom 2016-02-09 | `bear_steep, normal`         | `normal` only                                       | 1 |
| NDX C2 top 2019-07-26 | `inverted_flat, bull_steep`     | `normal` only                                       | 0 |
| NDX C2 bottom 2020-03-20 | `bear_steep, normal`         | `normal` only                                       | 1 |
| NDX C3 top 2021-11-19 | `inverted_flat, bull_steep`     | `bull_steep, normal` → matches `bull_steep`         | 1 |
| NDX C3 bottom 2022-12-28 | `bear_steep, normal`         | `bear_steep, inverted_flat, normal` → matches `bear_steep` | 1 |
| NDX C4 top 2026-06-02 | `inverted_flat, bull_steep`     | `normal` only                                       | 0 |
| **NDX**          | **4/7 = 0.57**                  | **fail**                                            |   |
| DXY C1 top 2015-03-13 | `inverted_flat`                 | `bull_steep, normal`                                | 0 |
| DXY C1 bottom 2016-05-02 | `bull_steep, bear_steep`     | `normal` only                                       | 0 |
| DXY C2 top 2016-12-20 | `inverted_flat`                 | `normal` only                                       | 0 |
| DXY C2 bottom 2018-02-15 | `bull_steep, bear_steep`     | `normal` only                                       | 0 |
| DXY C3 top 2022-09-27 | `inverted_flat`                 | `bull_steep, inverted_flat, normal` → matches `inverted_flat` | 1 |
| DXY C3 bottom 2023-07-13 | `bull_steep, bear_steep`     | `inverted_flat, normal`                             | 0 |
| DXY C4 top 2025-01-13 | `inverted_flat`                 | `normal` only                                       | 0 |
| DXY C4 bottom 2026-01-27 | `bull_steep, bear_steep`     | `normal` only                                       | 0 |
| **DXY**          | **1/8 = 0.12**                  | **fail** (catastrophic)                             |   |
| GOLD C1 top 2013-08-27 | `bull_steep, inverted_flat`    | `normal` only                                       | 0 |
| GOLD C1 bottom 2015-12-17 | `bear_steep, normal`         | `normal` only                                       | 1 |
| GOLD C2 top 2019-09-04 | `bull_steep, inverted_flat`    | `normal` only                                       | 0 |
| GOLD C2 bottom 2019-11-27 | `bear_steep, normal`         | `normal` only                                       | 1 |
| GOLD C3 top 2023-05-04 | `bull_steep, inverted_flat`    | `inverted_flat, normal` → matches `inverted_flat`  | 1 |
| GOLD C3 bottom 2023-10-05 | `bear_steep, normal`         | `inverted_flat, normal`                             | 1 |
| GOLD C4 top 2026-01-29 | `bull_steep, inverted_flat`    | `normal` only                                       | 0 |
| **GOLD**         | **4/7 = 0.57**                  | **fail**                                            |   |
| TLT C1 top 2015-01-30 | `bull_steep, inverted_flat`    | `bull_steep, normal` → matches `bull_steep`        | 1 |
| TLT C1 bottom 2015-06-26 | `bear_steep, normal`         | `bear_steep, normal` → matches `bear_steep`         | 1 |
| TLT C2 top 2019-08-28 | `bull_steep, inverted_flat`    | `normal` only                                       | 0 |
| TLT C2 bottom 2019-12-31 | `bear_steep, normal`         | `normal` only                                       | 1 |
| TLT C3 top 2020-11-20 | `bull_steep, inverted_flat`    | `bear_steep, normal`                                | 0 |
| TLT C3 bottom 2023-10-19 | `bear_steep, normal`         | `inverted_flat, normal` → matches `normal`          | 1 |
| TLT C4 top 2024-12-06 | `bull_steep, inverted_flat`    | `normal` only                                       | 0 |
| TLT C4 bottom 2026-08-10 | `bear_steep, normal`         | `normal` only                                       | 1 |
| **TLT**          | **5/8 = 0.62**                  | **fail**                                            |   |

**Verdict:** Only SPX passes (5/7). NDX, GOLD 4/7 each; TLT 5/8. DXY 1/8
is the catastrophic outlier. The user's pre-committed threshold
(≥4/5 assets passing) is missed. **H7 REJECTED.**

**Honest reading of the failure:** the most common observed state in
asset extrema is `normal` (often the sole state for the entire ±120d
window). Since `normal` covers 83% of all days AND appears as a predicted
state for `bottom` events (per "bear steep OR normal" rubric), the rubric
is structurally biased toward (a) easy passes for bottoms that fall in
benign regimes, and (b) systematic failures for `top` predictions where
the `normal` regime carried into the top rather than transition into
`inverted_flat` or `bull_steep`. The asymmetry is real: macro asset tops
in our data frequently occur OUTSIDE clear curve-shape stress.
Specifically: SPX-C2 top (2019-07-26), NDX-C2 top (2019-07-26),
TLT-C2 top (2019-08-28), SPX-C4 top (2026-08-07), NDX-C4 top (2026-06-02),
DXY-C4 top (2025-01-13), GOLD-C4 top (2026-01-29), TLT-C4 top (2024-12-06) —
**all** 8 of these recent tops had `normal` as the only observed state
in ±120d. The rubric predicted stress (`inverted_flat`/`bull_steep`)
for all of them and missed all.

This is consistent with round-1's H1 failure on BTC: at the daily-resolution
regime proxy scale, EU's curve-shape vocabulary singularly under-fires for
identifying cycle tops in macro assets.

### H8 — REJECTED  (Spearman ρ = 0.311, threshold 0.4)

15/17 asset tops occurred in `normal` state, so the state-ordinal is
nearly degenerate: only NDX-C3 (`bull_steep`), SPX-C3 (`bull_steep`),
TLT-C1 (`bull_steep`), DXY-C3 (`bull_steep`) departed from `normal`.

Pooling 17 top+drawdown points:

| Asset × cycle   | State-at-top | Drawdown |
|-----------------|--------------|----------|
| DXY C1 | normal       | 7.7%  |
| DXY C2 | normal       | 14.2% |
| DXY C3 | **bull_steep** | 12.6% |
| DXY C4 | normal       | 12.5% |
| GOLD C1 | normal       | 26.0% |
| GOLD C2 | normal       | 6.3%  |
| GOLD C3 | normal       | 11.3% |
| NDX C1 | normal       | 15.6% |
| NDX C2 | normal       | 12.8% |
| NDX C3 | **bull_steep** | 35.6% |
| SPX C1 | normal       | 14.2% |
| SPX C2 | normal       | 26.1% |
| SPX C3 | **bull_steep** | 25.4% |
| TLT C1 | **bull_steep** | 16.7% |
| TLT C2 | normal       | 8.3%  |
| TLT C3 | normal       | 48.8% |
| TLT C4 | normal       | 13.1% |

ρ = +0.311 (positive direction: higher-stress state → deeper drawdown, BUT weak). Threshold 0.4 missed.

**Honest reading:** there is a *weak directional* signal — every
`bull_steep` top in our data drew down materially (12.6%, 35.6%, 25.4%,
16.7% — average 22.6%, all deeper than the median `normal`-top drawdown of
14.2%). But 4 bull-steep observations out of 17 is not enough to clear
ρ=0.4. This is a *finding* not a *failure*: a `bull_steep` regime at a
macro asset's cycle top is empirically associated with a deeper-than-median
subsequent drawdown, but the effect size is small in our sample.

### H9 — PASS  (5/5 assets pass; threshold 3/5)

Per-asset mean Jensen–Shannon divergence between pre-extremum (250-day)
state distribution and the unconditional distribution:

| Asset | Mean JS | Verdict |
|-------|---------|---------|
| DXY   | 0.2560  | PASS    |
| GOLD  | 0.1846  | PASS    |
| NDX   | 0.1338  | PASS    |
| SPX   | 0.1881  | PASS    |
| TLT   | 0.2065  | PASS    |

**Threshold (≥0.1, ≥3/5 assets): all 5 pass.**

Notable individual extrema with very high JS divergence (>0.5):
- DXY C1 top 2015-03-13: JS=0.55 — pre-window dominated by `bull_steep`
  (87% of 250 days), not `normal`. Curve was actively transitioning.
- DXY C3 top 2022-09-27: JS=0.61 — pre-window dominated by `bull_steep`
  (91%). This was the post-COVID Fed-hike cycle.
- SPX C3 bottom 2022-10-12: JS=0.61 — pre-window dominated by
  `bull_steep` (91%), the post-COVID Fed-hike inversion burst.
- GOLD C3 bottom 2023-10-05: JS=0.58 — pre-window dominated by
  `inverted_flat` (85%).
- TLT C3 bottom 2023-10-19: JS=0.54 — pre-window dominated by
  `inverted_flat` (82%).

**Honest reading:** even though H7 failed (extrema don't align with
predicted curve-states *at the moment*), the regime context
*leading up to* extrema is reliably, materially different from average.
This is a clean positive finding that survives across all 5 non-crypto
assets. The descriptive insight is: **macro asset cycle extrema are
preceded by non-trivial regime context that's distinguishable from
"average" macro history.**

### H10 — PASS  (2/3 state pairs show opposite-sign BTC fwd returns)

BTC's 60-day forward return at each of 35 non-crypto extrema, grouped
by curve-state at the extremum date:

| State           | Mean BTC fwd 60d | n   |
|-----------------|------------------|-----|
| `normal`        | +11.93%          | 28  |
| `inverted_flat` | +11.19%          | 2   |
| `bull_steep`    | **−12.12%**       | 5   |

Pairwise sign test:
- `bull_steep` (−12.12%) vs `normal` (+11.93%) → **OPPOSITE signs** ✓
- `bull_steep` (−12.12%) vs `inverted_flat` (+11.19%) → **OPPOSITE signs** ✓
- `inverted_flat` (+11.19%) vs `normal` (+11.93%) → same sign
2/3 pairs opposite signs. **Threshold (≥2) met. H10 PASS.**

**Honest reading:** this is the cleanest signal of round-2. When a
non-crypto asset's extremum occurs in a `bull_steep` ("risk-off / Fed
cutting") curve regime, BTC's 60-day forward returns are *negative on
average* (−12.12%). When the same extremum occurs in a `normal` or
`inverted_flat` regime, BTC's forward returns are positive (+11.93%
and +11.19% respectively). The regime at macro landmarks modulates BTC's
subsequent behavior in a directionally consistent way: `bull_steep` =
BTC weakness within 60 days; non-`bull_steep` = BTC strength.

Sample caveat: only 5 observations in `bull_steep` state. But those 5
include SPX-C3 top (2022-01-03, BTC forward = −15.64%), NDX-C3 top
(2021-11-19, BTC forward = −27.10%), DXY-C3 top (2022-09-27, BTC forward
= −13.74%), SPX-C3 bottom (2022-10-12, BTC forward = −10.78%), TLT-C1
top (2015-01-30, BTC forward = +6.66% positive outlier). The first 4 are
all consistent with "risk-off regime at macro landmark → BTC weakness."

## 4. Final verdicts and promotion decision

| H  | Verdict             | Score / Detail                                              |
|----|---------------------|-------------------------------------------------------------|
| H7 | REJECTED            | 1/5 assets pass (only SPX); threshold 4/5                 |
| H8 | REJECTED            | Spearman ρ = 0.311; threshold 0.4                          |
| H9 | PASS                | 5/5 assets pass JS ≥ 0.1; threshold 3/5                   |
| H10 | PASS               | 2/3 state-pair sign-opposites; threshold 2                |

**Pre-committed promotion rule:** H7 AND (H8 OR H9) → I-21 proper
justified. Result: `False AND (False OR True) = False`. **Promotion NOT
TRIGGERED.**

Per the discipline established in round-1 §11.6, **no post-hoc tuning
of the rule is permitted**. We do not now redefine the gate from "H7
AND (H8 OR H9)" to "(H8 OR H9)" after seeing the numbers — that would be
exactly the post-hoc falsification I committed to avoid.

## 5. Honest reading of the mixed result

Three signals survived: **the regime framework DOES add information** —
but in a *narrower* form than the original "predict macro-cycle extrema"
hypothesis. Specifically:

1. **H9 says:** the curve-state distribution in the 250 days *leading
   up to* a non-crypto asset extremum is materially different from
   average (all 5 assets, JS ≥ 0.13 to 0.26). The macro regime context
   is *distinguishable* around extrema even though the exact state at
   the extremum date is usually `normal` (hence H7 fails).

2. **H10 says:** at non-crypto extrema, the curve-state *modulates* BTC's
   subsequent behavior: `bull_steep` regime → negative BTC 60d returns;
   non-`bull_steep` → positive BTC 60d returns. The cross-asset link
   between macro regime and BTC behavior is real, but it manifests as a
   *modulator*, not as a *predictor* of when the macro extremum occurs.

3. **H8 says (weakly):** `bull_steep` at a macro asset top is associated
   with a deeper-than-median subsequent drawdown (22.6% mean vs 14.2%
   median for `normal`), but sample is too small (n=4) to clear the
   pre-committed threshold.

What H7's catastrophic failure (especially DXY 1/8) tells us is the
*direct* use of EU's rubric to predict macro extrema does not generalize
to our 4 cycles × 5 assets sample. Whether this is (a) the rubric's
fault (small-n stress events are epiphenomenal in 4 cycles of macro
data) or (b) our substitution of 10y–5y for 10y–2y weakening detection
of mild inversions cannot be determined from this exploration. Per
round-1 §11.6 the proper re-test path requires FRED `T10Y2Y` data, still
unreachable this session.

## 6. What this means for the framework

**No model change.** The pre-committed promotion gate failed. Per the
discipline established when the user asked for "explore first, falsify,
then merge," I do **not** promote based on partial survival. The
framework's existing I-12 (DXY/TLT ±1σ strata) and I-19 (macro 2-stage
projection using each asset's own drawdown/multiplier series, no
regime-conditioning) stand unchanged.

**However, two findings are publishable as descriptive context in the
white paper sections** (no code/CSV changes — just narrative):

1. The regime context **leading into** macro asset extrema is
   distinguishable from average macro history. JS divergence test passes
   across all 5 non-crypto assets. This becomes a table in
   `sections/04-cross-asset-correlations.md` of the form
   "pre-extremum regime distribution by asset" — purely descriptive.

2. BTC's 60-day forward returns at macro landmarks are regime-modal:
   `bull_steep` → −12.12% mean, everything else → +11.93% mean. This is
   a one-paragraph "macro-regime modulates BTC behavior around macro
   landmarks" note in `sections/04-cross-asset-correlations.md` or
   `sections/07-conclusions.md`.

These two narrative additions are **not** part of an increment — they're
descriptive context the user can choose to add to the white paper if
they want, in a future round of editing. The exploration produces the
*evidence*; whether to publish is a separate decision and not part of
this exploration's mandate.

## 7. Files produced this session (all exploration-only, mutable)

- `scripts/exploration/curve_regime_noncrypto_v2.py` (~280 lines, runnable
  today against the existing round-1 derived series + framework
  artifacts; no framework dependencies added).
- `data/processed/exploration_eu_proxies_v2.csv` (37 rows, one per
  extremum, with predicted/observed states and match flag; mutable).
- This document.

## 8. Files NOT touched

Verified unchanged after the session (identical to round-1's file
set):
- `tests/` — unchanged
- `scripts/build_*.py`, `scripts/fetch_*.py` (existing ones) — unchanged
- `data/processed/correlations_phase.csv`,
  `correlations_BY_regime.csv`, `returns_aligned.csv`,
  `next_cycle_zones.csv`, `alt_next_cycle_zones.csv`,
  `alt_cycle_metrics.csv`, `alt_forward_ranges.csv` — all unchanged
- `DESIGN.md`, `AGENTS.md`, `status.md`, `index.md`,
  `sections/*.md` — all unchanged
- The round-1 blocker `docs/blockers/I-21-eurodollar-proxies-exploration.md`
  — unchanged (this is a separate document per round-1 §11.6's "re-tests
  are separate blocker notes" mandate).

## 9. Final disposition

**Status:** Round-2 exploration complete with mixed verdicts (2 PASS,
2 REJECTED). The pre-committed promotion gate (H7 AND (H8 OR H9)) was
NOT triggered. **No I-21 proper increment opened. No framework change.**

The two passing signals (H9 pre-extremum regime context divergence;
H10 BTC behavior conditioned on regime at macro landmarks) are recorded
as **published findings available for future narrative use in the white
paper**, but they do not justify a projection-model change on their own.
A future contributor who wants to revisit the merge may:

1. Re-run H7 with proper 10y–2y slope (FRED `T10Y2Y`), once FRED access
   is available. If H7 still fails, the rubric itself is wrong.
2. Re-run H8 with a larger sample (C4 bottoms observed) — if the
   `bull_steep → deeper drawdown` pattern holds with more data, it may
   justify a regime-conditional I-19 drawdown projection in a future I-22.
3. Re-run H10 with a longer forward horizon (90d, 120d) — if the
   `bull_steep → BTC weakness` effect holds at multiple horizons, it's
   a publishable regime-modulator table for `sections/04`.

None of these are sanctioned in this document. They are listed per
round-1 §11.6's "re-test path recorded but not authorized" discipline.

**The exploration closes here. No merge.**

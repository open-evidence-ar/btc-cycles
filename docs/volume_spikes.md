# Volume-spike proximity to cycle extrema — Phase A exploration

**Date:** 2026-11-15 (five passes: nearest-spike, bear-leg dominant spike,
flush-cluster rule, C4 zone overlap, direction/absolute reanalysis) ·
**Scripts:** `scripts/explore_volume_spikes.py` (P1),
`scripts/explore_bear_leg_spikes.py` (P2),
`scripts/explore_volume_clusters.py` (P3),
`scripts/explore_volume_reanalysis.py` (P5) — read-only, rerunnable ·
**Status:** exploration, not an increment. Nothing in the pipeline, schemas,
or charts was changed. Phase B (an I-23 increment) is a separate decision.

## Question

Does a volume spike occur close to cycle tops (and bottoms)? If so: **how
close** (proximity), **how big** (magnitude), **how long** (duration) — and is
the pattern **stable** across cycles, or a folklore that dissolves under
measurement? This is the same discipline applied to the halving-anchor premise
in I-19 (`scripts/check_cycle_tie.py`): turn the claim into a number.

## Data and method

**Series.** Per-asset merged volume from the same raw snapshots the price
series uses (`build_alt_cycle_metrics.load_asset` contract: stable sort,
later source wins). Assets: btc (Bitstamp), eth/xrp/sol (CDD→Yahoo), mstr/wgmi
(Yahoo). riot/mara excluded (proxy sources per AGENTS.md). DXY and GOLD are
excluded **by data**: their Yahoo volume is literally 0.0; yields have no
volume concept.

**Source-seam audit (required, not optional).** CDD vs Yahoo magnitudes are not
comparable — measured ratio drifts ~100x over 8 years (CDD's late-era volume is
a shrinking subset). The script detects every winning-source transition and its
30d median scale step: **eth 2017-11-09 ×7,384; xrp 2017-11-09 ×5; sol 2025-10-16
×0.75 (benign); btc/mstr/wgmi single-source.** Any extremum within ±30d of a >2x
step would be excluded (fabricated-spike risk); none fell inside one. The one
extremum whose trailing baseline straddles the eth seam (eth C2 top, 65d after)
survives with a *deflated* z (bimodal baseline inflates σ) — if anything its
hit is understated.

**Anchors.** The canonical extrema already published in
`btc_cycle_metrics.csv` / `alt_cycle_metrics.csv` — no re-detection, so the
test stays non-circular (volume proximity measured against price-defined tops).
C4 tops labelled `observed`; C4 bottoms labelled `provisional_low_to_date`
(a running minimum that can only fall). WGMI's C1–C3 are MARA proxy extrema
predating WGMI's own 2022 volume series and drop out on the coverage rule.

**Detectors (four families, so no conclusion can be an artefact of one):**
raw-volume z vs trailing 90-day baseline excluding self (z ≥ 2/3/4); the same z
on log1p(volume) (heavy-tail-robust); a climax proxy (z on volume × |daily
return|); and percentile-of-cycle (top 1% / 2% of the cycle's own volume —
independent of any baseline choice). Hit windows ±7/±14/±30 **calendar days**
(rows would silently widen ±40% for the equities). Chance baseline:
permutation — 10,000 draws of uniform random days inside each extremum's own
cycle window, same detector, same ±k window, fixed seed (paired across
detectors); p = P(random ≥ observed).

## Sample (the whole universe of evidence)

| asset | volume span | tops | bottoms | notes |
|---|---|---|---|---|
| btc | 2011-08 → | 4 | 4 (B4 prov.) | Bitstamp, single source |
| eth | 2016-03 → | 3 | 3 (B4 prov.) | C2 hit survives seam-deflated baseline |
| xrp | 2017-05 → | 2 | 2 (B4 prov.) | C1/C2 absent (data start) |
| sol | 2020-04 → | 2 | 2 (B4 prov.) | C1/C2 absent |
| mstr | 1998-06 → | 2 | 2 (B4 prov.) | |
| wgmi | 2022-02 → | 1 | 2 (B4 prov.) | C1–C3 are MARA proxy, pre-volume |
| **total** | | **14** | **15** | |

## Result 1 — TOPS: the pattern is real in this sample

Every detector family agrees (all ten at p < 0.10; the baseline-free
percentile detectors at p ≈ 0.000):

| detector | n | hit ±14d | random ±14d | p@14 | lag median (IQR) | magnitude median |
|---|---|---|---|---|---|---|
| z-raw ≥3 | 14 | **79%** (11/14) | 65% | **0.002** | **0d** (−4..+1) | **4.4x** |
| climax ≥4 | 14 | 79% | 51% | 0.001 | 0d (−4..+1) | 4.7x |
| top-2% of cycle | 14 | 79% | 45% | **0.000** | 0d (0..+1) | 4.3x |
| top-1% of cycle | 14 | 64% | 26% | 0.000 | 0d (0..+1) | 4.4x |

Per-extremum, z-raw ≥3 (lag = extremum − spike; negative = spike precedes top):

```
btc  C1  2013-12-04  −3d  4.4x    eth  C2  2018-01-13  +3d  7.6x
btc  C2  2017-12-16  −6d  4.4x    eth  C3  2021-11-08  −26d 2.1x
btc  C3  2021-11-08  −10d 2.9x    eth  C4  2025-08-22   0d  2.9x
btc  C4  2025-10-06  −4d  3.2x    xrp  C3  2021-04-14  +1d  5.6x
                                  xrp  C4  2025-07-21  +3d  6.0x
mstr C3  2021-02-09  miss         sol  C3  2021-11-06  miss
mstr C4  2024-11-20   0d  4.3x    sol  C4  2025-01-18   0d  5.6x
wgmi C4  2026-06-18  +13d 4.3x
```

Answers to the three questions, for tops:

- **Proximity:** the spike *is* the top window — median lag 0 days, IQR
  −4..+1. It is a top-day/next-few-days event, not an early warning. BTC is
  the exception that leads: all four BTC spikes precede the top by 3–10 days.
- **Magnitude:** median ~4.4x the trailing 90-day median volume (range
  2.1x–7.6x across hits). A z ≥ 3 day near the top is typically a 3–5x day.
- **Duration:** a burst, not a season — median 3 elevated days within ±30d
  (median 2.5 for BTC). Do not expect weeks of distribution volume.
- **Stability:** 5/8 confirmed-era tops, **6/6 observed-C4 tops** (2024–2026,
  every asset). The pattern is perfect in the current cycle and majority
  historically; 79% overall against a 45–65% chance baseline.

## Result 2 — BOTTOMS: the capitulation-volume folklore is not stable

No detector is significant (p ranges 0.11–1.00; z-log ≥4 finds literally 0/15).
Hit rates sit at or below the random-day baseline:

| detector | n | hit ±14d | random ±14d | p@14 |
|---|---|---|---|---|
| z-raw ≥3 | 15 | 40% | 65% | 0.465 |
| climax ≥3 | 15 | 60% | 64% | 0.139 |
| top-2% of cycle | 15 | 20% | 45% | 0.586 |

Sporadic giants exist — btc B1 printed 12.9x *at* the low, wgmi B3 8.3x,
btc B2 6.5x — but xrp B3/B4, sol B3/B4 and mstr B3 have **no** z ≥ 3 day within
±30d at all. The classic "capitulation spike marks the bear bottom" pattern
does not survive as a stable rule in 15 observations. (Caveat: five of the 15
bottoms are provisional lows-to-date; a lower low tomorrow re-dates them. But
the misses are not near-misses — they are zeros across every detector.)

## Result 3 — Perspective 2: the bear leg's dominant spike vs the final bottom

Second pass, reframed the way the model's windows of attention work: forget
"any spike near the bottom." In the down move (cycle top → final bottom), is
there a *single clearly dominant* volume spike — and does the final bottom land
at a stable distance from it (two weeks, one month, ±% of the leg)? Script:
`scripts/explore_bear_leg_spikes.py`. Legs = top → bottom (+60d tail; open
provisional legs run to the last data date). Dominant spike picked three ways:
raw max (`dmax`), max baseline-aware z (`dz`), max climax (`dclim`). Fairness:
permutation p against uniform random days *inside the same leg domain* (the
±60d hit rate is partly mechanical — the leg includes a +60d post-bottom tail —
so the raw hit rate alone cannot be cited).

### The biggest RAW volume day is top-anchored — ABSENT

On confirmed legs the raw max sits median **+271d before** the bottom (it is
the top-era frenzy, often the top day itself — xrp C3, sol C4 +1d, mstr C4 +1d,
eth C2 +4d after their tops). The bottom lands within ±30d of it **0/8 times**
(vs 14% random) — the bottom *systematically avoids* the volume maximum. No
window, dominance weak (median 1.25).

### The biggest BASELINE-AWARE spike clusters at the leg's end — CONFIRMED on closed legs

| detector | confirmed n | within ±30d | within ±60d | p@30 | p@60 | lag median | lag IQR |
|---|---|---|---|---|---|---|---|
| dz | 8 | 4/8 (50%) | **8/8 (100%)** | 0.016 | **0.000** | **+31d** | +9..+41 |
| dclim | 8 | 3/8 (38%) | 7/8 (88%) | 0.092 | 0.001 | +34d | +11..+51 |

- **Lags (dz, confirmed):** btc B1 **+0d** (spike *is* the low day, 12.9x),
  btc B2 +25, btc B3 +13, eth B2 −10, eth B3 +38, xrp B3 +38, sol B3 +51,
  mstr B3 +51. Every confirmed final bottom within ±51d of its leg's dominant
  z-spike.
- **The dates are the famous capitulations:** 2022-05-11 (LUNA collapse) is
  eth's and xrp's dominant spike; 2022-11-08 (FTX flush) is btc C3's, sol C3's
  and mstr C3's; 2018-11-20 (the Nov-2018 breakdown) precedes btc's final low
  by 25d.
- **In leg-length terms:** the spike sits within the final ~17% of the
  top→bottom leg in 7/8 cases (median ~8%) — the flush marks the last sixth of
  the down move.
- **"Single clearly one" is half-true:** dominance (best day vs best day
  outside ±3d) has median 1.25 — the flush is usually a 2-3 day cluster, not
  one towering day (sol C3's 3.80 is the exception).

**Window of attention (closed legs, n=8):** dominant z-flush at T ⇒ final low
historically in **[T+9, T+41] days** (IQR), honest envelope [T−10, T+51].
Median answer to "how long before the bottom": **~1 month**; within ±2 weeks in
38% of cases.

### Open legs: untestable — and the current C4 does not yet follow the rule

Provisional legs are structurally untestable (final bottom unknown; the
low-to-date can only fall). But the discrepancy deserves a place on the record:
BTC C4's dominant z-spike so far is **2026-02-05**, and the low-to-date
(2026-06-30) already sits **+145d** after it — outside the closed-leg window.
Either the C4 final bottom is still ahead of us, or the pattern fails this
cycle. No claim either way until the cycle closes.

### Why perspective 1 and perspective 2 disagree — and both are right

P1 asked "is there *any* z ≥ 3 spike within ±30d of the bottom": the nearest
spike to the bottom is random, so ABSENT. P2 asks "where does the leg's
*biggest baseline-aware* spike sit": at the leg's end, in a ±60d window P1
never tested (the misses were at +38..+51d). The capitulation signal is a
leg-end cluster, not a nearest-neighbour property.

## Result 4 — Perspective 3: the flush-cluster rule, stated plainly

The rule under review (2026-11-15): *"From the top to the bottom, is there a
stable 3+ days of volume concentration, and does the bottom occur at a stable
X days from the event with a ± time range?"* Script:
`scripts/explore_volume_clusters.py`.

**Operational definition:** qualifying day = daily volume z ≥ threshold vs
trailing 90d baseline (excluding self); cluster = ≥ N qualifying days with
gaps ≤ G days; event end = last qualifying day of the cluster. The operative
cluster is the **last** one in the bear leg — that is what a real-time monitor
can act on (you never know a later burst won't come). A sensitivity grid
varies threshold × minimum days × max gap.

### Strict form (z ≥ 3, 3+ days): FAILS

Only **5/8** closed legs contain such a cluster at all — and mstr C3's last
z ≥ 3 cluster ended **+231d** before its bottom (the LUNA burst of May 2022,
not the FTX flush that actually preceded the low). When present near the
bottom the timing is decent (4/5 within ±60d, p = 0.020, median +37d), but
presence is the failure. **As stated — "3+ days of *spiking* volume" — the
rule is not stable.**

### Working form (z ≥ 2, 3+ days, gaps ≤2d): HOLDS, modestly

| measure | result (closed legs) |
|---|---|
| presence | **7/8** (xrp C3 the sole counterexample: no 3-day z ≥ 2 cluster in its entire bear leg) |
| last cluster end within ±60d of bottom | **7/7** |
| lag, bottom − event end | median **+10d**, IQR −1..+49, envelope **−11..+49** |
| bottom AFTER the burst ended | 5/7 (btc B1 −1d and eth B2 −11d straddle it) |
| fair null (random cluster end, same legs) | 5/7 @±30d **p = 0.057**; 7/7 @±60d **p = 0.020** |
| random-day null | p = 0.001 / 0.000 — **flatters the rule** (z ≥ 2 clusters are dense; the last cluster is an order statistic, so the fair null is the citable one) |
| cluster-day coverage | 1–3% of leg days — the bursts are rare and short, which is what makes "burst, then quiet into the low" informative |

Sensitivity grid: z ≥ 2 / ≥3 days is the **only** configuration with presence
≥ 7/8 AND p@60 ≤ 0.02. Every z ≥ 3 or ≥ 4-day variant loses legs and
significance (see the script's grid table). The pattern exists but is
threshold-fragile — z ≥ 2 is the boundary, not the middle of a plateau.

### The C4 forward test (logged in advance)

At z ≥ 2, four assets' last C4 cluster ended 2026-08-21..28 (btc, eth, mstr,
sol) and their lows-to-date **predate** those clusters (−52/−57/−56/−83d). The
rule therefore makes a falsifiable demand: **either a lower low comes after
those dates, or the rule fails C4.** xrp is consistent so far (low-to-date
+50d after its 2026-09-25 cluster). wgmi has printed no cluster yet. This is
pattern bookkeeping logged before the outcome, not advice.

#### Does that demand overlap the model's own B4 windows? (checked 2026-11-15)

> **Note (added after the P5 reanalysis):** every cluster date in this table
> is direction-blind — August was rally volume, so its "flush" reading here
> is wrong. Result 5 redoes the C4 forward test with red-only clusters:
> btc **failing** (+145d from the February flush), mstr **consistent** (+0d),
> eth/xrp/sol no red cluster yet. Keep this table for the direction-blind
> lens only; the SOL/MSTR zone-convergence discussion survives only as a
> direction-blind observation.

The projected B4 bottom windows (`next_cycle_zones.csv` /
`alt_next_cycle_zones.csv`) were built by completely different machinery
(own-history / 2-stage projections) — independent provenance from the cluster
rule, so agreement is information:

| asset | cluster end | low-to-date | projected B4 window (base / outer) | overlap after cluster? | as of 2026-11-15 | price check |
|---|---|---|---|---|---|---|
| btc | 2026-08-21 | 2026-06-30 $58.5k | Oct 12–Nov 2 / Oct 5–Nov 16 2026 | yes — but expires at the outer edge | outer ends **the next day** | band $29.6k–$53.7k sits entirely **below** the low — the zones already demand a far lower low |
| eth | 2026-08-21 | 2026-06-25 $1,565 | Jun 27–Sep 13 / May 19–Oct 21 2026 | partial (base tail 23d) | **expired** Oct 21, no post-cluster low | low sits **inside** the band — the zones are price-consistent with the June low *being* B4 |
| mstr | 2026-08-21 | 2026-06-26 $82.31 | Sep 30–Jan 28 / Aug 1–Mar 29 | **yes** — base window entirely after the cluster | **live** (~2.5–4.5 months remain) | band $103.4–$121.4 sits **above** the observed low — the zones are already price-broken here, independent of timing |
| sol | 2026-08-28 | 2026-06-06 $62.19 | Sep 30–Jan 28 / Aug 1–Mar 29 | **yes** — base window entirely after the cluster | **live** (~2.5–4.5 months remain) | low sits at the band **centre** ($62.14) — price-perfect |
| (xrp) | 2026-09-25 | 2026-11-14 $0.913 | Mar 20–Jul 18 / Jan 19–Sep 16 2026 | rule satisfied (+50d) — but the zones' window had already closed | expired | low 0.2% above the band top |

Plain-English convergence read:

- **SOL and MSTR converge**: rule + zones agree on a joint window — a lower
  low between **late Sep 2026 and late Jan 2027** (base; outer to Mar 2027),
  after the August burst. SOL is the cleanest case (its projected B4 band
  centres exactly on the June low, so only the *timing* is in play). Caveat:
  mstr's and sol's windows are the same dates because both anchor on the
  BTC-derived timeline — one shared anchor, not two independent confirmations.
- **BTC converges only on a nearly-expired clock**: the projected outer window
  ends 2026-11-16. Rule + zones agree only if the lower low lands within days;
  after that they part ways.
- **ETH has already diverged**: the zones' B4 window closed 2026-10-21 with
  the June low standing, and that low is price-consistent with the band — so
  for ETH the zone framework says B4 already happened, while the cluster rule
  says the bottom should postdate 2026-08-21. First clean conflict between the
  two frameworks.
- **MSTR's price band is breached regardless** ($82.31 low vs $103.4 band
  floor, −20%): any further lower low deepens the breach. The MSTR B4 band
  needs review on its own terms.

### Plain-English answers

1. *"Is there a stable 3+ days of volume concentration?"* — At a demanding
   threshold (z ≥ 3): no, 5/8 legs. At a mild one (z ≥ 2): yes, 7/8 closed
   legs — the capitulation burst exists in nearly every closed bear leg.
2. *"Does the bottom occur at a stable X days from the event, ± a range?"* —
   The centre is **~1–2 weeks** (median +10d) and the stable part is the
   **envelope, about −2 to +7 weeks** (7/7 within ±60d). The tight "X ± small"
   version does not survive; the wide envelope does.
3. Verdict label: **WEAK-CONFIRMED** (cluster form, z ≥ 2) — real, modest,
   definition-fragile, n = 7–8 closed legs.

## Result 5 — Reanalysis: direction and absolute-vs-relative (2026-11-15)

Trigger: the user's TradingView weekly chart showed the Feb/June 2026 volume
peaks dwarfing the August burst the P3 rule had picked as BTC's operative
"flush". Down-day conditioning then proved the point: the Aug 19–21 cluster
is **0/3 down days — rally volume**, not capitulation. The rule had been
counting a buy-side burst as a sell-side flush. Script:
`scripts/explore_volume_reanalysis.py` (scenario grid: detector × direction,
read-only, rerunnable).

### What the mislabel changed

- **August is reclassified**: high *relative* to a collapsed July baseline
  (z 4.8 vs base 1,263), but a buy-side event. It says nothing about bottoms.
- **February is the real C4 capitulation** (z 6.4, base 2,769, 3/5 down days
  in its cluster) — and it sits +145d before the low-to-date: BTC's C4
  *sell-side* flush fails the timing rule outright.
- **MSTR's last red cluster ends exactly at its low-to-date** (2026-06-26,
  lag +0d) — the one asset where the capitulation lens is currently perfect.

### Scenario grid (closed legs, last cluster → bottom, ±60d)

| detector | direction | presence | in ±60d | lag med | envelope | p_day | p_end |
|---|---|---|---|---|---|---|---|
| z≥2 | any | 7/8 | 100% | +10d | −11..+49 | 0.000 | 0.016 |
| z≥2 | **mixed (≥½ red)** | **7/8** | **100%** | **+24d** | **−1..+49** | 0.000 | 0.057 |
| z≥2 | down (red days only, 3+ days) | 3/8 | 100% | +37d | +10..+50 | 0.033 | 0.494 |
| ≥2× 90d mean | any | 8/8 | 75% | +42d | −6..+426 | 0.006 | 0.011 |
| ≥2× 90d mean | mixed | 7/8 | 71% | +48d | −2..+426 | 0.018 | 0.066 |
| **top-2% of history (absolute)** | any | **4/8** | **25%** | **+270d** | **−2..+421** | **0.664** | 0.194 |

Two decisive results:

1. **Absolute spikes are the wrong lens.** The top-2%-of-all-history detector
   fails outright (4/8 presence, 25% in-window, p ≈ chance). February's
   12,980-BTC flush day does not even rank in BTC's all-time top 2% of daily
   volume — absolute comparisons are meaningless across a decade of growing
   volume. Relative-to-recent-baseline is the only defensible detector.
2. **The 2-day red-cluster rule is the strongest bottom signal found.**
   Relaxing the red-day cluster to ≥2 days (z ≥ 2, gap ≤ 2d):

   | measure | result (closed legs) |
   |---|---|
   | presence | **8/8** (xrp C3 included — the 3-day rule missed it) |
   | last cluster end within ±60d | **8/8** |
   | lag, bottom − cluster end | median **+31d**, envelope **+0..+50d — all positive** |
   | random-day null | p = 0.000 |
   | fair null (random cluster end, 23 clusters) | **p = 0.003** |

   The all-positive envelope is the sharpest statement available: *the final
   bottom has never come before the last 2-day red volume burst ends.* n = 8,
   one regime family, but zero counterexamples in the sample.

### Revised C4 forward-test status (sell-side clusters only)

| asset | last red cluster (≥2d rule) | lag to low-to-date | status |
|---|---|---|---|
| btc | 2026-02-05 (3/3 dn) | **+145d** | **FAILING** — outside ±60d |
| mstr | 2026-06-26 (3/3 dn) | **+0d** | consistent — flush at the low |
| eth, xrp, sol | none ≥2d yet | — | no sell-side burst yet |
| wgmi | none | — | no cluster yet |

Under direction-honest definitions the C4 picture changes from "four assets
failing forward" to: **one failing (btc), one perfect (mstr), four with no
operative signal yet.** Honest, and falsifiable on the same terms as before.

## Verdict

- **TOPS: CONFIRMED** in this sample — consistent across ~14 observations,
  direction-consistent across four independent detector families, and far
  beyond the chance baseline. Operational reading: a z ≥ 3 (or top-2%-of-cycle)
  volume day landing within ±14d of a candidate top is *confirmation*, not
  prediction — it arrives with the top (lag median 0d), leading only on BTC.
- **BOTTOMS, nearest spike (P1): ABSENT** — a random z ≥ 3 spike near the
  bottom carries no information; do not build on that framing.
- **BOTTOMS, dominant leg-end flush (P2): CONFIRMED on closed legs** — the
  leg's biggest baseline-aware spike precedes the final bottom by a median
  ~1 month (8/8 within ±60d, p ≈ 0.000), and the spike dates are the famous
  capitulations. Two honesty limits: (a) n = 8 closed legs; (b) the current
  C4 does not yet follow the rule — BTC's C4 flush (2026-02-05) is already
  +145d before the low-to-date, outside the window. Untestable until the
  cycle closes; **on the record, not sold**.
- **BOTTOMS, flush-cluster rule as stated (P3): FAILS at z ≥ 3, WEAK-CONFIRMED
  at z ≥ 2** — presence 7/8 closed legs, timing 7/7 within ±60d of the last
  cluster's end (median +10d), fair-null p = 0.02 at ±60d. Definition-fragile
  and currently *failing forward* on C4 (see the logged forward test above).
- **BOTTOMS, after the reanalysis (P5): the direction-honest forms are the
  keepers.** Absolute detectors are dead (p ≈ chance). Three-day red-only
  clusters are too strict (3/8). The two forms that survive with direction
  honesty: **2-day red clusters — 8/8 presence, 8/8 in ±60d, envelope
  +0..+50d, fair-null p = 0.003** (the strongest bottom signal found), and
  **3-day mixed clusters — 7/8, 100% in ±60d, p_end = 0.057** (the strict
  companion). The original direction-blind 3-day rule (7/8, p 0.016) stays
  as the fallback only with its direction mix published, because it counts
  rally bursts like Aug-2026 as flushes.

## Caveats (read before citing)

1. **n is tiny.** 14 tops / 15 bottoms across six assets is the entire
   observable universe; "CONFIRMED" means consistent-and-better-than-chance,
   not statistically robust.
2. **C4 asymmetry.** 6 of 14 tops are the still-open C4, one regime,
   100% hit — the historical rate (5/8) is the more conservative figure.
3. **Volume units are not comparable across assets** (and CDD's absolute
   scale is unreliable). Everything here is within-asset ratios only.
4. **Yahoo crypto volume denomination is ambiguous** (base vs USD); the
   detectors are ratio-based and invariant to it, but absolute comparisons
   remain forbidden.
5. Five bottoms are provisional lows-to-date; their dates can only move down/later.
6. The exploration is one analyst-pass; rerun the script before citing numbers.

## If Phase B is approved (candidate I-23)

Two signals, both confirmation-shaped rather than prediction-shaped:

1. **Top confirmation:** a `volume_spike` column next to Rule T output
   (z ≥ 3 vs trailing 90d, plus top-2%-of-cycle), gate-tested against the
   per-extremum table above, surfaced on the C5 candidate-top chart as a
   marker.
2. **Bottom flush monitor (revised after the P5 reanalysis):** the
   direction-honest definitions replace the direction-blind 3-day rule:
   - **Primary: 2-day red cluster** (z ≥ 2, ≥2 red days, gap ≤2d) — 8/8
     closed legs, envelope **+0..+50d** from cluster END to bottom, fair-null
     p = 0.003. Widening arithmetic: `outer_end = max(current, flush_end + 50d)`.
     With real numbers this is nearly a no-op today — only XRP's B4 outer
     window actually moves (2026-09-16 → 2026-11-15); every other crypto
     asset's outer window already reaches past its last red cluster.
   - **Companion: 3-day mixed cluster** (z ≥ 2, ≥3 days, ≥½ red) — 7/8,
     100% in ±60d, p_end = 0.057.
   - **Every cluster carries its direction mix** (`down/total` in the
     provenance) and chart markers distinguish red-bursts from rally-bursts
     — the Aug-2026 mislabel must not be repeatable silently.
   - C4 status to display: btc FAILING (+145d, February flush), mstr
     consistent (+0d), eth/xrp/sol/wgmi no operative red cluster yet.


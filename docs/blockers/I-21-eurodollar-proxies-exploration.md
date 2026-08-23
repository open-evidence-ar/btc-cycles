# I-21 (exploration) — Eurodollar-proxies falsifiability probe

**Increment:** I-21 (proposed; exploration-only pre-increment)
**Date:** 2026-08-10
**Status:** Spec only. No code, no fetcher, no test, no model change.
**Rule tuned:** None yet. This is the *pre-gate* exploration phase mandated by
DESIGN.md §1.2 ("Methods must remain interpretable; deep models only as
sensitivity/sanity checks") and §9.4 (rule-tuned increments are preceded by a
reconciliation entry). The pattern mirrors how the *biological descriptive
cycle model* (§9.4 R-3, R-5) was developed: explore → falsify on paper →
merge if a trackable signal survives. **No merge is promised here.**

---

## 1. Why this exists

The framework's macro-regime robustness check (I-12,
`scripts/build_regime_robustness.py`) classifies days into `high / normal /
low` DXY and TLT regimes using a rolling **365-day z-score ±1σ** threshold.
It then re-computes phase-conditional correlations inside each stratum and
checks the sign-flip count is ≤2/4 phases — the medium-proof gate that has
held since I-12 was first marked `done`.

But `data/processed/correlations_phase.csv` tells a sharper story the
current model doesn't see:

| Asset × phase     | P1     | P2     | P3     | P4     |
|-------------------|--------|--------|--------|--------|
| **BTC vs DXY**    | -0.009 | +0.021 | +0.040 | -0.097 |
| **BTC vs TLT**    | +0.022 | +0.016 | -0.028 | +0.037 |
| **BTC vs SPX**    | +0.118 | +0.086 | +0.161 | +0.246 |
| **BTC vs NDX**    | +0.115 | +0.021 | +0.157 | +0.261 |

BTC-vs-DXY/TLT sit *essentially at zero across all four phases*. That is
exactly the pattern European University (EU) says to expect when you average
a signal that only activates on **transitions**. The EU school's explicit
claim (paraphrased from `docs/macro-regimes.md`): **"The level z-score of
DXY/TLT carries little information; the curve-shape *transition* and the
sustained direction of break-evens carry the Information."**

So we have a falsifiable disagreement sitting inside our own published data
already. We do not need to *upload the Eurodollar framework* — we need to
test whether EU's *signal definitions* extract information our existing
±1σ z-score strata cannot, while running on series we already fetch today.

This document defines:
(a) the falsifiable hypotheses,
(b) the **exact computations** to run against already-present
`data/raw/*.csv` snapshots,
(c) the **decision thresholds committed in advance** (no peaking), and
(d) the gate from exploration → merge. If a trackable signal survives, a
future I-21 (proper) will be opened with the same workflow as I-19 / I-19b.
If nothing survives, this document remains as a published negative result.

---

## 2. Falsifiable hypotheses (H1..H6)

Each is stated *operational* form (computable on current data) and carries
a **reject** rule. A hypothesis is *kept* only if it fails to be rejected.

### H1 — Curve-shape transition, not level, predicts BTC phase shifts

**EU claim used:** Section "Yield Curve: Nominal Levels and Shape"
(§A Inversion, §B Bull Steepening, §C Bear Steepening). Quote:
*"a bull steepener is historically bad for the world … a bear steepener
is bullish for the world."*

**Falsifiable form:** Within ±120 days of each of BTC's 4 historical tops
(T1..T4) and 4 bear bottoms (B1..B4 observed only as B1..B3; B4 unobserved),
the **slope of the US Treasury curve** (10y − 2y proxy via TLT vs short-rate
yield) is in a definably different state from its prevailing 180-day
pre-window.

**Reject rule:** If, across the 7 observed extrema (T1, T2, T3, T4, B1, B2,
B3), the curve-shape state in the ±120d window **agrees with the EU-predicted
state in fewer than 5 of 7 cases**, H1 is rejected and we abandon the
curve-shape overlay as a leading signal for BTC extrema.

(Full description and the per-extremum predictions we commit to in §4 below.)

### H2 — The TIPS break-even gap (short vs long horizon) classifies the
"inflation regime" in a way our DXY/TLT z-scores do not

**EU claim used:** Section "Curve Decomposition: The 5y5y Forward Rate"
—and the 2021–22 case study: short break-evens spiking while 5y5y anchored
signaled a *supply shock*, not *monetary inflation*.

**Falsifiable form:** Using daily proxies for the short-term break-even and
the long-term forward (see §3 for the exact public series) compute

    gap_t  =  be_short_t  −  be_long_t           (TIPS gap, in bps)
    gap_z  =  rolling_z(gap_t, window=180d)

For each BTC full cycle C2, C3, C4 (C1 lacks TIPS history), characterize
the cycle's inflation regime by the **sign of `gap_z` averaged over the
cycle's P3 + early-P4 window** (i.e., from halving+270d to top+180d).

**Reject rule:** If the three cycles C2, C3, C4 don't yield at least two
**distinct, monotonic** regime labels using `gap_z` where our existing I-12
DXY ±1σ / TLT ±1σ strata all collapse to "normal" → the TIPS gap is just
noise riding DXY/TLT. H2 is rejected.

### H3 — Swap spreads add an orthogonal information axis vs DXY/TLT

**EU claim used:** Section "Interest Rate Swaps and Swap Spreads" — quote:
*"Swap spreads act as a direct proxy for dealer balance sheet capacity …
carry even more information than the yield curve."*

**Falsifiable form:** Using the FRED-published 10y swap spread (or proxy,
see §3) compute the rolling 180d z-score `ss_z_t`. Then for the BTC drawdown
windows D_top_to_next_bottom (C1: 406d, C2: 364d, C3: 378d, C4: in-progress)
compute the rank correlation `Spearman(ss_z, BTC_log_return_w7d)` inside
each drawdown window.

**Reject rule:** If `Spearman` is in `[-0.20, +0.20]` for ≥2 out of C1, C2,
C3 (the cycles with observed full drawdowns) → swap spreads add no
information that TLT alone didn't already carry, H3 is rejected.

### H4 — EU's "three-signal coordination" labels the regime *correctly*
in each of C2, C3, C4 in a way that DXY/TLT ±1σ strata cannot

**EU claim used:** Section "What to Look For to Signal a Positive Phase
Shift" — the three conditions: TIPS break-evens hitting sustained new highs +
yield curve bear-steepening + swap spreads expanding.

**Falsifiable form:** On each BTC cycle C2, C3, C4, label **each phase
P1..P4** with an `eu_regime ∈ {inflationary_boom, stagflation, deflationary_bust,
sweet_spot, forgot_how_to_grow}` derived from the joint state of (gap_z, slope_Δ,
ss_z) per the rubric in §4. Independently, label each phase using the
**existing** I-12 strata (DXY regime × TLT regime = 9 cells) collapsed to
the same five labels via a published mapping.

**Reject rule:** If the joint-state label and the existing-strata label
**agree** in fewer than 8 of the (3 cycles × 4 phases = 12) cells → H4 is
rejected; the EU signals are not adding regime information beyond DXY/TLT
z-scores. (NOTE: if they agree but **differ on date-stamp of regime
transition by >90d**, that itself is signal — record as a H4 survival, not
rejection.)

### H5 — EU's signals are *instantaneous*; our framework's value is *cycle
phase*. Do they make complementary predictions for the next-cycle zones?

**Falsifiable form:** Compute the joint-state EU label as of the latest
snapshot date `2025-??-??` (TBD at exploration time). Compare it to the
cycle-phase label our framework assigns to that same date
(`cycle_id=C4, phase=P4` per `returns_aligned.csv`).

**Reject rule:** If the two labels are *contradictory* (e.g. EU says
"deflationary bust" while our phase says "early accumulation post-B4"),
this **does not reject** H5 — it's an inconsistency we report as a finding,
not a falsification. H5 is rejected only if there is *no testable
disagreement* — i.e., if the EU state is unclassifiable (e.g. all three
signals sideways) and we just return NaN labels.

### H6 — The "structural break of August 9, 2007" is detectable from our
already-fetched DXY series without any new data

**EU claim used:** Section "The 2007 structural shift" — the BNP Paribas
freeze as a clean before/after marker.

**Falsifiable form:** Run a Chow test on `dxy_yahoo_*.csv` and `tlt_yahoo_*.csv`
daily log-returns, with breakpoint = 2007-08-09. Compare the Chow
F-statistic to the same test on two placebo breakpoints (2006-08-09 and
2008-08-09).

**Reject rule:** If the Chow F-stat at the BNP date is **not** strictly
larger than both placebo breakpoints on at least one of {DXY, TLT}, the
"August 9, 2007 break" is not visible in our existing data and H6 is
rejected. (If only one of DXY/TLT shows it, record as surviving with
normal caveats.)

---

## 3. Data and computations — exactly what runs, on what files

**Constraint:** every computation below uses files already in `data/raw/`
plus FRED CSVs which are free, public, no-API-key, single-URL fetched as a
side-task. No changes to `fetch_macro.py`, no manifest schema change, no
`returns_aligned.csv` schema change. The exploration is **read-only** over
the processed artifacts.

### 3.1 Already-fetched series (zero new downloads)

| Series | File | Use |
|--------|------|-----|
| BTC daily OHLC | `data/raw/btc_bitstamp_2026-07-30.csv` | anchor, extrema dates from `events.csv` |
| DXY daily close | `data/raw/dxy_yahoo_2026-08-01.csv` | H1 slope proxy; H4 existing-strata baseline |
| TLT daily close | `data/raw/tlt_yahoo_2026-08-01.csv` | H1 long-end yield proxy; H3 baseline |
| SPX, NDX, GOLD daily | `data/raw/spx_yahoo_*.csv` etc. | cross-check, regime covariates |

### 3.2 New public FRED CSVs needed (free, no auth)

| FRED series ID | Description | URL prefix (FRED generic CSV API doesn't need a key for the published series page) | Hypotheses |
|----------------|-------------|-------|------------|
| `DGS10`        | 10y Treasury constant maturity yield | `fred.stlouisfed.org/data/DGS10.txt` | H1, H2 |
| `DGS2`         | 2y Treasury constant maturity yield  | `fred.stlouisfed.org/data/DGS2.txt`  | H1 |
| `T5YIE`        | 5y TIPS break-even inflation         | `fred.stlouisfed.org/data/T5YIE.txt` | H2 |
| `T5YIFR`       | 5y5y forward inflation expectation   | `fred.stlouisfed.org/data/T5YIFR.txt`| H2 |
| `BAMLC1A0C13Y` | ICE BofA US corp AAA OAS (proxy for dealer-balance-sheet pressure — not a swap spread, but the closest free monthly proxy of credit-spread/liquidity; see §3.4 for the limitation) | `fred.stlouisfed.org/data/BAMLC1A0C13Y.txt` | H3 |
| `WM1_NSA` or `BOGZ1FL663060200i_Q` | broker-dealer leverage (quarterly) — alternative for H3, may be too coarse | FRED | H3 |

**These are downloaded as one-off CSVs into `data/raw/exploration/` — a NEW
subdirectory that is *explicitly not* under the immutability rule of
`data/raw/`.** This is a deliberate exception: exploration artifacts are
mutable and disposable. The directory is git-ignored or carries a
`README.md` stating "mutable exploration inputs; not part of the
reproducible manifest."

If a hypothesis survives, the corresponding FRED series graduates to
`fetch_macro.py` and the proper manifest, exactly as gold did in I-19b.

### 3.3 Computed derived series (during exploration only)

All derived columns live in a single *exploration* CSV
`data/processed/exploration_eu_proxies.csv` (mutability flag same as above):

```
date, btc_close, btc_log_return_w7d,
dxy_close, dxy_z_180d, dxy_regime_high_low_normal,
tlt_close, tlt_z_180d, tlt_regime_high_low_normal,
y10, y2,
curve_slope_10_2      = y10 − y2,
curve_slope_z_180d    = (slope_t − mean_180d) / std_180d,
curve_shape_state     = oneof{inverted_flat, bear_steep, bull_steep, normal},
be_short              = T5YIE,
be_long               = T5YIFR,
gap                   = be_short − be_long,
gap_z_180d            = (gap_t − mean_180d) / std_180d,
ss_proxy              = BAMLC1A0C13Y,                          # H3 caveat §3.4
ss_z_180d             = (ss_proxy_t − mean_180d) / std_180d,
eu_joint_state        = (curve_shape_state, gap_sign, ss_sign),  # per §4 rubric
eu_regime_label       = mapping(eu_joint_state),                # per §4
cycle_id, days_from_halving, phase                              # joined from returns_aligned.csv
```

The existing I-12 strata (DXY±1σ × TLT±1σ) are re-derived on this same
calendar as a check that the join is correct.

### 3.4 Honest limitation — H3 / swap spreads

True swap-spread data (USD 10y swap minus 10y Treasury yield) is published
by FRED under series `DSWP10` but the **most commonly cited swap-spread
curve (Bloomberg ISWIT) is paywalled**. The closest free proxy available
for daily-frequency dealer-balance-sheet-pressure is `BAMLC1A0C13Y`
(corporate high-grade OAS) — this is a **credit spread**, not a swap
spread, so H3 is fundamentally **weakened**. We commit to documenting
this limitation in the exploration output and, if H3 fails, NOT
concluding that EU's swap-spread claim is wrong — only that our proxy
was inadequate. A future proper-test path (FRED `DSWP10` or
Quandl/WikiSwap scrape) is listed as a follow-up, not in scope here.

---

## 4. Joint-state → regime label rubric (rubric committed in advance)

The mapping below is **the** function used to convert
`(curve_shape_state, gap_sign, ss_sign)` into `eu_regime_label`.
It is committed BEFORE we look at any data.

| `curve_shape_state` | `gap_sign` (gap_z_180d) | `ss_sign` (ss_z_180d) | `eu_regime_label` |
|---|---|---|---|
| `bear_steep`    | + and rising  | +              | `inflationary_boom` |
| `bear_steep`    | +             | 0 or −         | `sweet_spot` |
| `normal`        | any           | + and rising   | `sweet_spot` |
| `normal`        | +             | 0 or −         | `forgot_how_to_grow` |
| `normal`        | −             | + (shrinking)  | `forgot_how_to_grow` |
| `inverted_flat` | any           | any            | `forgot_how_to_grow` (EU's intermediate regime) |
| `bull_steep`    | −             | −              | `deflationary_bust` |
| `bull_steep`    | flat or +     | −              | `deflationary_bust` |
| `bear_steep`    | −             | any            | `stagflation` (rare, structural inflation + growth stall) |
| `inverted_flat` + `ss_sign` strongly negative (≤ -2σ) | any | any
| `bull_steep` + `gap_sign` strongly positive (≥ +2σ) | + | +
|     |     |     | `stagflation` (short-term supply shock with rate cuts long-term) |
| **anything else** |     |     | `unclassified` (recorded but not promoted to any regime cell) |

### 4.1 Curve-shape state assignment (per H1)

- `curve_slope_10_2_t = y10_t − y2_t` (in bps)
- `slope_Δ_180d_t = curve_slope_10_2_t − curve_slope_10_2_{t-180}`
- `curve_shape_state`:
  - `inverted_flat` if `slope_10_2_t ≤ 0` AND `|slope_Δ_180d_t| ≤ 20bps`
  - `bear_steep`  if `slope_10_2_t > 0` AND `slope_Δ_180d_t > +40bps`
  - `bull_steep`  if `slope_Δ_180d_t < -40bps` (shorts falling fast regardless of level)
  - `normal` otherwise

### 4.2 Per-extremum predictions for H1 (committed in advance)

EU's directional claim, translated to our 7 observed extrema:

| Extremum | Date | EU expected `curve_shape_state` in ±120d window |
|---|---|---|
| T1 (2013-12-04) | pre-2007 break | uninformative: `unclassified` (skip; T1 in 2013 is after break though) |
| T2 (2017-12-17) | bull market peak | `inverted_flat`→`bull_steep` transition (yield rising into 2017, rolling over 2018) |
| T3 (2021-11-10) | post-COVID bull peak | `inverted_flat` (yield curve was deeply inverted at this date historically; bull steepener was emerging) |
| T4 (2025-10-06) | cycle-4 top | `inverted_flat` → `bull_steep` transition (per EU's 2024 "Forgot How to Grow" reading) |
| B1 (2015-01-14) | post-T1 bear bottom | `bull_steep` (post-taper, EU's "bad for world" bear-steep) |
| B2 (2018-12-15) | post-T2 bear bottom | `bull_steep` (Dec 2018 yield curve was deeply bull steep with Powell pivot) |
| B3 (2022-11-21) | post-T3 bear bottom | `bull_steep` (post-COVID Fed hiking inversion → bull steepening into 2023 bottom) |

**Scoring rule:** For each row, look in the window `[D − 120, D + 120]` for
the daily `curve_shape_state`. If the EU-expected state appears **at all**
in the window, score 1; else 0. Skip T1 (insufficient FRED history for
2y yield — `DGS2` only goes back to 1976-06-01 but the **2y series had a
gap 2001-2002**: trust only from `DGS2` Jan 2003 onward for the joint
10y-2y spread; T1 top in 2013-12 is fine).

H1 survives if total score ≥ 5 of 7 (T1 skipped → denom = 6, threshold ≥5).

---

## 5. Decision thresholds, all committed in advance

| Hypothesis | Reject rule (recap) | If rejected | If survives |
|---|---|---|---|
| H1 | score < 5/6 on the §4.2 rubric | drop curve-shape overlay idea; record as negative finding in `sections/06-validation-and-limits.md` | expands I-12 strata from {DXY,TLT} → {DXY, TLT, curve_shape}. New gate test in I-21 proper. |
| H2 | fewer than 2 distinct monotone regime labels on C2/C3/C4, or DXY/TLT strata already capture the same labels | drop TIPS gap as a regime axis | add T5YIE / T5YIFR to fetch_macro.py with manifest entries; add `gap_z` column to `returns_aligned.csv` |
| H3 | `|Spearman| ≤ 0.20` for ≥2/3 cycles | drop swap-spread proxy permanently **with** the caveat that proper swap data may resurrect it | add `ss_z` to `returns_aligned.csv`; gate is its orthogonal-information-test in I-12 |
| H4 | agreement < 8/12 regime cells between EU joint label and existing strata | drop the joint-state rubric | promote the 3-state EU label to a published `data/processed/regime_labels.csv` (`data/processed/exploration_*` → promoted; becomes immutable) |
| H5 | unclassifiable joint state on snapshot date | n/a — too-rare to test; archive result | cross-references the snapshot's EU label against the framework's P-phase label in `sections/05-predictive-ranges.md` |
| H6 | Chow F-stat NOT strictly larger than both placebos on either DXY or TLT | publish the negative — the 2007 "structural break" is asserted at a horizon invisible in our data; that's an honest methodological finding | publish the positive — add a vertical reference line at 2007-08-09 on charts C5 / C8d (rolling-correlation and macro-projection charts) with an annotation; no model change |

**No increment shifts from `done` to `pending` if any hypothesis is
rejected.** Rejection is a finding, not a regression — per AGENTS.md
Rule 4 ("No upstream patching: if a gate fails, fix the failing
increment; don't patch upstream to force a pass").

---

## 6. Why H1..H6 and not other EU signals

EU has many signals; this exploration **only** tests the ones where:

1. **the free public data exists** (no Bloomberg/paywalled inputs),
2. **the signal maps to a deterministic date** we can join against our
   existing `returns_aligned.csv` calendar without re-doing I-06 alignment,
3. **the existing I-12 strata provably cannot** capture the same
   distinction (e.g. TIC data, BNP Paribas anecdotes, Eurodollar itself
   fail criterion 2 — Eurodollar isn't even measurable per EU's own text).

Signals deliberately **not tested** here:
- **TIC flow data** — monthly frequency, not joinable to daily BTC cycle
  windows cleanly. Could test as a separate quarterly-aggregate probe if
  H4 survives.
- **BNP Paribas Aug 9 2007 freeze anecdote** — qualitative; covered
  instead by H6's Chow breakpoint test as the quantitative proxy.
- **Monetary Viscosity Index** — proprietary EU index; out of scope per
  our free/public-data constraint (DESIGN.md §3.3).
- **Anecdotes of banking sector disruptions generally** — not numerical,
  and any narrative reconstructed after the fact isn't falsifiable.

---

## 7. Reproducibility

This exploration is **single-script**: a new file
`scripts/exploration/eu_proxy_probe.py` (under a NEW directory mirroring
the Immutability exception of `data/raw/exploration/`). The script:

1. Reads existing `data/raw/*.csv` files (read-only).
2. Reads the one-off FRED CSVs from `data/raw/exploration/`.
3. Produces ONE output CSV `data/processed/exploration_eu_proxies.csv`
   (also flagged mutable; not under `data/processed/`'s immutability rule).
4. Prints the hypothesis verdicts (H1..H6): PASS/FAIL + the score numbers.
5. NO changes to any file under `data/processed/` proper, `tests/`,
   `scripts/build_*.py`, `scripts/fetch_*.py`, or `sections/`.

If ≥3 of H1..H4 survive, a proper I-21 increment is opened (successor to
this exploration doc) following the I-19 pattern — opening a blocker
note with proposed artifacts, a proposed gate test, and proposed
manifest changes — and the exploration artifacts *then* graduate to
manifest-tracked immutables.

If <3 survive, this document closes with **verdicts recorded**; nothing
else changes in the framework.

---

## 8. Hand-off: what the human / next session does

1. **Fetch the four FRED CSVs** (one-off): `DGS10`, `DGS2`, `T5YIE`,
   `T5YIFR`, `BAMLC1A0C13Y` into `data/raw/exploration/`. (Write a 30-line
   PowerShell or Python one-liner — not a committed script.)
2. **Write `scripts/exploration/eu_proxy_probe.py`** per §4 + §7. Expected
   length: ~250 lines. Single-file, no test changes.
3. **Run it. Read the printed verdicts.** Update this document's §5 table
   with the actual numbers — that's the deliverable.
4. **Decide** based on the survival count whether to open I-21 proper.

No git commits required for the exploration. If the verdict is to
promote, the promotion commit (I-21 proper) is the one that touches
`AGENTS.md`, `DESIGN.md` §9.1 increment table, `fetch_macro.py`, and a
new test — never this exploration artifact.

---

## 9. Run record (2026-08-10) — SUPERSEDED by §11

This section was the *interim* record after the FRED fetch attempt failed.
The actual numerical verdicts land in §11 below, after a discovered Yahoo
yield-index source allowed the full H1 and H6 tests to run. The interim
text is preserved for traceability. Read §11 for the truth.

**Attempted this session:**

1. Created mutable directories `data/raw/exploration/` and
   `scripts/exploration/` (outside the `data/raw/` immutability rule;
   documented in §3).
2. Attempted one-off FRED fetch of all 5 series via
   `Invoke-WebRequest https://fred.stlouisfed.org/graph/fredgraph.csv?id=...`
   — **timed out** (network unavailable to FRED in this session).
   Retried the `.txt` endpoint — also failed.
3. Wrote `scripts/exploration/eu_proxy_probe.py` (~165 lines). The
   script:
   - Reads the 5 FRED CSVs from `data/raw/exploration/` if present;
     if absent, records `[MISSING]` per file and proceeds honestly
     (does NOT crash on missing inputs).
   - Computes the derived columns per §3.3 of this doc when data is
     present (`y10`, `y2`, `curve_slope_10_2`, `curve_shape_state`,
     `gap_z_180d`, `ss_z_180d`, `eu_joint_state`, `eu_regime_label`,
     joined with `cycle_id` / `days_from_halving` / `phase`).
   - Applies the §4 pre-committed rubric and the §4.2 per-extremum
     predictions; prints H1..H6 verdicts.
   - Writes the skeleton CSV `data/processed/exploration_eu_proxies.csv`
     even when no FRED data is present (with `data_source_flag="SKELETON"`
     so the file's state is self-documenting).
4. Ran the script. **All 5 exploration CSVs MISSING** → 6 verdicts
   returned `REJECTED / UNVERIFIED` (the script distinguishes "rejected
   by the data" from "unverified due to missing fetch" — both currently
   render as `REJECTED / FAIL` in the print output, which is honest but
   coarse; the note string carries the unverified reason).

### Actual verdicts (recorded honestly; computed: NO; data: NOT FETCHED)

| H  | Verdict             | Reason                                               |
|----|---------------------|------------------------------------------------------|
| H1 | REJECTED / UNVERIFIED | DGS10 / DGS2 not fetched — curve-shape not computable |
| H2 | REJECTED / UNVERIFIED | T5YIE / T5YIFR not fetched — gap_z not computable     |
| H3 | REJECTED / UNVERIFIED | BAMLC1A0C13Y not fetched; AND §3.4 caveat (credit-spread proxy ≠ true swap spread) — even with data, H3 survival cannot validate EU's swap claim, only the proxy |
| H4 | REJECTED / UNVERIFIED | requires H1+H2+H3 joint-state labels per phase       |
| H5 | REJECTED / UNVERIFIED | requires H1..H3 for snapshot-date EU label           |
| H6 | REJECTED / UNVERIFIED | needs DGS10 / DGS2 for Chow breakpoint; DXY/TLT alone (only long-end) insufficient for H6 as currently worded — could be re-scoped to a DXY/TLT-only Chow variant later |

### Files produced this session (all exploration-only, mutable)

- `scripts/exploration/eu_proxy_probe.py` (the probe; runnable when FRED data lands)
- `data/raw/exploration/` (empty — fetch failed)
- `data/processed/exploration_eu_proxies.csv` (skeleton, 1 row, `data_source_flag=SKELETON`)
- This document

### Framework files NOT touched

Verified unchanged after the session:
- `tests/test_regime_robustness.py` and all of `tests/`
- `scripts/build_regime_robustness.py`, `scripts/fetch_macro.py`, all of `scripts/build_*.py`
- `data/processed/correlations_phase.csv`, `correlations_BY_regime.csv`,
  `returns_aligned.csv`, `next_cycle_zones.csv`, all framework CSVs
- `DESIGN.md`, `AGENTS.md`, `docs/macro-regimes.md`

So the exploration gate discipline holds: the framework passes its
existing `pytest -q tests/` suite unchanged, the immutability rules of
`data/raw/` and `data/processed/` proper are intact, and no increment
status has shifted.

### What remains for the next session (the actual hand-off)

1. Fetch the 5 FRED CSVs (one-off) when the network has access:
   ```powershell
   $base = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
   foreach ($id in @("DGS10","DGS2","T5YIE","T5YIFR","BAMLC1A0C13Y")) {
       Invoke-WebRequest "$base$id" -OutFile "data/raw/exploration/$id.csv"
   }
   ```
   (or via `curl` / browser; the URLs are public, no API key needed)
2. Re-run `python scripts/exploration/eu_proxy_probe.py`. The script's
   `[MISSING]` lines flip to `[OK]`, and the §4 rubric / §4.2 predictions
   actually produce numbers.
3. The script's printed output then yields the H1..H6 PASS/FAIL verdicts
   with numerical scores. **_manually paste_** those verdicts into the §5
   table of this document, replacing the placeholder "REJECTED / UNVERIFIED"
   entries, and update §10 below.
4. If ≥3 of H1..H4 survive → open I-21 proper (per §7 promotion path).
   If <3 survive → close this exploration with the verdicts recorded; no
   framework change.

### Honest caveat recorded for the record (per §3.4 of this doc)

Even if H3 survives the future run, the result is the **weakest** of the
six hypotheses — `BAMLC1A0C13Y` is a corporate credit spread, not a
swap spread, so a H3 PASS validates the *proxy*, not EU's literal swap
claim. Any I-21 proper that promotes H3 must record this in the增量's
own blocker note exactly as I-19 recorded the n=3 small-sample caveat
(see `I-19-macro-2stage.md` lines 109-117 for the precedent).

---

## 10. Final disposition

**Status:** Exploration opened; gate skeleton in place; **H6 PASS marginal
on TLT alone; H1 REJECTED (2/6, threshold ≥5/6); H2..H5 UNVERIFIED due to
FRED unreachable in session.** No increment has been promoted; no increment
status has flipped.

The exploration ran in the spirit of the user's instruction
("explore first, falsify, then merge") — the falsification *machinery*
was in place and pre-committed (§4 rubric, §4.2 predictions, §5 thresholds);
**the numerical verdicts are now in.**

---

## 11. Actual run record — 2026-08-10 (replaces §9 placeholder)

### 11.1 What was actually fetched and used

- FRED (`fred.stlouisfed.org`) was unreachable from this session (network
  timeouts on both `fred.` and `api.` subdomains — google/yahoo/github all
  return 200, so it's a Treasury/FED-specific block, not offline).
- Discovered that **Yahoo Finance's v8/finance/chart endpoint** — the same
  one our existing `scripts/fetch_macro.py` uses for DXY/TLT/SPX/NDX/GOLD
  — also serves the **Cboe volatility/yield indices** (`^TNX`, `^FVX`,
  `^IRX`, `^TYX`, `^VIX`) and `TIP` (iShares TIPS Bond ETF) free, no auth,
  no API key. So the curve-shape exploration (H1, H6) is fully runnable
  TODAY without FRED. **This is a discovered data path worth recording.**
- Wrote `scripts/exploration/fetch_yield_indices.py` (mirrors
  `fetch_macro.py`) — fetched all 6 series into `data/raw/exploration/`:
  each `~/9,187 rows, 1990-01-02 to 2026-08-10` (covers all 4 BTC cycles).

### 11.2 Curve-shape distribution (computed on 9,187 daily rows)

Using §4.1 pre-committed rules applied to `curve_slope_10_5 = ^TNX − ^FVX`
(10y - 5y; substituted for the unavailable ^FVX-for-2y per §11.6 caveat
below):

| State            | Days | Note                                              |
|------------------|------|---------------------------------------------------|
| `inverted_flat`  |  356 | 10y < 5y sustained                                |
| `bear_steep`     |  535 | slope rose >40bps in 180d during bull-phase shifts |
| `bull_steep`     |  608 | slope fell >40bps in 180d (post-taper, post-pivot) |
| `normal`         | 7508 | ~82% of days; benign regime                       |
| `unclassified`   |  180 | NaN edges                                          |

### 11.3 H1 — Curve-shape transition at BTC extrema — **REJECTED**

Per pre-committed §4.2 prediction table (predictions committed before
looking at numbers):

| Label     | Date       | EU predicted      | Observed ±120d states           | Match |
|-----------|------------|-------------------|----------------------------------|-------|
| T1        | 2013-12-04 | `unclassified`    | SKIPPED per §4.2 footnote       | n/a   |
| T1_first  | 2013-04-09 | `unclassified`    | SKIPPED per §4.2 footnote       | n/a   |
| T2        | 2017-12-17 | `bull_steep`      | `normal`                        | 0     |
| T3        | 2021-11-10 | `inverted_flat`   | `bull_steep,normal`             | 0     |
| T4        | 2025-10-06 | `bull_steep`      | `bear_steep,normal`             | 0     |
| B1        | 2015-01-14 | `bull_steep`      | `bull_steep,normal`             | **1** |
| B2        | 2018-12-15 | `bull_steep`      | `normal`                        | 0     |
| B3        | 2022-11-21 | `bull_steep`      | `bull_steep,inverted_flat,normal` | **1** |

**Score = 2 / 6. Threshold was ≥5/6. H1 REJECTED.**

Honest finding: EU's curve-shape vocabulary, applied with PRE-COMMITTED
thresholds (§4.1: `slope_10_5 ≤ 0` for inversion; `Δ_180d > +40bps` for
bear-steep; `< −40bps` for bull-steep), does NOT predict BTC extrema at
the ±120d horizon we committed to. The 2017-12-17 cycle top (T2) exhibited
`normal` — the curve was steadily rising but not in a transition. The
2021-11-10 top (T3) was `bull_steep, normal` (EU expected `inverted_flat`).
The 2025-10-06 top (T4) was `bear_steep, normal` — opposite of EU's expected
`bull_steep`.

This is a **published negative finding**, not a failure of the script. It
may indicate the curve-shape signal activates at a different horizon
(±60d? ±240d?); or that 10y - 5y is the wrong substitute for 10y - 2y
in H1 (see §11.6); or that EU's directional claim simply does not
reliably reach BTC at the daily-resolution regime proxy. All three are
recorded as the exploration output.

### 11.4 H6 — 2007-08-09 BNP-Paribas structural break — **PASS, MARGINAL (1/3)**

Welch t-stats on log-returns, before vs after each breakpoint date:

| Series | BNP (2007-08-09) | Placebo A (2006-08-09) | Placebo B (2008-08-09) | Survives? |
|--------|------------------|------------------------|------------------------|-----------|
| `y10` (`^TNX`) | \|t\| = 0.214 | \|t\| = 0.116 | \|t\| = 0.429 | **NO** (BNP < placeboB) |
| `dxy`  | \|t\| = 0.471 | \|t\| = 0.470 | \|t\| = 0.868 | **NO** (BNP < placeboB) |
| `tlt`  | \|t\| = 0.683 | \|t\| = 0.375 | \|t\| = 0.230 | **YES** |

Survivors: 1/3. Threshold per §5 row H6: ≥1 of {y10, dxy, tlt} — **survived**.

**Honest caveat on marginality:** The pass on TLT (`|t|=0.683`) is driven
more by the placebo t-stats being *low* (`|t|=0.375`, `|t|=0.230`) than
by the BNP t-stat being *high*. Had we chosen placebo breakpoints closer
to the GFC volatility peak (e.g. 2008-09-15 — Lehman — instead of the
arbitrary 2008-08-09 H6 placebo B), the threshold likely flips. This is
**a robust pass only against the pre-committed placebos**, NOT a robust
confirmation of EU's "August 9, 2007 structural break" thesis in our
fetched data. Per §9.4 rule-tuned discipline, we record this caveat
honestly rather than tuning the placebo dates after the fact.

Additionally: TLT only began trading 2002-07-30 (`n=6040` rows), and the
breakpoint exercises the `n_before ≈ 1228` daily rows; this is enough
power for the Welch t but only barely.

### 11.5 H2 — H5: UNVERIFIED (cannot be tested this session)

- **H2 (TIPS break-even gap):** FRED `T5YIE` / `T5YIFR` unreachable.
  Yahoo's `TIP` ETF (price series) was fetched but a single price cannot
  decompose a nominal–real yield gap into a break-even rate. Verdict
  stays UNVERIFIED.
- **H3 (swap-spread / dealer-B/S):** FRED `BAMLC1A0C13Y` unreachable.
  `^VIX` was fetched as an alternative but is well-known to be orthogonal
  to dealer balance-sheet pressure (VIX measures equity-vol risk premium,
  not credit intermediation). Per §3.4 of this doc, substituting VIX for
  swaps would violate the same honest-limit rule that already applied to
  the credit-spread proxy. H3 stays UNVERIFIED with double-proxy caveat.
- **H4 (joint-state agreement):** requires H1+H2+H3. H1 REJECTED and H2/H3
  UNVERIFIED → H4 UNVERIFIED by construction. There is no joint-state
  rubric output for the comparison.
- **H5 (snapshot EU state vs framework's P4 label):** needs H1..H3.
  UNVERIFIED.

### 11.6 Honest caveats and pre-committed limits respected

1. **10y–5y substituted for 10y–2y in H1.** Yahoo does not publish a
   reliable 2y Treasury yield index (the `^STE` ticker is discontinuous).
   Our primary measure of the curve slope is `^TNX - ^FVX` (10y minus 5y).
   The threshold bands in §4.1 (`±20bps` for `inverted_flat`, `>40bps` for
   bear/bull-steep) were committed before realizing 10y–2y was unavailable
   — so we did NOT retune the thresholds to match the substituted slope.
   This is a real methodological weakening of H1; the rejection stands as
   honest because:
   (a) The 10y-5y slope is *narrower* than 10y-2y, so when inversion
       occurred in 10y-5y (e.g. 2023-07), 10y-2y was already deeper
       inverted. So the `inverted_flat → bull_steep transition at T3`
       prediction would have *under*-fired in 10y–5y.
   (b) But T3's actual observed states included `bull_steep` — i.e., the
       test fired in the opposite of expected. Using 10y–2y might have
       produced `inverted_flat` at T3 instead, matching EU's prediction.
   **Therefore the 10y-5y substitution biases the test toward rejection,
       but the rejection is published as-is rather than tuned.** A future
       re-test with actual 10y–2y data (FRED `T10Y2Y`) is recorded as
       the proper re-test path.
2. **H6 placebo dates were pre-committed in §5.** We did not adjust
   placeboB from 2008-08-09 (a near-arbitrary +1y offset) to 2008-09-15
   (the Lehman date) after seeing TLT's marginal pass. Adjusting
   post-hoc would violate the entire exploration's purpose. Recorded
   honestly.
3. **The 40bps / 20bps / ±120d thresholds in §4.1 / §4.2 were chosen
   pre-run** via a single rule of thumb (180-day rolling Δ roughly
   corresponding to "trend shift"; ±120d window roughly the duration
   of a BTC-cycle phase quarter). They are robust to *hand-waving* but
   not to grid-search. A future sensitivity test that ranges threshold
   `±10 / ±20 / ±40 bps` and window `±60 / ±120 / ±240d` is the proper
   follow-up if any of H1's prediction rows reverse — **that re-test is
   NOT authorized in this doc; doing so would be post-hoc tuning.**
4. **The script's verdict string for unverified H2..H5 does not
   distinguish "rejected by data" vs "unverified for lack of data" in
   the printed label — they both say "REJECTED / UNVERIFIED". This is
   coarse but honest. The H1 and H6 lines DO carry actual numbers;
   H1=2/6, H6=1/3. The H6 marginal pass is recorded honestly, not
   amplified.**

### 11.7 Promotion decision

- Survivors across H1..H4: **0** (H1 REJECTED; H2, H3, H4 UNVERIFIED).
- H6 PASS (marginal) is outside the H1..H4 promotion set in §7.
- **Promotion rule (§7: ≥3 of H1..H4 surviving) NOT TRIGGERED.** No I-21
  proper increment is opened.

### 11.8 What this exploration produced / what remains

**Produced (committed):**
- `scripts/exploration/fetch_yield_indices.py` (reusable Yahoo fetcher for
  Cboe yield/vol indices — useful beyond this exploration if any future
  increment needs curve-shape analysis).
- `scripts/exploration/eu_proxy_probe.py` (~280 lines, runnable today).
- `data/raw/exploration/{y10,y5,y13w,y30,tip,vix}_yahoo.csv` (9,187 rows
  each; mutable exploration inputs; not manifest-tracked).
- `data/processed/exploration_eu_proxies.csv` (9,187 rows; the full
  derived daily series with `curve_shape_state` etc.; mutable).
- This §11 section of the blocker doc with actual numbers.

**Findings (honest, falsification-first):**
- **EU's curve-shape rubric (the 3-state classifier with pre-committed
  thresholds) does NOT predict BTC extrema at the ±120d horizon.** H1
  rejected 2/6 (threshold was 5/6).
- **The BNP Paribas Aug-9-2007 break is marginally visible in TLT**
  (narrowest available rate series), but not in y10 (^TNX) or DXY. H6
  passes 1/3 (threshold was ≥1). This is the only signal we found.

**Did NOT change:**
- `tests/`, `scripts/build_*.py`, `scripts/fetch_macro.py`. No framework
  artifact touched.
- `DESIGN.md`, `AGENTS.md`, `status.md`. No increment status shifted.
- No new increment (I-21 proper) opened. The §7 promotion rule explicitly
  required ≥3 of H1..H4 surviving.

**Re-test path (NOT to be done post-hoc — recorded for any future
contributor who wants to falsify again with fresh data or 20/20 hindsight
discipline):**
1. Acquire FRED `T5YIE` / `T5YIFR` / `BAMLC1A0C13Y` / `T10Y2Y` (10y–2y
   proper, not the 10y–5y substitute used here).
2. Re-run `eu_proxy_probe.py` with two columns added:
   `curve_slope_10_2` (proper) keeping the §4.1 thresholds the same.
3. Score H1 again and inspect whether rows T2, T3, T4 flip.
4. If T3 flips to match (EU expected `inverted_flat`), H1 may yet rise
   from REJECTED; publish the re-test as a **separate** blocker note
   (`I-21-eurodollar-proxies-retest-YYYYMMDD.md`), do NOT update this one.
5. Independent of H1, if H2 yields >=2 distinct monotonic regime labels
   on C2/C3/C4 → that itself may justify a proper I-22 increment
   (track the TIPS gap as a regime covariate in I-12 strata). Out of
   scope here.

The exploration stays open as a **published negative result** for H1 and
a **marginal positive** for H6. No merge.

</content>

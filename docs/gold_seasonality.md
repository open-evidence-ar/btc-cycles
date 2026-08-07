# Gold Midterm Election Year Seasonality -- Analysis, Validation & Adaptation Plan

> Source thesis: Benjamin Cowen's gold trajectory analysis for the rest of 2026 and beyond.
> Validated against freshly-fetched Yahoo Finance data (`GC=F`, gold futures, 2000-08-30 to 2026-07-31).

---

## Core Thesis

Gold is currently in a significant correction phase characteristic of US midterm election years. Despite short-term weakness, this behavior is cyclical and sets the stage for a bullish continuation that would carry the metal to new all-time highs toward the end of 2026 and especially during 2027. The model holds that gold recovers from crises and recessions much faster and more vigorously than the S&P 500.

---

## Patterns Identified

### The Midterm Consolidation Cycle (Cowen)

> Midterm year Q3 weakness -> Jul-Oct bottoming -> Q4 stabilization -> Resumption of bull market in year+1

### Key Seasonal Rules (Claimed)

1. **Midterm corrections deep Jul-Oct**, finding the bottom generally between **July and October**.
2. **YTD ROI in 2026 tracks 2018 and 2022** midterm trajectories closely.
3. **Gold recovers post-recession faster than S&P 500** (e.g. 2008 cycle).
4. **Death Crosses (50d/200d)** tend to trigger short-term technical bounces before a definitive bottom forms.

---

## Sources of Patterns

- Historical gold price data back to late 1960s/early 1970s (Cowen's chart history)
- Reference midterm years: 1998, 2002, 2006, 2010, 2014, 2018, 2022
- Specific crises: 2008 financial crisis, 2025 tariff episode
- Long-cycle bull markets: 1999-2011, current cycle from 2015 trough

---

## Models Used

1. **Time-Based Analysis (Time-only model)**: Average timing of mid-term lows across all midterm years since 1970.
2. **Bull Market Support Band**: 20-month SMA + 21-month EMA on monthly closes. Currently claimed at $3,824-$3,841.
3. **Valuation against S&P 500**: Gold/SPX ratio to identify overbought/oversold conditions.
4. **Investing Through the Cycles (ITC)**: 10-12 year gold cycle framework with three phases -- Initial Impulse, Midterm Consolidation, Final Parabolic Move.

---

## Validation Against Local Data

### Data Sources Used (newly fetched for this analysis)
- `data/raw/gold_yahoo_2026-08-01.csv` -- GC=F gold futures, 6,587 rows from 2000-08-30 to 2026-07-31 (NEW -- added to fetch_macro.py)
- `data/raw/spx_yahoo_2026-08-01.csv` -- SPX refresh
- `data/raw/dxy_yahoo_2026-08-01.csv` -- DXY (gold inverse proxy)
- `data/raw/ndx_yahoo_2026-08-01.csv` -- NDX refresh

### Claim-by-Claim Validation

| Claim | Verdict | Evidence |
|---|---|---|
| Gold ~$4,000 currently | CONFIRMED | 2026-07-31 close = $4,049.10 |
| ~28% recent drop | CONFIRMED | From intraday ATH $5,586.20 on 2026-01-29, latest close drawdown = -27.52% (close-based ATH: -23.87%) |
| Bull support band $3,824-$3,841 (20-mo SMA / 21-mo EMA) | CONFIRMED | Current 20-mo SMA = $3,813.13, 21-mo EMA = $3,829.66 (slight divergence from Cowen due to data freshness) |
| 2026 ROI tracks 2018 and 2022 | NOT SUPPORTED | 2026 spiked +20% in Feb then crashed; 2018 was a slow grind down from Jan; 2022 was choppy down all year. Trajectories diverge sharply |
| Gold recovers from recessions faster than SPX | CONFIRMED | Post-2008: gold recovered to pre-crisis peak on 2009-09-16 vs SPX on 2013-04-10 (gold 3.5 years faster) |
| Jul-Oct midterm bottom pattern | WEAKLY SUPPORTED | Only 2018 (Aug 16 trough) cleanly fits Jul-Oct; 2014 (Nov 7) and 2022 (Nov 3) bottom in November; 2002/2006/2010 bottom in Jan-Feb |
| Aug/Sep seasonal weakness (mirrors SPX) | NOT APPLICABLE | Gold's Aug avg = +1.97%, Sep avg = +0.69% (both positive). Gold's worst month on avg is June (-1.27%). Aug/Sep weakness is SPX-specific, NOT gold-specific |
| Death Cross precedes bounce/bottom | PARTIALLY SUPPORTED | Most recent gold death cross: 2026-07-01 @ $4,068 (current period). Past death crosses (2021-12, 2022-01, 2022-07, 2023-09, 2026-07) showed mixed bounces |
| midterm Jul-Oct correction 10-20% | WEAKLY SUPPORTED | Only 2014 (-11.7%) and 2022 (-8.9%) Jul-Oct declines match magnitude; 2002/2006/2010/2018 actually had Jul-Oct gains |

### Gold Monthly Average Returns (2000-2026)

| Month | Avg | n |
|---|---|---|
| Jan | +2.32% | 26 |
| Feb | +1.03% | 26 |
| Mar | -0.09% | 26 |
| Apr | +1.08% | 26 |
| May | +0.66% | 26 |
| **Jun** | **-1.27%** | 26 | (only clearly negative month)
| Jul | +0.85% | 26 |
| Aug | +1.97% | 26 |
| Sep | +0.69% | 26 |
| Oct | +0.12% | 26 |
| Nov | +1.23% | 26 |
| Dec | +1.02% | 26 |

**Key finding**: Gold's seasonality is INVERSE to SPX's. SPX is weak Aug/Sep; gold is weak Jun. They are not seasonal proxies for each other.

### Gold Midterm Year Trough Dates (lowest intraday low)

| Year | Trough Date | Price | Fits "Jul-Oct"? |
|---|---|---|---|
| 2002 | 2002-01-24 | $278.10 | NO (January) |
| 2006 | 2006-01-03 | $518.60 | NO (January) |
| 2010 | 2010-02-05 | $1,045.20 | NO (February) |
| 2014 | 2014-11-07 | $1,133.00 | NO (November -- Cowen caveat) |
| 2018 | 2018-08-16 | $1,161.40 | YES (August) |
| 2022 | 2022-11-03 | $1,615.10 | NO (November) |
| 2026 | 2026-06-30 (so far) | $3,962.50 | TBD (year incomplete) |

### 2026 YTD Trajectory vs Prior Midterms

| Year | M1 | M2 | M3 | M4 | M5 | M6 | M7 | Year End |
|---|---|---|---|---|---|---|---|---|
| 2018 | +2.8% | +1.0% | +1.6% | +1.1% | -0.2% | -3.9% | -6.0% | -1.8% |
| 2022 | -1.9% | +3.8% | +6.5% | +4.3% | +0.7% | -1.4% | -3.7% | -0.6% |
| **2026** | **+8.4%** | **+20.2%** | **+6.8%** | **+6.1%** | **+4.8%** | **-7.5%** | **-6.9%** | TBD |

2026's Feb spike to +20% does NOT match either 2018 or 2022 trajectories. The claim that 2026 "closely tracks 2018 and 2022" is unsupported by monthly YTD data.

### Post-2008 Crisis Recovery: Gold vs SPX

| Metric | Gold | SPX |
|---|---|---|
| Pre-crisis peak (intraday) | 2008-03-17 @ $1,014.60 | 2007-10-11 @ $1,576.09 |
| Trough (intraday low) | 2008-10-24 @ $681.00 | 2009-03-06 @ $666.79 |
| Drawdown (peak-to-trough) | -32.88% | -57.69% |
| Recovery to pre-crisis peak | 2009-09-16 | 2013-04-10 |

**Confirmed**: Gold recovered ~3.5 years faster than SPX from the 2008 crisis and suffered a shallower drawdown.

### Long-Term Bull Market Context

- 2000-08-30 (start of data): gold = $273.90
- 2011-09-06 (bull cycle peak): gold = $1,911.60 -> 7.0x multiple in 11 years
- 2015-12-03 (cycle trough): gold = $1,046.20 (drawdown from 2011 peak = -45.3%)
- 2026-07-31 (current): gold = $4,049.10 -> 3.87x multiple from 2015 trough

The current cycle from the 2015 bottom is at ~3.9x over 10.5 years -- past the historical average mid-cycle but below the 2011 peak multiple of 7x seen in the prior 11-year bull market.

### Death Cross Status

Most recent gold 50d/200d death cross: **2026-07-01 @ $4,068.30**
Past death cross events (since 2005):
- 2021-12-02, 2022-01-31, 2022-07-06, 2023-09-29, **2026-07-01**

Gold is currently in a freshly-formed death cross. The thesis that this typically precedes a short-term bounce before a definitive bottom is being TESTED RIGHT NOW.

---

## Rational Predictions

Based on the validated evidence:

- **Bottoming window**: Jun-Oct 2026 (gold actually bottomed intra-month June at $3,962; observed sideways action Jan-Jul). Note: only 1 of 6 prior midterm years (2018) cleanly fit the Jul-Oct window.
- **Support level**: $3,813-$3,830 (current 20-mo SMA / 21-mo EMA band). Violation would invalidate the bull market support assumption.
- **Severity risk**: If bottoming extends to November (as in 2014 and 2022), drawdown could exceed -28% before exhaustion.
- **2027 trajectory**: Assuming the bottom forms and holds bull market support, gold would resume uptrend into 2027 with potential to exceed the $5,586 ATH set January 2026.
- **Cycle maturity**: Current 3.87x from 2015 trough suggests the gold bull is in mid-to-late phase vs the 7x seen in 1999-2011.

---

## Distinction Between Observation, Inference, and Speculation

| Type | Content |
|---|---|
| **Observation** | Gold closed 2026-07-31 at $4,049; down 27.5% from $5,586 ATH (2026-01-29); 20-mo SMA at $3,813; death cross on 2026-07-01 |
| **Inference** | Because gold's bull support band has held in prior corrections, $3,800 is a high-probability floor. Because the current cycle follows post-2015 trajectory, a retest of the ATH is likely in 2027 |
| **Speculation** | The 2027 move will be "parabolic" and the bull market will run to early 2030s. The current death cross will produce a bounce imminently (no quantitative evidence this occurs on a consistent schedule) |

---

## Connections Between Sources/Models

- **Gold vs SPX recovery asymmetry**: Gold's faster post-crisis recovery (2009 vs 2013) is the empirical anchor for the gold/SPX rotation thesis
- **DXY inverse**: DXY shows no decisive Aug/Sep pattern (Aug +0.09%, Sep -0.17% avg) -- the SPX Aug/Sep weakness does not transfer to DXY, and consequently does not transfer predictably to gold via the dollar channel
- **Crypto cycle alignment**: BTC's B4 (next bear-bottom, projected ~2026-10-22 per current model) FALLS WITHIN the Cowen gold Jul-Oct bottoming window. Both B4 (crypto) and the gold midterm bottom could coincide in Q4 2026.

---

## Adaptation Plan for Non-Crypto Prediction Models

### 1. Add Gold to the Macro Cycle Pipeline

Gold is now fetched via `fetch_macro.py` (added `"gold": "GC=F"`). Build gold cycle metrics analogous to SPX using BTC halving anchors.

**Target files**:
- `scripts/build_alt_cycle_metrics.py` -- extend to process gold
- `data/processed/alt_cycle_metrics.csv` -- add gold rows
- `tests/test_macro_provenance.py` -- add gold provenance gate

### 2. Apply I-19 Macro 2-Stage Model to Gold

Use the `macro_2_stage_own_shape` machinery (currently applied to SPX/NDX/DXY/TLT) to project gold B4/C5 from the macro's own drawdown & multiplier series.

**Target files**:
- `scripts/build_alt_next_cycle_zones.py` -- add gold branch
- `data/processed/alt_next_cycle_zones.csv` -- add gold B4/accumulation/distribution/exit zones
- `docs/blockers/I-19-macro-2stage.md` -- note gold added

### 3. Integrate 20-Month SMA / 21-Month EMA Support Band as a Cross-Check

Unlike SPX/NDX (which use drawdown power-law), gold has a long-validated bull market support band (20-mo SMA / 21-mo EMA). This could become a secondary valuation cross-check on the I-19 2-stage B4 projection.

**Target files**:
- `scripts/build_alt_next_cycle_zones.py` -- compute monthly SMA/EMA cross-check band for gold
- Add a `support_band_low` / `support_band_high` column to alt_next_cycle_zones.csv for gold rows

### 4. Use Gold/SPX Ratio as a Macro Regime Indicator

Gold/SPX ratio historically rises during crisis and equity-bear regimes. Tracking this ratio in the existing I-12 macro-regime robustness check could improve regime classification.

**Target file**: `scripts/build_regime_robustness.py`

### 5. Cross-Align With Crypto B4 Timing Window

Cowen's Jul-Oct gold bottoming window overlaps with BTC's projected B4 center 2026-10-22. This confluence could be used as a confirmation signal: if gold AND SPX both show Q3-Q4 weakness, tighten the crypto B4 confidence band.

**Target file**: `scripts/build_next_cycle_zones.py` -- multi-asset confluence cross-check

---

## Recommended Implementation Order

1. **DONE**: Add `gold` to `fetch_macro.py` ASSETS dict (symbol = GC=F)
2. **DONE**: Refresh macro data through 2026-07-31 (all assets)
3. **DONE**: Extend alt cycle metrics -- gold added to `alt_cycle_metrics.csv` using BTC halving anchors (I-05 machinery)
4. **DONE**: Add gold provenance test -- `tests/test_macro_provenance.py` gates gold data (`test_gold_covers_two_decades`; `MACRO_SYMBOLS` now 5 assets)
5. **DONE**: Apply I-19 to gold -- gold macro 2-stage branch in `build_alt_next_cycle_zones.py` (mode `macro_2_stage_own_shape`; C4 top Rule-T = 2026-01-29 @ $5,318; B4 band $3,242-$4,787, timing 2027-09-14..2027-09-29 = BTC B4 2026-10-22 +337d alt lag)
6. **DONE**: Compute 20-mo SMA / 21-mo EMA band as a side-by-side support cross-check -- `support_band_low`/`support_band_high` columns on gold's `bear_bottom` zone row ($3,813.13 / $3,829.66 @ 2026-07-31). Verdict: WARN (B4 projects below band -- bull-support invalidation risk)
7. **DONE**: Add chart C8g (gold next-cycle prediction with support band overlay) in `build_charts.py` -- replaces the original "C9 (or C10)" plan; C9 remains the cross-asset timing chart
8. **DONE**: Re-run pytest gates -- full suite 180 tests green (test_macro_provenance.py, test_alt_timing.py, test_release_checklist.py updated for gold; chart_snapshots.json refreshed)

---

## Compact Conceptual Model

**Investing Through the Cycles (ITC)** -- gold 10-12 year cycle:

> Initial Impulse (parabolic multi-year run) -> Midterm Consolidation (deep but cyclic drawdown) -> Final Parabolic Move (cycle-ending blow-off)

The model treats midterm-year corrections as **cleansing events** rather than cycle-terminators. Gold historically has shown:
- Faster recovery from crises than equities
- Bull market support at the 20-mo SMA / 21-mo EMA band
- Long-cycle multiple expansion (7x in prior 1999-2011 bull market; 3.87x so far in current 2015-2026 cycle)

---

## Key Findings Summary

**What Cowen got right (validation passed)**:
- Current price (~$4,000) and recent drawdown (~-28%) -- precise
- Bull support band at $3,813-$3,830 (vs claimed $3,824-$3,841) -- extremely close, small divergence from data freshness
- Gold recovers from crises faster than SPX -- strongly confirmed (2009 vs 2013 for 2008 crisis)
- Death cross just formed (2026-07-01) -- observationally accurate

**What Cowen got wrong (validation failed)**:
- "2026 ROI tracking 2018 and 2022" -- divergent trajectories (2026 spiked +20% in Feb then crashed; 2018/2022 grinded lower)
- "Jul-Oct midterm bottom" -- only 1 of 6 prior midterm years (2018) cleanly fits; 4 of 6 bottomed in Jan-Feb or Nov
- Implicit Aug/Sep seasonal transfer from SPX to gold -- gold's Aug/Sep returns are positive on average; gold's only clearly negative month is June
- "10-20% midterm correction" magnitude -- only 2014 (-11.7%) and 2022 (-8.9%) fit; 4 of 6 had Jul-Oct GAINS

**Implication**: The gold thesis is *partially* right on observations and price levels but oversimplified on seasonal timing. The Aug/Sep SPX seasonal pattern does NOT generalize to gold; gold is a June-seasonal asset.

---

## Key References

- Fetched gold data: `data/raw/gold_yahoo_2026-08-01.csv`
- SPX refresh: `data/raw/spx_yahoo_2026-08-01.csv`
- Fetcher extension: `scripts/fetch_macro.py` (added `"gold": "GC=F"`)
- I-19 macro 2-stage model: `docs/blockers/I-19-macro-2stage.md` and `scripts/build_alt_next_cycle_zones.py`
- Cycle metrics builder: `scripts/build_alt_cycle_metrics.py`
- Macro provenance tests: `tests/test_macro_provenance.py`
- Crypto B4 timing: `data/processed/next_cycle_zones.csv` (BTC B4 center 2026-10-22)
- Events table: `data/events.csv` (BTC halving anchors)
- Spy seasonality comparison: `docs/spy_seasonality.md` (the SPY Aug/Sep pattern is NOT replicated by gold)

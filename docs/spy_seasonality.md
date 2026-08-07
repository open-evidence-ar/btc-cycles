# S&P 500 Midterm Election Year Seasonality — Analysis, Validation & Adaptation Plan

---

## Core Thesis

The S&P 500 is prone to a significant seasonal correction of 10-20% during the August-September timeframe of midterm election years. This equity market weakness often serves as the catalyst for Bitcoin to find its major market cycle bottom during the latter half of the year.

---

## Patterns Identified

### The Midterm Distribution Cycle

> June (Shallow Dip) -> July (Relief Rally / New Highs) -> August/September (10-20% Correction) -> Q4 (Market Weakness / Asset Bottoming)

### Key Seasonal Rules

1. **August & September are the only months that are red (negative) on average** across the full SPX history.
2. **July has been positive every July since 2015** — a reliable summer buffer.
3. **Midterm years follow a specific sequence**: shallow June dip -> July recovery -> Aug/Sep correction -> Q4 weakness.
4. **The correction magnitude** is typically 10-20% from the June/July peak to the Sept/Oct trough.

---

## Sources of Patterns

- **Monthly Average Returns**: Analysis of the S&P 500 throughout its entire history shows that August and September are the only months that are negative on average.
- **Specific Midterm Case Studies**: Detailed year-over-year (YoY) and year-to-date (YTD) ROI comparisons focusing on the midterm years of 2014, 2018, and 2022.

---

## Models Used

1. **Distribution Phase Model**: A multi-step process where the market sees a shallow drop (a few weeks), a rally back to new highs, a period of sideways movement, and finally a larger distribution drop.
2. **Intertwined Cycle Model**: The four-year Bitcoin cycle is aligned with the stock market midterm year corrections, with Bitcoin bottoming being triggered by the seasonal volatility in equities.

---

## Validation Against Local Data

### Data Sources Used
- data/raw/spx_yahoo_2026-07-20.csv — SPX daily OHLCV from Yahoo Finance (1990-01-02 to 2026-01-30)
- data/raw/ndx_yahoo_2026-07-20.csv — NDX daily OHLCV from Yahoo Finance
- data/raw/dxy_yahoo_2026-07-20.csv — DXY daily OHLCV from Yahoo Finance
- data/raw/tlt_yahoo_2026-07-20.csv — TLT daily OHLCV from Yahoo Finance

### Claim-by-Claim Validation

| Claim | Verdict | Evidence |
|---|---|---|
| Aug/Sep are the only negative months on average | CONFIRMED | Aug avg = -0.49%, Sep avg = -0.72%; all other months positive |
| July positive every July since 2015 | CONFIRMED | All 11 July monthly returns (2015-2025) are positive |
| 2022: top mid-Aug, 19% drop | PARTIALLY SUPPORTED | Drop was ~14% from June peak to Sept trough |
| 2018: top mid-Sep, 20% drop | NOT WELL SUPPORTED | Top was late Jul/Aug, not mid-Sep; drop ~14% |
| 2014: Sept 10% correction | NOT SUPPORTED | Sept 2014 monthly return was -1.6%; no 10% correction |
| 2010: deviated from pattern | PARTIALLY SUPPORTED | Aug/Sep drop was -6.3% (smaller than claimed 10-20%); bigger drop was May-June |

### NDX Midterm Year Aug/Sep Pattern

| Year | Peak | Trough | Drop |
|---|---|---|---|
| 2010 | 1913.5 (Jun 18) | 1767.4 (Aug 31) | -7.6% |
| 2014 | 3986.2 (Jul 23) | 3857.9 (Aug 7) | -3.2% |
| 2018 | 7508.6 (Jul 25) | 7272.9 (Aug 1) | -3.1% |
| 2022 | 12948.0 (Jul 29) | 10971.2 (Sep 30) | -15.3% |

NDX shows the same directional pattern but with weaker magnitude than SPX.

### Data Freshness Note

SPX data currently only extends to **2026-01-30**. We are in August 2026, which is a midterm year. The etch_macro.py PERIOD2 is hardcoded to March 2026 (Unix 1770000000) and needs updating to capture current market data for real-time validation of the 2026 midterm pattern.

---

## Rational Predictions

Under the assumption that the current year (2026) follows the pattern of the last three midterm years:

- **Correction Timing**: A top should be expected in mid-August or mid-September 2026.
- **Magnitude**: The predicted drop is estimated at 10-20% from the summer peak.
- **Bitcoin Alignment**: If the S&P 500 enters its typical seasonal correction, Bitcoin is predicted to show simultaneous weakness and potentially hit its major market cycle bottom (B4).

---

## Distinction Between Observation, Inference, and Speculation

| Type | Content |
|---|---|
| **Observation** | S&P 500 dropped 19% in Aug 2022; July returns have been positive since 2015; Aug/Sep are negative on average over history |
| **Inference** | Because 2014, 2018, and 2022 followed a similar trajectory, the current midterm year is likely to follow suit |
| **Speculation** | The upcoming correction might be triggered by the semiconductor industry due to elevated valuations and specific sector fears |

---

## Connections Between Sources/Models

The analysis bridges traditional equity seasonality and cryptocurrency cycles:

- **Equity seasonality** provides the macro environment (the back half of the midterm year correction) that allows the crypto market to complete its specific four-year cycle bottoming process.
- **Broad index performance** connects to specific sector health, particularly the semiconductors, as a potential lead indicator for the wider market seasonal decline.
- **Crypto cycle projections** (B4/C5 zones) can be conditionally adjusted when the equity seasonal correction signal triggers.

---

## Adaptation Plan for Non-Crypto Prediction Models

### 1. Seasonal Overlay for C8 Macro Two-Stage Projection

The existing I-19 macro_2_stage_own_shape model in uild_charts.py projects SPX B4/C5 using the macro's own drawdown/multiplier series. A **seasonal timing adjustment** could be added: instead of projecting B4 purely from the BTC-anchored timing, shift the B4 window to **Aug-Sep of the midterm year** when the SPX shows the seasonal correction pattern.

**Target files**:
- scripts/build_charts.py — uild_c8_macro() function
- scripts/build_alt_next_cycle_zones.py — _project_asset_chain() macro branch

### 2. Refine SPX B4 Zone Timing

lt_next_cycle_zones.csv already has SPX B4 projected to 2027-04-16. The midterm seasonality suggests the **actual seasonal correction** (10-20% drop) in Aug/Sep 2026 could serve as an early signal that the B4 bear-bottom process is beginning — potentially pulling the B4 window forward.

**Target files**:
- data/processed/alt_next_cycle_zones.csv (SPX bear_bottom zone)
- scripts/build_alt_next_cycle_zones.py

### 3. Aug/Sep as a Leading Indicator for Crypto Cycle Bottoms

The thesis that equity seasonal weakness triggers crypto bottoms can be operationalized: if SPX enters its typical Aug/Sep correction, this could be used as a **conditional trigger** to tighten the crypto B4 zone bands or adjust the C5 top projection timing.

**Target files**:
- scripts/build_next_cycle_zones.py — cross-check logic
- scripts/build_alt_next_cycle_zones.py — macro conditional logic

### 4. NDX Semiconductor Sub-Sector as a Seasonal Catalyst

The summary speculates about semiconductors as a lead indicator. NDX data is available locally and could be used to build a **sector-seasonal model** that feeds into the macro projection. Specifically, tracking NDX semiconductor component performance in June-July could serve as a signal for whether the Aug/Sep correction is likely to materialize.

**Target files**:
- New script or addition to scripts/build_charts.py
- **Data source**: data/raw/ndx_yahoo_*.csv (NDX includes semiconductor-heavy components)

---

## Recommended Implementation Order

1. **Fetch fresh SPX/NDX/DXY/TLT data** — update etch_macro.py PERIOD2 to capture current market data through Aug 2026
2. **Build a seasonal adjustment module** — add Aug/Sep midterm correction probability to the C8 macro chart and zone projections
3. **Update lt_next_cycle_zones.csv** SPX B4 zone — incorporate the seasonal timing signal to potentially pull forward the B4 window
4. **Add NDX semiconductor sub-sector analysis** — track NDX semiconductor performance as a leading indicator for the Aug/Sep correction

---

## Compact Conceptual Model

**The Midterm Distribution Cycle:**

> June (Shallow Dip) -> July (Relief Rally / New Highs) -> August/September (10-20% Correction) -> Q4 (Market Weakness / Asset Bottoming)

This cycle suggests that summer strength is a temporary distribution before a structural seasonal adjustment that resets prices for both stocks and Bitcoin.

---

## Key References

- Historical S&P 500 Price Data: data/raw/spx_yahoo_*.csv
- NDX Price Data: data/raw/ndx_yahoo_*.csv
- I-19 Macro 2-Stage Model: docs/blockers/I-19-macro-2stage.md
- Cycle Metrics: data/processed/alt_cycle_metrics.csv
- Forward Ranges: data/processed/alt_forward_ranges.csv
- Zone Projections: data/processed/alt_next_cycle_zones.csv
- Events Table: data/events.csv

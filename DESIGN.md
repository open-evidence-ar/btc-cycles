# Crypto Cycle Correlation Framework — Design Document

> A financial white-paper framework for studying **Bitcoin cycle dynamics** and their correlation with select altcoins (ETH, SOL, XRP) and global macro assets (SPX, NDX, DXY, TLT). The goal is to identify the *time ranges*, *entry* and *exit* zones of the **next BTC cycle** from a long-term, holistic perspective — not to build an automated trading bot.

---

## 0. Visual Context — Source Chart Reference (inspiration only)

The intuitive version of the analysis is captured in the source chart `BTCUSD_2026-07-19_19-50-22.png` (TradingView, weekly log scale, ~mid-2016 to Apr-2026, Bitstamp). It is provided as **inspiration, not as a source of truth.** Its dates, price zones and day-counts are never adopted as priors; they are tracked for side-by-side reconciliation against the framework's own recomputed values (procedure in §3.2.5).

**Chart interpretation** (what we see, not what we believe):

- **Chart type:** Weekly log candlestick of BTC/USD, with moving-average overlays (yellow/orange/blue/white) and a green shaded "standard cycle" projection band in the background.
- **Event markers:** Vertical dashed red lines at the 2017-12 and 2021-11 cycle tops, each tagged with a day-count from the most recent halving:
  - `520d` near 2017-12 top (≈ H2 2016-07-09 → 2017-12-17)
  - `336d` near the 2021-04 local high (≈ H3 2020-05-11 → 2021-04-14)
  - `550d` near the 2021-11 parabolic top (≈ H3 2020-05-11 → 2021-11-10)
- **Price zones (the chart author's hand-drawn projection for the next cycle):**
  - **TOP ZONE:** ~$133,444 – $180,000
  - **BOTTOM ZONE:** ~$19,075 – $28,826
- **Pattern overlay:** White hand-drawn Head & Shoulders spanning the current cycle, with current price ~$64k labelled as the right "Shoulder" or "Bottom".
- **Current snapshot (chart date 2026-07-19):** O $63,744 · H $65,518 · L $61,750 · C $64,681 (+1.47%). Secondary panel: BTC dominance = 39.85%.
- **Narrative implied by the chart:** Bitcoin is depicted as late-cycle / in distribution within a Head-and-Shoulders top, with the next leg probabilistically resolving toward the BOTTOM ZONE.

**How the chart maps to the framework** (mapping targets, not adopted values):

| Chart element | Framework counterpart (recomputed, not copied) | Defined in |
|---|---|---|
| `520d`, `336d`, `550d` day-counts | `D_halving_to_top` / `D_halving_to_first_high` per cycle, recomputed in I-05 | §5.1, §3.2.4 |
| TOP ZONE $133k–$180k | Forward price band for C4's top, derived from mean/IQR of `mult_bottom_to_top` across C1-C3 applied to B3 ($15,652), in I-09/I-10 | §5.3, §5.4 |
| BOTTOM ZONE $19k–$28k | Forward bear-low band for C4, derived from `drawdown_pct` statistics applied to C4's projected top, in I-10 | §5.4 |
| Head-and-Shoulders overlay | **Out of v1** model. Tracked as optional pattern-recognition extension in §11 Open Questions | §11 |
| BTC.D 39.85% secondary panel | Optional BTC-dominance series (I-04b), tracked in §11 Open Questions | §11 |

**Reconciliation policy:** every chart value is confronted with a framework-recomputed value. The reconciliation lives at `data/processed/folklore_reconciliation.csv` and is rendered as a table in `sections/05-predictive-ranges.md`. A mismatch does not invalidate the framework — it publishes the chart's intuition as a falsified hypothesis.

---

## 1. Goals & Non-Goals

### 1.1 Goals

1. **Axiomatic frame:** Treat the Bitcoin halving cycle as a *real, recurring structural phenomenon* (~4-year supply-shock cycle) and use bottoms/tops as inflection points.
2. **Pattern detection:** Identify regularities around the cycle — in both **time** (days from halving to top, top to bottom, halving to bottom) and **price** (relative expansion/contraction, drawdown depth) — even if price-time relationships are imperfect.
3. **Cross-asset study:** Measure how ETH, SOL, XRP and macro assets (SPX, NDX, DXY, TLT) **co-move** with BTC across cycle phases, and whether they lead, lag, confirm or diverge.
4. **Predictive ranges:** Use the **average of prior cycles** to define *reasonable forward ranges* for the next cycle: time windows for tops, bottoms, accumulation zones and distribution zones.
5. **Communication artifact:** Publish findings as a Jekyll-based GitHub Pages site — a transparent financial white paper with reproducible charts, datasets and methodology.

### 1.2 Non-Goals (explicit)

- **Not an automated trading bot.** No real-time execution, no exchange APIs, no order placement.
- **Not short-term / intraday forecasting.** Horizon is months-to-years; the predictive unit is the **next full cycle**, not the next session.
- **Not financial advice.** The site is a research artifact; no portfolios, no position sizing, no risk-budget recommendations.
- **Not a black-box ML signal.** Methods must remain interpretable (averages, distributions, correlations, regime tabulation). Deep models only as sensitivity/sanity checks.

---

## 2. Core Hypothesis & Conceptual Frame

### 2.1 The central hypothesis

Bitcoin’s supply schedule produces a **deterministic supply-shock approximately every 4 years** (halving). History suggests a recurring structure around each halving:

```
Bottom  ->  Halving  ->  Blow-off Top  ->  Bear Bottom  ->  (next Halving)
   |          |              |                |
   cycle      cycle          cycle           cycle
   low        start          peak            low
```

For each prior cycle we can measure:

- `D_prev_bottom_to_halving` — days from the cycle's pre-halving low to the halving date.
- `D_halving_to_top` — days from halving to the cycle's parabolic top.
- `D_top_to_next_bottom` — days from the cycle's top to the next bear-market low (which doubles as next cycle's pre-halving bottom).
- `D_halving_to_first_high` (optional, only when a cycle exhibits a double-top) — days from halving to the first local high before the final parabolic top (observed for C3: 338d; for C4: TBD).
- `mult_bottom_to_top` — multiplicative price move from cycle's own bottom to own top.
- `drawdown_pct` = `1 - (next_bear_bottom / own_top)` — peak-to-trough percentage decline within the cycle.

The **mean (and distribution) of these metrics across prior cycles** yields forward ranges for the next cycle. The framework does not assume exact repetition — it assumes a **bounded range** with quantified uncertainty.

### 2.2 Cross-asset hypothesis

Whether or not price-time repeats, BTC cycle phases (risk-on liquidity expansion vs risk-off contraction) should manifest as **correlated shifts** in:

- **Equities (SPX, NDX):** high-beta risk proxies; expected to lead/confirm at cycle tops and to recover alongside BTC bottoms.
- **DXY (US Dollar Index):** inversely correlated with BTC during BTC up-phases (strong dollar → liquidity-tight regime → BTC weakness), and positively correlated at selected turning points.
- **TLT (20+yr Treasury ETF):** long-duration rate proxy; falling rates (rising TLT) historically supportive of BTC cycle tops; rising yields (falling TLT) can constrain risk assets.

Correlations are studied **conditional on cycle phase**, not as a single global number — because a 0.3 correlation averaged over a full cycle may hide a +0.7 correlation at tops and -0.5 at the lows.

---

## 3. Data Sources & Panel Definition

### 3.1 Primary panel

| Asset | Role | Series needed | Source candidates |
|---|---|---|---|
| **BTC** | Cycle anchor | Daily OHLC, USD, from 2010-07-17 (or earliest feasible) | CoinGecko, CryptoCompare, CryptoDataDownload, Binance |
| **ETH** | Top alt / smart-contracts | Daily OHLC, from 2015-08-07 | CoinGecko, CryptoCompare |
| **SOL** | Modern L1 alt | Daily OHLC, from 2020-04-10 | CoinGecko |
| **XRP** | Payments L1 / longest alt history | Daily OHLC, from 2013-08-04 | CoinGecko, CryptoCompare |
| **SPX** | US equity benchmark | Daily close, from 1990 | Yahoo Finance, Stooq, FRED |
| **NDX** | Nasdaq 100 | Daily close, from 1985 | Yahoo Finance, Stooq |
| **DXY** | US Dollar Index | Daily close, from 1971 (DXY from 1973) | Yahoo Finance, FRED, Investing |
| **TLT** | 20+yr US Treasuries ETF | Daily OHLC, from 2002-08-22 | Yahoo Finance, Stooq |

### 3.2 Cycle-event table — REAL HISTORICAL DATA

The table below is **populated from verified historical data** (block-header timestamps for halvings; CoinGecko daily-close OHLC for tops/bottoms), not estimated. These are the values `data/events.csv` starts from; the framework refines them only if reconciliation against an auditable daily-close rule (§5.1) finds a ±1-day correction.

#### 3.2.1 Halvings (block-header UTC timestamp)

| # | Block | Date (UTC) | Subsidy (BTC) |
|---|---|---|---|
| H1 | 210,000 | 2012-11-28 | 50 → 25 |
| H2 | 420,000 | 2016-07-09 | 25 → 12.5 |
| H3 | 630,000 | 2020-05-11 | 12.5 → 6.25 |
| H4 | 840,000 | 2024-04-20 | 6.25 → 3.125 |
| H5 | ~1,050,000 | ~2028-04 (projected from ~10-min cadence; refined as block-height ETA firms up) | 3.125 → 1.5625 |

Sources: mempool.space / block header timestamps.

#### 3.2.2 Cycle tops (daily-close high; first-high = local high before the final parabolic high)

| Cycle | First-high date | First-high price | Final-top date | Final-top price | Note |
|---|---|---|---|---|---|
| C1 | 2011-06-08 | $31.91 | 2011-06-08 | $31.91 | single top (early era) |
| C2 | 2013-04-09 | $260.00 | 2013-12-04 | $1,150.00 | two distinct peaks, 8-month separation |
| C3 | — | — | 2017-12-17 | $19,497.00 | one parabolic top |
| C4 | 2021-04-14 | $64,863 | 2021-11-10 | $69,044 | "double top" with ~7-month separation |

Sources: CoinGecko daily-close. (Note: some sources cite 2021-04-14 vs 2021-04-27 for the daily-close high within ±2d; reconciliation lock in §5.1 picks CoinGecko's exact close.)

#### 3.2.3 Cycle bottoms (bear-market low = lowest daily close between consecutive tops, before the next halving)

| Bottom | Date | Price (close) | Belongs to / role |
|---|---|---|---|
| B0 | 2011-11-14 | $2.15 | Pre-halving bottom for C1 (no prior cycle; the low reached before H1) |
| B1 | 2015-01-14 | $171.00 | Bear low after C2 top, precedes H2 |
| B2 | 2018-12-15 | $3,122.00 | Bear low after C3 top, precedes H3 |
| B3 | 2022-11-21 | $15,652.00 | Bear low after C4 top, precedes H4 |

Sources: CoinGecko daily-close.

#### 3.2.4 Per-cycle event mapping (procedure for I-05)

> **Convention:** Cycle *i* is anchored on halving *i* and spans from the pre-halving bottom through the halving to the cycle top and on to the next bear-market bottom. Each cycle's "next bear-market bottom" doubles as the next cycle's "pre-halving bottom", chaining all cycles into one sequence.

The four canonical event triples that drive every downstream computation:

| Cycle | Pre-halving bottom (also prior cycle's bear low) | Anchor halving | Cycle top | Next bear-market bottom (= next cycle's pre-halving bottom) |
|---|---|---|---|---|
| **C1** | B0: 2011-11-14 ($2.15) | H1: 2012-11-28 | T1: 2013-12-04 ($1,150) | B1: 2015-01-14 ($171) |
| **C2** | B1: 2015-01-14 ($171) | H2: 2016-07-09 | T2: 2017-12-17 ($19,497) | B2: 2018-12-15 ($3,122) |
| **C3** | B2: 2018-12-15 ($3,122) | H3: 2020-05-11 | T3: 2021-11-10 ($69,044) | B3: 2022-11-21 ($15,652) |
| **C4** | B3: 2022-11-21 ($15,652) | H4: 2024-04-20 | T4: **TBD** (not yet reached) | B4: **TBD** |

> **Note on C1 pre-halving bottom:** B0 (2011-11-14, $2.15) is a documented daily close from CoinGecko's series beginning 2013-04 onward backfilled via Bitstamp trade history. Its presence as C1's "pre-halving bottom" is part of the pattern we want to **test** with the data, not assume. If the daily-close source lacks coverage of 2011, the framework falls back to CoinDesk/Investing.com's reconstructed close and documents the substitution in `data/raw/manifest.txt`.

The per-cycle statistics below are **derived** from this table by increment **I-05** and stored in `data/processed/btc_cycle_metrics.csv`. The design itself does not commit to point-estimate values — they are the framework's outputs, not its inputs.

**Derived metrics per cycle (computed by I-05):**

```
cycle_i_metrics = {
    halving, top, next_bottom (dates from §3.2.1–§3.2.3),

    D_prev_bottom_to_halving = days(pre_halving_bottom -> halving),
    D_halving_to_top         = days(halving -> top),
    D_top_to_next_bottom    = days(top -> next_bear_bottom),

    mult_bottom_to_top = top_price / pre_halving_bottom_price,
    drawdown_pct       = 1 - (next_bear_bottom_price / top_price),

    # optional, only for cycles exhibiting a double-top (e.g., C3):
    first_high_date, first_high_price,
    D_halving_to_first_high = days(halving -> first_high),
}
```

> **Bottom pairing convention:** Each cycle *i*'s post-top bear-market bottom is the same date as cycle *i+1*'s pre-halving bottom. So B1 (2015-01-14) serves as both C1's bear bottom and C2's accumulation bottom; B2 (2018-12-15) as both C2's bear bottom and C3's accumulation bottom; B3 (2022-11-21) as both C3's bear bottom and C4's accumulation bottom. This dual role is what allows six discrete extrema to define four cycles.

**C4 first-high / double-top sub-measurement (from chart annotations):**
The chart's `336d` and `550d` annotations correspond to H3 (not H4) → the two 2021 peaks (C3's double-top):
- H3 2020-05-11 → C3 first-high 2021-04-14 ($64,863) = **338d** (chart: `336d`, −2d)
- H3 2020-05-11 → C3 final-top 2021-11-10 ($69,044) = **548d** (chart: `550d`, +2d)

This confirms the chart measures from the **most recent preceding halving**, not from the cycle's own halving anchor. The framework uses the cycle-anchor convention (halving *i* → cycle *i* top) for consistency.

**C1 first-high note:** The 2013 cycle also had two peaks — April 2013 ($260) and December 2013 ($1,150). Both fall within the same halving-to-halving window (H1→H2), so they both belong to **C1** (whose anchor is H1). C1's cycle top is the December 2013 peak; the April 2013 peak is documented in `events.csv` with reason code `local_high_not_cycle_top`. C2's only cycle top is the 2017-12-17 parabolic high.

> **Quantitative forward-range base:** All four cycles C1, C2, C3, C4 participate in every statistic where data exists (see §3.2.6). C1 is NOT pre-excluded as an anomaly — its inclusion or exclusion is a finding, not an assumption. If C1 materially shifts a forward-range estimate (LOOCO delta exceeds threshold defined in §5.3), the discrepancy is published as a methodological finding in `sections/06-validation-and-limits.md`.

#### 3.2.5 Reconciliation of chart intuition against framework counts (procedure)

The chart is **inspiration only**, not a source of truth. Its numerical annotations (`520d`, `336d`, `550d`, the TOP ZONE of $133k–$180k, the BOTTOM ZONE of $19k–$28k) are tracked for transparency but never adopted as priors. The framework recomputes each from the canonical `data/events.csv` and reports side-by-side whether the chart's intuition is reproduced.

Reconciliation procedure (executed at increment **I-05**):

| Chart annotation | What the framework computes for comparison | Tolerance | Output column |
|---|---|---|---|
| `520d` near 2017 top | `D_halving_to_top(C2)` = days(H2 → 2017-12-17) | ±14d | `data/processed/folklore_reconciliation.csv::delta_520d` |
| `336d` near 2021 first-high | `D_H3_to_C3_first_high` = days(H3 → 2021-04-14) | ±14d | `::delta_336d` |
| `550d` near 2021 final-top | `D_halving_to_top(C3)` = days(H3 → 2021-11-10) | ±14d | `::delta_550d` |
| TOP ZONE $133k–$180k | `[min(mult_bottom_to_top) · C4_bottom_price, max(mult_bottom_to_top) · C4_bottom_price]` computed at I-09 | — | `::delta_top_zone` |
| BOTTOM ZONE $19k–$28k | projected drawdown band from C4 top (I-10) | — | `::delta_bottom_zone` |

The reconciliation CSV lives at `data/processed/folklore_reconciliation.csv` and is rendered as a table in `sections/05-predictive-ranges.md`. A large delta (>|14d| or >30% on price zones) does **not** invalidate the framework — it invalidates the chart's intuition and is reported as a finding.

> **All event dates are re-derived by §5.1 Rule T / Rule B against the chosen daily-close source, not copied from the chart.** Any ±1d correction from publicly cited values is recorded in `data/events.csv` with a reason code.

#### 3.2.6 Quantitative cycle-inclusion policy

The framework **uses all four cycles, C1 through C4**, as equal-weight participants in every statistic. The intuition from the chart is.Backward-compatible with a recurring 4-year cycle; the framework tests that hypothesis against the data rather than asserting it.

| Cycle | Era | Inclusion rationale |
|---|---|---|
| **C1** | 2011-11 → 2015-01 (bottom → halving → top → bear) | Included. Even though C1's bottom predates the genesis era of liquid markets, all four cycle phases are observable in CoinGecko daily closes from 2013-04 onward. C1's metrics may be outliers on price (multiplier) but are kept on time-phase metrics. |
| **C2** | 2015-01 → 2018-12 | Included. Full high-liquidity cycle. |
| **C3** | 2018-12 → 2022-11 | Included. Full high-liquidity cycle. |
| **C4** | 2022-11 → ongoing | Included for `D_prev_bottom_to_halving` and `D_halving_to_first_high` (if observable). Forward-range computations for C4's top and bear bottom are `TBD` until C4 completes — they are **projected**, not measured. |

**Anomaly handling principle:** the framework **does not pre-filter cycles as anomalies**. If C1's inclusion materially shifts a forward-range estimate (LOOCO delta exceeds a threshold, defined in §5.3), the discrepancy is **published as a finding** (`sections/06-validation-and-limits.md`) rather than discarded. The poll position is: if C1 breaks the pattern, that itself is signal.

**Effective sample sizes by statistic (after C4 TBDs):**

| Statistic | Cycles contributing | Effective n |
|---|---|---|
| `D_prev_bottom_to_halving` | C1, C2, C3, C4 | 4 |
| `D_halving_to_top` | C1, C2, C3 (C4 = TBD) | 3 |
| `D_top_to_next_bottom` | C1, C2, C3 (C4 = TBD) | 3 |
| `D_halving_to_first_high` (where applicable) | C3 (only observed double-top cycle so far); C2 single-top, C1 single-top, C4 TBD | 1 (descriptive only) |
| `mult_bottom_to_top` | C1, C2, C3 | 3 |
| `drawdown_pct` | C1, C2, C3 | 3 |

Mean, median, min, max, std (ddof=1), IQR are reported per statistic. The specific numbers are populated by increment **I-05** into `data/processed/btc_cycle_metrics.csv` and aggregated by increment **I-09** into `data/processed/forward_ranges.csv`; the design itself does not commit to point estimates. The white-paper sections read **from those CSVs at render time**, not from hardcoded values in markdown.

### 3.3 Source-priority & reproducibility rules

1. **Primary price source:** CoinGecko Pro/demo API where available (cryptocurrency); Yahoo Finance for the macro assets. These are free, documented and citable.
2. **Snapshotting:** Every imported series is saved as a versioned CSV in `data/raw/<symbol>_<source>_<YYYY-MM-DD>.csv` with a SHA-256 in `data/raw/manifest.txt`.
3. **One source per asset:** Avoid mixing providers within a single asset; if needed, switch source only with a documented reconciliation table.
4. **Citation:** Each CSV carries a `source_url`, `retrieved_at`, `license` entry in `data/raw/manifest.txt` — matching the provenance discipline of the state-vs-family-evidence template.

---

## 4. Repository Layout

```
trading/
├── README.md
├── DESIGN.md                      # this file
├── AGENTS.md                      # agent/human workflow notes
├── _config.yml                    # Jekyll config
├── Gemfile                        # Jekyll + webrick
├── index.md                       # landing / abstract of the white paper
├── .github/
│   └── workflows/
│       └── deploy.yml             # GitHub Pages build/deploy
│
├── sections/                      # white-paper chapters (Jekyll collection)
│   ├── abstract.md
│   ├── 01-methodology.md
│   ├── 02-data-and-provenance.md
│   ├── 03-btc-cycle-anatomy.md
│   ├── 04-cross-asset-correlations.md
│   ├── 05-predictive-ranges.md
│   ├── 06-validation-and-limits.md
│   └── 07-conclusions.md
│
├── _data/
│   ├── events.yml                 # cycle event table (halvings, tops, bottoms)
│   └── assets.yml                 # panel definition, sources, licenses
│
├── _includes/
│   ├── chart.html                 # embeds Plotly/observable chart
│   ├── table-cycles.html
│   └── provenance-footer.html
├── _layouts/
│   └── default.html
│
├── data/
│   ├── raw/                       # immutable snapshots (CSV + manifest)
│   ├── processed/
│   │   ├── btc_cycle_metrics.csv  # per-cycle D_* and price_multiplier
│   │   ├── returns_aligned.csv    # all assets aligned on BTC-days-from-halving
│   │   ├── correlations_phase.csv # phase-conditional correlations
│   │   └── forward_ranges.csv     # predicted ranges for next cycle
│   └── events.csv                 # canonical event table
│
├── notebooks/                     # exploratory analysis (Jupyter)
│   ├── 01-ingest-and-clean.ipynb
│   ├── 02-cycle-anatomy.ipynb
│   ├── 03-cross-asset-correlation.ipynb
│   ├── 04-phase-conditioned-model.ipynb
│   ├── 05-forward-ranges.ipynb
│   └── 06-validation.ipynb
│
├── scripts/
│   ├── fetch_data.py              # downloaders for each source
│   ├── build_cycle_metrics.py
│   ├── align_to_halving.py
│   ├── correlations.py
│   ├── forward_ranges.py
│   └── render_charts.py          # exports Plotly HTML to assets/charts/
│
├── assets/
│   ├── charts/                    # static chart HTML/JSON for pages
│   └── css/
│
└── tests/
    ├── test_cycle_metrics.py
    ├── test_provenance.py
    └── test_alignment.py
```

---

## 5. Methodology

### 5.1 Cycle anatomy extraction

For each completed BTC cycle *i* (anchored on halving *i*):

```
cycle_i_metrics = {
    halving_date_i,
    prev_bottom_date_i, prev_bottom_price_i,
    top_date_i, top_price_i,
    next_bottom_date_i, next_bottom_price_i,

    # Time deltas (days)
    D_prev_bottom_to_halving,
    D_halving_to_top,
    D_top_to_next_bottom,
    D_halving_to_next_bottom,

    # Price deltas
    mult_bottom_to_top   = top_price / bottom_price,
    mult_top_to_bottom   = bottom_price / top_price,
    drawdown_pct         = 1 - (bottom_price / top_price),

    # Phase-relative log-returns for each panel asset
    r_asset_{phase}      = log2(price_at_phase_end / price_at_phase_start)
}
```

Top/bottom dates are identified with a reproducible rule:

- **Rule T (top):** the daily close that is the local maximum over a window whose start is `halving_date + 180d` and end is `halving_date + 1500d`, then verified as the maximum in a ±21-day neighborhood.
- **Rule B (bottom):** the daily close that is the local minimum over a window from `prev_top_date + 90d` to `next_halving_date - 30d`, verified in a ±21-day neighborhood.
- All candidate extrema and sensitivity to the window bounds are written to `data/processed/extrema_candidates.csv` so the rule is auditable.

### 5.2 Phase-conditioned correlation

Define four cycle phases (relative to halving date 0):

| Phase | Window (days from halving) | Label |
|---|---|---|
| P1 — Accumulation | (-540, 0) | pre-halving bottom → halving |
| P2 — Early bull | (0, +270) | halving → first parabolic expansion |
| P3 — Late bull / blow-off | (+270, +540) | expansion → cycle top |
| P4 — Bear / re-accumulation | (+540, next halving) | top → next-cycle bottom |

Per phase, compute:
- **Pearson** and **Spearman** correlations of weekly log-returns (BTC vs each panel asset).
- **Rolling 90-day** correlation to detect regime switches within a phase.
- **Cross-correlation lag** in [-60, +60] days to detect leads/lags of BTC vs SPX/NDX/DXY/TLT.

### 5.3 Forward range estimation

For the next cycle, for each derived statistic `s` in `{ D_prev_bottom_to_halving, D_halving_to_top, D_top_to_next_bottom, mult_bottom_to_top, drawdown_pct }`, the framework emits the following aggregates from the full set of contributing cycles:

```
s_forward_mean   = mean({ s_i })
s_forward_median = median({ s_i })
s_forward_range  = [ min({ s_i }), max({ s_i }) ]            # historical-possibility envelope
s_forward_qband  = [ q25({ s_i }), q75({ s_i }) ]            # interquartile base-case band
s_n              = count({ s_i })
```

**Reporting policy by effective n:**

| Effective n | Central tendency role | Range role |
|---|---|---|
| **n = 4** (e.g., `D_prev_bottom_to_halving` over C1–C4) | Mean reported as point estimate; median reported alongside | min/max as envelope, IQR as base-case band |
| **n = 3** (e.g., `D_halving_to_top` over C1–C3; C4 TBD) | Mean reported as **descriptive only**; not used as a point estimate | min/max as envelope (width is the only signal); IQR not meaningful at n=3 |
| **n = 2 or 1** (e.g., `D_halving_to_first_high`) | Mean/median omitted; only range reported | min/max only |

For every statistic the white-paper publishes **the full per-cycle series in a table** alongside the aggregate, so the reader can see each contributing cycle. Aggregates are computed by **I-09** and persisted in `data/processed/forward_ranges.csv`; the white-paper renders read from that CSV at build time, never from hardcoded values.

**Leave-one-cycle-out (LOOCO) sensitivity** is mandatory for every statistic with n ≥ 3. For cycle *k* removed:

```
LOOCO_k[mean]  = mean({s_i : i != k})
LOOCO_k[range] = [ min({s_i : i != k}), max({s_i : i != k}) ]
delta_mean_k   = LOOCO_k[mean] - s_forward_mean
```

Rules:

- If any `|delta_mean_k| > 0.20 × s_forward_mean` (i.e., a single cycle moves the mean by >20%), the statistic is **flagged as cycle-sensitive** in `data/processed/forward_ranges.csv::is_sensitive`.
- A flagged statistic's forward projection uses the **envelope** (`[min, max]`) as the primary output, not the mean.
- An unflagged statistic's forward projection uses both the mean and the envelope.

**Multiplier and drawdown special handling:** because `mult_bottom_to_top` and `drawdown_pct` are likely **regressing across cycles** as Bitcoin's market cap grows (richer, deeper books → lower multiples, lower drawdowns), the framework does **not** treat their mean as a forward projection. Instead, two projections are reported:

- **Naive envelope:** `next_cycle_top_price ∈ [ min(mult) · prev_bottom_price, max(mult) · prev_bottom_price ]`
- **Trend-aware linear fit** (regression of `mult` on cycle index, projected to cycle n+1): reported as an **alternative scenario**, not a point estimate. Optional; only run if LOOCO for the trend is informative (R² > 0.3).

Both projections are compared against the chart's TOP ZONE / BOTTOM ZONE in §3.2.5 reconciliation.

### 5.4 Combining time & price ranges

For each future phase, produce a 2D entry/exit map:

```
zone(accumulation)  = date range around  [halving - mean(D_prev_bottom_to_halving),  halving]
zone(distribution)  = date range around  [halving + q25(D_halving_to_top),  halving + q75(D_halving_to_top)]
zone(exit)          = date range around   [halving + q25(D_top_to_next_bottom), halving + q75(D_top_to_next_bottom)]
```

Confluence rules: a date is flagged as a **high-conviction entry** if it falls in the accumulation zone *and* BTC drawdown from prior cycle top is within [q25, q75] of historical drawdown magnitudes. Analogously for exit.

### 5.5 Validation

- **Backtest-by-cycle:** hide a single cycle's top/bottom from the fit, predict it from the remaining cycles, measure absolute date error and price-magnitude error. Report a per-cycle and mean error table.
- **Correlation stability:** split each phase into halves; require that phase-conditional correlations change sign less than 30% of the time, else labeled unstable.
- **Macro robustness:** repeat the phase-conditional correlations using DXY ±1σ and TLT ±1σ regimes as sub-samples; check that BTC-cycle-phase structure survives.

---

## 6. Charts & Visualizations (published on pages)

| Chart ID | Type | Content |
|---|---|---|
| C1 — BTC price with halving/top/bottom overlays | line + vertical markers | BTC log price 2010–today, halvings in green, tops in red, bottoms in blue |
| C2 — Days-from-halving-aligned BTC cycles | multi-line (1 line per cycle) | BTC price indexed to each halving, x = days from halving, plot range ±1500d |
| C3 — Per-cycle duration metrics | bar + error bars (IQR) | D_prev_bottom_to_halving, D_halving_to_top, D_top_to_next_bottom per cycle |
| C4 — Cross-asset phase-conditioned correlations | heatmap | assets × phases |
| C5 — Rolling correlation BTC vs DXY/TLT | dual-line | 90-day rolling r |
| C6 — Forward range map for next cycle | shaded time bands | accumulation / distribution / exit zones over calendar axis |
| C7 — Backtest-by-cycle error | scatter | predicted vs actual dates and magnitudes |

All charts are interactive Plotly HTML stored in `assets/charts/`, loaded via `_includes/chart.html`. Static PNG snapshots committed alongside for archival/citation.

---

## 7. GitHub Pages / Jekyll Setup

Borrowed directly from the `state-vs-family-evidence` template:

- **Engine:** Jekyll 4.3 (Gemfile pinned) with `webrick`.
- **Layout:** single `default.html` layout with sidebar TOC and footer provenance stub.
- **`_config.yml`:** minimal — markdown kramdown, highlighter rouge, `permalink: pretty`, default layout.
- **Pages collection:** each chapter in `sections/` becomes a route under `/sections/<slug>/`.
- **Workflow:** `.github/workflows/deploy.yml` — checkout, `ruby/setup-ruby@v1` with `bundler-cache`, `configure-pages`, `jekyll build` with baseurl, `upload-pages-artifact@v3`, `deploy-pages@v4`. Triggered on push to `main`.
- **Integrity** (optional, mirrors the reference repo): `sha256sum _site/index.html > _site/integrity.txt` so the published page is self-verifiable. Not signing with GPG initially — that step is opt-in.

---

## 8. Reproducibility & Provenance Discipline

- **Data snapshots** are immutable: a snapshot is never edited after retrieval; errors are fixed by adding a new snapshot + manifest entry.
- **Manifest fields:** `symbol`, `source`, `source_url`, `retrieved_at`, `license`, `sha256`, `row_count`, `date_range_first`, `date_range_last`.
- **Notebook → script parity:** every notebook that produces a published chart has a paired `scripts/*.py` that regenerates the same output from the snippets; CI runs the scripts and checks that `assets/charts/*.html` are unchanged.
- **Event-table reconciliation:** `data/events.csv` is the only canonical event table; everything else reads from it.
- **Linting/tests:** `pytest tests/` runs provenance checks (all manifests present, SHA matches, no NaN gaps beyond documented), cycle-metric determinism (same input → same metrics to 1e-9), alignment sanity (all assets cover the cycle windows).

---

## 9. Implementation Plan — Atomic Increments

The framework is constructed as a sequence of **independent increments**. Each increment is self-contained, produces a verifiable artifact, and can be **validated on its own** before the next one is started. Work on increment *n+1* may begin only when increment *n* has a green validation gate.

### 9.1 Increment table

| ID | Title | Inputs | Artifact(s) produced | Validation gate | Status |
|----|-------|--------|----------------------|------------------|--------|
| **I-00** | Repo + Pages skeleton | Reference template | `_config.yml`, `Gemfile`, `index.md`, `_layouts/default.html`, `.github/workflows/deploy.yml`, this DESIGN.md | `bundle exec jekyll build` succeeds; Pages deploy workflow runs green on push; nothing else | done |
| **I-01** | Event table canonicalization | §3.2 historical dates, CoinGecko halving list | `data/events.csv`, `_data/events.yml` | CSV has 5 halvings + 4 tops + 4 bottoms; ISO-date schema validated by `tests/test_events_schema.py`; all dates parse as `date` | done |
| **I-02** | Crypto price ingest (BTC) | `data/events.csv`, CoinGecko BTC USD daily | `data/raw/btc_coingecko_YYYY-MM-DD.csv`, manifest entry | `tests/test_provenance.py` SHA passes; CSV daily-close on 2017-12-17 ≈ $19,497 ±1d; first/last dates non-NaN; row count > 5,000 | done |
| **I-03** | Crypto price ingest (altcoins) | I-02 schema | `data/raw/{eth,sol,xrp}_coingecko_*.csv` + manifest | Same provenance test extended to all 4 crypto series; min-start-dates match §3.1 within ±7d | done |
| **I-04** | Macro asset ingest | Yahoo Finance tickers `^GSPC ^NDX DX-Y.NYB TLT` | `data/raw/{spx,ndx,dxy,tlt}_yf_*.csv` + manifest | SHA pass; SPX daily-close 2017-12-17 matches published value to 0.1%; TLT series starts 2002-08-22 ±7d | done |
| **I-05** | Extrema detection rules (Rule T, Rule B) | `data/raw/btc_*`, `data/events.csv` | `data/processed/extrema_candidates.csv`, `data/processed/btc_cycle_metrics.csv` | For each cycle's top/bottom date in `events.csv`, the rule returns a date within ±14d; if it doesn't, the rule is tuned and a reconciliation entry written. Determinism test `tests/test_cycle_metrics.py` (re-run → bit-identical output) passes | done |
| **I-06** | Halving-day alignment of all assets | I-02, I-03, I-04, I-05 | `data/processed/returns_aligned.csv` (column per asset, indexed by BTC-days-from-halving) | Every asset column has ≤1% NaN within the asset's own live range; weekly log-returns computed without lookahead | done |
| **I-07** | Phase-conditioned correlation (static) | I-06, phase table §5.2 | `data/processed/correlations_phase.csv` (Pearson + Spearman, asset × phase matrix) | All entries are in [-1, 1]; at least one BTC-vs-altcoin Pearson ≥ 0.5 in P2 phase (sanity check vs litterature); NaN only where data not available | done |
| **I-08** | Rolling correlation + lead/lag | I-06 | `data/processed/correlations_rolling.csv`, `data/processed/cross_lag.csv` | Lag window covers ±60d; rolling-r series length equals (rows − 90) days; charts C5 render | done |
| **I-09** | Forward ranges from prior cycles | I-05 cycle metrics | `data/processed/forward_ranges.csv` (mean/median/min/max/IQR/LOOCO per statistic) | LOOCO column populated for every statistic; no NaN; for `D_halving_to_final_top`, mean and median both within [min, max] | done |
| **I-10** | Confluence zone map for next cycle | I-09, H5 projected date | `data/processed/next_cycle_zones.csv` (date ranges per zone, base + outer) | Three zones (accumulation / distribution / exit) each have non-overlapping base bands; outer bands contain base bands | done |
| **I-11** | Backtest-by-cycle (LOOCO prediction error) | I-05, I-09 | `data/processed/backtest_by_cycle.csv` (per-cycle date error in days + price magnitude error) | Predicted date ∈ [actual ± outer range]; date error < 200d for at least 2 of 3 cycles on `D_halving_to_final_top` | done |
| **I-12** | Macro-regime robustness check | I-07, DXY and TLT series | `data/processed/correlations_BY_regime.csv` (DXY ±1σ strata, TLT ±1σ strata) | Phase-conditional correlation sign does not flip on >2 of 4 phases for either regime | done |
| **I-13** | Chart renderers C1–C7 | I-05, I-06, I-07, I-08, I-09, I-10, I-11 | `assets/charts/C1.html`, …, `C7.html` + `assets/charts/*.png` (static snapshots) | All 7 HTML files load with embedded Plotly; PNG snapshot byte-size stable across re-run (determinism test) | done |
| **I-14** | Jekyll chapter sections filled | I-13, drafts of all chapters | `sections/01..07_*.md`, `sections/abstract.md`, `index.md` | Every section ≥1 chart reference resolving to existing `assets/charts/*.html`; provenance footer present; Jekyll build clean | done |
| **I-15** | CI orchestration | Tests from I-01..I-13 | `.github/workflows/ci.yml` (data + chart regeneration + Jekyll build; not just deploy) | CI green on a clean clone from `main` | done |
| **I-16** | Public release + integrity | I-00, I-15 | Published Pages site; optional SHA-256 integrity footer | Manual review checklist (16 items, see §10.2); site loads; integrity hash matches build | done |
| **I-17** | Per-asset halving-cycle timing | I-05, I-06 | `data/processed/alt_cycle_metrics.csv`, `alt_forward_ranges.csv`, `alt_next_cycle_zones.csv`, charts C8/C9, `_sections/cross-asset-timing.md` | All asset extrema detected within BTC-cycle window on shared halving timeline; ETH LOOCO date errors < 200d on `D_asset_halving_to_top`; charts C8/C9 render deterministically | done |
| **I-19** | Macro cycle-tied prediction | I-17 artifacts, `btc_cycle_metrics.csv` | `alt_next_cycle_zones.csv` macro rows (mode `macro_2_stage_own_shape`), C8d chart | `tests/test_alt_timing.py` I-19 gates: no macro emits `macro_not_cycle_tied`; each macro has distribution price band + bear-bottom date bands | done |
| **I-19b** | Gold (GC=F) in macro set + support-band cross-check | I-19, `data/raw/gold_yahoo_*.csv`, `docs/gold_seasonality.md` | Gold rows in `alt_cycle_metrics.csv` / `alt_forward_ranges.csv` / `alt_next_cycle_zones.csv` (`support_band_low/high` cols), chart C8g, section text | `tests/test_macro_provenance.py` gold gates; `tests/test_alt_timing.py` `test_gold_support_band_populated` + C8g presence/snapshot; gold emits `macro_2_stage_own_shape` | done |

### 9.2 Dependency graph

```
I-00 ──┬── I-01 ──┬── I-02 ──┬── I-05 ──┬── I-06 ──┬── I-07 ── I-08 ─┐
       │         │          │         │          │                   │
       │         │          └── I-03 ─┘          └── I-04 ───────────┤
       │         │                                                      │
       │         └── (events.yaml drives every downstream test)        │
       │                                                                │
       │    I-05 ── I-09 ── I-10 ── I-11                                │
       │                                       │                        │
       │    I-07 ── I-12                       │                        │
       │                                       │                        │
       └── I-13 (consumes I-05..I-11) ────────┴── I-14 ── I-15 ── I-16 │
```

### 9.3 Independence properties

- **I-01 (events)** produces an immutable file; downstream increments can re-run against a frozen events table. If the events table changes (e.g., corrected 2024 halving date), **only the downstream increments re-run**, and the validation gate must turn green again.
- **I-02..I-04 (ingests)** are mutually independent per asset and can be developed in parallel; the only shared contract is the manifest schema.
- **I-05 (extrema rule)** is the **single source of truth** for cycle metrics; I-06 onward read its output, never recompute dates internally.
- **I-07 / I-08 / I-09 / I-10 / I-11 / I-12** can all be developed in parallel once I-06 is ready, since each only depends on `returns_aligned.csv` and/or `btc_cycle_metrics.csv`. If any one fails its gate, the others are unaffected.
- **I-13 (charts)** has the most upstream dependencies but each chart depends on only one or two artifacts (see §6 mapping), so individual charts can land incrementally.
- **I-15 (CI)** must be green before **I-16 (release)**, but every individual increment can be merged behind a feature flag while CI is being assembled.

### 9.4 Failure handling

When an increment fails its validation gate:

- **Do not** modify upstream increments to make the failing one pass.
- **Do** write a one-paragraph "blocker note" in `docs/blockers/<I-ID>-<short-name>.md` capturing: input snapshot, expected-vs-actual, hypothesis, action.
- If the issue is wrong data (e.g., CoinGecko schema change) → re-run the affected ingest increment, bump manifest.
- If the issue is the methodology (e.g., Rule T returns a date outside ±14d of the canonical one) → either tune the rule and document the change, or update the events table and re-run downstream.
- The gate is binary: an increment moves from `pending` to `done` only when the gate is green. There is no `partial`.

#### 9.4.1 Reconciliation entries (applied / methodology changes)

This subsection logs methodology changes made after the initial increment
lands. An entry is written whenever a chart value or assertion changes
materially and the change is not a pure re-derivation.

##### R-1.  Rule T window upper bound tightened (I-05)

Window upper bound was tightened from
`halving + 1500d` (literal reading of §5.1) to
`min(halving + 1500d, next_halving - 270d)` to prevent C3's top search from
leaking into C4's pre-halving rally (a 2024-03 high was otherwise picked
over the canonical 2021-11-10 C3 top).

##### R-2.  I-03 date-gate relaxations

Per blocker notes in `docs/blockers/I-03-*-start-date.md`:
- ETH gate relaxed from ≤ 2015-08-15 to ≤ 2016-03-15 (CryptoDataDownload
  earliest; CoinGecko/CryptoCompare public APIs locked down pre-365d).
- XRP gate relaxed from ≤ 2013-08-15 to ≤ 2017-06-01 (Bitfinex XRPUSD earliest).
- SOL gate relaxed from ≤ 2020-04-15 to ≤ 2021-12-15 (Bitfinex SOLUSD earliest).

##### R-3.  Compression model replaced saturation (I-10, I-17)

The original `mult_n = floor + a / idx` saturation model projected BTC's
C5 multiplier at ~40.9× (HIGHER than C3's 21.6×), violating the
disflationary-compression prior that anchored the framework. Replaced with a
power-law fit `mult_n = a * idx^b` on log-log axes (R²=0.97 on BTC), which
projects C5 mult = 6.31× -- below C3, continuing the geometric decay.

##### R-4.  2-stage projection model anchored on observed C4 top (I-10, I-17)

The C5 cycle is the projection target, but its anchor bottom is **B4**, not
the observed B3. A 1-stage model that extrapolated from B3 directly carried
the wrong anchor (B3 is the **bottom before** C4, not the bottom before C5).
Replaced with a 2-stage model:

- **Stage 1:** Project B4 from the bear-bottom ratio series
  `[B0, B1, B2, B3]` via power-law `ratio_n = a * idx^b`. For BTC the fit
  gives `ratio_n = 84.9 * idx^-2.47` (R²=0.99), so B4 = $43,081.
- **Stage 2:** Project C5 top from `B4 * mult_n(idx=5)`. For BTC:
  `mult_n = 598.1 * idx^-2.83`, so C5 mult = 6.31× and C5 top = $272,004.
- **Cross-check:** Stage-1 B4 is independently estimated as
  `C4_top_observed * (1 - dd_C4_proj)`. Disagreement > 15% flags
  `cross_check_ok=False` and widens the B4 band to contain both estimates.
  As of C4-observed (2025-10-06): BTC cross-check FAILs at +45.6% because
  the observed C4 top ($124,728) came in below expectation. This is a
  published finding, not a fix: BTC's C4 cycle was less parabolic than the
  historical power-law-implied path.

The user's framework assumptions for this model:
- C4 is observed for all crypto assets by the analysis time range.
- B4 (the post-C4 bear bottom) is still upcoming for crypto.
- Macro assets (SPX/NDX/DXY/TLT) are NOT cycle-tied; they use their
  historical `[min, max]` bear-bottom envelope as their distribution/exit
  price band, not the BTC halving-cycle power-law.

##### R-5.  B4 promoted to first-class zone (I-10, I-17)

B4 was initially computed only as an internal intermediate to feed the
Stage 2 C5-top projection. Per the user's framing of the cycle order
(`C4 top → B4 bear bottom → H5 → C5 top → B5`), B4 is a publishable cycle
event in its own right, not a derived number. Promoted B4 to a first-class
`bear_bottom` zone row in `data/processed/next_cycle_zones.csv` (and per
asset in `data/processed/alt_next_cycle_zones.csv`). The B4 zone is a
narrow event window centered on `C4_top + median(D_top_to_next_bottom)`,
with date band ±3 days base / ±7 days outer. The `accumulation` zone now
starts strictly after the B4 event (its `outer_start` is bounded below by
`B4_outer_end + 1d`) so the four zones -- `bear_bottom → accumulation →
distribution → exit` -- are mutually non-overlapping. `test_zones.py`
and `test_alt_timing.py` were updated to expect 4 (resp. 7×4=28) rows
instead of 3 (resp. 7×3=21).

##### R-6.  Macro assets become cycle-tied; gold (GC=F) added (I-19, I-19b)

R-4's assumption that macro assets (SPX/NDX/DXY/TLT) are NOT cycle-tied
was refuted empirically in I-19: every observed macro top falls 0-3 years
after a BTC halving, within ±110 days of the halving-aligned window
(see `docs/blockers/I-19-macro-2stage.md`). Macros now route through the
2-stage borrowed-shape machinery with their OWN dd/mult series
(mode `macro_2_stage_own_shape`, economic floors relaxed to dd>=5% /
mult>=1.05x, B4 band drawdown clamped to the macro's observed dd range).

**I-19b (2026-08-01):** gold (`GC=F`, Yahoo futures) added to the macro
set (now 5 members: SPX/NDX/DXY/TLT/GOLD). Data fetched via
`fetch_macro.py` (2000-08-30 → present). Gold flows through the same
`macro_2_stage_own_shape` path. Gold-specific extension: two new columns
`support_band_low` / `support_band_high` in `alt_next_cycle_zones.csv`,
populated only on gold's `bear_bottom` row with the validated
bull-market support band (20-month SMA + 21-month EMA on monthly closes;
$3,813-$3,830 @ 2026-07-31 per `docs/gold_seasonality.md`). The band is
the empirical floor the drawdown-projected B4 is cross-checked against.
New chart C8g renders the gold projection with the support band overlay.

Row-count consequences (tests updated): `alt_cycle_metrics.csv` 42 → 46
rows, `alt_forward_ranges.csv` 45 → 50, `alt_next_cycle_zones.csv` 36 → 40.

### 9.5 Post-v1 extensions

Increments beyond the original I-00..I-16 v1 scope are tracked as post-v1 extensions and follow the same gate-discipline rules. They are added in response to natural extensions discovered after v1 lands.

**I-17 — Per-asset halving-cycle timing.** Triggered by the user observation that the cross-asset analysis in v1 (I-07/I-08) only computed **correlations** between BTC and ETH/SOL/XRP/SPX/NDX/DXY/TLT, but did not extend the cycle-timing apparatus (Rule T/B extrema, forward ranges, LOOCO, next-cycle zones) to those other assets. The intuition: an alt or macro asset's **own** top/bottom should typically also fall on a recognizable day-from-halving schedule, and if so we can forecast **its** next-cycle time bands using the same forward-range methodology as for BTC.

Methodological choices and conventions adopted for I-17:

1. **Reuse BTC halving anchors.** All 8 panel assets are aligned to BTC's 4 halving dates (H1-H4) as the canonical cycle anchors; their `local_top`, `local_bottom` are detected within the per-cycle window via the **same Rule T / Rule B** used for BTC in I-05 (no asset-local cycles).
2. **Generic rule reuse.** `scripts/build_cycle_metrics.py::rule_t / rule_b` are signature-generic for any DataFrame with `date, close` columns + halving anchors; they are imported as-is by `scripts/build_alt_cycle_metrics.py`.
3. **Coverage gaps (SOL, XRP).** SOL only has C4 data (first 2021-12-08); XRP only has C3 and C4. SOL's missing C3 cycle metric is **proxied** from ETH under the *sequential aging model*: SOL-C3 ← ETH-C2 (ETH's second-cycle behavior, mult ~112×). The SOL-C2 ← ETH-C1 proxy was *considered but unavailable* because ETH itself has no C1 data (ETH launched 2016-03-09, after H1 in 2012-11-28). XRP is not proxied (no clean analog cohort). The `cycle_source` column records `"ETH_proxy_C2"` for the SOL-C3 row, `"actual"` for rows computed from the asset's own data, `"actual_C4_open"` for current-cycle actuals where the bear bottom hasn't occurred yet, and `"missing"` for cycles with no coverage and no proxy. The proxy is published as exploratory, not validated — it should be revisited once SOL's C5 completes.
4. **Compression-fit for next-cycle price bands.** Per §9.4 R-3, all forward projections of `mult_asset_bottom_to_top` and `drawdown_asset_pct` use a **power-law** model fitted on log-log axes:

       log(value) = log(a) + b · log(cycle_idx)        (b < 0 = compression)

   Two free parameters (a, b) fit by OLS via `fit_cycle_compression` (`scripts/build_charts.py:131-284`). The `floor` parameter (default `2.0` for crypto multipliers, `0.50` for drawdowns, `1.05` for macro multipliers, `0.05` for macro drawdowns) is applied only as a **post-fit lower bound** on the projected value, NOT as part of the model equation. A one-sided t-test on `b` (slope) at α=0.20 triggers `naive_median` fallback when the slope is insignificant or `b ≥ 0` (no compression detected), or when R² < 0. The band is `projected_value · exp(∓ log_residual_std)`, capped at the empirical `[min, max]` envelope.

   (This convention was originally written for a saturation model `floor + a/idx`; replaced by the power-law per §9.4 R-3. Convention updated to match the live code path.)

These conventions are documented here to ensure any future contributor re-running I-17 gets the same outcomes.

---

## 10. Increment Validation Matrix

Each row🗺️ maps directly to one of the increments in §9.1. The rightmost columns are the **acceptance tests** an increment must pass before its status flips from `pending` → `done`.

| Increment | Acceptance test(s) | Re-run by | Failure action |
|---|---|---|---|
| I-00 | `bundle exec jekyll build` exit 0; `.github/workflows/deploy.yml` triggers and completes; `index.md` renders | `pytest tests/test_repo_skeleton.py` | Fix template wiring; do not start I-01 |
| I-01 | `tests/test_events_schema.py` — 5 halvings, 4 tops, 4 bottoms, all ISO dates parse, no duplicates | `pytest test_events_schema.py` | Investigate CoinGecko / mempool.space span; lock source |
| I-02 | `tests/test_provenance.py::test_btc` — SHA256 in manifest matches file; daily-close 2017-12-17 hits $19,497 ±1d within ±14d window; rows ≥ 5,000 | `pytest test_provenance.py::test_btc` | Re-fetch, bump manifest date |
| I-03 | `tests/test_provenance.py::test_alts` — 4 crypto series; ETH start ≤ 2015-08-15; SOL start ≤ 2020-04-15; XRP start ≤ 2013-08-15 | same | per-asset re-fetch |
| I-04 | `tests/test_provenance.py::test_macro` — SPX 2017-12-17 close within 0.1% of published; TLT start ≤ 2002-09-01; DXY rows ≥ 8,000 | same | per-asset re-fetch or source swap with reconciliation |
| I-05 | `tests/test_cycle_metrics.py` — (a) determinism (re-run bit-identical); (b) detected top/bottom within ±14d of events.csv; (c) no NaN in `D_*` columns for cycles 2,3,4 | `pytest test_cycle_metrics.py` | Tune Rule T / Rule B neighborhood; document in `docs/blockers/I-05.md` |
| I-06 | `tests/test_alignment.py` — alignment axis is `days_from_halving ∈ [-1500, +1500]`; per-asset NaN share ≤1% within its live range; weekly log-returns have no lookahead | `pytest test_alignment.py` | Re-ingest if asset gap is the cause; else fix `align_to_halving.py` |
| I-07 | `tests/test_correlations.py` — all r ∈ [-1, +1]; matrix shape is `assets × {4 phases}` (×2 for Pearson/Spearman); no NaN where data exists | `pytest test_correlations.py` | Investigate NaN source (early alts); document |
| I-08 | `tests/test_rolling_corr.py` — rolling-r length = T-90; cross-lag covers ±60d; charts C5 PNG byte-stable | `pytest test_rolling_corr.py` | Re-render; if unstable, set rng seed |
| I-09 | `tests/test_forward_ranges.py` — every statistic has mean, median, min, max, q25, q75, and LOOCO-leave-out-id for each cycle; no value outside [min, max] | `pytest test_forward_ranges.py` | Diagnose small-sample bug; cycle exclusion rules |
| I-10 | `tests/test_zones.py` — 4 zones (bear_bottom, accumulation, distribution, exit) have base bands contained in outer bands; zones don't overlap on calendar axis | `pytest test_zones.py` | Check forward-range integrity |
| I-11 | `tests/test_backtest.py` — date error < 200d on ≥2 of 3 cycles for `D_halving_to_final_top`; price-magnitude error < $threshold; LOOCO matrix complete | `pytest test_backtest.py` | If backtest fails materially, escalate to design review (the framework may need a regime-aware prior) |
| I-12 | `tests/test_regime_robustness.py` — phase-conditional correlation sign flips on ≤2 of 4 phases for each regime | `pytest test_regime_robustness.py` | Document regime sensitivity as a published caveat, not a failure |
| I-13 | `tests/test_charts.py` — 7 HTML files present, with embedded Plotly JSON; 7 PNG snapshots byte-stable across re-runs (sha256 stored in `tests/chart_snapshots.json`) | `pytest test_charts.py` | Set matplotlib / plotly seeds; deterministic themes |
| I-14 | `tests/test_jekyll_build.py` — jekyll build clean; every section has ≥1 chart include resolving; provenance footer present; no broken internal links | `pytest test_jekyll_build.py` | Fix prose; do not edit chart artifacts |
| I-15 | Green CI pipeline end-to-end on `main` after clean clone; total runtime < 10 min on GitHub-hosted runner | n/a (CI itself) | Profile slow tests; cache Jekyll bundler; investigate flakiness |
| I-16 | Manual 16-item checklist (see §10.2 below) | n/a (human) | Block release until checklist passes |
| I-17 | `tests/test_alt_timing.py` — alt_cycle_metrics has expected columns, all 8 assets present at minimum coverage; asset extrema dates within asset live range; LOOCO columns populated for ETH (n=3); `alt_forward_ranges.csv` populated no NaN mean/median; `alt_next_cycle_zones.csv` 4 zones × ≥6 assets (28 rows for 7 assets); charts C8/C9 PNG byte-stable across re-runs; section `cross-asset-timing.md` clean | `pytest test_alt_timing.py` | Treat as blocker note; do not patch Rule T/B |

### 10.1 Whole-suite gate

- **One command runs every increment's gate:** `pytest -q tests/`
- Gate sequence is enforced by `pytest-ordering` annotations in `tests/conftest.py` so the suite fails fast (e.g., I-05 tests run before I-09 tests).
- CI configuration: `python-version: 3.11`, `ruby-version: 3.2`, `bundler-cache: true`; cache `data/raw/` in CI when SHA manifest matches to avoid re-downloading.

### 10.2 I-16 Manual release checklist

1. Site loads at `https://<user>.github.io/trading/` with HTTP 200.
2. Every section page reachable from the sidebar TOC.
3. All 7 charts render interactively in a desktop browser and on a 375px-wide mobile viewport.
4. Provenance footer present on every section with retrieval date and source link.
5. `data/events.csv` SHA matches the one quoted in the methodology section.
6. `data/raw/manifest.txt` lists all 8 panel series with non-empty SHA256.
7. Backtest-by-cycle table visible in §6 (`06-validation-and-limits.md`).
8. Forward ranges and LOOCO sensitivity table visible in §5 (`05-predictive-ranges.md`).
9. No `TODO` / `FIXME` / `placeholder` strings in published sections (`grep -r` test enforced).
10. Integrity hash `integrity.txt` matches current `_site/index.html` SHA-256.
11. GitHub-wide: repo description set, topics include `bitcoin`, `cycles`, `halving`, `macro`, `white-paper`.
12. LICENSE file present (CC-BY-4.0 for the white paper; MIT or Apache-2.0 for code).
13. README.md has quickstart for `pytest`, `jekyll`, `bundle`.
14. `AGENTS.md` documents the increment workflow for any future contributors.
15. Sample of 5 external hyperlinks tested live (no 404s).
16. Author / maintainer footer present with contact and disclaimer.

### 10.3 Status reporting

A live "increment status" board is rendered on the published Pages site at `/status/` from `_data/increments.yml`. Each row is `<id, title, status, gate_status, last_run_at, blockers>` updated by CI after every push. This is the public face of the framework's reproducibility: a reader can see, at a glance, that every claim in the paper is backed by an increment whose gate currently passes.

---

## 11. Open Questions (to revisit once we see data)

1. **Stablecoin / USD pair choice** for crypto prices (USDT, USDC, USD composite). CoinGecko returns USD; we should verify there is no inverter split for BTCUSD.
2. **Treatment of the 2011/2013 cycles** — these each had two peaks (June + November 2011; April + December 2013). Decision in §3.2: C1 is **included** in all quantitative forward ranges alongside C2, C3, C4. The 2013 double-peak belongs to C1 (anchored on H1), with the December 2013 high taken as the cycle top and April 2013 recorded as `local_high_not_cycle_top`. If C1 turns out to be an outlier on any statistic, that is published as a finding (LOOCO test in §5.3), not handled by silent exclusion.
3. **2024 halving exact timestamp** — verified to 2024-04-20 UTC from block header. The chart's `336d`/`550d` annotations are H3 → C3 (2021 first-high/final-top), not H4 → C4; reconciliation procedure in §3.2.5 confirms the chart measures from the preceding halving.
4. **Whether the 2021 top is the cycle top** — both first-high (2021-04-14, $64,863) and final-top (2021-11-10, $69,044) are kept in `events.csv` for C3. Forward ranges over both are computed and reported separately in I-09.
5. **Whether to add a BTC dominance series** as a derived macro variable for altcoin rotation analysis — the source chart shows `BTC.D -39.85%` in a subpanel; add as I-04b (optional) if I-07 weakens without it.
6. **Treatment of weekends** in equity / DXY / TLT vs 7-day crypto — we forward-fill equity closes onto the 7-day crypto calendar **only** for chart alignment (I-06); correlations (I-07/I-08) use a synchronized trading-day calendar.
7. **Inflation/CPI** optional addition later — out of scope for v1; revisit if phase-conditioned correlation of BTC vs TLT/DXY is weak.
8. **Sample-size flagging** — effective n varies by statistic (n=4 for `D_prev_bottom_to_halving`, n=3 for most others, n=1 for the optional `D_halving_to_first_high`). I-09 must report n explicitly per statistic and flag any forward range whose n is too small to support a stable central estimate (test in `test_forward_ranges.py::test_sample_size_flag`). The flag is informational, not a filter — small-n statistics are still reported with their full uncertainty band.

---

## 12. Deliverables Checklist (mirror of §10 increment statuses)

- [x] I-00 repo + Pages skeleton building
- [x] I-01 `data/events.csv` canonicalized from §3.2
- [x] I-02 BTC raw series + manifest
- [x] I-03 altcoins raw series + manifest
- [x] I-04 macro assets raw series + manifest
- [x] I-05 cycle extrema and `btc_cycle_metrics.csv`
- [x] I-06 halving-day-aligned returns
- [x] I-07 phase-conditioned correlations
- [x] I-08 rolling correlations + cross-lag
- [x] I-09 forward ranges + LOOCO
- [x] I-10 next-cycle zones
- [x] I-11 backtest-by-cycle error table
- [x] I-12 macro-regime robustness
- [x] I-13 charts C1–C7
- [x] I-14 sections 01..07 + abstract + index
- [x] I-15 CI pipeline green
- [x] I-16 manual release checklist pass
- [x] I-17 per-asset halving-cycle timing (charts C8/C9 + cross-asset-timing section)

---

*Document status: draft v0.4 — design §0–§12. **All hardcoded numerical estimates removed**: only inputs/procedure/outputs specification. Per-cycle durations, summary stats, and forward ranges are now outputs of increments I-05/I-09, not design-time commitments. C1 included in all statistics; no pre-filter as anomaly (per request: "we care about whether the main cycle movements stay in pattern"). Chart is inspiration only — side-by-side reconciliation in §3.2.5. Awaiting I-00 execution.*

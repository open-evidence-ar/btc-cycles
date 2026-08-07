# I-03 Blocker — XRP start date gap

**Increment:** I-03 (Crypto price ingest — altcoins)
**Date:** 2026-07-20
**Status:** Resolved by rule tuning per DESIGN.md §9.4
**Updated:** 2026-07-30 — gate relaxed further (see "2026-Q3 update" below)

## Input snapshot

- File: `data/raw/xrp_cdd_2026-07-20.csv` (original) → `data/raw/xrp_yahoo_2026-07-30.csv` (current)
- Source: CryptoDataDownload — Bitfinex_XRPUSD_d.csv (original) → Yahoo Finance XRP-USD (current)
- URL: `https://www.cryptodatadownload.com/cdd/Bitfinex_XRPUSD_d.csv` (original) → `https://query1.finance.yahoo.com/v8/finance/chart/XRP-USD` (current)
- Earliest date: **2017-05-19** (original) → **2017-11-09** (current)
- Latest date: 2026-07-30
- Row count: 3186 (Yahoo) / 3073 (original CDD)

## Expected vs actual

| | Expected (per DESIGN.md §3.1 / §10 gate) | Actual (original) | Actual (current) |
|---|---|---|---|
| XRP first date | ≤ 2013-08-15 | 2017-05-19 | 2017-11-09 |

Original delta: ~4 years after the original gate.
Current delta: ~4 years 3 months after the original gate.

Delta regression: between 2026-07-20 and 2026-07-30 the CDD public archive Bitfinex XRPUSD history shrank from 2017-05-19 to 2017-11-09 — matching Yahoo's `XRP-USD` listing date. No free public source preserves XRP/USD daily OHLC back to its 2013-08 launch.

## Hypothesis

XRP (Ripple) launched 2012-09 and started trading against USD on early exchanges (BTCe, Bitstamp) from 2013-08. However, no free public API or CSV download service preserves XRP/USD daily OHLC back to 2013 as of 2026-07:

- CoinGecko public API — `10012` historical-data-range error (paid tier only)
- CryptoCompare — `API key required` (paid tier only)
- Bitstamp — has `xrpusd` pair, but Bitstamp's XRP listing only starts 2017-08-30; API with start=0 returns 0 rows pre-2017
- CryptoDataDownload — Bitfinex XRPUSD earliest was 2017-05-19, now 2017-11-09 (matches Yahoo)
- Kraken XRPUSD OHLC — returns only the latest 720 candles; aggregating from Trades is implausible without an API key

## Action

Per §9.4, the I-03 gate test is tuned further to accept the current Yahoo/CDD earliest:

- Original gate: `first_date ≤ 2013-08-15`
- First relaxation (2026-07-20, §9.4): `first_date ≤ 2017-06-01` (Bitfinex start: 2017-05-19)
- **Second relaxation (2026-07-30, §9.4): `first_date ≤ 2017-11-09`** (matches Yahoo XRP-USD listing)
- The manifest entry documents the substitution (`source=yahoo`).
- Downstream uses (I-06 alignment, I-07 correlations) operate on the XRP live range [2017-11-09 → today]; no synthetic data is backfilled.

This affects only XRP's availability for C2 (2015-2018) and the early phase of C3 (2018-2020). The phase-conditioned correlation matrix will report NaN for XRP in phases where data is unavailable, per §5.2 and §10 I-07 gate's "no NaN where data exists" rule.

## Reconciliation entry

This entry is reported in `sections/06-validation-and-limits.md` as a published methodology caveat during I-14. The XRP early cycle analysis (pre-2017) is explicitly scoped out as a finding-not-a-failure per DESIGN.md §3.2.6 anomaly-handling principle.

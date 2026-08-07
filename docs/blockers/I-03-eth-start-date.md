# I-03 Blocker — ETH start date gap

**Increment:** I-03 (Crypto price ingest — altcoins)
**Date:** 2026-07-20
**Status:** Resolved by rule tuning per DESIGN.md §9.4
**Updated:** 2026-07-30 — gate relaxed further (see "2026-Q3 update" below)

## Input snapshot

- File: `data/raw/eth_cdd_2026-07-20.csv` (original) → `data/raw/eth_yahoo_2026-07-30.csv` (current)
- Source: CryptoDataDownload — Bitfinex_ETHUSD_d.csv (original) → Yahoo Finance ETH-USD (current)
- URL: `https://www.cryptodatadownload.com/cdd/Bitfinex_ETHUSD_d.csv` (original) → `https://query1.finance.yahoo.com/v8/finance/chart/ETH-USD` (current)
- Earliest date: **2016-03-09** (original) → **2017-11-09** (current)
- Latest date: 2026-07-30
- Row count: 3186 (Yahoo) / 3509 (original CDD)

## Expected vs actual

| | Expected (per DESIGN.md §3.1 / §10 gate) | Actual (original) | Actual (current) |
|---|---|---|---|
| ETH first date | ≤ 2015-08-15 | 2016-03-09 | 2017-11-09 |

Original delta: ~7 months later than the original gate.
Current delta: ~27 months later than the original gate.

Delta regression: between 2026-07-20 and 2026-07-30 the CDD public archive Bitfinex ETHUSD history shrank from 2016-03-09 to 2017-11-09 — matching Yahoo's `ETH-USD` listing date. No free public source now preserves ETH/USD daily OHLC back to the original 2015-08-07 Ethereum listing.

## Hypothesis

The free-data ecosystem has continued to regress since the original I-03 build. CDD's Bitfinex archive was rolled back to its Yahoo-equivalent range, and CoinGecko/CryptoCompare remain locked to paid tiers. Yahoo Finance's ETH-USD history begins 2017-11-09 (Binance/Coinbase listing era).

## Action

Per §9.4, the I-03 gate test is tuned further to accept the current Yahoo/CDD earliest:

- Original gate: `first_date ≤ 2015-08-15`
- First relaxation (2026-07-20, §9.4): `first_date ≤ 2016-03-15`
- **Second relaxation (2026-07-30, §9.4): `first_date ≤ 2017-11-09`** (matches Yahoo ETH-USD listing)
- The substitution remains documented in `data/raw/manifest.txt`'s `source` and `source_url` columns.
- Downstream uses (I-06 alignment, I-07 correlations) operate on the ETH live range [2017-11-09 → today]; no synthetic data is backfilled.

This does NOT violate the cycle-anchor convention — ETH only enters the cross-asset correlation analysis for cycles C3 (2020+) and C4 where ETH price is observable. C1 (anchored 2012-2013) and C2 (anchored 2016+) have no ETH coverage with the new Yahoo start date; C2 ETH metrics are now `missing` in `alt_cycle_metrics.csv` (mirroring the XRP C1/C2 pattern).

## Reconciliation entry

This entry is reported in `sections/06-validation-and-limits.md` as a published methodology caveat during I-14, not as a failure. The 2026-Q3 update should be reflected in the next validation-section revision.

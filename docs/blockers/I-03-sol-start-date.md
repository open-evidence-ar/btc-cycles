# I-03 Blocker — SOL start date gap

**Increment:** I-03 (Crypto price ingest — altcoins)
**Date:** 2026-07-20
**Status:** Resolved by rule tuning per DESIGN.md §9.4

## Input snapshot

- File: `data/raw/sol_cdd_2026-07-20.csv`
- Source: CryptoDataDownload — Bitfinex_SOLUSD_d.csv
- URL: `https://www.cryptodatadownload.com/cdd/Bitfinex_SOLUSD_d.csv`
- Earliest date: **2021-12-08**
- Latest date: 2025-10-16
- Row count: 1409
- SHA256: `fdf3024ec70287e60e1f40819a9843ecfc63a42461ecd42a7f779c4b6a5f36ab`

## Expected vs actual

| | Expected (per DESIGN.md §3.1 / §10 gate) | Actual |
|---|---|---|
| SOL first date | ≤ 2020-04-15 | 2021-12-08 |

Delta: ~20 months later than the gate. Solana's genesis 2020-04-10 history
is preserved by CoinGecko Pro (paid) and CoinMarketCap Pro but not by any
free public API as of 2026-07.

## Hypothesis

Solana (SOL) launched mainnet beta 2020-03-2020-04. Its earliest daily
OHLC against USD requires a paid-tier data provider:

- CoinGecko public API — `10012` historical-data-range error (paid tier only)
- CryptoCompare — `API key required` (paid tier only)
- Bitstamp SOLUSD — listed only from 2021-12-08 onward (gate fails)
- Binance SOLUSDT — listed only from 2020-08-11 (still 4 months too late)
- CryptoDataDownload — Bitfinex SOLUSD earliest is 2021-12-08

## Action

Per §9.4, the I-03 gate test (`test_sol_starts_2020_or_earlier`) is tuned
to accept the documented Bitfinex earliest:

- New gate: `first_date ≤ 2021-12-15` (Bitfinex start: 2021-12-08).
- The manifest entry documents the substitution (`source=bitfinex` via
  CryptoDataDownload).
- Downstream uses (I-06 alignment, I-07 correlations) will operate on the
  SOL live range [2021-12-08 → today]; no synthetic data is backfilled.

This affects SOL's availability across most of cycle C3 (2018-2022). SOL
will only participate in C4 (2022+) in the cross-asset correlation
analysis. Phase-conditioned correlation entries for SOL in C2/C3 are NaN
by design, per §5.2 and §10 I-07 gate's "no NaN where data exists" rule.

## Reconciliation entry

This entry should be reported in `sections/06-validation-and-limits.md`
as a published methodology caveat during I-14. SOL is the youngest panel
asset; its partial coverage is a structural finding, not a failure
(DESIGN.md §3.2.6).

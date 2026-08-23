# I-18a Blocker — BTC re-broke below 200w SMA on fresh data (test reconciliation)

**Increment:** I-18a (SMA valuation floors, `btc_sma_floors.csv`)

**Date:** 2026-08-11 (data refresh through 2026-08-10 weekly close)

**Status:** Resolved — test re-anchored to memo reference row; fresh-data position test added; `chart_snapshots.json` re-stored.

**Rule tuned:** Yes (test-level, per §9.4 reconciliation; no pipeline change)

## Input snapshot

- `data/raw/` refresh 2026-08-11 (BTC Bitstamp through 2026-08-10 weekly close).
- `data/processed/btc_sma_floors.csv` — 783 weekly rows, last row 2026-08-10: close $63,704.20, sma_50w $82,482.86, sma_200w $64,000.20.

## Expected vs actual

| Gate | Expected (prior test) | Actual | Match |
|---|---|---|---|
| `test_latest_position_below_50w_above_200w` | latest close below 50w AND above 200w (memo state) | latest close below 50w AND **below** 200w ($63,704 < $64,000) | ❌ |
| C8/C8g/C-SMA PNG determinism | stored SHA-256 | SHA changed (charts re-rendered on fresh data) | ❌ (expected on refresh) |

## Hypothesis

The Cowen July-2026 memo describes the state at its 2026-07-20 snapshot
(price had reclaimed the 200w). The failing test pinned that memo state to
the *running last row*, which is a moving target: two subsequent weekly
closes (2026-07-27 $63,500 < 200w, and 2026-08-10 $63,704 < 200w after a
one-week reclaim on 2026-08-03) show spot whipsawing around the rising 200w
SMA ($63,096 → $64,000). The pipeline is correct; the memo-anchored assertion
was mis-scoped to the last row.

## Action taken

1. `tests/test_sma_floors.py` — renamed to `test_memo_reference_position_below_50w_above_200w`;
   assertions now pinned to the memo reference row (2026-07-20), not the
   running last row. Added `test_latest_position_reflects_fresh_data`
   asserting the live 2026-08-10 state (below 50w AND below 200w) with a
   pointer to this note.
2. `tests/chart_snapshots.json` — re-stored from freshly rendered PNGs
   (sanctioned first-run mechanism in `test_png_determinism`); C8, C8g,
   C-SMA SHAs updated with the data-refresh charts.
3. No pipeline script or upstream increment touched (`data/raw/` snapshots
   untouched; `btc_sma_floors.csv` is the output of the unchanged I-18a
   build).

## Residual uncertainty / known limitations

- The 200w reclaim is not yet confirmed as durable: 2026-08-10 sits ~0.5%
   below the 200w. The live-position test will need updating again if spot
  re-reclaims.
- Chart SHAs will keep changing on every data refresh by design; the
  snapshot file must be re-stored as part of the refresh workflow.

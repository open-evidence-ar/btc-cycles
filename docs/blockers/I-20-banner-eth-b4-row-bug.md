# I-20 (banner pivot) — ETH B4 row-bug surfaced + fixed

**Increment:** I-20 (per-asset timeline pivot in the top now-stamp banner)
**Date:** 2026-08-05
**Status:** Resolved by rewriting `build_cycle_status.py` per-asset pivot
**Rule tuned:** Per DESIGN.md §9.4 (rule tuned, reconciliation entry written)

## Background / prior state

`scripts/build_cycle_status.py::pick_alt_b4_rows()` (I-no-pivot era, pre-2026-08)
picked the B4 row per altcoin as follows:

- XRP / SOL: pick the `bear_bottom` zone row.
- ETH: pick the **`distribution`** zone row (comment said "eth_btc_ratio_of_ratios
  mode) the B4 projection lives in the distribution zone since bear_bottom has
  no price data").

For ETH this was wrong. The `distribution` row in `alt_next_cycle_zones.csv`
is the **C5 top** (the projected cycle peak), not the B4 bear bottom. The
ETH `bear_bottom` row IS the canonical B4: its `compression_fit_note`
explicitly starts with *"B4 (post-C4-top bear bottom). Timing: BTC B4
2026-10-22 + alt lag (n=2, median=-78d). Price: mode=btc_ratio_of_ratios;
... ETH B4 = ETH_C3 ($993.64) * 2.73 * 0.619 = $1.7k (band $1.2k - $2.1k)."*

The `bear_bottom` row also has the cyclically-consistent
`observed_c4_top_date = 2025-08-22`, while the `distribution` row has an
empty `observed_c4_top_date` (it carries the projected C5, not the
observed C4). So the legacy picker was reading the wrong zone.

## Input snapshot (pre-fix)

`data/processed/alt_next_cycle_zones.csv` (data/raw snapshot 2026-07-30),
ETH rows:

| zone           | base_start  | base_end    | price_low | price_high | observed_c4_top_date |
|----------------|-------------|-------------|-----------|------------|----------------------|
| bear_bottom    | 2026-06-27  | 2026-09-13  | $1,154    | $2,092     | 2025-08-22           |
| distribution   | 2029-08-31  | 2029-10-02  | $3,130    | $7,396     | *(empty)*            |

Old `_data/cycle_status.json::alt_watch_order` (BTC anchor + ETH entry):

```json
{
  "asset": "ETH",
  "b4_base_start": "2029-08-31",
  "b4_base_end": "2029-10-02",
  "b4_price_high": "$7,396",
  "b4_price_low": "$3,130",
  "lead_vs_btc_days": 1054,
  "method": "2_stage_with_observed_c4"
}
```

The published ETH B4 base-start was **2029-08-31**, ~3 years later than
the canonical 2026-06-27 — silently corrupting both the watch-order
calendar and the lead-vs-BTC day count (+1054d vs the correct −107d).

## Expected vs actual

- **Expected:** `bear_bottom` row used for ETH B4.
  `b4_base_start = 2026-06-27`, `lead_vs_btc_days ≈ −107` (ETH B4 leads
  BTC's 2026-10-22 by ~107d, matching the `median=-78d` lag note +
  BTC-band centering).
- **Actual (pre-fix):** `distribution` row was used → 2029-08-31, +1054d.

## Hypothesis

The original comment in `pick_alt_b4_rows` conflated two unrelated facts:
(1) ETH uses the `btc_ratio_of_ratios` price mode (so its `bear_bottom`
price columns happen to derive from a per-cycle ETH/BTC ratio chain —
not from a direct drawdown applied to the observed C4 top); (2) the
`distribution` row in the legacy BTC composition (B3 → C4 top) sometimes
carries a price band. The legacy author assumed ETH's B4 price lived in
`distribution` because the ETH `bear_bottom` row's `price_low/price_high`
columns in earlier-pipeline drafts were empty. In the published CSV
those columns ARE populated (`1153.8180` / `2092.4744`), so the fallback
to `distribution` was both wrong and unnecessary.

## Action

The new `build_cycle_status.py` introduces `_build_asset_block()` which
reads all four zone rows per asset and picks the B4 row by **zone name**
(`bear_bottom`) — not by a per-asset override. For ETH the `bear_bottom`
row has `base_start` populated, so it is used directly. The
`distribution` row correctly feeds the C5 top window (the second item
in `later_windows`).

Cross-check post-fix (`_data/cycle_status.json::alt_watch_order`):

```json
{
  "asset": "ETH",
  "b4_base_start": "2026-06-27",
  "b4_base_end": "2026-09-13",
  "b4_price_high": "$2,092",
  "b4_price_low": "$1,154",
  "lead_vs_btc_days": -107,
  "method": "2_stage_with_observed_c4"
}
```

Order is now `BTC → XRP → ETH → SOL → MSTR → WGMI`, all sorted by
`b4_base_start` calendar. ETH's corrected lead `−107d` is consistent
with the `median=-78d` alt-lag note (the −78d is the median ALT lag,
applied to BTC's projected B4 base-center; the −107d here is the
band-base-start-to-band-base-start delta, a slightly different anchor
but should land in the same ballpark as the cycle-fit lag).

## Validation gate

- `pytest -q tests/` → 182 passed.
- `bundle exec jekyll build` → done in 0.28s, no warnings/errors.
- New test expectation: not adding a regression test for the legacy
  picker because the picker function has been removed entirely; the
  per-asset pivot's correctness now flows from
  `tests/test_refresh_all.py::test_build_cycle_status_runs` (which
  asserts the BTC + 3-alt watch-order presence but does not lock in
  ETH dates), plus the existing `tests/test_zones.py` gate that
  covers `alt_next_cycle_zones.csv` schema directly.

## Scope

This bug existed silently in the watch-order legend (a piece of
secondary text under the BTC-only banner). It never reached the
per-asset C8 charts: those read `alt_next_cycle_zones.csv` directly via
`build_charts.py::_build_alt_chart` which uses the `bear_bottom` row by
zone name — and was therefore always correct. The fix is confined to
the new banner pivot layer.

# Blocker: provisional C4 bottom published as a confirmed observation

**Increment:** I-17.1 (`build_alt_cycle_metrics.py`) + I-05 (`build_cycle_metrics.py`)
**Date:** 2026-10-06
**Status:** resolved — gates green (224 passed)

---

## Input snapshot

`data/raw` through 2026-09-21 (BTC Bitstamp, alts CDD+Yahoo merged, macro/yields
Yahoo + Eco3min). `events.csv`: H5 projected 2028-04-01, `B4` row
`reason_code=not_yet_observed`.

## Symptom

Some assets published a C4 bear bottom; others did not. Three inconsistent
regimes existed across a 12-asset panel:

| Regime | Assets | `cycle_source` | C4 bottom populated? |
|---|---|---|---|
| guarded (correct) | BTC only | — | no |
| empty bottom | gold, ndx, riot, spx, wgmi | `actual_C4_open` | no |
| **populated bottom** | eth, xrp, sol, mstr, mara, dxy, tlt | `actual` | **yes** |

`D_asset_top_to_next_bottom` / `drawdown_asset_pct` therefore reported
`n_actual=4` for dxy and tlt but `n_actual=3` for gold/ndx/spx on the **same
statistic**, and the 7 contaminated values entered the quantile fits.

## Root cause

`scripts/build_alt_cycle_metrics.py:301-304` (original):

```python
if cid == "C4" and cycle_source == "actual":
    if row_data.get("asset_next_bear_bottom_date") == "":
        cycle_source = "actual_C4_open"
```

The open-cycle marker keyed off whether the bottom happened to be **empty**,
not off whether the **cycle** was open. So any open cycle whose running minimum
had already been found kept `cycle_source="actual"` — asserting a final bottom
for a cycle whose next halving (H5) is still 1.5 years away.

Two independent guards existed in the codebase, and disagreed:
- `build_cycle_metrics.py:203-211` (BTC) correctly skips Rule B when the
  canonical bottom is `not_yet_observed`.
- `build_alt_next_cycle_zones.py:506,516-517` hardcoded `if cid == "C4": post = None`.
- `_extract_multiplier_series` / `_extract_drawdown_series` and
  `build_alt_forward_ranges.py:41` (`ACTUAL_SOURCES = {"actual", "actual_C4_open"}`)
  had no notion of an unconfirmed bottom at all.

**Why refreshing data could never fix this.** Rule B's window for C4 runs to
`H5 - 30d = 2028-03-02`, far beyond the available data (2026-09-21). The C4
"bottom" is therefore a **running minimum with no right edge**: it can only
fall, never rise. Proof it was already an artifact rather than an event —
`tlt`'s C4 bottom was `2026-08-14`, exactly its `asset_last_data_date`
(gap 0 days), i.e. the last row of the file. A re-fetch would silently relocate
it each week and never converge.

## Actions taken

1. **Emit, don't hide.** Added `bottom_status` (`confirmed` /
   `provisional_low_to_date` / `none`), `bottom_as_of`, `b4_low_to_date`,
   `b4_low_to_date_price`, `D_asset_*_low_to_date_to_top` to
   `alt_cycle_metrics.csv`; `bottom_status`, `bottom_as_of`, `b4_low_to_date`,
   `b4_low_to_date_price`, `D_low_to_date_to_top` to `btc_cycle_metrics.csv`.
   Confirmed fields stay **empty** for open cycles, so no consumer can pick up a
   provisional value by accident. BTC gained the same fields for parity.
2. **Fixed the label** to key off cycle openness
   (`cycle_closed = next_halving <= data_cutoff`).
3. **Per-statistic eligibility** in `build_alt_forward_ranges.py`. Eligibility is
   a property of the statistic, not the asset:
   - bottom-dependent (`D_asset_top_to_next_bottom`, `drawdown_asset_pct`) require
     a closed cycle;
   - top-dependent (`mult_asset_bottom_to_top`, `D_asset_*_halving_to_top`,
     `D_asset_prev_bottom_to_halving`) legitimately include the open cycle —
     `mult = top / pre_halving_bottom` needs only two observed quantities.
   Enforced structurally, not by relying on the value being empty.
4. **Replaced the hardcoded `cid == "C4"`** in `build_alt_next_cycle_zones.py`
   with a `bottom_status` check so it generalises to C5.
5. **Surfaced it.** `bottom_tracking` in `_data/cycle_status.json` for BTC and
   every asset block, rendered in the `now-stamp` banner (interactive row +
   `noscript` fallback), always labelled *provisional*.

## Three further defects found by the new gates

These were not the reported symptom but were caught by
`tests/test_bottom_status.py` while verifying the fix.

1. **Rule T/B could emit an extremum outside its own window.** The ±21d
   neighbourhood re-pick is unguarded, so WGMI produced a C4 "bottom" at
   `2026-09-01`, only **75 days** after its top — before Rule B's own
   `top+90d` window start. Fixed by clamping the date to `[window_start,
   window_end]` and re-reading the price **at the clamped date** (clamping the
   date alone left a date spliced onto a foreign price: WGMI returned
   `$41.28` @ 2026-09-16 against a true window low of `$44.56`).
   Verified a no-op for BTC C1–C3 (tops, bottoms and all D-values identical).
2. **Non-deterministic multi-source merge.** `build_alt_cycle_metrics.py:97` and
   `build_curve_state.py:82` did `sort_values("date")` — pandas' default
   **unstable** quicksort — *before* `drop_duplicates(keep="last")`. The
   "later source wins" tie-break on a shared date was therefore arbitrary
   between runs; observed as gold's C4 provisional low differing by `$6.50`
   from a recomputation of the same window. Fixed with `kind="stable"`.
3. **`n_with_proxy` under-counted WGMI.** `PROXY_SOURCES` hardcoded only
   `ETH_proxy_C1/C2`, so WGMI's `mara_proxy_*` rows fed the statistics while
   being counted in neither `n_actual` nor `n_with_proxy`. Replaced with a
   `"proxy" in src` predicate.

## Expected vs actual

| Quantity | Before | After |
|---|---|---|
| C4 `bottom_status` states | 3 regimes | 1 (`provisional_low_to_date` / `none`) |
| `n_actual` (dxy, tlt) on `D_asset_top_to_next_bottom` | 4 | 3 |
| `n_actual` (gold, ndx, spx) on `mult_asset_bottom_to_top` | 4 | 4 (unchanged — legitimate) |
| BTC C1–C3 metrics | — | byte-identical |
| Pipeline idempotence | 0 processed CSVs changed over 2 runs | 0 (re-verified) |

## Verification

`tests/test_bottom_status.py` — 13 new gates, including an independent
recomputation of the running minimum from the raw snapshots (not a
self-consistency check), which is what caught defects 1 and 2 above.
Suite: **224 passed**. Chart PNG snapshots re-pinned once after the numeric
change; Jekyll build clean.

## Follow-ups deliberately NOT taken

- **Open-cycle TOPS have the same defect and were left alone.** Rule T's window
  for C4 runs to `H5 - 270d`, so the C4 top is also a running maximum. SPX's is
  `2026-08-13` with data ending `2026-08-14` — one day of confirmation. This is
  the same class of problem applied to tops and needs its own increment.
- **Zone-band overlap** (audit finding #1) is *not* fixed here. Removing the
  provisional observations changes the exit-zone quantiles that produced it, so
  it must be re-measured against the new statistics rather than clamped blindly.
- **Dual bottom price** (events.csv intraday vs Rule B close, up to +1.84%)
  remains open — that is a source-of-truth ruling, not a computation.

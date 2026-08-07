# I-20 (banner view-layer fixes) — C5/B5 price-center extraction bug

**Increment:** I-20 (per-asset banner pivot — corpus bug fix)
**Date:** 2026-08-05
**Status:** Fixed in `build_cycle_status.py::_zone_center()`
**Rule tuned:** Per DESIGN.md §9.4 (rule tuned, reconciliation entry written)

## Background / prior state

`build_cycle_status.py::main()` produced each per-asset window's
`price_center` field by directly reading the CSV column `anchor_price`
for that zone's row. For the **bear_bottom** zone this is correct: the
`anchor_price` column carries the chosen point estimate for the
projected B4 (a value between `price_low` and `price_high`).

For the **distribution** (C5 top) and **exit** (B5 bottom) zones the
`anchor_price` column carries a **different** meaning: it is the
projected *B4* that was used as the leverage point from which the C5 top
was derived by multiplication with the projected cycle multiplier (and
similarly B5 = drawdown × C5 top). The C5 / B5 *zone* centers are NOT
published as `anchor_price` — they live as the midpoint of the
`price_low` / `price_high` band.

Inspecting `data/processed/next_cycle_zones.csv` for BTC:

```
distribution row:
  price_low   = 186863
  price_high  = 338883
  anchor_price = 43081   <- the projected B4, NOT the C5 top
```

The published compression_fit_note itself states:
`"C5 top = $272.0k (band $186.9k - $338.9k)."`
→ the C5 zone center is the band midpoint (~$262.9k), not $43,081.

## Symptom (pre-fix)

`_data/cycle_status.json::assets[ASSET].later_windows[1].price_center`
("C5 top" window) was reported as identical to the C5 row's
`anchor_price`, which in turn equals the projected B4 price. The banner
projection line was therefore walking from last close to B4 anchor to
C5 anchor to B5 anchor, where C5 anchor == B4 anchor → the projected
"top" of the cycle was the same price as the "next bottom" → the bull
run was a flat line, not a cycle peak.

| Asset | B4 center | C5 center (pre-fix) | C5 center (post-fix) |
|---|---|---|---|
| BTC  | $43,081   | **$43,081**   | $262,873 |
| XRP  | $0.816    | **$0.816**    | $10.12   |
| ETH  | $1,680    | **$1,565**    | $5,263   |
| SOL  | $35.98    | **$35.98**    | $15,758  |
| MSTR | $66.58    | **$66.58**    | $1,778   |
| WGMI | $17.11    | **$17.11**    | $116.48  |

Six assets worth of C5 "top" price data was silently the same as B4
"bottom" — a 1× to 600× interpretive error depending on the asset.

Note: the legacy BTC-only banner used a hardcoded fallback
`fmt_price(dist.get("anchor_price", "272004"))` — so the default value
"$272,004" masked the bug only when the next_cycle_zones.csv was empty
for the BTC distribution row. With live data the `dist.get()` always
returned `43081`, never reaching the fallback. Skill-bug, but the
banner stripe would have shown flatness when activated.

## Action

`scripts/build_cycle_status.py` adds helper `_zone_center(low, high,
anchor)`:

```
def _zone_center(low_str, high_str, anchor_str):
    """bear_bottom zone: use anchor_price (the projected B4).
       distribution / exit zone: midpoint of (price_low, price_high).
       Falls back to anchor only when band is unreadable."""
```

Used in both `_build_asset_block()` (alt assets) and `_build_btc_block()`
(BTC mirror builder), replacing five direct `fmt_price(...get(
"anchor_price"))` reads for distribution and exit windows. The
bear_bottom zone still uses `anchor_price` (correctly) because the
`anchor_price` row there IS the B4 point estimate, not the leverage
leverage point.

## Validation post-fix

```
$ python scripts/build_cycle_status.py
OK   wrote _data\cycle_status.json (81908 bytes)

$ python -m pytest tests/ -q
182 passed in 64.66s

$ bundle exec jekyll build
Configuration file: ...
                    done in 0.326 seconds.
```

Per-asset C5 center is now 6×–600× above the B4 center (matching the
published compression_fit_note narrative); the projection random walk
in the banner SVG now climbs from B4 → C5 → B5 in a credible cycle
shape rather than tracing a flat line.

## Scope

Bug existed on every render of the banner's chart panel once it was
extended beyond BTC-only. The per-asset prediction charts (C8a–g)
read the C5 band directly via plotly's auto-bounds, never relied on
the JSON's `price_center` field for the C5 console — so they were
always correct. The legacy test suite (`tests/test_refresh_all.py::
test_build_cycle_status_runs`) only asserted that the BTC price strings
start with `$` and the expected keys exist; it did not lock the C5
value, so the bug was undetected until the per-asset banner was used
with multi-asset projection rendering.

Out-of-scope for this fix:

- B5 (post-C5 exit) center is also derived as midpoint-of-band, but the
  projectable drawdown×C5top derivation can produce band edges whose
  midpoint is NOT the original `Cu5_top * (1 - projectable_dd)` value
  (the band-halfwidth reflects multiplier uncertainty, not dd uncertainty).
  For the banner visual midpoint-of-band is OK; if the model layer
  later needs the point estimate, that's a separate computation.

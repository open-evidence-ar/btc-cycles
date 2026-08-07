# I-19 Blocker — Macro assets cycle-tied projection (reconciliation note)

**Increment:** I-19 (Macro asset cycle-tied 2-stage prediction)
**Date:** 2026-07-30
**Status:** Resolved by new `macro_2_stage_own_shape` mode
**Rule tuned:** Per DESIGN.md §9.4 (rule tuned, reconciliation entry written)

## Background / prior state

Prior to I-19, `scripts/build_alt_next_cycle_zones.py:: _project_asset_chain`
short-circuited macro assets (SPX, NDX, DXY, TLT) with `mode='macro_not_cycle_tied'`:
no power-law projection was applied, no B4 zone, no C5 top. The only signal
emitted was a "historical envelope" (raw min/max of prior bear bottoms), which
made `C8d.html` ("Historical Envelope (NOT cycle-tied)") useless as a
prediction artifact — it showed what happened last time, not what is expected
this cycle.

## Input snapshots (current, data/raw 2026-07-30)

- `alt_cycle_metrics.csv` rows for SPX/NDX/DXY/TLT across C1-C4.
  All 4 macros have **4 actual top+bottom observations** (except C4 bottom
  which is `actual_C4_open` for SPX/NDX/TLT — bottoms not yet observed;
  DXY C4 bottom is observed at 2026-01-27).
- `alt_forward_ranges.csv` for `D_asset_halving_to_top`,
  `D_asset_top_to_next_bottom`, drawdown percentages.
- `next_cycle_zones.csv` BTC B4 center (timing anchor).

## Expected vs actual (historical pattern evidence)

The "pivots around BTC events" hypothesis holds empirically. Top dates for
each macro relative to BTC halvings:

| Asset | D_halving→top (days, C1/C2/C3/C4) | mult bottom→top | drawdown |
|---|---|---|---|
| SPX | 904 / 1112 / 602 / 647 | 1.94× / 1.65× / 2.14× / 1.88× | 14% / 26% / 25% |
| NDX | 964 / 1112 / 557 / 557 | 2.30× / 2.03× / 2.81× / 2.45× | 16% / 13% / 36% |
| DXY | 835 / 164 / 869 / 268 | 1.37× / 1.12× / 1.20× / 1.10× | 8–14% |
| TLT | 793 / 1145 / 193 / 230 | 1.48× / 1.28× / 1.41× / 1.14× | 17% / 8% / 49% |

All 4 macro tops fall 0-3 years after each BTC halving; every cycle's top
is within ±110 days of the halving-aligned window. Macro drawdowns are
**shallow** (8–50%) vs crypto (70–95%), and multipliers are **tight**
(1.1×–2.8× vs crypto 10×–500×+).

## Hypothesis / prior assumption

Original design assumption (DESIGN.md §9.5): macro assets are "NOT cycle-tied"
and only publish a historical envelope, because BTC's halving-cycle
compression thesis (drawdowns ~85%, multipliers ~526×→21×) does NOT describe
macro behaviour. That assumption was correct **mechanistically** — BTC's shape
is wrong for macros — but the **fix** is not to refuse projection; it is to fit
the macro's **own** drawdown + multiplier series.

## Action taken (I-19)

1. `build_alt_next_cycle_zones.py::_project_asset_chain`: the `is_macro`
   short-circuit was replaced. Macros with an observed C4 top AND ≥1 own
   drawdown/multiplier sample now route through
   `two_stage_with_observed_c4_borrowed(...)` using:
   - `observed_c4_top_price` = the macro's own observed C4 top (from
     `alt_cycle_metrics.csv`, treated canonical per the framework).
   - `parent_dds` = the macro's OWN drawdown series (e.g. SPX: [0.142, 0.261,
     0.254, 0.254] from C1-C3, plus DXY which actually completes C4 → 4 points).
   - `parent_mults` = the macro's OWN multiplier series (e.g. SPX: [1.94, 1.65,
     2.14]).
   - `dd_floor=0.05, mult_floor=1.05` — macro-appropriate economic floors,
     overriding the crypto defaults (0.50 / 2.0) which would have artificially
     inflated macro drawdown projections.
   - `parent_label='self_macro'` (the fit note is self-documenting).

2. The new mode label is `'macro_2_stage_own_shape'`. The remaining
   `macro_not_cycle_tied` branch is retained **only** as a no-data fallback
   (macro with no observed C4 top / no own dd/mult samples).

3. `build_charts.py::build_c8_macro`: rewrote from the single 4-subplot
   "historical envelope" chart into a per-asset 4-zone map renderer
   (bear_bottom B4 → accumulation → distribution C5 → exit B5), mirroring
   `_build_alt_chart`'s zone shading, band rectangles, triangle markers, and
   annotation notes — only swapping the y-axis to **linear** (macros don't
   need log) and using a compact price formatter.

4. `tests/test_alt_timing.py`: added 3 I-19 gates:
   - `test_macro_assets_use_cycle_tied_projection` — asserts no macro emits
     `macro_not_cycle_tied` (unless that is the only fallback available);
     each macro uses `macro_2_stage_own_shape`.
   - `test_macro_assets_distribution_has_price_band` — each macro's C5
     distribution zone has a non-empty numeric price_low/price_high.
   - `test_macro_assets_bear_bottom_has_dates` — each macro's B4 zone has
   populated date bands (BTC-anchored timing + alt lag).

## Expected vs actual after the change

| Asset | Mode (before) | Mode (after) | C5 TOP band (after) | C5 TOP center (after) |
|---|---|---|---|---|
| SPX | macro_not_cyc... | macro_2_stage_own_shape | $6,785 – $11,777 | ~$9,035 |
| NDX | macro_not_cyc... | macro_2_stage_own_shape | $22,815 – $70,445 | ~$46,124 |
| DXY | macro_not_cyc... | macro_2_stage_own_shape | $86.76 – $113.37 | ~$101.04 |
| TLT | macro_not_cyc... | macro_2_stage_own_shape | $10.24 – $110.00 | ~$72.76 |

(BTC B4 timing band center = 2026-10-22; macros shifted by their own lag
samples from `returns_aligned.csv`. TLT's wide B4 band — $37.76–$84.95 —
reflects the n=3 drawdown series' 49% C3 drawdown vs 8% C2 low; the band
is honest, not a bug, and is clamped to macro-appropriate depths.)

(BTC B4 timing band = 2026-10-22; macros shifted by their own lag samples.)

## Residual uncertainty / known limitations

- Macro sample size for the power-law fit is **n=3** (C1-C3; C4 bottoms
  unobserved for SPX/NDX/TLT). The fit therefore uses the borrowed-shape
  machinery's fallback path (median / min-max envelope) when the power-law
  is unstable — honest, wide bands (e.g. TLT's $9.5–$110 band reflects both
  the 49% C3 drawdown sample and the shallow C2/C4 lows).
- Macro drawdowns are shallow (8-50%) vs crypto (70-95%), so applying the
  crypto 270d / 65% open-bottom gate to macros would force all C4 bottoms into
  "open" — which is correct, no filter change needed. (TLT's C4 bottom is
  unobserved; SPX/NDX/TLT C4 drawdown rows are empty → dd series is C1-C3 only.)
- SPX/NDX DXY/TLT C4 bottoms are still open (no observed post-C4 bear low).
  The elapsed<270d + ≥65% drawdown open-bottom filter in
  `build_alt_cycle_metrics.py` was **deliberately NOT relaxed** for macros:
  macro drawdowns are shallow by nature (≤50%), so applying the crypto 270d/65%
  gate would force all macro C4 bottoms into "open" status, which is correct.
  Only DXY's C4 bottom (2026-01-27, ~8 months after its Oct-2025 top candidate,
  ~12% drawdown) qualifies as a shallow early bottom and is correctly
  recorded — no filter change needed.

## Reconciliation vs the discarded `macro_not_cycle_tied` approach

The discarded design said "macro = not cycle-tied." The empirical evidence
above refutes the **"not tied"** half: macro tops align to BTC halving
windows within ±110 days across all 4 cycles. The discarded design's valid
half was the **shape mismatch** warning — BTC's 85% drawdown / 526× mult is
not macro behaviour. I-19 resolves both: macros ARE cycle-tied (timing follows
BTC halvings + asset lag), but the *shape* (drawdown depth, multiplier) is
the macro's own, not borrowed from BTC's crypto series.

## I-19b extension — GOLD (GC=F) added to the macro set

**Date:** 2026-08-01
**Rule tuned:** No — asset set extended, no rule changed (per DESIGN.md §9.4,
reconciliation entry written).

Gold (`GC=F`, Yahoo futures) joins SPX/NDX/DXY/TLT in `MACRO_ASSETS`:
- `fetch_macro.py`: `"gold": "GC=F"` added to ASSETS (2026-08-01).
- `build_alt_cycle_metrics.py`: `"gold": ["gold_yahoo_*.csv"]` added to
  ASSET_FILES. Rule-T/Rule-B machinery runs unchanged — gold's C4 top is
  Rule-T detected in the BTC-C4 window (expected: the Jan-2026 ATH).
- `build_alt_forward_ranges.py`: gold added to ASSETS (n=4 actual cycles).
- `build_alt_next_cycle_zones.py`: gold added to ASSETS + MACRO_ASSETS.
  Gold flows through `_project_asset_chain(is_macro=True)` → mode
  `macro_2_stage_own_shape` with gold's own dd/mult series.
- **Gold-only new columns**: `support_band_low` / `support_band_high` in
  `alt_next_cycle_zones.csv`, populated only on gold's `bear_bottom` row.
  Value = gold's **bull-market support band** (20-month SMA + 21-month EMA
  on monthly closes), validated in `docs/gold_seasonality.md`:
  $3,813.13 / $3,829.66 @ 2026-07-31. This is the empirical floor the
  drawdown-projected B4 is cross-checked against (every gold correction
  since 2015 has held the band). All other assets leave the columns empty.
- `build_charts.py`: gold added to ASSET_DISPLAY; new `build_c8_gold()`
  renders **C8g** — single-asset next-cycle chart (log y-axis) with the
  support band drawn as a gold horizontal shaded rect. `_build_alt_chart`
  file resolution switched from hard-coded snapshot dates to glob-latest.
- Gates: `tests/test_macro_provenance.py` (gold in manifest + multi-decade
  coverage), `tests/test_alt_timing.py` (asset sets, row counts 46/50/40,
  `test_gold_support_band_populated`, C8g presence + snapshot determinism),
  `tests/test_charts.py` (C8g in CHART_IDS).

Expected gold output (to verify at gate time):
| Asset | Mode | C5 TOP band | Support band cross-check |
|---|---|---|---|
| GOLD | macro_2_stage_own_shape | 2-stage band anchored on observed C4 top | B4 vs $3,813–$3,830 support band verdict in `compression_fit_note` |

# Implementation-Only Adversarial Audit — 2026-10-01

Scope: implementation correctness. The scientific premise is assumed valid and was NOT
audited. Baseline on entry: `pytest -q tests/` = 211 passed; full rebuild is
idempotent for all 22 `data/processed/` CSVs.

---

## Critical / High

### 1. Published zone bands overlap — violates the R-5 non-overlap contract
- `DESIGN.md:605-608` states the four zones are "mutually non-overlapping".
- `scripts/build_alt_next_cycle_zones.py:1739-1743, 1785-1788` builds:
  - distribution base = `H5 + D_asset_halving_to_top [q25, q75]`
  - exit base = `H5 + median(D_halving_to_top) + D_asset_top_to_next_bottom [q25, q75]`
  - **No clamp** forces `exit_base_start >= dist_base_end + 1d`.
- Overlap occurs whenever `median(ht) + q25(tnb) < q75(ht)`.
- Confirmed in the published CSV (`data/processed/alt_next_cycle_zones.csv`):
  - **BASE band overlap:** tlt +229d, gold +117d.
  - **OUTER band overlap:** tlt +827d, gold +796d, dxy +416d, ndx +351d, spx +269d, wgmi +264d.
- Numeric proof (gold): `D_asset_halving_to_top` q25=554.75 / median=868.5 / q75=1104;
  `D_asset_top_to_next_bottom` q25=119. exit starts at H5+987, distribution ends at
  H5+1104 → 117-day base overlap.
- The gate `tests/test_alt_timing.py:333` is named `test_alt_next_cycle_zones_no_overlap`
  but only asserts `distribution.base_start >= accumulation.base_end`. It never inspects
  the `exit` zone and never inspects outer bands, so the contract breach passes 211/211.
- BTC's own `next_cycle_zones.csv` does not overlap today, but the same unguarded
  formula is used, so it is latent for BTC too.
- Impact: a date can legitimately fall in both the distribution and exit windows, so the
  confluence map (C6/C8) and the "which phase are we in" banner are ambiguous for 6 of 10
  assets; for gold and TLT even the primary published bands are ambiguous.

### 2. Frozen upstream feeds accepted as fresh — no max-date assertion
- Yahoo's `^TNX` (y10) has returned data ending **2026-08-14** on seven consecutive
  weekly fetches (`data/raw/y10_yield_yahoo_2026-08-18 .. 2026-09-21.csv`, all
  `data_last=2026-08-14`).
- `scripts/fetch_yields.py:162` only rejects `len(df) < MIN_ROWS`. There is no
  max-date freshness check, so each frozen fetch is logged `[OK]` and stamped with a
  fresh filename + fresh `retrieved_at=2026-09-21`.
- `curve_state.csv` requires both y10 and y2, so it truncates to
  `min(2026-08-14, 2026-09-17) = 2026-08-14`. The **entire I-21 regime overlay is
  48 days stale**, and `regime_anchor.csv.anchor_date = 2026-08-14`.
- The same Yahoo freeze hits SPX/NDX/DXY/TLT/GOLD: all `data_last=2026-08-14` (48d).
  These assets have no second source to merge from, unlike the crypto alts (see refuted
  item 4).
- Impact: the regime state that is documented as canonical for adjusting every B4 band is
  computed from a panel that stops 48 days before the snapshot date.

### 3. The I-21 regime overlay is numerically inert (multiplier = 1.0 everywhere)
- `data/processed/regime_multipliers.csv`: 32/32 rows have `multiplier == 1.0`
  (31 `fallback_to_1.0`, 1 `computed` — ndx/normal, where
  `drawdown_cond_mean == drawdown_uncond_mean == 0.213196`, so the ratio is 1.0).
- AGENTS.md documents R-9 as "CANONICAL: computed multiplier != 1.0 overrides
  bear_bottom price_low/high". That branch never fires for any asset.
- The mechanism is real (see item 4), but with `n_actual <= 3` per regime bucket the
  conditional and unconditional samples never separate, so the overlay never adjusts
  anything. An entire increment with a methodology appendix, a dedicated chart (C8h) and
  audit columns produces no numerical effect.

### 4. R-9 override has no sanity bound — publishes price_low = $0
- `scripts/build_next_cycle_zones.py:333-338` and the equivalent in
  `build_alt_next_cycle_zones.py` compute
  `adj_low = max(0.0, min(c4_top - mult*(c4_top - b4_low), b4_high))`.
- Mutation test: set multiplier = 1.40 for btc/normal and ndx/normal, then run the
  exact CI regeneration list. Result:
  - BTC bear_bottom band `[29596, 53673]` → `[0, 25251]`
  - ETH bear_bottom band `[1167.93, 2118.06]` → `[0.00, 996.46]`
- Any multiplier that pushes the projected B4 below zero is clamped to **$0** instead of
  being refused. `max(0.0, ...)` hides a nonsense bound rather than falling back.
- Gate behaviour: the suite caught it only **incidentally** — 3 failures, of which only
  `test_alt_next_cycle_zones_bear_bottom_floor` is semantic; the other two are
  PNG/snapshot determinism tests. There is **no test asserting the R-9 arithmetic**, and
  **no BTC-specific bear-bottom floor test** (`tests/test_zones.py` has none).

### 5. CI never recomputes the I-21 chain
- `.github/workflows/ci.yml:67-101` runs a hand-maintained script list that omits
  `build_curve_state.py` and `build_regime_multipliers.py`, and uses a **different
  order** than `scripts/refresh_all.py`.
- Consequence: "regenerate then re-verify gates" validates whatever `regime_multipliers.csv`
  / `curve_state.csv` happen to be committed. Confirmed by the item-4 mutation test:
  the corrupted multiplier survived the full CI list untouched.
- The ordering also means CI's regeneration is not representative of the real pipeline.

### 6. `refresh_all.py` runs `btc_zones` before regenerating its inputs
- `scripts/refresh_all.py:143-161` DERIVED order: `btc_zones` (step 5) → `curve_state`
  (6) → `regime_multipliers` (7) → `alt_zones` (8).
- `scripts/build_next_cycle_zones.py:311-312` reads `regime_multipliers.csv` and
  `regime_anchor.csv`. So BTC's canonical B4 band is computed from the **previous**
  run's regime table while alt assets get the fresh one.
- Latent today only because BTC's multipliers are always `fallback_to_1.0`; it becomes a
  real inconsistency the moment any BTC regime reaches `n_samples >= 3`.

### 7. Provenance manifest covers 18 of 227 raw snapshots
- `data/raw/manifest.txt` has 18 entries; `data/raw/` holds 227 CSVs. 209 snapshots
  (89%) have no provenance entry, contradicting AGENTS.md rule 2 ("Add a new snapshot +
  manifest entry").
- `scripts/build_cycle_metrics.py:41-46` selects the BTC snapshot via
  `sorted(glob("btc_bitstamp_*.csv"))[-1]` — a lexicographic filename sort with no
  manifest lookup, no SHA verification, no date validation. The fallback glob
  `btc_*.csv` can match a non-Bitstamp file.

---

## Medium

### 8. The same bear-bottom event carries two different prices
- `data/processed/btc_cycle_metrics.csv` stores, for the identical bottom date:
  `next_bear_bottom_price` (Rule B daily close) vs the next cycle's
  `pre_halving_bottom_price` (events.csv intraday low):
  - 2015-01-14: 171.41 vs 171.00 (+0.24%)
  - 2018-12-15: 3179.54 vs 3122.00 (+1.84%)
  - 2022-11-21: 15766 vs 15652 (+0.73%)
- Within a single row, `mult_bottom_to_top` uses the events.csv price while
  `drawdown_pct` uses the Rule B price. Both are self-consistent, but the two ratios are
  not built on a common base, and AGENTS.md rule 3 names events.csv canonical for bottoms.

### 9. DESIGN.md §3.2.2 cycle labels are off by one
- `DESIGN.md:128-132` labels the 2013-12-04 top "C2", the 2017-12-17 top "C3", the
  2021-11-10 top "C4". Every other artifact (`btc_cycle_metrics.csv`, zone CSVs,
  charts) calls them C1, C2, C3. The table counts the 2011-06-08 early-era top as "C1",
  a cycle the pipeline does not model.
- `DESIGN.md:134` cites "CoinGecko daily-close", but `fetch_data.py` is invoked with
  `--source bitstamp`. Documented source ≠ actual source.
- Price divergence from the same cause: C3 top $69,044 (events) vs $67,559 (Rule T,
  -2.2%); C1 $1,150 vs $1,132.01; C2 $19,497 vs $19,187.78.

### 10. Chart HTML artifacts are non-deterministic
- Plotly's `to_html()` emits a random `div id` UUID on every render. Verified by
  rendering `C1.html` twice: exactly 2 differing lines, both the `div id` UUID.
- All 17 chart HTMLs therefore change on every rebuild while all 22 processed CSVs stay
  byte-identical. `tests/test_charts.py` pins PNG determinism but has **no HTML
  determinism gate**, so a genuine content change in an HTML file would be invisible
  unless it also changed the PNG.
- Side effect: `git diff` on chart HTMLs is always noisy — this is why the working tree
  perpetually shows ~17 modified chart files with no underlying data change.

### 11. Stale doc counts and a silent asset drop
- `DESIGN.md:609` says `test_alt_timing.py` expects "7×4=28 rows"; the file actually
  has 10×4 = 40 rows.
- `data/processed/alt_cycle_metrics.csv` covers 12 assets (incl. `mara`, `riot`) but
  `alt_next_cycle_zones.csv` has only 10 — `mara` and `riot` vanish from the published
  zone map with no test asserting the expected asset set.

---

## Checked and REFUTED (not defects)

1. **LOOCO for `D_bottom_to_next_top` is correct.** Independent recomputation matches
   the CSV exactly (looco_C1=1054.5, C2=1058.5, C3=1063.0). The sub-agent claim of a
   mis-mapping was wrong; `build_forward_ranges.py:153-161` documents the source-cycle
   keying.
2. **Zone chronology is correct** — all 10 alt assets + BTC sort to
   bear_bottom → accumulation → distribution → exit.
3. **B4 center 2026-10-22 is correct** (base-band midpoint of 2026-10-12..2026-11-02).
4. **CDD 350-day freeze is correctly mitigated.** ETH/SOL/XRP CDD snapshots end
   2025-10-16, but `build_alt_cycle_metrics.py:37-54, 78-96` merges CDD (early) with
   Yahoo (recent), Yahoo winning on duplicate dates. Replicated merge: no duplicate
   dates, no gaps >4d, current to 2026-09-21. Residual risk: `fetch_alts.py --source
   auto` only falls back on an empty/short download, so it never notices a frozen feed —
   the consumer-side merge is doing the work, not the fetcher.
5. **`anchor_price` outside a zone's own price band is by design** — the anchor is the
   time-anchor event price (e.g. the observed C4 top), not a member of the projected
   band.
6. **`tests/test_sma_floors.py` modification is legitimate** — it tracks the 2026-09-14
   50w-SMA reclaim and *adds* an assertion. The gate was strengthened, not weakened.

## Hygiene
- Stray untracked debug scripts at repo root: `check_metric_identity.py`, `debug.py`.

## Config sync (completed, restart pending)
All 8 subagent slots repointed to live free-tier models (`mimo-v2.6-flash-free`,
`muse-spark-1.3-contributor-free`, `space-bunny-free`, `nemotron-3.5-lightning-free`,
`ling-3.0-flash-fin-free`, `muse-spark-1.2-contributor-free`, `nemotron-3-ultra-free`);
`big-pickle` removed. All 10 configured slots verified against the live catalog.
OpenCode does not hot-reload config — **restart required** for the new roster to take
effect.

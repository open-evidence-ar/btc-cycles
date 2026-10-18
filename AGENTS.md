# Agent / Contributor Workflow

This project is built as a sequence of **atomic increments** defined in [DESIGN.md](DESIGN.md) §9.

## Rules

1. **Gate discipline:** Do not start increment *n+1* until increment *n*'s validation gate is green.
2. **Immutable snapshots:** Never edit files in `data/raw/` after write. Add a new snapshot + manifest entry instead. **Documented exception:** snapshot filenames carry the *retrieval* date only (`spx_yahoo_2026-10-15.csv`), so re-running a fetcher on the same calendar day overwrites that day's file rather than adding a new one. Prior content survives only in git history. This is intentional — a per-day filename keeps `data/raw` from growing without bound — but it means a same-day refetch is *not* an append-only operation.
3. **Single source of truth:** `data/events.csv` drives all cycle computations. `btc_cycle_metrics.csv` (from I-05) is the only source for derived cycle dates downstream. Split canonical: `events.csv` canonical for event labels/halvings/bottoms; `btc_cycle_metrics.csv` canonical for displayed top dates/prices (Rule T re-detection).
4. **No upstream patching:** If an increment fails its gate, fix the failing increment — do not modify upstream increments to force a pass.
5. **Blocker notes:** On failure, write `docs/blockers/<I-ID>-<short-name>.md` with input snapshot, expected vs actual, hypothesis, and action.

## Subagents

Custom subagents are defined globally at `D:\opencode\config\opencode\agent\`. Invoke via the `task` tool with the agent name as `subagent_type`.

| Agent | Model | Purpose |
|-------|-------|---------|
| `@sub-agent-1` | `opencode/mimo-v2.6-flash-free` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-2` | `opencode/muse-spark-1.3-contributor-free` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-3` | `opencode/space-bunny-free` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-4` | `opencode/nemotron-3.5-lightning-free` | General-purpose — research, fact-checking, bash, editing |

All agents have identical permissions (read/grep/glob/websearch/webfetch/edit/bash). The **orchestrator** decides the task type at invocation time via the prompt — not the agent config.

**Rules:**
- One agent per task — never assign multiple independent tasks to a single subagent.
- Parallelize independent work — invoke subagents concurrently via separate `task` calls.
- Subagent output stays in subagent context — parent receives only the final summary.

## Validation

```bash
pytest -q tests/          # run all increment gates
bundle exec jekyll build  # site build check
```

## Git push (READ THIS before pushing)

**All push/init/Pages commands live in [`docs/github-workflow.md`](docs/github-workflow.md) — read it first.**
Plain `git push` FAILS in this environment (no TTY, no credential helper).
The documented method authenticates with the PAT from the gitignored `.env`
via `GIT_ASKPASS` + temporary remote URL, then restores the clean URL:

```powershell
# 1. Read PAT from .env (gitignored)
$pat = (Get-Content .env | Select-String "PAT=(.+)" | % { $_.Matches.Groups[1].Value }).Trim()
# 2. Askpass shim so the PAT never hits shell history
$askpass = "C:\Users\German\AppData\Local\Temp\opencode\askpass.cmd"
Set-Content -Path $askpass -Value "@echo off`necho $pat"
# 3. Auth env + temporary remote URL, push, restore clean URL
$env:GIT_ASKPASS = $askpass; $env:GIT_TERMINAL_PROMPT = "0"
git remote set-url origin "https://open-evidence-ar:${pat}@github.com/open-evidence-ar/btc-cycles.git"
git push -u origin main
git remote set-url origin "https://github.com/open-evidence-ar/btc-cycles.git"
Remove-Item $askpass
```

Full reference (init/reset/Pages/renormalize): `docs/github-workflow.md`.

## Local Jekyll build (Windows PATH note)

Some Windows shells do not have Ruby on `PATH`; plain `bundle exec jekyll
build` then fails. The working command on this machine prefixes Ruby 3.3:

```powershell
$env:PATH = "C:\Ruby33-x64\bin;$env:PATH"; bundle exec jekyll build
```

## Quick refresh workflow

One command rebuilds everything from fresh data:

```bash
python scripts/refresh_all.py              # fetch + rebuild + chart render (~2 min)
python scripts/refresh_all.py --no-fetch   # rebuild derived + charts only (~90s)
python scripts/refresh_all.py --dry-run    # preview what would run
```

Pipeline stages (dependency order enforced):
1. **FETCH** — BTC (Bitstamp), ETH/XRP/SOL (CDD+Yahoo), macro (SPX/NDX/DXY/TLT/GOLD), US Treasury yield panel (I-21: y10/y5/y13w/y30 via Yahoo, y2 via Eco3min DGS2 mirror). Parallel.
1b. **FRESHNESS** — `feed_freshness.py`. Serial. Reads `data/raw/manifest.txt` after the parallel fetches land and **fails the run** if a snapshot carries data more than 7 days older than its own `retrieved_at`. That signature means a fetcher has a hard-coded fetch window: `fetch_macro.py` and `fetch_yields.py` both pinned `PERIOD2 = 1786752000` (2026-08-15), so 11 consecutive fetches re-stamped a fresh `retrieved_at` onto 2026-08-14 data and every prior check passed. Gate coverage spans crypto, corporate, macro, and yields. Wall-clock age ("nobody has fetched lately") is reported as a warning only — CI rebuilds from committed snapshots and never fetches, so a today-anchored assertion would go red on a schedule no CI job could fix.
2. **CYCLE** — `build_cycle_metrics.py` + `build_alt_cycle_metrics.py`. Parallel.
3. **DERIVED** — SMA floors, forward ranges, alt forward ranges, BTC zones, **curve-state + regime multipliers (I-21)**, alt zones (regime-adjusted B4). Serial (zones depend on ranges; alt zones depend on regime tables).
4. **CORR** — `build_correlations_phase.py`. Serial. (`build_regime_robustness.py` reads `correlations_phase.csv`, so this must finish before HEAVY starts — the two previously raced when both lived in the parallel HEAVY stage.)
5. **HEAVY** — backtest, regime robustness, rolling corr. Parallel.
6. **CHARTS** — `build_charts.py` (all C1-C9 + C8h + C-SMA). Serial. Chart HTML pins the Plotly `div_id` to the filename stem — without it Plotly mints a fresh UUID per render and every regeneration dirtied all 17 charts even when the data was byte-identical.

All derived-artefact writes (processed CSVs, `cycle_status.json`, Pine exports, chart HTML) go through `scripts/csv_io.py::atomic_*` (write temp + `os.replace`): readers never see partial files, a failed write never truncates the previous output, and writes survive the transient `open(..., "w")` EINVAL failures this machine's external drive exhibits. Enforced by `tests/test_csv_io.py` (unit + scan gate).

Key data flow notes:
- `fetch_alts.py --source auto` pulls CDD first, Yahoo fallback if CDD unavailable.
- `build_alt_next_cycle_zones.py` reads BTC projected B4 from `next_cycle_zones.csv` for alt B4 timing anchoring.
- `build_next_cycle_zones.py` reads `forward_ranges.csv::D_bottom_to_next_top` for the folklore cross-check band on C6 (qualitative cross-reference, not independent validation — see DESIGN.md §9.4 R-4).
- I-21 curve-regime chain: `fetch_yields.py` (raw y2/y10/y5/y13w/y30) → `build_curve_state.py` (`curve_state.csv`: 10y-2y slope, §4.1 classifier, 5-day persistence gate) → `build_regime_multipliers.py` (`regime_multipliers.csv` + `regime_anchor.csv`, per-asset mean-ratio, n<3 → 1.0 fallback) → `build_alt_next_cycle_zones.py` (additive regime-adjusted B4 columns, anchor-date regime, auto re-adjust on regime change). Regime adjustment is CANONICAL (R-9): computed multiplier != 1.0 overrides bear_bottom price_low/high in both zones CSVs (audit in b4_price_*_unconditional); fallback leaves corridors untouched. Charts render unadjusted-as-dotted-gray only when active; mechanism docs (C8h + `_includes/regime-sensitivity.html`, emitted by `build_regime_multipliers.py`) live in methodology.md appendix.

## Increment status

| ID | Title | Gate test | Status |
|----|-------|-----------|--------|
| I-00 | Repo + Pages skeleton | `tests/test_repo_skeleton.py` | **done** |
| I-01 | Event table | `tests/test_events_schema.py` | **done** |
| I-02 | BTC ingest | `tests/test_provenance.py::test_btc` | **done** |
| I-03 | Altcoin ingest | `tests/test_alts_provenance.py` | **done** |
| I-04 | Macro ingest | `tests/test_macro_provenance.py` | **done** |
| I-05 | Cycle metrics | `tests/test_cycle_metrics.py` | **done** |
| I-06 | Halving-day alignment | `tests/test_alignment.py` | **done** |
| I-07 | Phase-conditioned correlation (static) | `tests/test_correlations.py` | **done** |
| I-08 | Rolling correlation + lead/lag | `tests/test_rolling_corr.py` | **done** |
| I-09 | Forward ranges (mean/median/IQR/LOOCO) | `tests/test_forward_ranges.py` | **done** |
| I-10 | Confluence zone map (next cycle) | `tests/test_zones.py` | **done** |
| I-11 | Backtest-by-cycle (LOOCO prediction error) | `tests/test_backtest.py` | **done** |
| I-12 | Macro-regime robustness check | `tests/test_regime_robustness.py` | **done** |
| I-13 | Chart renderers C1–C7 | `tests/test_charts.py` | **done** |
| I-14 | Jekyll chapter sections filled | `tests/test_jekyll_build.py` | **done** |
| I-15 | CI orchestration | `tests/test_ci_workflow.py` | **done** |
| I-16 | Public release + integrity | `tests/test_release_checklist.py` | **done** |
| I-17 | Per-asset halving-cycle timing | `tests/test_alt_timing.py` | **done** |
| I-18a | SMA valuation floors (decision overlay) | `tests/test_sma_floors.py` | **done** |
| I-18b | Folklore bull-rhythm cross-check | `tests/test_forward_ranges.py::test_d_bottom_to_next_top_values` | **done** |
| I-19 | Macro own-shape 2-stage prediction (dates from each macro's own history since 2026-10-16; halving anchor withdrawn — see `scripts/check_cycle_tie.py`) | `tests/test_alt_timing.py::test_macro_assets_use_own_shape_projection` + `::test_macro_zone_dates_are_own_history` (+ 2 companions) | **done** |
| I-19b | Gold (GC=F) in macro set + bull-support-band cross-check | `tests/test_alt_timing.py::test_gold_support_band_populated` (+ C8g presence/snapshot; `tests/test_macro_provenance.py` gold gates) | **done** |
| I-21 | Curve-regime multiplier overlay on B4 bands (proper 10y-2y) | `tests/test_yield_provenance.py`, `tests/test_curve_state.py`, `tests/test_regime_mult.py`, `tests/test_regime_integration.py` | **done** |
| I-22 | Provisional open-cycle bottoms (`bottom_status` + `bottom_tracking` banner) | `tests/test_bottom_status.py` | **done** |
| I-22a | Zone-band non-overlap clamp (R-5 enforcement) | `tests/test_zones.py::test_zones_dont_overlap_base_bands`, `test_zones.py::test_zone_chronological_order`, `tests/test_alt_timing.py::test_alt_next_cycle_zones_no_overlap`, `::test_alt_next_cycle_zones_chronological_order` | **done** |
| I-22b | Zone keys made direction-neutral (`exit`→`b5_bottom`, `distribution`→`top`, `bear_bottom`→`bottom`) | `tests/test_zones.py` (vocab + shape gates) | **done** |

Zone non-overlap note (I-22a): R-5 promises the four zones are mutually
non-overlapping, and they were not. The exit band is built independently as
`H5 + median(ht) + tnb_q25..q75` while distribution is `H5 + ht_q25..q75`, so
they collide whenever `median(ht) + tnb_q25 < ht_q75` — true for any asset whose
top-window IQR exceeds its lower-quartile post-top-to-bottom duration (gold:
IQR 549d vs q25 119d). Shipped output had 2 base-band and 6 outer-band
overlaps. `_shift_after()` in both zone builders TRANSLATES the exit band to
open the day after distribution closes, preserving its width so the published
IQR spread is unchanged. Clamp outer first, then base against
`max(dist_base_end + 1d, outer_start)` — the reverse order breaks
base-within-outer (NDX). The old `test_alt_next_cycle_zones_no_overlap` was
named for this contract but checked 1 of 6 adjacent pairs, base bands only; it
now checks all six across both band types, plus chronological order.

Zone vocabulary note (I-22b): the `zone` column may only contain the four keys
declared in `tests/test_zones.py::CANONICAL_ZONES` — `bottom` (B4, low, entry),
`accumulation` (H5, price-free, hold), `top` (C5, high, **exit**),
`b5_bottom` (B5, low, re-entry). The old keys were inverted from a trader's
reading: the zone named `exit` was a bear *bottom*, and the zone holding the
cycle *top* was named `distribution` and never said "top". Action words live
only in prose now, never in a key. `ZONE_SEMANTICS[...][1]` carries each zone's
price direction and is what chart markers are drawn from — B4/B5 get
`triangle-down`, the C5 top gets `triangle-up`. All three were previously
backwards. Gates: `test_zones.py::test_cycle_shape_price_ordering` (top centre
> b5_bottom centre, 11/11), `::test_rising_bear_bottoms_outside_documented_exceptions`
(DXY/TLT pinned — neither has a rise-then-fall projected shape).

Rule T/B window bound note (I-22): the ±21d neighbourhood re-pick in `rule_t` /
`rule_b` is now clamped to `[window_start, window_end]`, and the price is
re-read at the clamped date. Previously the re-pick could emit an extremum
outside its own window (WGMI produced a C4 "bottom" 75 days after its top,
before Rule B's `top+90d` start). Verified a no-op for BTC C1–C3.

Provisional-bottom convention (I-22): while a cycle is open — i.e. its *next*
halving has not yet occurred — Rule B's window has no right edge, so any bottom
found is a **running minimum that can only fall**. It is emitted in dedicated
columns (`bottom_status` = `provisional_low_to_date`, `bottom_as_of`,
`b4_low_to_date`, `b4_low_to_date_price`, `D_asset_low_to_date_to_top`) and the
confirmed fields (`asset_next_bear_bottom_*`, `D_asset_top_to_next_bottom`,
`drawdown_asset_pct`) stay **empty**. Eligibility in
`build_alt_forward_ranges.py` is therefore per-statistic, not per-asset:
bottom-dependent statistics require a closed cycle; top-dependent ones
(`mult_asset_bottom_to_top`, `D_asset_*_halving_to_top`,
`D_asset_prev_bottom_to_halving`) legitimately include the open cycle because
`mult = top / pre_halving_bottom` needs only observed quantities. Surface via
`bottom_tracking` in `_data/cycle_status.json` → the `now-stamp` banner, always
labelled *provisional*. **Never resolve this by refreshing data.** See
`docs/blockers/I-17-c4-provisional-bottom.md`.

Merge determinism note (I-22): any `sort_values("date").drop_duplicates(
keep="last")` over multiple source snapshots must use `kind="stable"` — pandas'
default quicksort is unstable, so the "later source wins" tie-break on a shared
date was arbitrary between runs. Fixed in `build_alt_cycle_metrics.py` and
`build_curve_state.py`.

Rule T tuning note (I-05): window upper bound was tightened from
`halving + 1500d` (DESIGN.md §5.1 literal) to
`min(halving + 1500d, next_halving - 270d)` to prevent C3's top
search from leaking into C4's pre-halving rally (a 2024-03 high
was otherwise picked over the canonical 2021-11-10 C3 top).
Documented per §9.4 (rule tuned, reconciliation entry written).

I-03 date-gate relaxations (per §9.4; blocker notes in
`docs/blockers/I-03-*-start-date.md`):
- ETH gate relaxed from ≤ 2015-08-15 to ≤ 2016-03-15
  (Bitfinex ETHUSD earliest history available via CryptoDataDownload;
  CoinGecko/CryptoCompare public APIs locked down pre-365d history).
- XRP gate relaxed from ≤ 2013-08-15 to ≤ 2017-06-01
  (Bitfinex XRPUSD earliest; no free public source preserves XRP back
  to its 2013 launch).
- SOL gate relaxed from ≤ 2020-04-15 to ≤ 2021-12-15
  (Bitfinex SOLUSD earliest; SOL genesis 2020-04 only on CoinGecko Pro).

2-stage projection model (per §9.4 R-4/R-5):
- The C5 cycle is projected in **two stages** anchored on the observed
  C4 top: Stage 1 projects B4 from the bear-bottom price ratio series
  `[B0,B1,B2,B3]` (power-law `ratio_n = a*idx^b`); Stage 2 projects C5
  top from `projected_B4 * mult_n(idx=5)` (power-law on multipliers).
- B4 is a **first-class zone row** in `next_cycle_zones.csv` (and
  `alt_next_cycle_zones.csv`), not an internal intermediate. The map
  has 4 zones per asset: `bear_bottom → accumulation → distribution → exit`.
- BTC: B4 = $43,081 (band $29.6k-$53.7k, center 2026-10-22, cross-check
  FAIL @ +45.6%); C5 top = $272,004 (band $186.9k-$338.9k).
- Crypto alts: ETH uses `2_stage_with_observed_c4` (cross-check FAILs
  due to n_drawdowns=2). XRP uses `naive_median_own_dd` (own dd/mult
  median, n=2 cycles C3+C4). SOL uses `borrowed_2_stage_from_ETH`
  (ordinal-aligned ETH borrow: SOL C3~ETH C2, SOL C4~ETH C3, SOL
  C5~ETH C4; SOL's own C3 502x mult makes its own-series naive-median
  absurd -- see `_sections/methodology.md`). Macro (SPX/NDX/DXY/TLT/GOLD) use
  `macro_2_stage_own_shape` (I-19): 2-stage borrowed-shape machinery,
  anchor = own observed C4 top, shape (drawdown at C4, multiplier at C5)
  fit on the macro's OWN dd/mult series (n=3 from C1-C3 since C4 bottoms
  are still open for SPX/NDX/TLT). Economic floors relaxed to macro levels
  (dd_floor=0.05, mult_floor=1.05); B4 band drawdown clamped to the macro's
  observed dd range so BTC-like depths do not inflate the band.
  Gold (I-19b) additionally carries `support_band_low/high` columns
  (validated 20-mo SMA / 21-mo EMA bull-market support band,
  ~$3,813-$3,830 @ 2026-07-31) cross-checking the drawdown-projected B4.
  See `docs/blockers/I-19-macro-2stage.md`.
- Helper: `two_stage_projection_with_observed_c4()` and
  `project_bear_bottom()` in `scripts/build_charts.py`.

Naive-median multiplier envelope (outlier-trim, 2026-10-15):
`naive_median_own_dd` takes its price band as the empirical min/max of the
asset's own multiplier series. With n=3 that envelope is set entirely by the
single most extreme historical cycle, and the result can be structurally
impossible. ETH's own multipliers are `[190.508, 57.077, 4.391]` (C1-C3),
median 57.08. Min/max gave a 43x band, which propagated to a C5 top band of
**$1,281-$190,053 (148x)** whose **lower edge sat below the B4 band** -- a
cycle top priced beneath the bear bottom that precedes it.

With n>=3 the single most extreme observation (largest log-distance from the
median) is now dropped **from the envelope only**; the centre estimate still
uses every observation. ETH's band became `[57.08x, 190.51x]` -> **$16,649-$190,053
(11.4x)** and the ordering violation cleared. Note the $190k ceiling survives:
it comes from C1's 190x multiplier, which is still inside the envelope. The trim
fixes the *shape*, not the small-sample problem -- n=3 multipliers cannot carry a
credible band, and this is a display-and-structure fix, not a claim that ETH's
C5 top is 11x uncertain.

`tests/test_zones.py::test_c5_top_band_sits_above_b4_band` now asserts the one
ordering that cannot legitimately overlap (`top.price_low >= bottom.price_high`),
with `BAND_ORDER_EXCEPTIONS = {"dxy", "tlt"}` pinned for the two
long-horizon-declining instruments whose fitted idx=5 drawdown lands at or below
their current-cycle B4.

Known dual-path asymmetry (ETH, open): ETH's *published* B4 band comes from the
ratio-of-ratios path ($1,154-$2,092) while its *C5* band is derived inside
`naive_median_own_dd` from a different B4 band ($292-$998). The two zones are
therefore not mutually consistent, which is why ETH needs the trim to clear the
band-ordering gate. Unfixed -- a fix means making C5 derive from the same B4 that
gets published, which changes the stage-2 anchor for every naive-median asset.

Chart captions are generated (2026-10-16): `scripts/build_chart_captions.py`
reads the same zone CSVs the charts read and writes
`_data/chart_captions.json`; markdown includes reference them as
`caption=site.data.chart_captions.<ID>`. Captions used to be hand-written
strings carrying hard-coded numbers and went stale silently on every refresh --
C8's caption published a C5 top band of `$3,130-$9,652` while the zone CSV
carried `$16,648.91-$190,052.96`, so the page contradicted the chart directly
above it. The same transcription defect also lived in the chart *subtitles*
(hard-coded prose; ETH, XRP, SOL and MSTR had all drifted from their actual
`compression_fit_used` mode) -- those are now derived via `_mode_prose()`.
`tests/test_chart_captions.py` forbids a `$` in any literal caption attribute,
checks every referenced key exists, and verifies each generated band matches its
zone row. Note a Jekyll include cannot take `{{ ... }}` inside a quoted
parameter -- the rendered text is re-parsed as tag params and fails the build --
so static caption prose lives in the generator, not the markdown.

Zone rows publish a model centre (2026-10-16): `price_center` -- both
`next_cycle_zones.csv` and `alt_next_cycle_zones.csv` now carry the
projection's own point estimate for that zone (B4 / C5 / B5 centre). The CSVs
published only `price_low`/`price_high`, so charts, figcaptions and the site
banner each reconstructed a "centre" as `(price_low + price_high) / 2`. A band
midpoint is not a projection: it is biased for geometric bands and diverges as
a band widens. ETH's C5 top band spans $16,649-$190,053, whose midpoint
($103,351) is 2.8x the model's actual $36,795; TLT's "59.66" -- cited in
DESIGN.md as a projected centre -- was the midpoint of $9.29-$110.02 while the
model projects $73.37. Both midpoints were published (chart marker, figcaption,
banner) before the fix, and the regression was invisible: the CSV still parsed
and every number was still a number.

Consumers now prefer `price_center` -- chart markers (`build_charts.py`),
generated captions (`build_chart_captions.py`), banner
(`build_cycle_status.py::_zone_center`) -- with the midpoint kept only as a
fallback for a row that has none. Gate:
`tests/test_zones.py::test_every_zone_row_publishes_a_price_center` (no priced
row without a centre; every centre inside its own band). Pinned exception
`CENTER_OUTSIDE_BAND = {"gold"}`: gold's ratio-path centre ($5,052) sits ABOVE
its own band ($3,241-$4,787) because the I-19b SMA/EMA support-band
cross-check narrows the band but not the centre -- a real inconsistency in
gold's B4 row, left visible rather than silently normalised. For DESIGN.md
R-11: "B5 below B4" survives on real centres (dxy 81.68 vs 92.77; tlt 43.83 vs
62.30); "TLT C5 below B4" is WITHDRAWN (73.37 vs 62.30).

Macro zone timing uses each macro's own history (2026-10-16): the five macro
windows (SPX/NDX/DXY/TLT/GOLD) were dated as `H5` + BTC's own
`D_halving_to_top` / `D_top_to_bottom`, importing BTC's halving calendar into
assets the data does not couple to. Measured evidence
(`scripts/check_cycle_tie.py`): halving-to-local-top lag spread across cycles
is 1.40y (SPX), 1.52y (NDX), 1.89y (DXY), 2.35y (GOLD), 2.57y (TLT) against
~0.2y for BTC itself and 0.18-0.74y for ETH/MSTR/XRP/SOL. The old
justification ("all 4 macro tops fall 0-3y after each halving") was a
period-matching artifact -- halvings are ~4y apart and macro cycles are ~4y,
so every macro top necessarily lands in some halving window.

Macros now date themselves from their OWN observed durations anchored on their
own last observed C4 top (`_macro_own_durations()` + `_own_history_window()` in
`build_alt_next_cycle_zones.py`): B4 from own top->bear-bottom, accumulation
ending where the C5 top window can first begin (its OUTER start, not its base
start), C5 top from own bottom->top, B5 from own top->bottom. PRICE shape is
unchanged -- still I-19 `macro_2_stage_own_shape` on the macro's own dd/mult
series. Only the DATES stopped being BTC's. Consequence: TLT's B4 window moved
to 2025-04-27 -> 2027-11-04 (own median top->bottom ~138d from its 2024-12-06
top) -- already open, and a window TLT actually traded in -- versus the old
halving-keyed 2027 dates. C8d is relabelled: title, subplot titles and footer
no longer say "cycle-tied"; the footer states the premise is unsupported and
carries the measured spreads.

Halving-anchor premise audit (2026-10-16): `scripts/check_cycle_tie.py`
measures, for every asset in `alt_cycle_metrics.csv`, the spread of
halving->local-top lags across cycles, writes `_data/cycle_tie.json`, and runs
as a DERIVED pipeline stage. Three classifications: TIED = {eth, mstr, xrp,
sol} (stable lag; halving-anchored timing kept); COUPLED_LOOSE = {wgmi}
(genuinely BTC-linked but the lag wanders at 1.61y spread, because miner tops
are set by equity beta and mining economics too, so it keeps the halving anchor
behind a wide honest window); NOT_COUPLED = {spx, ndx, dxy, tlt, gold}
(own-history timing, per the note above).

MARA and RIOT are PROXY DATA SOURCES, not projected assets: zero rows in
`alt_next_cycle_zones.csv`, absent from `ASSET_DISPLAY`, present only to supply
WGMI's pre-launch history (WGMI launched 2022; its C1-C3 IS MARA's). They are
deliberately NOT classified: since WGMI's pre-launch history *is* MARA's, the
two measure nearly the same lag spread (1.61y vs 1.52y) by construction, and
classifying both would double-count one observation as two. Gates
(`tests/test_cycle_tie.py`): the crypto alts must STAY tied (if that breaks,
the framework's core premise is in question and the build says so); the
NOT_COUPLED set is pinned so a newly-drifting macro fails the gate; proxies
must never acquire zone rows or a classification; every measured asset must be
classified exactly once.

Update this table as increments complete.

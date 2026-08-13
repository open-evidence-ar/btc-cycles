# Agent / Contributor Workflow

This project is built as a sequence of **atomic increments** defined in [DESIGN.md](DESIGN.md) §9.

## Rules

1. **Gate discipline:** Do not start increment *n+1* until increment *n*'s validation gate is green.
2. **Immutable snapshots:** Never edit files in `data/raw/` after write. Add a new snapshot + manifest entry instead.
3. **Single source of truth:** `data/events.csv` drives all cycle computations. `btc_cycle_metrics.csv` (from I-05) is the only source for derived cycle dates downstream. Split canonical: `events.csv` canonical for event labels/halvings/bottoms; `btc_cycle_metrics.csv` canonical for displayed top dates/prices (Rule T re-detection).
4. **No upstream patching:** If an increment fails its gate, fix the failing increment — do not modify upstream increments to force a pass.
5. **Blocker notes:** On failure, write `docs/blockers/<I-ID>-<short-name>.md` with input snapshot, expected vs actual, hypothesis, and action.

## Subagents

Custom subagents are defined globally at `D:\opencode\config\opencode\agent\`. Invoke via the `task` tool with the agent name as `subagent_type`.

| Agent | Model | Purpose |
|-------|-------|---------|
| `@sub-agent-1` | `opencode/deepseek-v4-flash-free` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-2` | `opencode/mimo-v2.5-free` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-3` | `opencode/big-pickle` | General-purpose — research, fact-checking, bash, editing |
| `@sub-agent-4` | `opencode/north-mini-code-free` | General-purpose — research, fact-checking, bash, editing |

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

Local GitHub / push / init workflow commands are documented at
`docs/github-workflow.md`.

## Quick refresh workflow

One command rebuilds everything from fresh data:

```bash
python scripts/refresh_all.py              # fetch + rebuild + chart render (~2 min)
python scripts/refresh_all.py --no-fetch   # rebuild derived + charts only (~90s)
python scripts/refresh_all.py --dry-run    # preview what would run
```

Pipeline stages (dependency order enforced):
1. **FETCH** — BTC (Bitstamp), ETH/XRP/SOL (CDD+Yahoo), macro (SPX/NDX/DXY/TLT/GOLD). Parallel.
2. **CYCLE** — `build_cycle_metrics.py` + `build_alt_cycle_metrics.py`. Parallel.
3. **DERIVED** — SMA floors, forward ranges, alt forward ranges, BTC zones, alt zones. Serial (zones depend on ranges).
4. **HEAVY** — backtest, regime robustness, correlations, rolling corr. Parallel.
5. **CHARTS** — `build_charts.py` (all C1-C9 + C-SMA). Serial.

Key data flow notes:
- `fetch_alts.py --source auto` pulls CDD first, Yahoo fallback if CDD unavailable.
- `build_alt_next_cycle_zones.py` reads BTC projected B4 from `next_cycle_zones.csv` for alt B4 timing anchoring.
- `build_next_cycle_zones.py` reads `forward_ranges.csv::D_bottom_to_next_top` for the folklore cross-check band on C6 (qualitative cross-reference, not independent validation — see DESIGN.md §9.4 R-4).

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
| I-19 | Macro cycle-tied prediction | `tests/test_alt_timing.py::test_macro_assets_use_cycle_tied_projection` (+ 2 companions) | **done** |
| I-19b | Gold (GC=F) in macro set + bull-support-band cross-check | `tests/test_alt_timing.py::test_gold_support_band_populated` (+ C8g presence/snapshot; `tests/test_macro_provenance.py` gold gates) | **done** |

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

Update this table as increments complete.

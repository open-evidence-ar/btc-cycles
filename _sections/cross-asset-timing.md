---
layout: default
title: Per-Asset Decision Windows
permalink: /cross-asset-timing/
weight: 30
---
> **Role:** [model-input -- extension of the BTC decision windows].
> Attention windows from [Prediction (BTC)](#predictive-ranges), translated
> onto non-BTC assets. Read alongside BTC: ETH bottom watch starts ~3 months earlier.

## The 10 per-asset decision windows

**Calendar spine:** B4 (bottom) -> Accumulation (2026-2028) -> Distribution
C5 top (2029) -> B5 re-entry.

Watch order (B4 calendar): **XRP** (Mar 2026) -> **ETH** (Jun 2026) -> **BTC** (Oct 2026)
-> **SOL** (Oct 2026 - Jan 2027) -> **MSTR** (Oct 2026 - Jan 2027) ->
**GOLD** (BTC-anchored, ~Oct 2026) -> **WGMI** (Apr - Nov 2027). ETH has its own native 2-stage fit; XRP, SOL, MSTR and WGMI borrow BTC's projected B4 timing,
shifted by each asset's own historical lag-vs-BTC-bottom (SOL's *price* shape borrows from ETH — see footnote 4). Macro assets are cycle-tied since
Macro assets (including GOLD) are dated from their own cycle history since 2026-10-16, not the halving calendar; GOLD retains the support-band cross-check.

Table: 10-asset per-asset decision windows — B4 and C5 windows. Crypto rows are halving-anchored; macro rows (GOLD, SPX, NDX, DXY, TLT) are dated from each macro's own cycle history. Band and center prices in USD. Cross-check and per-asset method metadata moved to the footnote list below the table (keyed by superscript).

{% include zone-summary-table.html %}

## I-21 — automatic regime adjustment of the B4 corridors

The US yield-curve regime (10y−2y classifier, 5-day persistence gate) can
**automatically adjust** each asset's B4 bear-bottom corridor:

> **Active rule:** when a *computed* multiplier exists for the asset in
> the anchor regime (n ≥ 3 observed drawdowns), the published corridor —
> here, on the charts, and in the Pine export — **already is** the
> regime-adjusted band. Charts mark it (`regime ×mult applied`, dotted
> gray = unadjusted reference). No action needed; no dual numbers.
>
> **Today: INACTIVE.** Every multiplier cell is `fallback` (n < 3) — all
> corridors below are unconditional. Nothing to do.

Mechanism details, the full sensitivity table, and the signal dashboard
(C8h) live in [Appendix A — Methodology](#methodology) §"I-21 curve-regime
mechanism". Evidence base: H9/H10 in
`docs/blockers/I-21-eurodollar-proxies-exploration-2.md` (H8 rejected —
this is decision-context, not a top-timer).

### ETH — 2-stage model with B4 projection

**ETH** — opens its B4 window around Jun 2026 (band on the chart below).

{% include chart.html id="C8" height="700px" caption=site.data.chart_captions.C8 %}

### XRP — borrowed 2-stage from BTC

**XRP** — opens its B4 window around Mar 2026 (band on the chart below).

{% include chart.html id="C8b" height="700px" caption=site.data.chart_captions.C8b %}

### SOL — borrowed 2-stage from ETH (ordinal-aligned)

**SOL** — opens its B4 window around Sep 2026 (band on the chart below).

{% include chart.html id="C8c" height="700px" caption=site.data.chart_captions.C8c %}

### MSTR — borrowed 2-stage from BTC

**MSTR** — opens its B4 window around Sep 2026 (band on the chart below).

{% include chart.html id="C8e" height="700px" caption=site.data.chart_captions.C8e %}

### WGMI — borrowed 2-stage from BTC + MARA proxy

**WGMI** — opens its B4 window around Apr 2027 (band on the chart below).

{% include chart.html id="C8f" height="700px" caption=site.data.chart_captions.C8f %}

### GOLD (GC=F) — I-19 macro 2-stage + bull support band (I-19b)

**GOLD** - BTC-anchored (~Oct 2026, drawdown-projected, cross-checked vs support band).

{% include chart.html id="C8g" height="700px" caption=site.data.chart_captions.C8g %}

---

# Method details

Per-asset projection modes, coverage matrix, per-cycle local-top dates,
and the SOL data-coverage note have moved to
[Appendix A — Methodology](#methodology) §"Per-asset projection modes".
Macro context charts (C8d macro 2-stage, C9 BTC calendar with alt
local-top overlays) live in
[Appendix C — Cross-Asset Correlations](#cross-asset).

---
*Artifacts: `data/processed/alt_cycle_metrics.csv` · `alt_forward_ranges.csv` · `alt_next_cycle_zones.csv` · charts C8/C8g/C9*
*Gate: `pytest tests/test_alt_timing.py`*

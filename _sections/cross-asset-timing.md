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
C5 (H2 2029) -> Exit B5.

Watch order (B4 calendar): **XRP** (Mar 2026) -> **ETH** (Jun 2026) -> **BTC** (Oct 2026)
-> **SOL** (Oct 2026 - Jan 2027) -> **MSTR** (Oct 2026 - Jan 2027) ->
**GOLD** (BTC-anchored, ~Oct 2026) -> **WGMI** (Apr - Nov 2027). ETH has its own native 2-stage fit; XRP, SOL, MSTR and WGMI borrow BTC's projected B4 timing,
shifted by each asset's own historical lag-vs-BTC-bottom. Macro assets are cycle-tied since
I-19; GOLD joins the macro set with an extra validated support-band cross-check.

Table: 10-asset per-asset decision windows — B4 and C5 windows for each asset on a shared BTC-halving-calendar frame. Band and center prices in USD. Cross-check and per-asset method metadata moved to the footnote list below the table (keyed by superscript).

{: .table-dense}
| Order | Asset | B4 window (base) | B4 price corridor | C5 (distribution) window | C5 price corridor | What to do |
|---|---|---|---|---|---|---|
| 1 | **XRP** | 2026-03-20 → 2026-07-18 | $0.54 – $0.83 | 2029-04-04 → 2029-06-03 | $3.28 – $8.20 | Earliest crypto bottom watch. <sup>1</sup> |
| 2 | **ETH** | 2026-06-27 → 2026-09-13 | $298 – $1,000 | 2029-08-31 → 2029-10-02 | $3,130 – $9,652 | ~3 months before BTC. <sup>2</sup> |
| 3 | **BTC** | (see [The Prediction (BTC)](#predictive-ranges)) | $29.6k – $53.7k | 2029-07-31 → 2029-09-20 | $186.9k – $338.9k | → anchor for XRP/SOL — XRP and SOL borrow BTC's projected B4. <sup>3</sup> |
| 4 | **SOL** | 2026-09-30 → 2027-01-28 | $39.65 – $61.11 | 2029-03-07 → 2029-07-21 | $241.80 – $604.31 | Lags BTC by ~3 months — only crypto asset with a later B4 than BTC. <sup>4</sup> |
| 5 | **MSTR** | 2026-09-30 → 2027-01-28 | $103.42 – $121.44 | 2028-11-16 → 2028-12-16 | $437.51 – $1,093.45 | BTC-leveraged equity — window coincident with SOL. <sup>5</sup> |
| 6 | **WGMI** | 2027-04-10 → 2027-11-07 | $15.74 – $18.48 | 2029-07-05 → 2030-05-04 | $66.57 – $166.38 | BTC miners ETF — MARA proxy for pre-launch cycles C1-C3. <sup>7</sup> |
| 7 | **GOLD** | BTC-anchored (~Oct 2026, ±own lag) | drawdown-projected B4, cross-checked vs support band | H5 + own halving-to-top Q25/Q75 | I-19 2-stage C5 band | Cycle-tied macro. Bull support band (20-mo SMA/21-mo EMA) is the empirical floor. <sup>8</sup> |
| – | **SPX/NDX/DXY/TLT** | BTC-anchored (I-19) | drawdown-projected B4 (own dd/mult series) | H5 + own halving-to-top Q25/Q75 | I-19 2-stage C5 band | Cycle-tied since I-19: watch as macro context for the crypto entries. <sup>6</sup> |

<ol class="table-dense-footnotes">
  <li><sup>1</sup> **XRP.** Cross-check: BTC-borrowed timing. Method: <code>borrowed_2_stage_from_BTC</code>.</li>
  <li><sup>2</sup> **ETH.** Cross-check: ETH-native Stage 1 vs dd-path <strong>FAIL @ +15.3%</strong>. Method: <code>2_stage_with_observed_c4</code>.</li>
  <li><sup>3</sup> **BTC.** Method: BTC 2-stage (Stage 1 + Stage 2). Full disclosure on the [The Prediction (BTC)](#predictive-ranges) page.</li>
  <li><sup>4</sup> **SOL.** Cross-check: BTC-borrowed timing. Method: <code>borrowed_2_stage_from_BTC</code>.</li>
  <li><sup>5</sup> **MSTR.** Cross-check: BTC-borrowed timing. Method: <code>borrowed_2_stage_from_BTC</code>.</li>
  <li><sup>6</sup> **SPX/NDX/DXY/TLT.** Method: <code>macro_2_stage_own_shape</code> (I-19). Cycle-tied 2-stage: anchor = own observed C4 top; shape (drawdown depth, bottom-to-top multiplier) fit on the macro's OWN series (n=3 from C1-C3). B4 band drawdown clamped to the macro's observed dd range (see docs/blockers/I-19-macro-2stage.md).</li>
  <li><sup>7</sup> **WGMI.** Cross-check: BTC-borrowed timing. Method: <code>borrowed_2_stage_from_BTC</code>. MARA proxy for pre-launch cycles C1-C3.</li>
  <li><sup>8</sup> **GOLD (GC=F).** Method: <code>macro_2_stage_own_shape</code> (I-19b). Anchor = own observed C4 top (Jan-2026 ATH, Rule-T detected). Gold-specific cross-check: 20-mo SMA / 21-mo EMA bull-market support band ($3,813–$3,830 @ 2026-07-31, validated in docs/gold_seasonality.md) — the projected B4 must respect this floor. See chart C8g.</li>
</ol>

### ETH — 2-stage model with B4 projection

**ETH** - Open ~Jun 2026 ($298-$1,000).

{% include chart.html id="C8" height="700px" caption="C8 — ETH next-cycle projection (2-stage with observed C4 top $4,831). B4 bear-bottom zone (cyan, $298–$1,000, window Jun–Sep 2026). C5 top zone (orange, $3,130–$9,652, window Aug–Oct 2029). B5 exit zone (blue, $1,153–$3,557, window Jun–Aug 2030). Cross-check vs drawdown path: FAIL @ +15.3%." %}

### XRP — borrowed 2-stage from BTC

**XRP** - Open ~Mar 2026 ($0.54-$0.83).

{% include chart.html id="C8b" height="700px" caption="C8b — XRP next-cycle projection (borrowed 2-stage from BTC). B4 bear-bottom zone (cyan, $0.54–$0.83, window Mar–Jul 2026 — BTC-anchored timing). C5 top zone (orange, $3.28–$8.20, window Apr–Jun 2029). B5 exit zone (blue, $0.78–$1.94, window May–Jun 2030)." %}

### SOL — borrowed 2-stage from BTC

**SOL** - Open ~Sep 2026 ($39.65-$61.11).

{% include chart.html id="C8c" height="700px" caption="C8c — SOL next-cycle projection (borrowed 2-stage from BTC; SOL C3 is now actual data — proxy retired). B4 bear-bottom zone (cyan, $39.65–$61.11, window Sep 2026–Jan 2027). C5 top zone (orange, $241.80–$604.31, window Mar–Jul 2029). B5 exit zone (blue, $57.37–$143.39, window Jul–Sep 2030)." %}

### MSTR — borrowed 2-stage from BTC

**MSTR** - Open ~Sep 2026 ($103.42-$121.44).

{% include chart.html id="C8e" height="700px" caption="C8e — MSTR next-cycle projection (borrowed 2-stage from BTC). B4 bear-bottom zone (cyan, $103–$121, window Sep 2026–Jan 2027). C5 top zone (orange, $438–$1,093, window Nov–Dec 2028). B5 exit zone (blue, $153–$383, window Jun–Jul 2030). MSTR leads BTC B4 by ~267d (historical: alts bottom 1–5 months before BTC)." %}

### WGMI — borrowed 2-stage from BTC + MARA proxy

**WGMI** - Open ~Apr 2027 ($15.74-$18.48).

{% include chart.html id="C8f" height="700px" caption="C8f — WGMI next-cycle projection (borrowed 2-stage from BTC; MARA proxy for C1-C3). B4 bear-bottom zone (cyan, $15.74–$18.48, window Apr–Nov 2027). C5 top zone (orange, $66.57–$166.38, window Jul 2029–May 2030). B5 exit zone (blue, $15.80–$39.48, window Jan 2031–Mar 2032). WGMI's B4 is projected later than BTC's because its observed C4 top is very recent (June 2026) — the asset has not yet traced out a full C4-to-B4 path." %}

### GOLD (GC=F) — I-19 macro 2-stage + bull support band (I-19b)

**GOLD** - BTC-anchored (~Oct 2026, drawdown-projected, cross-checked vs support band).

{% include chart.html id="C8g" height="700px" caption="C8g — GOLD next-cycle projection (I-19 macro 2-stage, own shape). B4 bear-bottom zone (cyan), C5 top zone (orange), B5 exit zone (blue). Gold horizontal band = validated 20-mo SMA / 21-mo EMA bull support ($3,813–$3,830 @ 2026-07-31): the projected B4 is cross-checked against this floor. See docs/gold_seasonality.md for the full validation." %}

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

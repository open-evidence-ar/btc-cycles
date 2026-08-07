---
layout: default
title: Confidence & Limits
permalink: /validation/
weight: 30
---
## Confidence grades (per published window)

> **Cross-check status** per zone is published inline on the source pages —
> see [The Prediction (BTC)](#predictive-ranges) (B4 / C5 cross-check) and
> [Per-Asset Windows](#cross-asset-timing) (per-asset cross-check). It is
> not duplicated here to avoid drift.

| Window | Confidence | Date error | Price error | Caveat |
|---|---|---|---|---|
| **B4** (Bear bottom) | **Med** | ~100d (C3 LOOCO worst-case) | Stage-1 $43k vs Stage-2 $29.6k — band = union of both | C4 top printed apathetic (mult 7.97×); Stage-2 path below euphoric expectation. Use the **union** band ($29.6k – $53.7k), not the center. The `top_character` [model input modifier](#cycle-anatomy) widened the cross-check tolerance from a single-path estimate to the union of both paths. |
| **Accumulation** | **High** | 488d mean (n=4, D_prev_bottom_to_halving) | n/a — not a price event | Tightest statistic in the framework (range 380–542). |
| **C5 distribution (top)** | **High** | ~50d base band (H5-anchored IQR) ± ~8d folklore band (B4-anchored) | $186.9k – $338.9k (center $272k) | Strongest confluence in the framework. Multiplier power-law anchored on Euphoric Tops C1–C3; C4 was apathetic so multiplier band may be compressed-down biased. |
| **B5 (Exit)** | **Low** | ~24d base band (Stage-1 ratio idx=5) | ± log_residual_std from B4 chain stages | 2nd-derivative — depends on B4 + C5 events being correctly observed first. Treat as preparation for the post-C5 watch, not as load-bearing for any position today. |

## LOOCO Backtest

All three leave-one-cycle-out predictions fall inside the published
min-max envelope; worst case ~100 days on C3. The holding map across a window of this precision is well within the published multi-year base band.

For the full LOOCO and macro-regime tables, see [Appendix A -- Methodology](#methodology).

## Macro-Regime Robustness

BTC vs macro correlation is regime-sensitive (sign-flip counts 2-4 of 4 phases under DXY/TLT ±1σ regimes). Don't abandon the BTC bands — the cycle anchor survives. Upgrade the 200w and folklore overlay (see [Appendix B](#cycle-anatomy)) during a sign-flip regime.

---
*Backtest: `data/processed/backtest_by_cycle.csv` · Regime: `data/processed/correlations_BY_regime.csv` · Lead/lag: `data/processed/cross_lag.csv` (produced by I-8; lead/lag info published qualitatively in cross-asset-timing.md)*

---
layout: default
title: C. Cross-Asset Correlations
permalink: /cross-asset/
weight: 50
---
> **Role of this page:** [context, not forecast]. The correlations here
> describe the environment the BTC bands in
> [`predictive-ranges.md`](#predictive-ranges) live in. They do **not**
> move the B4 / C5 numbers. They tell the reader two actionable things:
> (a) when a known sign-flip macro regime is active, *discount confidence
> in the BTC-vs-macro context for this cycle*; (b) which crypto alt tends
> to lead or lag BTC by how much, so the BTC band can be mentally shifted
> onto the alt calendar. The alt-side consequence (per-asset timing
> bands) is published in [`cross-asset-timing.md`](#cross-asset-timing).

## Phase-Conditioned Correlations (Pearson)

{% include chart.html id="C4" caption="C4 — Pearson correlation of BTC weekly log-returns vs each panel asset, conditioned on cycle phase." %}

**Reading this chart for actionable context.** Two clean signals recur
across cycles (Pearson r, per `data/processed/correlations_phase.csv`):

- **Altcoins (ETH, SOL, XRP) show positive correlation with BTC across
  all phases** (range 0.33–0.85); the altcoin-to-BTC link strengthens
  through the late bull / bear (P1 ETH=0.85, P4 ETH=0.84, P4 XRP=0.66,
  P4 SOL=0.70) and is weakest in P2/P3 for XRP (min 0.33). **Actionable
  read:** a B4 attention window on BTC tends to mark similar pressure on
  these alts within ±10 days (see `cross-asset-timing.md` for the
  actual per-asset lag table).
- **Macro assets (SPX, NDX, DXY, TLT) show weak-to-moderate correlation
  with BTC** — |r| ≤ 0.26 across phases, with most cells < 0.2. The
  lone exceptions are SPX P4 = 0.24 and NDX P4 = 0.25 (the bear phase,
  where all four alts likewise print their strongest BTC coupling).
  **Actionable read:** the BTC B4 / C5 bands are *not* materially
  downgraded when SPX/NDX print a soft patch — the historical link is
  weak enough that BTC's own cycle data dominates; treat the macro
  backdrops as sign-flip regime modifiers (next chart).

## Rolling 90-day Correlation: BTC vs DXY/TLT

{% include chart.html id="C5" caption="C5 — Rolling 90-day Pearson correlation of BTC vs DXY (red) and TLT (blue) across cycle C4." %}

**Reading this chart for actionable context.** The rolling correlation
swings between regimes — there is no stable "BTC always trades like X"
relationship with the dollar or long bonds. Two practical consequences:

- A **DXY-high / TLT-low regime** has historically been associated with
  elevated sign-flip counts in the BTC-macro correlations (see
  [`validation.md`](#validation) for the table). The actionable read is
  *not* "abandon the B4 band" — the BTC bands are anchored on the BTC
  cycle, and the cycle survives macro regimes — but it *is* "treat
  cycle/C5 multipliers as more uncertain in this regime", which is what
  the published union band already reflects.
- A regime switch **during** the B4 window is itself a signal: a DXY
  impulse INTO the B4 attention window historically coincides with a
  deeper drawdown-on-the-band. The C4-cross-check FAIL on the published
  B4 numbers (`cross_check_ok=False`) is consistent with this regime
  being active in the current cycle.

## Macro 2-stage projections (moved from Per-Asset Decision Windows)

Macro assets (SPX, NDX, DXY, TLT, GOLD) use the I-19 cycle-tied
2-stage projection — anchor = own observed C4 top; shape (drawdown and
bottom-to-top multiplier) fit on the macro's OWN series (n=3 from
C1-C3). B4 band drawdown clamped to the macro's observed dd range.
See `docs/blockers/I-19-macro-2stage.md` for full methodology.

{% include chart.html id="C8d" height="2000px" caption="C8d — Macro assets with cycle-tied 2-stage projection (I-19). Anchor = own observed C4 top; shape (drawdown depth at C4, bottom-to-top multiplier at C5) fit on the macro's OWN series (n=3 from C1-C3). B4 band drawdown clamped to the macro's observed dd range. I-21 regime status line at bottom (adjustments apply automatically when computed). See docs/blockers/I-19-macro-2stage.md." %}

## BTC calendar with alt local-top overlays

A short reference chart showing BTC log-price with each asset's own
halving-calendar local-top overlaid. Useful for eyeballing which alts
tend to top with / lead BTC — i.e. the cross-section's *top-side*
timing pattern (mirror of the *B4* timing pattern on the Decision
spine).

{% include chart.html id="C9" height="600px" caption="C9 — BTC log price with per-asset local-top markers. Each marker shows the asset's local top with its day-count from the most recent BTC halving. ETH C3 = 546d, BTC C3 = 546d — alts top ≈ with BTC." %}

---
*Correlations: `data/processed/correlations_phase.csv` · Rolling: `data/processed/correlations_rolling.csv`*

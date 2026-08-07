---
layout: default
title: E. Theoretical Framework
permalink: /theory/
weight: 65
---
> **Role of this page:** [context, not forecast]. The probes here describe
> *why* the structural coherence of the BTC halving cycle holds while the
> price-magnitude amplitude compresses. They do **not** move the B4 / C5
> numbers in [`predictive-ranges.md`](#predictive-ranges) and do not feed
> any forward-range statistic. The bands themselves are unchanged; this
> page is the honest interpretation layer alongside them.

## Why this section exists

Outside the empirical zone map, a natural cross-check asks whether the
BTC cycle's structural coherence is preserved as the system's approximate
market cap grows -- from ~25 M USD at the C1 bottom to ~306 B at the C4
bottom (a ~100x increase). The econophysics literature on flocking
(Vicsek-style ordered-phase polarization) and synchronization (Kuramoto
phase oscillator) predicts that an *ordered-phase* system retains its
coherence (dominant correlation eigenvalue, calendar phase, autocorrelation
structure) across system-size changes -- a prediction that maps directly
onto the BTC question. Three verification probes (V1/V2/V3) test that
prediction; one mixed-framework probe (V4) characterizes the amplitude-
compression leg; four predictive probes (P-D/P-H/P-O/P-FA) test whether the
framework adds any *new* forecast capability beyond the published bands.

## V1 -- Coherence does NOT decay (the earlier "decay" was a landmark artifact)

Dominant eigenvalue (lambda_1) of the per-cycle correlation matrix on a
**fixed 6-asset panel** (btc, mstr, spx, ndx, dxy, tlt; weekly log returns;
pure numpy -- removes the panel-growth confound that misleadingly shrank
lambda_1 across cycles under the landmark diffusion-map kernel):

| cycle | n rows | lambda_1 (fixed panel) | lambda_1 (mass-weighted) |
|-------|--------|------------------------|---------------------------|
| C1    | 2727   | 2.4142                 | 2.3288                    |
| C2    | 3039   | 2.3842                 | 2.7443                    |
| C3    | 2979   | 2.9204                 | 2.7443                    |
| C4    | 1503   | 2.7035                 | 2.8423                    |

lambda_1 is stable (2.38..2.92) and actually *rises* C1->C3. The previous
"decaying coherence" reading (0.99 -> 0.07 under P-D) was a measurement
artifact of the landmark diffusion-map kernel whose per-cycle subsets
differed -- not a system signal.

**Robustness** (validated 2026-08-02, read-only checks):
- Repeated on 3 alternate panels -- lambda_1 NEVER decays:
  drop_mstr (5 assets): 2.10 / 2.06 / 2.50 / 2.23 (range 2.06..2.50)
  risk_4 (btc/spx/ndx/tlt): 2.07 / 2.00 / 2.13 / 2.21 (flat, 2.00..2.21)
  crypto_4 (btc/eth/xrp/sol): n/a / 2.94 / 2.68 / 3.12 (rising, 2.68..3.12)
- Repeated on non-overlapping 7d returns (every 7th row): 2.41 / 2.45 /
  2.94 / 2.88 -- unchanged, ruling out rolling-window autocorrelation as
  the cause of lambda_1 stability.
- Bootstrap 95pct CI (200 resamples, orig_6 panel):
  C1 [2.359..2.483]  C2 [2.298..2.495]  C3 [2.838..3.012]  C4 [2.614..2.820]
  C1-C2 largely overlap; C3 sits clearly above C2 (disjoint CIs).

## V2 -- Calendar seasonality conserved

| interval | C1 | C2 | C3 | C4 | spread |
|----------|----|----|----|----|--------|
| Halving -> final top | 371d | 525d | 546d | 534d | +-4% of mean (535d), C2-C4 |
| Top -> next bear bottom | -- | 406d | 363d | 376d | +-11% of mean (382d) |

The clock did not compress across C2-C4 -- consistent with the
phase-locked-oscillator reading (theta = (t - t_halving)/1460; C4 top at
+534d matches the C2-C3 rhythm). C1 is the immature outlier.

## V3 -- Autocorrelation memory slows, mean |AC| stable

BTC weekly-return autocorrelation:

| cycle | dominant |AC| lag (weeks) | mean |AC| |
|-------|------------------------------|-----------|
| C1    | 89                           | 0.063     |
| C2    | 113                          | 0.060     |
| C3    | 116                          | 0.065     |

The dominant lag drifts *outward* (slowing, NOT dying); the mean |AC|
is flat. C4 reads 42w only because its window is truncated mid-cycle
(bottom not yet confirmed; 1503 rows vs ~3000 for completed cycles).

## V4 -- Mixed-framework regression (descriptive, mechanism open)

ln(cycle-multiplier) regressed on ln(market-cap at cycle bottom), 4 cycles:

| series | slope (beta) | R^2 | LOOCO slope range | LOOCO spread |
|--------|--------------|------|--------------------|--------------|
| BTC bottom -> final top | -0.395 | 0.974 | [-0.542, -0.308]  | 0.234 |
| BTC halving -> final top | -0.412 | 0.958 | [-0.555, -0.343] | 0.212 |

Both slopes are **negative and sample-stable**: leave-one-cycle-out
replication produces tight ranges whose signs never flip. The
amplitude-compression pattern is real and reproducible across
leave-one-out samples.

SPX macro cross-check (descriptive, n=4): SPX bottom-to-peak multipliers
also declined as the SPX level grew (post-2008 regimes) -- directionally
consistent with cap-driven amplitude compression, but n is small and no
theory-based claim is made for the macro cross-check.

## Predictive gates -- all four FAILED (a published negative result)

Four probes attempted to convert the framework into a *predictive* model
beyond the published bands. All four failed their out-of-sample gates:

| Probe | Method | Result | Failure mode |
|-------|--------|--------|--------------|
| P-D | landmark diffusion map | ARI = -0.001 | no unsupervised regime labels recovered; lambda_1 0.99 -> 0.07 was landmark subset artifact, not signal |
| P-H | Hawkes self-exciting + DXY/TLT covariates | OOS peak 337d EARLY (2024-11-03 vs actual 2025-10-06) | cascade WEAKENS (intensity at C4 top 36% below C3 top); contradicts Xia 2016 B-proportional-to-N prediction |
| P-O | noisy phase oscillator | C4 top at +534d, 373d outside any loose window | oscillator coupling inverted (HIGH < NORMAL < LOW), declared invalid |
| P-FA | Fourier-amp cycle-amp regression | r = -0.931 (first_high) -> -0.086 (final_top) | fragile to legitimate analyst choice (both labels canonical in events.csv); LOOCO all in [-0.97, -0.90] but slope collapses on label swap |

These are **published negative results, not methodology failures**: they
bound what the framework can honestly claim. The structural coherence is
real (V1-V3 PASS); the ability to predict a specific cycle top or
amplitude is NOT (P-D/P-H/P-O/P-FA FAIL). The published zone map remains
the sole forecast -- the framework layer sits *beside* it as
interpretation.

## The framework: "date = flock, compression = open mechanism"

V1-V4 split cleanly into a two-leg framework:

- **Leg 1 -- calendar seasonality (date = flock): fully supported by
  literature.** Stable polarization (lambda_1 N-independent across cycles),
  conserved halving->top interval (+-4%), and autocorrelation memory that
  slows without dying (dominant |AC| lag drifts outward, mean |AC| flat)
  are structurally analogous to an ordered-phase Vicsek-style flock with
  N-independent polarization (Ginelli 2016 EPJST 225:2099 -- explicit
  phi ~ N^0 in ordered phase, phi ~ 1/sqrt(N) in disordered; Cavagna 2010
  PNAS 107:11865 -- empirical Phi ~= 0.96 across 122-4,268 starlings,
  size-independent) and to a synchronized Kuramoto order parameter that
  is conserved across system size (Hong et al. 2015 PRE 92:022122 --
  r = |(1/N) sum exp(i theta_i)| is N-independent in the synchronized
  state). This leg holds.

- **Leg 2 -- amplitude compression (compression = market cap):
  descriptive pattern, mechanism open.** BTC cycle multipliers decay
  526 / 112 / 22 / 8x per the canonical series
  (btc_cycle_metrics.csv::mult_bottom_to_top -- bitinfocharts 2011-11-14
  bottom = $2.15); the V4-bitstamp-bitstamp read against
  returns_aligned.csv gives 458 / 111 / 20 / 8x -- the C1 difference (~13%)
  comes from Bitstamp's $2.47 OHLC close on 2011-11-14 vs canonical
  $2.15, and does not propagate to V4's β because ln-cap regression is
  dominated by the 100x cross-cycle range. Both views support the same
  qualitative story.
  as the system's approximate market cap grows ~100x. The V4 slope
  (beta ~= -0.40) is closer in magnitude to the BFL square-root impact
  analog (beta ~= -0.50, Bouchaud et al. 2009 *Handbook of Financial
  Markets*) than to the Gabaix cross-section firm-volatility analog
  (beta ~= -0.15 to -0.20, Plerou 1999 PRE / Gabaix 2003 Nature / Gabaix
  2009 Annu Rev Econ / Pessa, Perc, Ribeiro 2023 Sci Rep 13:3351 -- which
  is cross-section, NOT time-series BTC-specific; Pessa reports mixed
  direction, 37% of top-200 only). The closest BTC-specific corroboration
  is Drozd, Gebarowski, Minati, Oswiecimka, Watorek 2018 Chaos 28:071101
  (BTC fluctuation statistics mature: gamma 2.2 -> 3.3, Hurst -> 0.5 --
  thinner tails, same-season compression consistent, but no cap-model).
  **No single literature source derives the BTC multi-year multiplier-
  decay from cap growth** -- the framework's second leg is therefore an
  empirical finding with consistent-but-unsourced analogies, not a
  validated predictive mechanism.

## Honest limits (why this is descriptive, not predictive)

- **n = 4 completed cycles** (C1 immature, C4 incomplete): interval
  statistics are descriptive, not inferential.
- **C4 still open**: bottom not yet confirmed; V1's C4 row uses a 1503-row
  truncated window vs ~3000 for completed cycles.
- **Halving is scheduled, not exogenous** -- any "phase locking" partially
  reflects a deterministic schedule, not emergent synchronization.
- **ETF flows dwarf miner issuance** (~0.5-1B/day ETF vs ~36M/day miner,
  12-28x) -- the post-2024 supply-shock channel is structurally different
  from earlier cycles.
- **No prospective-OOS precedent** for crypto-cycle prediction exists
  (across Vicsek / Kuramoto / diffusion-map literature scanned: zero
  crypto-aware predictive applications).
- **Therefore**: the "heavy flock, same season" framing is a defensible
  *interpretation* of a conserved cycle, NOT a validated predictive model.
  Leg 2 mechanism (cap-driven amplitude compression) is empirical with
  finance analogies (BFL impact law, Pessa 2023 cross-section, Drozdz
  2018 BTC maturation) but has no uniquely-derived theoretical model. The
  slope beta ~= -0.40 (LOOCO stable, R^2 > 0.97) is descriptive, not
  predictive. **Do not extrapolate multipliers or dates from it.**

---
*Returns panel: `data/processed/returns_aligned.csv` (BTC + 5-panel, weekly log returns) -- Full notes: [`docs/theorical-framework/main-summary.md`](https://github.com/{{ site.github.owner_name }}/{{ site.github.repository_name }}/blob/main/docs/theorical-framework/main-summary.md) + [`docs/blockers/I-20-predictive-gates-failed.md`](https://github.com/{{ site.github.owner_name }}/{{ site.github.repository_name }}/blob/main/docs/blockers/I-20-predictive-gates-failed.md) -- Reproducibility scripts: `scripts/theory/` (diffusion_probe.py, hawkes_probe.py, noisy_oscillator.py, freq_amp_probe.py, heavy_flock_probe.py, validate_v1.py, mixed_framework_validation_V4.py).*

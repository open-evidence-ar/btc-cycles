# I-20 Blocker — Theoretical-framework predictive gates failed (publication note)

**Increment:** I-20 (econophysics "flock / heavy pendulum" framework — predictive validation)

**Date:** 2026-08-02

**Status:** Resolved as **descriptive-only** — no pipeline change; reframe published in
`docs/theorical-framework/main-summary.md` § "Cycle Vitality"

**Rule tuned:** No — new exploratory increment (per DESIGN.md §9.4, failures-publishable)

## Background / prior state

`docs/theorical-framework/main-summary.md` framed three econophysics papers
(collective behaviour / crowding synchronization / manifold learning) as the
quantitative handle on the BTC halving cycle. The framing was **literature-
level only** — no model had been fit, no gate had been run. The natural next
question: can any of these models *predict* the cycle (next top / next bottom
/ next phase), or are they only descriptive analogies?

## Input snapshots (current, data/processed 2026-08-02)

- `data/processed/returns_aligned.csv` — 12004 rows, 2008-10-20 → 2028-05-29,
  6-asset common panel (btc, mstr, spx, ndx, dxy, tlt) fully populated.

- `data/events.csv` — H1–H5, T1–T4 (final_top + C3 first_high 2021-04-14, both
  `reason_code=canonical`), B0–B3.

- `requirements.txt` — requests, pandas, numpy, plotly, kaleido, pytest.
  **No scipy, no sklearn.** All probes are pure-numpy implementations.

## Probe key (P1..P6 labels)

The "Probes run" table below uses short labels P-D / P-H / P-O / P-FA for
the four predictive probes and V1 / V2 / V3 for the three verification
probes. Two of the probes (P-O and P-FA) are themselves composite -- each
contains multiple sub-tests labeled P1..P6. This key enumerates what each
P-number tests so a reader can decode the per-probe internal numbers in the
"Per-probe internal numbers" section without ambiguity.

| Label | Probe | Sub-test | What it tests |
|-------|-------|----------|---------------|
| P-D   | diffusion map       | --   | Landmark diffusion-map embedding of the 6-asset weekly-return panel; ARI vs hand-labeled P1..P4 halving-cycle phases |
| P-H   | Hawkes              | --   | Hawkes self-exciting point process + DXY/TLT covariates; out-of-sample C4 peak prediction error vs +/-60d gate |
| P-O   | noisy oscillator    | P1   | Regime enrichment of extreme weekly returns INSIDE the top-phase window (theta = 0.36 +/- 0.027) across HIGH / NORMAL / LOW DXY regimes |
| P-O   | noisy oscillator    | P2   | Noise variance (var of detrended log price) INSIDE the top-phase window across HIGH / NORMAL / LOW DXY regimes |
| P-O   | noisy oscillator    | P3   | Calendar position of C4 top relative to the predicted top-phase window (loose H4+600..H4+1100d, tight H4+900..H4+1500d) |
| P-FA  | freq-amplitude      | P4   | Pearson r between trailing DXY-stress integral and the halving->top interval across the 4 completed cycles |
| P-FA  | freq-amplitude      | P5   | Trailing-integral regime enrichment (same construction as P-O P1 but on DXY-stress-integral terciles) |
| P-FA  | freq-amplitude      | P6   | Pearson r between TLT 180-day momentum and the halving->top interval (alternative macro covariate check) |
| V1    | verification        | --   | Dominant eigenvalue of the per-cycle correlation matrix on a FIXED 6-asset panel (no panel-growth confound); plus 3-alternate-panel and non-overlapping-7d robustness, plus bootstrap 95% CIs |
| V2    | verification        | --   | Calendar seasonality: halving->top and top->bottom intervals from canonical events.csv (reason_code=canonical) |
| V3    | verification        | --   | BTC weekly-return autocorrelation per cycle (lag scan 1..156w); stationarity of mean\|AC\| and of the dominant |AC| lag |
Note on the C3 / first_high vs final_top row in the table below: the "Probes
run" table uses C3 final_top 2021-11-10 as the canonical C3 top for the gate
verdicts. P-FA P4 was also evaluated with C3 first_high 2021-04-14 (which is
also reason_code=canonical in events.csv); the sign-flip between the two is
the documented fragility. Both labels are legitimate; the table chose
final_top for consistency with the other cycles where only final_top exists.

Adversarial review (3 subagents) independent findings:

- **Statistician:** +/-60d / >=3-of-4 gate is ill-defined and unregistered; panel
  coverage collapses pre-2022; Shakourloo & Azimli (2026) mischaracterized
  (no halving dummy in the structural VAR); Wątorek et al. (2025) already
  near order-parameter, narrowing the novelty wedge.
- **Crypto-realist:** halving is scheduled, not exogenous (breaks predator
  analogy); ETF flows $0.5-1B/day dwarf miner issuance (~$36M/day) 12-28x;
  reflexivity breaks the manifold assumption; 2024 ATH pre-halving.
- **Predictive auditor:** zero prospective-OOS precedent for crypto-cycle
  prediction (Couzin=0, Kuramoto=2, ISOMAP/diffusion=3 -- none on crypto).

## Per-probe internal numbers

The verdicts in the table above collapse each probe to a single pass/fail gate.
This section preserves the per-probe internal numbers that produced those
verdicts, so the negative result is auditable probe-by-probe rather than only
at the headline level.

### P-D — landmark diffusion map (Probe 1)

- Common panel: 6 assets (btc, mstr, spx, ndx, dxy, tlt), 7685 rows after
dropna + phase labels.

- ARI vs hand-labeled P1-P4 phases: -0.001 (no unsupervised phase recovery).

- Per-cycle Markov eigenvalues lambda_1: C1=0.9923, C2=0.7901, C3=0.0679.
  (This is the series that originally looked like coherence decay.)

- Spectral gap lambda_2/lambda_3: C1=1.020, C2=2.295, C3=2.785. The gap
  GROWS across cycles, which is the opposite of a noise-driven decay and is
  what clued the landmark-kernel-artifact diagnosis.

- C4 skipped (only 2 landmarks in the C4 window).

### P-H — Hawkes + DXY/TLT covariates (Probe 2)

- Train: events pre-H3 (2020-05-11). Test: 6 events at/after H3.

- Branching ratio eta = 0.3701 (stationary, <1; no explosive cascade).

- Decay rate beta = 0.00075/day -> excitation half-life ~= 924d.

- Covariates: DXY dominant (mu_1 = 1.99957e-3), TLT approximately null
  (mu_2 = 1.00000e-4, ~20x weaker).

- Predicted smoothed intensity peak: 2024-11-03. Actual C4 top: 2025-10-06.
  OOS error = 337d EARLY (gate +/-60d -> FAIL).

- Intensity at the C4 top (2.09e-3) is 36% BELOW intensity at the C3 top
  (3.26e-3). The model's predicted peak was therefore both early AND weak
  -- two independent failures compressed into the single 337d headline number
  cited in the summary table above.

### P-O — noisy phase-locked oscillator (Probe 3)

- Phase angle theta = (t - t_halving)/1460. Top-phase window theta =
  0.36 +/- 0.027.

- Extreme-week threshold: |weekly log return| >= 0.081; 2154 extreme weeks
total in the sample.

- P1 (regime enrichment of extreme weeks inside the top-phase window):
  HIGH DXY regime 1.01x (signal BURIED), NORMAL 2.45x, LOW 2.00x.
  The original prediction was HIGH > NORMAL > LOW; observation is NORMAL > LOW
  > HIGH -- the sign of the regime effect is the OPPOSITE of predicted.

- P2 (variance of detrended log price inside the top-phase window):
  HIGH=0.0101, NORMAL=0.1247, LOW=0.3449 -- INVERTED versus the prediction
  (high-liquidity regimes were expected to DAMPEN noise; they have the
  lowest variance instead). This P2 measurement is declared INVALID and
  would need re-measurement on return residuals rather than detrended price
  levels before any interpretation; published here only as the reason it is
  excluded from the convergent finding.

- P3 (C4 top window miss): C4 top observed at +534d post-H4. LOOSE window
  H4+600..H4+1100d, TIGHT window H4+900..H4+1500d. +534d is 373d BELOW the
  loose window floor -> FAIL. DXY at H4 = high (z=1.74); at H4+850d =
  normal (z=0.70).

### P-FA — freq-amplitude with trailing DXY stress integral (Probe 4)

Integral = integral of max(z_DXY_trailing - 1, 0) over trailing 365 or 730
days; z_DXY_trailing is the 365-day rolling z of DXY log-returns.

- P4 (correlation between integral and halving->top interval across cycles):
  * On C3 first_high (+338d): r(integ365) = -0.931, r(integ730) = -0.799.
  * On C3 final_top (+548d, canonical): r(integ365) = -0.086, r(integ730) = +0.192.
  The sign-flip under a legitimate canonical-top choice is the documented
  fragility. Both final_top 2021-11-10 AND first_high 2021-04-14 carry
  reason_code=canonical in events.csv (rows 13-14); neither is a labeling
  convention, both are analyst-defensible cycle-top labels.

- P4 LOOCO on the first_high version: drop C1 -> r=-0.968, drop C2 -> r=-0.913,
  drop C3 -> r=-0.902, drop C4 -> r=-0.964. All four LOOCO fits land in
  [-0.97, -0.90], i.e. the first_high correlation is sample-stable -- the
  P4 fragility is therefore PURELY the canonical-top-label choice, not a
  sample-stability issue.

- P5 (trailing-integral regime enrichment, same construction as P-O P1 but
  on the DXY-stress integral terciles): broken. Enrichments 0.68x /
  0.00x / 0.00x across the three regimes (the breakdown is a phase-correlated
  exposure issue, not an interpretable signal). Excluded from the convergent
  finding.

- P6 (TLT 180-day momentum as alternative macro covariate): r = +0.018
  (null). DXY dominates; TLT carries no cycle-amplitude information at this
  horizon.

### V1 / V2 / V3 — verification probes (numbers documented in

docs/theorical-framework/main-summary.md lines 49-87, including the
robustness subsection at lines 61-73 covering 4 alternate panels,
NON-overlapping 7d returns, and bootstrap CIs -- not duplicated here)

## Hypothesis / prior assumption

Prior framing implied the cycle's amplitude decay (multipliers 526×→112×→22×→8×)
was the cycle "dying." Reframe hypothesis: **the cycle is not dying — it is
being rung at lower amplitude by a ~100× heavier flock (market cap) on the
same calendar schedule.** If true, the descriptive gates (V1–V3) pass while
the point-prediction gates (P-D/P-H/P-O/P-FA) fail.

## Expected vs actual

| Gate class | Expected (reframe) | Actual | Match |
|---|---|---|---|
| Point-prediction (P-D/P-H/P-O/P-FA) | FAIL | all 4 FAIL | ✅ |
| Descriptive (V1/V2/V3) | PASS | all 3 PASS (V1 robust across 4 panels + non-overlapping samples; V1 bootstrap CIs tight, C3 above C2 disjoint) | ✅ |
The reframe predicts exactly the observed split.

## Action taken (I-20)

1. `docs/theorical-framework/main-summary.md` — appended the "Cycle Vitality:
   Heavier Flock, Same Season" section: V1/V2/V3 tables, robustness
   subsection (3 alternate panels + non-overlapping 7d returns + bootstrap
   CIs), convergent finding, and an **honest-limits** block listing the 4
   failed point-prediction gates + adversarial constraints.
2. Pre-existing 3-paper framing (§1–§3) preserved unchanged.
3. No pipeline script, no `data/processed/*` file, no test touched — this is a
   documentation/provenance increment, not a data increment.
4. **No new gate test added** — I-20's contribution is the published negative
   result, not a regression test. Future pipeline increments do not depend on
   it.

## Residual uncertainty / known limitations

- **n = 4 completed cycles** (C1 immature, C4 incomplete): the V1–V3 PASSes
  are descriptive, not inferential. The bootstrap CIs on λ₁ are the closest
  thing to inference; they say "stable," not "exactly conserved."

- **C3 cycle-top ambiguity** (both 2021-04-14 first_high and 2021-11-10
  final_top carry `reason_code=canonical` in events.csv) is the *legitimate*
  source of P-FA's fragility. A pre-registered choice would resolve it; until
  then P-FA stays in the failed pile.

- **C4 still open** (bottom not observed): V1's C4 row uses a 1503-row
  truncated window; the λ₁ value (2.70) is provisional.

- **Market-cap normalization used `btc_close` as a proxy** (system mass).
  Per-asset market-cap series were not available in the repo. The mass-weighted
  λ₁ series (2.33 / 2.74 / 2.74 / 2.84) does not differ materially from the
  equal-weighted series, so the proxy is unlikely to be load-bearing — but this
  has not been stress-tested against a true mcap series.

- **Blocker does NOT upgrade the reframe to a predictive model.** It publishes
  the negative prediction results and the positive descriptive results
  side-by-side, per §9.4 (failures-publishable). Do not extrapolate
  multipliers, dates, or prices from the "heavy flock" framing.

## Cross-references

- `docs/theorical-framework/main-summary.md` — published reframe (lines 69–114)

- Probe scripts (NOT in repo; ran from `C:\Users\German\AppData\Local\Temp\opencode\`):
  `diffusion_probe.py`, `hawkes_probe.py`, `noisy_oscillator.py`,
  `freq_amp_probe.py`, `heavy_flock_probe.py`, `validate_v1.py`.
  Kept out of the repo deliberately — exploratory, not pipelineincrement.

- Literature: Wątorek et al. 2025 PRE 112:044309 (arXiv:2509.18820);
  Shakourloo & Azimli 2026 Springer J. Econ & Finance + SSRN 6377464;
  Choi & Choi 2026 Networks & Heterogeneous Media; Bray et al. 2022 GRL
  (diffusion-map OOS on Lorenz-96); Ginelli 2016 EPJST 225:2099 + Cavagna 2010 PNAS 107:11865 (flock order-parameter verification); Hong 2015 PRE 92:022122 (Kuramoto model scaling); Bouchaud, Farmer, Lillo 2009 Handbook of Financial Markets + Pessa, Perc, Ribeiro 2023 Sci Rep 13:3351 + Drożdż et al. 2018 Chaos 28:071101 (amplitude-compression analogies, mechanism unsourced).
- Mixed-framework validation (V4, this session, scripts/theory/mixed_framework_validation_V4.py): BTC B->T slope beta ≈ -0.40 (R2=0.97, LOOCO [-0.54,-0.31], spread 0.23); BTC H->T beta ≈ -0.41 (R2=0.96, LOOCO [-0.56,-0.34], spread 0.21); SPX macro mult declining (descriptive, n=4); mechanism open.

## Stage 2 update (2026-08-03) — Grounded-replacement probes (DEAD-END)

**Question raised:** Since the n=3 power-law extrapolation is fragile
(LOOCO spread documented below) and the descriptive framework (V1-V4)
shows the cycle has flock/coordination structure, can any biological /
behavioral grounded model **replace** the naive extrapolation --
giving equivalent or better B4/C5 forecasts with actual theoretical
mechanism behind them?

**Two candidates probed and rejected:**

### S-P1: LPPL (Sornette log-periodic power law)

A well-known herding/bubble model with both timing (singularity `tc`)
and amplitude (power-law envelope) baked into one framework. Per-bubble
fit, 7 params.

Probe: `scripts/theory/lppl_probe.py`. Hand-rolled Nelder-Mead (no scipy).
Read-only on `data/processed/`. Tested:

- Phase 1 in-sample: fit LPPL on each cycle's run-up [pre_halving_bottom,
  final_top]. Free `tc` within window [top-180d, top+180d]. Recovery:
  all 4 fits collapse to **upper boundary** (tc_err = +180d for every
  cycle).
- Phase 2 forward: constrain `tc > top + 30d`. All 4 fits again
  collapse to upper boundary (~1100d past observed top).

**Verdict: DEAD-END.** BTC peaks are not herding singularities in the
Sornette sense. The fitted singularity wants to land ~1-3 years later
than where tops actually pop. The 5-15 `omega` (log-periodic frequency)
range cannot accommodate halving-punctuated cycle structure.

### S-P2: SIR / logistic adoption saturation (Leg 2 mechanism)

Hypothesis: amplitude compression (multipliers 526x -> 112x -> 22x -> 8x)
is driven by Verhulst saturation of cumulative adoption. If marginal
adoption rate `dN/dt / N` at each halving year matches the observed
multiplier trajectory, the power-law extrapolation has a grounded
SIR-style replacement.

Probe: `scripts/theory/sir_probe.py`. Logistic fit on BTC mcap (only
available long-series adoption proxy).

Findings:

- Logistic fit on monthly mcap: K=$1.52T asymptote, r=0.87/yr, t_mid=
  2022.6. Reasonable shape.
- Predicted multipliers C1->C4 = 527 -> 525 -> 477 -> 123. Observed =
  527 -> 112 -> 22 -> 8. Marginal adoption rate compresses only **4.3x**
  over 12 years; observed multipliers compress **65x**. Mechanism is
  ~15x too weak.
- Statistical: log-rho = 0.746, slope = 1.93 (target 1.0), log-RMSE =
  2.20. PARTIAL signal but not a replacement.

**Verdict: DEAD-END.** Adoption saturation by itself does not explain
multiplier compression. Proper SIR would require active-addresses or
hodler-wallet series (not ingested in this repo) and even then the
mechanism-rate mismatch is too large.

### Why this is a hard dead-end (more fundamental than these two misses)

Two fair 2-parameter grounded alternatives fit on the observed multipliers
`[526, 112, 21.6, 8]`:

| Model            | Form                       | C5 mult | R^2  | LOOCO stability |
|------------------|----------------------------|--------:|-----:|----------------:|
| Power-law (idx)  | `631 * idx^-3.04`          | **4.75**| 0.93 | fragile (drop-C1 err 2.95x) |
| Exponential (yr) | `ln mult = 757.87 - 0.3735 * year` | **1.47** | 0.97 | implausibly low |

The two disagree by **3.2x on C5** -- a factor larger than the power-
law's own LOOCO confidence band. Root cause: **n=3 cycles anchoring a
2-param fit, dominated by the C1 outlier (bubble of 526x)**. No mcap-
driven, time-driven, or cycle-index-driven grounded model can converge
to a meaningful C5 from this data quality. The mechanism-space and
parameter-space are not separately identifiable.

### Action taken (Stage 2)

1. `scripts/theory/lppl_probe.py` and `scripts/theory/sir_probe.py`
   added to the theory probe folder. Read-only on `data/processed/`.
   Not in pipeline; not regression-tested; results printed to stdout
   only.
2. `scripts/theory/README.md` will be updated to list both new probes
   with their headline findings (planned, not yet applied -- see todo
   list).
3. **No change to the published forecast methodology.** The n=3 power-
   law in `build_next_cycle_zones.py` / `build_alt_next_cycle_zones.py`
   remains the source of B4/C5 forecasts. Their fragility is already
   documented in the I-20 honest-limits block and in `theory.md`'s
   "mechanism open" caveat.
4. **No change to the published framework.** V1-V4 descriptive checks
   remain intact in `theory.md` and `main-summary.md`. The framework's
   role remains interpretation-layer, not forecast-layer.

### Residual uncertainty

- LPPL was fit with a hand-rolled Nelder-Mead (no scipy in requirements).
  A scipy-grade optimizer or the SLand package's blinded fitting might
  reach a different local minimum. However, the consistent boundary-
  collapse behavior across 4 independent cycles and 2 constraint
  regimes is unlikely to be an optimizer artifact.
- The SIR probe used mcap as adoption proxy; proper proxies (active
  addresses, distinct hodler wallets) would require new fetchers. The
  mechanism-rate mismatch is too large for this to flip the verdict
  in any case.
- No quorum-threshold probe (Leg 1 grounded replacement) was run. The
  S-P2 failure on Leg 2 and the LPPL failure on both legs together make
  the marginal value of another single-leg probe low; the fundamental
  n=3 problem remains regardless of mechanism.

## Cross-references (Stage 2)

- `scripts/theory/lppl_probe.py` (new) -- LPPL fit probe (DEAD-END)
- `scripts/theory/sir_probe.py` (new) -- logistic adoption probe (DEAD-END)
- `scripts/theory/README.md` -- to be updated with Stage-2 probe rows
- `docs/theorical-framework/main-summary.md` -- framework unchanged
- `_sections/theory.md` -- published framework unchanged

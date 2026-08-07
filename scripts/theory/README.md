# scripts/theory/

Exploratory econophysics probes supporting
`docs/theorical-framework/main-summary.md` and `docs/blockers/I-20-predictive-gates-failed.md`.

These scripts are **exploratory, not pipeline**. They are read-only on
`data/processed/returns_aligned.csv` and `data/events.csv`. Outputs go to
stdout (and optionally a timestamped CSV in `%TEMP%\opencode\`).

## Required deps

No new deps — pure `pandas` + `numpy` (already in `requirements.txt`).
**No scipy, no sklearn.** The landmark diffusion-map is hand-rolled.

## Scripts

| Script | Probe | What it tests | Numbers cited in | Findings (headline numbers) |
|--------|-------|---------------|-------------------|------------------------------|
| `diffusion_probe.py` | P-D | Landmark diffusion map of 6-asset weekly returns; ARI vs hand-labeled P1-P4 phases; per-cycle Markov spectral gap | I-20 row 1; main-summary honest-limits | ARI = -0.001; lambda_1 = 0.9923 / 0.7901 / 0.0679 (C1..C3); spectral gap 1.020 / 2.295 / 2.785 (grows, NOT decays -- the artifact signature) |
| `hawkes_probe.py` | P-H | Hawkes self-exciting + DXY/TLT covariates; OOS peak prediction for C4 | I-20 row 2 | eta = 0.37 (stationary); beta = 0.00075/d (t1/2 ~924d); DXY mu_1 = 2.0e-3 dominant, TLT mu_2 ~0; OOS peak 337d EARLY; intensity at C4 top 36% below C3 top |
| `noisy_oscillator.py` | P-O | Phase-locked oscillator (theta = (t-t_H)/1460); top-phase enrichment in HIGH/NORMAL/LOW DXY regimes; C4 top window miss | I-20 row 3 | P1 enrichment HIGH/NORMAL/LOW = 1.01x / 2.45x / 2.00x (HIGH buried, sign inverted); P2 noise var = 0.0101 / 0.1247 / 0.3449 (inverted, declared invalid); P3 C4 at +534d, 373d below the loose window -- FAIL |
| `freq_amp_probe.py` | P-FA | Trailing DXY-stress integral vs H->T interval; fragility to canonical C3 top choice (first_high vs final_top) | I-20 row 4 | P4 r(integ365) = -0.931 on C3 first_high, collapses to -0.086 on canonical final_top; LOOCO first_high all in [-0.97,-0.90] (sample-stable); P5 broken (0.68x/0x/0x); P6 TLT r = +0.018 (null) |
| `heavy_flock_probe.py` | V1+V2+V3 | Fixed-panel lambda1 per cycle; halving->top / top->bottom intervals from events.csv; BTC weekly-return autocorrelation per cycle | main-summary V1/V2/V3 tables | V1 lambda1 fixed-panel = 2.4142 / 2.3842 / 2.9204 / 2.7035 (C1..C4); mass-weighted = 2.3288 / 2.7443 / 2.7443 / 2.8423; V2 halving->top 371/525/546/534d; V3 dominant |AC| lag 89/113/116w, mean|AC| ~0.06 |
| `validate_v1.py`         | V1 robustness | Panel sensitivity (4 panels), non-overlapping 7d returns, bootstrap 95% CIs on lambda1 | main-summary robustness subsection | 4 panels all stable (orig_6 2.38-2.92, drop_mstr 2.06-2.50, crypto_4 2.68-3.12, risk_4 2.00-2.21); non-overlapping 7d lambda1 = 2.41/2.45/2.94/2.88; bootstrap 95% CIs: C1[2.359-2.483] C2[2.298-2.495] C3[2.838-3.012] C4[2.614-2.820] |
| `mixed_framework_validation_V4.py` | V4 mixed framework | BTC multiplier-decay vs cap growth (B->T + H->T regressions, LOOCO, macro cross-check SPX); mechanism-caveat frame | I-20 blocker cross-reference; proposed Section 4 (mixed framework: date=flock / compression=open) | beta = -0.395 (B->T, R2=0.97, LOOCO [-0.54,-0.31]); beta = -0.412 (H->T, R2=0.96, LOOCO [-0.56,-0.34]); closest analogies: BFL (~-0.50, multi-year caveat) > Gabaix (~-0.17, cross-section); mechanism UNSOURCED; descriptive only |
| `lppl_probe.py` | S-P1 | Sornette log-periodic power law per-bubble fit (free `tc` + fwd-constrained); 7 params; hand-rolled Nelder-Mead (no scipy) | I-20 Stage-2 update (DEAD-END) | Phase 1 (free tc, +/-180d window): 4/4 fits collapse to upper boundary (tc_err = +180d); Phase 2 (tc > top + 30d): 4/4 collapse to upper boundary (~1100d past observed top). BTC peaks are not herding singularities in the Sornette sense; fitted critical time wants to land 1-3yr after the actual pop. |
| `sir_probe.py` | S-P2 | Logistic / Verhulst saturation of BTC cumulative adoption (mcap proxy) as grounded alternative for multiplier compression (Leg 2) | I-20 Stage-2 update (DEAD-END) | K=$1.52T, r=0.87/yr, t_mid=2022.6. Predicted mult C1-C4 = 527/525/477/123; observed 527/112/22/8. Marginal adoption rate compresses 4.3x; observed mult compresses 65x (~15x mismatch). log-rho=0.746, slope=1.93, log-RMSE=2.20. PARTIAL signal, NOT a replacement. |

## Reproducing the published numbers

```powershell
cd D:\trading
$env:PYTHONIOENCODING="utf-8"
python scripts\theory\validate_v1.py        # ~30s, bit-exact reproduction
python scripts\theory\heavy_flock_probe.py   # V1+V2+V3
python scripts\theory\diffusion_probe.py     # P-D (~5-10s)
python scripts\theory\hawkes_probe.py        # P-H (~2-3 min, scipy-free Hawkes MLE)
python scripts\theory\noisy_oscillator.py   # P-O (~10s)
python scripts\theory\freq_amp_probe.py      # P-FA (~30s)
```

## Conventions

- All scripts hard-code `D:\trading` as `REPO` — they work from any cwd.
- All scripts print a `[saved]` line if they write a CSV; the CSV path is
  always under `%TEMP%\opencode\`, never under the repo.
- All scripts declare read-only intent in their docstring and never touch
  `data/processed/*` or `data/raw/*`.
- Scripts use rolling 7d log returns from `*_log_return_w7d` columns.
  Cycle windows are halving -> next-halving (C1: 2012-11-28 -> 2016-07-09,
  etc.).

## What this folder is NOT

- Not part of the increment pipeline. `pytest tests/` does not collect
  anything from here, and nothing in `scripts/theory/` is imported by
  `build_*.py` or `scripts/*.py`.
- Not a model fit. All probes are diagnostic — they print numbers and stop.
  No model is saved, no predictions are persisted.

If any of these scripts becomes a load-bearing piece of an increment,
it should be promoted out of `scripts/theory/` into `scripts/` proper
and given a gate test.
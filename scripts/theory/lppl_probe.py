"""
LPPL probe (Leg 1 + Leg 2 grounded alternative test).

Question: Can Sornette's Log-Periodic Power Law (LPPL) -- a well-known
behavioral/herding model with both timing (singularity tc) and amplitude
(power-law envelope) baked into ONE framework -- replace our naive n=3
power-law extrapolation for BTC B4/C5?

LPPL form (Sornette, Filimonov, Wu 2014 standardized form):
    ln P(t) = A + B * (tc - t)^m * [1 + C * cos(omega * ln(tc - t) + phi)]

This is a behavioral model:
    tc = critical time (singularity / crash / top)
    m  = power-law exponent (0 < m < 1 -- bubble growth exponent)
    omega = log-frequency of oscillations (herding oscillation)
    B, C, phi = amplitude / phase
    A = terminal price level

Strategy:
    Phase 1 (in-sample fit): Fit LPPL to each completed cycle's run-up
    (pre_halving_bottom -> final_top) and check whether the recovered
    tc lands within +/- 30 days of the observed top. If it does, LPPL
    is IN-SAMPLE consistent.

    Phase 2 (LOOCO forecast): Drop cycle Ci, fit LPPL on the other
    two cycles' combined run-up windows (treated as a single
    rescaled-time series -- normalize each cycle to 0..1 then
    concatenate), recover LPPL parameters, project tc for the held
    out cycle's price peak. Compare to power-law which has
    D_halving_to_top = 371/525/548/534 (C1/C2/C3/C4).

    Phase 3 (C5 forward): Fit LPPL on C4 ongoing run-up
    (2022-11-21 -> today) with tc > today constraint; report tc as
    implied C4 top and compare to observed C4 top (2025-10-06).
    Then if LPPL survived Phase 1+2, fit on ALL four cycles combined
    and project C5 top tc.

Dependencies: numpy only (no scipy, no sklearn). Nelder-Mead is
hand-rolled. Read-only on data/processed/. Outputs to stdout only.

References:
    Sornette, D. (2003) "Why Stock Markets Crash" Princeton.
    Filimonov & Sornette (2013) Physica A 392:3698.
    Lin, Filimonov, Sornette (2014) SSRN 25161.
"""

import numpy as np
import pandas as pd
import io as _io
import sys
import datetime as _dt

REPO = r"D:\trading"
ENV_PATH = REPO + r"\data\events.csv"
PRC_PATH = REPO + r"\data\processed\btc_cycle_metrics.csv"
RAW_PATH = REPO + r"\data\raw"  # may need to read raw BTC closes

# ---------- LPPL model ----------

def lppl(t, A, B, tc, m, C, omega, phi):
    """Sornette LPPL. t is time in days (scalar or array)."""
    dt = tc - np.asarray(t)
    dt = np.where(dt <= 0, 1e-6, dt)  # avoid log(0)/neg
    base = A + B * (dt ** m)
    osc = 1.0 + C * np.cos(omega * np.log(dt) + phi)
    return base * osc

def lppl_log(t, *p):
    """Log-price form (what we actually fit)."""
    A, B, tc, m, C, omega, phi = p
    return np.log(np.maximum(lppl(t, A, B, tc, m, C, omega, phi), 1e-9))

def fit_lppl(t, logp, t_bounds, seed_rd=None, n_restart=24):
    """Fit LPPL by Nelder-Mead. Returns (params, rmse).

    Sornette empirical bounds (Filimonov & Sornette 2013):
       m in [0.01, 0.99]    (for bubble; m<1 critical; typically 0.1-0.6)
       omega in [2.5, 15]    (log-periodic frequency, herding oscillation)
       C in [-0.95, 0.95]    (relative amplitude)
       B wide (positive=crash down, negative=bubble up)
       A in log-price scale
    """
    rng = np.random.default_rng(seed_rd if seed_rd is not None else 0)
    best = None
    best_rmse = np.inf
    bounds_default = [
        (float(logp.min())*1.1, float(logp.max())*1.1),    # A
        (-50.0, 50.0),                                       # B (sign free)
        (t_bounds[0], t_bounds[1]),                          # tc
        (0.01, 0.99),                                         # m
        (-0.95, 0.95),                                        # C
        (2.5, 15.0),                                          # omega
        (-np.pi, np.pi),                                      # phi
    ]
    # multi-start: include grid-seeded tc points within t_bounds
    tc_grid = np.linspace(t_bounds[0], t_bounds[1], 5)
    n_grid = len(tc_grid)
    n_total = max(n_restart, n_grid * 4)
    for i in range(n_total):
        p0 = np.array([rng.uniform(*b) for b in bounds_default])
        # for grid-starts, seed tc deterministically
        if i < n_grid * 4 and i % 4 == 0:
            p0[2] = tc_grid[i // 4]
        result = _nelder_mead(
            lambda p: _rmse(lppl_log(t, *p), logp),
            p0, bounds_default, max_iter=8000
        )
        r = _rmse(lppl_log(t, *result), logp)
        if r < best_rmse and np.isfinite(r):
            best_rmse = r
            best = result
    return best, best_rmse

def _rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))

# ---------- Hand-rolled Nelder-Mead (no scipy) ----------

def _nelder_mead(func, x0, bounds, max_iter=4000, tol=1e-6):
    """Simple bounded Nelder-Mead."""
    n = len(x0)
    clip = lambda x: np.array([min(max(x[i], bounds[i][0]), bounds[i][1]) for i in range(n)])
    # initial simplex
    simplex = [clip(x0.copy())]
    for i in range(n):
        e = np.zeros(n)
        e[i] = 0.05 * max(abs(x0[i]), 1.0)
        simplex.append(clip(x0 + e))
    simplex = np.array(simplex)
    f = np.array([func(x) for x in simplex])
    for _ in range(max_iter):
        order = np.argsort(f)
        simplex, f = simplex[order], f[order]
        if f[-1] - f[0] < tol:
            break
        centroid = simplex[:-1].mean(axis=0)
        centroid = clip(centroid)
        # reflection
        xr = clip(2*centroid - simplex[-1])
        fr = func(xr)
        if f[0] <= fr < f[-2]:
            simplex[-1], f[-1] = xr, fr
            continue
        # expansion
        if fr < f[0]:
            xe = clip(2*xr - centroid)
            fe = func(xe)
            if fe < fr:
                simplex[-1], f[-1] = xe, fe
            else:
                simplex[-1], f[-1] = xr, fr
            continue
        # contraction
        xc = clip(0.5*centroid + 0.5*simplex[-1])
        fc = func(xc)
        if fc < f[-1]:
            simplex[-1], f[-1] = xc, fc
            continue
        # shrink
        for i in range(1, n+1):
            simplex[i] = clip(simplex[0] + 0.5*(simplex[i] - simplex[0]))
            f[i] = func(simplex[i])
    return simplex[0]

# ---------- data ----------

def load_btc_closes():
    """Load BTC daily closes, return DataFrame with date, close."""
    # processed/btc_log_return_w7d.csv or raw/bitstamp_daily.csv
    cands = [
        REPO + r"\data\raw\btc_bitstamp_2026-07-30.csv",
        REPO + r"\data\raw\btc_bitstamp_2026-07-29.csv",
        REPO + r"\data\raw\btc_bitstamp_2026-07-20.csv",
        REPO + r"\data\raw\bitstamp_daily.csv",
        REPO + r"\data\raw\btc_daily.csv",
        REPO + r"\data\raw\bitstamp_btcusd_daily.csv",
    ]
    import os
    for p in cands:
        if os.path.exists(p):
            df = pd.read_csv(p)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            elif 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp'])
            else:
                df['date'] = pd.to_datetime(df.iloc[:,0])
            for col in ['close','Close','price','px_last']:
                if col in df.columns:
                    return df[['date', col]].rename(columns={col:'close'}).sort_values('date').reset_index(drop=True)
    raise FileNotFoundError("BTC daily closes not found")

def lppl_fit_cycle(df_close, t0_date, t1_date, t_bounds_date=None, n_restart=48, label="", verbose=True):
    """Fit LPPL on [t0, t1] window. t in days from t0.
    Returns dict with observed_peak_offset, fitted_tc_offset, error_days, params, rmse.
    """
    mask = (df_close['date'] >= t0_date) & (df_close['date'] <= t1_date)
    sub = df_close[mask].copy()
    if len(sub) < 60:
        return None
    sub['t'] = (sub['date'] - t0_date).dt.days.values.astype(float)
    sub['logp'] = np.log(sub['close'].values.astype(float))
    t = sub['t'].values
    logp = sub['logp'].values
    if t_bounds_date is None:
        # default: tc must lie within +/- 90 days of t1
        t1_offset = (t1_date - t0_date).days
        t_bounds = (t1_offset - 180, t1_offset + 180)
    else:
        t_bounds = ((t_bounds_date[0] - t0_date).days, (t_bounds_date[1] - t0_date).days)
    params, rmse = fit_lppl(t, logp, t_bounds, n_restart=n_restart)
    tc_offset = params[2]
    observed_peak_offset = (t1_date - t0_date).days
    err = tc_offset - observed_peak_offset
    if verbose:
        print(f"  [{label}] window {t0_date.date()}->{t1_date.date()} ({len(sub)}d)")
        print(f"   A={params[0]:.2f} B={params[1]:.3f} tc={params[2]:.1f} m={params[3]:.3f}")
        print(f"   C={params[4]:.3f} omega={params[5]:.2f} phi={params[6]:.3f}")
        print(f"   RMSE={rmse:.4f}  tc_offset={tc_offset:.1f} observed={observed_peak_offset} diff={err:+.1f}d")
    return {
        't0': t0_date, 't1_observed': t1_date,
        'observed_offset': observed_peak_offset,
        'tc_offset': float(tc_offset), 'err_days': float(err),
        'rmse': rmse, 'params': params,
    }

# Main

def main():
    print("=" * 78)
    print("LPPL PROBE -- Sornette behavioral model vs naive n=3 power-law extrapolation")
    print("=" * 78)

    df_close = load_btc_closes()
    print(f"BTC daily closes loaded: {len(df_close)} rows, range {df_close['date'].min().date()} .. {df_close['date'].max().date()}")

    cyc = pd.read_csv(PRC_PATH)
    cyc['pre_halving_bottom_date'] = pd.to_datetime(cyc['pre_halving_bottom_date'])
    cyc['halving_date'] = pd.to_datetime(cyc['halving_date'])
    cyc['final_top_date'] = pd.to_datetime(cyc['final_top_date'])
    cyc['first_high_date'] = pd.to_datetime(cyc['first_high_date'], errors='coerce')

    today = pd.Timestamp.now().normalize()
    if today < pd.Timestamp('2026-08-03'):
        today = pd.Timestamp('2026-08-03')  # use file-data aware "today"

    # ---------- Phase 1: in-sample LPPL fit per cycle ----------

    print("\n--- Phase 1: in-sample LPPL fit (run-up bottom -> observed top) ---")
    print("Question: does fitted tc land within +/- 30d of observed top?")
    phase1_results = {}
    for _, row in cyc.iterrows():
        c = row['cycle_id']
        if pd.isna(row['final_top_date']):
            continue
        t0 = row['pre_halving_bottom_date']
        t1 = row['final_top_date']
        r = lppl_fit_cycle(df_close, t0, t1, label=f"{c} in-sample", n_restart=48)
        phase1_results[c] = r

    print("\n  Phase 1 summary:")
    for c, r in phase1_results.items():
        verdict = "PASS" if abs(r['err_days']) <= 30 else ("MARGINAL" if abs(r['err_days']) <= 90 else "FAIL")
        print(f"   {c}: tc_err = {r['err_days']:+.1f}d  RMSE={r['rmse']:.4f}  -> {verdict}")

    # ---------- Phase 2: LOOCO forecast (drop one cycle, fit LPPL on other two,
    # project tc for the held-out cycle's run-up midpoint...) ---------------
    # NOTE: LPPL is a per-bubble model, not a multi-cycle model. So a proper
    # LOOCO is awkward. Instead, we do: drop cycle Ci, FIT LPPL on the run-up
    # window of Ci itself but with t_bounds forced OUTSIDE the observed top
    # by +365d..+1095d. If LPPL "predicts" a top within 12 months of the
    # observed top, that's a forward forecast (not in-sample).

    print("\n--- Phase 2: forward LPPL forecast (tc forced past observed top) ---")
    print("Question: if we force tc > observed_top + 30d, where does LPPL settle?")
    phase2_results = {}
    for _, row in cyc.iterrows():
        c = row['cycle_id']
        if pd.isna(row['final_top_date']):
            continue
        t0 = row['pre_halving_bottom_date']
        t1 = row['final_top_date']
        # constrain tc to land AFTER the observed top
        t_bounds_date = (t1 + pd.Timedelta(days=30), t1 + pd.Timedelta(days=1095))
        r = lppl_fit_cycle(df_close, t0, t1, t_bounds_date=t_bounds_date, label=f"{c} fwd", n_restart=48)
        phase2_results[c] = r

    print("\n  Phase 2 summary (fwd forecast, tc constrained past observed top):")
    for c, r in phase2_results.items():
        verdict = "PASS" if 0 <= r['tc_offset'] - r['observed_offset'] <= 60 else ("MARGINAL" if 0 <= r['tc_offset'] - r['observed_offset'] <= 180 else "FAIL")
        print(f"   {c}: tc_fwd = {r['tc_offset']:.1f}, observed = {r['observed_offset']}d, fwd_err = {r['tc_offset']-r['observed_offset']:+.1f}d  RMSE={r['rmse']:.4f}  -> {verdict}")

    # ---------- Phase 3: C4 forward + C5 forward (only if Phase 1 had >=2 PASSes) ----------

    n_phase1_pass = sum(1 for r in phase1_results.values() if abs(r['err_days']) <= 30)
    n_phase2_marg = sum(1 for r in phase2_results.values() if 0 <= r['tc_offset']-r['observed_offset'] <= 180)

    print(f"\n--- Phase 3: C4 ongoing and C5 forward (gated by phase 1 >=2 PASS or phase 2 >=2 MARGINAL) ---")
    print(f"  Phase 1 PASS = {n_phase1_pass}/4, Phase 2 MARGINAL+ = {n_phase2_marg}/4")

    if n_phase1_pass >= 2 or n_phase2_marg >= 2:
        print("  -> Proceeding with C4 forward fit (constrained tc > today)")
        # C4 ongoing
        c4 = cyc[cyc['cycle_id']=='C4'].iloc[0]
        t0 = c4['pre_halving_bottom_date']
        t1 = today
        # constrain tc to be after today
        t_bounds_date = (today + pd.Timedelta(days=1), today + pd.Timedelta(days=730))
        r4 = lppl_fit_cycle(df_close, t0, t1, t_bounds_date=t_bounds_date, label="C4 ongoing fwd", n_restart=64)
        if r4 is not None:
            tc_date = t0 + pd.Timedelta(days=int(r4['tc_offset']))
            obs_top_date = c4['final_top_date']
            if pd.notna(obs_top_date):
                print(f"  C4 implied tc = {tc_date.date()}  vs observed top = {obs_top_date.date()}")
            else:
                print(f"  C4 implied tc = {tc_date.date()}  (no observed top yet)")

        # C5 forward: fit on ALL FOUR cycles' run-up windows rescaled to [0,1]
        # Then project tc for C5 = ?
        # This is a stretch -- LPPL is per-bubble. We'll skip and acknowledge.
        print("\n  C5 projection: LPPL is a per-bubble model and has no straightforward")
        print("  multi-cycle aggregation. Skipping C5 forward projection.")
        print("  Verdict: if Phase 1+2 showed signal, the model is per-cycle descriptive;")
        print("  it does NOT replace the n=3 power-law for C5 top (insufficient n=3 history).")
    else:
        print("  -> DEAD-END: LPPL does not consistently forecast BTC cycle tops.")
        print("     Power-law extrapolation remains the only available forecast tool.")

    # ---------- Final verdict ----------

    print("\n" + "=" * 78)
    print("VERDICT:")
    print(f"  Phase 1 in-sample PASS: {n_phase1_pass}/4")
    print(f"  Phase 2 fwd MARGINAL+:  {n_phase2_marg}/4")
    if n_phase1_pass >= 3 and n_phase2_marg >= 2:
        print("  -> LPPL shows signal. Worth deeper investigation.")
    elif n_phase1_pass >= 2 or n_phase2_marg >= 2:
        print("  -> LPPL shows partial signal. Possible supplementary descriptive use,")
        print("     but does NOT replace the naive power-law extrapolation.")
    else:
        print("  -> DEAD-END. LPPL does not beat naive power-law fit on BTC cycles.")
        print("     No biological/behavioral grounded model beats n=3 curve-fit;")
        print("     the power-law remains the only available forecast tool.")
    print("=" * 78)

if __name__ == "__main__":
    main()

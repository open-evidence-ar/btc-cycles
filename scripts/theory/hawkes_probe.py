"""
Hawkes probe — READ ONLY on repo data.
Tests whether a self-exciting Hawkes process with DXY/TLT covariates
predicts cycle-extrema events out-of-sample.

Model:
  lambda(t) = mu0 + mu1*Dx(t) + mu2*T(t) + sum_k eta*exp(-beta*(t-tk))
    where Dx(t) = DXY pct-change (rolling 30d)
          T(t)  = TLT pct-change (rolling 30d)
          tk    = past extreme events (halvings, cycle tops, cycle bottoms)

Train: events up to 2020-05-11 (H3). Predict C3 events + C4 top.
Gate: |predicted_intensity_peak - observed_C4_top| < 60d
      AND branching ratio eta < 1 (stability)

Pure numpy (no scipy / sklearn per requirements.txt).
Output: stdout + /tmp/hawkes_probe_<ts>.csv only.
"""
import numpy as np
import pandas as pd
from datetime import datetime
import os, time

REPO = r"D:\trading"
RAW = os.path.join(REPO, "data", "processed", "returns_aligned.csv")
EV  = os.path.join(REPO, "data", "events.csv")
OUTDIR = r"C:\Users\German\AppData\Local\Temp\opencode"
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_csv(RAW); ev = pd.read_csv(EV)
df["date"] = pd.to_datetime(df["date"]); ev["date"] = pd.to_datetime(ev["date"])

# pivots: daily-close -> daily pct change of DXY + TLT (or use w7d log_return)
# use closest available daily-close series from returns_aligned
panel_cov = df[["date","dxy_close","tlt_close"]].dropna().sort_values("date").reset_index(drop=True)
# rolling 30d pct change
panel_cov["dxy_pct30"] = panel_cov["dxy_close"].pct_change(30)
panel_cov["tlt_pct30"] = panel_cov["tlt_close"].pct_change(30)
panel_cov = panel_cov.dropna().reset_index(drop=True)
# build Nx1 t = days since panel start
panel_cov["t_days"] = (panel_cov["date"] - panel_cov["date"].iloc[0]).dt.days.to_numpy()
T_TOTAL = panel_cov["t_days"].iloc[-1] + 1

# events: halvings + canonical tops + canonical bottoms
events_all = ev[ev["event_type"].isin(["halving","top","bottom"])].copy()
events_all = events_all[
    (events_all["reason_code"] == "canonical") |
    (events_all["event_type"] == "halving")
].copy()
# drop NaT
events_all = events_all[events_all["date"].notna()].copy()
events_all["t_days"] = (events_all["date"] - panel_cov["date"].iloc[0]).dt.days
events_all = events_all[events_all["t_days"] >= 0].sort_values("t_days").reset_index(drop=True)
print("[hawkes] total canonical events:", len(events_all))
print(events_all[["event_type","label","date","t_days"]].to_string())

# split train/test: cutoff at H3 = 2020-05-11
cutoff_h3 = pd.Timestamp("2020-05-11")
train_idx = events_all["date"] <= cutoff_h3
test_idx  = ~train_idx
train_events = events_all[train_idx].reset_index(drop=True)
test_events  = events_all[test_idx].reset_index(drop=True)
print(f"\n[hawkes] train: {len(train_events)} events (pre-2020-05-11)")
print(f"[hawkes] test:  {len(test_events)} events (post-2020-05-11)")
print(f"[hawkes] train event times (days): {train_events['t_days'].tolist()}")
print(f"[hawkes] test  event times (days): {test_events['t_days'].tolist()}")

# build covariate arrays on a common daily grid (t=0..T_TOTAL-1)
t_grid = np.arange(T_TOTAL, dtype=float)
def daily_lookup(series, t):
    # series is panel_cov[t_days, col]; t is day index; nearest lookup
    s_idx = panel_cov["t_days"].searchsorted(int(t))
    s_idx = min(max(s_idx, 0), len(panel_cov) - 1)
    return series.iloc[s_idx]
Dx_t = np.array([daily_lookup(panel_cov["dxy_pct30"], t) for t in t_grid])
T_t  = np.array([daily_lookup(panel_cov["tlt_pct30"], t) for t in t_grid])
# normalize
Dx_t = (Dx_t - np.nanmean(Dx_t)) / (np.nanstd(Dx_t) + 1e-9)
T_t  = (T_t  - np.nanmean(T_t )) / (np.nanstd(T_t ) + 1e-9)
Dx_t = np.nan_to_num(Dx_t); T_t = np.nan_to_num(T_t)

t_train_max = (cutoff_h3 - panel_cov["date"].iloc[0]).days
print(f"\n[hawkes] training window: t=0..{t_train_max} (H3 cutoff)")
print(f"[hawkes] total daily grid: {T_TOTAL} days ({T_TOTAL/365.25:.2f} yrs)")

# ---- Hawkes log-likelihood (exponential kernel) ----
# NLL = -sum log lambda(t_i) + integral_0^T lambda(s) ds
# Assuming train_events event times t_k (sorted), covariates dx,tl on grid
def hawkes_nll(params, t_events, Dx_full, T_full, t_end):
    mu0, mu1, mu2, eta, beta = params
    if eta < 0 or eta >= 0.95: return 1e10
    if beta <= 1e-4: return 1e10
    if mu0 <= 0: return 1e10
    lam_event = np.zeros(len(t_events))
    for i, ti in enumerate(t_events):
        # baseline + covariates at time ti
        lam = mu0 + mu1*Dx_full[int(ti)] + mu2*T_full[int(ti)]
        # sum over past events k < ti
        past = t_events[t_events < ti]
        if len(past) > 0:
            lam += eta*beta*np.sum(np.exp(-beta*(ti - past)))
        if lam <= 1e-12:
            lam = 1e-12
        lam_event[i] = lam
    # integral: piecewise-constant approximation on daily grid 0..t_end
    grid = np.arange(int(t_end) + 1, dtype=int)
    lam_grid = mu0 + mu1*Dx_full[grid] + mu2*T_full[grid]
    # self-exciting integral: for each day d, contribution eta*sum exp(-beta*(d-tk)) for tk<d
    events_in_grid = t_events[t_events <= t_end]
    if len(events_in_grid) > 0:
        for d in grid:
            past = events_in_grid[events_in_grid < d]
            if len(past) > 0:
                lam_grid[d - grid[0]] += eta*beta*np.sum(np.exp(-beta*(d - past)))
    integral = np.sum(lam_grid)
    nll = -np.sum(np.log(lam_event)) + integral
    if not np.isfinite(nll) or nll > 1e12:
        return 1e10
    return nll

# ---- simple coordinate descent / multistart ----
def fit(params0):
    best = None; best_nll = np.inf
    starts = [params0]
    rng = np.random.default_rng(0)
    for _ in range(15):
        starts.append(np.clip(params0 + rng.normal(0, 0.3*params0, size=5),
                              [1e-4]*5, [1.0]*5))
    starts = np.unique(starts, axis=0)
    for s in starts:
        cur = np.array(s, dtype=float)
        # greedy coordinate descent via numerical grad
        step = 0.05 * np.array([1,0.5,0.5,0.05,0.05])
        for it in range(60):
            nll_cur = hawkes_nll(cur, train_events["t_days"].to_numpy(),
                                  Dx_t, T_t, t_train_max)
            grad = np.zeros(5)
            for k in range(5):
                p2 = cur.copy(); p2[k] += step[k]
                n2 = hawkes_nll(p2, train_events["t_days"].to_numpy(),
                                Dx_t, T_t, t_train_max)
                grad[k] = (n2 - nll_cur) / step[k]
            new = cur - 0.05*grad*step
            new = np.clip(new, [1e-4]*5, [2.0]*5)
            nll_new = hawkes_nll(new, train_events["t_days"].to_numpy(),
                                 Dx_t, T_t, t_train_max)
            if nll_new < nll_cur:
                cur = new
            else:
                step *= 0.7
        nll_final = hawkes_nll(cur, train_events["t_days"].to_numpy(),
                                Dx_t, T_t, t_train_max)
        if nll_final < best_nll:
            best_nll = nll_final; best = cur
    return best, best_nll

T1 = time.time()
p0 = np.array([0.0005, 0.0001, 0.0001, 0.3, 0.01])
fit_params, fit_nll = fit(p0)
elapsed = time.time() - T1
mu0, mu1, mu2, eta, beta = fit_params
print(f"\n[hawkes] fit done in {elapsed:.1f}s; train NLL = {fit_nll:.4f}")
print(f"[hawkes] fitted params: mu0={mu0:.5e}, mu1={mu1:.5e}, mu2={mu2:.5e}, "
      f"eta={eta:.4f} (branching ratio, <1=stable), beta={beta:.5f} (1/days)")
print(f"[hawkes] branching ratio eta={eta:.4f} => {'STATIONARY' if eta < 1 else 'NON-STATIONARY'}")

# ---- predict intensity on test window (cutoff_day -> end) ----
cutoff_day = t_train_max
end_day = int(T_TOTAL)
test_days = np.arange(cutoff_day, end_day)
lam_test = np.zeros(len(test_days))
all_train_events = train_events["t_days"].to_numpy()
for d_idx, d in enumerate(test_days):
    lam = mu0 + mu1*Dx_t[d] + mu2*T_t[d]
    past = all_train_events[all_train_events < d]
    if len(past) > 0:
        lam += eta*beta*np.sum(np.exp(-beta*(d - past)))
    lam_test[d_idx] = lam

# pick argmax over rolling 60-day max of lambda (to find a localized peak)
# also smooth via 30-day moving average
lam_smooth = np.convolve(lam_test, np.ones(30)/30, mode="same")
argmax_d_smooth = test_days[np.argmax(lam_smooth)]
pred_date = panel_cov["date"].iloc[0] + pd.Timedelta(days=int(argmax_d_smooth))
print(f"\n[hawkes] predicted intensity peak (smoothed): day {argmax_d_smooth} = {pred_date.date()}")

# compare to observed C4 top
c4_top = pd.Timestamp("2025-10-06")
err_days = (pred_date - c4_top).days
print(f"[hawkes] observed C4 top: 2025-10-06")
print(f"[hawkes] |prediction - actual| = {abs(err_days)} days ({'PASS' if abs(err_days) <= 60 else 'FAIL'} vs ±60d)")
print(f"[hawkes] direction of error: {'LATE' if err_days > 0 else 'EARLY'} by {abs(err_days)}d")

# also check: predict on the C3 final-top 2021-11-10 (was held-out? yes if post cutofff)
c3_final_top = pd.Timestamp("2021-11-10")
c3_tday = (c3_final_top - panel_cov["date"].iloc[0]).days
if c3_tday > cutoff_day and c3_tday < end_day:
    lam_at_c3 = lam_test[c3_tday - cutoff_day]
    print(f"[hawkes] intensity at C3 final-top 2021-11-10: {lam_at_c3:.5e}")
    lam_at_c4 = lam_test[(c4_top - panel_cov["date"].iloc[0]).days - cutoff_day]
    print(f"[hawkes] intensity at C4 top 2025-10-06:     {lam_at_c4:.5e}")

# save lambda trajectory
out = pd.DataFrame({
    "date": panel_cov["date"].iloc[test_days].reset_index(drop=True),
    "lambda": lam_test,
    "lambda_smooth30": lam_smooth,
})
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
outcsv = os.path.join(OUTDIR, f"hawkes_probe_{ts}.csv")
out.to_csv(outcsv, index=False)
print(f"[hawkes] lambda(s) trajectory -> {outcsv}")
print("[hawkes] DONE. interpretation: <60d error => Hawkes captures event-intensity seasonality OOS.")

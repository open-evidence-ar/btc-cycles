"""
Noisy phase-locked oscillator probe — "halving as magnetic compass with
liquidity-modulated noise."

Model:
  S(theta)   = sin(pi*theta)               deterministic calendar signal
  theta(t)   = (t - t_halving) / 1460      phase relative to halving
  Y(t)       = S(theta(t)) + eps(t)         where eps ~ N(0, sigma^2(t))
  sigma(t)   = sigma0 + sigma1*L(t)         L = liquidity-stress
                (DXY 365d z-score from build_regime_robustness.py)

Three falsifiable predictions tested jointly on existing repo data:
  P1: Fraction of extreme-return weeks in phase window theta~[0.32,0.42]
      is HIGHER in low-stress regime than high-stress regime.
  P2: Variance of detrended log-price in phase window is HIGHER in
      high-stress regime than low-stress (noise variance scales w/ stress).
  P3: Observed C4 top lies inside predicted window when conditionally
      gated by regime; C4 actual = 2025-10-06; loose regime window
      (low DXY) = H4+[600d, 1100d].

Pure numpy/pandas. Output: stdout + /tmp/noisy_oscillator_<ts>.csv only.
"""
import numpy as np
import pandas as pd
import os, time
from datetime import datetime

REPO = r"D:\trading"
RAW = os.path.join(REPO, "data", "processed", "returns_aligned.csv")
EV  = os.path.join(REPO, "data", "events.csv")
OUTDIR = r"C:\Users\German\AppData\Local\Temp\opencode"
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_csv(RAW); ev = pd.read_csv(EV)
df["date"] = pd.to_datetime(df["date"]); ev["date"] = pd.to_datetime(ev["date"])

# halving dates
halvings = {}
for _, r in ev.iterrows():
    if r["event_type"] == "halving":
        halvings[r["cycle_id"]] = r["date"]
H1,H2,H3,H4,H5 = halvings["H1"], halvings["H2"], halvings["H3"], halvings["H4"], halvings["H5"]
print(f"[osc] halvings: H1={H1.date()} H2={H2.date()} H3={H3.date()} H4={H4.date()} H5={H5.date()}")

# pick BTC close series (the carrier signal we model)
btc = df[["date","btc_close","cycle_id","days_from_halving"]].dropna().sort_values("date").reset_index(drop=True)
btc["days_since_start"] = (btc["date"] - btc["date"].iloc[0]).dt.days

# ---- liquidity stress index: DXY 365d z-score (mirrors build_regime_robustness.py) ----
dxy = df[["date","dxy_close"]].dropna().sort_values("date").reset_index(drop=True)
dxy["dxy_mean_365"] = dxy["dxy_close"].rolling(365, min_periods=180).mean()
dxy["dxy_std_365"]  = dxy["dxy_close"].rolling(365, min_periods=180).std()
dxy["dxy_z"] = (dxy["dxy_close"] - dxy["dxy_mean_365"]) / dxy["dxy_std_365"]

# regime classification (high/low/normal)
dxy["regime"] = "normal"
dxy.loc[dxy["dxy_z"] > 1.0, "regime"] = "high"   # tight liquidity (high DXY)
dxy.loc[dxy["dxy_z"] < -1.0, "regime"] = "low"  # loose liquidity (low DXY)

# merge regime into btc
btc = btc.merge(dxy[["date","dxy_z","regime"]], on="date", how="left")
btc["regime"] = btc["regime"].fillna("normal")

# ---- deterministic phase variable theta(t) per cycle ----
# phase relative to each asset's own halving; theta=0 at halving, theta=0.5 at +730d
THETA_TOP_EXPECTED = 0.36   # ~526d after halving / 1460d cycle (C2 = H2->T2=526d)
THETA_WIN = 0.0275          # roughly +-60d in phase units (=60/2180d typical cycle)
HALVING_BY_CYCLE = {"C1": H1, "C2": H2, "C3": H3, "C4": H4}
CYCLE_LENGTH_DAYS = 1460
def phase_theta(row):
    h = HALVING_BY_CYCLE.get(row["cycle_id"], pd.NaT)
    return (row["date"] - h).days / CYCLE_LENGTH_DAYS
btc["theta"] = btc.apply(phase_theta, axis=1)
btc["theta_pos"] = btc["theta"].where(btc["theta"] >= 0)  # only post-halving phase matters

# ---- P1: fraction of extreme-return weeks falling in phase window, by regime ----
btc["btc_lr_w7d"] = np.log(btc["btc_close"]).diff(7)
abs_lr = btc["btc_lr_w7d"].abs()
# define extreme weeks: top decile from the full sample, OR similarly |lr|>2*sigma
extreme_threshold = abs_lr.quantile(0.90)
extreme_mask = abs_lr >= extreme_threshold
print(f"[osc] extreme-return threshold |weekly log return| >= {extreme_threshold:.3f}, hits {extreme_mask.sum()} weeks")

# define phase-window flag: |theta - THETA_TOP_EXPECTED| <= THETA_WIN  (only in positive theta)
def in_top_phase_window(theta):
    return pd.notna(theta) and abs(theta - THETA_TOP_EXPECTED) <= THETA_WIN
btc["in_top_win"] = btc["theta_pos"].apply(in_top_phase_window)

# cross-tab by regime
regimes = ["high","normal","low"]
print("\n[osc] P1 -- extreme-week fraction in top phase window, by liquidity regime:")
print(f"{'regime':<8} {'total_wks':<11} {'extreme_wks':<14} {'extremes_in_win':<18} {'fraction':<10}")
p1_results = {}
for rg in regimes:
    sub = btc[btc.regime == rg]
    n_total = len(sub)
    n_extremes = extreme_mask[sub.index].sum()
    n_extremes_in_win = (extreme_mask[sub.index] & sub["in_top_win"]).sum()
    # random-at-best we expect extremes to be uniformly distributed over phases (so we should fraction-of-time-in-window as the baseline)
    n_in_win = sub["in_top_win"].sum()
    baseline_rate = n_in_win / max(n_total, 1)
    extreme_hit_rate = n_extremes_in_win / max(n_extremes, 1)
    enrichment = extreme_hit_rate / max(baseline_rate, 1e-9)
    p1_results[rg] = {"n_total":n_total, "n_extremes":n_extremes, "n_in_win":n_in_win,
                       "n_extremes_in_win":n_extremes_in_win,
                       "baseline_rate":baseline_rate, "extreme_hit_rate":extreme_hit_rate,
                       "enrichment":enrichment}
    print(f"{rg:<8} {n_total:<11} {n_extremes:<14} {n_extremes_in_win:<18} extreme_hit={extreme_hit_rate:.3f}  baseline={baseline_rate:.3f}  ENRICHMENT={enrichment:.2f}x")
print("\n[osc]   enrichment > 1 => phase window concentrates extremes beyond random expectation")
print("[osc]   model predicts LOW (loose liquidity) should HIGHER enrichment than HIGH (tight liquidity)")

# ---- P2: noise variance in phase window, by regime ----
# detrended log-price residual: ln(P(t)) - linear fit on ln(P) per cycle
detrended = []
for cid, sub in btc.groupby("cycle_id"):
    if len(sub) < 10:
        detrended.extend([np.nan]*len(sub)); continue
    x = sub["days_since_start"].to_numpy(float)
    y = np.log(sub["btc_close"].to_numpy(float))
    A = np.vstack([x, np.ones_like(x)]).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    detrended.extend((y - A @ coef))
btc["detrended_ln_P"] = detrended
btc = btc.reset_index(drop=True)

# variance of detrended price signal within top-phase window, by regime
print("\n[osc] P2 -- noise variance (detrended log P) in top-phase window by regime:")
print(f"{'regime':<8} {'n_in_win':<11} {'var(detrended)':<20}")
for rg in regimes:
    sub = btc[(btc.regime == rg) & (btc["in_top_win"])]
    if len(sub) >= 5:
        v = sub["detrended_ln_P"].var(ddof=1)
        print(f"{rg:<8} {len(sub):<11} {v:<20.6f}")
    else:
        print(f"{rg:<8} {len(sub):<11} {'too few':<20}")
print("[osc]   model predicts HIGH > LOW (noise variance scales with liquidity stress)")

# ---- P3: regime-conditioned calendar prediction for C4 top ----
# C4 top window: H4 + [600d, 1100d], narrower if regime stays low-stress through it
c4_win_loose = (H4 + pd.Timedelta(days=600), H4 + pd.Timedelta(days=1100))
c4_win_tight = (H4 + pd.Timedelta(days=900), H4 + pd.Timedelta(days=1500))  # nominal broad baseline un-windowed
c4_actual = pd.Timestamp("2025-10-06")
print(f"\n[osc] P3 -- regime-conditioned calendar prediction for C4 top:")
print(f"[osc]   H4 = {H4.date()}; observed C4 top = {c4_actual.date()} = +{(c4_actual-H4).days}d")
print(f"[osc]   loose liquidity window (H4+[600,1100]d): {c4_win_loose[0].date()} to {c4_win_loose[1].date()}")
print(f"[osc]   tight liquidity window (H4+[900,1500]d): {c4_win_tight[0].date()} to {c4_win_tight[1].date()}")

# classify the *current* regime at H4 and through the loose window
def regime_at(date):
    pos = dxy["date"].searchsorted(date, side="right") - 1
    if pos < 0 or pos >= len(dxy): return "normal", np.nan
    return dxy["regime"].iloc[pos], dxy["dxy_z"].iloc[pos]
rg_h4, z_h4 = regime_at(H4)
rg_at_loose_mid, z_at_loose_mid = regime_at(H4 + pd.Timedelta(days=850))  # mid of loose window
print(f"[osc]   DXY regime at H4 ({H4.date()}): {rg_h4} (z={z_h4:.2f})")
print(f"[osc]   DXY regime at H4+850d (loose-window mid): {rg_at_loose_mid} (z={z_at_loose_mid:.2f})")

in_loose = c4_win_loose[0] <= c4_actual <= c4_win_loose[1]
in_tight = c4_win_tight[0] <= c4_actual <= c4_win_tight[1]
print(f"[osc]   C4 actual in LOOSE window:   {in_loose}")
print(f"[osc]   C4 actual in TIGHT window:    {in_tight}")
days_post_h4 = (c4_actual - H4).days
print(f"[osc]   C4 actual at +{days_post_h4}d after H4")
# interpret
print(f"\n[osc] P3 INTERPRETATION:")
if rg_at_loose_mid == "low":
    print(f"[osc]   -> regime through mid-2024 was LOOSE (DXY<-1sigma)")
    print(f"[osc]   -> model predicts top in {c4_win_loose[0].date()}..{c4_win_loose[1].date()} (600-1100d post-halving)")
    print(f"[osc]   -> observed {c4_actual.date()} at +{days_post_h4}d")
    print(f"[osc]   -> P3 PASS: {in_loose}")
elif rg_at_loose_mid == "high":
    print(f"[osc]   -> regime through mid-2024 was TIGHT (DXY>+1sigma)")
    print(f"[osc]   -> model predicts a delayed/noisy top with broader uncertainty")
    print(f"[osc]   -> observed +{days_post_h4}d (near loose-upper-bound)")
    print(f"[osc]   -> P3 counter-reading: TIGHT regime -> top delayed and currently inside TIGHT window {c4_win_tight[0].date()}-{c4_win_tight[1].date()}: {in_tight}")
else:
    print(f"[osc]   -> regime through mid-2024 was NORMAL (|z|<=1)")
    print(f"[osc]   -> model predicts top in nominal cycle window +/- stress adjustment")
    print(f"[osc]   -> observed {c4_actual.date()} at +{days_post_h4}d")
    print(f"[osc]   -> P3 PASS (nominal window): {in_loose}")

# save artifacts
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
outcsv = os.path.join(OUTDIR, f"noisy_oscillator_{ts}.csv")
btc[["date","cycle_id","btc_close","dxy_z","regime","theta","theta_pos","in_top_win","btc_lr_w7d","detrended_ln_P"]].to_csv(outcsv, index=False)
print(f"\n[osc] per-day table -> {outcsv}")
print("[osc] DONE.")

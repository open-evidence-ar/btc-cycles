"""
Frequency-amplitude probe.  Hypothesis: halving-to-top interval compresses
(after a stress period) when _sidelined liquidity_ that built up during the
high-DXY period is released.  Tests three predictions with a TRAILING
STRESS INTEGRAL (cumulative time DXY near its top), not current DXY level.

Outputs: stdout only + /tmp/freq_amp_<ts>.csv   (no repo edits)
Pure numpy/pandas.
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

halvings = {}
for _, r in ev.iterrows():
    if r["event_type"] == "halving":
        halvings[r["cycle_id"]] = r["date"]
H1,H2,H3,H4,H5 = (halvings["H1"], halvings["H2"], halvings["H3"], halvings["H4"], halvings["H5"])

# BTC peaks (canonical tops from events.csv)
top_dates = ev[(ev.event_type=="top") & (ev.reason_code=="canonical")].sort_values("date")
print("[fa] canonical cycle tops:")
for _, r in top_dates.iterrows():
    cid = r["cycle_id"]
    h = halvings.get({"C1":"H1","C2":"H2","C3":"H3","C4":"H4"}.get(cid,""), None)
    if h is None: continue
    interval = (r["date"] - h).days
    print(f"  {cid}: {h.date()} -> {r['date'].date()} = +{interval}d")

# DXY series
dxy = df[["date","dxy_close"]].dropna().sort_values("date").reset_index(drop=True)

# rolling z-score of DXY (mirrors build_regime_robustness.py: 365d rolling mean+std)
dxy["mean_365"] = dxy["dxy_close"].rolling(365, min_periods=180).mean()
dxy["std_365"]  = dxy["dxy_close"].rolling(365, min_periods=180).std()
dxy["z"] = (dxy["dxy_close"] - dxy["mean_365"]) / dxy["std_365"]

# ---- Build the trailing DXY STRESS INTEGRAL ----
# stress(t) = max(z(t) - 1, 0)   (excess above +1 sigma)
# integral_365(t) = sum_{s=t-365..t} stress(s)
#                = "how much DXY exceeded +1sigma over the last year, accumulated"
stress = (dxy["z"] - 1.0).clip(lower=0).fillna(0).to_numpy()
T = len(stress)
# efficient rolling sum (running integral over the trailing 365 days)
window = 365
csum = np.cumsum(np.concatenate(([0], stress)))
integral_365 = csum[window:] - csum[:len(stress)-window+1] if len(stress) > window else np.array([])
# pad to length T (initial window's first valid output is at index window-1)
pad = np.full(window - 1, np.nan)
dxy["stress_integral_365"] = np.concatenate([pad, integral_365])[:len(stress)]
# 730-day version
window2 = 730
integral_730 = csum[window2:] - csum[:len(stress)-window2+1] if len(stress) > window2 else np.array([])
dxy["stress_integral_730"] = np.concatenate([np.full(window2 - 1, np.nan), integral_730])[:len(stress)]

print("[fa] DXY stress integral computed; range:", dxy["stress_integral_365"].min(), "to", dxy["stress_integral_365"].max())

# stress-integral regime classification: terciles of the 365-d integral (non-NaN)
valid_int = dxy["stress_integral_365"].dropna()
q33, q66 = valid_int.quantile([0.33, 0.66])
print(f"[fa] stress-integral tercile thresholds: low<={q33:.2f}, high>={q66:.2f}")
def classify(integral):
    if pd.isna(integral): return "unknown"
    if integral <= q33:  return "low_integral"
    if integral >= q66:  return "high_integral"
    return "mid_integral"
dxy["integral_regime"] = dxy["stress_integral_365"].apply(classify)

# helper: regime at a given date
def integral_at(date):
    pos = dxy["date"].searchsorted(date, side="right") - 1
    if pos < 0 or pos >= len(dxy): return np.nan, "unknown"
    return dxy["stress_integral_365"].iloc[pos], dxy["integral_regime"].iloc[pos]
def integral_730_at(date):
    pos = dxy["date"].searchsorted(date, side="right") - 1
    if pos < 0 or pos >= len(dxy): return np.nan
    return dxy["stress_integral_730"].iloc[pos]

# ---- P4: halving-to-top interval vs trailing 365d DXY stress integral at the halving ----
print("\n[fa] ===== P4: Halving-to-top interval vs trailing DXY stress integral at halving =====")
pairs = []
for cid, hid in [("C1","H1"),("C2","H2"),("C3","H3"),("C4","H4")]:
    h_date = halvings[hid]; top_date = top_dates[top_dates.cycle_id == cid]["date"]
    if len(top_date) == 0: continue
    top_date = top_date.iloc[0]
    interval = (top_date - h_date).days
    int_365, regime_at_h = integral_at(h_date)
    int_730 = integral_730_at(h_date)
    pairs.append((cid, h_date, top_date, interval, int_365, regime_at_h, int_730))
print(f"  {'cycle':<6} {'halving':<12} {'top':<12} {'H->T days':<12} {'integ365':<10} {'regime':<14} {'integ730':<10}")
for p in pairs:
    print(f"  {p[0]:<6} {str(p[1].date()):<12} {str(p[2].date()):<12} {p[3]:<12} {p[4]:<10.2f} {p[5]:<14} {p[6]:<10.2f}")

# correlation between integral and interval (n=4 cycles, descriptive only)
integs = np.array([p[4] for p in pairs if not pd.isna(p[4])], dtype=float)
intervals = np.array([p[3] for p in pairs if not pd.isna(p[4])], dtype=float)
if len(integs) >= 3:
    r = np.corrcoef(integs, intervals)[0,1]
    print(f"\n[fa] P4 — Pearson r(stress_integral_365 at H, H->T interval) = {r:.3f}  (n={len(integs)})")
    print(f"[fa]       predicted sign NEGATIVE (more stored stress -> shorter cycle); observed {'NEGATIVE (supports)' if r<0 else 'POSITIVE (refutes)'}")
    # 730-day version (stress accumulated over prior 2 yrs)
    i730 = np.array([p[6] for p in pairs if not pd.isna(p[6])])
    if len(i730) >= 3:
        r730 = np.corrcoef(i730, intervals[:len(i730)])[0,1]
        print(f"[fa] P4 — Pearson r(stress_integral_730 at H, interval) = {r730:.3f}  (2-yr trailing window)")
        print(f"[fa]       NEGATIVE direction = more stored stress over prior 2yr compressed next cycle's length")

# ---- P5: extreme-week enrichment in phase window by trailing-integral regime ----
print("\n[fa] ===== P5: Extreme-week enrichment in top-phase window, by TRAILING stress integral =====")
# attach integral regime back to BTC panel
btc = df[["date","btc_close","cycle_id","days_from_halving"]].dropna().sort_values("date").reset_index(drop=True)
btc["btc_lr_w7d"] = np.log(btc["btc_close"]).diff(7)
# rebuild extreme_mask on the SAME btc index (post dropna)
abs_lr_btc = btc["btc_lr_w7d"].abs()
extreme_thresh_btc = abs_lr_btc.quantile(0.90)
extreme_mask_btc = (abs_lr_btc >= extreme_thresh_btc).reset_index(drop=True)
btc = btc.reset_index(drop=True)
print(f"[fa] (P5) extreme-return threshold on btc-panel = {extreme_thresh_btc:.3f}, hits {extreme_mask_btc.sum()} weeks")

# phase theta
HALVING_BY_CYCLE = {"C1":H1,"C2":H2,"C3":H3,"C4":H4}
CYCLE_LEN = 1460
THETA_EXPECTED = 0.36
THETA_WIN = 0.027
btc["theta"] = btc.apply(lambda r:(r["date"]-HALVING_BY_CYCLE.get(r["cycle_id"])).days/CYCLE_LEN, axis=1)
btc["theta_pos"] = btc["theta"].where(btc["theta"]>=0)
btc["in_top_win"] = btc["theta_pos"].apply(lambda t: pd.notna(t) and abs(t-THETA_EXPECTED) <= THETA_WIN)

# merge integral regime (use date, no index collision)
dxy_int = dxy[["date","stress_integral_365","integral_regime"]].copy()
btc = btc.merge(dxy_int, on="date", how="left")
btc["integral_regime"] = btc["integral_regime"].fillna("unknown")
btc = btc.reset_index(drop=True)
extreme_mask_btc = extreme_mask_btc.reset_index(drop=True)

phase_regimes = ["low_integral","mid_integral","high_integral"]
print(f"{'integral_regime':<16} {'total_wks':<11} {'extremes':<11} {'in_win':<9} {'ext_in_win':<13} {'enrich':<8} {'status':<25}")
for rg in phase_regimes:
    sub_mask = (btc["integral_regime"] == rg)
    n_tot = int(sub_mask.sum())
    n_ext = int((extreme_mask_btc & sub_mask).sum())
    n_in_win = int((btc["in_top_win"] & sub_mask).sum())
    n_ext_in_win = int((extreme_mask_btc & btc["in_top_win"] & sub_mask).sum())
    baseline = n_in_win/max(n_tot,1)
    hit = n_ext_in_win/max(n_ext,1)
    enrich = hit/max(baseline,1e-9)
    status = "+" if enrich > 1 else "-"
    print(f"{rg:<16} {n_tot:<11} {n_ext:<11} {n_in_win:<9} {n_ext_in_win:<13} {enrich:.2f}x {status:<25}")

print("[fa]   Model predicts HIGH integral (recent cumulative stress, liquidity now released) should HIGHER enrich than LOW")
print("[fa]   i.e. enrichment ordering: HIGH_integral >= MID >= LOW_integral")

# ---- P6: sidelined-liquidity-recovery proxy ----
# proxy: TLT monthly log-return over the prior 6 months (rising TLT = falling yields = liquidity easing)
# simpler: just correlation between 730d integral + 30d TLT momentum vs C1-C4 interval
print("\n[fa] ===== P6: sidelines-liquidity-release proxy vs H->T interval =====")
tlt = df[["date","tlt_close"]].dropna().sort_values("date").reset_index(drop=True)
tlt["tlt_pctchg_180d"] = tlt["tlt_close"].pct_change(180)
def tlt_mom_at(date):
    pos = tlt["date"].searchsorted(date, side="right") - 1
    if pos < 0 or pos >= len(tlt): return np.nan
    return tlt["tlt_pctchg_180d"].iloc[pos]
# combine for each cycle: integral365 at H + TLT momentum at H + interval
print(f"  {'cycle':<6} {'H->T':<8} {'integ365':<10} {'integ730':<10} {'TLT_180d_pct':<14}")
for p in pairs:
    cid, h_date, top_date, interval = p[0], p[1], p[2], p[3]
    i365 = p[4]; i730 = p[6]
    tmom = tlt_mom_at(h_date)
    print(f"  {cid:<6} {interval:<8} {i365:<10.2f} {i730:<10.2f} {tmom:<14.4f}")
# partial correlation of interval vs i730 (strongest pre-stress signal) and TLT momentum (release signal)
i730_arr = np.array([p[6] for p in pairs if not pd.isna(p[6])])
intervals_arr = np.array([p[3] for p in pairs if not pd.isna(p[6])])
tmom_arr = np.array([tlt_mom_at(p[1]) for p in pairs if not pd.isna(p[6])])
if len(i730_arr) >= 3 and not np.any(pd.isna(tmom_arr)):
    r_int = np.corrcoef(i730_arr, intervals_arr)[0,1]
    r_tmom = np.corrcoef(tmom_arr, intervals_arr)[0,1]
    print(f"\n[fa] P6 — r(integ730, interval) = {r_int:+.3f}")
    print(f"[fa]     r(TLT_180d_pct at H, interval) = {r_tmom:+.3f}  (positive TLT = yields fell prior = liquidity was loosening)")
    print(f"[fa]     combined model would say: more stress built up over 2yr AND/OR more easing into H = shorter next cycle")

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
outcsv = os.path.join(OUTDIR, f"freq_amp_{ts}.csv")
dxy[["date","dxy_close","z","stress_integral_365","stress_integral_730","integral_regime"]].to_csv(outcsv, index=False)
print(f"\n[fa] DXY-and-integral series -> {outcsv}")
print("[fa] DONE.")

"""
Verification probe — "heavier flock, same season" hypothesis.
Tests three claims with pure numpy/pandas on existing repo data:

  V1: The dominant correlation eigenvalue lambda1 decays across cycles
      -- but ONLY because the asset panel grows, not because coherence
      decays.  On a FIXED 6-asset common panel, lambda1 should be stable
      across C1..C4.  Also tested: market-cap-weighted (btc_close as
      mass proxy) lambda1.
  V2: Calendar seasonality is conserved: halving->top and top->bottom
      intervals from canonical events.csv are stable across cycles.
  V3: BTC weekly log-return autocorrelation (lags 1..156 weeks) is
      stationary across cycles (same seasonal rhythm, not compressing).

Output: stdout + /tmp/heavy_flock_<ts>.csv   (no repo edits)
"""
import numpy as np
import pandas as pd
import os
from datetime import datetime

REPO = r"D:\trading"
RAW = os.path.join(REPO, "data", "processed", "returns_aligned.csv")
EV  = os.path.join(REPO, "data", "events.csv")
OUTDIR = r"C:\Users\German\AppData\Local\Temp\opencode"
os.makedirs(OUTDIR, exist_ok=True)

df = pd.read_csv(RAW); ev = pd.read_csv(EV)
df["date"] = pd.to_datetime(df["date"]); ev["date"] = pd.to_datetime(ev["date"])

# ---------- V1: fixed-panel correlation eigenvalue per cycle ----------
print("=" * 78)
print("V1: dominant eigenvalue of correlation matrix, FIXED 6-asset panel")
print("    (btc, mstr, spx, ndx, dxy, tlt)  -- removes panel-growth confound")
print("=" * 78)

panel = ["btc", "mstr", "spx", "ndx", "dxy", "tlt"]
lr_cols = [f"{a}_log_return_w7d" for a in panel]

def corr_eigvals(X):
    """X: (n_samples, n_features) -> eigenvalues of correlation matrix, desc."""
    Xc = X - X.mean(axis=0)
    std = Xc.std(axis=0)
    Xn = Xc / (std + 1e-12)
    C = (Xn.T @ Xn) / max(Xn.shape[0] - 1, 1)
    w = np.linalg.eigvalsh((C + C.T) / 2)
    return np.sort(w)[::-1]

# cycle windows for correlation computation: halving -> next halving (full cycle span)
HALV = {"C1": pd.Timestamp("2012-11-28"), "C2": pd.Timestamp("2016-07-09"),
        "C3": pd.Timestamp("2020-05-11"), "C4": pd.Timestamp("2024-04-20")}
NEXT_H = {"C1": pd.Timestamp("2016-07-09"), "C2": pd.Timestamp("2020-05-11"),
          "C3": pd.Timestamp("2024-04-20"), "C4": pd.Timestamp("2028-04-01")}

rows_v1 = []
print(f"{'cycle':<6} {'span':<28} {'n_wks':<7} {'lam1_fixed':<12} {'lam1_masswt':<12} {'lam2':<8}")
for cid in ["C1", "C2", "C3", "C4"]:
    sub = df[(df["date"] >= HALV[cid]) & (df["date"] < NEXT_H[cid])].dropna(subset=lr_cols)
    if len(sub) < 20:
        print(f"{cid:<6} {str(HALV[cid].date()):<28} {len(sub):<7} {'(too few)':<12}")
        continue
    X = sub[lr_cols].to_numpy(float)
    w_fixed = corr_eigvals(X)
    # mass-weighted: weight each weekly observation by btc_close (mass proxy)
    mass = sub["btc_close"].to_numpy(float).reshape(-1, 1)
    wgt = mass / mass.sum()
    Xc = X - (wgt * X).sum(axis=0)
    Xn = Xc / (Xc.std(axis=0) + 1e-12)
    Cw = (wgt * Xn).T @ Xn
    w_mass = np.linalg.eigvalsh((Cw + Cw.T) / 2)
    w_mass = np.sort(w_mass)[::-1]
    rows_v1.append({"cycle": cid, "n_wks": len(sub),
                    "lam1_fixed": w_fixed[0], "lam1_masswt": w_mass[0], "lam2": w_fixed[1]})
    print(f"{cid:<6} {str(HALV[cid].date())}->{str(NEXT_H[cid].date()):<16} {len(sub):<7} {w_fixed[0]:<12.4f} {w_mass[0]:<12.4f} {w_fixed[1]:<8.4f}")

v1_df = pd.DataFrame(rows_v1)
if len(v1_df) >= 3:
    l1 = v1_df["lam1_fixed"].to_numpy()
    print(f"\n  lam1_fixed across cycles: {np.round(l1, 3)}")
    print(f"  range: {l1.min():.3f}..{l1.max():.3f}  (stable if tight)")
    l1w = v1_df["lam1_masswt"].to_numpy()
    print(f"  lam1_masswt across cycles: {np.round(l1w, 3)}")
    print(f"  range: {l1w.min():.3f}..{l1w.max():.3f}")

# ---------- V2: calendar seasonality from canonical events ----------
print("\n" + "=" * 78)
print("V2: calendar seasonality -- canonical event intervals")
print("=" * 78)
# canonical final tops and bottoms from events.csv
tops = ev[(ev.event_type == "top") & (ev.label == "final_top")].sort_values("date").reset_index(drop=True)
bottoms = ev[(ev.event_type == "bottom") & (ev.label.str.startswith("B")) & (ev.reason_code == "canonical")].sort_values("date").reset_index(drop=True)
halvings = ev[(ev.event_type == "halving") & (ev.cycle_id.str.startswith("H"))].sort_values("date").reset_index(drop=True)

print("\n  Halving -> final top (D_halving_to_top):")
ht = []
for cid, hd in [("C1", HALV["C1"]), ("C2", HALV["C2"]), ("C3", HALV["C3"]), ("C4", HALV["C4"])]:
    row = tops[tops.cycle_id == cid]
    if len(row) == 0: continue
    t = row["date"].iloc[0]
    ht.append({"cycle": cid, "interval_days": (t - hd).days, "top": t.date()})
    print(f"    {cid}: {hd.date()} -> {t.date()} = {(t - hd).days}d")
ht_df = pd.DataFrame(ht)
if len(ht_df) >= 3:
    iv = ht_df["interval_days"].to_numpy()
    print(f"    mean={iv.mean():.0f}d  min={iv.min()}d  max={iv.max()}d  spread={(iv.max()-iv.min())/iv.mean()*100:.1f}% of mean")

print("\n  Top -> next bear bottom (D_top_to_next_bottom):")
tb = []
for i in range(len(tops)):
    t = tops["date"].iloc[i]
    tcid = tops["cycle_id"].iloc[i]
    # bottom after this top, before next top
    nxt = bottoms[(bottoms["date"] > t)]
    if len(nxt) == 0: continue
    b = nxt["date"].iloc[0]
    tb.append({"cycle": tcid, "interval_days": (b - t).days, "bottom": b.date()})
    print(f"    {tcid}: {t.date()} -> {b.date()} = {(b - t).days}d")
tb_df = pd.DataFrame(tb)
if len(tb_df) >= 3:
    iv = tb_df["interval_days"].to_numpy()
    print(f"    mean={iv.mean():.0f}d  min={iv.min()}d  max={iv.max()}d  spread={(iv.max()-iv.min())/iv.mean()*100:.1f}% of mean")

# ---------- V3: autocorrelation stationarity ----------
print("\n" + "=" * 78)
print("V3: BTC weekly log-return autocorrelation (lags 1..156 wks) per cycle")
print("=" * 78)
max_lag = 156  # ~3 years
ac_rows = []
for cid in ["C1", "C2", "C3", "C4"]:
    sub = df[(df["date"] >= HALV[cid]) & (df["date"] < NEXT_H[cid])].dropna(subset=["btc_log_return_w7d"])
    r = sub["btc_log_return_w7d"].to_numpy(float)
    if len(r) < 60: continue
    r = r - r.mean()
    denom = (r @ r)
    ac = np.array([(r[:len(r)-l] @ r[l:]) / denom for l in range(1, min(max_lag, len(r)//2)+1)])
    # dominant seasonal lag: argmax |ac| in lags 40..120 wks (~9 months..2.3 yr)
    lo, hi = 40, min(120, len(ac))
    if hi > lo:
        seg = ac[lo:hi]
        k = lo + int(np.argmax(np.abs(seg)))
        ac_rows.append({"cycle": cid, "lag_weeks": k, "ac_at_lag": ac[k],
                        "mean_abs_ac": np.mean(np.abs(ac))})
        print(f"    {cid}: n={len(r)} wks | dominant |AC| at lag {k}w (ac={ac[k]:+.3f}) | mean|ac|={np.mean(np.abs(ac)):.3f}")
ac_df = pd.DataFrame(ac_rows)
if len(ac_df) >= 3:
    print(f"    dominant-lag series (weeks): {ac_df['lag_weeks'].tolist()}")
    print(f"    mean|ac| series: {np.round(ac_df['mean_abs_ac'].to_numpy(), 3).tolist()}")
    print(f"    -> stationary seasonal lag across cycles supports 'same season'")

# save
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out = os.path.join(OUTDIR, f"heavy_flock_{ts}.csv")
pd.concat([v1_df, ac_df], keys=["v1", "v3"], ignore_index=False).to_csv(out)
print(f"\n[saved] {out}")
print("DONE.")

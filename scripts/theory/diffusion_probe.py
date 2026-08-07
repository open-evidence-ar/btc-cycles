"""
Exploratory diffusion-map probe — READ ONLY on repo data.
Output: stdout + /tmp/diffusion_probe_<ts>.csv only.
Nothing written into repo/. Answer whether a diffusion-map embedding of
the asset panel can auto-recover the DESIGN.md P1-P4 phase labels (ARI)
and whether the Markov spectral gap spikes near Rule T/B extrema.
Uses LANDMARK diffusion maps (Coifman/Nosteraf etc.) so runtime is ~seconds.
"""
import numpy as np
import pandas as pd
import time, os
from datetime import datetime

REPO = r"D:\trading"
RAW = os.path.join(REPO, "data", "processed", "returns_aligned.csv")
EV  = os.path.join(REPO, "data", "events.csv")
OUTDIR = r"C:\Users\German\AppData\Local\Temp\opencode"
os.makedirs(OUTDIR, exist_ok=True)

# ---- 1. load ----
df = pd.read_csv(RAW)
ev = pd.read_csv(EV)
df["date"] = pd.to_datetime(df["date"])
ev["date"] = pd.to_datetime(ev["date"])

halvings = {}
for _, r in ev.iterrows():
    if r["event_type"] == "halving" and pd.notna(r.get("cycle_id")) and str(r["cycle_id"]).startswith("H"):
        halvings[r["cycle_id"]] = r["date"]

# 6-asset common panel (btc, mstr, spx, ndx, dxy, tlt) — all present since ~2013
panel = ["btc", "mstr", "spx", "ndx", "dxy", "tlt"]
feat_cols = [f"{a}_log_return_w7d" for a in panel]

sub = df[["cycle_id", "days_from_halving", "date"] + feat_cols].copy()
sub = sub.dropna(subset=feat_cols).sort_values("date").reset_index(drop=True)

# ---- 2. phase labels (mirrors build_regime_robustness.py assign_phase) ----
cycle_ids_all = ["C1", "C2", "C3", "C4"]
HALVING_ORDER = ["H1", "H2", "H3", "H4", "H5"]
p4_upper = {}
for i, cid in enumerate(cycle_ids_all):
    this_h = HALVING_ORDER[i]; next_h = HALVING_ORDER[i + 1]
    if this_h in halvings and next_h in halvings:
        p4_upper[cid] = (halvings[next_h] - halvings[this_h]).days
    else:
        p4_upper[cid] = 1500

def assign_phase(row):
    d = row["days_from_halving"]; cid = row["cycle_id"]
    if -540 < d <= 0:      return "P1"
    if  0 < d <= 270:      return "P2"
    if 270 < d <= 540:     return "P3"
    if 540 < d <= p4_upper.get(cid, 1500): return "P4"
    return None

sub["phase"] = sub.apply(assign_phase, axis=1)
sub = sub.dropna(subset=["phase"]).copy()
print(f"[probe] common-panel rows (6-asset, phase-labelled): {len(sub)}")
print("[probe] cycles:", sub.cycle_id.unique().tolist())
print("[probe] phase counts:\n", sub.phase.value_counts())

# ---- 3. LANDMARK diffusion map (Nyström) ----
# Landmark at the first occurrence of each days_from_halving grid value across cycles.
grid = sub["days_from_halving"].to_numpy()
seen = set(); landmark_idx = []
for gi, g in enumerate(grid):
    if g not in seen:
        landmark_idx.append(gi); seen.add(g)
landmark_idx = np.array(landmark_idx)
Xl = sub[feat_cols].to_numpy()[landmark_idx]
X_all = sub[feat_cols].to_numpy()

T1 = time.time()
d2L = np.square(np.linalg.norm(Xl[:,None] - Xl[None,:], axis=2))
eps = np.median(d2L[np.triu_indices(len(Xl), k=1)])
eps = eps if eps > 0 else 1.0
KL = np.exp(-d2L / eps); degL = KL.sum(1); PL = KL / degL[:, None]
wl, VL = np.linalg.eigh((PL+PL.T)/2); j = np.argsort(wl)[::-1]; wl, VL = wl[j], VL[:, j]
print(f"[probe] landmark eigendecomp done in {time.time()-T1:.2f}s; top-6 eigenvalues:", np.round(wl[:6],4))

# Nyström-extend landmarks->all rows
d2A = np.square(np.linalg.norm(X_all[:,None,:] - Xl[None,:,:], axis=2))  # T x N
KA = np.exp(-d2A / eps); degA = KA.sum(1); PA = KA / degA[:, None]
n_coords = 3
Psi = np.zeros((len(X_all), n_coords))
for k in range(1, n_coords+1):
    Psi[:, k-1] = PA @ VL[:, k] / wl[k]
Psi = Psi / (Psi.std(axis=0) + 1e-12)

# ---- 4. k-means k=4 (no label leakage) ----
def kmeans(X, k, iters=300, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), k, replace=False)].copy()
    for _ in range(iters):
        d = np.linalg.norm(X[:,None,:] - C[None,:,:], axis=2)
        asg = d.argmin(1)
        new = np.array([X[asg==c].mean(0) if np.any(asg==c) else C[c] for c in range(k)])
        if np.allclose(new, C, atol=1e-9): break
        C = new
    return asg

asg = kmeans(Psi, 4, seed=1)
sub = sub.reset_index(drop=True).copy(); sub["cluster"] = asg

# ---- 5. adjusted Rand index (pure numpy) ----
def ari(lt, lp):
    lt = np.asarray(lt); lp = np.asarray(lp); n = len(lt)
    classes = np.unique(lt); clusters = np.unique(lp)
    a = np.array([np.sum(lt==c) for c in classes])
    b = np.array([np.sum(lp==c) for c in clusters])
    Ctab = np.zeros((len(classes), len(clusters)))
    for i,c in enumerate(classes):
        for j,k in enumerate(clusters):
            Ctab[i,j] = np.sum((lt==c)&(lp==k))
    sum_ab = sum(x*(x-1)/2 for x in a); sum_bb = sum(x*(x-1)/2 for x in b)
    sum_C  = sum(Ctab[i,j]*(Ctab[i,j]-1)/2 for i in range(len(classes)) for j in range(len(clusters)))
    expected = sum_ab*sum_bb / (n*(n-1)/2)
    max_index = 0.5*(sum_ab+sum_bb)
    if max_index == expected: return 1.0
    return (sum_C - expected)/(max_index - expected)

labels_true = sub["phase"].astype("category").cat.codes.to_numpy()
ari_val = ari(labels_true, asg)
print(f"[probe] ARI (hand-labeled P1-P4 vs diffusion-clustered) = {ari_val:.3f}")
print(f"[probe]   (0~random, 1~perfect; >=0.65 would suggest phase recovery)")

# ---- 6. spectral gap rolling on landmark transition matrix (per-cycle) ----
# compute λ2/λ3 within each cycle's landmark block → one gap per cycle, compare to that cycle's regime
print("[probe] per-cycle spectral gap lam2/lam3 (landmark Markov matrix):")
tops = ev[(ev.event_type=="top") & (ev.reason_code=="canonical")]["date"].tolist()
bots = ev[(ev.event_type=="bottom") & (ev.reason_code.isin(["canonical"]))]["date"].tolist()
print("[probe] canonical tops:", [str(d.date()) for d in tops])
print("[probe] canonical bottoms:", [str(d.date()) for d in bots])

# map each landmark row to its cycle; compute gap per cycle block
lmark_cycle = sub["cycle_id"].to_numpy()[landmark_idx]
for cyc in sorted(sub.cycle_id.unique()):
    mask = lmark_cycle == cyc
    if mask.sum() < 5: 
        print(f"  {cyc}: too few landmarks ({mask.sum()}) — skip"); continue
    blk = PL[np.ix_(np.where(mask)[0], np.where(mask)[0])]
    wb, _ = np.linalg.eigh((blk+blk.T)/2); wb = np.sort(wb)[::-1]
    l1, l2, l3 = wb[0], wb[1], wb[2]
    ratio = l2/l3 if abs(l3)>1e-12 else float('nan')
    print(f"  {cyc}: lam1={l1:.4f} lam2={l2:.4f} lam3={l3:.4f}  gap(lam2/lam3)={ratio:.3f}")

# save artifacts to /tmp only
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
outcsv = os.path.join(OUTDIR, f"diffusion_probe_{ts}.csv")
out = sub[["date","cycle_id","days_from_halving","phase","cluster"]].reset_index(drop=True)
out.to_csv(outcsv, index=False)
print(f"[probe] embedding+cluster table -> {outcsv}")
print("[probe] DONE.")

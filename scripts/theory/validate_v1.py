"""
Robustness validation of V1 (the dominant correlation eigenvalue per cycle)
from heavy_flock_probe.py.

  CHECK 1a: panel sensitivity (orig_6, drop_mstr, crypto_4, risk_4)
  CHECK 1b: NON-overlapping 7d returns (every 7th row) on orig_6
  CHECK 2 : bootstrap 95% CI on lambda1 (orig_6, 200 resamples)

Output: stdout only. No files written.

The numbers from this script populate the "Robustness" subsection of
docs/theorical-framework/main-summary.md (lines 61-73). Re-running it
reproduces the published values bit-exactly given the same input snapshot.
"""
import numpy as np
import pandas as pd

REPO = r"D:\trading"
RAW = REPO + r"\data\processed\returns_aligned.csv"

df = pd.read_csv(RAW)
df["date"] = pd.to_datetime(df["date"])
H = {"C1": pd.Timestamp(2012, 11, 28), "C2": pd.Timestamp(2016, 7, 9),
     "C3": pd.Timestamp(2020, 5, 11), "C4": pd.Timestamp(2024, 4, 20)}
N = {"C1": pd.Timestamp(2016, 7, 9), "C2": pd.Timestamp(2020, 5, 11),
     "C3": pd.Timestamp(2024, 4, 20), "C4": pd.Timestamp(2028, 4, 1)}

def lam1(X):
    Xc = X - X.mean(0)
    Xn = Xc / (Xc.std(0) + 1e-12)
    C = (Xn.T @ Xn) / max(Xn.shape[0] - 1, 1)
    w = np.linalg.eigvalsh((C + C.T) / 2)
    return np.sort(w)[::-1][0]

panels = {
    "orig_6"   : ["btc", "mstr", "spx", "ndx", "dxy", "tlt"],
    "drop_mstr": ["btc", "spx", "ndx", "dxy", "tlt"],
    "crypto_4" : ["btc", "eth", "xrp", "sol"],
    "risk_4"   : ["btc", "spx", "ndx", "tlt"],
}

print("=" * 78)
print("CHECK 1a: lambda1 by panel (rolling 7d returns)")
print("=" * 78)
print("panel       C1      C2      C3      C4      range")
for name, cols in panels.items():
    lc = [c + "_log_return_w7d" for c in cols]
    r = []
    for cid in ["C1", "C2", "C3", "C4"]:
        s = df[(df.date >= H[cid]) & (df.date < N[cid])].dropna(subset=lc)
        r.append(lam1(s[lc].to_numpy(float)) if len(s) > 20 else np.nan)
    a = np.array([x for x in r if not np.isnan(x)])
    rg = ("%.2f..%.2f" % (a.min(), a.max())) if len(a) else "n/a"
    cells = "".join("%.3f   " % x if not np.isnan(x) else "--      " for x in r)
    print("%-11s %s %s" % (name, cells, rg))

print()
print("=" * 78)
print("CHECK 1b: lambda1 on NON-overlapping 7d returns (orig_6, every 7th row)")
print("=" * 78)
lc6 = [c + "_log_return_w7d" for c in panels["orig_6"]]
print("cycle   n     lam1")
for cid in ["C1", "C2", "C3", "C4"]:
    s = df[(df.date >= H[cid]) & (df.date < N[cid])].dropna(subset=lc6).iloc[::7]
    X = s[lc6].to_numpy(float)
    if len(X) >= 20:
        print("%-6s %-5d %.4f" % (cid, len(X), lam1(X)))
    else:
        print("%-6s %-5d --" % (cid, len(X)))

print()
print("=" * 78)
print("CHECK 2: bootstrap 95% CI on lambda1 (orig_6, 200 resamples)")
print("=" * 78)
rng = np.random.default_rng(42)
print("cycle  n     lam1     CI_lo   CI_hi   width")
for cid in ["C1", "C2", "C3", "C4"]:
    s = df[(df.date >= H[cid]) & (df.date < N[cid])].dropna(subset=lc6)
    X = s[lc6].to_numpy(float)
    if len(X) < 50:
        continue
    bs = np.array([lam1(X[rng.integers(0, len(X), len(X))]) for _ in range(200)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print("%-6s %-5d %.4f   %.3f   %.3f   %.3f" % (cid, len(X), lam1(X), lo, hi, hi - lo))

#!/usr/bin/env python3
"""
exploration/fetch_yield_indices.py  —  Exploration-only fetcher.

Fetches the four Cboe yield indices from Yahoo Finance using the SAME
v8/finance/chart endpoint proven in scripts/fetch_macro.py. Writes CSVs
into data/raw/exploration/ (mutable directory; NOT manifest-tracked per
docs/blockers/I-21 §3).

Series to fetch (all from Yahoo, all free, no auth, UA header only):
  ^TNX  = Cboe 10-Year Treasury Yield  (10y par yield, %)
  ^FVX  = Cboe 5-Year Treasury Yield   (5y par yield, %)
  ^IRX  = Cboe 13-Week Treasury Bill   (3m T-bill, %)
  ^TYX  = Cboe 30-Year Treasury Yield  (30y par yield, %)
  TIP   = iShares TIPS Bond ETF        (price proxy for real-yield side of break-even)
  ^VIX  = Cboe Volatility Index        (orthogonal sanity check)

Mapping to the exploration blocker doc §3.2:
  H1   needs y10, y2  -> ^TNX (y10), ^FVX (y2 proxy; closest free
                                   short-end substitute that Yahoo publishes
                                   natively; 2y ticker ^STE is unreliable)
  H2   needs be_short, be_long  -> approximated as:
            be_proxy_short = ^TNX close - TIP yield_proxy
            be_proxy_long  = same series; 5y5y not directly available via Yahoo
            (note: this PROXY DIFFERS from the FRED T5YIE/T5YIFR series listed
             in the blocker doc; block H2 verdict was caveated for FRED
             unavailability, and now further caveated for proxy substitution;
             see §3.4 honest-limit rule in blocker doc)
  H3   needs BAMLC1A0C13Y -> proxy via ^TNX-^FVX spread as credit/liquidity
            proxy (very weak). Final H3 verdict will explicitly note the
            double-proxy chain (credit wasn't available -> vendor risk spread
            used as liquidity proxy). H3 is the weakest of the six; we keep
            it only to honestly record the negative verdict.
  H6   needs y10/y2/dxy/tlt -> ^TNX, ^FVX, existing dxy/tlt
"""
import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
EXP_DIR = ROOT / "data" / "raw" / "exploration"

SERIES = {
    "y10":  "^TNX",
    "y5":   "^FVX",
    "y13w": "^IRX",
    "y30":  "^TYX",
    "tip":  "TIP",     # iShares TIPS Bond ETF (price; not a yield, but a real-yield proxy)
    "vix":  "^VIX",
}

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?period1={}&period2={}&interval=1d"
PERIOD1 = 631152000  # 1990-01-01
PERIOD2 = 1786752000  # ~2026-08-15
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_one(key: str, symbol: str) -> Path | None:
    url = BASE_URL.format(symbol, PERIOD1, PERIOD2)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as exc:
        print(f"  [FAIL] {key} ({symbol}): {exc}")
        return None
    data = r.json()
    if not data.get("chart", {}).get("result"):
        print(f"  [FAIL] {key} ({symbol}): no result")
        return None
    res = data["chart"]["result"][0]
    ts = res.get("timestamp")
    if not ts:
        print(f"  [FAIL] {key} ({symbol}): no timestamp")
        return None
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "timestamp": ts,
        "open":  q.get("open"),
        "high":  q.get("high"),
        "low":   q.get("low"),
        "close": q.get("close"),
        "volume": q.get("volume"),
    })
    df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["date", "close"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df = df[["date", "open", "high", "low", "close", "volume"]]
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    out = EXP_DIR / f"{key}_yahoo.csv"
    df.to_csv(out, index=False)
    print(f"  [OK] {key} ({symbol}) -> {out.name} ({len(df)} rows, {df['date'].iloc[0]}..{df['date'].iloc[-1]})")
    return out


def main():
    keys = list(SERIES.keys())
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", nargs="*", choices=keys, default=keys)
    args = parser.parse_args()
    print(f"Exploration fetch: data/raw/exploration/ (mutable)")
    for k in args.series:
        fetch_one(k, SERIES[k])
        time.sleep(1)


if __name__ == "__main__":
    main()

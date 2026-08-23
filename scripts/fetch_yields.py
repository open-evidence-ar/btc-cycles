#!/usr/bin/env python3
"""I-21.1: Fetch US Treasury yield panel for regime classification.

Two sources, all free, no API key, no auth:

  Yahoo v8 chart endpoint (same as fetch_macro.py) for the Cboe yield *indices*:
    y10  = ^TNX   10-Year Treasury par yield (%)
    y5   = ^FVX    5-Year Treasury par yield (%)
    y13w = ^IRX   13-Week Treasury Bill (%)   (3m T-bill)
    y30  = ^TYX   30-Year Treasury par yield (%)

  Eco3min mirror of FRED DGS2 for the proper 2-Year constant-maturity
    (Yahoo has no reliable native 2y ticker; the round-1 exploration
     substituted 10y-5y for the 10y-2y slope. A working free public DGS2
     mirror was identified in I-21.1 source discovery:
     https://eco3min.fr/dataset/us-2y-treasury-yield.csv
     which mirrors FRED DGS2 verbatim, coverage 1976-06-01 onwards,
     refreshed weekly. This resolves the round-1 honest-limit caveat
     ("FRED-UNAVAILABLE, 10y-5y substituted") with the proper 10y-2y
     gauge. See docs/blockers/I-21-eurodollar-proxies-exploration.md
     and I-21-eurodollar-proxies-exploration-2.md.)

Writes per-series immutable snapshots to data/raw/  with manifest entries
(append_manifest pattern from fetch_data.py / fetch_macro.py). The
classifier thresholds from the I-21 exploration blocker doc §4.1 (committed
in advance on the 10y-5y substitute) are re-applied UNCHANGED on the
proper 10y-2y slope; the thresholds are slope-agnostic (slope <= 0,
Δ > +40bps, Δ < -40bps), so the substitution upgrade does not retune them.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

# Yahoo v8 chart endpoint
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{}?period1={}&period2={}&interval=1d"
PERIOD1 = 631152000   # 1990-01-01
PERIOD2 = 1786752000  # ~2026-08-15
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Yahoo-sourced Cboe yield indices (key -> display ticker)
YAHOO_SERIES = {
    "y10":  "^TNX",
    "y5":   "^FVX",
    "y13w": "^IRX",
    "y30":  "^TYX",
}

# Eco3min mirror of FRED DGS2 (proper 2y constant-maturity, %)
ECO3MIN_SERIES = {"y2": "https://eco3min.fr/dataset/us-2y-treasury-yield.csv"}
ECO3MIN_LICENSE = "Eco3min open-data mirror of FRED DGS2 (H.15), public"

MANIFEST_HEADER = (
    "symbol\tsource\tsource_url\tretrieved_at\tlicense\tsha256\t"
    "row_count\tdate_range_first\tdate_range_last\tfilename"
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_manifest(
    *,
    symbol: str,
    source: str,
    source_url: str,
    license_name: str,
    filepath: Path,
    retrieved_at: str,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    digest = _sha256_file(filepath)
    df = pd.read_csv(filepath)
    # Require a 'date' column; use first/last date strings.
    first = str(df["date"].iloc[0])
    last = str(df["date"].iloc[-1])
    entry = "\t".join(
        [
            symbol, source, source_url, retrieved_at, license_name, digest,
            str(len(df)), first, last, filepath.name,
        ]
    )
    if MANIFEST.exists():
        lines = MANIFEST.read_text(encoding="utf-8").splitlines()
        if lines and lines[0] != MANIFEST_HEADER:
            lines = [MANIFEST_HEADER] + lines
        body = lines[1:] if lines else []
        # Remove any existing entry for this (symbol, source) so the latest
        # snapshot wins (mirrors fetch_macro.py dedup convention).
        body = [ln for ln in body if not ln.startswith(f"{symbol}\t{source}\t")]
        lines = [MANIFEST_HEADER] + body + [entry]
    else:
        lines = [MANIFEST_HEADER, entry]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_yahoo_yield(key: str, symbol: str) -> Path | None:
    """Fetch one Yahoo yield index via the v8 chart endpoint.

    Writes columns: date, close  (the par yield %). The Yahoo quote also
    exposes open/high/low but for yield indices the close is the daily
    par yield; we store close-only to keep the snapshot tight.

    Yahoo intermittently returns a truncated recent-only payload (16 rows)
    for some symbols under rapid sequential requests. We retry up to
    MAX_ATTEMPTS times, accepting a result only when it has >= MIN_ROWS
    rows (full-history sanity), otherwise re-requesting after a backoff.
    """
    MIN_ROWS = 1000
    MAX_ATTEMPTS = 3
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        url = YAHOO_BASE.format(symbol, PERIOD1, PERIOD2)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except Exception as exc:
            last_exc = exc
            print(f"  [retry {attempt}] {key} ({symbol}): {exc}")
            time.sleep(2 * attempt)
            continue
        data = r.json()
        if not data.get("chart", {}).get("result"):
            print(f"  [retry {attempt}] {key} ({symbol}): no result")
            time.sleep(2 * attempt)
            continue
        res = data["chart"]["result"][0]
        ts = res.get("timestamp")
        if not ts:
            print(f"  [retry {attempt}] {key} ({symbol}): no timestamp")
            time.sleep(2 * attempt)
            continue
        q = res["indicators"]["quote"][0]
        date_idx = pd.to_datetime(ts, unit="s", utc=True)
        df = pd.DataFrame({
            "date": date_idx.strftime("%Y-%m-%d"),
            "close": q.get("close"),
        })
        df = df.dropna(subset=["date", "close"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        if df.empty:
            print(f"  [retry {attempt}] {key} ({symbol}): empty after dropna")
            time.sleep(2 * attempt)
            continue
        if len(df) < MIN_ROWS:
            print(f"  [retry {attempt}] {key} ({symbol}): truncated ({len(df)} rows < {MIN_ROWS})")
            time.sleep(2 * attempt)
            continue
        break
    else:
        print(f"  [FAIL] {key} ({symbol}): all {MAX_ATTEMPTS} attempts failed")
        if last_exc is not None:
            print(f"         last error: {last_exc}")
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fname = f"{key}_yield_yahoo_{snapshot_date}.csv"
    filepath = RAW_DIR / fname
    df.to_csv(filepath, index=False)
    _append_manifest(
        symbol=key, source="yahoo",
        source_url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        license_name="Yahoo Finance Terms of Use",
        filepath=filepath, retrieved_at=retrieved_at,
    )
    print(f"  [OK] {key} ({symbol}) -> {fname} ({len(df)} rows, "
          f"{df['date'].iloc[0]}..{df['date'].iloc[-1]})")
    return filepath


def fetch_eco3min_yield(key: str, url: str) -> Path | None:
    """Fetch the 2y Treasury yield from the Eco3min DGS2 mirror.

    Source CSV format: `date,yield_2y` with a header row (verified in
    I-21.1 source discovery). Dates are ISO 8601 (YYYY-MM-DD), values
    are the 2y par yield in percent.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as exc:
        print(f"  [FAIL] {key} (eco3min): {exc}")
        return None
    text = r.text
    # Parse via pandas from the in-memory string.
    df = pd.read_csv(io.StringIO(text))
    # Normalize: expect columns `date,yield_2y` -> keep as `date,close`.
    if "date" not in df.columns:
        # Some mirrors emit `# comment` lines; re-skip.
        df = pd.read_csv(io.StringIO(text), comment="#")
    if "yield_2y" in df.columns:
        df = df.rename(columns={"yield_2y": "close"})
    elif "value" in df.columns:
        df = df.rename(columns={"value": "close"})
    if "date" not in df.columns or "close" not in df.columns:
        print(f"  [FAIL] {key} (eco3min): unexpected columns {list(df.columns)}")
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        print(f"  [FAIL] {key} (eco3min): empty after dropna")
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fname = f"{key}_eco3min_{snapshot_date}.csv"
    filepath = RAW_DIR / fname
    df = df[["date", "close"]]
    df.to_csv(filepath, index=False)
    _append_manifest(
        symbol=key, source="eco3min",
        source_url=url,
        license_name=ECO3MIN_LICENSE,
        filepath=filepath, retrieved_at=retrieved_at,
    )
    print(f"  [OK] {key} (eco3min) -> {fname} ({len(df)} rows, "
          f"{df['date'].iloc[0]}..{df['date'].iloc[-1]})")
    return filepath


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch US Treasury yield panel (I-21).")
    parser.add_argument(
        "--series", nargs="*",
        choices=list(YAHOO_SERIES.keys()) + list(ECO3MIN_SERIES.keys()),
        default=None,
        help="Subset of series to fetch (default: all).",
    )
    args = parser.parse_args(argv)

    yahoo_keys = list(YAHOO_SERIES.keys())
    eco3min_keys = list(ECO3MIN_SERIES.keys())
    if args.series:
        yahoo_keys = [k for k in yahoo_keys if k in args.series]
        eco3min_keys = [k for k in eco3min_keys if k in args.series]
    else:
        yahoo_keys = list(YAHOO_SERIES.keys())
        eco3min_keys = list(ECO3MIN_SERIES.keys())

    print("I-21.1: US Treasury yield panel fetch")
    print(f"  Yahoo: {yahoo_keys}")
    print(f"  Eco3min (DGS2 mirror): {eco3min_keys}")
    print()
    for k in yahoo_keys:
        fetch_yahoo_yield(k, YAHOO_SERIES[k])
        time.sleep(1)
    for k in eco3min_keys:
        fetch_eco3min_yield(k, ECO3MIN_SERIES[k])
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Download and snapshot altcoin price series with provenance manifest entries.

Supports two data sources:
  - CryptoDataDownload (CDD): Bitfinex OHLCV pairs. Frozen at Oct 2025 for
    ETH/XRP/SOL as of 2026-07-23.
  - Yahoo Finance: Fresh data through current date. Used as fallback when CDD
    is stale or unavailable.

Source selection (--source):
  - cryptodatadownload: CDD only
  - yahoo: Yahoo only
  - auto (default): Try CDD first, fall back to Yahoo on failure

The build scripts (build_alt_cycle_metrics.py) merge both CDD and Yahoo
snapshots to get the widest date range: CDD provides early historical data
(e.g. ETH-C2 pre-halving bottom Apr 2016), Yahoo provides fresh data
through current date.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

MANIFEST_HEADER = (
    "symbol\tsource\tsource_url\tretrieved_at\tlicense\tsha256\t"
    "row_count\tdate_range_first\tdate_range_last\tfilename"
)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_cryptodatadownload_ohlc(asset: str, exchange: str) -> pd.DataFrame:
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Map asset to symbol format
    asset_map = {
        "eth": ("ETHUSD", "Bitfinex_ETHUSD_d.csv"),
        "xrp": ("XRPUSD", "Bitfinex_XRPUSD_d.csv"),
        "sol": ("SOLUSD", "Bitfinex_SOLUSD_d.csv")
    }
    
    if asset not in asset_map:
        raise ValueError(f"Unsupported asset: {asset}")
    
    required_symbol, required_filename = asset_map[asset]
    
    print(f"  Downloading from: https://www.cryptodatadownload.com/cdd/{required_filename}")
    source_url = f"https://www.cryptodatadownload.com/cdd/{required_filename}"
    response = requests.get(source_url, headers=headers, timeout=60)
    response.raise_for_status()
    
    lines = response.text.strip().split("\n")
    print(f"  File has {len(lines)} lines ({len(response.content)} bytes)")
    
    # Print first 5 lines for debugging
    print(f"  First 10 lines:")
    for i, line in enumerate(lines[:10]):
        print(f"    {i}: {repr(line[:100])}")
    
    # Skip the homepage URL line (line 0)
    # The format is:
    # Line 0: https://www.CryptoDataDownload.com
    # Line 1: unix,date,symbol,open,high,low,close,Volume USD,Volume ETH
    # Line 2+: data rows
    
    data_rows = []
    
    for i in range(2, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        
        parts = line.split(",")
        if len(parts) >= 7:
            try:
                # Extract date and convert to YYYY-MM-DD format
                # Format: "2025-10-16 00:00:00"
                date_str = parts[1]
                if " " in date_str:
                    date_iso = date_str.split(" ")[0]  # Extract YYYY-MM-DD
                else:
                    date_iso = date_str[:10] if len(date_str) >= 10 else date_str
                
                # Parse numeric columns
                # Note: open, high, low, close are at indices 3, 4, 5, 6
                open_price = float(parts[3])
                high = float(parts[4])
                low = float(parts[5])
                close = float(parts[6])
                
                # Find volume column based on asset
                # For ETH: Volume ETH is typically at index 8 in Bitfinex files
                # For XRP: Volume XRP is typically at index 8
                # For SOL: Volume SOL is typically at index 8
                volume = 0.0
                
                # Try to find volume by looking for "Volume X" in the header and then the corresponding value
                if len(lines) > 1:
                    header_parts = lines[1].strip().lower().split(",")
                    # Find which column contains the asset-specific volume
                    volume_col_idx = -1
                    for j, col in enumerate(header_parts):
                        if asset == "eth" and "volume eth" in col:
                            volume_col_idx = j
                        elif asset == "xrp" and "volume xrp" in col:
                            volume_col_idx = j
                        elif asset == "sol" and "volume sol" in col:
                            volume_col_idx = j
                        elif "volume usd" in col and volume_col_idx == -1:
                            volume_col_idx = j
                    
                    if volume_col_idx != -1 and volume_col_idx < len(parts):
                        try:
                            volume = float(parts[volume_col_idx])
                        except:
                            volume = 0.0
                elif asset == "eth" and len(parts) > 8:
                    try:
                        volume = float(parts[8])
                    except:
                        pass
                elif asset == "xrp" and len(parts) > 8:
                    try:
                        volume = float(parts[8])
                    except:
                        pass
                elif asset == "sol" and len(parts) > 8:
                    try:
                        volume = float(parts[8])
                    except:
                        pass
                
                data_rows.append({
                    "date": date_iso,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                })
            except Exception as e:
                print(f"    Warning: Skipping malformed line {i}: {line[:50]}... ({e})")
                continue
    
    if not data_rows:
        raise ValueError(f"No data rows found in {exchange} {asset} file")
    
    print(f"  Parsed {len(data_rows)} data rows")
    
    # Create DataFrame and sort by date (newest first as per original fetch_data.py pattern)
    df = pd.DataFrame(data_rows)
    df["_date_sort"] = pd.to_datetime(df["date"])
    df = df.sort_values("_date_sort", ascending=False)
    df = df.drop(columns=["_date_sort"])
    
    print(f"  Date range (newest to oldest): {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
    print(f"  Volume stats: min={df['volume'].min()}, max={df['volume'].max()}, mean={df['volume'].mean():.2f}")
    
    return df


def append_manifest(
    *,
    symbol: str,
    source: str,
    source_url: str,
    license_name: str,
    filepath: Path,
    retrieved_at: str,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    df = pd.read_csv(filepath)
    
    # CRITICAL: date_range_first and date_range_last must be chronological:
    # date_range_first = oldest date (first in chronological order)
    # date_range_last = newest date (last in chronological order)
    chronological_dates = df["date"].sort_values().tolist()
    date_range_first = chronological_dates[0] if chronological_dates else df["date"].iloc[0]
    date_range_last = chronological_dates[-1] if chronological_dates else df["date"].iloc[-1]
    
    digest = sha256_file(filepath)
    
    entry = "\t".join([
        symbol,
        source,
        source_url,
        retrieved_at,
        license_name,
        digest,
        str(len(df)),
        date_range_first,
        date_range_last,
        filepath.name,
    ])
    
    if MANIFEST.exists():
        lines = MANIFEST.read_text(encoding="utf-8").splitlines()
        if lines and lines[0] != MANIFEST_HEADER:
            lines = [MANIFEST_HEADER] + lines
        body = lines[1:] if lines else []
        body = [ln for ln in body if not ln.startswith(f"{symbol}\t")]
        lines = [MANIFEST_HEADER] + body + [entry]
    else:
        lines = [MANIFEST_HEADER, entry]
    
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_asset(asset: str, source: str, out_dir: Path) -> Path:
    asset = asset.lower()
    source = source.lower()

    if source == "cryptodatadownload":
        return _fetch_cdd(asset, out_dir)
    elif source == "yahoo":
        return _fetch_yahoo(asset, out_dir)
    elif source == "auto":
        # Try CDD first, fall back to Yahoo if CDD fails or is stale
        try:
            return _fetch_cdd(asset, out_dir)
        except Exception as e:
            print(f"  CDD failed ({e}), falling back to Yahoo")
            return _fetch_yahoo(asset, out_dir)
    else:
        raise ValueError(f"Unsupported source: {source}")


def _fetch_cdd(asset: str, out_dir: Path) -> Path:
    """Fetch from CryptoDataDownload (Bitfinex pair)."""
    asset_map = {
        "eth": ("ETHUSD", "Bitfinex_ETHUSD_d.csv"),
        "xrp": ("XRPUSD", "Bitfinex_XRPUSD_d.csv"),
        "sol": ("SOLUSD", "Bitfinex_SOLUSD_d.csv")
    }

    if asset not in asset_map:
        raise ValueError(f"Unsupported asset: {asset}")

    required_symbol, required_filename = asset_map[asset]
    source_url = f"https://www.cryptodatadownload.com/cdd/{required_filename}"

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{asset}_cdd_{snapshot_date}.csv"
    filepath = out_dir / filename

    print(f"  Fetching {asset} data from Bitfinex (CDD)")
    df = fetch_cryptodatadownload_ohlc(asset, "Bitfinex")

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)

    append_manifest(
        symbol=asset,
        source=source,
        source_url=source_url,
        license_name="CryptoDataDownload Terms (free for personal/educational use)",
        filepath=filepath,
        retrieved_at=retrieved_at,
    )

    print(f"Wrote {filepath} ({len(df)} rows)")
    return filepath


def _fetch_yahoo(asset: str, out_dir: Path) -> Path:
    """Fetch from Yahoo Finance (USD pair)."""
    import time as _time

    yahoo_map = {
        "eth": "ETH-USD",
        "xrp": "XRP-USD",
        "sol": "SOL-USD",
        "mstr": "MSTR",
        "wgmi": "WGMI",
        "riot": "RIOT",
        "mara": "MARA",
    }

    if asset not in yahoo_map:
        raise ValueError(f"Unsupported asset for Yahoo: {asset}")

    yahoo_symbol = yahoo_map[asset]
    source_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"

    # Yahoo epoch: 1949-12-31 to ~now
    period1 = 631152000
    period2 = int(datetime.now(timezone.utc).timestamp())

    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"{source_url}?period1={period1}&period2={period2}&interval=1d"
    print(f"  Fetching {asset} data from Yahoo ({yahoo_symbol})")
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()
    if not data["chart"] or not data["chart"]["result"]:
        raise ValueError(f"No data returned for {yahoo_symbol}")

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quotes = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": quotes.get("open", [None] * len(timestamps)),
        "high": quotes.get("high", [None] * len(timestamps)),
        "low": quotes.get("low", [None] * len(timestamps)),
        "close": quotes.get("close", [None] * len(timestamps)),
        "volume": quotes.get("volume", [None] * len(timestamps)),
    })

    df["date"] = df["timestamp"].apply(
        lambda ts: (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts)).strftime("%Y-%m-%d")
    )
    df = df.dropna(subset=["timestamp", "date"]).drop_duplicates(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[["date", "open", "high", "low", "close", "volume"]]

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{asset}_yahoo_{snapshot_date}.csv"
    filepath = out_dir / filename

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)

    append_manifest(
        symbol=asset,
        source="yahoo",
        source_url=source_url,
        license_name="Yahoo Finance Terms of Use",
        filepath=filepath,
        retrieved_at=retrieved_at,
    )

    print(f"Wrote {filepath} ({len(df)} rows)")
    _time.sleep(2)
    return filepath


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and snapshot altcoin market data.")
    parser.add_argument("--asset", required=True, help="Asset symbol (e.g. eth, xrp, sol)")
    parser.add_argument("--source", default="auto",
                        choices=["cryptodatadownload", "yahoo", "auto"],
                        help="Data source (default: auto = CDD first, Yahoo fallback)")
    parser.add_argument(
        "--out",
        default=str(RAW_DIR),
        help="Output directory for raw snapshots",
    )
    args = parser.parse_args(argv)
    fetch_asset(args.asset, args.source, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

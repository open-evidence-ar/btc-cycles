#!/usr/bin/env python3
"""Download and snapshot price series with provenance manifest entries."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

COINGECKO_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "xrp": "ripple",
}

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


def fetch_bitstamp_ohlc(symbol: str) -> pd.DataFrame:
    rows = []
    start_ts = 1279315200  # 2010-07-16
    import time as _time
    now_ts = int(_time.time())
    while True:
        r = requests.get(
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/",
            params={"step": 86400, "limit": 1000, "start": start_ts},
            timeout=60,
        )
        r.raise_for_status()
        chunk = r.json()["data"]["ohlc"]
        if not chunk:
            break
        rows.extend(chunk)
        last_ts = int(chunk[-1]["timestamp"])
        if last_ts >= now_ts - 86400:
            break
        start_ts = last_ts + 86400
        if len(chunk) < 1000:
            _time.sleep(1)
            continue
        _time.sleep(1)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    # Convert timestamp to integer (as string then int)
    df["timestamp"] = df["timestamp"].astype(int)
    df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.strftime(
        "%Y-%m-%d"
    )
    df = df[["date", "open", "high", "low", "close", "volume"]]
    # Convert numeric columns to float
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = df[col].astype(float)
    return df


def fetch_coingecko_ohlc(coin_id: str, days: str = "max") -> pd.DataFrame:
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": days}
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        raise ValueError(f"Empty OHLC response for {coin_id}")

    df = pd.DataFrame(rows, columns=["timestamp_ms", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.strftime(
        "%Y-%m-%d"
    )
    df = df[["date", "open", "high", "low", "close"]]
    df["volume"] = pd.NA
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
    digest = sha256_file(filepath)
    entry = "\t".join(
        [
            symbol,
            source,
            source_url,
            retrieved_at,
            license_name,
            digest,
            str(len(df)),
            str(df["date"].iloc[0]),
            str(df["date"].iloc[-1]),
            filepath.name,
        ]
    )
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
    if source not in ("coingecko", "bitstamp"):
        raise ValueError(f"Unsupported source: {source}")

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{asset}_{source}_{snapshot_date}.csv"
    filepath = out_dir / filename

    if source == "coingecko":
        coin_id = COINGECKO_IDS.get(asset)
        if coin_id is None:
            raise ValueError(f"Unsupported asset: {asset}")
        source_url = (
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
            "?vs_currency=usd&days=max"
        )
        df = fetch_coingecko_ohlc(coin_id)
        license_name = "CoinGecko Terms of Service"
    else:  # bitstamp
        if asset != "btc":
            raise ValueError("Bitstamp only supports BTC")
        source_url = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
        df = fetch_bitstamp_ohlc("btc")
        license_name = "Bitstamp License (unspecified, use at own risk)"

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)

    append_manifest(
        symbol=asset,
        source=source,
        source_url=source_url,
        license_name=license_name,
        filepath=filepath,
        retrieved_at=retrieved_at,
    )
    print(f"Wrote {filepath} ({len(df)} rows)")
    return filepath


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and snapshot market data.")
    parser.add_argument("--asset", required=True, help="Asset symbol (e.g. btc)")
    parser.add_argument("--source", default="coingecko", help="Data source")
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

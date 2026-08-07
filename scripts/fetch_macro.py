import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

ASSETS = {
    "spx": "^GSPC",
    "ndx": "^NDX",
    "dxy": "DX-Y.NYB",
    "tlt": "TLT",
    "gold": "GC=F",
}

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}?period1={}&period2={}&interval=1d"

# Yahoo's Unix epoch start (1949-12-31 00:00:00 UTC) and end (2026-08-15 00:00:00 UTC)
PERIOD1 = 631152000
PERIOD2 = 1786752000

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_yahoo_asset(symbol_key: str, target_symbol: str) -> None:
    url = BASE_URL.format(target_symbol, PERIOD1, PERIOD2)

    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()

    data = response.json()
    if not data["chart"] or not data["chart"]["result"]:
        raise ValueError(f"No data returned for {target_symbol}")

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quotes = result["indicators"]["quote"][0]

    if not timestamps:
        raise ValueError(f"No timestamps returned for {target_symbol}")

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": quotes.get("open", [None] * len(timestamps)),
            "high": quotes.get("high", [None] * len(timestamps)),
            "low": quotes.get("low", [None] * len(timestamps)),
            "close": quotes.get("close", [None] * len(timestamps)),
            "volume": quotes.get("volume", [None] * len(timestamps)),
        }
    )

    # Convert timestamp to datetime and extract date
    df["date"] = df["timestamp"].apply(
        lambda ts: (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=ts)).strftime("%Y-%m-%d")
    )

    df = df.dropna(subset=["timestamp", "date"]).drop_duplicates(subset=["date"])

    df = df.sort_values("date").reset_index(drop=True)

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    filename = f"{symbol_key}_yahoo_{retrieved_at[:10]}.csv"
    filepath = RAW_DIR / filename

    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

    df.to_csv(filepath, index=False)

    sha256 = _sha256_file(filepath)
    row_count = len(df)
    date_range_first = df["date"].iloc[0]
    date_range_last = df["date"].iloc[-1]

    manifest_entry = {
        "symbol": symbol_key,
        "source": "yahoo",
        "source_url": f"https://query1.finance.yahoo.com/v8/finance/chart/{target_symbol}",
        "retrieved_at": retrieved_at,
        "license": "Yahoo Finance Terms of Use",
        "sha256": sha256,
        "row_count": row_count,
        "date_range_first": date_range_first,
        "date_range_last": date_range_last,
        "filename": filename,
    }

    if not MANIFEST.is_file():
        with open(MANIFEST, "w") as f:
            f.write("symbol\tsource\tsource_url\tretrieved_at\tlicense\tsha256\trow_count\tdate_range_first\tdate_range_last\tfilename\n")

    manifest_df = pd.read_csv(MANIFEST, sep="\t", dtype=str)

    symbol_exists = manifest_df[(manifest_df["symbol"] == symbol_key) & (manifest_df["source"] == "yahoo")]

    if not symbol_exists.empty:
        manifest_df = manifest_df.drop(symbol_exists.index)

    new_row = pd.DataFrame([manifest_entry])
    manifest_df = pd.concat([manifest_df, new_row], ignore_index=True)

    manifest_df.to_csv(MANIFEST, sep="\t", index=False)

    print(f"Fetched {target_symbol} ({symbol_key}) -> {filename} ({row_count} rows, {date_range_first} to {date_range_last})")

    time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Fetch macro assets from Yahoo Finance")
    parser.add_argument("--asset", choices=list(ASSETS.keys()), help="Asset to fetch (spx, ndx, dxy, tlt)")
    parser.add_argument("--source", default="yahoo", help="Data source (default: yahoo)")
    args = parser.parse_args()

    if args.asset:
        fetch_yahoo_asset(args.asset, ASSETS[args.asset])
    else:
        for symbol_key, target_symbol in ASSETS.items():
            fetch_yahoo_asset(symbol_key, target_symbol)


if __name__ == "__main__":
    main()

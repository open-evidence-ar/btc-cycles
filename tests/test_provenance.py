"""I-02+ validation gate: raw data provenance and sanity checks."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> pd.DataFrame:
    assert MANIFEST.is_file(), "manifest.txt missing"
    return pd.read_csv(MANIFEST, sep="\t", dtype=str)


def _latest_snapshot(symbol: str) -> tuple[Path, pd.Series]:
    manifest = _load_manifest()
    rows = manifest[manifest["symbol"] == symbol]
    assert not rows.empty, f"No manifest entry for {symbol}"
    row = rows.iloc[-1]
    path = RAW_DIR / row["filename"]
    assert path.is_file(), f"Snapshot file missing: {path}"
    return path, row


class TestBtcProvenance:
    """I-02 gate: BTC CoinGecko snapshot."""

    def test_manifest_sha_matches_file(self):
        path, row = _latest_snapshot("btc")
        assert _sha256_file(path) == row["sha256"]

    def test_row_count(self):
        _, row = _latest_snapshot("btc")
        assert int(row["row_count"]) >= 5000

    def test_dates_non_nan(self):
        path, row = _latest_snapshot("btc")
        df = pd.read_csv(path)
        assert pd.notna(df["date"].iloc[0])
        assert pd.notna(df["date"].iloc[-1])
        assert row["date_range_first"] == df["date"].iloc[0]
        assert row["date_range_last"] == df["date"].iloc[-1]

    def test_c3_top_close_within_tolerance(self):
        """Daily close near 2017-12-17 should be ~$19,497 within ±14d window."""
        path, _ = _latest_snapshot("btc")
        df = pd.read_csv(path, parse_dates=["date"])
        target = datetime(2017, 12, 17)
        window_start = target - timedelta(days=14)
        window_end = target + timedelta(days=14)
        mask = (df["date"] >= window_start) & (df["date"] <= window_end)
        window = df.loc[mask]
        assert not window.empty, "No rows in ±14d window around 2017-12-17"
        expected = 19497.0
        tolerance = 500.0  # allow for OHLC candle vs daily close variance
        diffs = (window["close"] - expected).abs()
        assert diffs.min() <= tolerance, (
            f"Closest close in window: {window.loc[diffs.idxmin(), 'close']:.2f} "
            f"(expected {expected} ±{tolerance})"
        )

    def test_series_starts_early_enough(self):
        _, row = _latest_snapshot("btc")
        first = datetime.fromisoformat(row["date_range_first"])
        assert first <= datetime(2011, 8, 1) + timedelta(days=365)

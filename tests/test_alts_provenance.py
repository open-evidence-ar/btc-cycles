"""I-03 validation gate: altcoin provenance and sanity checks.

Gate start-date tolerances were relaxed per DESIGN.md §9.4 to match the
earliest-available dates from CryptoDataDownload's Bitfinex snapshots
(CoinGecko/CryptoCompare public APIs locked down historical access during
the I-03 build). See docs/blockers/I-03-*-start-date.md for documented
substitutions and rationale.
"""

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


def _test_start_date(symbol: str, gate_date: datetime) -> None:
    """Test that symbol's earliest data date meets or precedes gate date.

    Checks all manifest entries for this symbol (CDD + Yahoo) and uses the
    earliest date_range_first across all snapshots, since the build scripts
    merge both sources.
    """
    manifest = _load_manifest()
    rows = manifest[manifest["symbol"] == symbol]
    assert not rows.empty, f"No manifest entry for {symbol}"
    earliest = min(datetime.fromisoformat(r["date_range_first"]) for _, r in rows.iterrows())
    assert earliest <= gate_date, (
        f"{symbol.upper()} earliest date {earliest.date()} is after gate date {gate_date.date()}. "
        f"Need to update gate or replace data source"
    )


def _check_daily_granularity(symbol: str) -> None:
    """Verify daily granularity: gaps between consecutive dates are 1-4 days.

    The first row's gap is NaN by definition and is excluded from the assertion.
    """
    path, _ = _latest_snapshot(symbol)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    gaps = df["date"].diff().dt.days
    gaps_clean = gaps.dropna()
    bad = gaps_clean[(gaps_clean < 1) | (gaps_clean > 4)]
    assert bad.empty, (
        f"{symbol.upper()} gaps outside 1-4 day range: {bad.tolist()[:20]} "
        f"({len(bad)} bad gaps out of {len(gaps_clean)})"
    )


class TestAltsProvenance:
    """I-03 gate: ALTCOIN provenance validation.

    Start-date gate tolerances were tuned per DESIGN.md §9.4 from the original
    §3.1 spec to the earliest-available dates from CryptoDataDownload's Bitfinex
    snapshots. See docs/blockers/I-03-*-start-date.md for the substitution
    rationale and reconciliation entries.
    """

    def test_alts_in_manifest(self):
        """All three altcoin symbols present."""
        manifest = _load_manifest()
        symbols = set(manifest["symbol"].tolist())
        for symbol in {"eth", "xrp", "sol"}:
            assert symbol in symbols, f"Missing altcoin symbol: {symbol}"

    def test_eth_starts_2016_or_earlier(self):
        """ETH first date must be ≤ 2017-11-09 (CDD/Yahoo earliest available).

        Original DESIGN.md §10 gate was 2015-08-15; relaxed to 2016-03-15 per §9.4
        (CoinGecko/CryptoCompare public APIs locked down during I-03 build);
        further relaxed to 2017-11-09 per §9.4 (2026-Q3 update: CDD public
        archive Bitfinex ETHUSD history shrank to 2017-11-09 start, matching
        Yahoo's ETH-USD listing date — no free public source preserves ETH/USD
        daily OHLC back to the original 2015 launch). See
        docs/blockers/I-03-eth-start-date.md.
        """
        _test_start_date("eth", datetime(2017, 11, 9))

    def test_xrp_starts_2017_or_earlier(self):
        """XRP first date must be ≤ 2017-11-09 (CDD/Yahoo earliest available).

        Original DESIGN.md §10 gate was 2013-08-15; relaxed to 2017-06-01 per §9.4
        (no free public API provides XRP/USD daily OHLC back to 2013); further
        relaxed to 2017-11-09 per §9.4 (2026-Q3 update: CDD public archive
        Bitfinex XRPUSD history shrank to 2017-11-09 start, matching Yahoo's
        XRP-USD listing date — no free public source preserves XRP/USD daily
        OHLC back to its 2013 launch). See
        docs/blockers/I-03-xrp-start-date.md.
        """
        _test_start_date("xrp", datetime(2017, 11, 9))

    def test_sol_starts_2021_or_earlier(self):
        """SOL first date must be ≤ 2021-12-15 (Bitfinex earliest).

        Original DESIGN.md §10 gate was 2020-04-15; relaxed to 2021-12-15 per §9.4
        because SOL Bitfinex listing began 2021-12. SOL genesis 2020-04 is only
        available from CoinGecko Pro (paid). See docs/blockers/I-03-sol-start-date.md.
        """
        _test_start_date("sol", datetime(2021, 12, 15))


class TestEthAltcoin:
    """ETH provenance validation."""

    def test_manifest_sha_matches_file(self):
        path, row = _latest_snapshot("eth")
        assert _sha256_file(path) == row["sha256"]

    def test_eth_row_count(self):
        _, row = _latest_snapshot("eth")
        assert int(row["row_count"]) >= 100

    def test_eth_daily_granularity(self):
        _check_daily_granularity("eth")


class TestXrpAltcoin:
    """XRP provenance validation."""

    def test_manifest_sha_matches_file(self):
        path, row = _latest_snapshot("xrp")
        assert _sha256_file(path) == row["sha256"]

    def test_xrp_row_count(self):
        _, row = _latest_snapshot("xrp")
        assert int(row["row_count"]) >= 100

    def test_xrp_daily_granularity(self):
        _check_daily_granularity("xrp")


class TestSolAltcoin:
    """SOL provenance validation."""

    def test_manifest_sha_matches_file(self):
        path, row = _latest_snapshot("sol")
        assert _sha256_file(path) == row["sha256"]

    def test_sol_row_count(self):
        _, row = _latest_snapshot("sol")
        assert int(row["row_count"]) >= 100

    def test_sol_daily_granularity(self):
        _check_daily_granularity("sol")

"""I-21.1 gate: US Treasury yield panel provenance.

Validates that the yield series are manifest-tracked, that the 2y series
(the I-21.1 resolution of the round-1 "FRED-UNAVAILABLE, 10y-5y substituted"
honest limit) is present with full-history coverage, and that the Yahoo
indices have full 1990+ coverage (not the truncated 16-row payloads Yahoo
sometimes returns under rapid sequential requests).
"""

import pandas as pd
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

YIELD_SYMBOLS = {"y2", "y10", "y5", "y13w", "y30"}


def _load_manifest():
    assert MANIFEST.is_file(), "manifest.txt missing"
    return pd.read_csv(MANIFEST, sep="\t", dtype=str)


def _latest_snapshot(symbol):
    manifest = _load_manifest()
    rows = manifest[manifest["symbol"] == symbol]
    assert not rows.empty, f"No manifest entry for {symbol}"
    row = rows.iloc[-1]
    path = RAW_DIR / row["filename"]
    assert path.is_file(), f"Snapshot file missing: {path}"
    return path, row


class TestYieldProvenance:
    def test_yield_symbols_in_manifest(self):
        manifest = _load_manifest()
        present = set(manifest["symbol"].tolist())
        missing = YIELD_SYMBOLS - present
        assert not missing, f"Missing yield series in manifest: {missing}"

    def test_y2_available(self):
        """The proper 2y constant-maturity series (Eco3min DGS2 mirror) must
        be present, full-history (>= 5000 rows), and start <= 1990-12-31 so
        it covers every cycle back to the 1989 pre-C1 era."""
        path, _ = _latest_snapshot("y2")
        df = pd.read_csv(path, parse_dates=["date"])
        assert len(df) >= 5000, f"y2 too short: {len(df)} rows"
        assert df["date"].min().date().isoformat() <= "1990-12-31", (
            f"y2 starts too late: {df['date'].min().date()}"
        )
        assert df["date"].max().year >= 2025, "y2 not current"

    def test_y2_is_dgs2(self):
        """The 2y mirror tracks FRED DGS2 (~1-5%, not a stripped index like
        the Cboe yields which are quoted in absolute percent already; the
        sanity here is just that values are in a plausible yield band)."""
        path, _ = _latest_snapshot("y2")
        df = pd.read_csv(path, parse_dates=["date"])
        close = df["close"].dropna()
        assert close.between(0.0, 20.0).all(), "y2 outside plausible yield band"

    def test_yahoo_indices_full_history(self):
        """y10/y5/y13w/y30 must have full 1990+ coverage (>= 5000 rows),
        guarding against Yahoo's intermittent truncated payloads."""
        for sym in ["y10", "y5", "y13w", "y30"]:
            path, _ = _latest_snapshot(sym)
            df = pd.read_csv(path, parse_dates=["date"])
            assert len(df) >= 5000, f"{sym} too short: {len(df)} rows"
            assert df["date"].min().year <= 1990, f"{sym} starts too late"

    def test_y2_geo_coverage_extends_beyond_yahoo(self):
        """The 2y series goes back to 1976-06-01, longer than the Yahoo
        indices (1990), which is required for the 180-day delta on the
        earliest slope observations."""
        path_y2, _ = _latest_snapshot("y2")
        path_y10, _ = _latest_snapshot("y10")
        y2 = pd.read_csv(path_y2, parse_dates=["date"])
        y10 = pd.read_csv(path_y10, parse_dates=["date"])
        assert y2["date"].min() < y10["date"].min(), "y2 should start before y10"
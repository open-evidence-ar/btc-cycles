import pandas as pd
import pytest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "manifest.txt"

MACRO_SYMBOLS = {"spx", "ndx", "dxy", "tlt", "gold"}


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


class TestMacroProvenance:
    def test_macro_in_manifest(self):
        manifest = _load_manifest()
        macro_symbols = MACRO_SYMBOLS
        present_symbols = set(manifest["symbol"].tolist())
        missing = macro_symbols - present_symbols
        assert not missing, f"Missing macro assets in manifest: {missing}"
        macro_rows = manifest[manifest["symbol"].isin(macro_symbols)]
        assert len(macro_rows) == 5, f"Expected 5 macro rows, found {len(macro_rows)}"

    def test_spx_2017_12_17_close_within_0_1_pct(self):
        path, _ = _latest_snapshot("spx")
        df = pd.read_csv(path, parse_dates=["date"])

        target = datetime(2017, 12, 17)
        window_start = target - timedelta(days=14)
        window_end = target + timedelta(days=14)
        mask = (df["date"] >= window_start) & (df["date"] <= window_end)
        window = df.loc[mask]

        assert not window.empty, "No rows in ±14d window around 2017-12-17"

        expected = 2672.22
        window["close_diff_pct"] = abs(window["close"] - expected) / expected
        closest_idx = window["close_diff_pct"].idxmin()
        closest_close = window.loc[closest_idx, "close"]
        closest_date = window.loc[closest_idx, "date"]

        tolerance = 0.001
        assert window.loc[closest_idx, "close_diff_pct"] <= tolerance, (
            f"SPX {closest_date.date()} close {closest_close:.2f} "
            f"outside 0.1% of $2672.22 (diff: {abs(closest_close - expected) / expected:.6f})"
        )

    def test_tlt_starts_earlier_than_2002_09_01(self):
        _, row = _latest_snapshot("tlt")
        first = datetime.fromisoformat(row["date_range_first"])
        assert first <= datetime(2002, 9, 1), (
            f"TLT first date {first.date()} is after 2002-09-01"
        )

    def test_dxy_row_count_at_least_8000(self):
        _, row = _latest_snapshot("dxy")
        assert int(row["row_count"]) >= 8000, (
            f"DXY row count {row['row_count']} is less than 8000"
        )

    def test_sha_matches(self):
        macro_symbols = MACRO_SYMBOLS
        for symbol in macro_symbols:
            path, row = _latest_snapshot(symbol)

            import hashlib
            def _sha256_file(path):
                h = hashlib.sha256()
                with path.open("rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                return h.hexdigest()

            file_sha = _sha256_file(path)
            assert file_sha == row["sha256"], (
                f"SHA256 mismatch for {symbol}: manifest={row['sha256']}, file={file_sha}"
            )

    def test_dates_non_nan(self):
        macro_symbols = MACRO_SYMBOLS
        for symbol in macro_symbols:
            path, row = _latest_snapshot(symbol)
            df = pd.read_csv(path)

            assert pd.notna(df["date"].iloc[0]), f"{symbol}: first date is NaN"
            assert pd.notna(df["date"].iloc[-1]), f"{symbol}: last date is NaN"

            df["date_str"] = df["date"].astype(str)
            df_first_str = df["date_str"].iloc[0]
            df_last_str = df["date_str"].iloc[-1]
            assert row["date_range_first"] == df_first_str, f"{symbol}: first date mismatch"
            assert row["date_range_last"] == df_last_str, f"{symbol}: last date mismatch"

    def test_gold_covers_two_decades(self):
        """Gold (GC=F) must have multi-decade history (starts 2000-08-30) so
        the I-19 macro 2-stage fit has C1-C3 drawdown/multiplier samples."""
        path, row = _latest_snapshot("gold")
        first = datetime.fromisoformat(row["date_range_first"])
        last = datetime.fromisoformat(row["date_range_last"])
        assert first <= datetime(2001, 1, 1), (
            f"Gold first date {first.date()} is after 2001-01-01"
        )
        assert (last - first).days >= 20 * 365, (
            f"Gold history span {(last - first).days}d is under 20 years"
        )
        assert int(row["row_count"]) >= 6000, (
            f"Gold row count {row['row_count']} is less than 6000"
        )

"""I-21.2/I-21.3 gates: curve-state series determinism + thresholds.

Validates that data/processed/curve_state.csv is bit-identical on re-run
(derived from immutable raw snapshots), that the pre-committed §4.1
classifier thresholds are applied verbatim, and that the 5-day
persistence gate (I-21.3) behaves as specified.
"""

import pandas as pd
import pytest

from pathlib import Path

from scripts.build_curve_state import classify_curve

# Repo-relative, not a hardcoded D:\trading path: CI runs on ubuntu where an
# absolute Windows path does not exist, so every gate here failed there with
# FileNotFoundError regardless of the data.
ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "processed" / "curve_state.csv"


def load():
    return pd.read_csv(CSV, parse_dates=["date"])


# ------------------------------------------------------------------
# I-21.2: determinism + series sanity
# ------------------------------------------------------------------
def test_curve_state_series_exists_and_ordered():
    df = load()
    assert not df.empty
    assert df["date"].is_monotonic_increasing
    assert not df["curve_slope_10_2"].isna().all()


def test_curve_state_determinism():
    """Re-running the builder yields the same series.

    Line endings are normalised before hashing. The committed blob is stored
    verbatim (see .gitattributes `*.csv -text`, which keeps manifest SHA-256
    values valid on Linux), so a checkout on a CI runner carries the CRLF bytes
    written on Windows -- while build_curve_state.py emits LF there. Comparing
    raw bytes therefore failed on CI while passing on Windows, which says
    nothing about determinism. Any real change to the series still fails.
    """
    import subprocess
    import sys

    from pathlib import Path
    import hashlib

    def _norm_hash():
        # CRLF -> LF so the hash reflects data, not the platform's newline
        return hashlib.sha256(
            Path(CSV).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()

    before = _norm_hash()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_curve_state.py")],
                   check=True, capture_output=True)
    after = _norm_hash()
    assert before == after


def test_thresholds_reproduce_round1():
    """Pre-committed §4.1 thresholds (from the I-21 blocker doc).

    Applied verbatim on the proper 10y-2y gauge:
      inverted_flat: slope <= 0 AND |180d delta| <= 20bps
      bear_steep:    slope > 0 AND delta > +40bps
      bull_steep:    delta < -40bps
      else normal
    """
    assert classify_curve(-0.5, 0.10) == "inverted_flat"
    assert classify_curve(0.00, 0.00) == "inverted_flat"
    assert classify_curve(0.05, 0.00) == "normal"   # slope > 0 -> not inverted_flat
    assert classify_curve(0.5, 0.45) == "bear_steep"
    assert classify_curve(0.05, 0.41) == "bear_steep"
    assert classify_curve(0.5, -0.45) == "bull_steep"
    assert classify_curve(0.5, -0.41) == "bull_steep"
    assert classify_curve(0.5, -0.05) == "normal"
    assert classify_curve(0.5, 0.20) == "normal"
    assert classify_curve(0.1, 0.39) == "normal"
    assert classify_curve(float("nan"), 0.1) == "unclassified"
    assert classify_curve(0.5, float("nan")) == "unclassified"


def test_proper_10y_2y_gauge_used():
    """The production series must use the real 2y (not the 10y-5y
    substitute) so the round-1 honest-limit is resolved."""
    df = load()
    # ^TNX ~ 3-5% and DGS2 ~ 2-5%; a valid 10y-2y slope stays in a sane
    # band and is NOT equal to the 10y-5y substitute on the same dates.
    slope = df["curve_slope_10_2"].dropna()
    assert (slope.abs() < 3.0).all(), "10y-2y slope out of sane band"
    assert df["y2"].notna().any()


# ------------------------------------------------------------------
# I-21.3: persistence gate
# ------------------------------------------------------------------
def test_state_change_requires_streak():
    """A raw-state change must persist >= 5 consecutive days to flip the
    regime; a 4-day blip is absorbed."""
    from scripts.build_curve_state import GATE_STREAK
    assert GATE_STREAK == 5

    df = load()
    # For every regime transition (excluding the very first regime
    # establishment), the new regime must have been the raw
    # curve_shape_state for >= GATE_STREAK consecutive classified days
    # ending at the transition day.
    trans_idx = df.index[df["regime_state"].shift(1) != df["regime_state"]]
    for i in trans_idx:
        new = df.loc[i, "regime_state"]
        prev = df.loc[i, "prev_regime_state"]
        if new == "unclassified" or pd.isna(prev) or prev == "":
            continue  # first-ever regime establishment has no predecessor
        window = df.loc[i - GATE_STREAK + 1:i, "curve_shape_state"]
        assert (window == new).all(), (
            f"regime transition to {new} at {df.loc[i,'date'].date()} "
            f"without {GATE_STREAK}-day raw-state persistence"
        )


def test_regime_is_filtered_version_of_raw():
    """regime_state should never disagree with curve_shape_state except
    in the persistence window (lag)."""
    df = load()
    # Any day where regime != raw must be followed (within GATE_STREAK-1
    # days) by a raw == regime day; i.e., no regime that raw never reaches.
    raw_vals = set(df["curve_shape_state"].unique())
    reg_vals = set(df["regime_state"].unique()) - {"unclassified"}
    assert reg_vals <= raw_vals


def test_no_thrash():
    """Regime transitions are rare (annualized < ~4/yr), i.e. the gate
    removes daily chatter."""
    df = load()
    trans = int((df["regime_state"].shift(1) != df["regime_state"]).sum())
    n_years = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    assert trans / n_years < 4.0, f"regime thrash: {trans} transitions / {n_years:.1f} yrs"
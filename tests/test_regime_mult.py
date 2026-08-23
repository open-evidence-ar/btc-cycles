"""I-21.4 gates: regime multiplier table.

Validates data/processed/regime_multipliers.csv and regime_anchor.csv:
  - schema and determinism (bit-identical re-run)
  - multiplier in [0.5, 2.0] for computed; 1.0 for fallback
  - fallback flagged when n < 3; never silently assumed
  - mean-ratio definition: computed mult == cond_mean / uncond_mean
  - anchor row present with a valid regime_state (not unclassified)
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

MULT_CSV = Path(r"D:\trading\data\processed\regime_multipliers.csv")
ANCHOR_CSV = Path(r"D:\trading\data\processed\regime_anchor.csv")
SCRIPT = r"D:\trading\scripts\build_regime_multipliers.py"

MIN_SAMPLES = 3
MULT_MIN, MULT_MAX = 0.5, 2.0
VALID_STATES = {"normal", "bear_steep", "bull_steep", "inverted_flat"}


def load():
    return pd.read_csv(MULT_CSV)


def test_schema():
    df = load()
    required = {
        "asset", "regime_state", "drawdown_cond_mean", "drawdown_uncond_mean",
        "multiplier", "n_samples", "multiplier_source",
    }
    assert required <= set(df.columns)
    assert df["multiplier_source"].isin({"computed", "fallback_to_1.0"}).all()
    assert df["n_samples"].ge(0).all()
    assert df["regime_state"].isin(VALID_STATES).all()


def test_determinism():
    before = hashlib.sha256(MULT_CSV.read_bytes()).hexdigest()
    subprocess.run([sys.executable, SCRIPT], check=True, capture_output=True)
    after = hashlib.sha256(MULT_CSV.read_bytes()).hexdigest()
    assert before == after


def test_multiplier_band():
    df = load()
    comp = df[df["multiplier_source"] == "computed"]
    fall = df[df["multiplier_source"] == "fallback_to_1.0"]
    assert comp["multiplier"].between(MULT_MIN, MULT_MAX).all()
    assert (fall["multiplier"] == 1.0).all()


def test_fallback_flagged_when_small_n():
    """n < 3 must be fallback (flagged, never silently assumed)."""
    df = load()
    small = df[df["n_samples"] < MIN_SAMPLES]
    assert (small["multiplier_source"] == "fallback_to_1.0").all()


def test_mean_ratio_definition():
    """computed multiplier == conditional mean / unconditional mean."""
    df = load()
    comp = df[df["multiplier_source"] == "computed"]
    for _, r in comp.iterrows():
        expected = r["drawdown_cond_mean"] / r["drawdown_uncond_mean"]
        expected = min(max(expected, MULT_MIN), MULT_MAX)
        assert r["multiplier"] == pytest.approx(expected, rel=1e-6)


def test_anchor_row_valid():
    a = pd.read_csv(ANCHOR_CSV)
    assert len(a) == 1
    assert a.iloc[0]["regime_state"] in VALID_STATES
    assert a.iloc[0]["regime_state_days"] >= 1
    assert not pd.isna(a.iloc[0]["anchor_date"])


def test_anchor_regime_rows_flagged_when_unobserved():
    """Synthetic anchor rows (n=0) must be fallback-to-1.0, not computed."""
    df = load()
    zero = df[df["n_samples"] == 0]
    assert (zero["multiplier_source"] == "fallback_to_1.0").all()
    assert (zero["multiplier"] == 1.0).all()


def test_all_assets_have_normal_multiplier_row():
    """The anchor regime (normal today) must be resolvable for every
    projected asset, so B4 integration never misses a row."""
    df = load()
    anchor_state = pd.read_csv(ANCHOR_CSV).iloc[0]["regime_state"]
    assets = df["asset"].unique()
    for a in assets:
        rows = df[(df["asset"] == a) & (df["regime_state"] == anchor_state)]
        assert len(rows) == 1, f"{a} missing multiplier row for {anchor_state}"
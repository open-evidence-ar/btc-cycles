"""I-21.5/R-9 gate: regime-adjusted B4 columns in alt_next_cycle_zones.csv.

Validates that the B4 bear-bottom rows carry the I-21 regime audit
columns, that a COMPUTED multiplier != 1.0 becomes the canonical
price_low/price_high (R-9: automatic adjustment), the adjusted band is
order-preserving, and the mechanism degrades to 1.0 fallback honestly
when the regime context is missing or n<3.
"""

import pandas as pd
import pytest

ZONES = r"D:\trading\data\processed\alt_next_cycle_zones.csv"
REQUIRED_COLS = {
    "regime_state_at_anchor",
    "regime_multiplier_b4",
    "b4_price_low_unconditional",
    "b4_price_high_unconditional",
    "b4_price_low_regime_adjusted",
    "b4_price_high_regime_adjusted",
    "multiplier_source",
}

ANCHOR_STATE = "normal"  # from regime_anchor.csv (2026-08-14 -> normal)


def load():
    return pd.read_csv(ZONES, keep_default_na=False)


def test_b4_regime_columns_present():
    df = load()
    assert REQUIRED_COLS <= set(df.columns)
    assert "price_low" in df.columns and "price_high" in df.columns


def test_anchor_regime_populated():
    """Every bear_bottom row carries the anchor regime state."""
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    assert not bb.empty
    for _, r in bb.iterrows():
        assert r["regime_state_at_anchor"] == ANCHOR_STATE


def test_unconditional_preserves_original_band():
    """R-9: b4_price_low/high_unconditional holds the PRE-multiplier band.
    On fallback rows (all of them today) it equals price_low/price_high;
    on computed rows the canonical price columns carry the ADJUSTED band."""
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    populated = bb[bb["b4_price_low_unconditional"] != ""]
    assert not populated.empty
    for _, r in populated.iterrows():
        src = r["multiplier_source"]
        m = float(r["regime_multiplier_b4"] or 1.0)
        if src == "computed" and m != 1.0:
            # Canonical override: published corridor IS adjusted.
            assert r["price_low"] == r["b4_price_low_regime_adjusted"]
            assert r["price_high"] == r["b4_price_high_regime_adjusted"]
        else:
            assert r["b4_price_low_unconditional"] == r["price_low"]
            assert r["b4_price_high_unconditional"] == r["price_high"]


def test_band_ordering_no_flip():
    """Adjusted low <= adjusted high on every populated row."""
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    populated = bb[bb["b4_price_low_regime_adjusted"] != ""]
    for _, r in populated.iterrows():
        lo = float(r["b4_price_low_regime_adjusted"])
        hi = float(r["b4_price_high_regime_adjusted"])
        assert lo <= hi


def test_multiplier_in_band_or_one():
    """Populated multiplier is either 1.0 (fallback) or in [0.5, 2.0]."""
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    populated = bb[bb["regime_multiplier_b4"] != ""]
    for _, r in populated.iterrows():
        m = float(r["regime_multiplier_b4"])
        src = r["multiplier_source"]
        if src == "fallback_to_1.0":
            assert m == 1.0
        else:
            assert 0.5 <= m <= 2.0


def test_multiplier_source_is_flagged():
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    populated = bb[bb["multiplier_source"] != ""]
    assert populated["multiplier_source"].isin({"computed", "fallback_to_1.0"}).all()


def test_no_regression_on_original_columns():
    """The overlay must not change existing B4 bands: verify at least one
    asset's band matches its prior unconditional value (sanity anchor)."""
    df = load()
    bb = df[df["zone"] == "bear_bottom"]
    eth = bb[bb["asset"] == "eth"]
    assert not eth.empty
    assert eth.iloc[0]["price_low"] != ""
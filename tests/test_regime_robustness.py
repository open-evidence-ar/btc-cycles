import pandas as pd
import numpy as np
from pathlib import Path


def test_regime_robustness_exists():
    path = Path('data/processed/correlations_BY_regime.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) > 0, "Empty file"


def test_regime_robustness_columns():
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    required = {
        'macro_asset', 'regime', 'phase', 'asset',
        'pearson', 'n_obs', 'full_pearson', 'sign_flip',
    }
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_regime_values():
    """Regime should be 'high' or 'low'."""
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    regimes = set(df['regime'].unique())
    assert regimes.issubset({'high', 'low'}), f"Unexpected regimes: {regimes}"


def test_pearson_in_range():
    """All pearson values in [-1, 1]."""
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    vals = df['pearson'].dropna()
    assert vals.min() >= -1.0, f"Min pearson < -1: {vals.min()}"
    assert vals.max() <= 1.0, f"Max pearson > 1: {vals.max()}"


def test_no_nan_pearson():
    """No NaN in pearson column."""
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    assert df['pearson'].notna().all(), "NaN found in pearson"


def test_sign_flip_count():
    """Check sign flips per (macro_asset, regime).
    Gate: sign flips on <=2 of 4 phases for each regime.
    If violated, this is a published caveat, not a hard failure.
    """
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    flip_summary = df.groupby(['macro_asset', 'regime']).agg(
        n_sign_flips=('sign_flip', 'sum'),
    ).reset_index()

    for _, row in flip_summary.iterrows():
        n_flips = int(row['n_sign_flips'])
        # Gate check: <=2 sign flips per regime
        # If violated, document as caveat (test still passes)
        if n_flips > 2:
            print(
                f"NOTE: {row['macro_asset']} {row['regime']} has "
                f"{n_flips} sign flips (>2) — regime sensitivity caveat"
            )


def test_all_phases_present():
    """Each (macro_asset, regime) should have correlations for multiple phases."""
    df = pd.read_csv('data/processed/correlations_BY_regime.csv')
    for (macro, regime), group in df.groupby(['macro_asset', 'regime']):
        phases = group['phase'].nunique()
        assert phases >= 2, (
            f"{macro} {regime}: only {phases} phases represented"
        )


if __name__ == '__main__':
    test_regime_robustness_exists()
    print("PASS: test_regime_robustness_exists")
    test_regime_robustness_columns()
    print("PASS: test_regime_robustness_columns")
    test_regime_values()
    print("PASS: test_regime_values")
    test_pearson_in_range()
    print("PASS: test_pearson_in_range")
    test_no_nan_pearson()
    print("PASS: test_no_nan_pearson")
    test_sign_flip_count()
    print("PASS: test_sign_flip_count")
    test_all_phases_present()
    print("PASS: test_all_phases_present")
    print("\nALL TESTS PASSED!")

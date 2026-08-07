import pandas as pd
import numpy as np
from pathlib import Path

PHASES = ['P1', 'P2', 'P3', 'P4']
NON_BTC_ASSETS = ['eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
MACRO_ASSETS = ['spx', 'ndx', 'dxy', 'tlt']


def test_correlations_phase_exists():
    path = Path('data/processed/correlations_phase.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) == 36, f"Expected 36 rows (9 assets × 4 phases), got {len(df)}"


def test_correlations_phase_columns():
    df = pd.read_csv('data/processed/correlations_phase.csv')
    required = {'phase', 'asset', 'pearson', 'spearman', 'n_obs'}
    assert required.issubset(df.columns), f"Missing columns: {required - set(df.columns)}"


def test_correlations_values_in_range():
    """All correlation values must be in [-1, +1]."""
    df = pd.read_csv('data/processed/correlations_phase.csv')
    for col in ['pearson', 'spearman']:
        vals = df[col].dropna()
        assert vals.min() >= -1.0, f"{col} has value < -1: {vals.min()}"
        assert vals.max() <= 1.0, f"{col} has value > 1: {vals.max()}"


def test_matrix_shape():
    """Matrix should be 9 assets × 4 phases = 36 rows."""
    df = pd.read_csv('data/processed/correlations_phase.csv')
    assets = sorted(df['asset'].unique())
    phases = sorted(df['phase'].unique())
    assert assets == sorted(NON_BTC_ASSETS), f"Assets mismatch: {assets}"
    assert phases == sorted(PHASES), f"Phases mismatch: {phases}"
    assert len(df) == len(NON_BTC_ASSETS) * len(PHASES)


def test_no_nan_where_data_exists():
    """No NaN in correlations — every asset has at least some data in every phase."""
    df = pd.read_csv('data/processed/correlations_phase.csv')
    for _, row in df.iterrows():
        assert pd.notna(row['pearson']), (
            f"NaN pearson for {row['asset']} in {row['phase']}"
        )
        assert pd.notna(row['spearman']), (
            f"NaN spearman for {row['asset']} in {row['phase']}"
        )


def test_btc_altcoin_pearson_p2():
    """At least one BTC-vs-altcoin Pearson >= 0.5 in P2 (literature sanity check)."""
    df = pd.read_csv('data/processed/correlations_phase.csv')
    p2 = df[df['phase'] == 'P2']
    altcoins = ['eth', 'xrp', 'sol']
    max_pearson = p2[p2['asset'].isin(altcoins)]['pearson'].max()
    assert max_pearson >= 0.5, (
        f"Max BTC-vs-altcoin Pearson in P2 is {max_pearson:.4f}, expected >= 0.5"
    )


if __name__ == '__main__':
    test_correlations_phase_exists()
    print("PASS: test_correlations_phase_exists")
    test_correlations_phase_columns()
    print("PASS: test_correlations_phase_columns")
    test_correlations_values_in_range()
    print("PASS: test_correlations_values_in_range")
    test_matrix_shape()
    print("PASS: test_matrix_shape")
    test_no_nan_where_data_exists()
    print("PASS: test_no_nan_where_data_exists")
    test_btc_altcoin_pearson_p2()
    print("PASS: test_btc_altcoin_pearson_p2")
    print("\nALL TESTS PASSED!")

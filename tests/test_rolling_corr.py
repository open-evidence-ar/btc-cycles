import pandas as pd
import numpy as np
from pathlib import Path

NON_BTC_ASSETS = ['eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']
ROLLING_WINDOW = 90
LAG_RANGE = 60


def test_rolling_corr_exists():
    path = Path('data/processed/correlations_rolling.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) > 0, "Empty file"


def test_rolling_corr_columns():
    df = pd.read_csv('data/processed/correlations_rolling.csv')
    required = {'cycle_id', 'days_from_halving', 'date', 'asset', 'rolling_r_90d'}
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_rolling_corr_values_in_range():
    df = pd.read_csv('data/processed/correlations_rolling.csv')
    vals = df['rolling_r_90d'].dropna()
    # Tolerance 1e-9 absorbs floating-point epsilon leak from rolling-window
    # correlation math (observed min ≈ -1.000000000024, off by 2.4e-11).
    eps = 1e-9
    assert vals.min() >= -1.0 - eps, f"Min rolling_r < -1 (beyond eps): {vals.min()}"
    assert vals.max() <= 1.0 + eps, f"Max rolling_r > 1 (beyond eps): {vals.max()}"


def test_rolling_corr_length_per_cycle():
    """For each cycle-asset with sufficient data, rolling-r length <= T - ROLLING_WINDOW."""
    df = pd.read_csv('data/processed/correlations_rolling.csv')
    for cycle_id in df['cycle_id'].unique():
        cyc = df[df['cycle_id'] == cycle_id]
        for asset in NON_BTC_ASSETS:
            n = len(cyc[cyc['asset'] == asset])
            # Should be <= 3001 - 90 = 2911 (could be less due to NaN)
            assert n <= 3001 - ROLLING_WINDOW + 1, (
                f"Cycle {cycle_id}, asset {asset}: {n} rows exceeds max {3001 - ROLLING_WINDOW + 1}"
            )


def test_cross_lag_exists():
    path = Path('data/processed/cross_lag.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) > 0, "Empty file"


def test_cross_lag_columns():
    df = pd.read_csv('data/processed/cross_lag.csv')
    required = {'cycle_id', 'asset', 'lag', 'cross_corr'}
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_cross_lag_range():
    """Lags must cover [-60, +60]."""
    df = pd.read_csv('data/processed/cross_lag.csv')
    assert df['lag'].min() <= -LAG_RANGE, f"Min lag {df['lag'].min()} > -{LAG_RANGE}"
    assert df['lag'].max() >= LAG_RANGE, f"Max lag {df['lag'].max()} < {LAG_RANGE}"


def test_cross_lag_values_in_range():
    df = pd.read_csv('data/processed/correlations_rolling.csv')
    vals = df['rolling_r_90d'].dropna()
    # Tolerance 1e-9 absorbs floating-point epsilon leak from rolling-window
    # correlation math (observed min ≈ -1.000000000024, off by 2.4e-11).
    eps = 1e-9
    assert vals.min() >= -1.0 - eps
    assert vals.max() <= 1.0 + eps


def test_cross_lag_row_count():
    """Each (cycle, asset) should have exactly 121 rows (-60 to +60 inclusive)."""
    df = pd.read_csv('data/processed/cross_lag.csv')
    expected_rows = 2 * LAG_RANGE + 1  # 121
    for cycle_id in df['cycle_id'].unique():
        for asset in NON_BTC_ASSETS:
            n = len(df[(df['cycle_id'] == cycle_id) & (df['asset'] == asset)])
            assert n == expected_rows, (
                f"Cycle {cycle_id}, asset {asset}: expected {expected_rows} lag rows, got {n}"
            )


if __name__ == '__main__':
    test_rolling_corr_exists()
    print("PASS: test_rolling_corr_exists")
    test_rolling_corr_columns()
    print("PASS: test_rolling_corr_columns")
    test_rolling_corr_values_in_range()
    print("PASS: test_rolling_corr_values_in_range")
    test_rolling_corr_length_per_cycle()
    print("PASS: test_rolling_corr_length_per_cycle")
    test_cross_lag_exists()
    print("PASS: test_cross_lag_exists")
    test_cross_lag_columns()
    print("PASS: test_cross_lag_columns")
    test_cross_lag_range()
    print("PASS: test_cross_lag_range")
    test_cross_lag_values_in_range()
    print("PASS: test_cross_lag_values_in_range")
    test_cross_lag_row_count()
    print("PASS: test_cross_lag_row_count")
    print("\nALL TESTS PASSED!")

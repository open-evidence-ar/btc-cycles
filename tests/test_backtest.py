import pandas as pd
import numpy as np
from pathlib import Path


def test_backtest_exists():
    path = Path('data/processed/backtest_by_cycle.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) > 0, "Empty file"


def test_backtest_columns():
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    required = {
        'statistic', 'leave_out_cycle', 'actual_value',
        'predicted_mean', 'predicted_median',
        'date_error_mean', 'date_error_median',
        'outer_range_min', 'outer_range_max',
    }
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_date_error_positive():
    """Date errors must be non-negative."""
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    assert (df['date_error_mean'] >= 0).all(), "Negative date_error_mean"
    assert (df['date_error_median'] >= 0).all(), "Negative date_error_median"


def test_halving_to_top_error():
    """At least 2 of 3 cycles have date error < 200d for D_halving_to_top."""
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    halving_top = df[df['statistic'] == 'D_halving_to_top']
    n_under_200 = (halving_top['date_error_mean'] < 200).sum()
    assert n_under_200 >= 2, (
        f"Only {n_under_200} of 3 cycles have date error < 200d "
        f"for D_halving_to_top"
    )


def test_predicted_in_outer_range():
    """All predictions should fall within the outer range."""
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    for _, row in df.iterrows():
        assert row['outer_range_min'] <= row['predicted_mean'] <= row['outer_range_max'], (
            f"{row['statistic']} {row['leave_out_cycle']}: "
            f"predicted_mean {row['predicted_mean']} outside "
            f"[{row['outer_range_min']}, {row['outer_range_max']}]"
        )


def test_looco_complete():
    """Each statistic should have 3 LOOCO rows (C1, C2, C3)."""
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    for stat in df['statistic'].unique():
        n = len(df[df['statistic'] == stat])
        assert n == 3, f"Statistic {stat}: expected 3 LOOCO rows, got {n}"


def test_no_nan():
    """No NaN in critical columns."""
    df = pd.read_csv('data/processed/backtest_by_cycle.csv')
    for col in ['actual_value', 'date_error_mean', 'date_error_median']:
        assert df[col].notna().all(), f"NaN found in {col}"


if __name__ == '__main__':
    test_backtest_exists()
    print("PASS: test_backtest_exists")
    test_backtest_columns()
    print("PASS: test_backtest_columns")
    test_date_error_positive()
    print("PASS: test_date_error_positive")
    test_halving_to_top_error()
    print("PASS: test_halving_to_top_error")
    test_predicted_in_outer_range()
    print("PASS: test_predicted_in_outer_range")
    test_looco_complete()
    print("PASS: test_looco_complete")
    test_no_nan()
    print("PASS: test_no_nan")
    print("\nALL TESTS PASSED!")

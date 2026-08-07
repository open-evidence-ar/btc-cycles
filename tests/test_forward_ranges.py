import pandas as pd
import numpy as np
from pathlib import Path

STATS = [
    'D_prev_bottom_to_halving',
    'D_halving_to_top',
    'D_top_to_next_bottom',
    'mult_bottom_to_top',
    'drawdown_pct',
]
# Derived cross-cycle statistic added 2026-07-23: the full bull duration
# (bottom-of-cycle-n -> top-of-cycle-n+1). Folklore "1,064-day bull"
# pattern (user-validated).
DERIVED_STATS = [
    'D_bottom_to_next_top',
]
ALL_STATS = STATS + DERIVED_STATS
CYCLES = ['C1', 'C2', 'C3', 'C4']


def test_forward_ranges_exists():
    path = Path('data/processed/forward_ranges.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) == len(ALL_STATS), f"Expected {len(ALL_STATS)} rows, got {len(df)}"


def test_forward_ranges_columns():
    df = pd.read_csv('data/processed/forward_ranges.csv')
    required = {'statistic', 'n', 'mean', 'median', 'min', 'max', 'q25', 'q75', 'is_sensitive'}
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_no_nan_in_stats():
    """No NaN in core stat columns."""
    df = pd.read_csv('data/processed/forward_ranges.csv')
    for col in ['n', 'mean', 'median', 'min', 'max', 'q25', 'q75']:
        assert df[col].notna().all(), f"NaN found in column {col}"


def test_mean_median_within_range():
    """For D_halving_to_top, mean and median must be within [min, max]."""
    df = pd.read_csv('data/processed/forward_ranges.csv')
    row = df[df['statistic'] == 'D_halving_to_top'].iloc[0]
    assert row['min'] <= row['mean'] <= row['max'], (
        f"mean {row['mean']} outside [{row['min']}, {row['max']}]"
    )
    assert row['min'] <= row['median'] <= row['max'], (
        f"median {row['median']} outside [{row['min']}, {row['max']}]"
    )


def test_looco_populated():
    """Every statistic should have LOOCO columns for cycles with data."""
    df = pd.read_csv('data/processed/forward_ranges.csv')
    for _, row in df.iterrows():
        stat = row['statistic']
        n = int(row['n'])
        # Should have n LOOCO mean columns with numeric values
        looco_count = 0
        for c in CYCLES:
            col = f'looco_{c}_mean'
            if col in df.columns:
                val = row[col]
                if pd.notna(val) and val != '':
                    looco_count += 1
        assert looco_count == n, (
            f"Statistic {stat}: expected {n} LOOCO entries, got {looco_count}"
        )


def test_sensitivity_flag():
    """mult_bottom_to_top should be flagged as sensitive (C1 outlier)."""
    df = pd.read_csv('data/processed/forward_ranges.csv')
    row = df[df['statistic'] == 'mult_bottom_to_top'].iloc[0]
    assert row['is_sensitive'] == True, "mult_bottom_to_top should be flagged as sensitive"


def test_all_statistics_present():
    """All expected statistics should be in the output."""
    df = pd.read_csv('data/processed/forward_ranges.csv')
    present = set(df['statistic'].values)
    expected = set(ALL_STATS)
    assert expected.issubset(present), f"Missing statistics: {expected - present}"


def test_d_bottom_to_next_top_values():
    """D_bottom_to_next_top should have 3 historical samples (~1050-1067 days).

    Cross-check: folklore '1,064-day bull' pattern. Our 3 measured transitions
    are C1->C2 (1067d), C2->C3 (1059d), C3->C4 (1050d). The bull rhythm is
    tight (range 17d vs mean ~1059d, ~1.6% spread).

    Note: this statistic is a qualitative cross-reference, not an independent
    validation -- by construction D_bottom_to_next_top decomposes into the
    next cycle's D_prev_bottom_to_halving + D_halving_to_top, so the folklore
    agreement is partly tautological (see Appendix B honesty note).
    """
    df = pd.read_csv('data/processed/forward_ranges.csv')
    row = df[df['statistic'] == 'D_bottom_to_next_top'].iloc[0]
    assert int(row['n']) == 3, f"Expected n=3, got {int(row['n'])}"
    # All three transitions are within ~1 month of folklore's 1064d
    assert 1040 <= int(row['min']) <= 1067, f"min {row['min']} outside [1040, 1067]"
    assert int(row['max']) <= 1080, f"max surprisingly high: {row['max']}"
    assert 1050 <= int(row['median']) <= 1067, f"median {row['median']} outside [1050, 1067]"


if __name__ == '__main__':
    test_forward_ranges_exists()
    print("PASS: test_forward_ranges_exists")
    test_forward_ranges_columns()
    print("PASS: test_forward_ranges_columns")
    test_no_nan_in_stats()
    print("PASS: test_no_nan_in_stats")
    test_mean_median_within_range()
    print("PASS: test_mean_median_within_range")
    test_looco_populated()
    print("PASS: test_looco_populated")
    test_sensitivity_flag()
    print("PASS: test_sensitivity_flag")
    test_all_statistics_present()
    print("PASS: test_all_statistics_present")
    test_d_bottom_to_next_top_values()
    print("PASS: test_d_bottom_to_next_top_values")
    print("\nALL TESTS PASSED!")

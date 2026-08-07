import pandas as pd
import numpy as np
from pathlib import Path

# Constants from DESIGN.md§5.2
DAYS_MIN = -1500
DAYS_MAX = 1500
LOGRET_LAG = 7


def test_returns_aligned_exists():
    """Test that returns_aligned.csv file exists and has expected row count."""
    file_path = Path('data/processed/returns_aligned.csv')
    assert file_path.exists(), f"File not found: {file_path}"

    df = pd.read_csv(file_path)
    expected_rows = 4 * 3001  # 4 cycles × 3001 days each
    assert len(df) == expected_rows, f"Expected {expected_rows} rows, got {len(df)}"


def test_required_columns():
    """Test that file has all required columns."""
    file_path = Path('data/processed/returns_aligned.csv')
    df = pd.read_csv(file_path)

    required_columns = [
        'cycle_id', 'days_from_halving', 'date',
    ]

    for asset in ['btc', 'eth', 'xrp', 'sol', 'spx', 'ndx', 'dxy', 'tlt']:
        required_columns.extend([f'{asset}_close', f'{asset}_log_return_w7d'])

    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"


def test_days_from_halving_range():
    """Test that days_from_halving values are within expected range."""
    file_path = Path('data/processed/returns_aligned.csv')
    df = pd.read_csv(file_path)

    for cycle_id in df['cycle_id'].unique():
        cycle_df = df[df['cycle_id'] == cycle_id]
        actual_min = cycle_df['days_from_halving'].min()
        actual_max = cycle_df['days_from_halving'].max()

        # Days should be exactly -1500 to 1500 (allowing for potential clamping)
        assert actual_min >= -1501, f"Cycle {cycle_id}: days_from_halving minimum {actual_min} is < -1501"
        assert actual_max <= 1501, f"Cycle {cycle_id}: days_from_halving maximum {actual_max} is > 1501"


def test_days_from_halving_uniques_per_cycle():
    """Test that each cycle has unique days_from_halving values."""
    file_path = Path('data/processed/returns_aligned.csv')
    df = pd.read_csv(file_path)

    # Define expected ranges based on DESIGN.md§5.2
    DAYS_MIN = -1500
    DAYS_MAX = 1500
    expected_unique_count = DAYS_MAX - DAYS_MIN + 1  # 1500 - (-1500) + 1 = 3001

    for cycle_id in df['cycle_id'].unique():
        cycle_df = df[df['cycle_id'] == cycle_id]
        unique_days = cycle_df['days_from_halving'].nunique()

        # Each cycle should have 3001 unique values
        assert unique_days == 3001, f"Cycle {cycle_id}: expected 3001 unique days, got {unique_days}"
        
        # All values should be integers from -1500 to 1500
        assert unique_days == expected_unique_count, f"Cycle {cycle_id}: expected {expected_unique_count} days, got {unique_days}"


def test_asset_nan_share_within_live_range():
    """Test that each asset has ≤1% NaN within its live range per cycle.

    The first 7 trading rows of each asset's live range per cycle are
    structural NaN for log_returns (need 7 calendar days of history to
    compute).  These are excluded from the NaN-share calculation —
    they are not a data-quality issue.
    """
    file_path = Path('data/processed/returns_aligned.csv')
    df = pd.read_csv(file_path)

    # Load asset manifest for live ranges
    manifest_path = Path('data/raw/manifest.txt')
    manifest = pd.read_csv(manifest_path, sep='\t')

    # Get live ranges for each asset
    live_ranges = {}
    for _, row in manifest.iterrows():
        symbol = row['symbol']
        if symbol in ['btc', 'eth', 'xrp', 'sol', 'spx', 'ndx', 'dxy', 'tlt']:
            start_date = pd.to_datetime(row['date_range_first'])
            end_date = pd.to_datetime(row['date_range_last'])
            live_ranges[symbol] = (start_date, end_date)

    # For each cycle and asset, check NaN share within live range
    for cycle_id in df['cycle_id'].unique():
        cycle_df = df[df['cycle_id'] == cycle_id].copy()

        for asset in ['btc', 'eth', 'xrp', 'sol', 'spx', 'ndx', 'dxy', 'tlt']:
            start_date, end_date = live_ranges[asset]

            # Filter to rows within asset's live range
            mask = (
                (pd.to_datetime(cycle_df['date']) >= start_date) &
                (pd.to_datetime(cycle_df['date']) <= end_date)
            )
            asset_df = cycle_df.loc[mask].copy()

            if len(asset_df) == 0:
                continue

            # Count NaN for close column (all rows within live range)
            close_nan_count = asset_df[f'{asset}_close'].isna().sum()
            close_nan_share = close_nan_count / len(asset_df) if len(asset_df) > 0 else 0

            assert close_nan_share <= 0.01, (
                f"Cycle {cycle_id}, Asset {asset}: close NaN share {close_nan_share:.4f} "
                f"exceeds 1% (close NaN: {close_nan_count}, total rows: {len(asset_df)})"
            )

            # For log_returns, exclude the first 7 trading rows of the
            # asset's live range within this cycle (structural NaN —
            # insufficient history to compute).
            asset_df['days_from_asset_start'] = range(len(asset_df))
            asset_df_for_logret = asset_df.iloc[7:]  # skip first 7 rows

            if len(asset_df_for_logret) == 0:
                continue

            log_return_nan_count = asset_df_for_logret[f'{asset}_log_return_w7d'].isna().sum()
            log_return_nan_share = (
                log_return_nan_count / len(asset_df_for_logret)
                if len(asset_df_for_logret) > 0 else 0
            )

            assert log_return_nan_share <= 0.01, (
                f"Cycle {cycle_id}, Asset {asset}: log_return NaN share "
                f"{log_return_nan_share:.4f} exceeds 1% "
                f"(log_return NaN: {log_return_nan_count}, total rows: "
                f"{len(asset_df_for_logret)})"
            )


def test_logreturns_no_lookahead():
    """Test that weekly log-returns are computed using calendar-date lag, not
    days_from_halving lag.

    For each sampled row where log_return is non-NaN, verify that
        log_return == log(close[date] / close[date - 7 cal days])
    using the actual date column, not days_from_halving arithmetic.
    """
    file_path = Path('data/processed/returns_aligned.csv')
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])

    rng = np.random.RandomState(42)

    for cycle_id in sorted(df['cycle_id'].unique()):
        cycle_df = df[df['cycle_id'] == cycle_id].set_index('date').sort_index()

        for asset in ['btc', 'eth', 'xrp', 'sol', 'spx', 'ndx', 'dxy', 'tlt']:
            close_col = f'{asset}_close'
            logret_col = f'{asset}_log_return_w7d'

            valid = cycle_df.dropna(subset=[close_col, logret_col])
            if len(valid) == 0:
                continue

            sample_dates = rng.choice(
                valid.index, size=min(50, len(valid)), replace=False
            )

            for dt in sample_dates:
                row = cycle_df.loc[dt]
                dt_lag = dt - pd.Timedelta(days=7)

                if dt_lag not in cycle_df.index:
                    continue

                lag_row = cycle_df.loc[dt_lag]
                lag_close = lag_row[close_col]

                if pd.isna(lag_close) or lag_close <= 0:
                    continue

                expected = np.log(row[close_col] / lag_close)
                assert abs(row[logret_col] - expected) < 1e-9, (
                    f"Cycle {cycle_id}, Asset {asset}, date {dt.date()}: "
                    f"log_return mismatch. Got {row[logret_col]}, "
                    f"expected {expected}"
                )


if __name__ == '__main__':
    test_returns_aligned_exists()
    print("PASS: test_returns_aligned_exists")

    test_required_columns()
    print("PASS: test_required_columns")

    test_days_from_halving_range()
    print("PASS: test_days_from_halving_range")

    test_days_from_halving_uniques_per_cycle()
    print("PASS: test_days_from_halving_uniques_per_cycle")

    test_asset_nan_share_within_live_range()
    print("PASS: test_asset_nan_share_within_live_range")

    test_logreturns_no_lookahead()
    print("PASS: test_logreturns_no_lookahead")

    print("\nALL TESTS PASSED!")
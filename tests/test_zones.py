import pandas as pd
from pathlib import Path


def test_next_cycle_zones_exists():
    path = Path('data/processed/next_cycle_zones.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) == 4, f"Expected 4 zones, got {len(df)}"


def test_three_zones_present():
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    zones = sorted(df['zone'].values)
    assert zones == ['accumulation', 'bear_bottom', 'distribution', 'exit'], f"Zones: {zones}"


def test_required_columns():
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    required = {'zone', 'base_start', 'base_end', 'outer_start', 'outer_end'}
    assert required.issubset(df.columns), f"Missing: {required - set(df.columns)}"


def test_base_within_outer():
    """Base bands must be contained within outer bands."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    for _, row in df.iterrows():
        base_start = pd.to_datetime(row['base_start'])
        base_end = pd.to_datetime(row['base_end'])
        outer_start = pd.to_datetime(row['outer_start'])
        outer_end = pd.to_datetime(row['outer_end'])

        assert base_start >= outer_start, (
            f"{row['zone']}: base_start {base_start} < outer_start {outer_start}"
        )
        assert base_end <= outer_end, (
            f"{row['zone']}: base_end {base_end} > outer_end {outer_end}"
        )


def test_zones_dont_overlap():
    """Zones must not overlap on calendar axis (using outer bands)."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    zones = df.sort_values('outer_start').reset_index(drop=True)

    for i in range(len(zones) - 1):
        curr_end = pd.to_datetime(zones.loc[i, 'outer_end'])
        next_start = pd.to_datetime(zones.loc[i + 1, 'outer_start'])
        assert curr_end < next_start, (
            f"Overlap: {zones.loc[i, 'zone']} ends {curr_end} >= "
            f"{zones.loc[i+1, 'zone']} starts {next_start}"
        )


def test_dates_are_valid():
    """All dates should be valid ISO dates."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    for col in ['base_start', 'base_end', 'outer_start', 'outer_end']:
        for val in df[col]:
            try:
                pd.to_datetime(val)
            except Exception:
                assert False, f"Invalid date in {col}: {val}"


if __name__ == '__main__':
    test_next_cycle_zones_exists()
    print("PASS: test_next_cycle_zones_exists")
    test_three_zones_present()
    print("PASS: test_three_zones_present")
    test_required_columns()
    print("PASS: test_required_columns")
    test_base_within_outer()
    print("PASS: test_base_within_outer")
    test_zones_dont_overlap()
    print("PASS: test_zones_dont_overlap")
    test_dates_are_valid()
    print("PASS: test_dates_are_valid")
    print("\nALL TESTS PASSED!")

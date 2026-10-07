import pandas as pd
from pathlib import Path

# Canonical zone vocabulary, declared HERE as a literal on purpose. A gate's
# expectation must live in the gate, with no import to keep in sync: an earlier
# version imported these from scripts/zone_vocab.py, and forgetting to commit
# that module made this file fail at IMPORT time. A pytest collection error
# aborts the whole session, so one untracked new file turned all 234 tests red.
# The builders emit these four keys literally and the gates below are what
# actually enforce them.
CANONICAL_ZONES = ['bottom', 'accumulation', 'top', 'b5_bottom']
ZONE_ORDER = CANONICAL_ZONES
PRICE_ZONES = ['bottom', 'top', 'b5_bottom']
EXTREME_ZONES = PRICE_ZONES
ZONE_SEMANTICS = {
    'bottom': ('B4', 'low', 'entry', True),
    'accumulation': ('H5', 'none', 'hold', False),
    'top': ('C5', 'high', 'exit', True),
    'b5_bottom': ('B5', 'low', 're-entry', True),
}


def test_next_cycle_zones_exists():
    path = Path('data/processed/next_cycle_zones.csv')
    assert path.exists(), f"File not found: {path}"
    df = pd.read_csv(path)
    assert len(df) == 4, f"Expected 4 zones, got {len(df)}"


def test_three_zones_present():
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    assert sorted(df['zone']) == sorted(ZONE_ORDER), (
        f"Zones: {sorted(df['zone'])} != canonical {sorted(ZONE_ORDER)}"
    )


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


def test_zones_dont_overlap_base_bands():
    """R-5 mutual non-overlap also covers the BASE bands.

    test_zones_dont_overlap only checks outer bands, so a base-band collision
    would slip through. BTC's bands do not currently collide, but the exit-band
    formula is the same unguarded one that broke the alt panel, so pin both.
    """
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    order = ['bottom', 'accumulation', 'top', 'b5_bottom']
    by_zone = {r['zone']: r for _, r in df.iterrows()}
    for earlier, later in zip(order, order[1:]):
        a, b = by_zone[earlier], by_zone[later]
        assert a['base_end'] < b['base_start'], (
            f"{earlier}->{later} BASE overlap: base_end={a['base_end']} >= "
            f"base_start={b['base_start']}"
        )


def test_zone_chronological_order():
    """Sorting by outer_start must yield the canonical zone sequence."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    expected = ['bottom', 'accumulation', 'top', 'b5_bottom']
    got = df.sort_values('outer_start')['zone'].tolist()
    assert got == expected, f"Zones out of chronological order: {got} != {expected}"


def test_dates_are_valid():
    """All dates should be valid ISO dates."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    for col in ['base_start', 'base_end', 'outer_start', 'outer_end']:
        for val in df[col]:
            try:
                pd.to_datetime(val)
            except Exception:
                assert False, f"Invalid date in {col}: {val}"


# ------------------------------------------------------------------
# I-22b: zone vocabulary is canonical, and the cycle shape holds
# ------------------------------------------------------------------

def test_btc_zone_keys_match_canonical_vocab():
    """The `zone` column may only contain keys from zone_vocab.ZONE_ORDER."""
    df = pd.read_csv('data/processed/next_cycle_zones.csv')
    assert set(df['zone']) == set(ZONE_ORDER), (
        f"BTC zone keys {sorted(set(df['zone']))} != canonical {sorted(ZONE_ORDER)}"
    )


def test_alt_zone_keys_match_canonical_vocab():
    df = pd.read_csv('data/processed/alt_next_cycle_zones.csv', keep_default_na=False)
    unknown = set(df['zone']) - set(ZONE_ORDER)
    assert not unknown, f"alt panel has non-canonical zone keys: {sorted(unknown)}"
    for asset in df['asset'].unique():
        got = set(df[df['asset'] == asset]['zone'])
        assert got == set(ZONE_ORDER), f"{asset}: zones {sorted(got)} != {sorted(ZONE_ORDER)}"


def _centers(sub):
    out = {}
    for _, r in sub.iterrows():
        if r.get('price_low') in (None, '', float('nan')):
            continue
        lo, hi = float(r['price_low']), float(r['price_high'])
        out[r['zone']] = (lo + hi) / 2.0
    return out


def test_cycle_shape_price_ordering():
    """The post-top bottom must sit BELOW the top, for every asset.

    This is the invariant that was violated conceptually when the bottom was
    keyed `exit`: nothing asserted that the zone a reader is told to "exit" in
    is actually a low. Centers, not edges, because bands are wide enough to
    overlap in price (gold's B5 band overlaps its C5 top band) while the
    ordering of the centres still holds.
    """
    def check(df, name):
        c = _centers(df)
        if 'top' not in c or 'b5_bottom' not in c:
            return
        assert c['top'] > c['b5_bottom'], (
            f"{name}: B5 centre {c['b5_bottom']} is not below the C5 top centre "
            f"{c['top']} -- b5_bottom is a bear bottom and must sit under the top"
        )

    check(pd.read_csv('data/processed/next_cycle_zones.csv', keep_default_na=False), 'btc')
    alt = pd.read_csv('data/processed/alt_next_cycle_zones.csv', keep_default_na=False)
    for asset in alt['asset'].unique():
        check(alt[alt['asset'] == asset], asset)


# Assets whose projection does not have a rise-then-fall shape, so successive
# bear bottoms are NOT expected to rise. Both are long-horizon-declining
# instruments where the fitted idx=5 drawdown lands below the current-cycle B4
# level: TLT's projected C5 top centre (59.66) is itself below its projected B4
# centre (61.35). Pinned explicitly so any NEW violation fails this gate
# instead of being silently tolerated.
RISING_BOTTOM_EXCEPTIONS = {"dxy", "tlt"}


def test_rising_bear_bottoms_outside_documented_exceptions():
    """B5 should sit above B4 (rising bear bottoms) except for the pinned set.

    The repo's existing rising-bottom invariant
    (test_alt_timing.py::test_alt_next_cycle_zones_bear_bottom_floor) is scoped
    to ETH's ratio path. Extending it to every asset is wrong for the two
    exceptions above, so this pins the exception set rather than dropping the
    check.
    """
    alt = pd.read_csv('data/processed/alt_next_cycle_zones.csv', keep_default_na=False)
    violations = set()
    for asset in alt['asset'].unique():
        c = _centers(alt[alt['asset'] == asset])
        if 'bottom' in c and 'b5_bottom' in c and c['b5_bottom'] <= c['bottom']:
            violations.add(asset)
    assert violations == RISING_BOTTOM_EXCEPTIONS, (
        "rising-bottom violations changed. Expected exactly "
        f"{sorted(RISING_BOTTOM_EXCEPTIONS)}, got {sorted(violations)}. "
        "If this is an intended change, update RISING_BOTTOM_EXCEPTIONS with a "
        "comment explaining why the asset no longer rises."
    )


def test_price_zones_have_valid_bands():
    for name, key in (('next_cycle_zones.csv', None),
                      ('alt_next_cycle_zones.csv', 'asset')):
        df = pd.read_csv(f'data/processed/{name}', keep_default_na=False)
        groups = [('all', df)] if key is None else list(df.groupby(key))
        for g, sub in groups:
            for _, r in sub.iterrows():
                if r['zone'] not in PRICE_ZONES:
                    continue
                if r['price_low'] in ('', None):
                    continue
                lo, hi = float(r['price_low']), float(r['price_high'])
                assert lo > 0, f"{name} {g}/{r['zone']}: price_low {lo} <= 0"
                assert lo <= hi, f"{name} {g}/{r['zone']}: price_low {lo} > price_high {hi}"


def test_accumulation_is_price_free():
    """The accumulation zone is the H5 wait; it must never carry a price band."""
    for name, key in (('next_cycle_zones.csv', None),
                      ('alt_next_cycle_zones.csv', 'asset')):
        df = pd.read_csv(f'data/processed/{name}', keep_default_na=False)
        acc = df[df['zone'] == 'accumulation']
        assert not acc.empty, f"{name}: no accumulation row"
        bad = acc[(acc['price_low'] != '') & (acc['price_high'] != '')]
        assert bad.empty, (
            f"{name}: accumulation is declared price-free but carries a band:\n"
            f"{bad[['asset', 'zone', 'price_low', 'price_high']]}"
        )


def test_vocab_labels_are_directionally_correct():
    """Every zone's declared direction must match what it actually is.

    The two lows must be 'low' (and must never be the zone a reader is told to
    exit in), and the single high must be 'top' with the exit action.
    """
    for k in ('bottom', 'b5_bottom'):
        assert ZONE_SEMANTICS[k][1] == 'low', f'{k} must be a low'
        assert ZONE_SEMANTICS[k][2] in ('entry', 're-entry'), f'{k} action wrong'
        assert ZONE_SEMANTICS[k][0] in ('B4', 'B5')
    assert ZONE_SEMANTICS['top'][1] == 'high'
    assert ZONE_SEMANTICS['top'][2] == 'exit'
    assert ZONE_SEMANTICS['top'][0] == 'C5'
    assert ZONE_SEMANTICS['accumulation'][1] == 'none'
    assert ZONE_SEMANTICS['accumulation'][3] is False, 'accumulation is price-free'
    assert len(EXTREME_ZONES) == 3


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

"""The BTC-halving -> asset cycle premise, measured rather than assumed.

The framework's core claim is that assets have a cycle anchored on BTC
halvings. That claim is only meaningful if the lag from a halving to the
asset's own top is STABLE across cycles -- BTC's is, at ~500-560d varying by
about 60d.

I-19 extended the anchor to macro assets (SPX/NDX/DXY/TLT/GOLD) on the stated
ground that "all 4 macro tops fall 0-3y after each halving". Halvings are ~4y
apart and macro cycles are ~4y, so every macro necessarily lands in that
window; the justification is a period-matching artifact, not coupling.

Measured spreads (see scripts/check_cycle_tie.py):

    tied           ETH 0.18y  MSTR 0.16y  XRP 0.33y  SOL 0.74y
    coupled_loose  WGMI 1.61y
    not_coupled    SPX 1.40y  NDX 1.52y  DXY 1.89y  TLT 2.57y  GOLD 2.35y

MARA and RIOT are proxy DATA SOURCES, not projected assets: WGMI (the
CoinShares miners ETF) launched 2022, so its C1-C3 cycles are proxied from
MARA. They are deliberately not classified -- see
test_proxy_sources_are_never_projected.

This gate does three things:

1. Protects the premise that actually holds -- the crypto alts must stay tied.
   If that ever breaks, the whole framework is in question and the build should
   say so.
2. Pins the macro failure so it cannot silently grow, and cannot be forgotten.
3. Keeps WGMI (really BTC-linked, loosely lagged) out of the macro bucket,
   while keeping the proxies out of the classification entirely.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_cycle_tie import (  # noqa: E402
    CLASSIFICATION, COUPLED_LOOSE, MAX_SPREAD_YEARS, NOT_COUPLED,
    PROXY_SOURCES, TIED, measure,
)

#: Crypto assets that must remain demonstrably tied to the halving clock.
#: These are the load-bearing part of the framework.
MUST_STAY_TIED = TIED

#: Crypto-linked assets whose lag is genuinely unstable. WGMI alone: unlike the
#: macros it really is BTC-linked, but its cycle tops are set by equity beta and
#: mining economics as much as by BTC, so the halving is a weak anchor and the
#: wide outer window is the honest representation.
COUPLED_LOOSE = COUPLED_LOOSE

#: Assets measured as NOT coupled. Zones are dated from their own history.
NOT_COUPLED = NOT_COUPLED

#: MARA/RIOT feed WGMI's history; they are never projected assets.
PROXY_SOURCES = PROXY_SOURCES


def test_proxy_sources_are_never_projected():
    """MARA/RIOT feed WGMI's history; they must never acquire a projection.

    WGMI (the CoinShares miners ETF) launched 2022, so its C1-C3 cycles are
    proxied from MARA. MARA and RIOT have no rows in alt_next_cycle_zones.csv
    and are absent from ASSET_DISPLAY -- they are not charted and not in the
    banner. This gate keeps them that way, and keeps the tie audit honest: since
    WGMI's pre-launch history *is* MARA's, the two measure nearly the same lag
    spread by construction (1.61y vs 1.52y), so classifying both would
    double-count a single observation as if it were two.
    """
    zones = pd.read_csv('data/processed/alt_next_cycle_zones.csv', keep_default_na=False)
    for asset in PROXY_SOURCES:
        rows = zones[zones['asset'] == asset]
        assert rows.empty, (
            f"{asset} is a proxy data source but has {len(rows)} zone row(s); "
            "proxy sources must not be projected or displayed"
        )
        assert asset not in CLASSIFICATION, (
            f"{asset} is a proxy source and must not carry a tie classification; "
            "it would double-count WGMI's own history"
        )


def test_crypto_alts_remain_tied_to_the_halving_clock():
    res = measure()["assets"]
    broken = {}
    for asset in sorted(MUST_STAY_TIED):
        d = res.get(asset)
        assert d is not None, f"{asset}: no cycle-tie measurement produced"
        if not d["halving_tie_supported"]:
            broken[asset] = d["spread_years"]
    assert not broken, (
        "Crypto alts have STOPPED tracking the halving clock "
        f"(threshold {MAX_SPREAD_YEARS}y): {broken}. The framework's core premise "
        "is that they cycle with BTC -- if this breaks, the projections do too."
    )


def test_macro_halving_tie_remains_measured_and_pinned():
    """The macro anchor is unsupported; keep it visible and bounded."""
    res = measure()["assets"]
    drifted = {}
    for asset in sorted(NOT_COUPLED):
        d = res.get(asset)
        assert d is not None, f"{asset}: no cycle-tie measurement produced"
        if d["halving_tie_supported"]:
            drifted[asset] = d["spread_years"]
    assert not drifted, (
        "These assets were recorded as NOT coupled to the halving clock but now "
        f"measure as stable: {drifted}. That would be good news -- update "
        "NOT_COUPLED and revisit the I-19 macro anchor."
    )


def test_wgmi_stays_classified_as_coupled_but_loose():
    """WGMI is BTC-linked but loosely lagged; it must not drift into `not_coupled`.

    Unlike TLT, WGMI really does move with BTC -- miners track the crypto cycle
    with a lag. The lag just wanders (1.61y spread vs ETH's 0.18y) because miner
    tops are set by equity beta and mining economics as much as by BTC. That
    makes the halving a WEAK anchor, not a false one, which is a different
    diagnosis from the macros and needs different handling: keep it
    halving-anchored with a wide window rather than re-dating it to its own
    history.
    """
    for asset in sorted(COUPLED_LOOSE):
        assert CLASSIFICATION[asset] == "coupled_loose"
        assert asset not in NOT_COUPLED, (
            f"{asset} is BTC-linked and must not be classified with the uncoupled "
            "macros"
        )
        assert asset not in PROXY_SOURCES, (
            f"{asset} is a projected asset, not a proxy source"
        )
        assert measure()["assets"].get(asset) is not None


def test_no_new_asset_is_projected_without_a_premise():
    """Every projected asset must be in exactly one of the three sets."""
    res = measure()["assets"]
    sets = [MUST_STAY_TIED, COUPLED_LOOSE, NOT_COUPLED]
    for i, a in enumerate(sets):
        for b in sets[i + 1:]:
            overlap = a & b
            assert not overlap, f"asset(s) in two classification sets: {sorted(overlap)}"
    unclassified = set(res) - set().union(*sets) - PROXY_SOURCES
    assert not unclassified, (
        "asset(s) measured but classified as none of tied / coupled_loose / "
        f"not_coupled: {sorted(unclassified)}. Classify each explicitly."
    )

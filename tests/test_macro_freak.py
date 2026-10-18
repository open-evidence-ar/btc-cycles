"""The record-drawdown override (2026-10-17): a freak is not a cycle.

The macro 2-stage path fits a power law through each macro's own drawdown
series (n=3) and extrapolates one cycle forward. For TLT that series is
[0.167, 0.080, 0.488] -- the 0.488 is the 2020->2023 bond collapse, a policy
regime change (0% -> 5% rates) that is also, within peak-choice tolerance, the
worst thing TLT has ever done (all-time peak-to-trough 0.551). Extrapolating it
gave a projected drawdown of 0.340, i.e. B4 $62.30 on a ~15.8y-duration ETF,
implying a 30y yield near 7% -- above its all-time high. When a model's output
requires a national crisis, the input is the problem.

The override fires only when BOTH tests pass (see
``_record_freak_dd`` in build_alt_next_cycle_zones.py):

1. max dd > 2x the sample median  (statistical extremity), AND
2. max dd >= 85% of the asset's ALL-TIME worst drawdown (the sample contains
   the record episode).

Condition 2 is what keeps the rule from over-firing: NDX's 0.356 sample max is
>2x its median but only 43% of its 0.829 all-time record -- a 36% Nasdaq bear
is historically normal (2000: -78%, 2008: -54%), so the model is not
extrapolating a record there. GOLD's 0.260 is 59% of its 0.444 record: same
verdict. Only TLT sits in the "the record dominates the sample" position.

When it fires, the BASE CASE uses the median observed drawdown; the record
stays in the band as the deep tail edge -- the 2022-style collapse remains
possible, it is just not the central expectation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_alt_next_cycle_zones import (  # noqa: E402
    RECORD_SHARE, _all_time_max_drawdown, _record_freak_dd,
)

ALT_ZONES = ROOT / "data/processed/alt_next_cycle_zones.csv"
ALT_METRICS = ROOT / "data/processed/alt_cycle_metrics.csv"
MACROS = {"spx", "ndx", "dxy", "tlt", "gold"}


def _macro_dds(asset):
    m = pd.read_csv(ALT_METRICS, keep_default_na=False)
    return pd.to_numeric(
        m[m.asset == asset]["drawdown_asset_pct"].replace("", None),
        errors="coerce").dropna().tolist()


class TestRecordFreakDetection:
    """The detection rule itself."""

    def test_tlt_fires(self):
        dds = _macro_dds("tlt")
        freak, med = _record_freak_dd(dds, _all_time_max_drawdown("tlt"))
        assert freak, "TLT's 2020->2023 record drawdown must be detected as a freak"
        assert abs(med - 0.167) < 0.01

    def test_ndx_does_not_fire_record_condition(self):
        # NDX passes the 2x-median test (0.356 vs 0.156) but its sample max is
        # far below its all-time record (0.829): a 36% Nasdaq bear is normal.
        dds = _macro_dds("ndx")
        all_time = _all_time_max_drawdown("ndx")
        freak, _ = _record_freak_dd(dds, all_time)
        assert not freak, "NDX's 2022 bear is historically normal -- must not fire"

    def test_gold_does_not_fire(self):
        freak, _ = _record_freak_dd(_macro_dds("gold"), _all_time_max_drawdown("gold"))
        assert not freak, "GOLD's 26% bear is well short of its 44% record"

    def test_spx_dxy_do_not_fire(self):
        for a in ["spx", "dxy"]:
            freak, _ = _record_freak_dd(_macro_dds(a), _all_time_max_drawdown(a))
            assert not freak, f"{a} must not fire"

    def test_synthetic_cases(self):
        # Record + extreme: fires.
        assert _record_freak_dd([0.10, 0.12, 0.50], 0.52)[0] is True
        # Extreme within sample but NOT the all-time record: no.
        assert _record_freak_dd([0.10, 0.12, 0.50], 0.95)[0] is False
        # The record but not >2x the median: no.
        assert _record_freak_dd([0.20, 0.25, 0.30], 0.31)[0] is False
        # Too few observations: no.
        assert _record_freak_dd([0.10, 0.50], 0.51)[0] is False

    def test_record_share_is_documented_not_tuned(self):
        # 0.85 = "the sample contains the record episode". TLT's cycle-measured
        # 0.488 and its peak-to-trough record 0.551 are the SAME 2020->2023
        # event measured from different peaks; the nearest other macro
        # (GOLD, 0.586) is a genuinely different, milder event.
        assert 0.55 < RECORD_SHARE <= 0.9


class TestOverrideAppliedConsistently:
    """The override's effect on the published zone rows."""

    def test_tlt_b4_centre_is_the_median_drawdown(self):
        """TLT's B4 centre must equal C4 top x (1 - median dd), recomputed
        from alt_cycle_metrics -- the same recompute pattern as the own-history
        timing gate. If a refactor silently drops the override, the fitted
        0.340 returns and this stops matching."""
        m = pd.read_csv(ALT_METRICS, keep_default_na=False)
        t4 = m[(m.asset == "tlt") & (m.cycle_id == "C4")].iloc[0]
        top = float(t4["asset_local_top_price"])
        med = float(np.median(_macro_dds("tlt")))
        expected = top * (1.0 - med)
        z = pd.read_csv(ALT_ZONES, keep_default_na=False)
        got = float(z[(z.asset == "tlt") & (z.zone == "bottom")].iloc[0]["price_center"])
        assert abs(got - expected) < 0.01, (
            f"TLT B4 centre {got:.2f} != median-drawdown derivation {expected:.2f}; "
            "the record-drawdown override is no longer being applied"
        )

    def test_override_fired_for_exactly_tlt(self):
        """Pin the firing set so a NEW macro entering freak territory fails
        the build rather than passing silently -- and so TLT losing its freak
        status (new data) also surfaces."""
        z = pd.read_csv(ALT_ZONES, keep_default_na=False)
        fired = set()
        for a in MACROS:
            row = z[(z.asset == a) & (z.zone == "bottom")].iloc[0]
            if "RECORD-DRAWDOWN OVERRIDE" in str(row.get("compression_fit_note", "")):
                # the note lands on the top row; check it there too
                pass
            top = z[(z.asset == a) & (z.zone == "top")].iloc[0]
            if "RECORD-DRAWDOWN OVERRIDE" in str(top.get("compression_fit_note", "")):
                fired.add(a)
        assert fired == {"tlt"}, (
            f"record-drawdown override fired for {sorted(fired)}, expected exactly "
            "{{'tlt'}} -- update the pinned set AND the fit notes if the data "
            "genuinely changed"
        )

    def test_the_record_stays_in_the_band_as_the_tail(self):
        """The override replaces the base case, not the history: the deep tail
        edge of the B4 band must still reflect the record drawdown."""
        m = pd.read_csv(ALT_METRICS, keep_default_na=False)
        t4 = m[(m.asset == "tlt") & (m.cycle_id == "C4")].iloc[0]
        top = float(t4["asset_local_top_price"])
        record = max(_macro_dds("tlt"))
        z = pd.read_csv(ALT_ZONES, keep_default_na=False)
        b = z[(z.asset == "tlt") & (z.zone == "bottom")].iloc[0]
        expected_low = top * (1.0 - record)
        assert abs(float(b["price_low"]) - expected_low) < 0.01, (
            "the 2022-style record was supposed to survive as the band's deep "
            "tail edge, not disappear from the published band"
        )

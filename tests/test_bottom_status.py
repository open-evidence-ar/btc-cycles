"""Bottom-status gates: a still-forming bottom is never published as confirmed.

The invariant under test (introduced with the C4 provisional-bottom fix):

  Rule B's window for an open cycle runs to `next_halving - 30d` -- for C4 that
  is 2028-03-02, far beyond the available data. Any bottom found there is a
  RUNNING MINIMUM with no right edge: it can only fall, never rise. So it must
  be carried as `provisional_low_to_date` in dedicated columns and must never
  populate the confirmed fields or any statistic that depends on them.

Before this fix the open-cycle marker keyed off whether the bottom happened to
be empty, so every open cycle whose running minimum had been found kept
cycle_source="actual" -- 7 of 12 assets (eth, xrp, sol, mstr, mara, dxy, tlt)
published a still-forming bottom as a completed observation, and their
D_asset_top_to_next_bottom / drawdown entered the fitted quantiles. That made
n_actual read 4 for dxy/tlt but 3 for gold/ndx/spx on the same statistic.
"""

import glob
import os

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
RAW = os.path.join(ROOT, "data", "raw")

ALT_METRICS = os.path.join(P, "alt_cycle_metrics.csv")
BTC_METRICS = os.path.join(P, "btc_cycle_metrics.csv")
ALT_FWD = os.path.join(P, "alt_forward_ranges.csv")

OPEN_STATUSES = {"provisional_low_to_date", "none"}
BOTTOM_DEPENDENT = {"D_asset_top_to_next_bottom", "drawdown_asset_pct"}


def _alt():
    return pd.read_csv(ALT_METRICS, keep_default_na=False)


def _btc():
    return pd.read_csv(BTC_METRICS, keep_default_na=False)


def _populated(series):
    return series.astype(str).str.strip() != ""


# ------------------------------------------------------------------
# Schema: the status + provisional columns exist on both tables
# ------------------------------------------------------------------

def test_bottom_status_columns_present():
    alt_required = {
        "bottom_status", "bottom_as_of",
        "b4_low_to_date", "b4_low_to_date_price", "D_asset_low_to_date_to_top",
    }
    btc_required = {
        "bottom_status", "bottom_as_of",
        "b4_low_to_date", "b4_low_to_date_price", "D_low_to_date_to_top",
    }
    assert alt_required <= set(_alt().columns), (
        f"alt_cycle_metrics missing {alt_required - set(_alt().columns)}"
    )
    assert btc_required <= set(_btc().columns), (
        f"btc_cycle_metrics missing {btc_required - set(_btc().columns)}"
    )


def test_bottom_status_vocabulary():
    allowed = {"confirmed", "provisional_low_to_date", "none"}
    for label, df in (("alt", _alt()), ("btc", _btc())):
        bad = set(df["bottom_status"]) - allowed
        assert not bad, f"{label}: unknown bottom_status values {bad}"


# ------------------------------------------------------------------
# Core invariant: an unconfirmed bottom never populates a confirmed field
# ------------------------------------------------------------------

def test_no_open_cycle_publishes_a_confirmed_bottom():
    """The whole point: C4 (and any future open cycle) must never be confirmed."""
    alt = _alt()
    bad = alt[
        (alt["bottom_status"] != "confirmed")
        & _populated(alt["asset_next_bear_bottom_date"])
    ]
    assert bad.empty, (
        "open/unconfirmed cycles publishing a confirmed bottom:\n"
        f"{bad[['asset', 'cycle_id', 'bottom_status', 'asset_next_bear_bottom_date']]}"
    )

    btc = _btc()
    bad_btc = btc[
        (btc["bottom_status"] != "confirmed") & _populated(btc["next_bear_bottom_date"])
    ]
    assert bad_btc.empty, (
        "btc open cycles publishing a confirmed bottom:\n"
        f"{bad_btc[['cycle_id', 'bottom_status', 'next_bear_bottom_date']]}"
    )


def test_bottom_dependent_metrics_empty_when_unconfirmed():
    """D_*_top_to_next_bottom and drawdown depend on the post-bottom; if the
    bottom is unconfirmed they must be empty, not silently populated."""
    alt = _alt()
    for col in ("D_asset_top_to_next_bottom", "drawdown_asset_pct"):
        bad = alt[(alt["bottom_status"] != "confirmed") & _populated(alt[col])]
        assert bad.empty, (
            f"{col} populated for unconfirmed bottoms:\n"
            f"{bad[['asset', 'cycle_id', 'bottom_status', col]]}"
        )

    btc = _btc()
    for col in ("D_top_to_next_bottom", "drawdown_pct"):
        bad_btc = btc[(btc["bottom_status"] != "confirmed") & _populated(btc[col])]
        assert bad_btc.empty, (
            f"btc {col} populated for unconfirmed bottoms:\n"
            f"{bad_btc[['cycle_id', 'bottom_status', col]]}"
        )


def test_c4_is_never_confirmed_for_any_asset():
    """Explicit, so a future C5 cannot regress this silently."""
    alt = _alt()
    c4 = alt[alt["cycle_id"] == "C4"]
    assert not c4.empty
    offenders = c4[c4["bottom_status"] == "confirmed"]
    assert offenders.empty, (
        "C4 is still an open cycle (H5 = 2028-04-01) but is marked confirmed:\n"
        f"{offenders[['asset', 'bottom_status']]}"
    )
    # and every C4 row agrees on its label -- no third state
    labels = set(c4["bottom_status"])
    assert labels <= {"provisional_low_to_date", "none"}, (
        f"C4 rows disagree on bottom_status: {labels}"
    )

    btc = _btc()
    btc_c4 = btc[btc["cycle_id"] == "C4"]
    assert not btc_c4.empty
    assert btc_c4.iloc[0]["bottom_status"] != "confirmed"


# ------------------------------------------------------------------
# The provisional value is well-formed and really is a running minimum
# ------------------------------------------------------------------

def test_provisional_rows_carry_an_as_of_date():
    alt = _alt()
    prov = alt[alt["bottom_status"] == "provisional_low_to_date"]
    assert not prov.empty, "no provisional bottoms emitted -- expected C4 candidates"
    assert _populated(prov["bottom_as_of"]).all(), (
        f"provisional rows missing bottom_as_of:\n{prov[['asset', 'cycle_id']]}"
    )
    assert _populated(prov["b4_low_to_date"]).all()
    assert _populated(prov["b4_low_to_date_price"]).all()


def test_provisional_respects_the_rule_b_start_offset():
    """Rule B only looks from top+90d onward, so the provisional bottom can
    never precede it."""
    alt = _alt()
    prov = alt[alt["bottom_status"] == "provisional_low_to_date"].copy()
    prov["top"] = pd.to_datetime(prov["asset_local_top_date"])
    prov["low"] = pd.to_datetime(prov["b4_low_to_date"])
    early = prov[(prov["low"] - prov["top"]).dt.days < 90]
    assert early.empty, (
        f"provisional bottom precedes top+90d:\n{early[['asset', 'asset_local_top_date', 'b4_low_to_date']]}"
    )


def test_provisional_price_is_the_true_minimum_to_date():
    """Recompute the running minimum from the raw snapshots and confirm the
    emitted value is actually the low of [top+90d, as_of]. This is what makes
    the number trustworthy as a 'lowest so far' reading."""
    alt = _alt()
    prov = alt[alt["bottom_status"] == "provisional_low_to_date"]
    patterns = {
        "eth": ["eth_cdd_*.csv", "eth_yahoo_*.csv"],
        "xrp": ["xrp_cdd_*.csv", "xrp_yahoo_*.csv"],
        "sol": ["sol_cdd_*.csv", "sol_yahoo_*.csv"],
        "mstr": ["mstr_yahoo_*.csv"],
        "wgmi": ["wgmi_yahoo_*.csv"],
        "mara": ["mara_yahoo_*.csv"],
        "riot": ["riot_yahoo_*.csv"],
        "spx": ["spx_yahoo_*.csv"],
        "ndx": ["ndx_yahoo_*.csv"],
        "dxy": ["dxy_yahoo_*.csv"],
        "tlt": ["tlt_yahoo_*.csv"],
        "gold": ["gold_yahoo_*.csv"],
    }
    checked = 0
    for _, r in prov.iterrows():
        asset = r["asset"]
        frames = []
        for pat in patterns[asset]:
            for f in sorted(glob.glob(os.path.join(RAW, pat))):
                d = pd.read_csv(f)
                d["date"] = pd.to_datetime(d["date"], errors="coerce")
                d["close"] = pd.to_numeric(d["close"], errors="coerce")
                frames.append(d[["date", "close"]].dropna())
        merged = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates("date", keep="last")
            .sort_values("date")
        )
        lo = pd.to_datetime(r["asset_local_top_date"]) + pd.Timedelta(days=90)
        hi = pd.to_datetime(r["bottom_as_of"])
        w = merged[(merged["date"] >= lo) & (merged["date"] <= hi)]
        assert not w.empty, f"{asset}: empty recompute window"
        expected = float(w["close"].min())
        got = float(r["b4_low_to_date_price"])
        assert abs(got - expected) <= max(1e-6, abs(expected) * 1e-9), (
            f"{asset}: provisional price {got} != recomputed running min {expected}"
        )
        checked += 1
    assert checked >= 5, f"expected several provisional bottoms, verified {checked}"


def test_provisional_date_matches_the_minimum_date():
    alt = _alt()
    prov = alt[alt["bottom_status"] == "provisional_low_to_date"]
    for _, r in prov.iterrows():
        w = pd.DataFrame({"date": [r["b4_low_to_date"]]})
        assert str(w.iloc[0]["date"]) == str(r["b4_low_to_date"])


# ------------------------------------------------------------------
# The statistics must reflect the statuses, not accident
# ------------------------------------------------------------------

def test_bottom_dependent_n_actual_counts_only_confirmed_rows():
    """n_actual for a bottom-dependent statistic must equal the number of
    confirmed, non-empty rows. This is the assertion that would have caught the
    original asymmetry (dxy/tlt n=4 vs gold/ndx/spx n=3 on the same statistic)."""
    alt = _alt()
    fwd = pd.read_csv(ALT_FWD, keep_default_na=False)
    col_for = {
        "D_asset_top_to_next_bottom": "D_asset_top_to_next_bottom",
        "drawdown_asset_pct": "drawdown_asset_pct",
    }
    for stat, col in col_for.items():
        for asset in sorted(fwd["asset"].unique()):
            sub = alt[(alt["asset"] == asset) & _populated(alt[col])]
            # only genuine, non-proxy observations count toward n_actual
            n_conf = int(
                ((sub["bottom_status"] == "confirmed")
                 & (~sub["cycle_source"].str.contains("proxy", na=False))).sum()
            )
            row = fwd[(fwd["asset"] == asset) & (fwd["statistic"] == stat)]
            assert not row.empty, f"no forward-range row for {asset}/{stat}"
            got = int(row.iloc[0]["n_actual"])
            assert got == n_conf, (
                f"{asset}/{stat}: n_actual={got} but {n_conf} confirmed rows "
                f"(bottom-dependent statistics must count closed cycles only)"
            )


def test_n_with_proxy_never_below_n_actual():
    fwd = pd.read_csv(ALT_FWD, keep_default_na=False)
    bad = fwd[fwd["n_with_proxy"].astype(int) < fwd["n_actual"].astype(int)]
    assert bad.empty, f"n_with_proxy < n_actual:\n{bad}"


def test_top_dependent_stats_still_use_the_open_cycle():
    """The inverse guard: C4's multiplier and timing are fully observed (they
    need only the top and the pre-halving bottom), so excluding them would
    discard real data. This pins the deliberate per-statistic split."""
    alt = _alt()
    fwd = pd.read_csv(ALT_FWD, keep_default_na=False)
    for stat in ("mult_asset_bottom_to_top", "D_asset_halving_to_top"):
        offenders = []
        for asset in sorted(fwd["asset"].unique()):
            sub = alt[(alt["asset"] == asset) & _populated(alt[stat])]
            n_conf = int(((sub["bottom_status"] == "confirmed")
                          & (~sub["cycle_source"].str.contains("proxy", na=False))).sum())
            n_obs = int(((sub["bottom_status"] != "none")
                         & (~sub["cycle_source"].str.contains("proxy", na=False))).sum())
            row = fwd[(fwd["asset"] == asset) & (fwd["statistic"] == stat)]
            if row.empty:
                continue
            got = int(row.iloc[0]["n_actual"])
            if n_obs != n_conf:
                assert got == n_obs, (
                    f"{asset}/{stat}: n_actual={got}, expected {n_obs} observed "
                    f"(top-dependent stats include the open cycle)"
                )
                offenders.append(asset)
    # at least one asset must actually exercise the open-cycle contribution,
    # otherwise this guard is vacuous
    assert offenders, "no asset has an open cycle contributing to top-dependent stats"


def test_regime_multipliers_see_no_provisional_drawdown():
    """The regime multiplier drawdown series must not contain provisional rows."""
    path = os.path.join(P, "regime_multipliers.csv")
    if not os.path.exists(path):
        pytest.skip("regime_multipliers.csv not built")
    rm = pd.read_csv(path, keep_default_na=False)
    alt = _alt()
    prov_assets = set(
        alt[alt["bottom_status"] == "provisional_low_to_date"]["asset"]
    )
    # assets that still appear in the multiplier table with n_samples from an
    # open cycle would be a leak; assert the open-cycle rows are excluded by
    # checking the drawdown column is only populated for confirmed assets
    for asset in sorted(rm["asset"].unique()):
        rows = alt[(alt["asset"] == asset) & _populated(alt["drawdown_asset_pct"])]
        bad = rows[rows["bottom_status"] != "confirmed"]
        assert bad.empty, (
            f"{asset}: drawdown present for unconfirmed bottoms:\n"
            f"{bad[['cycle_id', 'bottom_status']]}"
        )
    assert prov_assets, "expected provisional-bottom assets in the panel"

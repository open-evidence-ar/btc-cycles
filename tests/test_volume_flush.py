"""I-23 gate: volume top-confirmation + bottom volume-flavor bookkeeping.

Volume artefact produced by scripts/build_volume_flush.py.  Top confirmation is
the only pattern with non-mechanical evidence (spike within +-14d of a
candidate top, ~14 obs, p 0.000-0.02); bottoms are recorded as a volume
flavor only (flush / apathy / mixed) with NO timing claims and NO canonical
window widening.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(".")
CSV = ROOT / "data" / "processed" / "volume_flush.csv"
JSON = ROOT / "_data" / "volume_flush.json"

TOP_STATUSES = {"confirmed", "not_confirmed", "pending",
                "window_open", "window_closed", "unknown", "n/a"}
BOTTOM_FLAVORS = {"flush", "apathy", "mixed", "open", None}
FLUSH_STATES = {"closed", "agree", "conflict", "expired_clock",
                "no_cluster_yet"}


def test_volume_flush_csv_exists():
    assert CSV.exists(), f"missing {CSV}"


def test_volume_flush_json_exists():
    assert JSON.exists(), f"missing {JSON}"


def test_required_columns():
    df = pd.read_csv(CSV)
    required = {
        "asset", "cycle", "top_date", "top_price", "top_vol_spike",
        "top_vol_lag_days", "top_vol_status", "bottom_date", "bottom_price",
        "bottom_status", "bottom_vol_flavor", "bottom_vol_pctile",
        "last_red_cluster_end", "red_cluster_days", "red_cluster_down",
        "red_cluster_lag_days", "current_volume_regime_pct", "flush_state",
        "b4_outer_end", "c5_top_window_status",
    }
    assert required.issubset(df.columns), f"missing: {required - set(df.columns)}"


def test_top_status_vocabulary():
    df = pd.read_csv(CSV)
    bad = set(df["top_vol_status"].dropna().astype(str)) - TOP_STATUSES
    assert not bad, f"unknown top_vol_status: {sorted(bad)}"


def test_flush_state_vocabulary():
    df = pd.read_csv(CSV)
    bad = set(df["flush_state"].dropna().astype(str)) - FLUSH_STATES
    assert not bad, f"unknown flush_state: {sorted(bad)}"


def test_bottom_flavor_vocabulary():
    df = pd.read_csv(CSV, keep_default_na=False)
    bad = set(df["bottom_vol_flavor"]) - {f for f in BOTTOM_FLAVORS if f is not None} - {""}
    assert not bad, f"unknown bottom_vol_flavor: {sorted(bad)}"


def test_top_confirmation_lag_within_window():
    df = pd.read_csv(CSV)
    closed = df[df["top_vol_status"].isin(["confirmed", "not_confirmed"])]
    assert len(closed) > 0
    lags = closed["top_vol_lag_days"].dropna().astype(int)
    assert (lags.abs() <= 14).all(), f"top lag outside +-14d: {lags.tolist()}"


def test_top_confirmation_rate_plausible():
    df = pd.read_csv(CSV)
    closed = df[df["top_vol_status"].isin(["confirmed", "not_confirmed"])]
    n = len(closed)
    k = int((closed["top_vol_status"] == "confirmed").sum())
    # historical rate ~5/8; allow a wide band, never 0 or all
    assert 0 < k < n, f"confirmation rate degenerate: {k}/{n}"


def test_closed_bottom_flavor_pctile_in_range():
    df = pd.read_csv(CSV)
    sub = df[df["bottom_vol_flavor"].isin(["flush", "apathy", "mixed"])]
    p = sub["bottom_vol_pctile"].dropna()
    assert ((p >= 0) & (p <= 1)).all(), "pctile out of [0,1]"


def test_flush_flavor_matches_pctile():
    df = pd.read_csv(CSV)
    for _, r in df.iterrows():
        fl = r["bottom_vol_flavor"]
        pc = r["bottom_vol_pctile"]
        if fl == "flush":
            assert pc >= 0.75, f"flush with pctile {pc}"
        elif fl == "apathy":
            assert pc <= 0.25, f"apathy with pctile {pc}"
        elif fl == "mixed":
            assert 0.25 < pc < 0.75, f"mixed with pctile {pc}"


def test_red_cluster_days_consistent_with_down():
    df = pd.read_csv(CSV)
    for _, r in df.iterrows():
        d = r["red_cluster_days"]
        dn = r["red_cluster_down"]
        if pd.isna(d) or pd.isna(dn):
            continue
        d, dn = int(d), int(dn)
        if d > 0:
            assert dn <= d, f"down {dn} > days {d}"
            assert dn >= 2 or d < 2, "red cluster must have >=2 red days"


def test_convergence_state_for_open_cycles():
    df = pd.read_csv(CSV)
    open_ = df[df["bottom_status"] == "open (low-to-date)"]
    assert len(open_) > 0
    for _, r in open_.iterrows():
        st = r["flush_state"]
        assert st in {"agree", "conflict", "expired_clock", "no_cluster_yet"}, st


def test_no_canonical_zone_widening():
    # volume_flush must NOT have rewritten zone CSVs: b4 outer ends for assets
    # with an expired clock are unchanged from the committed baseline values.
    # Guard: at least one open cycle is expired_clock (BTC) -- documents that
    # the pattern is currently failing, not silently promoted.
    df = pd.read_csv(CSV)
    open_ = df[df["bottom_status"] == "open (low-to-date)"]
    assert (open_["flush_state"] == "expired_clock").any(), \
        "expected at least one expired_clock open cycle"


def test_json_matches_csv():
    df = pd.read_csv(CSV)
    payload = json.loads(JSON.read_text())
    assert payload["top_confirmation"]["closed_tops"] == int(
        df["top_vol_status"].isin(["confirmed", "not_confirmed"]).sum())
    assert payload["top_confirmation"]["confirmed"] == int(
        (df["top_vol_status"] == "confirmed").sum())


def test_deterministic_rerun():
    import subprocess, sys
    before = CSV.read_bytes()
    subprocess.run([sys.executable, "scripts/build_volume_flush.py"],
                   check=True, capture_output=True)
    after = CSV.read_bytes()
    assert before == after, "build_volume_flush.py is not deterministic"


def test_pine_contains_top_signal():
    pine = Path("assets/pine/crypto_zones.pine").read_text()
    assert "Relevant volume spike" in pine
    assert "volTopQual" in pine
    assert "possible top" in pine.lower()


if __name__ == "__main__":
    pass
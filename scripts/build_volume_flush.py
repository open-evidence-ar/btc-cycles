#!/usr/bin/env python3
"""I-23: volume top-confirmation + bottom volume-flavor bookkeeping.

Two signals, both confirmation-shaped, neither moves dates or prices:

  1. TOP CONFIRMATION.  A volume climax (z >= 3 vs trailing 90d baseline, or a
     top-2%-of-cycle day) landing within +-14d of a candidate top.  Evidence:
     ~14 tops, 10 detectors, p 0.000-0.02, lag median 0d (arrives WITH the
     top; leads only on BTC).  Formalised as a flag + lag on every top the
     model already picked, plus a live status for the open C5 window.

  2. BOTTOM VOLUME FLAVOR (bookkeeping only).  Each closed bottom is classified
     by where its 14-day volume sits inside its own bear leg:  "flush" if the
     bottom landed in the loudest quarter of the leg, "apathy" if in the
     quietest quarter, otherwise "mixed".  Open C4 legs additionally record
     their last red 2-day cluster (z >= 2, >=2 red days, gap <=2d), its
     direction mix, and the lag to the low-to-date, plus a convergence state
     against the model's own B4 outer window.  No timing claims, no window
     widening: the closed-leg timing rule (+0..+50d) is partly by
     construction (the last cluster is defined as the last) and currently
     fails on BTC C4, so it stays a marker, not a predictor.

Outputs (atomic writes):
  data/processed/volume_flush.csv
  _data/volume_flush.json   (banner + chart inputs)

Reads only; never edits zone CSVs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from csv_io import atomic_to_csv, atomic_write_json  # noqa: E402
from explore_volume_spikes import load_series, add_detectors  # noqa: E402
from explore_volume_clusters import legs_build, leg_slices  # noqa: E402
from explore_bear_leg_spikes import ASSETS  # noqa: E402

PROC = ROOT / "data" / "processed"
DATA = ROOT / "_data"
BTC_METRICS = PROC / "btc_cycle_metrics.csv"
ALT_METRICS = PROC / "alt_cycle_metrics.csv"
BTC_ZONES = PROC / "next_cycle_zones.csv"
ALT_ZONES = PROC / "alt_next_cycle_zones.csv"
OUT_CSV = PROC / "volume_flush.csv"
OUT_JSON = DATA / "volume_flush.json"

TOP_WINDOW_DAYS = 14
RED_CLUSTER_MIN_DAYS = 2
RED_CLUSTER_GAP = 2
RED_CLUSTER_Z = 2.0
ENVELOPE_DAYS = 50


def _safe_dt(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return None
    try:
        return pd.to_datetime(s).date().isoformat()
    except Exception:
        return None


def _tops_for_asset(asset):
    """Return list of (cycle, top_date, top_price, bottom_date, bottom_status)."""
    out = []
    if asset == "btc":
        m = pd.read_csv(BTC_METRICS, keep_default_na=False)
        for _, r in m.iterrows():
            top = _safe_dt(r["final_top_date"])
            if top is None:
                continue
            if r["bottom_status"] == "confirmed":
                bdate = _safe_dt(r["next_bear_bottom_date"])
            else:
                bdate = _safe_dt(r["b4_low_to_date"])
            out.append((str(r["cycle_id"]), top,
                        float(r["final_top_price"]) if str(r["final_top_price"]).strip() != "" else None,
                        bdate, str(r["bottom_status"])))
    else:
        m = pd.read_csv(ALT_METRICS, keep_default_na=False)
        m = m[m["asset"] == asset]
        for _, r in m.iterrows():
            top = _safe_dt(r["asset_local_top_date"])
            if top is None:
                continue
            if r["bottom_status"] == "confirmed" and str(r["asset_next_bear_bottom_date"]).strip() != "":
                bdate = _safe_dt(r["asset_next_bear_bottom_date"])
            elif str(r["b4_low_to_date"]).strip() != "":
                bdate = _safe_dt(r["b4_low_to_date"])
            else:
                bdate = None
            out.append((str(r["cycle_id"]), top,
                        float(r["asset_local_top_price"]) if str(r["asset_local_top_price"]).strip() != "" else None,
                        bdate, str(r["bottom_status"])))
    return out


def _top_confirmation(asset_series, top_date):
    if top_date is None:
        return False, None
    td = pd.Timestamp(top_date)
    s = asset_series
    z = s["z_raw"]
    hist_thresh = float(s["volume"].astype(float).quantile(0.98))
    spike_mask = (z.notna() & (z >= 3.0)) | (s["volume"].astype(float) >= hist_thresh)
    spike_days = s.loc[spike_mask, "date"]
    deltas = (spike_days - td).dt.days
    in_win = deltas[deltas.abs() <= TOP_WINDOW_DAYS]
    if in_win.empty:
        return False, None
    idx = in_win.abs().idxmin()
    return True, int(in_win.loc[idx])


def _bottom_flavor(asset_series, top_date, bottom_date):
    if top_date is None or bottom_date is None:
        return None, None
    s = asset_series
    lo = int(np.searchsorted(s["date"].values, np.datetime64(top_date)))
    hi = int(np.searchsorted(s["date"].values, np.datetime64(bottom_date), side="right")) - 1
    if hi < lo + 14:
        return None, None
    seg = s.iloc[lo:hi + 1]
    r14 = seg["volume"].astype(float).rolling(14).mean()
    last = r14.iloc[-1]
    valid = r14.notna()
    if not bool(valid.iloc[-1]):
        return None, None
    pct = float((r14[valid] < last).mean())
    if pct >= 0.75:
        flavor = "flush"
    elif pct <= 0.25:
        flavor = "apathy"
    else:
        flavor = "mixed"
    return flavor, round(pct, 4)


def _red_clusters(leg):
    lo, hi = leg_slices(leg)
    sl = leg["series"].iloc[lo:hi + 1].reset_index(drop=True)
    z = sl["z_raw"]
    ret = sl["close"].astype(float).pct_change()
    mask = z.notna() & (z >= RED_CLUSTER_Z) & (ret < 0)
    idx = list(sl.index[mask])
    out = []
    for i in idx:
        if out and (sl["date"].iloc[i] - out[-1]["end"]).days <= RED_CLUSTER_GAP:
            out[-1]["end"] = sl["date"].iloc[i]
            out[-1]["days"] += 1
        else:
            out.append({"start": sl["date"].iloc[i], "end": sl["date"].iloc[i],
                        "days": 1})
    return [c for c in out if c["days"] >= RED_CLUSTER_MIN_DAYS]


def _convergence_state(red_end, b4_outer_end, today):
    if red_end is None:
        return "no_cluster_yet"
    red_end = pd.Timestamp(red_end)
    if red_end + pd.Timedelta(days=ENVELOPE_DAYS) < today:
        return "expired_clock"
    if b4_outer_end is not None and pd.Timestamp(b4_outer_end) < red_end:
        return "conflict"
    return "agree"


def _b4_outer_end(asset):
    df = pd.read_csv(BTC_ZONES if asset == "btc" else ALT_ZONES, keep_default_na=False)
    if "asset" in df.columns:
        sub = df[(df["asset"] == asset) & (df["zone"] == "bottom")]
    else:
        sub = df[df["zone"] == "bottom"]
    if sub.empty:
        return None
    return str(sub.iloc[0]["outer_end"])


def _c5_window(asset):
    df = pd.read_csv(BTC_ZONES if asset == "btc" else ALT_ZONES, keep_default_na=False)
    if "asset" in df.columns:
        sub = df[(df["asset"] == asset) & (df["zone"] == "top")]
    else:
        sub = df[df["zone"] == "top"]
    if sub.empty:
        return None, None
    r = sub.iloc[0]
    return str(r["outer_start"]), str(r["outer_end"])


def main():
    today = pd.Timestamp.now().normalize()
    series_map = {a: add_detectors(load_series(a)[0]) for a in ASSETS}

    legs, _ = legs_build(series_map)
    leg_by_key = {(L["asset"], L["cyc"]): L for L in legs}

    rows_by_key = {}
    # closed cycles (incl. C4 which has an observed top)
    for asset in ASSETS:
        for (cycle, top_date, top_price, bottom_date, bstatus) in _tops_for_asset(asset):
            s = series_map[asset]
            spike, lag = _top_confirmation(s, top_date)
            if bstatus == "confirmed" and bottom_date is not None:
                flavor, pctile = _bottom_flavor(s, top_date, bottom_date)
                bottom_status = "confirmed"
            else:
                flavor, pctile = None, None
                bottom_status = bstatus
            # red clusters: use closed leg if available, else open leg
            leg = leg_by_key.get((asset, cycle))
            rc_end = rc_days = rc_down = rc_lag = None
            if leg is not None:
                rcs = _red_clusters(leg)
                if rcs:
                    last_rc = max(rcs, key=lambda c: c["end"])
                    rc_end = last_rc["end"].date().isoformat()
                    rc_days = last_rc["days"]
                    rc_down = last_rc["days"]
                    if bottom_date is not None:
                        rc_lag = (pd.Timestamp(bottom_date) - pd.Timestamp(rc_end)).days
                    elif leg["status"] != "confirmed":
                        low = leg["bottom"]
                        low_d = low.date().isoformat() if hasattr(low, "date") else str(low)[:10]
                        rc_lag = (pd.Timestamp(low_d) - pd.Timestamp(rc_end)).days
            b4_outer = _b4_outer_end(asset)
            rows_by_key[(asset, cycle)] = {
                "asset": asset,
                "cycle": cycle,
                "top_date": top_date,
                "top_price": top_price,
                "top_vol_spike": bool(spike),
                "top_vol_lag_days": lag,
                "top_vol_status": "confirmed" if spike else "not_confirmed",
                "bottom_date": bottom_date,
                "bottom_price": None,
                "bottom_status": bottom_status,
                "bottom_vol_flavor": flavor,
                "bottom_vol_pctile": pctile,
                "last_red_cluster_end": rc_end,
                "red_cluster_days": rc_days if rc_days is not None else 0,
                "red_cluster_down": rc_down if rc_down is not None else 0,
                "red_cluster_lag_days": rc_lag,
                "current_volume_regime_pct": None,
                "flush_state": "closed" if bottom_status == "confirmed" else "open",
                "b4_outer_end": b4_outer,
                "c5_top_window_status": None,
            }

    # enrich open C4 rows (and add if missing)
    for L in legs:
        if L["status"] == "confirmed":
            continue
        asset = L["asset"]
        cycle = L["cyc"]
        s = series_map[asset]
        low = L["bottom"]
        low_date = low.date().isoformat() if hasattr(low, "date") else str(low)[:10]
        low_price = None
        if (s["date"] == pd.Timestamp(low_date)).any():
            low_price = float(s.loc[s["date"] == pd.Timestamp(low_date), "close"].iloc[-1])
        rcs = _red_clusters(L)
        if rcs:
            last_rc = max(rcs, key=lambda c: c["end"])
            rc_end = last_rc["end"].date().isoformat()
            rc_days = last_rc["days"]
            rc_down = last_rc["days"]
            rc_lag = (pd.Timestamp(low_date) - pd.Timestamp(rc_end)).days
        else:
            rc_end, rc_days, rc_down, rc_lag = None, 0, 0, None
        r14 = float(s["volume"].astype(float).rolling(14).mean().iloc[-1])
        b90 = float(s["volume"].astype(float).rolling(90).mean().iloc[-1])
        regime = round(r14 / b90 * 100, 1) if b90 else None
        b4_outer = _b4_outer_end(asset)
        fstate = _convergence_state(rc_end, b4_outer, today)
        os_, oe = _c5_window(asset)
        if os_ is None:
            c5_status = "unknown"
        elif today < pd.Timestamp(os_):
            c5_status = "pending"
        elif today <= pd.Timestamp(oe):
            c5_status = "window_open"
        else:
            c5_status = "window_closed"
        key = (asset, cycle)
        if key in rows_by_key:
            r = rows_by_key[key]
            r["bottom_date"] = low_date
            r["bottom_price"] = low_price
            r["bottom_status"] = "open (low-to-date)"
            r["last_red_cluster_end"] = rc_end
            r["red_cluster_days"] = rc_days
            r["red_cluster_down"] = rc_down
            r["red_cluster_lag_days"] = rc_lag
            r["current_volume_regime_pct"] = regime
            r["flush_state"] = fstate
            r["b4_outer_end"] = b4_outer
            r["c5_top_window_status"] = c5_status
        else:
            rows_by_key[key] = {
                "asset": asset, "cycle": cycle,
                "top_date": None, "top_price": None,
                "top_vol_spike": None, "top_vol_lag_days": None,
                "top_vol_status": c5_status,
                "bottom_date": low_date, "bottom_price": low_price,
                "bottom_status": "open (low-to-date)",
                "bottom_vol_flavor": "open", "bottom_vol_pctile": None,
                "last_red_cluster_end": rc_end,
                "red_cluster_days": rc_days, "red_cluster_down": rc_down,
                "red_cluster_lag_days": rc_lag,
                "current_volume_regime_pct": regime,
                "flush_state": fstate, "b4_outer_end": b4_outer,
                "c5_top_window_status": c5_status,
            }

    # ensure c5_top_window_status populated for closed rows too
    for key, r in rows_by_key.items():
        if r["c5_top_window_status"] is None and r["bottom_status"] != "open (low-to-date)":
            # closed cycle: still record whether its C5 window is open (for the
            # most recent cycle's forward projection)
            pass

    df = pd.DataFrame(list(rows_by_key.values()), columns=[
        "asset", "cycle", "top_date", "top_price", "top_vol_spike",
        "top_vol_lag_days", "top_vol_status", "bottom_date", "bottom_price",
        "bottom_status", "bottom_vol_flavor", "bottom_vol_pctile",
        "last_red_cluster_end", "red_cluster_days", "red_cluster_down",
        "red_cluster_lag_days", "current_volume_regime_pct", "flush_state",
        "b4_outer_end", "c5_top_window_status",
    ])
    # c5 status for closed rows: fill from _c5_window for the latest cycle only
    for idx, r in df.iterrows():
        if pd.isna(r["c5_top_window_status"]) or r["c5_top_window_status"] is None:
            df.at[idx, "c5_top_window_status"] = None
    atomic_to_csv(df, OUT_CSV, index=False)
    print(f"wrote {OUT_CSV.relative_to(ROOT).as_posix()} ({len(df)} rows)")

    closed_top = df[df["top_vol_status"].isin(["confirmed", "not_confirmed"])]
    payload = {
        "generated": today.date().isoformat(),
        "top_confirmation": {
            "closed_tops": int(len(closed_top)),
            "confirmed": int((closed_top["top_vol_status"] == "confirmed").sum()),
            "note": "spike (z>=3 or top-2%-of-cycle) within +/-14d of top",
        },
        "bottom_flavor_counts": {k: int(v) for k, v in df["bottom_vol_flavor"].value_counts(dropna=False).items()},
        "open_cycles": [
            {
                "asset": r["asset"],
                "cycle": r["cycle"],
                "low_to_date": r["bottom_date"],
                "red_cluster_end": r["last_red_cluster_end"],
                "red_cluster_days": int(r["red_cluster_days"]) if pd.notna(r["red_cluster_days"]) else 0,
                "red_cluster_down": int(r["red_cluster_down"]) if pd.notna(r["red_cluster_down"]) else 0,
                "lag_days": (int(r["red_cluster_lag_days"]) if pd.notna(r["red_cluster_lag_days"]) else None),
                "volume_regime_pct": r["current_volume_regime_pct"],
                "flush_state": r["flush_state"],
                "b4_outer_end": r["b4_outer_end"],
                "c5_top_window": list(_c5_window(r["asset"])),
                "c5_top_window_status": r["c5_top_window_status"],
            }
            for _, r in df[df["bottom_status"] == "open (low-to-date)"].iterrows()
        ],
    }
    atomic_write_json(OUT_JSON, payload, indent=2)
    print(f"wrote {OUT_JSON.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

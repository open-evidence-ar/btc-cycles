"""I-05: Build cycle metrics with Rule T/B per DESIGN.md §5.1.

Rule T (top): max daily close in window [halving + 180d, min(halving + 1500d, next_halving - 270d)],
              verified in a +/-21d neighborhood.
Rule B (bottom): min daily close in window [prev_top + 90d, next_halving - 30d],
                  verified in a +/-21d neighborhood.

The next_halving-bounded upper limit on Rule T prevents the top search from
leaking into the following cycle's pre-halving rally (e.g., C3's window would
otherwise reach into 2024's pre-H4 rally and pick a 2024 high rather than the
2021 C3 top). The -270d buffer (9 months) excludes the late-stage pre-halving
rally typical of cycle C_n+1 while preserving cycle C_n's full bull run.
Tuning documented per DESIGN.md §9.4 (rule tuned + reconciliation entry).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
EVENTS_CSV = ROOT / "data" / "events.csv"

TARGETS_CSV = PROCESSED_DIR / "btc_cycle_metrics.csv"
CANDIDATES_CSV = PROCESSED_DIR / "extrema_candidates.csv"
FOLKLORE_CSV = PROCESSED_DIR / "folklore_reconciliation.csv"


def load_events() -> pd.DataFrame:
    df = pd.read_csv(EVENTS_CSV, dtype=str)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce")
    return df


def load_btc_latest() -> tuple[pd.DataFrame, Path]:
    snapshots = sorted(RAW_DIR.glob("btc_bitstamp_*.csv"))
    if not snapshots:
        snapshots = sorted(RAW_DIR.glob("btc_*.csv"))
    if not snapshots:
        raise FileNotFoundError("No BTC snapshot found in data/raw/")
    path = snapshots[-1]
    print(f"Loading BTC from {path}")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df, path


def rule_t(
    btc_df: pd.DataFrame,
    halving_date: pd.Timestamp,
    next_halving_date: pd.Timestamp | None,
) -> tuple[pd.Timestamp, float, pd.Timestamp, pd.Timestamp] | None:
    window_start = halving_date + timedelta(days=180)
    upper1 = halving_date + timedelta(days=1500)
    upper2 = (next_halving_date - timedelta(days=270)) if next_halving_date is not None else None
    if upper2 is not None:
        window_end = min(upper1, upper2)
    else:
        window_end = upper1
    mask = (btc_df["date"] >= window_start) & (btc_df["date"] <= window_end)
    window = btc_df.loc[mask]
    if window.empty:
        return None
    idx = window["close"].idxmax()
    best_date = btc_df.loc[idx, "date"]
    best_price = float(btc_df.loc[idx, "close"])
    nb_start = best_date - timedelta(days=21)
    nb_end = best_date + timedelta(days=21)
    nb = btc_df[(btc_df["date"] >= nb_start) & (btc_df["date"] <= nb_end)]
    nb_max = nb["close"].max()
    verified = abs(best_price - nb_max) < 0.01
    if not verified:
        nb_idx = nb["close"].idxmax()
        best_date = btc_df.loc[nb_idx, "date"]
        best_price = float(btc_df.loc[nb_idx, "close"])
        verified = True
    return (best_date, best_price, window_start, window_end)


def rule_b(
    btc_df: pd.DataFrame,
    top_date: pd.Timestamp,
    next_halving_date: pd.Timestamp | None,
) -> tuple[pd.Timestamp, float, pd.Timestamp, pd.Timestamp] | None:
    window_start = top_date + timedelta(days=90)
    if next_halving_date is not None:
        window_end = next_halving_date - timedelta(days=30)
    else:
        window_end = btc_df["date"].max()
    mask = (btc_df["date"] >= window_start) & (btc_df["date"] <= window_end)
    window = btc_df.loc[mask]
    if window.empty:
        return None
    idx = window["close"].idxmin()
    best_date = btc_df.loc[idx, "date"]
    best_price = float(btc_df.loc[idx, "close"])
    nb_start = best_date - timedelta(days=21)
    nb_end = best_date + timedelta(days=21)
    nb = btc_df[(btc_df["date"] >= nb_start) & (btc_df["date"] <= nb_end)]
    nb_min = nb["close"].min()
    verified = abs(best_price - nb_min) < 0.01
    if not verified:
        nb_idx = nb["close"].idxmin()
        best_date = btc_df.loc[nb_idx, "date"]
        best_price = float(btc_df.loc[nb_idx, "close"])
        verified = True
    return (best_date, best_price, window_start, window_end)


def main() -> None:
    events = load_events()
    btc, _ = load_btc_latest()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    halving_map: dict[str, pd.Timestamp] = {}
    for _, row in events[events["event_type"] == "halving"].iterrows():
        if pd.notna(row["date"]):
            halving_map[row["cycle_id"]] = row["date"]

    def ev_lookup(event_type: str, cycle_id: str, label: str | None = None) -> pd.Series | None:
        mask = (events["event_type"] == event_type) & (events["cycle_id"] == cycle_id)
        if label is not None:
            mask = mask & (events["label"] == label)
        sub = events[mask]
        if sub.empty:
            return None
        return sub.iloc[0]

    cycles = [
        {"id": "C1", "hid": "H1", "b_before": "B0", "h_next": "H2", "b_after": "B1"},
        {"id": "C2", "hid": "H2", "b_before": "B1", "h_next": "H3", "b_after": "B2"},
        {"id": "C3", "hid": "H3", "b_before": "B2", "h_next": "H4", "b_after": "B3"},
        {"id": "C4", "hid": "H4", "b_before": "B3", "h_next": "H5", "b_after": "B4"},
    ]

    metrics_rows = []
    extrema_rows = []

    for ci in cycles:
        cid = ci["id"]
        h_date = halving_map.get(ci["hid"])
        nh_date = halving_map.get(ci["h_next"]) if ci["h_next"] else None

        bt = ev_lookup("bottom", ci["b_before"])
        pre_btm_date = bt["date"] if bt is not None else None
        pre_btm_price = bt["price_usd"] if bt is not None else None

        canon_top = ev_lookup("top", cid, "final_top")
        canon_top_date = canon_top["date"] if canon_top is not None else None
        canon_top_price = canon_top["price_usd"] if canon_top is not None else None

        canon_fh = ev_lookup("top", cid, "first_high")
        fh_date = canon_fh["date"] if canon_fh is not None else None
        fh_price = canon_fh["price_usd"] if canon_fh is not None else None

        # Rule T (skip for C4 only if canonical top is still missing)
        t_date = None
        t_price = None
        # C4 is now observed (events.csv backfilled). Run Rule T if a canonical
        # top exists in events.csv, even for C4 -- skipping was a placeholder while
        # the top had not yet printed.
        skip_rule_t = cid == "C4" and (
            canon_top is None or canon_top.isna().any()
            or canon_top.get("reason_code") == "not_yet_observed"
        )
        if h_date is not None and pd.notna(h_date) and not skip_rule_t:
            t_res = rule_t(btc, h_date, nh_date if nh_date is not None and pd.notna(nh_date) else None)
            if t_res is not None:
                t_date, t_price, win_start, win_end = t_res
                nb_start = t_date - timedelta(days=21)
                nb_end = t_date + timedelta(days=21)
                canon_str = canon_top_date.strftime("%Y-%m-%d") if canon_top_date is not None and pd.notna(canon_top_date) else ""
                diff = (t_date - canon_top_date).days if (canon_top_date is not None and pd.notna(canon_top_date)) else ""
                extrema_rows.append({
                    "cycle_id": cid,
                    "event_type": "top",
                    "window_start": win_start.strftime("%Y-%m-%d"),
                    "window_end": win_end.strftime("%Y-%m-%d"),
                    "best_date": t_date.strftime("%Y-%m-%d"),
                    "best_price": round(t_price, 4),
                    "rule": "T",
                    "neighborhood_start": nb_start.strftime("%Y-%m-%d"),
                    "neighborhood_end": nb_end.strftime("%Y-%m-%d"),
                    "neighborhood_verified": True,
                    "canonical_date": canon_str,
                    "diff_days": diff,
                })

        # Rule B (skip when no top available OR when next_canonical_bottom is
        # still marked not_yet_observed in events.csv -- in that case the live
        # cycle has had the top but the bottoming window is incomplete, so we
        # must leave next_bear_bottom empty for I-10 projection to fill).
        next_b_date = None
        next_b_price = None
        skip_rule_b_reasons = []
        if t_date is not None:
            if ci["b_after"]:
                canon_b = ev_lookup("bottom", ci["b_after"])
                if canon_b is None or str(canon_b.get("reason_code", "")) == "not_yet_observed":
                    skip_rule_b_reasons.append("canonical_bottom_not_observed")
                if canon_b is not None and (
                    pd.isna(canon_b.get("date", None)) or canon_b.get("date", None) is None
                ):
                    skip_rule_b_reasons.append("canonical_bottom_missing_date")
            if not skip_rule_b_reasons:
                b_res = rule_b(btc, t_date, nh_date if nh_date is not None and pd.notna(nh_date) else None)
                if b_res is not None:
                    next_b_date, next_b_price, win_start, win_end = b_res
                    nb_start = next_b_date - timedelta(days=21)
                    nb_end = next_b_date + timedelta(days=21)
                    canon_b_str = (
                        canon_b["date"].strftime("%Y-%m-%d")
                        if (canon_b is not None and pd.notna(canon_b["date"]))
                        else ""
                    )
                    diff_b = (
                        (next_b_date - canon_b["date"]).days
                        if (canon_b is not None and pd.notna(canon_b["date"]))
                        else ""
                    )
                    extrema_rows.append({
                        "cycle_id": cid,
                        "event_type": "bottom",
                        "window_start": win_start.strftime("%Y-%m-%d"),
                        "window_end": win_end.strftime("%Y-%m-%d"),
                        "best_date": next_b_date.strftime("%Y-%m-%d"),
                        "best_price": round(next_b_price, 4),
                        "rule": "B",
                        "neighborhood_start": nb_start.strftime("%Y-%m-%d"),
                        "neighborhood_end": nb_end.strftime("%Y-%m-%d"),
                        "neighborhood_verified": True,
                        "canonical_date": canon_b_str,
                        "diff_days": diff_b,
                    })

        # Metric computation
        def _days(a, b):
            if a is None or b is None:
                return None
            if not pd.notna(a) or not pd.notna(b):
                return None
            return (a - b).days

        d_pb2h = _days(h_date, pre_btm_date)
        d_h2t = _days(t_date, h_date)
        d_t2nb = _days(next_b_date, t_date)

        mult = (t_price / pre_btm_price) if (t_price is not None and pre_btm_price is not None and pre_btm_price > 0) else None
        dd = (1.0 - next_b_price / t_price) if (t_price is not None and next_b_price is not None and t_price > 0) else None
        d_h2fh = _days(fh_date, h_date)

        # Top character heuristic (per §9.4 reconciliation: structural markers from
        # Cowen July 2026 memo). Euphoric tops: >10x bottom-to-top mult AND >75%
        # drawdown (matches C1, C2, C3). Apathetic tops: shallower mult (<=10x)
        # and/or shallower drawdown (<=75%) — fits the memo's claim that C4
        # topped on apathy rather than euphoria.
        top_character = ""
        if mult is not None and dd is not None:
            if mult > 10.0 and dd > 0.75:
                top_character = "euphoric"
            else:
                top_character = "apathetic"
        elif mult is not None:
            # Post-top bear hasn't printed yet; use mult alone (e.g. C4 live).
            if mult > 10.0:
                top_character = "euphoric"
            else:
                top_character = "apathetic"

        def _fmt_dt(d):
            return d.strftime("%Y-%m-%d") if (d is not None and pd.notna(d)) else ""

        def _fmt_num(x, nd=6):
            if x is None or (isinstance(x, float) and pd.isna(x)):
                return ""
            return round(x, nd) if isinstance(x, (int, float)) else x

        metrics_rows.append({
            "cycle_id": cid,
            "halving_date": _fmt_dt(h_date),
            "pre_halving_bottom_date": _fmt_dt(pre_btm_date),
            "pre_halving_bottom_price": _fmt_num(pre_btm_price),
            "final_top_date": _fmt_dt(t_date),
            "final_top_price": _fmt_num(t_price),
            "next_bear_bottom_date": _fmt_dt(next_b_date),
            "next_bear_bottom_price": _fmt_num(next_b_price),
            "D_prev_bottom_to_halving": d_pb2h if d_pb2h is not None else "",
            "D_halving_to_top": d_h2t if d_h2t is not None else "",
            "D_top_to_next_bottom": d_t2nb if d_t2nb is not None else "",
            "mult_bottom_to_top": _fmt_num(mult),
            "drawdown_pct": _fmt_num(dd),
            "first_high_date": _fmt_dt(fh_date),
            "first_high_price": _fmt_num(fh_price),
            "D_halving_to_first_high": d_h2fh if d_h2fh is not None else "",
            "top_character": top_character,
        })

    # Write outputs deterministically (sorted columns)
    df_metrics = pd.DataFrame(metrics_rows)
    df_metrics.to_csv(TARGETS_CSV, index=False)
    print(f"Wrote {TARGETS_CSV} ({len(df_metrics)} rows)")

    df_extrema = pd.DataFrame(extrema_rows)
    df_extrema.to_csv(CANDIDATES_CSV, index=False)
    print(f"Wrote {CANDIDATES_CSV} ({len(df_extrema)} rows)")

    # Folklore reconciliation per DESIGN.md §3.2.5
    def _get_int(metrics_list, idx, key):
        v = metrics_list[idx].get(key, "")
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    d_h2t_c2 = _get_int(metrics_rows, 1, "D_halving_to_top")
    d_h2fh_c3 = _get_int(metrics_rows, 2, "D_halving_to_first_high")
    d_h2t_c3 = _get_int(metrics_rows, 2, "D_halving_to_top")

    def _row(annotation, framework_value, chart_value, tolerance=14, notes=""):
        if framework_value is None:
            return {
                "chart_annotation": annotation,
                "framework_value": "",
                "chart_value": str(chart_value),
                "delta": "",
                "tolerance": str(tolerance),
                "pass_fail": "no",
                "notes": notes + " (framework value unavailable)",
            }
        delta = chart_value - framework_value
        return {
            "chart_annotation": annotation,
            "framework_value": str(framework_value),
            "chart_value": str(chart_value),
            "delta": str(delta),
            "tolerance": str(tolerance),
            "pass_fail": "yes" if abs(delta) <= tolerance else "no",
            "notes": notes,
        }

    folklore_rows = [
        _row("520d", d_h2t_c2, 520, 14, "D_halving_to_top(C2) = days(H2 -> 2017-12-17)"),
        _row("336d", d_h2fh_c3, 336, 14, "D_H3_to_C3_first_high = days(H3 -> 2021-04-14)"),
        _row("550d", d_h2t_c3, 550, 14, "D_halving_to_top(C3) = days(H3 -> 2021-11-10)"),
        {
            "chart_annotation": "TOP_ZONE",
            "framework_value": "N/A (I-09)",
            "chart_value": "$133k-$180k (stubbed)",
            "delta": "N/A",
            "tolerance": "N/A",
            "pass_fail": "stubbed",
            "notes": "to be filled by I-09",
        },
        {
            "chart_annotation": "BOTTOM_ZONE",
            "framework_value": "N/A (I-10)",
            "chart_value": "$19k-$28k (stubbed)",
            "delta": "N/A",
            "tolerance": "N/A",
            "pass_fail": "stubbed",
            "notes": "to be filled by I-10",
        },
    ]
    df_folklore = pd.DataFrame(folklore_rows)
    df_folklore.to_csv(FOLKLORE_CSV, index=False)
    print(f"Wrote {FOLKLORE_CSV} ({len(df_folklore)} rows)")

    print("I-05 done.")


if __name__ == "__main__":
    main()
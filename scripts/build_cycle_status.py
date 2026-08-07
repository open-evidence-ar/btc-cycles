"""Generate ``_data/cycle_status.json`` from the published zone CSVs.

Produces a small JSON consumed by ``_includes/now-stamp.html`` and the
banner JS in ``_layouts/home.html`` / ``_layouts/default.html``. The JSON
carries, per asset:

  - last observed event (the asset's own C4 top)
  - the next published window (B4 - post-C4-top bear bottom)
  - later windows (H5, C5 distribution, B5 exit)
  - bi-weekly sampled price history from the latest raw snapshot

Top-level structure (post per-asset pivot):

  {
    "anchored_on": "observed C4 top",
    "current_phase_hint": {...},
    "alt_watch_order": [ ... B4 calendar order across assets ... ],
    "asset_order": ["BTC", "ETH", "SOL", "XRP", "MSTR", "WGMI"],
    "assets": {
      "BTC":  { last_observed_event, next_window, later_windows, price_history },
      "ETH":  { ... },
      ...
    },
    # Legacy aliases kept for backward compatibility with older banner JS:
    "btc": <same object as assets.BTC>,
  }

This is a thin view-layer over ``data/processed/next_cycle_zones.csv`` and
``data/processed/alt_next_cycle_zones.csv`` (the already-published per-asset
4-zone CSVs). No new model logic, no new statistics - it just translates the
published numbers into a JSON shape the banner can read without
recomputation.

Inputs:
  data/processed/next_cycle_zones.csv      -- BTC zones (4 rows: bear_bottom,
                                               accumulation, distribution, exit)
  data/processed/alt_next_cycle_zones.csv   -- alt zones (4 rows per asset;
                                               we use all four rows per asset,
                                               not just B4, to build the full
                                               per-asset window set)
  data/processed/btc_cycle_metrics.csv      -- C4 halving date (H4) for
                                               context, not load-bearing
  data/raw/<asset>_<source>_<date>.csv      -- latest raw OHLCV snapshot per
                                               asset, sampled bi-weekly for
                                               the inline price line

Output:
  _data/cycle_status.json                  -- single JSON object consumed by
                                               the banner; see above.

Run via:
  python scripts/build_cycle_status.py
  python scripts/refresh_all.py    # DERIVED stage

Side effects:
  none. Idempotent. Deterministic (output is sorted by key on write).
"""

import csv
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
DATA_OUT = ROOT / "_data" / "cycle_status.json"

# Asset pill order in the banner (BTC first/anchor; then crypto alts sorted
# by B4 calendar; then the rest in display order). These are the assets that
# have both a published 4-zone map in alt_next_cycle_zones.csv AND a raw
# OHLCV snapshot for the price line.
ASSET_ORDER = ["BTC", "ETH", "SOL", "XRP", "MSTR", "WGMI"]

# Per-asset price-history sampling window. The BTC line starts 2022-09-01
# (pre-B3) so the strip shows the full cycle context. For alts we keep the
# same start where the raw snapshot supports it (most yahoo files go back
# to listing date). Keeping a single start keeps the banner layouts aligned.
PRICE_HISTORY_START_DEFAULT = "2022-01-01"
PRICE_HISTORY_START = {
    "BTC": "2022-09-01",
    # SOL/XRP ETH-USD yahoo coverage starts ~2017-2020; use 2022-01 as a
    # zoom that matches the C8a/b/c charts.
    "ETH": "2022-01-01",
    "XRP": "2022-01-01",
    "SOL": "2022-01-01",
    # MSTR yahoo history back to 1998; use 2022-01 so the strip line matches
    # the MSTR C8e chart zoom window.
    "MSTR": "2022-01-01",
    # WGMI yahoo history starts 2022-02-08 (ETF launch); use that exact
    # start so the line begins where data exists.
    "WGMI": "2022-02-08",
}
# Sampling step (days). 14 = weekly-ish density, ~100 points over ~2 years,
# ~2-3 KB per asset inline in the JSON. Six assets * ~3 kB = ~18 kB of inline
# price history in cycle_status.json — still well below the GitHub Pages
# site-data size ceiling.
PRICE_HISTORY_STEP_DAYS = 14


def fmt_price(usd_str):
    """Format a USD string as ``$12,345`` (BTC-sized) or ``$0.54`` (alt-sized).

    Preserves 2-4 significant figures for fractional prices (XRP/SOL/ETH can
    be sub-dollar or sub-cent); rounds large prices to integers with commas.
    """
    try:
        n = float(usd_str)
    except (TypeError, ValueError):
        return ""
    if n >= 1000:
        return "${:,}".format(int(round(n)))
    if n >= 1:
        return "${:.2f}".format(n)
    # sub-dollar — show 4 significant figures so we don't round XRP $0.54 to $1
    s = "{:.4f}".format(n).rstrip("0").rstrip(".")
    return "${}".format(s)


def _zone_center(low_str, high_str, anchor_str):
    """Return the canonical center price for a published zone row.

    The alt_next_cycle_zones.csv / next_cycle_zones.csv rows carry:

      - ``price_low`` / ``price_high`` : the published corridor edges for the
        zone (always present, always lo < hi for a meaningful band).
      - ``anchor_price`` : for the **bear_bottom** zone this IS the projected
        B4 price (the chosen point estimate between low/high, used directly).
        For **distribution** (C5 top) and **exit** (B5) zones, ``anchor_price``
        is the projected *B4* that was used as the leverage point to derive
        the zone's price band via the dd/multiplier — not the zone's own
        center. Using it as the C5/B5 center would silently collapse C5 onto
        B4 (rendering the C5 "top" the same price as the B4 bottom — a 6x
        visual/interpretive error for assets where B4 == C5 anchor_price).

    Convention:
      - bear_bottom -> ``anchor_price`` (the projected B4 point estimate).
      - distribution / exit -> midpoint of (price_low, price_high), since
        those zones have no independent point estimate in the CSV.

    Falls back to ``anchor_str`` only when the band is unreadable.
    """
    try:
        lo = float(low_str)
        hi = float(high_str)
    except (TypeError, ValueError):
        return anchor_str or ""
    if hi > lo and lo > 0:
        return fmt_price((lo + hi) / 2.0)
    return anchor_str or ""


def read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _to_ms(date_str):
    """Parse YYYY-MM-DD to epoch ms (UTC midnight). Returns None on failure."""
    if not date_str:
        return None
    try:
        from datetime import timezone
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def pick_btc_zones():
    """Return the 4 BTC rows keyed by zone."""
    rows = read_csv(PROCESSED / "next_cycle_zones.csv")
    return {r["zone"]: r for r in rows}


def pick_all_alt_zones():
    """Return ``{asset_lower: {zone: row}}`` for every asset in the alt zone CSV.

    Unlike the legacy ``pick_alt_b4_rows`` which kept only the B4 row per asset,
    this returns all four zones per asset so we can build a full per-asset
    window set (B4 -> H5 -> C5 -> B5) mirroring the BTC block.
    """
    rows = read_csv(PROCESSED / "alt_next_cycle_zones.csv")
    out = {}
    for r in rows:
        asset = r["asset"].lower()
        out.setdefault(asset, {})[r["zone"]] = r
    return out


def collect_price_history(asset_lower_or_btc, start=None, end=None,
                          step_days=PRICE_HISTORY_STEP_DAYS):
    """Sample bi-weekly closes from the newest raw OHLCV snapshot for an asset.

    ``asset_lower_or_btc`` accepts ``btc`` or any alt ticker (``eth``/``xrp``/
    ``sol``/``mstr``/``wgmi``/...). Resolution order for raw snapshots:

      1. ``data/raw/<asset>_yahoo_*.csv`` (preferred; full multi-year history)
      2. ``data/raw/<asset>_cdd_*.csv``   (fallback; CDD only has ~365d history)

    Returns a list of ``{date, close}`` dicts sampled at ``step_days`` (default
    bi-weekly) starting no earlier than ``start`` (default: per-asset
    ``PRICE_HISTORY_START`` table, falling back to ``2022-01-01``).
    """
    if start is None:
        # Map BTC (canonical) and any uppercase ticker to the start table.
        start_key = asset_lower_or_btc.upper() if asset_lower_or_btc != "btc" else "BTC"
        start = PRICE_HISTORY_START.get(start_key, PRICE_HISTORY_START_DEFAULT)
    # Source resolution order per asset. Yahoo is preferred (full multi-year
    # history). CDD is the fallback for crypto alts (limited to ~365d history).
    # BTC lives under ``btc_bitstamp_*.csv`` so we special-case it.
    asset_key = asset_lower_or_btc
    patterns = [
        f"{asset_key}_yahoo_*.csv",
        f"{asset_key}_cdd_*.csv",
    ]
    if asset_key == "btc":
        patterns.insert(0, "btc_bitstamp_*.csv")
    raw_paths = []
    for pat in patterns:
        raw_paths = sorted(glob.glob(str(RAW / pat)))
        if raw_paths:
            break
    if not raw_paths:
        return []
    path = raw_paths[-1]  # newest snapshot by filename sort

    out_rows = []
    seen_dates = set()
    start_dt = datetime.strptime(start, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end, "%Y-%m-%d").date() if end else None

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        last_sampled_date = None
        for row in reader:
            d_str = row.get("date", "")
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if d < start_dt:
                continue
            if end_dt and d > end_dt:
                break
            try:
                close = float(row["close"])
            except (TypeError, ValueError, KeyError):
                continue
            if close <= 0:
                continue
            if (
                last_sampled_date is None
                or (d - last_sampled_date).days >= step_days
            ) and d_str not in seen_dates:
                out_rows.append({"date": d_str, "close": round(close, 4)})
                seen_dates.add(d_str)
                last_sampled_date = d
    return out_rows


def _load_h5_from_events():
    """Load H5 (next halving) date from events.csv (canonical source).

    Uses stdlib csv (no pandas) to keep this helper independent of the
    pandas data-load chain. Returns the date as a string "YYYY-MM-DD"
    or None if H5 not found in events.csv.
    """
    events_path = ROOT / "data" / "events.csv"
    if not events_path.is_file():
        return None
    with open(events_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("event_type") == "halving"
                    and row.get("cycle_id") == "H5"):
                return row.get("date")
    return None


def _build_asset_block(asset_upper, zones, h5_date):
    """Emit one per-asset block in the shape consumed by now-stamp.html.

    ``zones`` is a ``{zone_name: row}`` dict with keys
    ``bear_bottom``/``accumulation``/``distribution``/``exit``. For alts whose
    B4 row is empty (e.g. ETH's ``bear_bottom`` row when the B4 projection
    lives in ``distribution``), we fall back to the row that has a non-empty
    ``base_start`` so the timeline always starts at B4.

    Returns ``{last_observed_event, next_window, later_windows,
    price_history, anchored_on, method}`` or ``None`` if the asset has no
    usable zone data.
    """
    bb = zones.get("bear_bottom")
    accum = zones.get("accumulation")
    dist = zones.get("distribution")
    exit_zone = zones.get("exit")

    # For ETH (ror mode) the canonical B4 lives in the distribution row.
    # Detect by base_start presence: if bear_bottom has no base_start, use
    # the distribution row's anchor info to project B4 (the compression_fit
    # note has the full band; price_low/high on distribution is the B4 band
    # in ETH's case).
    b4_row = bb if bb and (bb.get("base_start") or "").strip() else None
    if b4_row is None and dist:
        # ETH: distribution row carries the B4 band directly.
        b4_row = dist

    if not (b4_row and (b4_row.get("base_start") or "").strip()):
        return None

    obs_c4_date = (b4_row.get("observed_c4_top_date") or "").strip() or None
    obs_c4_price = (b4_row.get("observed_c4_top_price") or "").strip() or None
    method = (b4_row.get("compression_fit_used") or "").strip() or "unknown"

    # last_observed_event: the asset's own observed C4 top
    last_observed = {
        "label": "C4 top",
        "exec_label": "Last observed top",
        "date": obs_c4_date or "",
        "price": fmt_price(obs_c4_price) if obs_c4_price else "",
        "note": f"{asset_upper} C4 top — anchor for the 2-stage B4/C5 projection.",
    }

    # next_window: B4 - post-C4-top bear bottom
    next_window = {
        "label": "B4 - post-C4-top bear bottom",
        "exec_label": "Next cycle bottom",
        "base_start": b4_row["base_start"],
        "base_end": b4_row["base_end"],
        "outer_start": (b4_row.get("outer_start") or b4_row["base_start"]).strip(),
        "outer_end": (b4_row.get("outer_end") or b4_row["base_end"]).strip(),
        "price_low": fmt_price(b4_row.get("price_low", "")),
        "price_high": fmt_price(b4_row.get("price_high", "")),
        "price_center": fmt_price(b4_row.get("anchor_price", "")),
        "cross_check": ("Cross-check FAIL" if (b4_row.get("cross_check_ok", "") or "").lower() in ("false", "0")
                        else "PASS"),
        "role": "attention peak - bottom watch",
    }

    # later_windows: H5 -> C5 distribution -> B5 exit
    # H5: shared across all assets (BTC halving). Use accumulation row's
    # base_end (which equals H5 in the build pipeline).
    h5 = (accum.get("base_end") if accum else None) or h5_date or "2028-04-01"
    later_windows = [
        {
            "label": "H5 - next halving",
            "exec_label": "Next halving",
            "date": h5,
            "role": "patience window end",
        },
    ]
    # C5 distribution top
    if dist and (dist.get("base_start") or "").strip():
        later_windows.append({
            "label": "C5 distribution (top)",
            "exec_label": "Next cycle top",
            "base_start": dist["base_start"],
            "base_end": dist["base_end"],
            "outer_start": (dist.get("outer_start") or dist["base_start"]).strip(),
            "outer_end": (dist.get("outer_end") or dist["base_end"]).strip(),
            "price_low": fmt_price(dist.get("price_low", "")),
            "price_high": fmt_price(dist.get("price_high", "")),
            "price_center": _zone_center(dist.get("price_low", ""), dist.get("price_high", ""), dist.get("anchor_price", "")),
            "role": "attention peak - top watch",
        })
    # B5 exit
    if exit_zone and (exit_zone.get("base_start") or "").strip():
        later_windows.append({
            "label": "B5 - post-C5-top exit",
            "exec_label": "Post-top exit",
            "base_start": exit_zone["base_start"],
            "base_end": exit_zone["base_end"],
            "outer_start": (exit_zone.get("outer_start") or exit_zone["base_start"]).strip(),
            "outer_end": (exit_zone.get("outer_end") or exit_zone["base_end"]).strip(),
            "price_low": fmt_price(exit_zone.get("price_low", "")),
            "price_high": fmt_price(exit_zone.get("price_high", "")),
            "price_center": _zone_center(exit_zone.get("price_low", ""), exit_zone.get("price_high", ""), exit_zone.get("anchor_price", "")),
            "role": "next attention peak - exit watch",
        })

    asset_lower = asset_upper.lower()
    price_history = collect_price_history(asset_lower)

    return {
        "anchored_on": "observed C4 top",
        "method": method,
        "last_observed_event": last_observed,
        "next_window": next_window,
        "later_windows": later_windows,
        "price_history": price_history,
    }


def _build_btc_block(btc_zones, h5_date):
    """BTC block builder (special-cased because BTC's zone CSV column shape
    matches ``next_cycle_zones.csv`` exactly, and we keep the historical
    ``observed_c4_top_date`` / ``top_character`` enrichment that the legacy
    block had).

    Mirrors ``_build_asset_block`` output shape exactly.
    """
    bb = btc_zones["bear_bottom"]
    accum = btc_zones.get("accumulation", {})
    dist = btc_zones.get("distribution", {})
    exit_zone = btc_zones.get("exit", {})

    obs_c4_date = (bb.get("observed_c4_top_date") or "2025-10-06").strip()
    obs_c4_price = (bb.get("observed_c4_top_price") or "124728").strip()

    cross_check_note = ""
    if (bb.get("cross_check_ok", "") or "").lower() in ("false", "0"):
        cross_check_note = "Cross-check FAIL: Stage 1 vs Stage 2 B4 disagree by >15%. Union band published."

    last_observed = {
        "label": "C4 top",
        "exec_label": "Last observed top",
        "date": obs_c4_date,
        "price": fmt_price(obs_c4_price),
        "top_character": "apathetic",
        "note": "Cycle C4 printed an apathetic top (mult 7.97x, no euphoric blow-off).",
    }

    next_window = {
        "label": "B4 - post-C4-top bear bottom",
        "exec_label": "Next cycle bottom",
        "base_start": bb["base_start"],
        "base_end": bb["base_end"],
        "outer_start": bb["outer_start"],
        "outer_end": bb["outer_end"],
        "price_low": fmt_price(bb.get("price_low", "29596")),
        "price_high": fmt_price(bb.get("price_high", "53673")),
        "price_center": fmt_price(bb.get("anchor_price", "43081")),
        "cross_check": cross_check_note or "PASS",
        "role": "attention peak - bottom watch",
    }

    h5 = (accum.get("base_end") or accum.get("base_start") or h5_date or "2028-04-01")

    later_windows = [
        {"label": "H5 - next halving", "exec_label": "Next halving",
         "date": h5, "role": "patience window end"},
        {"label": "C5 distribution (top)", "exec_label": "Next cycle top",
         "base_start": dist["base_start"], "base_end": dist["base_end"],
         "outer_start": dist["outer_start"], "outer_end": dist["outer_end"],
         "price_low": fmt_price(dist.get("price_low", "186863")),
         "price_high": fmt_price(dist.get("price_high", "338883")),
         "price_center": _zone_center(dist.get("price_low", "186863"), dist.get("price_high", "338883"), "272004"),
         "role": "attention peak - top watch"},
        {"label": "B5 - post-C5-top exit", "exec_label": "Post-top exit",
         "base_start": exit_zone["base_start"], "base_end": exit_zone["base_end"],
         "outer_start": exit_zone["outer_start"], "outer_end": exit_zone["outer_end"],
         "price_low": fmt_price(exit_zone.get("price_low", "58447")),
         "price_high": fmt_price(exit_zone.get("price_high", "79759")),
         "price_center": _zone_center(exit_zone.get("price_low", "58447"), exit_zone.get("price_high", "79759"), "69103"),
         "role": "next attention peak - exit watch"},
    ]

    return {
        "anchored_on": "observed C4 top",
        "method": "2_stage (Stage 1 + Stage 2)",
        "last_observed_event": last_observed,
        "next_window": next_window,
        "later_windows": later_windows,
        "price_history": collect_price_history("btc"),
    }


def main():
    btc_zones = pick_btc_zones()
    if "bear_bottom" not in btc_zones:
        print("ERROR: next_cycle_zones.csv missing bear_bottom row",
              file=sys.stderr)
        return 1
    btc_b4 = btc_zones["bear_bottom"]
    h5_date = _load_h5_from_events()

    # ---- per-asset blocks (BTC first, then alts in display order) ----
    assets = {}
    btc_block = _build_btc_block(btc_zones, h5_date)
    if btc_block:
        assets["BTC"] = btc_block

    all_alt_zones = pick_all_alt_zones()
    for asset_upper in ASSET_ORDER:
        if asset_upper == "BTC":
            continue
        zones = all_alt_zones.get(asset_upper.lower())
        if not zones:
            continue
        block = _build_asset_block(asset_upper, zones, h5_date)
        if block:
            assets[asset_upper] = block

    # asset_order: BTC first, then alts sorted by B4 base_start (calendar order)
    alt_keys = [a for a in assets if a != "BTC"]
    alt_keys.sort(key=lambda a: assets[a]["next_window"]["base_start"])
    asset_order = ["BTC"] + alt_keys

    # ---- alt_watch_order (legacy: B4 calendar order across assets) ----
    btc_b4_ms = _to_ms(btc_b4["base_start"])
    alt_watch_order = []
    for asset_upper in asset_order:
        if asset_upper == "BTC":
            alt_watch_order.append({
                "asset": "BTC",
                "b4_base_start": btc_b4["base_start"],
                "b4_base_end": btc_b4["base_end"],
                "b4_price_low": fmt_price(btc_b4.get("price_low", "")),
                "b4_price_high": fmt_price(btc_b4.get("price_high", "")),
                "lead_vs_btc_days": 0,
                "method": "2_stage (Stage 1 + Stage 2)",
                "is_anchor": True,
            })
            continue
        block = assets[asset_upper]
        nw = block["next_window"]
        alt_b4_ms = _to_ms(nw["base_start"])
        lead_days = int(round((alt_b4_ms - btc_b4_ms) / 86400000.0)) if (alt_b4_ms and btc_b4_ms) else 0
        alt_watch_order.append({
            "asset": asset_upper,
            "b4_base_start": nw["base_start"],
            "b4_base_end": nw["base_end"],
            "b4_price_low": nw["price_low"],
            "b4_price_high": nw["price_high"],
            "lead_vs_btc_days": lead_days,
            "method": block.get("method", ""),
        })

    current_phase_hint = {
        "pre_b4_bear": "Late bear - next bottom watch imminent",
        "in_b4_window": "Bottom window open - attention peak",
        "in_accumulation": "Patience window - accumulation",
        "exit": "Post-top bear - exit watch",
    }

    data = {
        "generated_for": "now-stamp.html (browser-rendered banner)",
        "generated_by": "scripts/build_cycle_status.py",
        "anchored_on": "observed C4 top",
        "asset_order": asset_order,
        "assets": assets,
        # Legacy alias kept for backward compatibility with any older banner
        # JS that reads the top-level ``btc`` block directly.
        "btc": assets.get("BTC", btc_block),
        "alt_watch_order": alt_watch_order,
        "current_phase_hint": current_phase_hint,
    }

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_OUT, "w", encoding="utf-8") as f:
        # deterministic: sort_keys + stable separators so diffs are clean
        json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
    print(f"OK   wrote {DATA_OUT.relative_to(ROOT)} ({DATA_OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

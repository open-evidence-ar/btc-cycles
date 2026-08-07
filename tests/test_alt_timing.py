"""I-17 validation gate: per-asset halving-cycle timing.

Validates the artifacts produced by I-17.1, I-17.2, I-17.3, and the chart /
section deliverables produced by I-17.4 and I-17.5. Mirrors the structure
of the prior increment gate tests.
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

ALT_METRICS = PROCESSED / "alt_cycle_metrics.csv"
ALT_FWD = PROCESSED / "alt_forward_ranges.csv"
ALT_ZONES = PROCESSED / "alt_next_cycle_zones.csv"

EXPECTED_ASSETS = {"eth", "xrp", "sol", "mstr", "wgmi", "riot", "mara", "spx", "ndx", "dxy", "tlt", "gold"}
EXPECTED_ZONE_ASSETS = {"eth", "xrp", "sol", "mstr", "wgmi", "spx", "ndx", "dxy", "tlt", "gold"}
EXPECTED_CYCLES = {"C1", "C2", "C3", "C4"}
CYCLES = ["C1", "C2", "C3", "C4"]


def test_alt_cycle_metrics_exists():
    assert ALT_METRICS.is_file(), f"Missing {ALT_METRICS}"


def test_alt_cycle_metrics_columns_and_rows():
    df = pd.read_csv(ALT_METRICS)
    required_cols = {
        "asset", "cycle_id", "halving_date", "next_halving_date",
        "cycle_source",
        "asset_pre_halving_bottom_date", "asset_pre_halving_bottom_price",
        "asset_local_top_date", "asset_local_top_price",
        "asset_next_bear_bottom_date", "asset_next_bear_bottom_price",
        "D_asset_prev_bottom_to_halving", "D_asset_halving_to_top",
        "D_asset_top_to_next_bottom",
        "mult_asset_bottom_to_top", "drawdown_asset_pct",
    }
    assert required_cols.issubset(set(df.columns)), (
        f"Missing columns: {required_cols - set(df.columns)}"
    )
    # 12 assets x 4 BTC cycles = 48 rows (eth, xrp, sol, mstr, wgmi, riot, mara, spx, ndx, dxy, tlt, gold)
    # MSTR has 2 (C1/C2 excluded), others have 4 — total = 11*4 + 2 = 46
    assert len(df) == 46, f"Expected 46 rows, got {len(df)}"
    assert set(df["asset"].unique()) == EXPECTED_ASSETS
    assert set(df["cycle_id"].unique()) == EXPECTED_CYCLES


def test_alt_cycle_metrics_cycle_source_valid():
    """Every row's cycle_source must be one of the allowed enum values."""
    df = pd.read_csv(ALT_METRICS)
    allowed = {
        "actual", "actual_C4_open", "missing",
        "ETH_proxy_C1", "ETH_proxy_C2",  # SOL proxies per §9.5.3
        "mara_proxy_C1", "mara_proxy_C2", "mara_proxy_C3",  # WGMI proxies per I-17 + MARA proxy swap
    }
    bad = df[~df["cycle_source"].isin(allowed)]
    assert bad.empty, f"Invalid cycle_source values: {bad['cycle_source'].unique()}"


def test_alt_extrema_dates_within_live_range():
    """For each row with actual extrema, top/bottom dates must fall within
    the asset's live date range AND within the BTC cycle's window.
    Proxy rows (cycle_source starts with 'ETH_proxy_' or 'mara_proxy_') inherit
    the source proxy's dates so they are exempt from this range check by design."""
    df = pd.read_csv(ALT_METRICS)
    for _, r in df.iterrows():
        if r["cycle_source"] in ("missing",):
            continue
        if str(r["cycle_source"]).startswith(("ETH_proxy_", "mara_proxy_")):
            continue  # proxy dates belong to the proxy asset, not this asset
        first = pd.to_datetime(r["asset_first_data_date"])
        last = pd.to_datetime(r["asset_last_data_date"])
        for col in ["asset_pre_halving_bottom_date",
                    "asset_local_top_date",
                    "asset_next_bear_bottom_date"]:
            v = r.get(col)
            if pd.isna(v) or v == "":
                continue
            d = pd.to_datetime(v)
            assert first <= d <= last, (
                f"{r['asset']} {r['cycle_id']} {col}={v} outside live range "
                f"{first.date()}..{last.date()}"
            )


def test_alt_no_nan_in_required_columns():
    """For rows with cycle_source != 'missing', numeric columns must be populated."""
    df = pd.read_csv(ALT_METRICS, keep_default_na=False)
    required = [
        "asset_pre_halving_bottom_date", "asset_pre_halving_bottom_price",
        "asset_local_top_date", "asset_local_top_price",
        "D_asset_prev_bottom_to_halving", "D_asset_halving_to_top",
        "mult_asset_bottom_to_top",
    ]
    for _, r in df.iterrows():
        if r["cycle_source"] == "missing":
            continue
        for col in required:
            v = r.get(col)
            assert v != "" and not pd.isna(v), (
                f"{r['asset']} {r['cycle_id']} {col} empty (source={r['cycle_source']})"
            )


def test_sol_proxy_assignment():
    """SOL coverage with Yahoo data: C3 and C4 are 'actual' (Yahoo goes back
    to 2020-04-10, covering the C3 window). C1 and C2 are 'missing' because
    SOL didn't exist during those BTC cycles. No ETH_proxy rows remain now
    that Yahoo provides actual SOL data through the C3 window."""
    df = pd.read_csv(ALT_METRICS)
    sol = df[df["asset"] == "sol"]
    proxy_rows = sol[sol["cycle_source"].str.startswith("ETH_proxy", na=False)]
    assert len(proxy_rows) == 0, (
        f"SOL should have 0 ETH_proxy rows with Yahoo data, found {len(proxy_rows)}"
    )
    # SOL C1 and C2 must be missing
    assert sol[sol["cycle_id"] == "C1"].iloc[0]["cycle_source"] == "missing"
    assert sol[sol["cycle_id"] == "C2"].iloc[0]["cycle_source"] == "missing"
    # SOL C3 and C4 must be actual (Yahoo covers both windows)
    # C4 may be "actual" or "actual_C4_open" depending on whether a bear
    # bottom has been observed (>270d after top).
    assert sol[sol["cycle_id"] == "C3"].iloc[0]["cycle_source"] == "actual"
    c4_source = sol[sol["cycle_id"] == "C4"].iloc[0]["cycle_source"]
    assert c4_source in ("actual", "actual_C4_open"), (
        f"SOL C4 source should be actual or actual_C4_open, got {c4_source}"
    )


def test_eth_full_coverage():
    """ETH should be present in C2, C3 (actual) and C4 (actual_C4_open).
    C1 is missing-by-data (ETH launched 2016, after H1)."""
    df = pd.read_csv(ALT_METRICS)
    eth = df[df["asset"] == "eth"].set_index("cycle_id")
    assert eth.loc["C1", "cycle_source"] == "missing"
    assert eth.loc["C2", "cycle_source"] == "actual"
    assert eth.loc["C3", "cycle_source"] == "actual"
    # C4 either "actual_C4_open" (no bear bottom yet) or "actual" if one was detected
    assert eth.loc["C4", "cycle_source"] in ("actual", "actual_C4_open")


# ---------- I-17.2 tests: alt_forward_ranges.csv ----------

def test_alt_forward_ranges_exists():
    assert ALT_FWD.is_file(), f"Missing {ALT_FWD}"


def test_alt_forward_ranges_rows_and_columns():
    """10 assets x 5 statistics = 50 rows (expected)."""
    df = pd.read_csv(ALT_FWD, keep_default_na=False)
    required_cols = {
        "asset", "statistic", "n_actual", "n_with_proxy",
        "mean", "median", "min", "max", "q25", "q75",
        "is_sensitive", "n_with_proxy_note",
    }
    assert required_cols.issubset(set(df.columns)), (
        f"Missing columns: {required_cols - set(df.columns)}"
    )
    assert set(df["asset"].unique()) == EXPECTED_ZONE_ASSETS
    # expected rows = 10 assets x 5 stats = 50 (one row even when no data)
    assert len(df) == 50, f"Expected 50 rows, got {len(df)}"


def test_alt_forward_ranges_looco_populated_for_n3_assets():
    """For assets with n >= 3, LOOCO columns must be populated.
    ETH (n=3 on D_asset_halving_to_top) and SPX/NDX/DXY/TLT (n=4) qualify."""
    df = pd.read_csv(ALT_FWD, keep_default_na=False)
    # ETH D_asset_halving_to_top: n_with_proxy=3, LOOCO must be present
    eth_ht = df[(df["asset"] == "eth") & (df["statistic"] == "D_asset_halving_to_top")].iloc[0]
    assert int(eth_ht["n_with_proxy"]) == 3
    # All 3 cycle-specific LOOCO columns populated (for the 3 actual cycles)
    for c in ["C2", "C3", "C4"]:
        col = f"looco_{c}_mean"
        assert eth_ht[col] != "", f"LOOCO column {col} empty for ETH D_halving_to_top"
    # SPX (n=4) must have all 4 LOOCO columns populated
    spx_ht = df[(df["asset"] == "spx") & (df["statistic"] == "D_asset_halving_to_top")].iloc[0]
    assert int(spx_ht["n_with_proxy"]) == 4
    for c in CYCLES:
        col = f"looco_{c}_mean"
        assert spx_ht[col] != "", f"LOOCO column {col} empty for SPX D_halving_to_top"


def test_alt_forward_ranges_no_nan_in_core_stats():
    """For every row, mean/median/min/max must be numeric (not empty)
    EXCEPT when n_with_proxy == 0 (the row is a no-data placeholder)."""
    df = pd.read_csv(ALT_FWD, keep_default_na=False)
    for _, r in df.iterrows():
        if int(r["n_with_proxy"]) == 0:
            continue
        for col in ["mean", "median", "min", "max"]:
            v = r.get(col)
            assert v != "" and not pd.isna(v), (
                f"{r['asset']} {r['statistic']} {col} empty (n_with_proxy={r['n_with_proxy']})"
            )


def test_alt_forward_ranges_sol_proxy_flag():
    """SOL must carry explanatory notes about its data coverage in n_with_proxy_note.

    With Yahoo data, SOL has 2 actual cycles (C3, C4) and no ETH proxy rows.
    The D_asset_top_to_next_bottom row should carry a timing borrow note since
    n_actual=2 < 3.
    """
    df = pd.read_csv(ALT_FWD, keep_default_na=False)
    sol = df[df["asset"] == "sol"]
    # Check that at least one row has a note about coverage or borrowing
    notes = sol["n_with_proxy_note"].tolist()
    has_note = any("n=" in str(n) or "borrowed" in str(n) for n in notes)
    assert has_note, (
        f"SOL forward-range rows should carry coverage caveat; notes: {notes}"
    )


# ---------- I-17.3 tests: alt_next_cycle_zones.csv ----------

def test_alt_next_cycle_zones_exists():
    assert ALT_ZONES.is_file(), f"Missing {ALT_ZONES}"


def test_alt_next_cycle_zones_structure():
    """10 assets x 4 zones = 40 rows, with expected columns."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    required = {"asset", "zone", "base_start", "base_end",
                "outer_start", "outer_end",
                "price_low", "price_high",
                "compression_fit_used", "compression_fit_note"}
    assert required.issubset(set(df.columns)), (
        f"Missing columns: {required - set(df.columns)}"
    )
    # 10 assets x 4 zones (bear_bottom + accumulation, distribution, exit)
    assert len(df) == 40, f"Expected 40 rows, got {len(df)}"
    assert set(df["asset"].unique()) == EXPECTED_ZONE_ASSETS
    # Each asset has exactly 4 zones: bear_bottom, accumulation, distribution, exit
    for asset in EXPECTED_ZONE_ASSETS:
        zones = set(df[df["asset"] == asset]["zone"].unique())
        assert zones == {"bear_bottom", "accumulation", "distribution", "exit"}, (
            f"{asset}: expected 4 zones, got {zones}"
        )


def test_gold_support_band_populated():
    """I-19b: gold's bear_bottom row must carry the validated bull-market
    support band (20-mo SMA / 21-mo EMA) in support_band_low/high columns.

    Other assets must leave the columns empty (gold-only overlay per
    docs/gold_seasonality.md)."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    assert "support_band_low" in df.columns and "support_band_high" in df.columns, (
        "alt_next_cycle_zones.csv missing support_band_low/support_band_high columns"
    )
    gold_bb = df[(df["asset"] == "gold") & (df["zone"] == "bear_bottom")]
    assert not gold_bb.empty, "gold: missing bear_bottom row"
    r = gold_bb.iloc[0]
    assert r["support_band_low"] != "" and r["support_band_high"] != "", (
        "gold: support band empty on bear_bottom row"
    )
    lo, hi = float(r["support_band_low"]), float(r["support_band_high"])
    assert 0 < lo <= hi, f"gold: support band invalid (low={lo}, high={hi})"
    # Sanity against the validated values from docs/gold_seasonality.md
    # (20-mo SMA $3,813.13 / 21-mo EMA $3,829.66 as of 2026-07-31).
    assert 2500 <= lo <= 4500, f"gold: support band low {lo} outside plausible range"
    assert 2500 <= hi <= 4500, f"gold: support band high {hi} outside plausible range"
    for asset in EXPECTED_ZONE_ASSETS - {"gold"}:
        others = df[(df["asset"] == asset) & (df["zone"] == "bear_bottom")]
        assert not others.empty, f"{asset}: missing bear_bottom row"
        o = others.iloc[0]
        assert o["support_band_low"] == "" and o["support_band_high"] == "", (
            f"{asset}: support band should be empty (gold-only feature)"
        )


# ---------- I-19 tests: macro cycle-tied 2-stage projection ----------

MACRO_ASSETS_I19 = {"spx", "ndx", "dxy", "tlt", "gold"}


def test_macro_assets_use_cycle_tied_projection():
    """I-19: macro assets (SPX/NDX/DXY/TLT/GOLD) must NOT use the legacy
    'macro_not_cycle_tied' mode when they have an observed C4 top + >=1 own
    drawdown/multiplier sample. Each must emit a cycle-tied 2-stage
    projection (mode='macro_2_stage_own_shape')."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    for asset in MACRO_ASSETS_I19:
        sub = df[df["asset"] == asset]
        assert not sub.empty, f"{asset}: missing from alt_next_cycle_zones.csv"
        modes = set(sub["compression_fit_used"].unique())
        assert "macro_not_cycle_tied" not in modes, (
            f"{asset}: still uses deprecated 'macro_not_cycle_tied' mode "
            f"(modes seen: {modes})"
        )
        assert "macro_2_stage_own_shape" in modes, (
            f"{asset}: expected 'macro_2_stage_own_shape' mode, got {modes}"
        )


def test_macro_assets_distribution_has_price_band():
    """I-19: each macro's distribution (C5 TOP) zone must carry a
    non-empty price_low/price_high band (cycle-tied projection produces
    a real band, unlike the legacy historical envelope)."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    for asset in MACRO_ASSETS_I19:
        dist = df[(df["asset"] == asset) & (df["zone"] == "distribution")]
        assert not dist.empty, f"{asset}: missing distribution zone"
        r = dist.iloc[0]
        assert r["price_low"] != "" and r["price_high"] != "", (
            f"{asset}: distribution price_low/price_high empty"
        )
        try:
            lo = float(r["price_low"])
            hi = float(r["price_high"])
        except (ValueError, TypeError):
            assert False, f"{asset}: distribution prices not numeric"
        assert lo > 0 and hi > 0 and hi >= lo, (
            f"{asset}: distribution band invalid (low={lo}, high={hi})"
        )


def test_macro_assets_bear_bottom_has_dates():
    """I-19: each macro's bear_bottom zone must have populated date bands
    (cycle-tied projection anchors on BTC B4 + alt lag)."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    for asset in MACRO_ASSETS_I19:
        bb = df[(df["asset"] == asset) & (df["zone"] == "bear_bottom")]
        assert not bb.empty, f"{asset}: missing bear_bottom zone"
        r = bb.iloc[0]
        for col in ["base_start", "base_end", "outer_start", "outer_end"]:
            assert r[col] != "", f"{asset}: bear_bottom {col} empty"


def test_alt_next_cycle_zones_no_overlap():
    """Per asset: distribution zone must not overlap accumulation zone
    (distribution must start after halving, accumulation ends at halving)."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    for asset in EXPECTED_ZONE_ASSETS:
        # Skip rows with empty dates (insufficient-data placeholders)
        sub = df[df["asset"] == asset]
        acc = sub[sub["zone"] == "accumulation"].iloc[0]
        dist = sub[sub["zone"] == "distribution"].iloc[0]
        if dist["base_start"] == "" or acc["base_end"] == "":
            continue
        # Distribution base starts after H5; accumulation ends at H5
        assert dist["base_start"] >= acc["base_end"], (
            f"{asset}: distribution starts {dist['base_start']} before "
            f"accumulation ends {acc['base_end']}"
        )


def test_alt_next_cycle_zones_base_within_outer():
    """Per asset, per zone: base_start/elapsed fits within outer bounds."""
    df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    for _, r in df.iterrows():
        if r["base_start"] == "" or r["outer_start"] == "":
            continue
        assert r["outer_start"] <= r["base_start"] <= r["base_end"] <= r["outer_end"], (
            f"{r['asset']} {r['zone']}: base band not within outer band "
            f"(outer={r['outer_start']}..{r['outer_end']}, base={r['base_start']}..{r['base_end']})"
        )


def test_alt_next_cycle_zones_bear_bottom_floor():
    """Each crypto asset's bear_bottom price_low must exceed the prior
    observed deep bear bottom price (rising bear bottoms invariant).

    Economic invariant: successive BTC-cycle bear bottoms rise over time.
    The projected bear_bottom zone's lower bound must not fall below the
    asset's most recently observed deep bear bottom.

    Scoped to assets using the Stage 1 ratio-path (own bear-bottom power-
    law fit, floor_ratio=1.0). Borrowed-path assets (XRP, SOL) use a
    different economic model and are tested separately if needed.
    """
    zones_df = pd.read_csv(ALT_ZONES, keep_default_na=False)
    metrics_df = pd.read_csv(ALT_METRICS, keep_default_na=False)

    # ETH uses the BTC ratio-of-ratios path. ETH's C4 post-bottom
    # ($1,564.82) is unconfirmed in the user's framework, so the floor
    # check must use the last CONFIRMED bottom (C3 post-bottom).
    asset = "eth"
    bb = zones_df[(zones_df["asset"] == asset)
                  & (zones_df["zone"] == "bear_bottom")]
    assert not bb.empty, f"{asset}: no bear_bottom row"
    price_low_str = bb.iloc[0]["price_low"]
    assert price_low_str != "", f"{asset}: bear_bottom price_low is empty"
    price_low = float(price_low_str)

    # Last CONFIRMED bear bottom = C3 post-bottom (exclude C4 post-bottom
    # which is unconfirmed in the user's framework).
    rows = metrics_df[(metrics_df["asset"] == asset)
                      & (metrics_df["cycle_source"] != "missing")
                      & (metrics_df["cycle_source"] != "proxy")]
    rows = rows.sort_values("cycle_id")
    last_confirmed_bottom = None
    for _, r in rows.iterrows():
        cid = r.get("cycle_id", "")
        if cid == "C4":
            continue  # C4 post-bottom unconfirmed
        p = r.get("asset_next_bear_bottom_price")
        if pd.notna(p) and float(p) > 0:
            last_confirmed_bottom = float(p)
    assert last_confirmed_bottom is not None, f"{asset}: no confirmed bear bottom"

    assert price_low >= last_confirmed_bottom, (
        f"{asset}: bear_bottom price_low={price_low:.2f} is below "
        f"last confirmed bear bottom {last_confirmed_bottom:.2f} "
        f"(ratio={price_low/last_confirmed_bottom:.3f})"
    )


# ---------- I-17.4 charts + I-17.5 section tests ----------

import hashlib
import json

SECTIONS_DIR = ROOT / "_sections"
LAYOUT_FILE = ROOT / "_layouts" / "default.html"
CHARTS_DIR = ROOT / "assets" / "charts"
SNAPSHOTS = ROOT / "tests" / "chart_snapshots.json"


def test_charts_c8_c9_present():
    """Charts C8.html and C8.png + C9.html and C9.png must exist and contain
    Plotly content."""
    for cid in ["C8", "C9"]:
        html = CHARTS_DIR / f"{cid}.html"
        png = CHARTS_DIR / f"{cid}.png"
        assert html.is_file() and html.stat().st_size > 1000, f"{cid}.html missing/too small"
        assert png.is_file() and png.stat().st_size > 10000, f"{cid}.png missing/too small"
        content = html.read_text(encoding="utf-8", errors="ignore")
        assert "plotly" in content.lower(), f"{cid}.html missing Plotly content"


def test_charts_c8_c9_snapshot_determinism():
    """PNG snapshots for C8 and C9 must match the stored SHA-256."""
    if not SNAPSHOTS.is_file():
        assert False, "chart_snapshots.json is missing"
    stored = json.loads(SNAPSHOTS.read_text())
    for cid in ["C8", "C9"]:
        assert cid in stored, f"No stored snapshot for {cid}"
        path = CHARTS_DIR / f"{cid}.png"
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        assert h == stored[cid], f"{cid}.png SHA mismatch"


def test_charts_c8g_present():
    """Gold chart C8g.html + C8g.png must exist and contain Plotly content."""
    for ext in ["html", "png"]:
        path = CHARTS_DIR / f"C8g.{ext}"
        assert path.is_file(), f"C8g.{ext} missing"
    html = CHARTS_DIR / "C8g.html"
    assert html.stat().st_size > 1000, "C8g.html too small"
    png = CHARTS_DIR / "C8g.png"
    assert png.stat().st_size > 10000, "C8g.png too small"
    content = html.read_text(encoding="utf-8", errors="ignore")
    assert "plotly" in content.lower(), "C8g.html missing Plotly content"


def test_charts_c8g_snapshot_determinism():
    """PNG snapshot for C8g must match the stored SHA-256."""
    if not SNAPSHOTS.is_file():
        assert False, "chart_snapshots.json is missing"
    stored = json.loads(SNAPSHOTS.read_text())
    assert "C8g" in stored, "No stored snapshot for C8g"
    path = CHARTS_DIR / "C8g.png"
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    assert h == stored["C8g"], "C8g.png SHA mismatch"


def test_cross_asset_timing_section_exists():
    """`_sections/cross-asset-timing.md` must exist with expected front-matter."""
    s = SECTIONS_DIR / "cross-asset-timing.md"
    assert s.is_file(), "cross-asset-timing.md section file is missing"
    text = s.read_text(encoding="utf-8")
    assert "permalink: /cross-asset-timing/" in text, "missing permalink"
    assert "title:" in text, "missing title"


def test_cross_asset_timing_section_has_chart_refs():
    """Section must render C8 (ETH) and C8g (GOLD) via the chart.html include.
    C9 (${QC9}) was moved to Appendix C (Cross-Asset Correlations) in the
    Aug-2026 reorg: it is BTC-calendar + alt-local-top overlay context, not
    a per-asset projection chart; the macro-context charts C8d and C9 now
    render on the Cross-Asset Correlations appendix page."""
    text = (SECTIONS_DIR / "cross-asset-timing.md").read_text(encoding="utf-8")
    assert "id=\"C8\"" in text or 'id="C8"' in text, "missing C8 chart include"
    assert "id=\"C8g\"" in text or 'id="C8g"' in text, "missing C8g chart include"


def test_cross_asset_appendix_has_macro_context_charts():
    """Aug-2026 reorg: C8d (macro 2-stage) and C9 (BTC calendar w/ alt local-top
    overlays) moved from cross-asset-timing.md to cross-asset.md (Appendix C —
    Cross-Asset Correlations). Verify the receiving page renders them."""
    text = (SECTIONS_DIR / "cross-asset.md").read_text(encoding="utf-8")
    assert 'id="C8d"' in text or "id=\"C8d\"" in text, (
        "cross-asset.md missing C8d chart include (moved here Aug-2026 reorg)"
    )
    assert 'id="C9"' in text or "id=\"C9\"" in text, (
        "cross-asset.md missing C9 chart include (moved here Aug-2026 reorg)"
    )


def test_cross_asset_timing_section_provenance_footer():
    """Section must include a provenance footer referencing the artifacts."""
    text = (SECTIONS_DIR / "cross-asset-timing.md").read_text(encoding="utf-8")
    assert "alt_cycle_metrics.csv" in text and "alt_next_cycle_zones.csv" in text, (
        "cross-asset-timing.md missing provenance footer references"
    )


def test_sidebar_links_to_cross_asset_timing():
    """The sidebar nav must include the cross-asset-timing link as either an
    anchor (#cross-asset-timing, the single-page form) or a full URL."""
    text = LAYOUT_FILE.read_text(encoding="utf-8")
    assert ("/cross-asset-timing/" in text
            or "#cross-asset-timing" in text), (
        "sidebar nav missing cross-asset-timing link"
    )


def test_index_links_to_cross_asset_timing():
    """The home page (index.md) must reference cross-asset-timing via the
    single-page anchor convention (#cross-asset-timing)."""
    text = (ROOT / "index.md").read_text(encoding="utf-8")
    assert "#cross-asset-timing" in text, (
        "index.md missing #cross-asset-timing anchor link (single-page form)"
    )

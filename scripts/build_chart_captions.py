#!/usr/bin/env python3
"""Emit data-derived figure captions to ``_data/chart_captions.json``.

Why this exists
---------------
The chart captions in ``_sections/*.md`` were hand-written strings carrying
hard-coded numbers. They went stale silently on every refresh and the site
published prices that contradicted the charts directly above them. Concretely,
C8's caption advertised a C5 top zone of ``$3,130-$9,652`` while the zone CSV
carried ``$16,648.91-$190,052.96`` and the chart's own footer printed the real
band. Same class of defect as the stale chart subtitles: transcription, not
generation.

The captions are now built from the same zone CSVs the charts read, so they
cannot disagree with the rendered figure. Markdown includes reference them as
``caption=site.data.chart_captions.C8``.

``tests/test_chart_captions.py`` pins the invariant: no ``{% include
chart.html %}`` may carry a hand-written ``$`` number.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ALT_ZONES = ROOT / "data" / "processed" / "alt_next_cycle_zones.csv"
BTC_ZONES = ROOT / "data" / "processed" / "next_cycle_zones.csv"
OUT = ROOT / "_data" / "chart_captions.json"

# chart id -> (asset key, display label) for the single-asset zone charts.
ALT_CHARTS = {
    "C8": ("eth", "ETH"),
    "C8b": ("xrp", "XRP"),
    "C8c": ("sol", "SOL"),
    "C8e": ("mstr", "MSTR"),
    "C8f": ("wgmi", "WGMI"),
    "C8g": ("gold", "GOLD (GC=F)"),
}

# Same wording as the chart subtitles (scripts/build_charts.py::_mode_prose),
# kept short here because the caption also carries the zone table.
MODE_NOTE = {
    "naive_median_own_dd": "own-series naive median",
    "borrowed_2_stage_from_BTC": "2-stage borrowed from BTC",
    "borrowed_2_stage_from_ETH": "2-stage borrowed from ETH",
    "macro_2_stage_own_shape": "macro 2-stage, own shape",
}

ZONE_PHRASE = {
    "bottom": "B4 bear-bottom zone (cyan)",
    "accumulation": "accumulation window (green, price-free)",
    "top": "C5 top / distribution zone (orange)",
    "b5_bottom": "B5 re-entry zone (blue)",
}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None          # reject NaN


def _fmt(p):
    """Price formatting: sub-$1 assets need cents, BTC does not."""
    if p is None:
        return ""
    if p < 1:
        return f"${p:,.4f}"
    if p < 100:
        return f"${p:,.2f}"
    return f"${p:,.0f}"


def _window(row):
    a = str(row.get("outer_start", "") or "")[:10]
    b = str(row.get("outer_end", "") or "")[:10]
    if not a or a == "nan":
        return ""
    return f"window {a} → {b}"


def _zone_clause(row):
    parts = [ZONE_PHRASE.get(row["zone"], row["zone"])]
    lo, hi = _num(row.get("price_low")), _num(row.get("price_high"))
    if lo and hi:
        parts.append(f"{_fmt(lo)}–{_fmt(hi)}")
    # The model's point estimate, distinct from the band. Omitted for
    # price-free zones.
    ctr = _num(row.get("price_center"))
    if ctr and lo and hi:
        parts.append(f"centre {_fmt(ctr)}")
    win = _window(row)
    if win:
        parts.append(win)
    return ", ".join(parts)


def _caption(chart_id, label, zones, mode=None, anchor=None, extra=None):
    clauses = [_zone_clause(z) for _, z in zones.iterrows()]
    head = f"{chart_id} — {label} next-cycle (C5) projection"
    bits = []
    if mode:
        bits.append(MODE_NOTE.get(mode, mode))
    if anchor:
        bits.append(f"anchor = observed C4 top {anchor[0]} @ {_fmt(anchor[1])}")
    if bits:
        head += " (" + "; ".join(bits) + ")"
    tail = ". ".join(clauses)
    if extra:
        tail += f". {extra.rstrip('.')}"
    return f"{head}. {tail}."


# Visual-explanation prose that is static (no numbers), so it cannot drift.
# It lives here rather than in the markdown because a Jekyll include cannot take
# a `{{ ... }}` interpolation inside a quoted parameter -- the rendered text
# would be re-parsed as tag params and blow up the build.
C6_EXTRA = (
    "Single tall log-scale panel: BTC price line with zone shading, event "
    "markers (B3, H4, observed C4 top, projected B4, H5) and prediction bands. "
    "The translucent purple folklore band marks the B4-anchored C5 top (see "
    "Appendix B). Muted dotted 50w/200w SMA floor overlays cross-reference the "
    "B4 in-band confirmation rule (see decision table row 1). Bands narrowed "
    "(0.75x residual std)."
)


def build() -> dict:
    alt = pd.read_csv(ALT_ZONES, keep_default_na=False)
    btc = pd.read_csv(BTC_ZONES, keep_default_na=False)
    caps: dict[str, str] = {}

    for cid, (asset, label) in ALT_CHARTS.items():
        sub = alt[alt["asset"] == asset]
        if sub.empty:
            continue
        bottom = sub[sub["zone"] == "bottom"]
        mode = str(bottom.iloc[0].get("compression_fit_used", "")) if not bottom.empty else ""
        anchor = None
        if not bottom.empty:
            p = _num(bottom.iloc[0].get("observed_c4_top_price"))
            d = str(bottom.iloc[0].get("observed_c4_top_date", "") or "")[:10]
            if p and d:
                anchor = (d, p)
        extra = None
        if asset == "gold" and not bottom.empty:
            lo = _num(bottom.iloc[0].get("support_band_low"))
            hi = _num(bottom.iloc[0].get("support_band_high"))
            if lo and hi:
                extra = (f"Gold bull-support band (20-mo SMA / 21-mo EMA) "
                         f"{_fmt(lo)}–{_fmt(hi)}; the projected B4 is cross-checked "
                         f"against this floor (docs/gold_seasonality.md).")
        caps[cid] = _caption(cid, label, sub, mode, anchor, extra)

    btc_bottom = btc[btc["zone"] == "bottom"]
    anchor = None
    if not btc_bottom.empty:
        p = _num(btc_bottom.iloc[0].get("observed_c4_top_price"))
        d = str(btc_bottom.iloc[0].get("observed_c4_top_date", "") or "")[:10]
        if p and d:
            anchor = (d, p)
    caps["C6"] = _caption("C6", "BTC", btc, None, anchor, C6_EXTRA)

    caps["C8d"] = _c8d_caption(alt)

    return caps


# ---------------------------------------------------------------------------
# Decision-windows summary table (_includes/zone-summary-table.html)
# ---------------------------------------------------------------------------
# The cross-asset-timing page used to carry this table as hand-written
# Kramdown. It was the single most-read block on the site and it had drifted
# badly: the ETH row advertised a B4 corridor of $298-$1,000 against the real
# $1,153.82-$2,092.47, XRP $0.54-$0.83 against $0.78-$0.91, SOL $77.80-$85.96
# against $57.16-$67.12. Worse, the macro rows described timing ("BTC-anchored",
# "H5 + own halving-to-top") that was false the day macro timing moved to each
# macro's own history. The table is now generated from the same zone CSVs the
# charts read, following the _includes/regime-sensitivity.html precedent.

TABLE_INCLUDE = ROOT / "_includes" / "zone-summary-table.html"

MACRO_PANEL_ASSETS = ["spx", "ndx", "dxy", "tlt", "gold"]
MACRO_LABELS = {"spx": "SPX", "ndx": "NDX", "dxy": "DXY", "tlt": "TLT", "gold": "GOLD"}

# Static "What to do" prose per asset (no numbers -- those are generated),
# keyed to the footnote number the old hand-written table used.
WHAT_TO_DO = {
    "xrp": ("Earliest crypto bottom watch.", 1),
    "eth": ("~3 months before BTC.", 2),
    "btc": ("Anchor for XRP/SOL — they borrow BTC's projected B4.", 3),
    "sol": ("Lags BTC — the later crypto B4.", 4),
    "mstr": ("BTC-leveraged equity — window near SOL's.", 5),
    "wgmi": ("BTC miners ETF — MARA proxy supplies pre-launch cycles C1-C3.", 7),
    "spx": ("Macro, own-history timing — crypto-entry context.", 6),
    "ndx": ("Macro, own-history timing — crypto-entry context.", 6),
    "dxy": ("Macro, own-history timing — crypto-entry context.", 6),
    "tlt": ("Macro, own-history timing — crypto-entry context.", 6),
    "gold": ("Macro, own-history timing. Bull support band (20-mo SMA / 21-mo EMA) "
             "is the empirical floor.", 8),
}

# Footnote prose: {mode} is filled from the CSV's compression_fit_used so the
# method claim can never go stale again (the hand-written footnotes asserted
# 2_stage_with_observed_c4 for ETH and borrowed_2_stage_from_ETH for SOL; both
# had silently drifted to other paths).
FOOTNOTES = {
    1: ("<strong>XRP.</strong> Timing: BTC-borrowed (BTC B4 + own lag). "
        "Method: <code>{mode}</code>."),
    2: ("<strong>ETH.</strong> Method: <code>{mode}</code>. Note: ETH's published "
        "B4 comes from the BTC ratio-of-ratios path while C5 derives from the "
        "naive-median B4 band — different anchors (see AGENTS.md, \"dual-path "
        "asymmetry\")."),
    3: ("<strong>BTC.</strong> Method: BTC 2-stage (Stage 1 + Stage 2). Full "
        "disclosure on The Prediction (BTC) page."),
    4: ("<strong>SOL.</strong> Timing: BTC-borrowed (B4 window = BTC B4 + SOL "
        "lag). Method: <code>{mode}</code>."),
    5: ("<strong>MSTR.</strong> Timing: BTC-borrowed. Method: <code>{mode}</code>."),
    6: ("<strong>SPX/NDX/DXY/TLT.</strong> Method: <code>{mode}</code> (I-19): "
        "drawdown depth and bottom-to-top multiplier fit on the macro's OWN "
        "series. Zone DATES come from each macro's own observed cycle durations "
        "since 2026-10-16 — NOT from BTC's halving calendar (halving-to-top lag "
        "spread 1.4y-2.6y vs ~0.2y for BTC; scripts/check_cycle_tie.py). See "
        "docs/blockers/I-19-macro-2stage.md."),
    7: ("<strong>WGMI.</strong> Timing: BTC-borrowed. Method: <code>{mode}</code>. "
        "MARA proxy for pre-launch cycles C1-C3 (MARA is a data source, never "
        "projected itself)."),
    8: ("<strong>GOLD (GC=F).</strong> Method: <code>{mode}</code> (I-19b). "
        "Own-history timing. Bull-market support band (20-mo SMA / 21-mo EMA) at "
        "{support} — the projected B4 is cross-checked against this floor "
        "(docs/gold_seasonality.md). See chart C8g."),
}


def _band(lo, hi):
    if lo and hi:
        return f"{_fmt(lo)} – {_fmt(hi)}"
    return "n/a"


def _base_window(row):
    a = str(row.get("base_start", "") or "")[:10]
    b = str(row.get("base_end", "") or "")[:10]
    if not a or a == "nan":
        return "n/a"
    return f"{a} → {b}"


def _row_cells(asset, sub):
    """(b4_window, b4_band, c5_window, c5_band, b5_window, b5_band)."""
    bottom = sub[sub["zone"] == "bottom"]
    top = sub[sub["zone"] == "top"]
    b5 = sub[sub["zone"] == "b5_bottom"]
    b4w = b4b = c5w = c5b = b5w = b5b = "n/a"
    if not bottom.empty:
        b4w = _base_window(bottom.iloc[0])
        b4b = _band(_num(bottom.iloc[0].get("price_low")),
                    _num(bottom.iloc[0].get("price_high")))
    if not top.empty:
        c5w = _base_window(top.iloc[0])
        c5b = _band(_num(top.iloc[0].get("price_low")),
                    _num(top.iloc[0].get("price_high")))
    if not b5.empty:
        b5w = _base_window(b5.iloc[0])
        b5b = _band(_num(b5.iloc[0].get("price_low")),
                    _num(b5.iloc[0].get("price_high")))
    return b4w, b4b, c5w, c5b, b5w, b5b


def _table_rows(alt, btc):
    """Ordered (asset, label, cells, what_to_do, footnote_no) tuples."""
    rows = []
    for asset in ["xrp", "eth", "sol", "mstr", "wgmi", "spx", "ndx", "dxy", "tlt", "gold"]:
        sub = alt[alt["asset"] == asset]
        if sub.empty:
            continue
        label = MACRO_LABELS.get(asset, asset.upper())
        cells = _row_cells(asset, sub)
        rows.append((asset, label, cells, WHAT_TO_DO.get(asset)))
    # BTC: from its own zones file; keeps its predictive-ranges link.
    cells = _row_cells("btc", btc)
    rows.append(("btc", "BTC", cells, WHAT_TO_DO["btc"]))

    def sort_key(r):
        sub = btc if r[0] == "btc" else alt[alt["asset"] == r[0]]
        bottom = sub[sub["zone"] == "bottom"]
        if bottom.empty:
            return "9999"
        return str(bottom.iloc[0].get("base_start", "") or "9999")[:10]

    rows.sort(key=sort_key)
    return rows


def build_table_html(alt, btc) -> str:
    out = ['<table class="table-dense">',
           '<thead><tr><th>Order</th><th>Asset</th><th>B4 window (base)</th>'
           '<th>B4 price corridor</th><th>C5 (distribution) window</th>'
           '<th>C5 price corridor</th><th>What to do</th></tr></thead>',
           '<tbody>']
    modes = {}
    support = ""
    for n, (asset, label, cells, todo) in enumerate(_table_rows(alt, btc), start=1):
        b4w, b4b, c5w, c5b, _b5w, _b5b = cells
        note = f' <sup>{todo[1]}</sup>' if todo else ''
        if asset == "btc":
            b4w = ('(see <a href="/btc-cycles/predictive-ranges/">The '
                   'Prediction (BTC)</a>) ' + b4w)
        out.append(
            f'<tr><td>{n}</td><td><strong>{label}</strong></td>'
            f'<td>{b4w}</td><td>{b4b}</td><td>{c5w}</td><td>{c5b}</td>'
            f'<td>{todo[0]}{note}</td></tr>')
        sub = btc if asset == "btc" else alt[alt["asset"] == asset]
        bottom = sub[sub["zone"] == "bottom"]
        if not bottom.empty:
            modes[asset] = str(bottom.iloc[0].get("compression_fit_used", "") or "n/a")
            if asset == "gold":
                lo = _num(bottom.iloc[0].get("support_band_low"))
                hi = _num(bottom.iloc[0].get("support_band_high"))
                if lo and hi:
                    support = f"{_fmt(lo)} – {_fmt(hi)}"
    out.append('</tbody></table>')
    out.append('<ol class="table-dense-footnotes">')
    per_footnote_mode = {
        1: modes.get("xrp", "n/a"),
        2: modes.get("eth", "n/a"),
        3: "btc_2_stage",
        4: modes.get("sol", "n/a"),
        5: modes.get("mstr", "n/a"),
        6: modes.get("spx", "n/a"),
        7: modes.get("wgmi", "n/a"),
        8: modes.get("gold", "n/a"),
    }
    for n in sorted(FOOTNOTES):
        text = FOOTNOTES[n].format(mode=per_footnote_mode.get(n, "n/a"),
                                   support=support or "n/a")
        out.append(f'<li><sup>{n}</sup> {text}</li>')
    out.append('</ol>')
    return "\n".join(out)


def _c8d_caption(alt) -> str:
    """Caption for the macro panel: per-macro clauses, all from the CSV."""
    head = ("C8d — Macro assets own-cycle projection (I-19 shape, own timing). "
            "Zone dates come from each macro's own observed cycle durations "
            "anchored on its own last observed C4 top — not from BTC's halving "
            "calendar (halving-to-top lag spread 1.4y-2.6y vs ~0.2y for BTC; "
            "scripts/check_cycle_tie.py).")
    clauses = []
    for asset in ["spx", "ndx", "dxy", "tlt"]:
        sub = alt[alt["asset"] == asset]
        if sub.empty:
            continue
        b4w, b4b, c5w, c5b, b5w, b5b = _row_cells(asset, sub)
        clauses.append(f"{MACRO_LABELS[asset]}: B4 {b4b} ({b4w}); "
                        f"C5 {c5b} ({c5w}); B5 {b5b} ({b5w})")
    tail = ("I-21 regime status line at bottom (adjustments apply automatically "
            "when computed). See docs/blockers/I-19-macro-2stage.md")
    return head + " " + ". ".join(clauses) + ". " + tail + "."


def main() -> None:
    alt = pd.read_csv(ALT_ZONES, keep_default_na=False)
    btc = pd.read_csv(BTC_ZONES, keep_default_na=False)
    caps = build()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from csv_io import atomic_write_json, atomic_write_text
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(OUT, caps, indent=2)
    print(f"  chart captions written ({len(caps)}): {', '.join(sorted(caps))}")
    html = build_table_html(alt, btc)
    atomic_write_text(TABLE_INCLUDE, html + "\n", encoding="utf-8")
    print(f"  zone summary table written: {TABLE_INCLUDE}")

if __name__ == "__main__":
    main()

"""Export next-cycle (C5) zone maps as a single TradingView Pine overlay.

Reads the BTC zone map (data/processed/next_cycle_zones.csv) and the crypto
alt zone maps (data/processed/alt_next_cycle_zones.csv, assets eth/xrp/sol/mstr/wgmi)
and emits one self-contained Pine Script:

  data/processed/tv_pine/crypto_zones.pine

The script auto-selects zones per chart via syminfo.basecurrency: applied on
any BTC / ETH / XRP / SOL chart (any exchange) it draws the matching zone map;
symbols without a model zone draw nothing.

Usage:
    python scripts/export_tradingview_pine.py
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from csv_io import atomic_write_text
except ImportError:  # imported as scripts.export_tradingview_pine
    from scripts.csv_io import atomic_write_text

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
INPUT_BTC = PROCESSED / "next_cycle_zones.csv"
INPUT_ALTS = PROCESSED / "alt_next_cycle_zones.csv"
OUT_DIR = PROCESSED / "tv_pine"
OUTPUT = OUT_DIR / "crypto_zones.pine"
# Published copy — Jekyll excludes data/, so the site-facing script lives in
# assets/pine/. Both files are written by the same run so they never drift.
PUBLISH_DIR = ROOT / "assets" / "pine"
PUBLISHED = PUBLISH_DIR / "crypto_zones.pine"

ZONE_COLORS = {
    "bottom": "bottomCol",
    "top": "topCol",
    "b5_bottom": "b5Col",
}


def num(v: float) -> str:
    """Compact numeric literal for Pine (no trailing zeros)."""
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4f}".rstrip("0").rstrip(".")


def fmt_price(v: float) -> str:
    """Human-readable price for labels."""
    v = float(v)
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 10_000:
        return f"${v / 1000:.1f}k"
    if v >= 1000:
        return f"${v / 1000:.2f}k"
    if v >= 1:
        return f"${v:.2f}"
    return f"${v:.4f}"


def ts(date_str: str) -> str:
    """Pine timestamp() call from an ISO date string."""
    d = datetime.strptime(str(date_str), "%Y-%m-%d")
    return f"timestamp({d.year},{d.month},{d.day})"


def mid_date(start: str, end: str) -> str:
    """ISO midpoint date of a window (for center markers)."""
    d1 = datetime.strptime(str(start), "%Y-%m-%d")
    d2 = datetime.strptime(str(end), "%Y-%m-%d")
    return (d1 + (d2 - d1) / 2).strftime("%Y-%m-%d")


def box_line(left, top, right, bottom, color, tier, width=1) -> str:
    if tier == "base":
        b_transp, f_transp = "boxesBorderInput", "boxesFillInput"
        border_style = ""
    else:
        b_transp, f_transp = "outerBorderInput", "outerFillInput"
        border_style = ", border_style=line.style_dashed"
    return (
        f"box.new({ts(left)}, {num(top)}, {ts(right)}, {num(bottom)}, "
        f"xloc=xloc.bar_time, "
        f"border_color=color.new({color}, {b_transp}), border_width={width}"
        f"{border_style}, bgcolor=color.new({color}, {f_transp})"
        ")"
    )


def level_line(y: float, color: str) -> str:
    return (
        f"line.new(timestamp(2009,1,1), {num(y)}, timestamp(2036,1,1), {num(y)}, "
        f"xloc=xloc.bar_time, style=line.style_dotted, "
        f"color=color.new({color}, linesInput), width=1)"
    )


def asset_block(asset: str, zones: dict, guard: str | None = None) -> list[str]:
    """Render one asset's draws guarded by its syminfo match (basecurrency for crypto, ticker for equities)."""
    bear = zones["bottom"]
    dist = zones["top"]
    b5_ = zones["b5_bottom"]

    b4_center = float(bear["anchor_price"])
    b4_low = float(bear["price_low"])
    b4_high = float(bear["price_high"])
    c5_low = float(dist["price_low"])
    c5_high = float(dist["price_high"])
    c5_mid = (c5_low + c5_high) / 2.0
    c4_price = float(bear["observed_c4_top_price"])
    c4_date = str(bear["observed_c4_top_date"])

    body = []
    A = body.append
    A(f"// {asset.upper()}: observed C4 top (projection anchor)")
    A(level_line(c4_price, "c4Col"))
    A(
        f"label.new({ts(c4_date)}, {num(c4_price)}, "
        f"\"C4 top (obs) {fmt_price(c4_price)}\\n{c4_date}\", "
        "xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_label_down, color=color.new(c4Col, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A("")
    A(f"// {asset.upper()}: reference levels (model centers)")
    A(level_line(b4_center, "bottomCol"))
    A(level_line(c5_mid, "topCol"))
    A("")

    A(f"// {asset.upper()}: average prediction markers")
    A(
        f"label.new({ts(mid_date(bear['base_start'], bear['base_end']))}, {num(b4_center)}, "
        f"\"B4 {fmt_price(b4_center)}\", xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_diamond, color=color.new(bottomCol, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A(
        f"label.new({ts(mid_date(dist['base_start'], dist['base_end']))}, {num(c5_mid)}, "
        f"\"C5 {fmt_price(c5_mid)}\", xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_diamond, color=color.new(topCol, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A("")

    for zone in ("bottom", "top", "b5_bottom"):
        row = zones[zone]
        col = ZONE_COLORS[zone]
        s, e = row["base_start"], row["base_end"]
        os_, oe = row["outer_start"], row["outer_end"]

        if zone == "bottom":
            top, bottom = b4_high, b4_low
            text = f"B4 BEAR BOTTOM\\n{fmt_price(b4_center)} (band {fmt_price(b4_low)}-{fmt_price(b4_high)})\\n{s} -> {e}"
            label_y = b4_high * 1.02
        elif zone == "top":
            top, bottom = c5_high, c5_low
            text = f"C5 TOP (band)\\n{fmt_price(c5_low)}-{fmt_price(c5_high)}\\n{s} -> {e}"
            label_y = c5_high * 1.02
        else:
            ex_low, ex_high = float(b5_["price_low"]), float(b5_["price_high"])
            top, bottom = ex_high, ex_low
            # Was "EXIT / B5". B5 is the bear BOTTOM that follows the C5 top, so
            # it is a re-entry window -- "exit" on a low was inverted.
            text = f"B5 BEAR BOTTOM (re-entry)\\n{fmt_price(ex_low)}-{fmt_price(ex_high)}\\n{s} -> {e}"
            label_y = ex_high * 1.02

        A(f"// {asset.upper()}: {zone} (base + outer window)")
        A(box_line(os_, top, oe, bottom, col, "outer"))
        A(box_line(s, top, e, bottom, col, "base"))
        A(
            f"label.new({ts(e)}, {num(label_y)}, \"{text}\", "
            "xloc=xloc.bar_time, yloc=yloc.price, "
            f"style=label.style_label_down, color=color.new({col}, labelsInput), "
            "textcolor=color.new(color.white, labelsTextInput), size=size.small)"
        )
        A("")

    if guard is None:
        guard = f'syminfo.basecurrency == "{asset.upper()}"'
    lines = ["    if " + guard]
    lines += [("        " + ln if ln else "") for ln in body]
    return lines


def main() -> int:
    btc_df = pd.read_csv(INPUT_BTC)
    alts_df = pd.read_csv(INPUT_ALTS)

    guards = {
        "mstr": 'syminfo.ticker == "MSTR"',
        "wgmi": 'syminfo.ticker == "WGMI"',
    }
    blocks = []
    for asset in ("btc", "eth", "xrp", "sol", "mstr", "wgmi"):
        df = btc_df if asset == "btc" else alts_df[alts_df["asset"] == asset]
        if df.empty:
            print(f"ERROR: no rows for {asset}", file=sys.stderr)
            return 1
        zones = {row["zone"]: row.to_dict() for _, row in df.iterrows()}
        missing = [z for z in ("bottom", "accumulation", "top", "b5_bottom")
                   if z not in zones]
        if missing:
            print(f"ERROR {asset}: missing zones {missing}", file=sys.stderr)
            return 1
        blocks.append(asset_block(asset, zones, guard=guards.get(asset)))

    header = [
        "// TradingView Pine Script - Crypto next-cycle (C5) zones (BTC/ETH/XRP/SOL/MSTR/WGMI)",
        f"// Generated: {datetime.now().strftime('%Y-%m-%d')} by scripts/export_tradingview_pine.py",
        "// Sources: data/processed/next_cycle_zones.csv, data/processed/alt_next_cycle_zones.csv",
        "// Open chart: BITSTAMP:BTCUSD / COINBASE:ETHUSD / BINANCE:XRPUSDT / BINANCE:SOLUSDT / NASDAQ:MSTR / ARCA:WGMI (1D)",
        "// Zones auto-select via syminfo.basecurrency (crypto) or syminfo.ticker (MSTR, WGMI); non-model symbols draw nothing.",
        "//@version=6",
        'indicator("Crypto Cycle Zones (model)", overlay=true, '
        "max_boxes_count=200, max_labels_count=100, max_lines_count=50)",
        "",
        "// ---- Zone colors (pickers; transparency applied below) ----",
        'const string ZONE_COLORS_GROUP = "Zone colors"',
        'color bottomCol = input.color(color.blue,   "B4 bear-bottom zone", group=ZONE_COLORS_GROUP)',
        'color topCol    = input.color(color.orange, "C5 top zone",         group=ZONE_COLORS_GROUP)',
        'color b5Col     = input.color(color.purple, "B5 re-entry zone",   group=ZONE_COLORS_GROUP)',
        'color c4Col     = input.color(color.red,    "C4 top reference",   group=ZONE_COLORS_GROUP)',
        "",
        "// ---- Multi-SMA overlay ----",
        'const string SMA_GROUP = "Multi-SMA overlay"',
        'string smaTf   = input.timeframe("W", "SMA base timeframe (D = daily, reused in weekly views)", group=SMA_GROUP)',
        'int    smaLen1 = input.int(50,  "SMA 1 length (bars of base TF)", minval=1, group=SMA_GROUP)',
        'int    smaLen2 = input.int(100, "SMA 2 length (bars of base TF)", minval=1, group=SMA_GROUP)',
        'int    smaLen3 = input.int(200, "SMA 3 length (bars of base TF)", minval=1, group=SMA_GROUP)',
        'bool   showSma = input.bool(true, "Show SMAs", group=SMA_GROUP)',
        'color  sma1Col = input.color(color.blue,   "SMA 1 color", group=SMA_GROUP)',
        'color  sma2Col = input.color(color.orange, "SMA 2 color", group=SMA_GROUP)',
        'color  sma3Col = input.color(color.red,    "SMA 3 color", group=SMA_GROUP)',
        "",
        'f_sma(len) => request.security(syminfo.tickerid, smaTf, ta.sma(close, len), barmerge.gaps_off, barmerge.lookahead_on)',
        "float sma1 = f_sma(smaLen1)",
        "float sma2 = f_sma(smaLen2)",
        "float sma3 = f_sma(smaLen3)",
        "",
        'plot(showSma ? sma1 : na, "SMA 50",  color=sma1Col, linewidth=2)',
        'plot(showSma ? sma2 : na, "SMA 100", color=sma2Col, linewidth=2)',
        'plot(showSma ? sma3 : na, "SMA 200", color=sma3Col, linewidth=2)',
        "",
        "// ---- MA-anchored volume (LuxAlgo-style) ----",
        'const string VOL_GROUP = "MA-anchored volume"',
        'bool   showVol    = input.bool(true,  "Show volume", group=VOL_GROUP)',
        'string volAnchor  = input.string("SMA 2", "Anchor volume on", options=["SMA 1","SMA 2","SMA 3"], group=VOL_GROUP)',
        'string volSide    = input.string("Auto (away from price)", "Which side of the SMA", options=["Auto (away from price)","Candle direction","All above"], group=VOL_GROUP)',
        'int    volNormLen = input.int(200, "Normalization lookback (p95)", minval=10, group=VOL_GROUP)',
        'int    volAtrLen  = input.int(14,  "ATR length (height scale)", minval=1, group=VOL_GROUP)',
        'float  volHeight  = input.float(1.0, "Height multiplier", minval=0.1, maxval=5.0, step=0.1, group=VOL_GROUP)',
        'color  volUpCol   = input.color(color.new(color.teal, 55), "Up volume", group=VOL_GROUP)',
        'color  volDnCol   = input.color(color.new(color.red,  55), "Down volume", group=VOL_GROUP)',
        "",
        'float volAnchorMa = switch volAnchor',
        '    "SMA 1" => sma1',
        '    "SMA 2" => sma2',
        '    => sma3',
        "",
        "float volP95 = ta.percentile_nearest_rank(nz(volume), volNormLen, 95)",
        "float volAtr = ta.atr(volAtrLen)",
        "float volH   = volP95 > 0 and volAtr > 0 ? (nz(volume) / volP95) * volHeight * volAtr : 0.0",
        "bool  volUp  = close >= open",
        "bool  priceAbove = close >= volAnchorMa",
        "",
        "bool  drawAbove = switch volSide",
        '    "Auto (away from price)" => not priceAbove',
        '    "Candle direction"       => volUp',
        '    => true',
        "",
        "bool  volOk  = showVol and not na(volume) and not na(volAnchorMa)",
        "float volO   = volOk ? volAnchorMa : na",
        "float volC   = volOk ? (drawAbove ? volAnchorMa + volH : volAnchorMa - volH) : na",
        "float volHi  = volOk ? math.max(volO, volC) : na",
        "float volLo  = volOk ? math.min(volO, volC) : na",
        "color volCol = volUp ? volUpCol : volDnCol",
        "",
        'plotcandle(volO, volHi, volLo, volC, "Volume", color=volCol, wickcolor=color.new(color.gray, 100))',
        "",
        "const string OPACITY_GROUP = \"Element opacity (Style tab not available for drawings)\"",
        "int boxesFillInput = input.int(95, \"Zone fill transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int boxesBorderInput = input.int(85, \"Zone border transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int outerFillInput = input.int(98, \"Outer (extended) zone fill transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int outerBorderInput = input.int(85, \"Outer (extended) zone border transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int linesInput = input.int(0, \"Reference lines transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int labelsInput = input.int(0, \"Labels transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "int labelsTextInput = input.int(0, \"Label text transparency (0 = solid)\", minval = 0, maxval = 100, group = OPACITY_GROUP)",
        "",
    ]

    OUT_DIR.mkdir(exist_ok=True)
    for stale in ("btc", "eth", "xrp", "sol"):
        (OUT_DIR / f"{stale}.pine").unlink(missing_ok=True)

    lines = header[:]
    lines.append("if barstate.islast")
    for block in blocks:
        lines += block
    content = "\n".join(lines) + "\n"
    atomic_write_text(OUTPUT, content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    PUBLISH_DIR.mkdir(exist_ok=True)
    atomic_write_text(PUBLISHED, content, encoding="utf-8")
    print(f"published {PUBLISHED.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
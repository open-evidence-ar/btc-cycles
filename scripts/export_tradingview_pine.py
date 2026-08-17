"""Export next-cycle (C5) zone maps as a single TradingView Pine overlay.

Reads the BTC zone map (data/processed/next_cycle_zones.csv) and the crypto
alt zone maps (data/processed/alt_next_cycle_zones.csv, assets eth/xrp/sol)
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
    "bear_bottom": "blue",
    "distribution": "orange",
    "exit": "purple",
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
        border_style = ", border_style=box.border_style_dashed"
    return (
        f"box.new({ts(left)}, {num(top)}, {ts(right)}, {num(bottom)}, "
        f"xloc=xloc.bar_time, "
        f"border_color=color.new(color.{color}, {b_transp}), border_width={width}"
        f"{border_style}, bgcolor=color.new(color.{color}, {f_transp})"
        ")"
    )


def level_line(y: float, color: str) -> str:
    return (
        f"line.new(timestamp(2009,1,1), {num(y)}, timestamp(2036,1,1), {num(y)}, "
        f"xloc=xloc.bar_time, style=line.style_dotted, "
        f"color=color.new(color.{color}, linesInput), width=1)"
    )


def asset_block(asset: str, zones: dict) -> list[str]:
    """Render one asset's draws guarded by its syminfo.basecurrency match."""
    bear = zones["bear_bottom"]
    dist = zones["distribution"]
    exit_ = zones["exit"]

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
    A(level_line(c4_price, "red"))
    A(
        f"label.new({ts(c4_date)}, {num(c4_price)}, "
        f"\"C4 top (obs) {fmt_price(c4_price)}\\n{c4_date}\", "
        "xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_label_down, color=color.new(color.red, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A("")
    A(f"// {asset.upper()}: reference levels (model centers)")
    A(level_line(b4_center, "blue"))
    A(level_line(c5_mid, "orange"))
    A("")

    A(f"// {asset.upper()}: average prediction markers")
    A(
        f"label.new({ts(mid_date(bear['base_start'], bear['base_end']))}, {num(b4_center)}, "
        f"\"B4 {fmt_price(b4_center)}\", xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_diamond, color=color.new(color.blue, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A(
        f"label.new({ts(mid_date(dist['base_start'], dist['base_end']))}, {num(c5_mid)}, "
        f"\"C5 {fmt_price(c5_mid)}\", xloc=xloc.bar_time, yloc=yloc.price, "
        "style=label.style_diamond, color=color.new(color.orange, labelsInput), textcolor=color.new(color.white, labelsTextInput), size=size.small)"
    )
    A("")

    for zone in ("bear_bottom", "distribution", "exit"):
        row = zones[zone]
        col = ZONE_COLORS[zone]
        s, e = row["base_start"], row["base_end"]
        os_, oe = row["outer_start"], row["outer_end"]

        if zone == "bear_bottom":
            top, bottom = b4_high, b4_low
            text = f"B4 BEAR BOTTOM\\n{fmt_price(b4_center)} (band {fmt_price(b4_low)}-{fmt_price(b4_high)})\\n{s} -> {e}"
            label_y = b4_high * 1.02
        elif zone == "distribution":
            top, bottom = c5_high, c5_low
            text = f"C5 TOP (band)\\n{fmt_price(c5_low)}-{fmt_price(c5_high)}\\n{s} -> {e}"
            label_y = c5_high * 1.02
        else:
            ex_low, ex_high = float(exit_["price_low"]), float(exit_["price_high"])
            top, bottom = ex_high, ex_low
            text = f"EXIT / B5\\n{fmt_price(ex_low)}-{fmt_price(ex_high)}\\n{s} -> {e}"
            label_y = ex_high * 1.02

        A(f"// {asset.upper()}: {zone} (base + outer window)")
        A(box_line(os_, top, oe, bottom, col, "outer"))
        A(box_line(s, top, e, bottom, col, "base"))
        A(
            f"label.new({ts(e)}, {num(label_y)}, \"{text}\", "
            "xloc=xloc.bar_time, yloc=yloc.price, "
            f"style=label.style_label_down, color=color.new(color.{col}, labelsInput), "
            "textcolor=color.new(color.white, labelsTextInput), size=size.small)"
        )
        A("")

    lines = ["    if syminfo.basecurrency == \"" + asset.upper() + "\""]
    lines += [("        " + ln if ln else "") for ln in body]
    return lines


def main() -> int:
    btc_df = pd.read_csv(INPUT_BTC)
    alts_df = pd.read_csv(INPUT_ALTS)

    blocks = []
    for asset in ("btc", "eth", "xrp", "sol"):
        df = btc_df if asset == "btc" else alts_df[alts_df["asset"] == asset]
        if df.empty:
            print(f"ERROR: no rows for {asset}", file=sys.stderr)
            return 1
        zones = {row["zone"]: row.to_dict() for _, row in df.iterrows()}
        missing = [z for z in ("bear_bottom", "accumulation", "distribution", "exit")
                   if z not in zones]
        if missing:
            print(f"ERROR {asset}: missing zones {missing}", file=sys.stderr)
            return 1
        blocks.append(asset_block(asset, zones))

    header = [
        "// TradingView Pine Script - Crypto next-cycle (C5) zones (BTC/ETH/XRP/SOL)",
        f"// Generated: {datetime.now().strftime('%Y-%m-%d')} by scripts/export_tradingview_pine.py",
        "// Sources: data/processed/next_cycle_zones.csv, data/processed/alt_next_cycle_zones.csv",
        "// Open chart: BITSTAMP:BTCUSD / COINBASE:ETHUSD / BINANCE:XRPUSDT / BINANCE:SOLUSDT (1D)",
        "// Zones auto-select via syminfo.basecurrency; non-model symbols draw nothing.",
        "//@version=6",
        'indicator("Crypto Cycle Zones (model)", overlay=true, '
        "max_boxes_count=100, max_labels_count=50, max_lines_count=50)",
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
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    PUBLISH_DIR.mkdir(exist_ok=True)
    PUBLISHED.write_text(content, encoding="utf-8")
    print(f"published {PUBLISHED.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
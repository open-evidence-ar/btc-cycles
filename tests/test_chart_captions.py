"""Figure captions must be generated, never transcribed.

Every ``{% include chart.html %}`` caption used to be a hand-written string
carrying hard-coded numbers. They went stale silently on each refresh and the
site published prices that contradicted the chart directly above them -- C8's
caption advertised a C5 top band of $3,130-$9,652 while the zone CSV carried
$16,648.91-$190,052.96. The same transcription defect also lived in the chart
*subtitles* (see ``scripts/build_charts.py::_mode_prose``).

Captions now come from ``scripts/build_chart_captions.py`` into
``_data/chart_captions.json``. This gate pins both halves of that contract:

1. no include may contain a hand-written ``$`` number in its caption;
2. every referenced caption key must exist in the generated JSON, and its
   numbers must match the zone CSVs it was built from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ROOT / "_sections"
CAPTIONS_JSON = ROOT / "_data" / "chart_captions.json"
ALT_ZONES = ROOT / "data" / "processed" / "alt_next_cycle_zones.csv"
BTC_ZONES = ROOT / "data" / "processed" / "next_cycle_zones.csv"

INCLUDE = re.compile(r"\{%\s*include\s+chart\.html(.*?)%\}", re.S)
MONEY = re.compile(r"\$\s?[\d,]+(?:\.\d+)?")

# Sections whose numbers are all generated. A hand-written price here is
# transcription, and transcription drifts: the cross-asset-timing summary table
# published ETH B4 "$298 - $1,000" against the real $1,153.82 - $2,092.47, and
# XRP/SOL were similarly wrong, while the generated captions directly below the
# table carried the true bands.
GENERATED_SECTIONS = ["cross-asset-timing.md", "cross-asset.md"]

TABLE_INCLUDE = ROOT / "_includes" / "zone-summary-table.html"


def test_no_handwritten_prices_in_generated_sections():
    """No `$<digit>` may be hand-written in the generated-number sections.

    Every price in these two files comes from _data/chart_captions.json or
    _includes/zone-summary-table.html, both emitted by
    scripts/build_chart_captions.py from the same zone CSVs the charts read.
    """
    offenders = []
    for name in GENERATED_SECTIONS:
        path = SECTIONS / name
        text = path.read_text(encoding="utf-8")
        # Liquid interpolations are the generated channel; anything else is
        # hand-written.
        scrub = re.sub(r"\{\{.*?\}\}", "", text)
        scrub = re.sub(r"\{%.*?%\}", "", scrub)
        for m in MONEY.finditer(scrub):
            offenders.append(f"{name}: {m.group(0)}")
    assert not offenders, (
        "Hand-written price numbers found in the generated-number sections. "
        "Reference site.data.chart_captions.<ID> or the "
        "zone-summary-table.html include instead:\n  "
        + "\n  ".join(offenders)
    )


def test_zone_summary_table_matches_zone_data():
    """The generated summary table must reflect the CURRENT zone CSVs.

    The include is a build artefact: if the pipeline runs the zone builders but
    skips scripts/build_chart_captions.py (or someone edits the include by
    hand), the site publishes a stale table again -- exactly the defect this
    generator exists to prevent. Every priced zone band must therefore appear
    in the include exactly as the CSV computes it.
    """
    assert TABLE_INCLUDE.is_file(), (
        "_includes/zone-summary-table.html missing -- run "
        "scripts/build_chart_captions.py"
    )
    html = TABLE_INCLUDE.read_text(encoding="utf-8")
    alt = pd.read_csv(ALT_ZONES, keep_default_na=False)
    btc = pd.read_csv(BTC_ZONES, keep_default_na=False)

    def fmt(p):
        p = float(p)
        if p < 1:
            return f"${p:,.4f}"
        if p < 100:
            return f"${p:,.2f}"
        return f"${p:,.0f}"

    checked = 0
    for rows in (alt, btc):
        for _, r in rows.iterrows():
            if r.get("zone") not in ("bottom", "top"):
                continue
            try:
                lo_f, hi_f = float(r["price_low"]), float(r["price_high"])
            except (TypeError, ValueError):
                continue
            if lo_f <= 0 or hi_f <= 0:
                continue
            pair = f"{fmt(lo_f)} – {fmt(hi_f)}"
            asset = str(r.get("asset", "btc"))
            assert pair in html, (
                f"zone-summary-table.html is missing the {asset} {r['zone']} "
                f"band {pair}; the include has gone stale against the zone CSVs"
            )
            checked += 1
    assert checked >= 20, (
        f"only {checked} bands checked -- the table/CSV shape changed; update "
        "this gate"
    )


def _includes():
    for md in sorted(SECTIONS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for m in INCLUDE.finditer(text):
            body = m.group(1)
            cid = re.search(r'id="([^"]+)"', body)
            if cid:
                yield md.name, cid.group(1), body


def test_no_handwritten_numbers_in_captions():
    """A ``$`` inside a literal caption attribute is transcription; forbid it."""
    offenders = []
    for name, cid, body in _includes():
        cap = re.search(r'caption="(.*)"\s*$', body.strip(), re.S)
        if not cap:
            continue
        literal = cap.group(1)
        # Numbers injected via {{ site.data... }} are fine; numbers typed into
        # the markdown are not.
        literal = re.sub(r"\{\{.*?\}\}", "", literal)
        for tok in MONEY.findall(literal):
            offenders.append(f"{name}: {cid} -> {tok}")
    assert not offenders, (
        "Hand-written price numbers found in chart captions. Captions are "
        "generated by scripts/build_chart_captions.py; reference them as "
        "caption=site.data.chart_captions.<ID> instead:\n  "
        + "\n  ".join(offenders)
    )


def test_captions_file_exists_and_covers_referenced_charts():
    assert CAPTIONS_JSON.is_file(), (
        "_data/chart_captions.json missing -- run scripts/build_chart_captions.py"
    )
    caps = json.loads(CAPTIONS_JSON.read_text(encoding="utf-8"))
    referenced = set()
    for _name, _cid, body in _includes():
        for key in re.findall(r"chart_captions\.([A-Za-z0-9_]+)", body):
            referenced.add(key)
    missing = referenced - set(caps)
    assert not missing, (
        f"markdown references caption keys that were never generated: {sorted(missing)}"
    )


def test_generated_caption_numbers_match_zone_data():
    """Every zone band in a generated caption must appear in the zone CSV."""
    caps = json.loads(CAPTIONS_JSON.read_text(encoding="utf-8"))
    alt = pd.read_csv(ALT_ZONES, keep_default_na=False)
    btc = pd.read_csv(BTC_ZONES, keep_default_na=False)

    def fmt(p):
        p = float(p)
        if p < 1:
            return f"${p:,.4f}"
        if p < 100:
            return f"${p:,.2f}"
        return f"${p:,.0f}"

    mapping = {
        "C8": alt[alt["asset"] == "eth"],
        "C8b": alt[alt["asset"] == "xrp"],
        "C8c": alt[alt["asset"] == "sol"],
        "C8e": alt[alt["asset"] == "mstr"],
        "C8f": alt[alt["asset"] == "wgmi"],
        "C8g": alt[alt["asset"] == "gold"],
        "C6": btc,
        # C8d is the 4-macro panel: every macro's bottom+top band must appear.
        "C8d": alt[alt["asset"].isin(["spx", "ndx", "dxy", "tlt"])],
    }
    for cid, rows in mapping.items():
        if cid not in caps or rows.empty:
            continue
        caption = caps[cid]
        for _, r in rows.iterrows():
            lo, hi = r.get("price_low"), r.get("price_high")
            try:
                lo_f, hi_f = float(lo), float(hi)
            except (TypeError, ValueError):
                continue
            if lo_f <= 0 or hi_f <= 0:
                continue
            # _zone_clause renders "lo–hi" (no spaces); the C8d panel caption
            # renders "lo – hi". Accept either so the test follows the data,
            # not the typography.
            pair = f"{fmt(lo_f)}–{fmt(hi_f)}"
            pair_spaced = f"{fmt(lo_f)} – {fmt(hi_f)}"
            assert pair in caption or pair_spaced in caption, (
                f"{cid} caption is missing the {r['zone']} band {pair}; the "
                f"caption and zone row have diverged"
            )

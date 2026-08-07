"""I-16 validation gate: automated portion of the 16-item manual release checklist.

The DESIGN.md §10.2 release checklist has 16 items; 9 of them are mechanically
verifiable from the repository contents and are enforced here. The remaining 7
are inherently human-in-the-loop (site loads at the published URL, charts render
in a real browser, GitHub repo metadata, etc.) and are re-reviewed only at
release cuts.
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS_DIR = ROOT / "_sections"
LAYOUT_FILE = ROOT / "_layouts" / "default.html"


def _events_csv_sha() -> str:
    return hashlib.sha256(
        (ROOT / "data" / "events.csv").read_bytes()
    ).hexdigest()


def test_sidebar_links_to_all_sections():
    """Item 2: every section reachable from sidebar TOC.
    Site is single-page form: sidebar links are `#section-anchor` not full URLs."""
    layout = LAYOUT_FILE.read_text(encoding="utf-8")
    expected = {
        "abstract",
        "methodology",
        "cycle-anatomy",
        "cross-asset",
        "predictive-ranges",
        "validation",
        "release-checklist",
        "status",
    }
    for slug in expected:
        anchor = f"#{slug}"
        token = f"href=\"{anchor}\""
        # Accept either anchor link (#slug) or full path (/slug/) in the layout
        # (deep-link URLs are still useful for sharing).
        assert (token in layout) or (f"/{slug}/" in layout), (
            f"sidebar nav missing link to {slug}"
        )


def test_provenance_footer_on_sections():
    """Item 4: provenance footer present on every published section."""
    skip = {"release-checklist.md"}
    for path in SECTIONS_DIR.glob("*.md"):
        if path.name in skip:
            continue
        text = path.read_text(encoding="utf-8")
        has_footer = (
            "manifest.txt" in text
            or "data/processed" in text
            or "data/raw" in text
        )
        assert has_footer, f"{path.name} missing provenance footer"


def test_events_sha_in_methodology():
    """Item 5: data/events.csv SHA matches the one quoted in the methodology section."""
    actual = _events_csv_sha()
    methodology = (SECTIONS_DIR / "methodology.md").read_text(encoding="utf-8")
    assert actual in methodology, (
        f"methodology.md does not quote current events.csv SHA ({actual}). "
        "Update the SHA reference after any events.csv change."
    )


def test_manifest_lists_eight_series():
    """Item 6: manifest lists all panel series with non-empty SHA256."""
    manifest = (ROOT / "data" / "raw" / "manifest.txt").read_text(encoding="utf-8")
    lines = [ln for ln in manifest.splitlines() if ln.strip() and not ln.startswith("symbol")]
    assert len(lines) >= 12, f"manifest must list all panel + proxy series, found {len(lines)}"
    required = {"btc", "eth", "xrp", "sol", "mstr", "wgmi", "riot", "mara", "spx", "ndx", "dxy", "tlt", "gold"}
    present = {ln.split("\t")[0] for ln in lines}
    missing = required - present
    assert not missing, f"manifest missing series: {missing}"
    for ln in lines:
        cols = ln.split("\t")
        assert cols[0] in required, f"unexpected symbol {cols[0]}"
        sha = cols[5] if len(cols) > 5 else ""
        assert re.fullmatch(r"[0-9a-f]{64}", sha), (
            f"{cols[0]}: sha256 column must be 64-hex, got {sha!r}"
        )


def test_backtest_table_in_validation():
    """Item 7: backtest-by-cycle table visible in validation section."""
    text = (SECTIONS_DIR / "validation.md").read_text(encoding="utf-8")
    assert "backtest_by_cycle" in text or "LOOCO Backtest" in text, (
        "validation.md must reference the backtest-by-cycle table"
    )
    assert "backtest_by_cycle.csv" in text or "Leave-one" in text.lower() \
        or "LOOCO" in text, "validation.md must mention LOOCO backtest"


def test_forward_ranges_table_in_predictive():
    """Item 8: forward ranges + LOOCO sensitivity table visible in predictive-ranges section."""
    text = (SECTIONS_DIR / "predictive-ranges.md").read_text(encoding="utf-8")
    assert "forward_ranges.csv" in text or "Forward Range" in text, \
        "predictive-ranges.md must reference forward_ranges.csv"
    assert "LOOCO" in text or "Sensitive" in text, \
        "predictive-ranges.md must include LOOCO sensitivity reporting"


def test_no_todo_fixme_in_sections():
    """Item 9: no TODO / FIXME / placeholder strings in published sections."""
    banned = ("TODO", "FIXME", "placeholder")
    for path in SECTIONS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, (
                f"{path.name} contains banned token '{token}'"
            )


def test_license_present():
    """Item 12: LICENSE file present (CC-BY-4.0 for the white paper; MIT for code)."""
    license_file = ROOT / "LICENSE"
    assert license_file.is_file(), "LICENSE file missing"
    text = license_file.read_text(encoding="utf-8")
    assert "CC-BY-4.0" in text or "Creative Commons Attribution 4.0" in text, \
        "LICENSE must cover white-paper content under CC-BY-4.0"
    assert "MIT" in text, "LICENSE must cover software code under MIT"


def test_agents_md_present():
    """Item 14: AGENTS.md documents the increment workflow for future contributors."""
    agents = ROOT / "AGENTS.md"
    assert agents.is_file(), "AGENTS.md missing"
    text = agents.read_text(encoding="utf-8")
    assert "I-00" in text and "I-16" in text, \
        "AGENTS.md must reference the increment workflow (I-00..I-16)"


def test_release_checklist_section_exists():
    """The release-checklist page itself must exist and be linked from the sidebar."""
    rc = SECTIONS_DIR / "release-checklist.md"
    assert rc.is_file(), "release-checklist.md section missing"
    text = rc.read_text(encoding="utf-8")
    assert "16-item" in text or "16 item" in text.lower(), \
        "release-checklist.md must reference the 16-item checklist"


def test_disclaimer_footer_in_layout():
    """Item 16: author/maintainer + disclaimer footer rendered via the layout include."""
    footer = (ROOT / "_includes" / "provenance-footer.html").read_text(encoding="utf-8")
    assert "Disclaimer" in footer or "disclaimer" in footer, \
        "provenance-footer.html must include a disclaimer"
    assert "financial advice" in footer.lower() or "not financial" in footer.lower(), \
        "footer must include the not-financial-advice disclaimer"
    layout = LAYOUT_FILE.read_text(encoding="utf-8")
    assert "provenance-footer" in layout, \
        "default layout must include provenance-footer.html"


def test_readme_has_quickstart():
    """Item 13 (auto portion): README has pytest / jekyll / bundle quickstart."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for token in ["pytest", "jekyll build", "bundle"]:
        assert token in readme, f"README.md missing quickstart reference to {token!r}"

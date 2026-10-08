import hashlib
import json
import platform
from pathlib import Path

CHARTS_DIR = Path('assets/charts')
SNAPSHOT_FILE = Path('tests/chart_snapshots.json')
CHART_IDS = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C8b', 'C8c', 'C8d', 'C8g', 'C8h', 'C9', 'C-SMA']


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def test_all_html_files_exist():
    for cid in CHART_IDS:
        path = CHARTS_DIR / f'{cid}.html'
        assert path.exists(), f"Missing: {path}"


def test_all_png_files_exist():
    for cid in CHART_IDS:
        path = CHARTS_DIR / f'{cid}.png'
        assert path.exists(), f"Missing: {path}"


def test_html_files_nonempty():
    for cid in CHART_IDS:
        path = CHARTS_DIR / f'{cid}.html'
        assert path.stat().st_size > 1000, f"{cid}.html too small: {path.stat().st_size}"


def test_png_files_nonempty():
    for cid in CHART_IDS:
        path = CHARTS_DIR / f'{cid}.png'
        assert path.stat().st_size > 10000, f"{cid}.png too small: {path.stat().st_size}"


def test_html_contains_plotly():
    """Each HTML file should contain embedded Plotly JSON."""
    for cid in CHART_IDS:
        path = CHARTS_DIR / f'{cid}.html'
        content = path.read_text(encoding='utf-8', errors='ignore')
        assert 'plotly' in content.lower(), f"{cid}.html missing Plotly content"


def _load_snapshot():
    """Read chart_snapshots.json, separating pins from the reserved ``platform`` key.

    Rendered PNG bytes are deterministic on one platform (fonts,
    anti-aliasing, kaleido/Chromium) but differ across platforms, so strict
    SHA comparison is only meaningful where the platform matches the pins.
    Returns (pins, enforce): enforce is True only on the recorded platform;
    elsewhere callers must assert presence/non-trivial size instead of bytes.
    """
    stored = json.loads(SNAPSHOT_FILE.read_text()) if SNAPSHOT_FILE.exists() else {}
    pins = {k: v for k, v in stored.items() if k != "platform"}
    enforce = bool(pins) and stored.get("platform") == platform.system().lower()
    return pins, enforce


def test_png_determinism():
    """PNG SHA-256 should match stored snapshot (determinism test).

    Iterates over every PNG in assets/charts, so the snapshot file is the
    source of truth (CHART_IDS only covers charts with HTML output).
    First run: stores snapshots. Subsequent runs: compare bytes on the
    recorded platform; on any other platform assert every chart renders
    non-trivially instead, because cross-platform byte equality of rendered
    PNGs is not expected.
    """
    current = {}
    for png in sorted(CHARTS_DIR.glob('*.png')):
        current[png.stem] = _sha256(png)

    pins, enforce = _load_snapshot()
    if not pins:
        payload = {"platform": platform.system().lower()}
        payload.update(current)
        SNAPSHOT_FILE.write_text(json.dumps(payload, indent=2))
        print(f"  Stored initial snapshots to {SNAPSHOT_FILE}")
        return

    for cid in sorted(pins):
        assert cid in current, f"No PNG on disk for snapshot {cid}"
    for cid in current:
        assert cid in pins, f"No stored snapshot for {cid}"

    if enforce:
        for cid in sorted(pins):
            assert current[cid] == pins[cid], (
                f"{cid}.png SHA changed: {pins[cid]} -> {current[cid]}"
            )
    else:
        for cid in sorted(current):
            size = (CHARTS_DIR / f"{cid}.png").stat().st_size
            assert size > 10000, (
                f"{cid}.png suspiciously small ({size}B); cross-platform byte "
                "equality is not expected, but every chart must still render"
            )
        print("  PNG SHA comparison skipped (pins recorded on a different platform)")


def test_all_chart_pngs_pinned():
    """Every PNG in assets/charts must be present in the snapshot file.

    Guards against chart outputs being added to the site without a pinned
    determinism snapshot (Fix 7: C-CAL, C8e, C8f, C8h were previously unpinned).
    """
    stored = json.loads(SNAPSHOT_FILE.read_text()) if SNAPSHOT_FILE.exists() else {}
    on_disk = sorted(p.name for p in CHARTS_DIR.glob('*.png'))
    missing = [name for name in on_disk if name[:-4] not in stored]
    assert not missing, f"Unpinned chart PNGs (no snapshot entry): {missing}"


if __name__ == '__main__':
    test_all_html_files_exist()
    print("PASS: test_all_html_files_exist")
    test_all_png_files_exist()
    print("PASS: test_all_png_files_exist")
    test_html_files_nonempty()
    print("PASS: test_html_files_nonempty")
    test_png_files_nonempty()
    print("PASS: test_png_files_nonempty")
    test_html_contains_plotly()
    print("PASS: test_html_contains_plotly")
    test_png_determinism()
    print("PASS: test_png_determinism")
    print("\nALL TESTS PASSED!")

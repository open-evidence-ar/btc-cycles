"""Smoke tests for scripts/refresh_all.py.

Validates that the single-command refresh pipeline is structurally correct
and can execute the --dry-run and --no-fetch modes without error.

Note: --no-fetch takes ~90s (runs all build_*.py + chart render).  This is
intentionally slow — it proves the full pipeline is end-to-end reproducible.
"""

import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "refresh_all.py"
CHARTS_DIR = ROOT / "assets" / "charts"
PROCESSED = ROOT / "data" / "processed"


def _run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )


def test_refresh_all_exists():
    assert SCRIPT.is_file(), f"Missing script: {SCRIPT}"


def test_refresh_all_importable():
    """Script should be importable without side effects."""
    r = subprocess.run(
        [sys.executable, "-c", "import importlib.util; "
         "spec=importlib.util.spec_from_file_location('r','scripts/refresh_all.py'); "
         "mod=importlib.util.module_from_spec(spec); "
         "spec.loader.exec_module(mod)"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, f"Import failed: {r.stderr[-300:]}"


def test_refresh_all_dry_run():
    r = _run(["--dry-run"], timeout=30)
    assert r.returncode == 0, f"--dry-run failed: {r.stdout[-300:]}\n{r.stderr[-300:]}"
    assert "DRY RUN complete" in r.stdout
    assert "17 steps" in r.stdout or "steps" in r.stdout


def test_refresh_all_no_fetch():
    """Full rebuild from existing data (no network). ~90s on typical hardware."""
    r = _run(["--no-fetch"], timeout=600)
    assert r.returncode == 0, f"--no-fetch failed: {r.stdout[-500:]}\n{r.stderr[-500:]}"
    assert "ALL OK" in r.stdout


def test_refresh_all_produces_output_files():
    """After a --no-fetch run, all expected processed artefacts exist and are non-empty."""
    expected_files = [
        PROCESSED / "btc_cycle_metrics.csv",
        PROCESSED / "btc_sma_floors.csv",
        PROCESSED / "forward_ranges.csv",
        PROCESSED / "next_cycle_zones.csv",
        PROCESSED / "backtest_by_cycle.csv",
        PROCESSED / "correlations_BY_regime.csv",
        PROCESSED / "correlations_phase.csv",
        PROCESSED / "correlations_rolling.csv",
    ]
    for f in expected_files:
        assert f.is_file(), f"Missing output: {f}"
        assert f.stat().st_size > 0, f"Empty output: {f}"


def test_refresh_all_produces_charts():
    """After a --no-fetch run, all expected chart PNGs exist and are non-empty."""
    expected_charts = [f"C{i}.png" for i in range(1, 10)] + ["C-SMA.png"]
    for name in expected_charts:
        p = CHARTS_DIR / name
        assert p.is_file(), f"Missing chart: {p}"
        assert p.stat().st_size > 1000, f"Chart too small ({p.stat().st_size}B): {p}"


def test_build_cycle_status_runs():
    """scripts/build_cycle_status.py runs end-to-end and emits valid JSON."""
    script = ROOT / "scripts" / "build_cycle_status.py"
    out = ROOT / "_data" / "cycle_status.json"
    if not script.is_file():
        return  # not built yet; skip
    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=30,
    )
    assert r.returncode == 0, f"build_cycle_status.py failed: {r.stderr[-300:]}"
    assert out.is_file(), "cycle_status.json not written"
    data = json.loads(out.read_text(encoding="utf-8"))
    # Required top-level keys
    for key in ("btc", "alt_watch_order", "current_phase_hint"):
        assert key in data, f"Missing top-level key: {key}"
    # Required BTC sub-keys
    btc = data["btc"]
    for key in ("last_observed_event", "next_window", "later_windows"):
        assert key in btc, f"Missing btc.{key}"
    # Exec labels must be present (used by the banner JS)
    assert btc["last_observed_event"].get("exec_label"), "missing last_observed exec_label"
    assert btc["next_window"].get("exec_label"), "missing next_window exec_label"
    for w in btc["later_windows"]:
        assert w.get("exec_label"), f"missing exec_label on later window {w.get('label')}"
    # Next-window price strings must not be corrupted (the previous known bug)
    pl = btc["next_window"]["price_low"]
    ph = btc["next_window"]["price_high"]
    assert pl.startswith("$") and ph.startswith("$"), \
        f"Price strings corrupted: price_low={pl!r} price_high={ph!r}"
    # alt_watch_order must contain BTC (anchor) plus XRP, ETH, SOL
    assets = {a["asset"] for a in data["alt_watch_order"]}
    assert {"BTC", "XRP", "ETH", "SOL"} <= assets, \
        f"alt_watch_order missing assets: got {assets}"

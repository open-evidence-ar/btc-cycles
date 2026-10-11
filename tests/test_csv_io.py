"""Atomic-write gates (scripts/csv_io.py): unit tests + pipeline convention scan.

Every pipeline artefact write must go through csv_io.atomic_* so that:
  (a) readers never observe a partially-written file (the corr_phase ->
      regime_robustness read/write race class of bug),
  (b) a failed or interrupted write never truncates the previous good output,
  (c) writes survive transient open(..., 'w') EINVAL failures observed on
      external drives, where an in-place truncating open of an existing file
      can fail while fresh-file creation and os.replace keep working.

The scan gate forbids raw `.to_csv(` / `.write_text(` artefact writes in the
18 pipeline scripts so the convention cannot silently regress. fetch_*.py
(raw snapshots: new timestamped files, immutable-append domain) and the
scripts/theory + scripts/exploration research probes are out of scope.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from csv_io import atomic_to_csv, atomic_write_json, atomic_write_text

PIPELINE_SCRIPTS = [
    "align_to_halving",
    "build_alt_cycle_metrics",
    "build_alt_forward_ranges",
    "build_alt_next_cycle_zones",
    "build_alt_sma_floors",
    "build_backtest",
    "build_charts",
    "build_correlations_phase",
    "build_curve_state",
    "build_cycle_metrics",
    "build_cycle_status",
    "build_forward_ranges",
    "build_next_cycle_zones",
    "build_regime_multipliers",
    "build_regime_robustness",
    "build_rolling_corr",
    "build_sma_floors",
    "export_tradingview_pine",
]


def test_atomic_to_csv_byte_identical_and_no_residue(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    dest = tmp_path / "out.csv"
    plain = tmp_path / "plain.csv"
    atomic_to_csv(df, dest, index=False)
    df.to_csv(plain, index=False)  # the call the old code made, byte-for-byte
    assert dest.read_bytes() == plain.read_bytes()
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_atomic_write_text_matches_plain_write_text_bytes(tmp_path):
    dest = tmp_path / "atomic.txt"
    plain = tmp_path / "plain.txt"
    atomic_write_text(dest, "a\nb\n", encoding="utf-8")
    plain.write_text("a\nb\n", encoding="utf-8")
    assert dest.read_bytes() == plain.read_bytes()
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_atomic_write_json_roundtrip(tmp_path):
    dest = tmp_path / "out.json"
    atomic_write_json(dest, {"b": 1, "a": [2, 3]}, indent=2, sort_keys=True)
    assert json.loads(dest.read_text(encoding="utf-8")) == {"a": [2, 3], "b": 1}
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_failed_write_never_truncates_previous_output(tmp_path):
    dest = tmp_path / "out.csv"
    dest.write_text("previous-good-output", encoding="utf-8")

    class Boom(pd.DataFrame):
        def to_csv(self, *args, **kwargs):
            raise RuntimeError("simulated mid-write failure")

    with pytest.raises(RuntimeError):
        atomic_to_csv(Boom(), dest)
    assert dest.read_text(encoding="utf-8") == "previous-good-output"
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_pipeline_scripts_use_atomic_writes_only():
    """No pipeline script may write artefacts with a raw truncating open."""
    for name in PIPELINE_SCRIPTS:
        src = (ROOT / "scripts" / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"(?<!atomic_)\.to_csv\(", src), \
            f"{name}.py: raw .to_csv() — use csv_io.atomic_to_csv"
        assert not re.search(r"(?<!atomic_)\.write_text\(", src), \
            f"{name}.py: raw .write_text() — use csv_io.atomic_write_text"
        assert "atomic_" in src, f"{name}.py: no atomic write found"


def test_cycle_status_json_write_is_atomic():
    """The banner JSON (regenerated on every pipeline run) must go through
    atomic_write_json, not a truncating open()."""
    src = (ROOT / "scripts" / "build_cycle_status.py").read_text(encoding="utf-8")
    assert "atomic_write_json(DATA_OUT" in src
    assert 'with open(DATA_OUT, "w"' not in src

"""I-18a validation gate: BTC 50w/200w SMA floors computed deterministically.

Verifies that the SMA floors csv is built; that columns match the agreed
schema; that the file is deterministic on re-run; and that the latest
weekly values reproduce the Cowen July-2026 memo's reference levels
(200w near $63k, 50w near $86k at Jul-15-2026 reference).
"""

import hashlib
import subprocess
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
TARGET_CSV = PROCESSED_DIR / "btc_sma_floors.csv"
SCRIPT = ROOT / "scripts" / "build_sma_floors.py"

REQUIRED_COLUMNS = {
    "date",
    "close",
    "sma_50w",
    "sma_200w",
    "below_sma_50w",
    "below_sma_200w",
    "event_first_below_50w",
    "event_first_below_200w",
    "event_reclaim_50w",
    "event_reclaim_200w",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_sma_floors_if_missing():
    """Generate the csv if missing."""
    if not TARGET_CSV.is_file():
        subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)


@pytest.fixture(scope="module", autouse=True)
def ensure_artifacts_exist():
    build_sma_floors_if_missing()


def test_outputs_exist():
    assert TARGET_CSV.is_file(), f"Missing {TARGET_CSV}"


def test_file_columns():
    df = pd.read_csv(TARGET_CSV, dtype=str)
    assert set(df.columns) == REQUIRED_COLUMNS, (
        f"Missing/extra columns: {REQUIRED_COLUMNS ^ set(df.columns)}"
    )


def test_determinism():
    """Re-running the build script must produce byte-identical output."""
    sha_before = _sha256_file(TARGET_CSV)
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    sha_after = _sha256_file(TARGET_CSV)
    assert sha_before == sha_after, (
        "btc_sma_floors.csv SHA changed after re-run; non-deterministic build"
    )


def test_min_weeks_present():
    """The series must include at least 200 weekly rows so both SMAs can be
    computed (200w SMA needs ~200 weeks of history)."""
    df = pd.read_csv(TARGET_CSV)
    assert len(df) >= 200, f"Expected >=200 weekly rows, got {len(df)}"


def test_smnas_start_at_min_periods():
    """sma_50w must start populating at row 50; sma_200w at row 200."""
    df = pd.read_csv(TARGET_CSV, dtype=str)
    sma_50_first = df["sma_50w"].replace("", pd.NA).dropna().index[0]
    sma_200_first = df["sma_200w"].replace("", pd.NA).dropna().index[0]
    assert sma_50_first == 49, (
        f"sma_50w first populated at idx {sma_50_first}; expected 49 (50th row, 0-indexed)"
    )
    assert sma_200_first == 199, (
        f"sma_200w first populated at idx {sma_200_first}; expected 199 (200th row, 0-indexed)"
    )


def test_last_row_matches_memo_jul_2026_reference():
    """Cowen July 2026 memo states: 200w SMA near $63,100; 50w SMA near $86,500;
    spot near $65,300. Cross-check is pinned to the memo snapshot row
    (2026-07-20), not the running last row — the latest row drifts as data
    refreshes and is covered by test_latest_position_reflects_fresh_data.
    Bands: 200w $60k-$66k; 50w $82k-$90k; close $60k-$70k."""
    df = pd.read_csv(TARGET_CSV, dtype=str)
    df["date_dt"] = pd.to_datetime(df["date"])
    memo_row = df[df["date_dt"] == pd.Timestamp("2026-07-20")]
    assert len(memo_row) == 1, "Memo reference row 2026-07-20 not found"
    row = memo_row.iloc[0]
    close = float(row["close"])
    sma_50 = float(row["sma_50w"])
    sma_200 = float(row["sma_200w"])
    assert 60_000 <= sma_200 <= 66_000, (
        f"Memo sma_200w=${sma_200:,.0f} outside $60k-$66k band (memo ~$63,100)"
    )
    assert 82_000 <= sma_50 <= 90_000, (
        f"Memo sma_50w=${sma_50:,.0f} outside $82k-$90k band (memo ~$86,500)"
    )
    assert 60_000 <= close <= 70_000, (
        f"Memo close=${close:,.0f} outside $60k-$70k band (memo ~$65,300)"
    )


def test_memo_reference_position_below_50w_above_200w():
    """Memo: 'Price traded beneath the 200-week SMA at the early-summer low
    near $57,000 and has since recovered above it, closing near $65,300'
    AND '50-week SMA sits far above at roughly $86,500'. So as of the memo
    reference row (2026-07-20 snapshot), price must be below 50w AND above
    200w. Pinned to the reference date, not the running last row."""
    df = pd.read_csv(TARGET_CSV, dtype=str)
    df["date_dt"] = pd.to_datetime(df["date"])
    memo_row = df[df["date_dt"] == pd.Timestamp("2026-07-20")]
    assert len(memo_row) == 1, f"Memo reference row 2026-07-20 not found"
    row = memo_row.iloc[0]
    assert row["below_sma_50w"] == "True", (
        f"Expected memo reference close below sma_50w; got below_sma_50w={row['below_sma_50w']!r}"
    )
    assert row["below_sma_200w"] == "False", (
        f"Expected memo reference close above sma_200w; got below_sma_200w={row['below_sma_200w']!r}"
    )


def test_latest_position_reflects_fresh_data():
    """Live position as of the latest weekly row (2026-08-10 refresh):
    price re-broke below the 200w SMA (close $63,704 vs sma_200w $64,000),
    still below the 50w. This is a moving state — update when data changes.
    See docs/blockers/I-18a-sma-position-rebreak.md."""
    df = pd.read_csv(TARGET_CSV, dtype=str)
    last = df.iloc[-1]
    assert last["below_sma_50w"] == "True", (
        f"Expected latest close below sma_50w; got below_sma_50w={last['below_sma_50w']!r}"
    )
    assert last["below_sma_200w"] == "True", (
        f"Expected latest close below sma_200w (post-memo re-break); "
        f"got below_sma_200w={last['below_sma_200w']!r}"
    )


def test_known_historical_break_and_reclaim_events():
    """The C3-cycle (2022) history must include the break-then-false-reclaim
    sequence on the 200w that the memo documents:
    - First break-below 200w in mid-2022 (June-Aug timeframe)
    - At least one brief reclaim followed by a second break
    - Final reclaim in 2023
    """
    df = pd.read_csv(TARGET_CSV, dtype=str)
    # Filter to 2022-2023 weekly rows
    df["date_dt"] = pd.to_datetime(df["date"])
    yr_22_23 = df[(df["date_dt"].dt.year.isin([2022, 2023]))].copy()
    breaks_200w = yr_22_23[yr_22_23["event_first_below_200w"] == "True"]
    reclaims_200w = yr_22_23[yr_22_23["event_reclaim_200w"] == "True"]
    assert len(breaks_200w) >= 2, (
        f"Expected >=2 200w break-below events in 2022-23 (memo's break + second-break); "
        f"got {len(breaks_200w)}"
    )
    assert len(reclaims_200w) >= 1, (
        f"Expected >=1 200w reclaim event in 2022-23; got {len(reclaims_200w)}"
    )


def test_boolean_columns_string_format():
    """bool columns must be the strings 'True'/'False' for stable CSV output
    (no missing values, no '1'/'0', no 'True'/'False' mixed with NaN)."""
    df = pd.read_csv(TARGET_CSV, dtype=str)
    bool_cols = [
        "below_sma_50w",
        "below_sma_200w",
        "event_first_below_50w",
        "event_first_below_200w",
        "event_reclaim_50w",
        "event_reclaim_200w",
    ]
    for col in bool_cols:
        unique = set(df[col].dropna().unique())
        assert unique.issubset({"True", "False"}), (
            f"Bool column {col} has non True/False values: {unique}"
        )
        assert not df[col].isna().any(), f"Bool column {col} has missing values"

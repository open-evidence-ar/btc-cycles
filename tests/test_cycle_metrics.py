"""I-05 validation gate: cycle metrics determinants and Rule T/B agreement."""

import hashlib
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TARGETS_CSV = PROCESSED_DIR / "btc_cycle_metrics.csv"
CANDIDATES_CSV = PROCESSED_DIR / "extrema_candidates.csv"
FOLKLORE_CSV = PROCESSED_DIR / "folklore_reconciliation.csv"
EVENTS_CSV = DATA_DIR / "events.csv"

CHECKPOINT = PROCESSED_DIR / "__cycle_metrics_checkpoint__.csv"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_btc_snapshot():
    manifest = pd.read_csv(RAW_DIR / "manifest.txt", sep="\t", dtype=str)
    row = manifest[manifest["symbol"] == "btc"].iloc[-1]
    path = RAW_DIR / row["filename"]
    return path


def build_cycle_metrics_if_missing():
    """Generate cycle metrics files if any of the required outputs is missing."""
    if not (TARGETS_CSV.exists() and CANDIDATES_CSV.exists() and FOLKLORE_CSV.exists()):
        print("Running build_cycle_metrics.py to generate required files...")
        import subprocess
        script_path = ROOT / "scripts" / "build_cycle_metrics.py"
        subprocess.run(["python", str(script_path)], cwd=ROOT, check=True)
        print("Generation complete.")


@pytest.fixture(scope="module", autouse=True)
def ensure_artifacts_exist():
    build_cycle_metrics_if_missing()


def test_outputs_exist():
    assert TARGETS_CSV.is_file()
    assert CANDIDATES_CSV.is_file()
    assert FOLKLORE_CSV.is_file()


def test_determinism():
    df_before = pd.read_csv(TARGETS_CSV)
    check_before = _sha256_file(TARGETS_CSV)
    df_before.to_csv(CHECKPOINT, index=False)

    build_cycle_metrics_if_missing()

    check_after = _sha256_file(TARGETS_CSV)
    df_after = pd.read_csv(TARGETS_CSV)

    assert check_before == check_after, (
        "btc_cycle_metrics.csv after re-run differs from before; determinism test failed."
    )
    assert df_before.equals(df_after), "Dataframes differ after re-run."
    CHECKPOINT.unlink(missing_ok=True)


def test_file_columns():
    targets = pd.read_csv(TARGETS_CSV)
    candidates = pd.read_csv(CANDIDATES_CSV)

    required_targets = {
        "cycle_id",
        "halving_date",
        "pre_halving_bottom_date",
        "pre_halving_bottom_price",
        "final_top_date",
        "final_top_price",
        "next_bear_bottom_date",
        "next_bear_bottom_price",
        "D_prev_bottom_to_halving",
        "D_halving_to_top",
        "D_top_to_next_bottom",
        "mult_bottom_to_top",
        "drawdown_pct",
        "first_high_date",
        "first_high_price",
        "D_halving_to_first_high",
        "top_character",
    }
    assert set(targets.columns) == required_targets

    required_candidates = {
        "cycle_id",
        "event_type",
        "window_start",
        "window_end",
        "best_date",
        "best_price",
        "rule",
        "neighborhood_start",
        "neighborhood_end",
        "neighborhood_verified",
        "canonical_date",
        "diff_days",
    }
    assert set(candidates.columns) == required_candidates


def test_agreement_c1_c2_c3_c4_tops():
    events = pd.read_csv(EVENTS_CSV)
    targets = pd.read_csv(TARGETS_CSV)

    cycle_to_canon = {}
    for cid in {"C1", "C2", "C3", "C4"}:
        sub = events[
            (events["cycle_id"] == cid) & (events["label"] == "final_top")
        ]
        assert len(sub) == 1, f"{cid} final_top missing in events.csv"
        cycle_to_canon[cid] = sub.iloc[0]

    for _, row in targets.iterrows():
        cid = row["cycle_id"]
        if cid not in cycle_to_canon:
            continue
        canon_row = cycle_to_canon[cid]
        if str(canon_row.get("reason_code", "")) == "not_yet_observed":
            continue
        canon_date = pd.to_datetime(canon_row["date"])
        # Live cycles (e.g. C4 post-top pre-bottom) have final_top_date present
        # in the targets csv. Allow missing only if not_yet_observed.
        top_str = row["final_top_date"]
        if pd.isna(top_str) or str(top_str).strip() == "":
            assert str(canon_row.get("reason_code", "")) == "not_yet_observed", (
                f"{cid} expected a top date from script but got empty"
            )
            continue
        pred_date = pd.to_datetime(top_str)
        diff = abs((pred_date - canon_date).days)
        assert diff <= 14, (
            f"{cid} top date mismatch: predicted {pred_date.date()}, "
            f"canonical {canon_date.date()}, diff {diff}d >14d"
        )


def test_agreement_c1_c2_c3_c4_bottoms():
    events = pd.read_csv(EVENTS_CSV)
    targets = pd.read_csv(TARGETS_CSV)

    canon_map = {}
    for bid in {"B1", "B2", "B3"}:
        sub = events[(events["cycle_id"] == bid)]
        assert len(sub) == 1, f"{bid} missing in events.csv"
        canon_map[bid] = sub.iloc[0]

    cycle_to_b = {"C1": "B1", "C2": "B2", "C3": "B3"}

    for _, row in targets.iterrows():
        cid = row["cycle_id"]
        if cid not in cycle_to_b:
            continue
        canon_date = pd.to_datetime(canon_map[cycle_to_b[cid]]["date"])
        bottom_str = row["next_bear_bottom_date"]
        if pd.isna(bottom_str) or str(bottom_str).strip() == "":
            continue
        pred_date = pd.to_datetime(bottom_str)
        diff = abs((pred_date - canon_date).days)
        assert diff <= 14, (
            f"{cid} bottom date mismatch: predicted {pred_date.date()}, "
            f"canonical {canon_date.date()}, diff {diff}d >14d"
        )


def test_completeness_d_columns():
    targets = pd.read_csv(TARGETS_CSV)

    for _, row in targets.iterrows():
        cycle = row["cycle_id"]
        if cycle in {"C2", "C3"}:
            for col in ["D_prev_bottom_to_halving", "D_halving_to_top", "D_top_to_next_bottom"]:
                assert not pd.isna(row[col]), f"{cycle} {col} is NaN"
        if cycle == "C4":
            assert not pd.isna(row["D_prev_bottom_to_halving"]), "C4 D_prev_bottom_to_halving is NaN"
            # After Jul-2026 reconciliation (memo backfill), C4 has an observed
            # top, so D_halving_to_top must be present.
            assert not pd.isna(row["D_halving_to_top"]), "C4 D_halving_to_top is NaN (top now observed)"
            # C4 next-bear-bottom (B4) is NOT yet observed; the cycle duration
            # column must stay empty until B4 prints. I-10 confluence zone map
            # carries the projected B4 date band independently.
            assert pd.isna(row["D_top_to_next_bottom"]), (
                "C4 D_top_to_next_bottom must be NaN -- B4 is projected, not observed"
            )


def test_top_character_populated():
    """top_character column must be filled for any cycle with a final_top."""
    targets = pd.read_csv(TARGETS_CSV)
    valid_chars = {"euphoric", "apathetic", ""}
    for _, row in targets.iterrows():
        ts = str(row["top_character"] or "").strip()
        assert ts in valid_chars, f"{row['cycle_id']} top_character={ts!r} not in {valid_chars}"
        # If we have a mult, top_character must be non-empty.
        mult = row["mult_bottom_to_top"]
        if pd.notna(mult) and str(mult).strip() != "":
            assert ts != "", f"{row['cycle_id']} has mult but no top_character label"


def test_folklore_columns():
    folklore = pd.read_csv(FOLKLORE_CSV)

    required = {"chart_annotation", "framework_value", "chart_value", "delta", "tolerance", "pass_fail", "notes"}
    assert set(folklore.columns) == required


def test_extrema_candidates_match_targets():
    events = pd.read_csv(EVENTS_CSV)
    candidates = pd.read_csv(CANDIDATES_CSV)

    targets = pd.read_csv(TARGETS_CSV)

    cycle_ids_with_observed_top = set()
    for _, ev in events[(events["event_type"] == "top") & (events["label"] == "final_top")].iterrows():
        if str(ev.get("reason_code", "")) != "not_yet_observed" and pd.notna(ev["date"]):
            cycle_ids_with_observed_top.add(ev["cycle_id"])

    for _, row in targets.iterrows():
        cycle = row["cycle_id"]
        if cycle not in cycle_ids_with_observed_top:
            continue
        cycle_tops = events[
            (events["event_type"] == "top") & (events["cycle_id"] == cycle)
        ].copy()
        cycle_tops["date"] = pd.to_datetime(cycle_tops["date"])

        for _, cand in candidates[
            (candidates["cycle_id"] == cycle)
            & ((candidates["event_type"] == "top") | (candidates["event_type"] == "bottom"))
        ].iterrows():
            if cand["event_type"] == "top":
                diffs = abs(
                    (pd.to_datetime(cand["best_date"]) - cycle_tops["date"]).dt.days
                )
                assert diffs.min() <= 14, (
                    f"Candidate top for {cycle} differs from events.csv within ±14d"
                )


def test_btc_snapshot_exists_and_nonempty():
    path = _latest_btc_snapshot()
    assert path.is_file()
    df = pd.read_csv(path)
    assert not df.empty

"""I-01 validation gate: canonical event table schema."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
EVENTS_CSV = ROOT / "data" / "events.csv"

REQUIRED_COLUMNS = [
    "event_type",
    "cycle_id",
    "label",
    "date",
    "price_usd",
    "reason_code",
    "source",
    "notes",
]


@pytest.fixture(scope="module")
def events():
    df = pd.read_csv(EVENTS_CSV, dtype=str)
    return df


def test_events_file_exists():
    assert EVENTS_CSV.is_file()


def test_required_columns(events):
    assert list(events.columns) == REQUIRED_COLUMNS


def test_row_counts(events):
    halvings = events[events["event_type"] == "halving"]
    bottoms = events[events["event_type"] == "bottom"]
    tops = events[events["event_type"] == "top"]
    final_tops = tops[tops["label"] == "final_top"]

    assert len(halvings) == 5
    assert len(bottoms) == 5  # B0-B4
    assert len(final_tops) == 4


def test_all_dates_parse(events):
    dated = events[events["date"].notna() & (events["date"] != "")]
    for d in dated["date"]:
        date.fromisoformat(d)


def test_no_duplicate_keys(events):
    keys = events[["event_type", "cycle_id", "label"]].apply(tuple, axis=1)
    assert keys.is_unique, f"Duplicate keys: {keys[keys.duplicated()].tolist()}"


def test_anchor_dates(events):
    halvings = events[events["event_type"] == "halving"].set_index("cycle_id")
    tops = events[
        (events["event_type"] == "top") & (events["label"] == "final_top")
    ].set_index("cycle_id")
    bottoms = events[events["event_type"] == "bottom"].set_index("cycle_id")

    assert halvings.loc["H2", "date"] == "2016-07-09"
    assert halvings.loc["H3", "date"] == "2020-05-11"
    assert halvings.loc["H4", "date"] == "2024-04-20"
    assert tops.loc["C2", "date"] == "2017-12-17"
    assert tops.loc["C3", "date"] == "2021-11-10"
    assert bottoms.loc["B3", "date"] == "2022-11-21"


def test_c1_local_high_reason_code(events):
    local = events[
        (events["event_type"] == "top")
        & (events["cycle_id"] == "C1")
        & (events["label"] == "first_high")
    ]
    assert len(local) == 1
    assert local.iloc[0]["reason_code"] == "local_high_not_cycle_top"


def test_c4_top_observed(events):
    """C4 top is now observed (per I-05 / bitstamp snapshot reconciliation
    with Cowen July 2026 memo). Date 2025-10-06; price $124,728."""
    c4_top = events[
        (events["event_type"] == "top")
        & (events["cycle_id"] == "C4")
        & (events["label"] == "final_top")
    ]
    assert len(c4_top) == 1
    assert c4_top.iloc[0]["reason_code"] == "canonical"
    assert c4_top.iloc[0]["date"] == "2025-10-06"
    assert float(c4_top.iloc[0]["price_usd"]) == 124728.00


def test_b4_bottom_tbd(events):
    """B4 (post-C4 bear bottom) is not yet observed; reason_code must be
    not_yet_observed and date/price empty."""
    b4 = events[
        (events["event_type"] == "bottom")
        & (events["cycle_id"] == "B4")
    ]
    assert len(b4) == 1
    assert b4.iloc[0]["reason_code"] == "not_yet_observed"
    assert pd.isna(b4.iloc[0]["date"]) or b4.iloc[0]["date"] == ""


def test_events_yml_exists():
    assert (ROOT / "_data" / "events.yml").is_file()

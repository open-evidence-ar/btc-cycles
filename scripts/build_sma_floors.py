"""I-18a: Build BTC 50-week and 200-week SMA floors.

Weekly Simple Moving Averages of BTC close, computed from the same raw BTC
Bitstamp snapshot used by I-05 (deterministic re-run). These SMAs are
structural valuation floors -- per the Cowen "Bitcoin Cycle Memo" (Jul 2026):
the 200-week SMA marks a deep-value region whose weekly-close loss has
historically clustered in late-stage bear markets ("date with destiny"), and
the 50-week SMA's sustained reclaim (taken as two consecutive weekly closes
above) is a higher-confidence transition signal than an initial 200-week
reclaim.

Outputs (deterministic, regenerated on each run):
  - data/processed/btc_sma_floors.csv
      columns: date (ISO Monday-of-week), close (last daily close of that week),
               sma_50w, sma_200w, below_sma_50w (bool), below_sma_200w (bool),
               event_first_below_50w, event_first_below_200w, event_reclaim_50w,
               event_reclaim_200w (bool flags indicating transition that week)

The SMA series starts where it is mathematically defined (week 50 for sma_50w,
week 200 for sma_200w). Transition events are recorded only on the weekly
row where the price first crosses below or reclaims (2-close rule) each SMA.

Reference: DESIGN.md section 11 (Open Questions) -- "SMAs and moving-average
valuation floors" listed as optional pattern-recognition extension.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TARGET_CSV = PROCESSED_DIR / "btc_sma_floors.csv"


def load_btc_latest() -> tuple[pd.DataFrame, Path]:
    snapshots = sorted(RAW_DIR.glob("btc_bitstamp_*.csv"))
    if not snapshots:
        snapshots = sorted(RAW_DIR.glob("btc_*.csv"))
    if not snapshots:
        raise FileNotFoundError("No BTC snapshot found in data/raw/")
    path = snapshots[-1]
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df, path


def to_weekly_eff(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily closes to weekly closes (last close of ISO week)."""
    daily = daily.copy()
    daily["week_start"] = daily["date"] - pd.to_timedelta(
        daily["date"].dt.weekday, unit="D"
    )
    weekly = (
        daily.groupby("week_start", as_index=False)
        .agg(close=("close", "last"), date_max=("date", "max"))
        .rename(columns={"week_start": "date"})
        .sort_values("date")
        .reset_index(drop=True)
    )
    return weekly


def compute_smas(weekly: pd.DataFrame) -> pd.DataFrame:
    weekly = weekly.copy()
    weekly["sma_50w"] = weekly["close"].rolling(window=50, min_periods=50).mean()
    weekly["sma_200w"] = weekly["close"].rolling(window=200, min_periods=200).mean()
    weekly["below_sma_50w"] = weekly["close"] < weekly["sma_50w"]
    weekly["below_sma_200w"] = weekly["close"] < weekly["sma_200w"]
    return weekly


def mark_transitions(weekly: pd.DataFrame) -> pd.DataFrame:
    """Mark break-below and reclaim events using the 2-consecutive-close rule
    (symmetric to the memo's "two consecutive weekly closes above" rule for
    50w reclaim). A break-below is recorded on the second consecutive close
    below the SMA. A reclaim is recorded on the second consecutive close above.
    """
    weekly = weekly.copy()
    b50 = weekly["below_sma_50w"].fillna(False)
    b200 = weekly["below_sma_200w"].fillna(False)

    def _transitions(below: pd.Series) -> tuple[pd.Series, pd.Series]:
        prev = below.shift(1, fill_value=False)
        nxt = below.shift(-1, fill_value=False)
        # break-below: prev_week was False, this & next are both True.
        break_evt = (~prev) & below & nxt
        # reclaim: prev_week was True, this & next are both False.
        reclaim_evt = prev & ~below & ~nxt
        return break_evt, reclaim_evt

    weekly["event_first_below_50w"], weekly["event_reclaim_50w"] = _transitions(b50)
    weekly["event_first_below_200w"], weekly["event_reclaim_200w"] = _transitions(b200)
    # Drop "event_first_above_*" helper columns (not in output schema).
    return weekly


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    daily, path = load_btc_latest()
    weekly = to_weekly_eff(daily)
    sma = compute_smas(weekly)
    sma = mark_transitions(sma)

    # Drop helper columns kept for clarity, output the canonical schema.
    out = sma[
        [
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
        ]
    ].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    for col in [
        "below_sma_50w",
        "below_sma_200w",
        "event_first_below_50w",
        "event_first_below_200w",
        "event_reclaim_50w",
        "event_reclaim_200w",
    ]:
        out[col] = out[col].fillna(False).astype(bool).map({True: "True", False: "False"})
    # SMA NaNs (early weeks) become ''.
    for col in ["sma_50w", "sma_200w"]:
        out[col] = out[col].map(lambda x: "" if pd.isna(x) else round(float(x), 2))
    out.to_csv(TARGET_CSV, index=False)
    print(f"Wrote {TARGET_CSV} ({len(out)} weekly rows; source={path.name})")
    print("I-18a done.")


if __name__ == "__main__":
    main()

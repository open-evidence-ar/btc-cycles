"""I-18a-alt: Build 50-week and 200-week SMA floors per altcoin.

Weekly Simple Moving Averages of each altcoin's close, computed from the
same raw yahoo snapshot used by I-17. Mirrors build_sma_floors.py (BTC)
for the crypto altcoins that carry a next-cycle zone chart (eth, xrp, sol,
mstr, wgmi).

Outputs (deterministic, regenerated on each run):
  - data/processed/alt_sma_floors.csv
      columns: asset, date (ISO Monday-of-week), close (last daily close
               of that week), sma_50w, sma_200w, below_sma_50w, below_sma_200w,
               event_first_below_50w, event_first_below_200w, event_reclaim_50w,
               event_reclaim_200w (bool flags, same schema as btc_sma_floors).

The SMA series starts where it is mathematically defined (week 50 for
sma_50w, week 200 for sma_200w). Transition events are recorded only on
the weekly row where the price first crosses below or reclaims (2-close
rule) each SMA.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TARGET_CSV = PROCESSED_DIR / "alt_sma_floors.csv"

ALT_ASSETS = ["eth", "xrp", "sol", "mstr", "wgmi"]


def _load_alt_latest(asset: str) -> tuple[pd.DataFrame, Path]:
    cands = sorted(RAW_DIR.glob(f"{asset}_yahoo_*.csv"))
    if not cands:
        raise FileNotFoundError(f"No raw snapshot for {asset}")
    path = cands[-1]
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df, path


def to_weekly_eff(daily: pd.DataFrame) -> pd.DataFrame:
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
    weekly = weekly.copy()
    b50 = weekly["below_sma_50w"].fillna(False)
    b200 = weekly["below_sma_200w"].fillna(False)

    def _transitions(below: pd.Series) -> tuple[pd.Series, pd.Series]:
        prev = below.shift(1, fill_value=False)
        nxt = below.shift(-1, fill_value=False)
        break_evt = (~prev) & below & nxt
        reclaim_evt = prev & ~below & ~nxt
        return break_evt, reclaim_evt

    weekly["event_first_below_50w"], weekly["event_reclaim_50w"] = _transitions(b50)
    weekly["event_first_below_200w"], weekly["event_reclaim_200w"] = _transitions(b200)
    return weekly


def build_one(asset: str) -> pd.DataFrame:
    daily, path = _load_alt_latest(asset)
    weekly = to_weekly_eff(daily)
    sma = compute_smas(weekly)
    sma = mark_transitions(sma)
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
    out.insert(0, "asset", asset)
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
    for col in ["sma_50w", "sma_200w"]:
        out[col] = out[col].map(lambda x: "" if pd.isna(x) else round(float(x), 2))
    return out


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for asset in ALT_ASSETS:
        frames.append(build_one(asset))
    alt_sma = pd.concat(frames, ignore_index=True)
    alt_sma.to_csv(TARGET_CSV, index=False)
    print(f"Wrote {TARGET_CSV} ({len(alt_sma)} weekly rows, {len(frames)} assets)")
    print("I-18a-alt done.")


if __name__ == "__main__":
    main()
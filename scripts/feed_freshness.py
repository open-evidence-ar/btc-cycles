#!/usr/bin/env python3
"""Feed freshness audit for the `data/raw` snapshot registry.

There are two *different* kinds of staleness, and conflating them is what
allowed a 62-day data freeze to look like a healthy fetch for weeks:

1. **Snapshot-internal lag** = ``retrieved_at - date_range_last``
   "When the fetch ran, did it actually request recent data?"
   This is the failure that froze the macro and Treasury-yield panel: both
   ``fetch_macro.py`` and ``fetch_yields.py`` hard-coded ``PERIOD2`` to
   2026-08-15, so each run stamped a *today* retrieval date onto a snapshot
   still carrying 2026-08-14 data. The registry looked fresh; the data was not.
   This measure is self-contained, wall-clock independent, and therefore safe
   to assert in pytest -- CI never fetches, but a correctly-constructed
   snapshot always satisfies it.

2. **Wall-clock age** = ``today - date_range_last``
   "Has anyone run a fetch lately at all?"
   This is an *operational* question, not a correctness one. The `tests` and
   `regenerate-artifacts` CI jobs rebuild everything from the committed
   snapshots and never invoke the fetchers, so a today-anchored pytest gate
   would go red on a schedule that no CI job could ever fix. It is therefore
   reported as a warning (and runs in `refresh_all.py`'s FRESHNESS stage, where
   a fetch has just happened), never as an assertion.

Usage:
    python scripts/feed_freshness.py              # report; exit 1 on internal-lag violations
    python scripts/feed_freshness.py --quiet      # violations only
    python scripts/feed_freshness.py --no-warn-aging
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "raw" / "manifest.txt"

#: Maximum tolerated gap between when a snapshot was retrieved and the last
#: observation it contains. Covers weekends and exchange holidays (a Friday
#: close retrieved on the following Monday is a 3-day lag).
MAX_INTERNAL_LAG_DAYS = 7

#: Wall-clock age at which the aging warning is printed.
AGING_WARN_DAYS = 7

#: Symbols deliberately excluded from every freshness check.
#: `mara` and `riot` are dead SSR proxy tickers -- their upstream stopped
#: publishing in 2026-07 and there is no working replacement. They are padding
#: in the alt panel, never a load-bearing series. Exempt rather than silently
#: absent so the exemption is a decision on the record, not an oversight.
EXEMPT_SYMBOLS = frozenset({"mara", "riot"})


def _parse_date(value: str) -> date:
    """Parse a manifest date or timestamp into a `date` (tz-naive).

    Accepts `YYYY-MM-DD` and the ISO-8601 timestamps the fetchers write,
    including the trailing `Z` and fractional-second variants.
    """
    text = (value or "").strip()
    if not text:
        raise ValueError("empty date value")
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date()


def load_rows(manifest: Path = MANIFEST) -> list[dict]:
    """Read the snapshot registry into a list of row dicts."""
    if not Path(manifest).is_file():
        raise FileNotFoundError(f"manifest not found: {manifest}")
    with open(manifest, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def internal_lag_days(row: dict) -> int:
    """Days between the snapshot's retrieval date and its last observation.

    Zero means the fetch captured data through its own retrieval date. A large
    value means the fetcher never asked the source for recent bars.
    """
    retrieved = _parse_date(row["retrieved_at"])
    last_data = _parse_date(row["date_range_last"])
    return (retrieved - last_data).days


def wallclock_age_days(row: dict, today: date | None = None) -> int:
    """Days between today's date and the snapshot's last observation."""
    today = today or datetime.now(timezone.utc).date()
    return (today - _parse_date(row["date_range_last"])).days


def evaluate(rows: list[dict], today: date | None = None) -> dict:
    """Partition manifest rows into violations / aging / exempt / fresh.

    Returns a dict with keys:
      ``violations`` -- rows whose internal lag exceeds ``MAX_INTERNAL_LAG_DAYS``
                         (a real bug: the fetcher's window is lying)
      ``aging``      -- rows whose wall-clock age exceeds ``AGING_WARN_DAYS``
                         (nobody has fetched lately -- advisory only)
      ``exempt``     -- rows for ``EXEMPT_SYMBOLS``
      ``fresh``      -- everything else
    """
    violations: list[dict] = []
    aging: list[dict] = []
    exempt: list[dict] = []
    fresh: list[dict] = []

    for row in rows:
        symbol = row.get("symbol", "?")
        entry = {
            "symbol": symbol,
            "source": row.get("source", "?"),
            "retrieved_at": row.get("retrieved_at", "?"),
            "data_last": row.get("date_range_last", "?"),
            "internal_lag": internal_lag_days(row),
            "age_days": wallclock_age_days(row, today),
        }
        if symbol in EXEMPT_SYMBOLS:
            exempt.append(entry)
        elif entry["internal_lag"] > MAX_INTERNAL_LAG_DAYS:
            violations.append(entry)
        elif entry["age_days"] > AGING_WARN_DAYS:
            aging.append(entry)
        else:
            fresh.append(entry)

    return {
        "violations": violations,
        "aging": aging,
        "exempt": exempt,
        "fresh": fresh,
    }


def format_report(report: dict, today: date | None = None) -> str:
    """Render an :func:`evaluate` result as a human-readable block."""
    today = today or datetime.now(timezone.utc).date()
    lines: list[str] = []
    counts = {k: len(report[k]) for k in ("fresh", "aging", "violations", "exempt")}
    lines.append(
        f"Feed freshness @ {today.isoformat()}  "
        f"(fresh={counts['fresh']} aging={counts['aging']} "
        f"VIOLATIONS={counts['violations']} exempt={counts['exempt']})"
    )

    if report["violations"]:
        lines.append("")
        lines.append(
            f"  !! {len(report['violations'])} feed(s) retrieved data older than "
            f"{MAX_INTERNAL_LAG_DAYS}d -- the fetcher window is lying:"
        )
        for e in report["violations"]:
            lines.append(
                f"     {e['symbol']:<6s} {e['source']:<8s} retrieved={e['retrieved_at'][:19]} "
                f"data_last={e['data_last']} lag={e['internal_lag']}d"
            )
        lines.append(
            "     (a hard-coded PERIOD2 epoch is the usual cause -- see "
            "scripts/feed_freshness.py docstring)"
        )

    if report["aging"]:
        lines.append("")
        lines.append(
            f"  ! {len(report['aging'])} feed(s) have not been refreshed in over "
            f"{AGING_WARN_DAYS}d. Advisory only -- CI rebuilds from committed"
        )
        lines.append("    snapshots and never fetches, so this is an ops reminder, not a gate:")
        for e in report["aging"]:
            lines.append(
                f"     {e['symbol']:<6s} {e['source']:<8s} data_last={e['data_last']} "
                f"age={e['age_days']}d"
            )

    if report["exempt"]:
        names = ", ".join(sorted(e["symbol"] for e in report["exempt"]))
        lines.append("")
        lines.append(f"  - exempt from freshness checks: {names}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit data/raw snapshot freshness")
    parser.add_argument("--manifest", default=str(MANIFEST), help="path to manifest.txt")
    parser.add_argument("--quiet", action="store_true", help="only print violations")
    parser.add_argument("--no-warn-aging", action="store_true",
                        help="suppress the wall-clock aging advisory")
    args = parser.parse_args()

    rows = load_rows(Path(args.manifest))
    report = evaluate(rows)

    if args.quiet:
        if report["violations"]:
            for e in report["violations"]:
                print(f"{e['symbol']}: internal lag {e['internal_lag']}d "
                      f"(retrieved {e['retrieved_at'][:19]}, data_last {e['data_last']})")
    else:
        print(format_report(report))
        if args.no_warn_aging:
            report["aging"] = []

    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

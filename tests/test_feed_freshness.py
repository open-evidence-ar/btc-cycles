"""Feed freshness gates.

Two independent properties are asserted here:

* **Snapshot-internal lag** (`retrieved_at - date_range_last`) must stay within
  `MAX_INTERNAL_LAG_DAYS` for every non-exempt feed. This is the regression that
  let the macro and Treasury-yield panel sit on 2026-08-14 data for 11
  consecutive fetches: both fetchers hard-coded `PERIOD2` to 2026-08-15, so a
  snapshot re-stamped with today's retrieval date still carried two-month-old
  observations and every prior freshness check passed.

* **Coverage.** The check is not limited to the feeds that were broken -- it
  spans crypto, the alt/corporate panel, macro, and the yield panel, so
  re-introducing a hard-coded epoch in *any* fetcher is caught.

Wall-clock age is deliberately *not* asserted (see
`scripts/feed_freshness.py`): CI rebuilds artefacts from committed snapshots and
never runs the fetchers, so a today-anchored assertion would fail on a schedule
no CI job could fix. It is exercised only as a pure function.
"""

from __future__ import annotations

from datetime import date, timedelta

from scripts.feed_freshness import (
    AGING_WARN_DAYS,
    EXEMPT_SYMBOLS,
    MAX_INTERNAL_LAG_DAYS,
    evaluate,
    format_report,
    internal_lag_days,
    load_rows,
    wallclock_age_days,
)

TODAY = date(2026, 10, 15)

# Feeds that must be demonstrably current, grouped by panel.
CRYPTO = ["btc", "eth", "xrp", "sol"]
CORPORATE = ["mstr", "wgmi"]
MACRO = ["spx", "ndx", "dxy", "tlt", "gold"]
YIELDS = ["y2", "y10", "y5", "y13w", "y30"]


def _row(symbol: str, retrieved: str, data_last: str, source: str = "yahoo") -> dict:
    return {
        "symbol": symbol,
        "source": source,
        "retrieved_at": retrieved,
        "date_range_last": data_last,
    }


def _real_rows() -> list[dict]:
    return load_rows()


def _symbols(rows: list[dict]) -> set[str]:
    return {r["symbol"] for r in rows}


class TestInternalLagArithmetic:
    """The lag measure itself -- pure, no I/O."""

    def test_same_day_is_zero(self):
        row = _row("spx", "2026-10-15T19:59:08Z", "2026-10-15")
        assert internal_lag_days(row) == 0

    def test_fractional_and_z_timestamps_parse(self):
        row = _row("spx", "2026-10-15T19:59:55.048878Z", "2026-08-14")
        assert internal_lag_days(row) == 62

    def test_weekend_hop_is_three_days(self):
        # Friday close retrieved on the following Monday.
        row = _row("y10", "2026-10-12T10:00:00Z", "2026-10-09")
        assert internal_lag_days(row) == 3

    def test_wallclock_age_uses_supplied_today(self):
        row = _row("btc", "2026-10-15T10:00:00Z", "2026-10-15")
        assert wallclock_age_days(row, TODAY) == 0
        assert wallclock_age_days(row, TODAY + timedelta(days=30)) == 30


class TestEvaluateClassification:
    """Routing into fresh / aging / violations / exempt."""

    def test_frozen_window_is_a_violation(self):
        rows = [_row("spx", "2026-10-15T19:59:00Z", "2026-08-14")]
        report = evaluate(rows, today=TODAY)
        assert len(report["violations"]) == 1
        v = report["violations"][0]
        assert v["symbol"] == "spx"
        assert v["internal_lag"] == 62

    def test_lag_exactly_at_limit_is_allowed(self):
        at_limit = _row("spx", "2026-10-15T19:59:00Z",
                        (date(2026, 10, 15) - timedelta(days=MAX_INTERNAL_LAG_DAYS)).isoformat())
        over = _row("ndx", "2026-10-15T19:59:00Z",
                    (date(2026, 10, 15) - timedelta(days=MAX_INTERNAL_LAG_DAYS + 1)).isoformat())
        report = evaluate([at_limit, over], today=TODAY)
        assert [v["symbol"] for v in report["violations"]] == ["ndx"]
        assert "spx" in {f["symbol"] for f in report["fresh"]}

    def test_exempt_symbols_are_never_violations(self):
        # Frozen since 2026-07-29; would violate by ~78 days if not exempt.
        rows = [_row(sym, "2026-07-30T05:21:56Z", "2026-07-29") for sym in sorted(EXEMPT_SYMBOLS)]
        report = evaluate(rows, today=TODAY)
        assert report["violations"] == []
        assert {e["symbol"] for e in report["exempt"]} == set(EXEMPT_SYMBOLS)

    def test_internally_consistent_but_unfetched_is_aging_not_violating(self):
        # The distinction that keeps CI honest: a snapshot that was internally
        # fine but never refreshed is advisory, never a gate failure.
        old = (TODAY - timedelta(days=AGING_WARN_DAYS + 3)).isoformat()
        rows = [_row("btc", old, old)]
        report = evaluate(rows, today=TODAY)
        assert report["violations"] == []
        assert [a["symbol"] for a in report["aging"]] == ["btc"]


class TestRealManifestIsFresh:
    """The committed registry must satisfy the internal-lag gate."""

    def test_manifest_loads(self):
        rows = _real_rows()
        assert rows, "data/raw/manifest.txt produced no rows"
        assert {"symbol", "retrieved_at", "date_range_last"} <= set(rows[0])

    def test_no_feed_exceeds_internal_lag(self):
        report = evaluate(_real_rows(), today=TODAY)
        assert report["violations"] == [], (
            "Feeds retrieved far newer than the data they contain -- a fetcher "
            "is probably capped by a hard-coded epoch:\n"
            + format_report(report, today=TODAY)
        )

    def test_crypto_panel_present_and_fresh(self):
        rows = _real_rows()
        assert set(CRYPTO) <= _symbols(rows)
        self._assert_fresh(rows, CRYPTO)

    def test_corporate_panel_present_and_fresh(self):
        rows = _real_rows()
        assert set(CORPORATE) <= _symbols(rows)
        self._assert_fresh(rows, CORPORATE)

    def test_macro_panel_present_and_fresh(self):
        rows = _real_rows()
        assert set(MACRO) <= _symbols(rows)
        self._assert_fresh(rows, MACRO)

    def test_yield_panel_present_and_fresh(self):
        rows = _real_rows()
        assert set(YIELDS) <= _symbols(rows)
        self._assert_fresh(rows, YIELDS)

    def _assert_fresh(self, rows: list[dict], symbols: list[str]) -> None:
        worst = []
        for row in rows:
            if row["symbol"] in symbols:
                worst.append((row["symbol"], internal_lag_days(row), row["date_range_last"]))
        assert worst, f"none of {symbols} found in manifest"
        offenders = [w for w in worst if w[1] > MAX_INTERNAL_LAG_DAYS]
        assert not offenders, (
            f"{symbols} exceed the {MAX_INTERNAL_LAG_DAYS}d internal-lag budget: {offenders}"
        )

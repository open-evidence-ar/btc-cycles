# I-18a — memo cross-check test drifted after 2026-08-17 refresh

**Increment:** I-18a (SMA valuation floors, decision overlay)

**Input snapshot:** `data/raw/*_2026-08-17.csv` (fresh fetch via
`scripts/refresh_all.py`); previous latest weekly row was 2026-08-10.

**Expected vs actual:** `tests/test_sma_floors.py::test_last_row_matches_memo_jul_2026_reference`
failed:

- Expected (band, from Cowen July 2026 memo): `sma_50w` in $82k-$90k.
- Actual on the new latest row (2026-08-17): `sma_50w` = $81,502 (BTC's
  recent decline dragged the 50-week SMA below the memo band's floor).
  `sma_200w` = $64,213, close = $62,982 (still in band).

**Hypothesis:** The test read `df.iloc[-1]` (the running latest row) while
asserting memo-pinned bands. That coupling is only valid while the latest
snapshot row *is* the 2026-07-20 memo reference; as data advances, the
latest row legitimately moves outside the memo-era bands. The data change is
correct — the assertion was stale.

**Action:** Pinned the memo cross-check to the 2026-07-20 snapshot row (same
pattern as its sibling `test_memo_reference_position_below_50w_above_200w`).
Values at that row: `sma_50w` $85,426, `sma_200w` $63,329, close $65,339 — all
in band. Live position is covered separately by
`test_latest_position_reflects_fresh_data` (still below both SMAs; that
test's docstring should be updated on future refreshes as it is a moving state).

Also re-stored `tests/chart_snapshots.json` after the chart rebuild (C1-C9,
C-SMA PNG hashes changed with fresh data).
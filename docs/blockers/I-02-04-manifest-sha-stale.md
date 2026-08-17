# Blocker: manifest.txt sha256 stale for 2026-08-13 snapshots

**ID:** I-02 / I-03 / I-04 (provenance gates)

**Status:** Resolved — manifest rows re-stored from committed files.

## Input snapshot

- Commit `f34814f` ("chore(data): refresh snapshots through 2026-08-13, rebuild
  derived artifacts and re-store chart/test snapshots").
- All 11 `data/raw/*_2026-08-13.csv` files + their `data/raw/manifest.txt`
  rows.

## Expected vs actual

- Expected: `sha256` in `manifest.txt` equals the SHA-256 of the referenced
  snapshot file (`tests/test_provenance.py::test_manifest_sha_matches_file`,
  `tests/test_alts_provenance.py::test_manifest_sha_matches_file`,
  `tests/test_macro_provenance.py::test_sha_matches`).
- Actual: all 11 `2026-08-13` rows carried an sha256 that does not match the
  committed file. Verified with `git show HEAD:data/raw/<file>` — every CSV is
  byte-identical to HEAD (79/79 raw CSVs verified), so the manifest rows, not
  the data files, were stale. `row_count` / `date_range_first` /
  `date_range_last` in the same rows were already correct.

## Hypothesis

The manifest was written from a different (mid-fetch or pre-roll) copy of the
snapshot files during the 2026-08-13 refresh — e.g. the digest was computed
while the final row of the day was still being appended, or the fetch ran twice
and only the second fetch's files were committed.

## Action

- Re-stored the 11 `sha256` values in `data/raw/manifest.txt` from the
  committed files on disk (line endings and all other columns preserved).
- No `data/raw/*.csv` file was edited (immutability rule respected; verified
  79/79 CSVs byte-identical to HEAD).
- Re-ran gates: full suite `pytest -q tests/` = 183 passed.
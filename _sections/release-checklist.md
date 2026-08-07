---
layout: default
title: D. Release Checklist
permalink: /release-checklist/
weight: 70
---
This page mirrors the 16-item manual release checklist defined in
[`DESIGN.md` §10.2](https://github.com/{{ site.github.owner_name }}/{{ site.github.repository_name }}/blob/main/DESIGN.md#102-i-16-manual-release-checklist).
**9 of the 16 items are enforced automatically** by
`tests/test_release_checklist.py`; the remaining 7 are inherently
human-in-the-loop and are re-verified before each public release.

The automated gate runs on every push to `main` as part of I-15's CI
pipeline; the manual items are re-reviewed only at release cuts.

## Automated items (enforced by `tests/test_release_checklist.py`)

| # | Item | Status |
|---|------|--------|
| 2 | Every section reachable from sidebar TOC | `test_sidebar_links_to_all_sections` |
| 4 | Provenance footer present on every section | `test_provenance_footer_on_sections` (delegates to I-14) |
| 5 | `data/events.csv` SHA quoted in methodology | `test_events_sha_in_methodology` |
| 6 | manifest lists 8 panel series with non-empty SHA256 | `test_manifest_lists_eight_series` |
| 7 | Backtest-by-cycle table visible in validation section | `test_backtest_table_in_validation` |
| 8 | Forward ranges + LOOCO table visible in predictive ranges | `test_forward_ranges_table_in_predictive` |
| 9 | Sections free of work-in-progress markers | `test_no_todo_fixme_in_sections` |
| 12 | LICENSE file present (CC-BY-4.0 + MIT) | `test_license_present` |
| 14 | `AGENTS.md` documents increment workflow | `test_agents_md_present` |

## Manual items (reviewed at release cut)

1. Site loads at `https://<user>.github.io/trading/` with HTTP 200.
3. All 7 charts render interactively in a desktop browser and on a
   375px-wide mobile viewport.
10. Integrity hash `integrity.txt` matches current `_site/index.html`
    SHA-256 (validated by the CI `jekyll-build` job's `sha256sum` step).
11. GitHub-wide: repo description set, topics include `bitcoin`, `cycles`,
    `halving`, `macro`, `white-paper`.
13. Sample of 5 external hyperlinks tested live (no 404s).
15. `README.md` has quickstart for `pytest`, `jekyll`, `bundle`.
16. Author / maintainer footer present with contact and disclaimer (rendered
    via the `provenance-footer.html` include — see footer below).

## Notes on license scope

- White-paper content (`_sections/*.md`, `abstract.md`, `DESIGN.md` text):
  CC-BY-4.0.
- Software code (`scripts/`, `tests/`, `.github/workflows/`): MIT.
- Raw data snapshots under `data/raw/`: re-distributed under the terms
  of the original upstream sources (Bitstamp, CryptoDataDownload, Yahoo
  Finance); see `LICENSE` for full attribution.

---
*Gate: `pytest tests/test_release_checklist.py` · Manifest: `data/raw/manifest.txt`*

# I-00 — Repo + Pages Skeleton (done)

**Increment:** I-00
**Status:** done
**Gate:** `pytest tests/test_repo_skeleton.py` → 4/4 passed
**Built on:** 2026-07-19
**Session commit:** pending (treat this file as the PR description)

## What landed

- Jekyll 4.3 site with `Gemfile`, `Gemfile.lock`, `_config.yml` copied from the
  `state-vs-family-evidence` template (per the I-00 decision).
- Single custom layout `_layouts/default.html` (header + nav + main + provenance
  footer) + minimal `_includes/provenance-footer.html` + `_assets/css/style.css`.
- Pages content: `index.md`, `abstract.md`, `status.md`, and forward-reference
  stubs in `_sections/` (methodology, cycle-anatomy, cross-asset,
  predictive-ranges, validation). Each stub points to the increment that will
  populate it.
- `.github/workflows/deploy.yml` — Pages build + deploy (with optional SHA-256
  integrity footer; GPG signing deferred).
- `.gitignore` covering `_site/`, `data/raw/`, `data/processed/`, Python caches,
  IDE files, env files, .png reference-chart.

## Gate evidence

```
$ python -m pytest -q tests/test_repo_skeleton.py
....                                                                     [100%]
4 passed in 1.28s

$ bundle exec jekyll build
Configuration file: D:/trading/_config.yml
            Source: D:/trading
       Destination: D:/trading/_site
...
      Generating...
                    done in 0.516 seconds.
EXIT 0

$ ls _site
abstract/index.html  assets/css/style.css  cross-asset/index.html
cycle-anatomy/index.html  index.html  methodology/index.html
predictive-ranges/index.html  status/index.html  validation/index.html
```

No stray files in `_site/`; `*.py` files excluded via `_config.yml::exclude`.

## Adjacent state (preexisting, not modified by I-00)

The following directories were already present in the working tree from a prior
session and are NOT claimed by this increment:

- `data/events.csv` — I-01 artifact; passes its own gate.
- `_data/events.yml` — I-01 artifact (mirror); passes its own gate.
- `tests/test_repo_skeleton.py`, `test_events_schema.py`,
  `test_provenance.py` — gate tests, written by prior session.
- `check_coingecko.py`, `fetch_btc_full.py`, `temp_fetch_btc.py`,
  `scripts/fetch_data.py`, `scripts/_test_bitstamp.py`,
  `tests/__pycache__/`, `notebooks/`, `sections/` (lowercase, not the
  collection dir), `requirements.txt` — workspace clutter / scratch.

These files will be brought under `.gitignore` and removed in a follow-up
cleanup commit, or kept as user-authored scratch. None of them are required
for the I-00 gate.

## Adjacent increments already passing (found during this session)

- **I-01** `tests/test_events_schema.py` → 9/9 passed. The canonical event
  table is already on disk. Status in `AGENTS.md` was updated to **done**.

## Decisions recorded by this session

- Layout/style: copy from `state-vs-family-evidence` verbatim
  (per user-confirmed plan-mode question).
- Repo stays uncommitted; no remote configured.

## Next increment

**I-02 (BTC ingest):** requires `data/raw/manifest.txt` (currently absent — see
failing tests in `tests/test_provenance.py`). Will be implemented next session
if approved; the test file's expectations are already on disk
(spot-check 2017-12-17 close ≈ $19,497 within ±1d; row count > 5,000).

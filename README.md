# Repository entry point for the Bitcoin Halving-Cycle Framework.

## What this site is

A long-term research framework that studies Bitcoin's halving cycles and
their cross-asset correlations with select altcoins (ETH, SOL, XRP) and
global macro assets (SPX, NDX, DXY, TLT). Forecasts the **time ranges and
entry/exit zones of the next BTC cycle** as uncertainty bands. Not an
automated trading bot, not financial advice.

The full design (sources, procedure, deliverables, validation gates) lives
in [`DESIGN.md`](./DESIGN.md).

## Quick start

```bash
# Build the site locally
bundle install
bundle exec jekyll build

# Run the validation gates (full test suite)
pytest -q tests/
```

Published at `https://<user>.github.io/trading/` (auto-deployed on push to
`main` via `.github/workflows/deploy.yml`).

<!-- TODO: replace with published Pages URL once the GitHub remote is configured. -->

## Repository layout

```
.
├── DESIGN.md                # Inputs / procedure / deliverables — NO point estimates
├── AGENTS.md                # Workflow notes for human + agent contributors
├── _config.yml              # Jekyll config
├── Gemfile                  # Jemml + webrick
├── .github/workflows/       # GitHub Pages deploy
├── index.md                 # Site landing
├── status.md                # Live increment statuses (linked from sidebar)
├── _layouts/                # Jekyll layout
├── _includes/               # Reusable HTML partials (e.g. provenance footer)
├── _sections/               # White-paper collection (abstract, methodology, ...)
├── assets/                  # CSS + later: charts (C1-C7 in I-13)
├── data/                    # raw/ (immutable), processed/ (regenerable), events.csv
├── scripts/                 # fetcher, cycle_metrics, correlations, forward_ranges
├── notebooks/               # exploratory Jupyter (paired with scripts/)
└── tests/                   # gate tests per increment (test_events_schema, test_provenance, ...)
```

## Validation discipline

- Every increment has a gate (`pytest tests/test_*.py`) before merging.
- The full suite runs against `main` after clean clone.
- A failed gate does **not** cause upstream increments to be modified to
  force a pass. Failures write a blocker note in `docs/blockers/`.

See [`AGENTS.md`](./AGENTS.md) for the contributor workflow.

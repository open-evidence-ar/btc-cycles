# I-20 (banner refinements) — 2024 timeline floor + accumulation drop + window center markers

**Increment:** I-20 (per-asset banner pivot — second-view-layer follow-up)
**Date:** 2026-08-05
**Status:** Applied (view-layer only — no backend change)
**Rule tuned:** Per DESIGN.md §9.4 (rule tuned, reconciliation entry written)

## Background / prior state

After the first per-asset banner pivot emitted a clean 6-pill timeline with
a phase-aware projection walk, three refinements clarified the chart's
readability:

1. **Timeline was visually too wide** — every pill's visible span ran
   ~9–10 y because `tlStart` was set to the earliest of (lastMs, firstHistMs)
   and most assets' raw history began 2022-01. The banner's purpose is the
   *cycle decision window* (H4 halving → C4 top → bear → B4 → C5 → B5),
   not long-term price-history context — which is what the C1–C9 charts
   carry. A 7 y window from 2024-01-01 onward shows the actionable timeline.
2. **The long accumulation band dominated the strip width** — for BTC the
   published "accumulation / patience window" between B4 close (2026-11-17)
   and C5 outer start (2029-04-07) is ~501 days. That green-band width
   dwarfed the 21-day B4 *base* band (the actual decision window) and the
   175-d C5 outer band (the next top window). The accumulation band is a
   *secondary patience indicator*, not a buying-action band — rendering it
   as a colored vrect made the strip visually misleadingly top-heavy on
   patience rather than action.
3. **Thin windows were barely visible at strip scale** — MSTR's projected
   C5 outer spans only 60 days, vs WGMI's 589 days and BTC's 175 days. On a
   ~7 y strip 60 d ≈ 2.4% of the width — a thin sliver, easy to miss when
   scanning per-pill. Same with SOL's C5 outer (271 d) contracting relative
   to BTC's. Without a positional marker the user could not reliably tell
   "C5 happens around 2028-12" for assets whose band was thin.

## Action (view-layer only — `_includes/now-stamp.html` + `assets/css/style.css`)

### 1. Timeline floor
`drawStrip()` now hard-caps `tlStart = parseDate('2024-01-01')` for all pills
and filters `histPts` to on-or-after 2024-01-01 (drops ~half the
pre-2024 weekly samples per asset, making each pill's line focus on the
post-H4 cycle). Right-only pad (2% of visible span) keeps slight breathing
room near the projected outer_end; left side stays pinned to 2024-01-01.
Result: pill widths are uniformly ~7 y (6.81–7.14 y).

### 2. Accumulation rect dropped
The `(baseEnd + 1d) → distOS - 1d` vrect (`.band .band-patience`) and its
"Accumulation" label are no longer rendered. The three action windows —
B4 bottom (amber), C5 top (amber strong), B5 exit (red) — are now the only
colored mass on the strip. The accumulation period remains implicitly
visible as the uncolored plot area between B4 close and C5 open.

### 3. Vertical window center markers
A new `windowCenterMarker()` renderer draws a thin dashed vertical line +
small label ("C5 ⌄" / "B5 ⌄") at each window's outer-band center date.
CSS `.window-center-marker` (1px dashed, white-alpha 0.32) and
`.window-center-label` (8px white-alpha 0.78) keep the marks low-key vs the
band-corridor ribbons — they guarantee every window has at least one
visible chart mark even for MSTR's 60-day C5 outer and SOL's 271-day exit.

### 4. SVG `<svg>` aria-label
Updated to drop the "accumulation" word from the screen-reader description
(reflects the actual stripped-down render).

### 5. Timeline cap
Tightened from `TIMELINE_CAP_YEARS = 10` to `= 7` so WGMI's exit window
(ends 2033-07) triggers the continuation marker (`→ +2.55y`) instead of
expanding WGMI's strip to ~10 y. With the tighter cap every asset's strip
width formats to ~7 y, plus an optional continuation marker for assets
whose published windows extend past the cap.

## Per-asset span summary (post-fix)

| Asset | tl_start | tl_end | span (y) | overshoot marker? |
|---|---|---|---|---|
| BTC  | 2024-01-01 | 2030-12-29 | 6.99 | no |
| XRP  | 2024-01-01 | 2030-10-24 | 6.81 | no |
| ETH  | 2024-01-01 | 2030-10-24 | 6.81 | no |
| SOL  | 2024-01-01 | 2031-02-20 | 7.14 | **+0.12y** (SOL exit ends 2031-04) |
| MSTR | 2024-01-01 | 2031-01-08 | 7.02 | no |
| WGMI | 2024-01-01 | 2031-02-20 | 7.14 | **+2.55y** (WGMI exit ends 2033-07) |

## MSTR 60-day C5 outer — was this ever a bug?

No. MSTR's projected C5 outer span (60 d) reflects MSTR's historically
tight cycle multipliers `[13.806, 34.680]` vs BTC's wider `[22–93]` — the
width of the projected C5 distribution band derives from the spread on
MSTR's own multipliers (n=2). A wider spread (BTC/WGMI) produces a wider
projected top window; a tighter spread contracts it. Post-I-19 the model
respects each alt's own-asset-shape so MSTR's narrow top window IS
methodology-correct. The vertical center marker (#3 above) addresses the
visualisation concern without altering the model input.

## Validation

```
$ python -m pytest tests/ -q
182 passed in 64.52s
$ bundle exec jekyll build
                    done in 0.46 seconds.
```

The `tests/test_refresh_all.py::test_build_cycle_status_runs` test continues
to pass since none of its assertions lock on the timeline start (it asserts
required keys present + price strings start with `$` + the BTC + 3-alt watch
order presence). My changes are confined to `_includes/now-stamp.html` and
`assets/css/style.css` — no backend, no `_data/cycle_status.json` shape
change.

## Scope

These refinements tune the banner's readability without altering the data
authoritative source (alt_next_cycle_zones.csv / next_cycle_zones.csv).
Any reader who wants the long pre-2024 view still gets it via the C1–C9
prediction charts and the campaign-level analysis in the body chapters.
The banner is now narrowly focused on "where are we today / when is the
next action window / what does the price projection look like over the
upcoming cycle window".

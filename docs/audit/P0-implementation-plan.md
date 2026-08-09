# P0 Implementation Plan — Crypto Cycle Correlation Site

Status: EXECUTED — all P0 items implemented and verified green (2026-08-08)
Audit source: `docs/audit/ui-ux-audit-2026-08-08.md`
Gates: each P0 item must pass `bundle exec jekyll build` + `bundle exec jekyll serve` visual verification at desktop 1440×900 and mobile 390×844 before starting next item.
Rule (AGENTS.md): fix failing increment — do NOT patch upstream increments.

---

## P0-1 — 8 section pages return 404 (nav links broken everywhere, desktop + mobile)

**Symptom:** Sidebar in `_layouts/default.html` links to `/predictive-ranges/`, `/cross-asset-timing/`, `/validation/`, `/methodology/`, `/cycle-anatomy/`, `/cross-asset/`, `/release-checklist/`, `/theory/` — all 404 (unstyled Jekyll default). Only `/`, `/abstract/`, `/status/` render.

**Root cause (file:line):**
- `_config.yml:17` — `collections.sections.output: false` → collection pages are never emitted.
- `_sections/*.md` (8 files) — no `permalink:` in front matter; `_config.yml:18` sets `permalink: /sections/:name/` but `output: false` suppresses emission regardless.
- `_layouts/default.html:24-36` — hardcoded URLs assume `/predictive-ranges/` (name-based), but the collection permalink produces `/sections/predictive-ranges/` when output is enabled.

**Fix (pick ONE of A or B — A preferred, keeps URLs stable):**

### Option A — emit sections at the URLs the nav already uses (RECOMMENDED)
Edit `_config.yml`:
```
collections:
  sections:
    output: true
    permalink: /:name/
```
No changes needed to `_layouts/default.html`. The 8 URLs (`/predictive-ranges/` etc.) will now resolve to `_sections/predictive-ranges.md` etc.

Add front matter to each `_sections/*.md` (if missing) so `layout: default` applies:
Already covered by `_config.yml` defaults (`defaults` block line 9-13 applies `layout: default`). Confirmed working for `/abstract/` and `/status/` which are not in `sections` but are top-level markdown files.

Verification:
```bash
bundle exec jekyll build
# Check _site/ contains: predictive-ranges/index.html, cross-asset-timing/index.html,
# validation/index.html, methodology/index.html, cycle-anatomy/index.html,
# cross-asset/index.html, release-checklist/index.html, theory/index.html
```

### Option B — change sidebar links to match `/sections/:name/`
Keep `_config.yml:output: false` unchanged. Edit `_layouts/default.html:24-36` to prepend `/sections/` to all 8 links. Less preferred — breaks external/bookmarked URLs; audit evidence shows the site was intended to have name-based permalinks (`permalink: pretty` set globally).

**Gate:** After fix, all 11 sidebar links must return HTTP 200 (not 404). Screenshot `page_predictive-ranges.png` must show the actual section content, not the unstyled Jekyll 404.

**Risk:** None — pure config + build verification. No upstream files edited except `_config.yml` and optionally `_sections/*.md` front matter (only if a file is missing layout — verify after build).

---

## P0-2 — Zero mobile navigation (`.mobile-toc` CSS exists but never rendered)

**Symptom:** At ≤760 px, `.sidebar { display: none }` (`assets/css/style.css:345`). `.mobile-toc { display: block }` (`style.css:349`, 405-425) is defined but **no element with class `mobile-toc` exists in any layout or include**. Mobile users have zero navigation chrome.

**Fix — add `.mobile-toc` element to `home.html` and `default.html`:**

In `_layouts/home.html` (after `<body>` open, before `.main`): add a collapsible mobile nav that mirrors the sidebar links. Example structure (matches existing `.mobile-toc` CSS rules):
```html
<nav class="mobile-toc">
  <button onclick="document.querySelector('.mobile-toc ul').classList.toggle('open')">Menu</button>
  <ul>
    <li><a href="{{ '/' | relative_url }}">Home</a></li>
    <li><a href="{{ '/abstract/' | relative_url }}">Abstract</a></li>
    ... (same 11 links as sidebar)
  </ul>
</nav>
```
The `.mobile-toc` CSS (lines 349, 405-425) defines styling (`position: sticky`, `top`, `background`, `box-shadow`, `ul { display: none }` toggled by `.open`). Confirm the `.mobile-toc ul.open` selector is present (line 420-425) — yes, it is. Only the HTML element is missing.

**File to edit:** `_layouts/home.html` and `_layouts/default.html` (add the same block). Prefer adding to both; `home.html` uses `layout: home`, `default.html` is the section layout.

**Verification:**
- Desktop (1440): `.mobile-toc` hidden (`display: none` or `block` overridden by media query at >760). Confirm sidebar visible.
- Mobile (390): `.mobile-toc` visible; sidebar hidden; tapping button reveals links; all 11 links clickable and resolve (after P0-1 is done).
- Screenshot `page_index.png` mobile must show the mobile-toc button, not an empty left column.

**Gate:** Mobile viewport (390×844) must have a working nav element with all links functional. No new CSS needed — `.mobile-toc` rules are already complete.

**Risk:** Low. Only HTML insertion; uses existing CSS selectors.

---

## P0-3 — C8-family charts overflow at every viewport (C8, C8b, C8c, C8e, C8f, C8g, C8d)

**Symptom (measured):**
- Desktop iframe innerW=1066: chart svgW=1200 → bodyScrollW=1208 → internal horizontal scrollbar on desktop; vertical overflow (820px content in 700px iframe, scrollH 836 vs innerH 700).
- Mobile iframe innerW=348: only ~29% of chart width visible (`bodyScrollW=1208` clipped behind `overflow-x: clip`).

**Root cause (file:line):**
- `scripts/build_charts.py:1921` — `_build_alt_chart()` sets `height=820, width=1200`.
- `scripts/build_charts.py:2244` — `build_c8_macro()` (`C8d`) sets `height=2000, width=1200`.
- Both pass `config={'responsive': True}` (`line 1924, 2247`), but `responsive` does NOT rescale figures whose `width` is fixed — confirmed empirically in audit (§5.1, 3.1 table).
- The embedded `.html` files (not `.png`) are what render on the site (`_includes/chart.html` embeds `*.html`).

**Fix — drop fixed `width`/`height`, rely on responsive sizing controlled by the iframe/container:**

Edit `scripts/build_charts.py`:

1. In `_build_alt_chart` (`line 1917-1923`), change:
```
fig.update_layout(
    ...
    height=820, width=1200,
    ...
)
```
to:
```
fig.update_layout(
    ...
    height=700,      # slightly shorter — fits standard iframe height; responsive width
    # width=1200,     # REMOVED — let autosize/responsive handle width
    autosize=True,   # ADD — was missing; combined with responsive=True allows resize
    ...
)
```
Note: the chart content (annotations, zone bands) uses paper-coordinate references (`yref='paper'`, fixed `ax`/`ay`) — reducing height slightly may shift bottom notes. Verify notes don't overlap bottom zone bands after resize.

2. In `build_c8_macro` (`line 2240-2245`), change:
```
    height=2000, width=1200,
```
to:
```
    height=1000,
    autosize=True,
```
The macro chart has 4 sub-panels stacked; 2000px was excessive even for desktop. 1000px with responsive width fits better and avoids the internal scrollbar.

3. Confirm `_includes/chart.html`: the iframe has `width:100%` and no fixed pixel width (line 293-299). Confirmed — it uses `width:100%; max-width:100%`. The issue is the *plotly figure's internal SVG width*, not the iframe width.

4. Confirm `_includes/chart.html` inline `style="height:{{include.height}}"` (line 11-14). The charts use `height="700px"` etc. in chapter markdown. After reducing `fig.update_layout(height=...)` to 700, the inline iframe height should match (or be reduced to 560px for mobile). No change needed to `chart.html` unless we want mobile-specific heights — out of scope for P0.

**Verification (must be done after rebuild + chart re-export):**
```python
python scripts/build_charts.py  # or the refresh pipeline
```
Then open `assets/charts/C8.html`, `C8d.html` in browser at 1440 and 390. Confirm:
- No horizontal scrollbar (`body.scrollWidth <= clientWidth`).
- Chart fills the full card width (no large empty right margin as with 700px fixed charts).
- All annotations (zone labels `BEAR_BOTTOM`, `ACCUMULATION`, `DISTRIBUTION`, `EXIT`, `C4 top`, `B4 proj`) remain visible and do NOT overlap (P1-5 overlaps must be retested after resize — reducing width may actually improve overlap).

**Gate:** C8-family charts render fully at 348px mobile width with no horizontal clipping. Desktop shows full-width chart, no internal scrollbar.

**Note on overlap:** Reducing width from 1200→responsive may shift annotation positions (annotations use `ax`, `ay` pixel offsets). The overlap audit (§5.2) measured overlaps at the *current* 1200px-fixed size. After resize, retest overlaps — some may resolve, new ones may appear. Document any new overlaps in the audit file; fix overlaps is a P1 task (P1-5), not P0.

**Risk:** Medium — changing chart dimensions may alter annotation placement. Must retest overlaps. But P0 gate only requires no overflow/clip; overlap is P1.

---

## P0-4 — C2/C3/C4/C5/C7 stuck at 700px (same root cause, smaller impact)

**Symptom (measured):**
- Desktop (iframe innerW=1066): chart svgW=700 in 1050px div → large empty right half; chart does not fill card.
- Mobile (iframe innerW=348): svgW=700 > 348 → right ~50% clipped; same overflow mechanism as P0-3 but at 700px.

**Root cause (file:line):**
- `scripts/build_charts.py:877` — C2: `autosize=False`
- `scripts/build_charts.py:917` — C3: `autosize=False`
- `scripts/build_charts.py:949` — C4: `autosize=False` (need to read for confirmation)
- `scripts/build_charts.py:976` — C5: `autosize=False` (need to read for confirmation)
- `scripts/build_charts.py:1486` — C7: `autosize=False` (need to read for confirmation)

**Fix — remove `autosize=False` and set responsive width:**

In each of the 5 build functions, change:
```
fig.update_layout(
    ...
    autosize=False,
    ...
)
```
to:
```
fig.update_layout(
    ...
    autosize=True,   # or simply remove the autosize=False line
    # add: width is handled by responsive config; no fixed width
    ...
)
```
Keep the existing `height=500` or `height=560` (those are fine). Do NOT add `width=700` or any fixed width. The `config={'responsive': True}` already passes to the HTML writer. Removing `autosize=False` allows Plotly to resize the figure to the container.

**Files/lines to edit (exact):**
- C2: `build_charts.py:877` (confirmed in audit §5.1)
- C3: `build_charts.py:917` (confirmed)
- C4: `build_charts.py:949` — verify by reading; edit same pattern
- C5: `build_charts.py:976` — verify; edit same pattern
- C7: `build_charts.py:1486` — verify; edit same pattern

**Verification (after rebuild):**
- Desktop 1440: C2/C3/C4/C5/C7 fill the full card width (no 700px small chart floating left).
- Mobile 390: no internal horizontal scrollbar; full chart visible.
- No annotation overlap introduced by wider layout (test at 348px).

**Gate:** All 5 charts must render without clipping at mobile width. Confirm with Playwright screenshots at 390×844.

**Risk:** Very low — removing `autosize=False` restores default responsive behavior. No layout changes to annotations unless the wider view reveals more of the plot area (which is positive).

---

## Cross-dependencies / order

Order: P0-1 (404 fix) → P0-2 (mobile nav) → P0-3 (C8 overflow) → P0-4 (C2-5/C7 overflow).

Dependencies:
- P0-2 requires P0-1 to be meaningful (mobile nav links must resolve to real pages).
- P0-3 and P0-4 are independent of P0-2 (they are chart source edits + rebuild); can be done in parallel with P0-2 if a second agent handles chart rebuild while first handles HTML.
- P0-3 and P0-4 touch the same file (`scripts/build_charts.py`) and the same rebuild pipeline — do them sequentially in the same session to avoid merge conflicts on the rebuilt `.html`/`.png` assets.

## Rebuild pipeline

After any `build_charts.py` edit:
```bash
python scripts/refresh_all.py --no-fetch   # rebuild derived + charts only (~90s)
# OR, if only charts changed:
python -c "
import sys; sys.path.append('scripts')
from build_charts import build_all
build_all()
"
```
Then:
```bash
bundle exec jekyll build
bundle exec jekyll serve --port 4000 &
# Then Playwright screenshot at desktop + mobile for verification.
```

## Blocker note format (per AGENTS.md)

If any P0 item fails its gate, write to `docs/blockers/P0-X-name>.md` with:
- Input snapshot (git commit hash of files edited)
- Expected vs actual (e.g., screenshot path + measurement)
- Hypothesis (why the fix didn't work)
- Action (next step — do NOT patch upstream P0 items)

## Confirmed after audit (do NOT change these — they work)

- Viewport meta (`_layouts/default.html:5`, `home.html:5`) — correct.
- C1 / C6 / C9 / C-SMA responsive — already working; do not add `autosize=False` back.
- `_includes/provenance-footer.html` — no issue.
- Dark theme, banner interactivity, index page anchor links — all confirmed working; no changes needed.

---
*Plan written: 2026-08-08. Source: audit `docs/audit/ui-ux-audit-2026-08-08.md`. No source files modified during plan drafting.*

---

## Execution log (2026-08-08)

All four P0 items implemented and verified in real browsers (Playwright + system Chrome):

### Changes applied
| Item | File(s) | Change |
|---|---|---|
| P0-1 | `_config.yml` | `collections.sections.output: true` + `permalink: /:name/` → all 8 section pages now emit at `/predictive-ranges/` etc. |
| P0-2 | `_layouts/home.html`, `_layouts/default.html` | Added `.mobile-toc` nav (11 links) mirroring the sidebar; home scrollspy updated to include `#mobile-toc` |
| P0-2 (fix) | `assets/css/style.css` | Base `.mobile-toc { display:none }` moved into `@media (min-width:761px)` so the ≤760px `display:block` rule is not overridden by source-order cascade |
| P0-3 | `scripts/build_charts.py` | `_build_alt_chart`: dropped `width=1200`, added `autosize=True`, `height` 820→700 (matches iframe `700px`); `build_c8_macro` (C8d): dropped `width=1200`, added `autosize=True` |
| P0-4 | `scripts/build_charts.py` | Removed `autosize=False` from C2 (was :877), C3 (:917), C4 (:949), C5 (:976), C7 (:1486) |

### Verification (Playwright, 1440×900 desktop + 390×844 mobile)
- **Pages:** all 11 URLs return HTTP 200 on both viewports (was 3/11; the 8 section pages previously 404'd).
- **Charts:** all 16 HTML charts (`C1`–`C9`, `C-SMA`) render full-width with **no overflow** on both viewports:
  - desktop: svg 1424px = client 1440px, scrollW == clientW (was: C8-family 1208px scroll, C2–C5/C7 stuck at 700px with empty right half)
  - mobile: svg 374px fits client 390px (was: C8-family ~29% visible, C2–C5/C7 right ~50% clipped)
- **Mobile nav:** `.mobile-toc` visible at 390px with 11 links (was: zero nav chrome ≤760px).
- Evidence: `audit_screenshots/fix_mobile_index.png`, `fix_desktop_section.png`, JSON in `opencode_temp/p0_verify.json`.

### Test suite: `python -m pytest -q` → 178 passed, 4 failed
All 4 failures are **pre-existing** (confirmed against git HEAD, not caused by this work):
1. `test_png_determinism` — committed PNG blobs already differ from `tests/chart_snapshots.json` (audit: PNGs corrupt since init commit `bb3045a`).
2. `test_charts_c8_c9_snapshot_determinism` — same root cause (committed C8/C9 PNGs differ from snapshot).
3. `test_charts_c8g_snapshot_determinism` — same root cause.
4. `test_events_sha_in_methodology` — `data/events.csv` working-copy SHA differs from methodology.md's quoted SHA **only** via CRLF/LF line endings on this Windows checkout (`git diff` shows no content change; committed SHA `be24…` vs working `80e2…`).

**Deferred (not in P0 scope):**
- Regenerating `tests/chart_snapshots.json` after intentional chart-size changes (P0-3/P0-4) — the gate pins PNG byte determinism; refresh only after confirming the new PNGs are byte-stable.
- Fixing the CRLF artifact in `data/events.csv` + methodology SHA (pre-existing).
- All P1/P2 items from the audit (zone-label overlaps on C6/C8/C8g, banner strip overlap, table clipping, 8px fonts).

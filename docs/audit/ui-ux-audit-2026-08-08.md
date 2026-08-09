# UI/UX Audit — Crypto Cycle Correlation Framework (GitHub Pages)

- **Date:** 2026-08-08
- **Scope:** Overlapping labels, broken UI/UX, mobile-viewport usability of the Jekyll site at `D:\trading`
- **Method:** static file audit + real-browser capture (Playwright + system Chrome) at 1440×900 (desktop) and 390×844 (mobile, iPhone-14-class), served from `_site` via `python -m http.server 4000`
- **Build under test:** `bundle exec jekyll build` (passes, 0.585 s); pages served from `_site`
- **Status of target pages:** `/`, `/abstract/`, `/status/` render; **all 8 section pages 404** (see P0-1)

---

## 1. Screenshot inventory

No `docs/screenshots/` directory exists in the repo, so this audit captured its own inventory into `D:\trading\audit_screenshots\` (42 files, 21 per viewport). Do not commit these — they are audit artifacts.

### 1.1 Existing static assets (broken)
- `assets/charts/*.png` (16 files, C1–C9, C8b–C8g, C-SMA): **all corrupt since the initial commit**. PNG signature bytes `89 50 4E 47` were replaced by text-mangled bytes during a UTF-8/latin-1 round-trip:
  - init commit `bb3045a` blob: `3F 50 4E 47` (`?PNG`)
  - HEAD blob `a222bd4`: `3F 3F 3F 50 4E 47` (`???PNG`)
  - `PIL.UnidentifiedImageError` and `System.Drawing` both fail to open them.
- The site does **not** reference the PNGs (`_includes/chart.html` embeds the paired `*.html` Plotly files). `DESIGN.md` static snapshots pointing at the PNGs are dead.
- `assets/charts/*.html` (16 files): valid Plotly 3.7.0 documents, render correctly (all frames `ready=True`).

### 1.2 Captured screenshots (this audit)
| Viewport | Pages | Charts | Banner |
|---|---|---|---|
| Desktop 1440×900 | `page_index.png` (3.1 MB), `page_abstract.png`, `page_status.png`, `page_predictive-ranges.png` (**404 page** — 14 KB) | `chart_C*.png` ×16 | `banner_expanded.png` |
| Mobile 390×844 | same 4 page files | `chart_C*.png` ×16 | `banner_expanded.png` |

- `page_predictive-ranges.png` (both viewports) is the unstyled Jekyll default **404 page** — direct visual evidence of the broken-nav issue (P0-1).
- Desktop `page_index.png` (3.1 MB) covers the full-length single-page layout incl. lazy-loaded charts.
- Chart screenshots were taken by navigating directly to each `assets/charts/*.html` and in-context (iframe) metrics captured via Playwright.

---

## 2. Layout / template files audited

| File | Role | Findings |
|---|---|---|
| `_config.yml` | Site config | `collections.sections.output: false` + `_sections/*.md` have no `permalink:` front matter → **sections never emitted as pages** (P0-1) |
| `_layouts/default.html` | Sidebar layout (abstract/status) | viewport meta present (line 5); sidebar hardcodes 11 absolute URLs, **8 of which 404** |
| `_layouts/home.html` | Single-page home | viewport meta present (line 5); anchors only — home is the only page with working navigation |
| `_includes/chart.html` | Chart wrapper | `<iframe … loading="lazy" style="width:100%;max-width:100%;border:none;height:{{include.height}};">` — inline height beats the mobile CSS override (P2-3) |
| `_includes/now-stamp.html` | Sticky banner | Inline SVG strip (`viewBox="0 0 600 120"`) with JS-built band labels (lines 364–388) → **overlapping labels** (P1-1); segs truncated by CSS (P1-3) |
| `_includes/provenance-footer.html` | Footer | no issues |
| `assets/css/style.css` (869 lines) | All styling | see §4 |
| `_sections/*.md` (8 files) | Chapter content | no inline styles; only `{% include chart.html %}` tags with `height="700px"` etc. |

---

## 3. Real-browser capture (Playwright + Chrome, two viewports)

Served `_site` at `http://127.0.0.1:4000`; frames measured in-context (defeated `loading="lazy"` by scrolling each iframe into view).

### 3.1 Chart iframe geometry (measured)

| Chart(s) | Desktop iframe (innerW=1066) | Mobile iframe (innerW=348) | Verdict |
|---|---|---|---|
| C1, C6, C9, C-SMA | svgW=1050 = divW (responsive) | svgW=332 = divW | ✅ fit |
| C2, C3, C4, C5, C7 | **svgW=700** (fixed) in 1050 px div — big empty right half, chart not full-width | **svgW=700 in 348 px iframe → bodyScrollW=708** → right ~50% clipped behind internal scrollbar | ❌ (P0-4) |
| C8, C8b, C8c, C8d, C8e, C8f, C8g | **svgW=1200** → bodyScrollW=1208 > 1066 → **horizontal scrollbar even on desktop**; content 820 px tall in 700 px iframe → vertical scroll (scrollH 836 vs innerH 700) | **svgW=1200 in 348 px iframe → only ~29% of chart width visible** | ❌❌ (P0-3) |

### 3.2 Page-level checks (measured)
- No page-level horizontal overflow anywhere (`scrollW == innerW` on `/`, `/abstract/`, `/status/` at both viewports) — `.main { overflow-x: clip }` hides it, but it also makes clipped table columns **unreachable** (P1-4).
- Banner expanded height measured: **289.9 px desktop, 334.5 px mobile** vs CSS var `--banner-height-expanded: 17rem` = **272 px** → anchor `scroll-margin-top` under-shoots (P2-4).
- `/predictive-ranges/` and the other 7 section URLs return HTTP 404 (P0-1).

---

## 4. CSS audit (`assets/css/style.css`)

| Area | Line(s) | Finding |
|---|---|---|
| `--banner-height-expanded: 17rem` | 33 | under-measures actual banner height (see §3.2) |
| `.main { overflow-x: clip }` | 157 | prevents page scroll but **clips + hides** overflowing tables on mobile (P1-4) |
| `.chart-container iframe` | 293–299 | default `height:560px`; overridden by inline styles from `chart.html` |
| `@media (max-width:760px)` | 334–349 | sidebar `nav {display:none}` (345) + `.mobile-toc {display:block}` (349) — **but no `.mobile-toc` element exists in any layout/include → mobile users get zero nav chrome** (P0-2) |
| `@media (max-width:768px)` | 852–857 | second, overlapping mobile block; `iframe {height:400px}` (348) is dead code — inline `height:` wins (P2-3) |
| `.now-stamp-text .seg` | 526–532 | `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` → banner text truncated at **both** viewports (P1-3) |
| `scroll-margin-top` | 394 | uses banner-height var (272 px) < actual banner (290–335 px) |
| font sizes | 661, 684, 739, 752, 771, 790, 808, 818 | `8px`/`8.5px` on `.table-dense` + footnotes — below any usable/accessible floor (P2-5) |
| `.mobile-toc` | 349, 405–425 | defined, never rendered (P0-2) |

Media query breakpoints present: 960, 760, 768 px. Only two font-size families total (`--font-size` base), but 20+ distinct sizes incl. px values.

---

## 5. Chart label audit (`scripts/build_charts.py`, 2213 lines)

### 5.1 Hardcoded figure sizes (root cause of P0-3/P0-4)
| Location | Code | Charts affected |
|---|---|---|
| `build_charts.py:877, 917, 949, 976, 1486` | `autosize=False` (no width → default 700) | C2, C3, C4, C5, C7 |
| `build_charts.py:1921` | `height=820, width=1200` (inside `_build_alt_chart`, line 1508) | C8 (ETH), C8b (XRP), C8c (SOL), C8e (MSTR), C8f (WGMI), C8g (GOLD) |
| `build_charts.py:2244` | `height=2000, width=1200` | C8d (macro) |
| all writes | `config={'responsive': True}` | — does **not** rescale figures whose width/autosize is fixed (confirmed empirically: svg stays 700/1200) |

### 5.2 Overlapping annotations (measured bounding-box intersections)
| Chart | Overlap pair(s) | Desktop | Mobile |
|---|---|---|---|
| C6 | `BEAR_BOTTOM` ↔ `ACCUMULATION` | yes | yes |
| C6 | `DISTRIBUTION` ↔ `EXIT`; `C4 top` ↔ `B4 proj` | no | yes |
| C8 (ETH) | `BEAR_BOTTOM` ↔ `ACCUMULATION` | yes | yes |
| C8g (GOLD) | `BEAR_BOTTOM` ↔ `ACCUMULATION` + `DISTRIBUTION` ↔ `EXIT` | yes | yes |
| C1–C5, C7, C8b–C8f, C9, C-SMA | none | — | — |

Annotations are placed at fixed coordinates (e.g., zone labels at fixed `x` refs in `_build_alt_chart`; C1 alternates paper-anchored `y=0.97/0.93/0.05/0.10`, font size 9; alt-chart `C4 top` marker `ax=40, ay=-20`), so they collide when the plot is rendered at 1200 px vs when it is squeezed — they never re-flow.

### 5.3 Banner strip overlap (`_includes/now-stamp.html`)
- `bandLabel(distOS, distOE, 'Next top')` (line 368) and `bandLabel(exitOS, exitOE, 'Exit')` (line 369) place band labels at band midpoints; `windowCenterMarker(…, 'C5 ⌄')` (384) and `windowCenterMarker(…, 'B5 ⌄')` (388) place marker labels at window centers with `text-anchor` start.
- **Measured overlaps at both viewports:** `Next top` ↔ `C5 ⌄` and `Exit` ↔ `B5 ⌄`. No collision avoidance; SVG is 600×120 logical units scaled to 1032 px (desktop) / 322 px (mobile) width.

---

## 6. Mobile usability checklist

| Check | Result | Evidence |
|---|---|---|
| Viewport meta present | ✅ | `_layouts/default.html:5`, `home.html:5` |
| No horizontal page scroll | ✅ | scrollW == innerW all pages, both viewports |
| Navigation available on ≤760 px | ❌ | `.sidebar nav` hidden (style.css:345); `.mobile-toc` never rendered (P0-2) |
| Charts fit width | ❌ | C2–C5/C7 svg 700 px; C8-family svg 1200 px (P0-3/P0-4) |
| Tables readable | ❌ | 13/19 home tables exceed 358 px column (up to 660 px); `.main` clips, no scroll (P1-4); status table 761 px |
| Banner text visible | ❌ | all three segs ellipsized; `Next: Next cycle bottom in 57d…` truncated (P1-3) |
| Banner labels not overlapping | ❌ | `Next top`↔`C5 ⌄`, `Exit`↔`B5 ⌄` (P1-1) |
| Minimum readable font | ❌ | 8–8.5 px table/footnote text (P2-5) |
| Dead links | ❌ | 8 sidebar links → 404 (P0-1) |

---

## 7. Prioritized issue list (with remediation)

### P0 — broken, fix first
1. **8 of 11 sidebar nav links 404** — `_config.yml` (`collections.sections.output: false`) + no `permalink:` in `_sections/*.md` vs hardcoded links in `_layouts/default.html`. Every abstract/status user hits unstyled 404 pages.
   → Set `output: true` + add per-section `permalink:` (or convert to Jekyll collections-as-pages correctly).
2. **No mobile navigation at all** — `.mobile-toc` CSS exists (style.css:349, 405–425) but no element is rendered in any layout/include; sidebar is hidden ≤760 px (style.css:345).
   → Add a real `.mobile-toc` nav element to `home.html`/`default.html`.
3. **C8-family charts overflow at every viewport** — `width=1200` hardcoded (build_charts.py:1921, 2244) inside 1066×700 px desktop iframes / 348 px mobile iframes; desktop needs internal h+v scrollbars, mobile shows ~29% of chart.
   → Drop fixed `width`/`height`, use `autosize=True` + responsive; set iframe height via CSS (or `height:auto` + aspect-ratio) not inline px.
4. **C2/C3/C4/C5/C7 stuck at 700 px** — `autosize=False` (build_charts.py:877, 917, 949, 976, 1486): desktop shows a 700 px chart in a 1050 px card; mobile clips right ~50%.
   → Remove `autosize=False` (or set explicit responsive width).

### P1 — major UX defects
5. **Zone labels overlap** — C6/C8/C8g `BEAR_BOTTOM↔ACCUMULATION` (both viewports), C6 +`DISTRIBUTION↔EXIT`/`C4 top↔B4 proj` (mobile), C8g +`DISTRIBUTION↔EXIT`. Fixed annotation coords never re-flow (build_charts.py `_build_alt_chart` region 1773–1921).
   → Offset via `ax/ay`, stagger alternate bands, or use `xshift` conditioned on band width; test at 348 px.
6. **Banner strip labels overlap** — `Next top`↔`C5 ⌄`, `Exit`↔`B5 ⌄` at both viewports (now-stamp.html:364–388).
   → Add per-band text-anchor/rotation, shorten marker labels, or place marker labels under the strip.
7. **Banner text truncated everywhere** — segs ellipsized even on desktop (style.css:526–532); mobile cuts the critical `Next: …` forecast.
   → Allow wrapping or two-line layout for segs; or drop fixed flex-basis and let segs wrap.
8. **Mobile tables clipped & unreachable** — 13/19 tables exceed 358 px column (up to 660 px) + `.main {overflow-x:clip}` (style.css:157); status table 761 px.
   → Wrap tables in `overflow-x:auto` containers (remove reliance on clip); or scale `.table-dense` font down on mobile.

### P2 — polish / maintenance
9. **Static chart PNGs corrupt since init commit** (`?PNG` → `???PNG`); unreferenced by site but DESIGN.md snapshots broken; no `docs/screenshots/` dir.
   → Re-export PNGs from the Python pipeline and re-commit (git blobs are binary-corrupt in history; add a regression gate that opens every PNG).
10. **Unstyled 404 pages** for all 8 dead section URLs → will disappear with P0-1; still add a styled 404.html.
11. **Dead mobile iframe rule** — `iframe {height:400px}` (style.css:348) can never win against inline `height:` (chart.html:11–14).
12. **Banner height var under-measures** (272 px var vs 290–335 px actual) → anchor links land under the banner (style.css:33, 394).
13. **8–8.5 px fonts** in `.table-dense`/footnotes (style.css:661–818) — below usable minimum.
14. **Duplicate mobile breakpoints** 760 px (style.css:334) and 768 px (style.css:852) — consolidate.

### Confirmed OK
- Viewport meta, no page-level horizontal scroll, desktop tables fit, C1/C6/C9/C-SMA fully responsive, chart HTML frames all render (`ready=True`), dark theme + banner interactivity work, index page single-file TOC anchors functional.

---

*Audit artifacts: `D:\trading\audit_screenshots\`, diagnostics in `D:\trading\opencode_temp\` (`overlap_diag.json`, `deep_diag.json`, `iframe_diag3.json`). No project files were modified.*

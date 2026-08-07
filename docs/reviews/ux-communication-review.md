# UX Communication Review — Bitcoin Halving-Cycle Framework Report

**Scope:** Holistic review of the published Jekyll white paper covering BTC
halving cycles and cross-asset correlations (ETH, SOL, XRP, SPX, NDX, DXY,
TLT, MSTR). Reviewed from the perspective of an executive reader whose goal
is to extract a calendar-and-price corridor for the next cycle and decide
whether to act on it.

**Method:** Read every rendered source file (section pages, layouts,
includes, data files, CSS) and assessed against nine UX communication
principles: hierarchy & scannability; trust & epistemic discipline;
cognitive load on the first 30 seconds; accessibility & inclusivity; visual
hierarchy & typography; wayfinding & cross-references; information density
in tables; source-of-truth over-reference; and narrative drift between
roles.

**Status of this document:** Source-of-truth remediation plan. Each finding
is grouped under a remediation increment (R-1 through R-10) with concrete
file/line anchors, severity, and acceptance criteria. Increments are
ordered so each is independently shippable and verifiable. Work them in
order; do not skip R-1 (it unblocks R-2 through R-4).

**Cross-cutting decisions recorded (per author clarification):**
- D-1: Reorder `_sections` weights to match the "Decision spine then
  Appendices" promise. Also fix the stray H1 issue discovered during review.
- D-2: Cowen-memo reconciliation gets a verifiable citation:
  https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026
- D-3: Disclaimer consolidated to 2 locations (abstract blockquote +
  footer one-liner). Other redundant copies removed.
- D-4: Per-asset table kept as one wide table for screen-reader
  linearity. Density addressed via typography, not table splitting.
- D-5: Status freshness surfaced via a GitHub Actions workflow badge
  only. No manual timestamp in `status.md`.

---

## Severity legend

| Tag | Meaning |
|---|---|
| P0 | Accessibility or correctness blocker. Must ship before public release. |
| P1 | Clarity win for the executive reader. Should ship before public release. |
| P2 | Trust and polish. Can ship in a follow-up. |

---

## Remediation increments

| ID | Title | Severity | Files touched (summary) |
|----|-------|----------|--------------------------|
| R-1 | Section ordering & double-H1 hygiene | P1 | `_sections/*.md` weights, `cross-asset-timing.md`, `home.html` sidebar labels |
| R-2 | Accessibility floor (ARIA, color, reduced-motion) | P0 | `home.html`, `style.css`, `now-stamp.html`, `chart.html` |
| R-3 | Now-stamp state machine & banner polish | P1 | `now-stamp.html`, `style.css`, `cycle_status.json` |
| R-4 | Trust & epistemic discipline (disclaimer, citation, freshness) | P1 | `abstract.md`, `provenance-footer.html`, `home.html`, `default.html`, `cycle-anatomy.md`, `memo-reconciliation.md`, `README.md` |
| R-5 | 8-asset per-asset table layout | P1 | `cross-asset-timing.md`, `style.css` |
| R-6 | Provenance footer de-duplication | P2 | `provenance-footer.html`, `chart.html`, section footers |
| R-7 | Confidence-grades table consolidation | P2 | `validation.md`, `predictive-ranges.md` |
| R-8 | `top_character` role clarification | P2 | `cycle-anatomy.md`, `validation.md`, `abstract.md` |
| R-9 | Dead code & stale markers | P2 | `cycle_status.json`, `now-stamp.html` |
| R-10 | Date-format convention documented | P2 | `abstract.md`, `cycle_status.json` |

---

## R-1 — Section ordering & double-H1 hygiene

**Problem.** The home-page table of contents (`index.md`) and the sidebar
(`home.html:20-41`) promise a "Decision spine" reading order:

> Abstract → Prediction → Per-Asset Windows → Confidence & Limits →
> [Appendices] Methodology / Anatomy / Cross-Asset / Release Checklist

The actual rendered order is determined by Jekyll's `weight` front-matter
on each section file. Current weights produce:

> `predictive-ranges` (20) → `cross-asset-timing` (30) → `validation` (40)
> → `cycle-anatomy` (70) → `cross-asset` (80) → `methodology` (90) →
> `release-checklist` (95)

So the reader meets the LOOCO backtest **before** the methodology that
defines it, and meets "Cycle Anatomy" before "Cross-Asset" even though
the sidebar labels them B and C respectively. This violates the
"Decision spine then Appendices" promise documented in `index.md:14-20`.

**Secondary problem.** `cross-asset-timing.md:96` contains a stray
`# Method appendix` H1 in the middle of the document. Combined with the
H1 emitted by `home.html`'s section header, the page renders with two H1s
in sequence, breaking document outline for AT users and visually
demoting the page title.

**Fix (D-1).**

1. Re-weight `_sections` files to match the promised reading order:
   - `predictive-ranges.md` → weight `10`
   - `cross-asset-timing.md` → weight `20`
   - `validation.md` → weight `30`
   - `cycle-anatomy.md` → weight `40`
   - `cross-asset.md` → weight `50`
   - `methodology.md` → weight `60`
   - `release-checklist.md` → weight `70`
2. Update sidebar labels in `home.html:20-41` to match the new weight
   order; keep the "Decision" / "Appendices" / "Project" grouping labels
   but verify group boundaries match the new weights.
3. Demote `cross-asset-timing.md:96` `# Method appendix` to
   `## Method appendix` so it renders as an H2 subsection.

**Verification.**
- `bundle exec jekyll build` succeeds.
- Open `_site/index.html` in a browser: sidebar order matches TOC; no
  two H1s in any section page.
- Run `python -m pytest -q tests/test_jekyll_build.py` — should still be
  green; if it asserts specific section order, update expected order in
  the test to match the new reading order.

---

## R-2 — Accessibility floor (ARIA, color, reduced-motion)

**Problem.** The report clears the accessibility bar in most places but
misses several WCAG 2.1 AA expectations.

**Findings.**

1. **Scrollspy active state is visual-only.** `home.html:121` toggles an
   `.active` CSS class on sidebar nav `<a>` elements but does not set
   `aria-current="true"`. Screen-reader users get no indication of
   current section.
2. **Color-only state encoding in now-stamp.** The colored dot in
   `now-stamp.html` is the only signal for state (`pre` / `outer` /
   `base` / `patience`). Color-blind readers cannot distinguish
   `pre` (red) from `outer` (orange).
3. **`prefers-reduced-motion` is partially respected.** `style.css`
   handles it for `scroll-behavior` but not for the
   `now-stamp-pulse` keyframe (`style.css:430-433`). The pulse continues
   for users who explicitly request reduced motion.
4. **Charts lack `aria-label` on the figure and `<figcaption>` semantics.**
   `chart.html` puts the chart title in an `iframe title` attribute but
   the caption sits as plain text under the figure. Screen readers hear
   the title but miss the caption's structural role.
5. **`<noscript>` fallback for now-stamp is absent.** If JS is disabled,
   the inline SVG is empty; the long ARIA label remains but the visible
   content is blank. Provide a static text fallback summarizing Today /
   Next / Phase.
6. **Footer has no explicit `role="contentinfo"`.** Newer HTML specs
   imply it but legacy AT may not recognize the element; add the role
   for explicitness.

**Fix.**

1. In `home.html:118-125`, add `aria-current="true"` alongside `.active`
   on the active nav link.
2. In `now-stamp.html`, add a textual state badge (e.g. `[PRE]`,
   `[OUTER]`, `[BASE]`, `[PATIENCE]`) immediately beside the colored
   dot, styled to match the dot color but readable independently.
3. In `style.css`, add a `@media (prefers-reduced-motion: reduce)`
   block that sets `animation: none` for `.now-stamp-pulse` and any
   related keyframe-driven elements.
4. In `chart.html`, wrap the caption in `<figcaption>` and add
   `aria-label="<title> — <caption>"` to the `<figure>`.
5. In `now-stamp.html`, wrap the JS-built content in a
   `<noscript>` block containing a static summary sourced from
   `cycle_status.json` values (Today / Next halving / Phase label /
   Next window open date). Keep ARIA label on the SVG for AT users with
   JS enabled.
6. In `provenance-footer.html` (or `default.html` footer element),
   add `role="contentinfo"`.

**Verification.**
- Lighthouse run on `_site/index.html` Accessibility score ≥ 95.
- Manual screen-reader pass (NVDA or VoiceOver): sidebar announces
  "current page" on the active section.
- macOS "Reduce Motion" setting enabled: pulse stops; scrollspy still
  works.
- Disable JS in the browser: now-stamp shows the static fallback text;
  no blank panel.

---

## R-3 — Now-stamp state machine & banner polish

**Problem.** The now-stamp banner is the right concept but several details
erode its usefulness for the executive.

**Findings.**

1. **Banner text uses "Xd since C4 top" parenthetical.** The reader has to
   mentally convert "~295 days since Oct 6 2025" into "we are deep in the
   bear phase." Replace with calendar-relative framing: "post-C4-top
   bear — day N".
2. **One `phaseHint` key is dead.** `cycle_status.json` defines five
   `current_phase_hint` entries. Four are wired in the JS state machine
   (`now-stamp.html:82,95,117,122`): `pre_b4_bear`, `in_b4_window`,
   `in_accumulation`, `exit`. Only `in_distribution` is unreachable —
   the state machine has no branch for the distribution/C5 phase.
   **Correction applied during pre-implementation verification (rev 1.1):
   earlier draft of this review mistakenly claimed 4 of 5 keys were
   dead.** Delete only `in_distribution`.
3. **Sticky banner may cover section titles on expand.** Banner uses
   `position: sticky; top: 0` (`style.css`); section titles use
   `scroll-margin-top: 4rem` (64px). On expanded banner (~240px tall
   including SVG), scrolling to a section anchor may hide the H1 behind
   the banner.

**Fix.**

1. In `now-stamp.html`, change the parenthetical from `(Xd since C4 top)`
   to `post-C4-top bear — day N` (or whatever the current cycle phase
   is, templated by state).
2. Delete the single dead `current_phase_hint` key (`in_distribution`)
   from `cycle_status.json`; keep the 4 wired keys.
3. In `style.css`, adjust `scroll-margin-top` to a CSS variable
   (`--banner-height-expanded`) set to the expanded banner height, and
   apply `scroll-margin-top: var(--banner-height-expanded)` on section
   H2 elements. Test by clicking sidebar links with banner expanded.

**Verification.**
- Banner text reads naturally without mental arithmetic.
- `grep in_distribution _includes/now-stamp.html` returns zero hits.
- `grep in_distribution _data/cycle_status.json` returns zero hits.
- Clicking each sidebar link with the banner fully expanded lands the
  section H2 *below* the banner with visible top margin.

---

## R-4 — Trust & epistemic discipline

**Problem.** The report is unusually disciplined about uncertainty bands
and cross-check status. Two patterns dilute that discipline.

**Findings.**

1. **Disclaimer redundancy.** The "not financial advice" disclaimer
   appears in 5 rendered locations: `abstract.md:7-10` (blockquote,
   canonical), `provenance-footer.html:3` (one-liner "research
   framework, not financial advice"), `provenance-footer.html:16-21`
   (full paragraph disclaimer — a near-duplicate of the abstract
   blockquote), `home.html:46` (sidebar footer one-liner) and
   `default.html:46` (sidebar footer one-liner, identical to
   `home.html`). The full paragraph at `provenance-footer.html:16-21`
   is the duplication problem — it repeats the abstract text nearly
   verbatim. Sidebar footers are already one-liners and acceptable
   as cross-page pointers (per author decision D-R-3, July 2026).
2. **Cowen-memo reconciliation lacks a verifiable citation.**
   `cycle-anatomy.md:108-118` and `docs/memo-reconciliation.md` reference
   "Benjamin Cowen, *Bitcoin Cycle Memo* (July 2026, internal
   research)" — named author + "internal research" with no link is a
   citation anti-pattern. The reader cannot verify; trust erodes.
3. **Status table is "all green" with no freshness signal.** `status.md`
   shows every increment as `done`. With no "last checked" timestamp or
   CI badge, a reader has no way to know whether the greens are current.

**Fix (per D-2, D-3, D-5).**

1. Keep `abstract.md:7` blockquote as the canonical disclaimer. Reduce
   `provenance-footer.html:16-21` (the full paragraph that
   near-duplicates the abstract) to a one-line pointer: "Not financial
   advice — see [Abstract](/abstract/#disclaimer) for full text."
   Leave `provenance-footer.html:3` (one-liner "research framework, not
   financial advice") and `home.html:46` / `default.html:46` sidebar
   footers as-is — they're already one-liners (per author decision
   D-R-3, July 2026).
2. In `cycle-anatomy.md:108-118`, replace "Benjamin Cowen, *Bitcoin
   Cycle Memo* (July 2026, internal research)" with a clickable
   citation: "[Cowen, *Bitcoin Cycle Memo* (July
   2026)](https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026)".
   Apply the same change to `docs/memo-reconciliation.md:38-40` and
   `docs/open-questions.md:37-39`.
   - Optionally also update the prose in `cycle-anatomy.md:108-118` so
     it doesn't say "internal research" — that phrasing contradicts a
     public URL. Rephrase to "an independent July-2026 analysis".
3. Add a GitHub Actions workflow badge to `status.md` near the top of
   the table, e.g.:
   `[![CI](https://github.com/<org>/<repo>/actions/workflows/deploy.yml/badge.svg)](https://github.com/<org>/<repo>/actions/workflows/deploy.yml)`
   - Use the actual `org`/`repo` once the GitHub remote is configured
     (currently the repo has no remote; placeholder acceptable until
     then, with a TODO comment).
   - Do NOT add a manual timestamp field to `status.md` (per D-5).

**Verification.**
- `grep -r "not financial advice" _site/` returns exactly 4 hits:
  1 full blockquote on `abstract/index.html`, 1 one-liner in
  `provenance-footer.html:3` (rendered site-wide), 2 one-liners in
  `home.html:46` and `default.html:46` sidebar footers (rendered
  per-page), and 1 one-line pointer at `provenance-footer.html:16-21`
  (replaced paragraph). The 5→4 reduction is the full paragraph at
  `provenance-footer.html:16-21` becoming a single line.
- Clicking the Cowen citation opens
  https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026 in a
  browser.
- `status.md` shows the badge image; if the workflow hasn't run yet,
  the badge reads "no status" — that's still better than a missing
  signal.

---

## R-5 — 8-asset per-asset table layout

**Problem.** The 8-asset per-asset table in `cross-asset-timing.md:34-41`
is the densest table on the page. Asymmetric column count (5 cols vs
the BTC table's also 5 cols) and cell content with stacked
price-band / window / cross-check / method leaves the executive scanning
in a different mode than the BTC table just above it.

**Fix (per D-4: keep one wide table).**

1. Reduce the table's `font-size` to `0.85rem` (locally scoped; do
   not touch the global `0.9rem`). Add a CSS class
   `.table-dense` on this table and scope the rule:
   ```css
   .table-dense { font-size: 0.85rem; }
   .table-dense td, .table-dense th { padding: 0.35rem 0.5rem; }
   ```
2. Move "Cross-check" and "Method" columns into a footnote below the
   table — they are per-asset metadata, not decision input. Replace
   those two columns with a single `Notes` column that links to a
   keyed footnote (`¹`, `²`, …) below the table where cross-check and
   method are expanded.
3. Add a `caption` element above the table summarizing its scope: "B4
   and C5 windows for 8 assets. Notes column keys to the footnote
   below; band and center prices in USD."

**Verification.**
- Table still reads top-to-bottom in a screen reader; row content is
  linear.
- The asymmetry with the BTC table is reduced — both tables now have 4
  visible columns (Asset / B4 corridor / C5 corridor / Notes для this
  one; Zone / Window / Price band / Decision rule for the other).
- No horizontal scroll at 1200px viewport.

---

## R-6 — Provenance footer de-duplication

**Problem.** The discipline of showing "where this number comes from" is
excellent; the *display* of it is over-rotated. The site-wide footer
in `provenance-footer.html:5-8` carries a generic "Data provenance:
`data/raw/manifest.txt`" line that duplicates the more specific CSV
trail published in each section file's own footer. The site-wide line
adds no information the section footers don't already cover.

**Correction applied during pre-implementation verification (rev 1.1):
earlier draft of this review mistakenly claimed `chart.html` had a
per-chart "Data:" label. It does not — `chart.html` only renders
`<div class="chart-caption">{{ include.caption }}</div>`. The actual
redundancy is site-wide footer vs. per-section footer.**

**Fix (P2 — can ship in a follow-up). Per author decision D-R-6
(July 2026): keep per-section footers, remove the site-wide line.**

1. Keep the per-section provenance footer lines (one per section is
   fine — they name the specific CSV(s) for that section).
2. Remove the "Site built … Data provenance: `data/raw/manifest.txt`"
   meta line from `provenance-footer.html:5-8`. Keep the "Site built
   `<timestamp>`" half only if a build-time freshness signal is
   desired; otherwise drop the entire `meta` div at lines 5-8.
3. **Decision (D-R-6): keep per-section, remove site-wide.** The
   section files are the source of truth for their own data trail; the
   generic site-footer line carries no information that the section
   footers don't already cover, more specifically.

**Verification.**
- `grep -c "Data provenance" _site/` returns one hit per section page
  (the per-section footer; unchanged).
- `grep "manifest.txt" _site/index.html` returns zero hits in the
  site-wide footer block (the only `manifest.txt` references are inside
  per-section footer blocks).

---

---

## R-7 — Confidence-grades table consolidation

**Problem.** `validation.md:21-26` reprints the cross-check status that
already appears in `predictive-ranges.md` and `cross-asset-timing.md`.
The duplication invites drift if one is updated and the other isn't.

**Fix (P2).**

1. Remove the "Cross-check" column from `validation.md:21-26`. Replace
   with a one-line note above the table: "Cross-check status per zone
   is published inline on the [Predictive
   Ranges](/predictive-ranges/#cross-check) and [Per-Asset
   Windows](/cross-asset-timing/#per-asset-table) pages."
2. Keep the Confidence-grades table's other columns (Layer, Band,
   Method, LOOCO error, Regime robustness). These are unique to
   `validation.md`.
3. Update the surrounding prose in `validation.md:19-21` to reference
   the cross-check disclosure on the source pages rather than
   reproducing it.

**Verification.**
- The cross-check PASS/FAIL strings appear in exactly 2 places: the
  BTC predictive-ranges section and the per-asset section. Nowhere
  else.
- The validation page still tells a coherent story without the
  duplicated column.

---

## R-8 — `top_character` role clarification

**Problem.** The three-role taxonomy says `top_character` is a *decision
overlay* (`cycle-anatomy.md:69-79`). But `validation.md:23` uses
`top_character` ("apathetic") as the **reason** the B4 cross-check FAIL
confidence is downgraded — i.e. as a model-input adjuster in disguise.
The role label and the empirical usage disagree.

**Fix (P2). Either path is acceptable; pick one and document.**

- **Path A (recommended): Make `top_character` a first-class model-input
  modifier.** Add a fourth role label `model input modifier` and apply
  it to `top_character` in `cycle-anatomy.md:69-79`. Document that
  `top_character` widens the cross-check band tolerance when its value
  is `apathetic`. Update `abstract.md` role-label paragraph to mention
  the fourth role.
- **Path B: Remove the band-widening reasoning from `validation.md`.**
  Keep `top_character` as a pure decision overlay explaining *why* the
  top looked the way it did; do not let it influence the published
  confidence grade. The cross-check FAIL stands on its own without the
  apathetic-top reasoning.

**Recommended:** Path A. The reasoning is real; the labeling is the
problem. Adding a fourth role name is cleaner than removing real
analytical content.

**Verification.**
- Either `abstract.md` mentions 4 roles (Path A) or `validation.md:23`
  no longer references `top_character` (Path B).
- Whichever path is chosen, the role label and the empirical usage
  agree.

---

## R-9 — Dead code & stale markers

**Problem.** Several bits of dead code and stale content signal
"unfinished" to a careful reader.

**Findings.**

1. **One dead `current_phase_hint` key in `cycle_status.json`.**
   Verified during pre-implementation read: only `in_distribution` is
   unreferenced in `now-stamp.html`. The other 4 keys (`pre_b4_bear`,
   `in_b4_window`, `in_accumulation`, `exit`) ARE wired at lines
   82/95/117/122. Delete `in_distribution` only.
2. **`README.md:25` says `https://<user>.github.io/trading/`.** Placeholder
   URL not yet replaced. Once the GitHub remote is configured, replace
   with the actual URL. Until then, mark it explicitly as a placeholder:
   `<!-- TODO: replace with published Pages URL once remote is configured -->`
   above the line.
3. **Stale "added 2026-07-23" parenthetical in `cycle-anatomy.md:128`.**
   Reads like a CHANGELOG entry embedded in narrative prose. Either
   move to a `## Change log` section at the bottom of
   `cycle-anatomy.md`, or remove the parenthetical (the
   reconciliation content itself stays).

**Fix (P2).**

1. Delete the single dead `in_distribution` key from `_data/cycle_status.json`.
   Verify `now-stamp.html` makes no reference to it (already confirmed
   during R-1 pre-implementation read; keep that grep assertion in the
   verification block below).
2. Add the TODO comment above the placeholder URL in `README.md:25`.
3. Remove the `(added 2026-07-23)` parenthetical from
   `cycle-anatomy.md:128` and either move the whole
   "Folklore pattern reconciliation" subsection to a `## Change log`
   H2 at the bottom of the same page, or accept it as evergreen content
   and drop the date marker.

**Verification.**
- `grep in_distribution _data/cycle_status.json` returns zero hits.
- `grep in_distribution _includes/now-stamp.html` returns zero hits.
- `grep "added 202" _sections/` returns zero hits (no inline date
  markers anywhere in section prose).
- `grep "<user>" README.md` returns zero (placeholder commented out).

---

## R-10 — Date-format convention documented

**Problem.** Dates appear in two formats across the report:
`YYYY-MM-DD` in tables and `Mon YYYY` in the now-stamp banner. The
convention is consistent in practice but not documented anywhere. A
new contributor or a careful reader might not pick up the pattern.

**Fix (P2).**

1. Add a one-paragraph note to `abstract.md` near the existing "How to
   read this report" block:
   > **Date format convention.** Tabular data uses ISO `YYYY-MM-DD`.
   > The sticky banner at the top of each page uses `Mon YYYY` for
   > brevity. Both refer to the same calendar dates; cross-references
   > resolve to the day, not the month.
2. Audit all `_sections/*.md` for any date not in this convention
   (e.g. `Oct 6, 2025` in `memo-reconciliation.md` is acceptable for
   narrative prose but should be `2025-10-06` if it appears in a
   table).

**Verification.**
- `abstract.md` contains a "Date format convention" paragraph.
- All table cells containing dates use `YYYY-MM-DD`. A grep for
  `[A-Z][a-z][a-z] [0-9]` inside `<table>` blocks returns zero hits.

---

## Out of scope for this review

The following were considered but judged out of scope or unnecessary:

- **CSS refactor.** The 603-line stylesheet is dense but coherent.
  Splitting it would not improve the executive reader's experience.
- **Jekyll theme change.** The custom layout is small and
  understandable; switching to a theme adds dependencies without
  reader benefit.
- **Translation.** English-only is fine for the current audience.
- **Adding new charts.** Chart coverage is already dense; the
  executive reader is better served by reducing density, not adding to
  it.
- **Mobile-specific layout work.** Responsive breakpoints exist
  (`style.css` media queries at 1024px and 768px). Specific mobile
  UX improvements should wait for actual mobile traffic data.

---

## Sequencing recommendation

The increments are written so each can ship as one PR. Recommended order
with suggested PR grouping:

- **PR-1 = R-1 + R-9** (section ordering, H1 hygiene, dead `phaseHint`
  cleanup, TODO markers). Smallest blast radius; unblocks subsequent
  visual fixes.
- **PR-2 = R-2 + R-3** (accessibility floor + now-stamp state machine +
  banner scroll-margin). Both touch `now-stamp.html` and `style.css`;
  ship together to avoid merge conflicts.
- **PR-3 = R-4** (disclaimer consolidation + Cowen citation + CI badge).
  Mostly prose edits; independent of layout work.
- **PR-4 = R-5** (per-asset table density; scoped CSS, no other file
  touched).
- **PR-5 = R-6 + R-7** (provenance de-dup + confidence-grade table
  consolidation). Both reduce redundancy; ship together.
- **PR-6 = R-8** (role-label taxonomy decision; isolated to two files
  but conceptually weighty — keep separate so it's easy to revert if
  the author prefers Path B over Path A).
- **PR-7 = R-10** (date-format convention; lowest-risk documentation
  pass; ship last).

Each PR should keep the corresponding `tests/test_*.py` gate green and
pass `bundle exec jekyll build` before merge.

---

*End of review. Source files referenced are accurate as of session
read; line numbers may drift slightly if sections are edited before this
document is consulted.*

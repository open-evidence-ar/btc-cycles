# Data Integrity Audit Report

**Date:** 2026-08-06  
**Scope:** All `data/processed/*.csv`, `data/events.csv`, key scripts  
**Auditor:** Sub-agent 2 (MiMo V2.5)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 4 |
| LOW | 1 |
| **Total** | **7** |

---

## HIGH Findings

### H-1: Rolling correlation value outside [-1, 1]

| Field | Value |
|-------|-------|
| File | `data/processed/correlations_rolling.csv` |
| Location | `cycle_id=C4, asset=eth, date=2026-11-02` |
| Observed | `rolling_r_90d = -1.0000000000239684` |
| Expected | `[-1, 1]` |
| Note | Floating-point precision artifact (deviation = 2.4e-11). Technically violates the mathematical constraint. Likely caused by near-perfect collinearity in the 90-day window for ETH on that date. **Recommendation:** Clip or clamp to [-1, 1] in the correlation script. |

### H-2: Gold C1 multiplier < 1

| Field | Value |
|-------|-------|
| File | `data/processed/alt_cycle_metrics.csv` |
| Location | `asset=gold, cycle_id=C1` |
| Observed | `mult_asset_bottom_to_top = 0.9584` (top $1,420.60 < bottom $1,482.30) |
| Expected | `> 1` (top should exceed bottom for a bull cycle) |
| Note | Gold's C1 local top (2013-08-27, $1,420.60) was detected lower than the C1 bottom (2011-07-01, $1,482.30). This is because gold's actual peak (~$1,900, Sept 2011) occurred *before* the BTC C1 halving window, so the extrema detector found the highest point *within* the halving window, which was already in decline. This feeds a mult < 1 into gold's own shape series for 2-stage projection, which could produce unreliable zone estimates. **Recommendation:** Consider whether gold's extrema should use gold-specific cycle boundaries rather than BTC halving dates, or flag the C1 multiplier as unreliable in the projection pipeline. |

---

## MEDIUM Findings

### M-1: Missing columns vs DESIGN.md §5.1

| Field | Value |
|-------|-------|
| File | `data/processed/btc_cycle_metrics.csv` |
| Missing | `D_halving_to_next_bottom`, `mult_top_to_bottom` |
| Expected | Columns promised by DESIGN.md §5.1 |
| Note | These columns would complete the cycle metrics schema. Currently absent from the CSV header. |

### M-2: No B4 entry in folklore_reconciliation.csv

| Field | Value |
|-------|-------|
| File | `data/processed/folklore_reconciliation.csv` |
| Missing | Entry for BTC projected B4 (`chart_annotation` containing "B4") |
| Expected | At minimum, a row acknowledging the B4 projection exists and its cross-check status |
| Note | The folklore reconciliation has stubs for TOP_ZONE and BOTTOM_ZONE but no B4 row. Since B4 is a first-class zone (DESIGN.md §9.4), a folklore cross-check entry would complete the narrative. |

### M-3: Gold B4 anchor above support band

| Field | Value |
|-------|-------|
| File | `data/processed/alt_next_cycle_zones.csv` |
| Location | `asset=gold, zone=bear_bottom` |
| Observed | `anchor_price=4998.01`, `support_band_high=3829.66`, `price_high=4786.56` |
| Expected | B4 anchor near or within the support band (~$3,813–$3,830) |
| Note | The 2-stage drawdown-projected B4 ($4,998) is significantly above the 20-mo SMA / 21-mo EMA bull-support band ($3,813–$3,830). The `cross_check_ok` field is empty, suggesting the cross-check was not run or not populated. This weakens the gold B4 estimate. |

### M-4: Alt next_cycle_zones cross_check_ok not populated

| Field | Value |
|-------|-------|
| File | `data/processed/alt_next_cycle_zones.csv` |
| Location | Multiple assets (eth bear_bottom, gold bear_bottom, others) |
| Observed | `cross_check_ok` is empty or None |
| Expected | Populated with True/False |
| Note | For BTC, cross_check_ok is populated (True/False). For alts, most values are empty, making it impossible to assess whether the cross-check was performed or failed silently. |

---

## LOW Findings

### L-1: H5 halving date flagged as future (by design)

| Field | Value |
|-------|-------|
| File | `data/events.csv` |
| Location | `halving/H5/date = 2028-04-01` |
| Observed | Date is in the future (today is 2026-08-06) |
| Expected | N/A |
| Note | **Not a defect.** This is a documented projection (`reason_code=projected`), not an error. Flagged by automated check; included here for completeness only. |

---

## No Findings (Verified Clean)

| Check | Result |
|-------|--------|
| `events.csv` date integrity | All halvings chronological. All tops after their halvings. No dates outside [2010-07-17, today+projected]. |
| `btc_cycle_metrics` date ordering | All pre_halving_bottom < halving < final_top. C4 has no next_bear_bottom (correct — still open). |
| `btc_cycle_metrics` drawdown_pct | All values in [0, 1]. |
| `forward_ranges` LOOCO (BTC) | Verified C1–C4 leave-one-out means are mathematically correct. |
| `forward_ranges` min/mean/median/max ordering | All min ≤ mean/median ≤ max. |
| `correlations_phase` pearson/spearman | All 40 values in [-1, 1]. |
| `next_cycle_zones` B4 in band | BTC B4 ($43,081) is within band [$29,596, $53,673]. |
| `next_cycle_zones` cross-check | bear_bottom FAIL at +45.6% confirmed (matches AGENTS.md). |
| BTC 2-stage projection values | B4=$43,081, band=$29.6k–$53.7k — matches AGENTS.md exactly. |
| Stale snapshot check | All derived files have git dates >= their dependencies. No staleness. |
| `btc_cycle_metrics` price mismatch vs `events.csv` | C2/C3 date/price discrepancies are documented Rule T differences (Bitstamp raw vs CoinGecko). Known, not a new defect. |

---

## Recommendations

1. **H-1 (rolling corr):** Add `np.clip(r, -1, 1)` after correlation computation.
2. **H-2 (gold C1):** Evaluate whether gold extrema should use gold-specific cycle boundaries. Flag C1 multiplier as unreliable in projection code.
3. **M-1 (missing columns):** Add `D_halving_to_next_bottom` and `mult_top_to_bottom` to `build_cycle_metrics.py` output.
4. **M-2 (B4 folklore):** Add a B4 row to `folklore_reconciliation.csv` with cross-check status.
5. **M-3/M-4 (gold B4 + alt cross_check):** Populate `cross_check_ok` for all alt zones. Review gold B4 anchor relative to support band.

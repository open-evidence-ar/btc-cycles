import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import json
import math
import time
from datetime import timedelta

CHARTS_DIR = (Path(__file__).resolve().parent.parent / 'assets' / 'charts')
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_write_html(fig, path, retries=12, delay=0.3, **kwargs):
    """write_html with retry on Windows OSError [Errno 22]/[Errno 13].

    Plotly's write_html can sporadically hit OSError when the parent
    process is a subprocess (Kaleido Chromium leaving stale handles, or
    concurrent PNG writes racing the HTML write). On Windows the errno
    may also surface as None when Plotly re-raises the io.open exception,
    so we retry on *any* OSError up to `retries`; a persistent failure
    (real permission issue) will simply exhaust retries and re-raise.
    Retries with a small backoff let the OS release the handle.

    Auto-height post-pass: every chart is written as a *fluid* document so
    the iframe height (driven by CSS in style.css) is the single sizing
    authority on all viewports. We strip the figure's fixed `"height":N`
    from the layout JSON and make the wrapper/plotly-graph-div height:100%.
    Plotly's `responsive: True` then refits the SVG to whatever box the
    iframe gives it, so narrow portrait charts swipe and short landscape
    windows never overflow.
    """
    import random
    import re
    last_err = None
    for attempt in range(retries):
        try:
            fig.write_html(path, **kwargs)
            _autoheight_html(path)
            return
        except (OSError, IOError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1) + random.uniform(0, 0.1))
                continue
            raise
    if last_err:
        raise last_err


def _autoheight_html(path):
    """Post-process a freshly-written Plotly HTML doc to fluid height.

    - `<div style="height:<N>px; width:100%;">`  ->  height:100%
    - plotly-graph-div inline height            ->  height:100%
    - layout JSON `,"height":N}`                 ->  `}`  (last layout key)
    """
    import re
    from pathlib import Path
    p = Path(path)
    c = p.read_text(encoding='utf-8', errors='replace')
    c = re.sub(r'<div style="height:\d+px; width:100%;">',
               '<div style="height:100%;width:100%;">', c, count=1)
    c = re.sub(r'(class="plotly-graph-div" style=")height:\d+px; ',
               r'\1height:100%; ', c, count=1)
    c = re.sub(r'<div style="height:\d+px; width:100%;">',
               '<div style="height:100%;width:100%;">', c, count=1)
    c = re.sub(r'(class="plotly-graph-div" style=")height:\d+px; ',
               r'\1height:100%; ', c, count=1)
    c = re.sub(r',"height":\d+,', ',', c)      # mid-layout height key
    c = re.sub(r',"height":\d+}', '}', c, count=1)  # height last layout key
    c = re.sub(r'\{"height":\d+,', '{', c)     # height first layout key
    if '<style>html,body' not in c:
        c = c.replace('</head>',
                      '<style>html,body{height:100%;margin:0;padding:0}</style></head>')
    p.write_text(c, encoding='utf-8')


def _safe_write_image(fig, path, retries=12, delay=0.3, **kwargs):
    """write_image with retry on Windows OSError [Errno 22] (Kaleido Chromium race)."""
    import random
    last_err = None
    for attempt in range(retries):
        try:
            fig.write_image(path, **kwargs)
            return
        except (OSError, IOError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1) + random.uniform(0, 0.1))
                continue
            raise
    if last_err:
        raise last_err


def log_to_usd_ticks(log_min, log_max, num_ticks=8):
    """Generate y-axis tick positions and $-formatted labels within the given log range."""
    lo = np.exp(log_min)
    hi = np.exp(log_max)
    log_lo = np.log10(lo)
    log_hi = np.log10(hi)
    prices = np.logspace(log_lo, log_hi, num=num_ticks)
    def fmt(p):
        if p >= 1e6:
            return f'${p/1e6:.1f}M'
        if p >= 1e5:
            return f'${p/1e3:.0f}k'
        if p >= 1e3:
            return f'${p/1e3:.1f}k'
        if p >= 100:
            return f'${p:,.0f}'
        if p >= 1:
            return f'${p:,.2f}'
        return f'${p:.2f}'
    return dict(
        tickvals=[float(p) for p in prices],
        ticktext=[fmt(p) for p in prices],
    )


def _to_float(v):
    """Coerce a pandas cell / numpy value to float, returning None on NaN/failure."""
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Load all data sources
events = pd.read_csv('data/events.csv')
events['date'] = pd.to_datetime(events['date'], errors='coerce')


def _load_h5_date():
    """Load H5 (next halving) date from events.csv (canonical source).

    Falls back to 2028-04-01 if H5 not found in events.csv.
    """
    h5_row = events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H5')]
    if not h5_row.empty:
        return pd.to_datetime(h5_row.iloc[0]['date'])
    return pd.to_datetime("2028-04-01")  # fallback


H5_DATE = _load_h5_date()

metrics = pd.read_csv('data/processed/btc_cycle_metrics.csv')
btc = pd.read_csv('data/raw/btc_bitstamp_2026-07-20.csv', parse_dates=['date'])
corr_phase = pd.read_csv('data/processed/correlations_phase.csv')
corr_rolling = pd.read_csv('data/processed/correlations_rolling.csv')
fwd = pd.read_csv('data/processed/forward_ranges.csv')
zones = pd.read_csv('data/processed/next_cycle_zones.csv')
backtest = pd.read_csv('data/processed/backtest_by_cycle.csv')
# I-18a SMA floors
sma_floors_path = Path('data/processed/btc_sma_floors.csv')
if sma_floors_path.is_file():
    sma_floors = pd.read_csv(sma_floors_path, dtype={'date': str})
else:
    sma_floors = None

# I-17 per-asset artifacts
alt_metrics = pd.read_csv('data/processed/alt_cycle_metrics.csv', keep_default_na=False)
alt_zones = pd.read_csv('data/processed/alt_next_cycle_zones.csv', keep_default_na=False)

def fit_cycle_compression(values, cycle_indices, project_to_idx, floor=2.0):
    """Fit **power-law decay** to per-cycle multipliers / drawdowns:

        value_n = a * cycle_idx^b       (b < 0 for compression)

    Economic motivation: BTC is *disflationary* — each successive halving
    cycle's bottom-to-top multiplier compresses by a roughly constant
    **ratio** as the asset's market cap grows. A geometric (constant-ratio)
    decay is modelled exactly by a power law on log-log axes:

        log(value) = log(a) + b * log(cycle_idx)        (b < 0)

    Long-term uptrend is preserved because the anchor price (B3 etc.) keeps
    growing even as the *multiplier* shrinks, so the projected USD top still
    rises cycle-over-cycle.

    `floor` is retained for API backward-compat as a sanity lower bound: the
    projected_value is floored at `floor` so we never publish a multiplier
    below the mature-asset minimum (default 2.0x for multipliers, 0.50 for
    drawdowns). The power-law fit itself does NOT use the floor.

    Band construction:
      - Center: projected_value
      - Low  / High: projected_value * exp(∓ log_residual_std)
      - Capped so that the band never exceeds [naive_min, naive_max]
        of the historical observations (avoids publishing a band wider
        than the empirical envelope, which would mean the fit adds
        no information).
      - Floor sanity: band_low floored at `floor` for mult fits (so the
        lower edge of a TOP band is never below the mature-asset minimum).

    Returns dict with:
      n, used ('power_law_fit' or 'median_fallback'),
      projected_value, band_low, band_high,
      fit_a, fit_b (the power-law coefficients),
      fit_floor, r_squared, slope_t_stat, log_residual_std,
      fallback_reason.
    """
    vals = np.array(values, dtype=float)
    idxs = np.array(cycle_indices, dtype=float)
    mask = ~np.isnan(vals) & (vals > 0)
    vals = vals[mask]
    idxs = idxs[mask]
    n = len(vals)

    naive_median = float(np.median(vals)) if n > 0 else float('nan')
    naive_min = float(np.min(vals)) if n > 0 else float('nan')
    naive_max = float(np.max(vals)) if n > 0 else float('nan')

    out = {
        'n': int(n),
        'used': 'median_fallback',
        'projected_value': naive_median,
        'band_low': naive_min,
        'band_high': naive_max,
        'r_squared': None,
        'slope_t_stat': None,
        'fit_floor': float(floor),
        'fit_a': None,
        'fit_b': None,
        'log_residual_std': None,
        'fallback_reason': '',
    }

    if n < 3:
        out['fallback_reason'] = f'n={n} < 3'
        return out

    # --- Power-law fit on log-log axes ---
    log_vals = np.log(vals)
    log_idxs = np.log(idxs)

    # 2-parameter OLS: log(value) = log(a) + b * log(idx)
    # polyfit returns highest-power-first: [b, log(a)]
    coef = np.polyfit(log_idxs, log_vals, 1)
    b_hat = float(coef[0])
    log_a_hat = float(coef[1])
    a_hat = float(np.exp(log_a_hat))

    preds_log = log_a_hat + b_hat * log_idxs
    ss_res = float(np.sum((log_vals - preds_log) ** 2))
    ss_tot = float(np.sum((log_vals - log_vals.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # t-test on the slope b: H0: b = 0 (no compression / no trend).
    df_resid = n - 2  # 2-parameter fit
    if df_resid > 0 and ss_res > 0:
        mse = ss_res / df_resid
        s_xx = float(np.sum((log_idxs - log_idxs.mean()) ** 2))
        se_b = float(np.sqrt(mse / s_xx)) if s_xx > 0 else float('nan')
        t_stat = b_hat / se_b if se_b > 0 else float('nan')
        # One-sided a=0.20 critical values of student-t (small df_resid):
        #   df_resid=1 -> 1.376, 2 -> 1.061, 3 -> 0.978, 4 -> 0.941, 5 -> 0.920
        t_crit_table = {1: 1.376, 2: 1.061, 3: 0.978, 4: 0.941, 5: 0.920}
        t_crit = t_crit_table.get(df_resid, 1.0)
        # For "compression" we want b < 0 and statistically significant.
        # Use one-sided |t| >= t_crit (the sign is enforced by b_hat).
        slope_significant = bool(abs(t_stat) >= t_crit and b_hat < 0)
    else:
        t_stat = float('nan')
        slope_significant = False

    log_resid_std = float(np.sqrt(ss_res / df_resid)) if df_resid > 0 else 0.0

    out['r_squared'] = float(r2)
    out['slope_t_stat'] = float(t_stat)
    out['fit_a'] = a_hat
    out['fit_b'] = b_hat
    out['log_residual_std'] = log_resid_std

    if slope_significant and r2 >= 0.0:
        projected_val = a_hat * (float(project_to_idx) ** b_hat)
        # Soft economic floor: the multiplier / drawdown does not decay below
        # this value (mature assets still multiply off the bottom, etc.).
        # Default 2.0 for speculative assets (BTC, ETH); caller passes
        # 1.0 for macro / near-constant series so the fit is uninformed by
        # a floor that contradicts the data.
        projected_val = max(projected_val, float(floor))
        projected_log = np.log(projected_val)
        # Statistical prediction interval on the log scale: residual std of
        # the fit, propagated symmetrically around the projection.
        #
        # The fit is statistically significant (slope t-test passes one-sided
        # alpha=0.20) and R^2 >= 0, so we trust the model's extrapolation
        # including trend continuation past the last observed cycle.
        band_low_fit = float(np.exp(projected_log - log_resid_std))
        band_high_fit = float(np.exp(projected_log + log_resid_std))
        # Defensive sanity: ensure non-inverted band and lower-edge floored
        # at the same value that floors the projection.
        band_low = max(band_low_fit, float(floor))
        band_high = max(band_high_fit, band_low)
        out['projected_value'] = float(projected_val)
        out['band_low'] = band_low
        out['band_high'] = band_high
        out['used'] = 'power_law_fit'
    else:
        if not (b_hat < 0):
            out['fallback_reason'] = (
                f'slope b={b_hat:.3f} >= 0 (no compression detected); '
                f't={t_stat:.2f}'
            )
        elif r2 < 0.0:
            out['fallback_reason'] = (
                f'R^2={r2:.2f} < 0 (fit worse than mean); '
                f't={t_stat:.2f}'
            )
        else:
            out['fallback_reason'] = (
                f'slope t={t_stat:.2f} below one-sided a=0.20 crit '
                f'(df_resid={df_resid}, t_crit~{t_crit:.2f})'
            )
        # Median fallback retained (projected_value, band_low, band_high
        # were already set to naive stats above).
    return out


def project_bear_bottom(bear_bottom_prices, project_idx, floor_ratio=1.0):
    """Stage 1 of the 2-stage cycle projection model.

    Fit a power-law decay to the **bear-bottom-to-bear-bottom price
    appreciation ratio** series and project forward to `project_idx`.

    Economic premise: BTC's successive bear-market lows rise by a ratio that
    itself compresses over time as the asset's market cap grows. The observed
    ratios for BTC: B1/B0 = 79.5x, B2/B1 = 18.3x, B3/B2 = 5.0x, decay as a
    power law in idx. Projecting idx=4 yields the next bear-bottom multiple
    B4/B3; multiplying by B3 gives the projected B4 USD price.

    Inputs:
      bear_bottom_prices: ordered list of bear-bottom USD prices
                          [B0, B1, ..., Bn-1] (n >= 3 required).
      project_idx:        the index of the bottom to project (i.e. for B_n,
                        call with project_idx = n+1, since ratios live at
                        indices 1..n-1).
                        Example: with [B0,B1,B2,B3] (4 prices -> 3 ratios),
                        project_idx=4 projects the B4/B3 ratio.
      floor_ratio:        economic lower bound on the projected ratio.
                        Default 1.0x means "bear bottom does not fall below
                        the prior bear bottom" (deflation-safe prior). For
                        speculative assets a 1.5x floor may be more apt; for
                        macros whose bottom prices barely move, 1.0x is fine.

    Returns:
      dict with:
        n                -- number of ratios used in the fit
        used             -- 'power_law_fit' or 'naive_fallback'
        projected_ratio  -- projected B_n+1 / B_n ratio
        ratio_band_low   -- lower edge of the ratio band (projected * exp(-std))
        ratio_band_high  -- upper edge of the ratio band (projected * exp(+std))
        projected_price  -- projected_ratio * last observed price
        price_band_low   -- ratio_band_low * last observed price
        price_band_high  -- ratio_band_high * last observed price
        fit_a, fit_b     -- power-law coefficients ratio_n = a * idx^b
        r_squared        -- R^2 of the log-log fit
        slope_t_stat     -- t-stat on the fitted slope b
        log_residual_std -- residual std in log-space
        fallback_reason  -- when fit fails
    """
    prices = np.array(bear_bottom_prices, dtype=float)
    prices = prices[~np.isnan(prices) & (prices > 0)]
    n_prices = len(prices)
    if n_prices < 4:
        # Need at least 3 ratios to fit meaningfully, i.e. 4 prices.
        last = float(prices[-1]) if n_prices > 0 else float('nan')
        return {
            'n': n_prices - 1,
            'used': 'naive_fallback',
            'projected_ratio': float('nan'),
            'ratio_band_low': float('nan'),
            'ratio_band_high': float('nan'),
            'projected_price': float('nan'),
            'price_band_low': float('nan'),
            'price_band_high': float('nan'),
            'fit_a': None,
            'fit_b': None,
            'r_squared': None,
            'slope_t_stat': None,
            'log_residual_std': None,
            'fallback_reason': f'need >= 4 bear bottoms for fit, got {n_prices}',
            'last_observed_price': last,
        }

    # Ratios: r_n = B_n / B_{n-1}, indexed 1..n_prices-1
    idxs = np.arange(1, n_prices, dtype=float)
    ratios = prices[1:] / prices[:-1]
    n = len(ratios)
    last_price = float(prices[-1])

    # Repurpose the power-law fit function on ratios
    fit = fit_cycle_compression(
        ratios.tolist(),
        cycle_indices=idxs.tolist(),
        project_to_idx=project_idx,
        floor=floor_ratio,
    )

    out = {
        'n': fit['n'],
        'used': fit['used'],
        'projected_ratio': fit['projected_value'],
        'ratio_band_low': fit['band_low'],
        'ratio_band_high': fit['band_high'],
        'projected_price': fit['projected_value'] * last_price,
        'price_band_low': max(fit['band_low'] * last_price, floor_ratio * last_price),
        'price_band_high': fit['band_high'] * last_price,
        'fit_a': fit['fit_a'],
        'fit_b': fit['fit_b'],
        'r_squared': fit['r_squared'],
        'slope_t_stat': fit['slope_t_stat'],
        'log_residual_std': fit['log_residual_std'],
        'fallback_reason': fit['fallback_reason'],
        'last_observed_price': last_price,
    }
    return out


def two_stage_cycle_projection(bear_bottom_prices, multipliers, drawdowns,
                               project_to_c4=True):
    """End-to-end 2-stage projection of the cycle chain.

    Stage 1: project B4 from bottom-price ratio series  -> projected B4 USD
    Stage 2a: project C4 top from B3 * mult_n (idx=4)  -> C4 top USD
              (only if project_to_c4 is True)
    Stage 2b: project C5 top from B4 * mult_n (idx=5)  -> C5 top USD
    Cross-check (Stage 2 via drawdown): B4_check = C4_top * (1 - dd_n(idx=4)).
    Disagreement >15% between Stage 1 and Stage 2 cross-check triggers the
    flag `cross_check_ok = False`.

    Inputs:
      bear_bottom_prices: [B0, B1, B2, B3] (must have >= 4 prices)
      multipliers:        [m1, m2, m3]     (B0->C1, B1->C2, B2->C3)
      drawdowns:          [d1, d2, d3]     (1 - B_next/C_top per cycle)

    Returns:
      dict with keys:
        stage1_b4            -- projected B4 USD (price_band_low/high too)
        stage2_c4_top        -- projected C4 top USD (Stage 2a)
        stage2_c4_dd         -- projected C4 drawdown fraction
        stage2_b4_cross_check-- B4 estimated via C4_top * (1 - dd) path
        stage2_c5_top        -- projected C5 top USD (Stage 2b)
        cross_check_ok      -- True if Stage1 B4 vs Stage2 B4 within 15%
        cross_check_rel_diff-- the relative disagreement (signed)
        b4_band_low, b4_band_high -- intersection of the two B4 estimates
        ...
    """
    stage1 = project_bear_bottom(bear_bottom_prices, project_idx=4, floor_ratio=1.0)
    if not math.isfinite(stage1['projected_price']):
        return {
            'available': False,
            'stage1': stage1,
            'reason': 'Stage 1 failed: ' + stage1.get('fallback_reason', ''),
        }

    # Stage 2: multiplier power-law fit (idx 1..n -> project to 4 and 5)
    mult_fit = fit_cycle_compression(
        multipliers,
        cycle_indices=list(range(1, len(multipliers) + 1)),
        project_to_idx=5,  # we'll read idx=4 and idx=5 from the fit_a/fit_b
        floor=2.0,
    )
    if mult_fit['fit_a'] is None or mult_fit['fit_b'] is None:
        return {
            'available': False,
            'stage1': stage1,
            'reason': 'Stage 2 multiplier fit failed: ' + mult_fit.get('fallback_reason', ''),
        }
    a_m, b_m = mult_fit['fit_a'], mult_fit['fit_b']
    # Manually compute mult at idx=4 and idx=5 (apply floor=2.0)
    mult_c4 = max(a_m * (4.0 ** b_m), 2.0)
    mult_c5 = max(a_m * (5.0 ** b_m), 2.0)

    # Drawdown fit for cross-check
    dd_fit = fit_cycle_compression(
        drawdowns,
        cycle_indices=list(range(1, len(drawdowns) + 1)),
        project_to_idx=4,
        floor=0.50,
    )

    b3 = float(bear_bottom_prices[-1])  # the most-recent observed bottom
    c4_top = b3 * mult_c4  # Stage 2a: C4 top, anchored on B3 directly
    if dd_fit['fit_a'] is not None and dd_fit['fit_b'] is not None:
        dd_c4 = max(dd_fit['fit_a'] * (4.0 ** dd_fit['fit_b']), 0.50)
    else:
        dd_fit_dd_proj = dd_fit['projected_value']
        dd_c4 = dd_fit_dd_proj if math.isfinite(dd_fit_dd_proj) else float('nan')
    c4_dd = dd_c4
    b4_via_drawdown = c4_top * (1.0 - c4_dd)  # Stage 2 cross-check

    # Stage 2b: C5 top from projected B4 (Stage 1)
    b4_stage1 = stage1['projected_price']
    c5_top = b4_stage1 * mult_c5

    # Cross-check: Stage 1 vs Stage 2 B4 estimates
    if b4_via_drawdown > 0 and math.isfinite(b4_via_drawdown):
        rel_diff = (b4_stage1 - b4_via_drawdown) / b4_via_drawdown
        cross_check_ok = abs(rel_diff) <= 0.15
    else:
        rel_diff = float('nan')
        cross_check_ok = False

    # Combined B4 band: intersection of [Stage1 low, Stage1 high] and
    # [Stage2 drawdown-path low, Stage2 drawdown-path high]
    s1_low, s1_high = stage1['price_band_low'], stage1['price_band_high']
    # Stage 2 B4 band via drawdown: carry through band on mult + dd (omit
    # for simplicity, treat as single point estimate).
    s2_b4 = b4_via_drawdown
    b4_band_low = min(s1_low, s2_b4)
    b4_band_high = max(s1_high, s2_b4)

    # Stage 1 B5 is the post-C5 bottom (optional)
    stage1_b5 = None
    try:
        stage1_b5 = project_bear_bottom(bear_bottom_prices + [b4_stage1],
                                        project_idx=5, floor_ratio=1.0)
    except Exception:
        pass

    return {
        'available': True,
        'stage1': stage1,
        'mult_fit': mult_fit,
        'dd_fit': dd_fit,
        'b3_observed': b3,
        'c4_top': c4_top,
        'c4_dd': c4_dd,
        'b4_stage1': b4_stage1,
        'b4_via_drawdown': b4_via_drawdown,
        'b4_band_low': b4_band_low,
        'b4_band_high': b4_band_high,
        'cross_check_ok': cross_check_ok,
        'cross_check_rel_diff': rel_diff,
        'mult_c4': mult_c4,
        'mult_c5': mult_c5,
        'c5_top': c5_top,
        'c5_top_band_low': b4_band_low * mult_c5,
        'c5_top_band_high': b4_band_high * mult_c5,
        'stage1_b5': stage1_b5,
    }


def two_stage_projection_with_observed_c4(bear_bottom_prices, multipliers,
                                          drawdowns, observed_c4_top_price,
                                          observed_c4_top_date=None,
                                          mult_floor=2.0):
    """2-stage projection variant that accepts an **observed C4 top** as input.

    Use this when C4's top has actually been observed in real-time data (the
    canonical assumption per the user's framework: "C4 is already in for all
    crypto assets by time range; assume it is observed").

    The projection chain becomes:
      Stage 1  -- project B4 from the bear-bottom ratio series  -> B4 USD
      Stage 2  -- project C5 top from projected B4 using the multiplier
                  power-law (idx=5)                              -> C5 top
    Cross-check: B4 is also derived as observed_C4_top * (1 - dd_C4) where
                  dd_C4 is the projected drawdown at idx=4 from the drawdown
                  power-law fit. Disagreement > 15% triggers the flag
                  `cross_check_ok = False` and the B4 band is widened to
                  contain both Stage 1 and Stage 2 estimates.

    Inputs:
      bear_bottom_prices: [B0, B1, B2, B3] (n >= 4)
      multipliers:        [m1, m2, m3]     (B0->C1, B1->C2, B2->C3)
      drawdowns:          [d1, d2, d3]     (1 - B_next/C_top per cycle)
      observed_c4_top_price: float, the observed USD price of C4 top
      observed_c4_top_date:  optional ISO date string (for record-keeping)
      mult_floor:          economic floor on multipliers (2.0 for crypto)

    Returns:
      dict with keys:
        available
        stage1            -- the Stage 1 result dict
        mult_fit          -- the multiplier power-law fit dict
        dd_fit            -- the drawdown power-law fit dict
        b3_observed       -- last observed bear bottom USD
        c4_top_observed   -- the input observed C4 top price
        c4_top_observed_date
        c4_dd             -- projected C4 drawdown (idx=4)
        b4_stage1         -- Stage 1 projection of B4 (USD)
        b4_via_drawdown   -- Stage 2 cross-check B4 = C4_top * (1 - dd_C4)
        b4_band_low, b4_band_high
        cross_check_ok, cross_check_rel_diff
        mult_c5           -- projected C5 multiplier (idx=5)
        c5_top            -- projected C5 top USD
        c5_top_band_low, c5_top_band_high
        stage1_b5         -- Stage 1 B5 projection (optional, post-C5)
    """
    if len(bear_bottom_prices) < 4:
        return {
            'available': False,
            'reason': ('need >= 4 bear bottoms for Stage 1 ratio fit, got %d'
                       % len(bear_bottom_prices)),
        }
    if len(multipliers) < 3:
        return {
            'available': False,
            'reason': ('need >= 3 multipliers for Stage 2 power-law fit, got %d'
                       % len(multipliers)),
        }

    # Stage 1: project B4 from the bear-bottom ratio series
    stage1 = project_bear_bottom(bear_bottom_prices, project_idx=4, floor_ratio=1.0)
    if not math.isfinite(stage1['projected_price']):
        return {
            'available': False,
            'stage1': stage1,
            'reason': 'Stage 1 failed: ' + stage1.get('fallback_reason', ''),
        }

    # Stage 2: multiplier power-law fit; we use idx=5 only (C5)
    # since C4 is observed.
    mult_fit = fit_cycle_compression(
        multipliers,
        cycle_indices=list(range(1, len(multipliers) + 1)),
        project_to_idx=5,
        floor=mult_floor,
    )
    if mult_fit['fit_a'] is None or mult_fit['fit_b'] is None:
        return {
            'available': False,
            'stage1': stage1,
            'mult_fit': mult_fit,
            'reason': 'Stage 2 multiplier fit failed: ' + mult_fit.get('fallback_reason', ''),
        }
    a_m, b_m = mult_fit['fit_a'], mult_fit['fit_b']
    mult_c5 = max(a_m * (5.0 ** b_m), mult_floor)

    # Drawdown power-law fit for cross-check (B4 via observed C4 top * (1 - dd_C4))
    if len(drawdowns) >= 3:
        dd_fit = fit_cycle_compression(
            drawdowns,
            cycle_indices=list(range(1, len(drawdowns) + 1)),
            project_to_idx=4,
            floor=0.50,
        )
        if dd_fit['fit_a'] is not None and dd_fit['fit_b'] is not None:
            dd_c4 = max(dd_fit['fit_a'] * (4.0 ** dd_fit['fit_b']), 0.50)
        else:
            dd_proj = dd_fit['projected_value']
            dd_c4 = dd_proj if math.isfinite(dd_proj) else float('nan')
    else:
        dd_fit = None
        dd_c4 = float(np.median(drawdowns)) if drawdowns else float('nan')

    b3 = float(bear_bottom_prices[-1])
    b4_stage1 = stage1['projected_price']
    b4_via_drawdown = observed_c4_top_price * (1.0 - dd_c4) if math.isfinite(dd_c4) else float('nan')

    # Cross-check Stage 1 vs Stage 2
    if math.isfinite(b4_via_drawdown) and b4_via_drawdown > 0:
        rel_diff = (b4_stage1 - b4_via_drawdown) / b4_via_drawdown
        cross_check_ok = abs(rel_diff) <= 0.15
    else:
        rel_diff = float('nan')
        cross_check_ok = False

    s1_low, s1_high = stage1['price_band_low'], stage1['price_band_high']
    s2_b4 = b4_via_drawdown if math.isfinite(b4_via_drawdown) else b4_stage1
    b4_band_low = min(s1_low, s2_b4)
    b4_band_high = max(s1_high, s2_b4)

    # Stage 1 B5 is the post-C5 bottom (optional). Requires the projected B4
    # appended to the chain so we can fit a ratio at idx=5.
    stage1_b5 = None
    try:
        stage1_b5 = project_bear_bottom(bear_bottom_prices + [b4_stage1],
                                        project_idx=5, floor_ratio=1.0)
    except Exception:
        pass

    c5_top = b4_stage1 * mult_c5
    c5_top_band_low = b4_band_low * mult_c5
    c5_top_band_high = b4_band_high * mult_c5

    return {
        'available': True,
        'stage1': stage1,
        'mult_fit': mult_fit,
        'dd_fit': dd_fit if dd_fit is not None
                  else {'fit_a': None, 'fit_b': None, 'r_squared': None,
                        'projected_value': dd_c4},
        'b3_observed': b3,
        'c4_top_observed': float(observed_c4_top_price),
        'c4_top_observed_date': observed_c4_top_date,
        'c4_dd': dd_c4,
        'b4_stage1': b4_stage1,
        'b4_via_drawdown': b4_via_drawdown,
        'b4_band_low': b4_band_low,
        'b4_band_high': b4_band_high,
        'cross_check_ok': cross_check_ok,
        'cross_check_rel_diff': rel_diff,
        'mult_c5': mult_c5,
        'c5_top': c5_top,
        'c5_top_band_low': c5_top_band_low,
        'c5_top_band_high': c5_top_band_high,
        'stage1_b5': stage1_b5,
    }


def two_stage_with_observed_c4_borrowed(observed_c4_top_price,
                                          observed_c4_top_date,
                                          parent_dds, parent_mults,
                                          parent_label='parent',
                                          dd_floor=0.50, mult_floor=2.0):
    """2-stage projection variant for assets with **insufficient own history**.

    Use when an alt has fewer than 4 observed bear bottoms or fewer than 3
    multipliers (XRP, SOL etc.) and so the own-asset power-law fit is
    unreliable. The **anchor** stays the asset's own observed C4 top; the
    **relative shape** (drawdown depth at C4, multiplier at C5) is borrowed
    from a higher-market-cap asset's fitted power-law curves.

    Returns a dict with the same keys as
    ``two_stage_projection_with_observed_c4`` plus:
      - ``shape_source``           -- label of parent whose shape was used
      - ``shape_synthetic``        -- True always (no own-data fit)
      - ``b4_stage1_origin``       -- 'borrowed_from_<parent>'

    Inputs:
      observed_c4_top_price: float, the asset's own observed C4 top
      observed_c4_top_date:  ISO string (or None)
      parent_dds:            list of *parent asset's observed drawdowns*
                             (e.g. BTC's [0.85, 0.83, 0.77])
      parent_mults:          list of *parent asset's observed bottom-to-top
                             multipliers* at idx 1..N
                             (e.g. BTC's [526, 112, 21.6])
      parent_label:          string for the fit note ('BTC', 'ETH', etc.)
      dd_floor, mult_floor:  economic floors (0.50, 2.0 for crypto)
    """
    c4_top = float(observed_c4_top_price)

    # --- Stage 2 (drawdown path) -- project dd_C4 from parent shape.
    dd_fit = fit_cycle_compression(
        parent_dds,
        cycle_indices=list(range(1, len(parent_dds) + 1)),
        project_to_idx=4,
        floor=dd_floor,
    )
    if dd_fit['fit_a'] is not None and dd_fit['fit_b'] is not None:
        dd_c4 = float(max(dd_fit['fit_a'] * (4.0 ** dd_fit['fit_b']), dd_floor))
        dd_band_low = float(max(dd_fit['fit_a'] * (4.0 ** dd_fit['fit_b']) - dd_fit['log_residual_std'] * 0.5, dd_floor))
        dd_band_high = float(min(0.95, dd_c4 + dd_fit['log_residual_std'] * 0.5))
    else:
        dd_c4 = dd_fit['projected_value']
        dd_band_low = dd_c4 * 0.85
        dd_band_high = min(0.95, dd_c4 * 1.15)

    b4_via_drawdown = c4_top * (1.0 - dd_c4)
    b4_low = c4_top * (1.0 - dd_band_high)
    b4_high = c4_top * (1.0 - max(dd_band_low, 0.10))

    # --- Stage 2 multiplier -- project mult_C5 from parent shape.
    mult_fit = fit_cycle_compression(
        parent_mults,
        cycle_indices=list(range(1, len(parent_mults) + 1)),
        project_to_idx=5,
        floor=mult_floor,
    )
    if mult_fit['fit_a'] is not None and mult_fit['fit_b'] is not None:
        mult_c5 = float(max(mult_fit['fit_a'] * (5.0 ** mult_fit['fit_b']), mult_floor))
        log_std = mult_fit['log_residual_std'] or 0.3
        mult_band_low = float(max(mult_c5 * math.exp(-log_std), mult_floor))
        mult_band_high = float(mult_c5 * math.exp(log_std))
    else:
        mult_c5 = float(np.median(parent_mults)) if parent_mults else mult_floor
        mult_band_low = float(np.min(parent_mults)) if parent_mults else mult_floor
        mult_band_high = float(np.max(parent_mults)) if parent_mults else mult_floor

    # Sanity: B4 must be below C4 top (otherwise the borrowed shape is
    # itself broken; in that case force a conservative 50% drawdown).
    if not (0.0 < b4_via_drawdown < c4_top):
        b4_via_drawdown = c4_top * (1.0 - 0.66)
        b4_low = c4_top * (1.0 - 0.80)
        b4_high = c4_top * (1.0 - 0.50)

    c5_top = b4_via_drawdown * mult_c5
    c5_top_band_low = b4_low * mult_band_low
    c5_top_band_high = b4_high * mult_band_high

    # B5 (post-C5 bottom) = C5 * (1 - dd_C5) where dd_C5 is projected dd at idx=5.
    if dd_fit['fit_a'] is not None and dd_fit['fit_b'] is not None:
        dd_c5 = float(max(dd_fit['fit_a'] * (5.0 ** dd_fit['fit_b']), dd_floor))
    else:
        dd_c5 = dd_c4
    b5_center = c5_top * (1.0 - dd_c5)
    b5_low = c5_top_band_low * (1.0 - min(0.95, dd_c5 + 0.10))
    b5_high = c5_top_band_high * (1.0 - max(0.10, dd_c5 - 0.10))

    return {
        'available': True,
        'shape_source': parent_label,
        'shape_synthetic': True,
        'b3_observed': None,
        'c4_top_observed': float(observed_c4_top_price),
        'c4_top_observed_date': observed_c4_top_date,
        'stage1': {'used': 'borrowed', 'fallback_reason':
                   f'n_own_bottoms < 4; shape borrowed from {parent_label}'},
        'mult_fit': mult_fit,
        'dd_fit': dd_fit,
        'c4_dd': dd_c4,
        'b4_stage1': b4_via_drawdown,
        'b4_stage1_origin': f'borrowed_from_{parent_label}',
        'b4_via_drawdown': b4_via_drawdown,
        'b4_band_low': b4_low,
        'b4_band_high': b4_high,
        'cross_check_ok': None,
        'cross_check_rel_diff': float('nan'),
        'mult_c5': mult_c5,
        'mult_c5_band_low': mult_band_low,
        'mult_c5_band_high': mult_band_high,
        'c5_top': c5_top,
        'c5_top_band_low': c5_top_band_low,
        'c5_top_band_high': c5_top_band_high,
        'b5_band_low': b5_low,
        'b5_band_high': b5_high,
        'b5_center': b5_center,
        'stage1_b5': None,
    }


# --- C1: BTC price with halving/top/bottom overlays ---
def build_c1():
    fig = go.Figure()

    # BTC log price
    fig.add_trace(go.Scatter(
        x=btc['date'].dt.strftime('%Y-%m-%d'), y=np.log(btc['close']),
        mode='lines', name='BTC log price',
        line=dict(color='#666', width=1.2),
    ))

    # Halvings (green)
    halvings = events[events['event_type'] == 'halving']
    for _, h in halvings.iterrows():
        fig.add_vline(x=str(h['date']), line_dash='dash',
                      line_color='green', opacity=0.5)

    # Tops (red) — alternating top/bottom annotation positions
    tops = events[events['event_type'] == 'top']
    positions_top = ['top right', 'top left', 'top right', 'top left']
    for i, (_, t) in enumerate(tops.iterrows()):
        if pd.notna(t['price_usd']):
            pos = positions_top[i % len(positions_top)]
            yref = 'paper' if 'top' in pos else 'paper'
            y_anchor = 0.97 if 'right' in pos else 0.93
            fig.add_vline(x=str(t['date']), line_dash='dot',
                          line_color='red', opacity=0.5)
            fig.add_annotation(
                x=str(t['date']), y=y_anchor, yref='paper',
                text=f"TOP {t['cycle_id']}",
                showarrow=False, font=dict(size=9, color='#f87171'),
                bgcolor='rgba(10,14,26,0.8)', borderpad=2,
            )

    # Bottoms (blue) — alternating positions
    bottoms = events[events['event_type'] == 'bottom']
    positions_bot = ['bottom left', 'bottom right', 'bottom left', 'bottom right']
    for i, (_, b) in enumerate(bottoms.iterrows()):
        pos = positions_bot[i % len(positions_bot)]
        y_anchor = 0.05 if 'left' in pos else 0.10
        fig.add_vline(x=str(b['date']), line_dash='dot',
                      line_color='blue', opacity=0.5)
        fig.add_annotation(
            x=str(b['date']), y=y_anchor, yref='paper',
            text=f"BOT {b['cycle_id']}",
            showarrow=False, font=dict(size=9, color='#60a5fa'),
            bgcolor='rgba(10,14,26,0.8)', borderpad=2,
        )

    y_ticks = log_to_usd_ticks(float(np.log(btc['close'].min())),
                                float(np.log(btc['close'].max())))
    fig.update_layout(
        title='C1 — BTC Price with Halving / Top / Bottom Overlays',
        xaxis_title='Date', yaxis_title='Price (USD)',
        template='plotly_dark', height=500,
        yaxis=dict(type='log', **y_ticks),
    )
    _safe_write_html(fig, CHARTS_DIR / 'C1.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C1.png', scale=2)
    print("  C1 done")


# --- C2: Days-from-halving-aligned BTC cycles ---
def build_c2():
    aligned = pd.read_csv('data/processed/returns_aligned.csv')
    fig = go.Figure()

    colors = {'C1': '#1f77b4', 'C2': '#ff7f0e', 'C3': '#2ca02c', 'C4': '#d62728'}
    for cycle_id in ['C1', 'C2', 'C3', 'C4']:
        cyc = aligned[aligned['cycle_id'] == cycle_id]
        fig.add_trace(go.Scatter(
            x=cyc['days_from_halving'], y=np.log(cyc['btc_close']),
            mode='lines', name=cycle_id,
            line=dict(color=colors.get(cycle_id, 'gray'), width=1.5),
        ))

    # Compute y-range across all cycles
    all_log_prices = aligned['btc_close'].apply(lambda x: np.log(x) if x > 0 else np.nan).dropna()
    y_ticks = log_to_usd_ticks(float(all_log_prices.min()), float(all_log_prices.max()))

    fig.update_layout(
        title='C2 — BTC Cycles Aligned by Days from Halving',
        xaxis_title='Days from Halving', yaxis_title='Price (USD)',
        xaxis=dict(range=[-1500, 1500]),
        template='plotly_dark', height=500,
        yaxis=dict(type='log', **y_ticks),
    )
    _safe_write_html(fig, CHARTS_DIR / 'C2.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C2.png', scale=2)
    print("  C2 done")


# --- C3: Per-cycle duration metrics ---
def build_c3():
    stats = ['D_prev_bottom_to_halving', 'D_halving_to_top', 'D_top_to_next_bottom']
    labels = ['Bottom → Halving', 'Halving → Top', 'Top → Next Bottom']
    cycles = ['C1', 'C2', 'C3', 'C4']

    fig = go.Figure()
    for i, (stat, label) in enumerate(zip(stats, labels)):
        vals = []
        for c in cycles:
            row = metrics[metrics['cycle_id'] == c]
            if not row.empty and pd.notna(row[stat].iloc[0]):
                vals.append(float(row[stat].iloc[0]))
            else:
                vals.append(None)  # Plotly renders None as a gap

        fig.add_trace(go.Bar(
            x=cycles, y=vals, name=label,
            text=[(f'{v:.0f}d' if v is not None else 'pending') for v in vals],
            textposition='auto',
        ))

    fig.add_annotation(
        text='C4 bar pending — bottom not yet observed',
        x='C4', y=0, showarrow=False, yshift=10,
        font=dict(size=10, color='gray'),
    )

    fig.update_layout(
        title='C3 — Per-Cycle Duration Metrics',
        xaxis_title='Cycle', yaxis_title='Days',
        barmode='group', template='plotly_dark', height=500,
        showlegend=False,
    )
    _safe_write_html(fig, CHARTS_DIR / 'C3.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C3.png', scale=2)
    print("  C3 done")


# --- C4: Cross-asset phase-conditioned correlations (heatmap) ---
def build_c4():
    assets = sorted(corr_phase['asset'].unique())
    phases = ['P1', 'P2', 'P3', 'P4']

    z = []
    for asset in assets:
        row = []
        for phase in phases:
            match = corr_phase[(corr_phase['asset'] == asset) & (corr_phase['phase'] == phase)]
            row.append(float(match['pearson'].iloc[0]) if len(match) > 0 else 0)
        z.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z, x=phases, y=assets,
        colorscale='RdBu_r', zmin=-1, zmax=1,
        text=[[f'{v:.2f}' for v in row] for row in z],
        texttemplate='%{text}', textfont=dict(size=11),
    ))

    fig.update_layout(
        title='C4 — Cross-Asset Phase-Conditioned Correlations (Pearson)',
        template='plotly_dark', height=400,
    )
    _safe_write_html(fig, CHARTS_DIR / 'C4.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C4.png', scale=2)
    print("  C4 done")


# --- C5: Rolling correlation BTC vs DXY/TLT ---
def build_c5():
    fig = go.Figure()
    colors = {'dxy': '#e41a1c', 'tlt': '#377eb8'}

    for asset in ['dxy', 'tlt']:
        sub = corr_rolling[(corr_rolling['asset'] == asset) & (corr_rolling['cycle_id'] == 'C4')]
        sub = sub.sort_values('days_from_halving')
        fig.add_trace(go.Scatter(
            x=sub['days_from_halving'], y=sub['rolling_r_90d'],
            mode='lines', name=f'BTC vs {asset.upper()}',
            line=dict(color=colors[asset], width=1.5),
        ))

    fig.add_hline(y=0, line_dash='dash', line_color='gray', opacity=0.5)
    fig.update_layout(
        title='C5 — Rolling 90-day Correlation: BTC vs DXY/TLT (C4)',
        xaxis_title='Days from Halving', yaxis_title='Pearson r',
        xaxis=dict(range=[-1500, 1500]),
        template='plotly_dark', height=400,
    )
    _safe_write_html(fig, CHARTS_DIR / 'C5.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C5.png', scale=2)
    print("  C5 done")


# --- C6: BTC prediction chart — single tall panel with C5 TOP + B5 BOTTOM ---
def build_c6():
    """C6 — Single tall log-scale panel BTC prediction chart.

    The BTC price line extends 2022-09 to 2031-06. C5 TOP and B5 BOTTOM
    prediction bands are rendered as semi-transparent rectangles inside the
    main panel (log scale), with prediction annotations.  Event markers
    (B3, H4, observed C4 top, projected B4, H5) are vertical lines with
    labels at top. B5 marker added at exit-zone midpoint.

    Bands are narrowed by using 0.75x the residual standard deviation
    (prediction-interval scaling) so the range is tighter and more useful.
    """
    # --- Narrowing factor: 0.75x residual_std for tighter prediction bands ---
    BAND_SCALE = 0.75

    def _narrow_band(center, lo, hi, scale):
        """Narrow a band around its center by compressing in log-space."""
        if center <= 0 or lo <= 0 or hi <= 0:
            return lo, hi
        log_c = math.log(center)
        log_half = math.log(hi) - log_c
        return center * math.exp(-log_half * scale), center * math.exp(log_half * scale)

    # --- Observed C4 top: raw BTC peak since H4 ---
    btc_post_h4 = btc[btc['date'] >= '2024-04-20'].reset_index(drop=True)
    peak_idx = btc_post_h4['close'].idxmax()
    observed_c4_top_price = float(btc_post_h4.loc[peak_idx, 'close'])
    observed_c4_top_date = btc_post_h4.loc[peak_idx, 'date'].strftime('%Y-%m-%d')

    # --- 2-stage projection ---
    bear_rows = events[(events['event_type'] == 'bottom')
                       & (events['cycle_id'].isin(['B0', 'B1', 'B2', 'B3']))]
    bear_rows = bear_rows.sort_values('cycle_id')
    bear_prices = bear_rows['price_usd'].astype(float).tolist()

    top_rows = events[(events['event_type'] == 'top')
                      & (events['reason_code'] == 'canonical')
                      & (events['cycle_id'].isin(['C1', 'C2', 'C3']))]
    top_rows = top_rows.sort_values('cycle_id').drop_duplicates('cycle_id', keep='last')
    top_prices = top_rows['price_usd'].astype(float).tolist()
    mult_vals = [top_prices[i] / bear_prices[i] for i in range(len(top_prices))]
    dd_vals = [float(metrics[metrics['cycle_id'] == c].iloc[0]['drawdown_pct'])
               for c in ['C1', 'C2', 'C3']]

    proj = two_stage_projection_with_observed_c4(
        bear_prices, mult_vals, dd_vals,
        observed_c4_top_price=observed_c4_top_price,
        observed_c4_top_date=observed_c4_top_date,
        mult_floor=2.0,
    )

    if not proj.get('available'):
        c5_top_center = c5_top_low = c5_top_high = 0
        b4_proj = b4_proj_low = b4_proj_high = 0
        b5_low = b5_high = 0
        cross_check_ok = False
        cross_check_rel_diff = float('nan')
        ratio_a = ratio_b = ratio_r2 = 0
        mult_a = mult_b = mult_r2 = 0
        mult_c5 = 0
        dd_c4 = 0
        b4_via_drawdown = 0
    else:
        c5_top_center = proj['c5_top']
        c5_top_low_raw = proj['c5_top_band_low']
        c5_top_high_raw = proj['c5_top_band_high']
        b4_proj = proj['b4_stage1']
        b4_proj_low_raw = proj['b4_band_low']
        b4_proj_high_raw = proj['b4_band_high']
        # Narrow B4 band first (tighter anchor for C5)
        b4_proj_low, b4_proj_high = _narrow_band(
            b4_proj, b4_proj_low_raw, b4_proj_high_raw, BAND_SCALE)
        # Narrow C5 TOP band
        c5_top_low, c5_top_high = _narrow_band(
            c5_top_center, c5_top_low_raw, c5_top_high_raw, BAND_SCALE)
        # B5 (post-C5 bear bottom) via Stage 1 ratio(idx=5)
        s1b5 = proj.get('stage1_b5')
        if s1b5 is not None and s1b5.get('used') == 'power_law_fit':
            b5_low_raw = s1b5['price_band_low']
            b5_high_raw = s1b5['price_band_high']
            b5_center = s1b5['projected_price']
            b5_low, b5_high = _narrow_band(
                b5_center, b5_low_raw, b5_high_raw, BAND_SCALE)
        elif s1b5 is not None and math.isfinite(s1b5.get('projected_price', float('nan'))):
            b5_low = b5_high = b5_center = s1b5['projected_price']
        else:
            b5_low = b5_high = b5_center = c5_top_center * (1.0 - proj['c4_dd']) if c5_top_center else 0
        cross_check_ok = proj['cross_check_ok']
        cross_check_rel_diff = proj['cross_check_rel_diff']
        ratio_a = proj['stage1']['fit_a']
        ratio_b = proj['stage1']['fit_b']
        ratio_r2 = proj['stage1']['r_squared']
        mult_a = proj['mult_fit']['fit_a']
        mult_b = proj['mult_fit']['fit_b']
        mult_r2 = proj['mult_fit']['r_squared']
        mult_c5 = proj['mult_c5']
        dd_c4 = proj['c4_dd']
        b4_via_drawdown = proj['b4_via_drawdown']

    b3_price = float(bear_prices[-1])
    btc_now = float(btc[btc['date'] >= '2022-09-01'].iloc[-1]['close'])

    # --- Single tall figure (no subplots) ---
    fig = go.Figure()

    # BTC price line
    btc_zoom = btc[btc['date'] >= '2022-09-01']
    fig.add_trace(go.Scatter(
        x=btc_zoom['date'].dt.strftime('%Y-%m-%d'), y=btc_zoom['close'],
        customdata=btc_zoom['close'],
        mode='lines', name='BTC price',
        line=dict(color='#888', width=1),
        hovertemplate='%{x}<br>$%{customdata:,.0f}<extra></extra>',
        showlegend=False,
    ))

    # --- Muted SMA floor overlay (50w / 200w) — decision-context reference, not a model input ---
    if sma_floors is not None and not sma_floors.empty:
        # Filter to dates within C6's visible range [2022-09-01, 2031-06-01]
        sma_floors['date_parsed'] = pd.to_datetime(sma_floors['date'], errors='coerce')
        sma_zoom = sma_floors[sma_floors['date_parsed'] >= '2022-09-01'].copy()
        sma_zoom = sma_zoom[sma_zoom['date_parsed'] <= '2031-06-01'].copy()
        if not sma_zoom.empty:
            for sma_col, label, color in [
                ('sma_50w', '50w SMA', '#6b7280'),
                ('sma_200w', '200w SMA', '#9ca3af'),
            ]:
                sub = sma_zoom[['date_parsed', sma_col]].dropna()
                if len(sub) > 1:
                    fig.add_trace(go.Scatter(
                        x=sub['date_parsed'].dt.strftime('%Y-%m-%d'),
                        y=sub[sma_col],
                        mode='lines', name=label,
                        line=dict(color=color, width=1, dash='dot'),
                        opacity=0.5,
                        hovertemplate=f'{label}<br>%{{x}}<br>$%{{y:,.0f}}<extra></extra>',
                        showlegend=False,
                    ))

    # --- Zone shading (faint vertical bands) ---
    zone_fill = {
        'accumulation': 'rgba(74,222,128,0.06)',
        'distribution': 'rgba(251,146,60,0.10)',
        'exit': 'rgba(96,165,250,0.10)',
    }
    for _, z in zones.iterrows():
        fig.add_vrect(x0=z['outer_start'], x1=z['outer_end'],
                      fillcolor=zone_fill.get(z['zone'], 'gray'),
                      line_width=0, layer='below')
        fig.add_annotation(x=z['base_start'], y=0.97, yref='paper',
                           text=f"<b>{z['zone'].upper()}</b>", showarrow=False,
                           font=dict(size=7, color='white'), xanchor='left', xshift=2)

    dist_zone = zones[zones['zone'] == 'distribution'].iloc[0]
    exit_zone = zones[zones['zone'] == 'exit'].iloc[0]

    # --- C5 TOP band rectangle (orange, spans distribution zone dates) ---
    fig.add_shape(
        type='rect', xref='x', yref='y',
        x0=dist_zone['outer_start'], x1=dist_zone['outer_end'],
        y0=c5_top_low, y1=c5_top_high,
        fillcolor='rgba(251,146,60,0.25)',
        line=dict(color='rgb(251,146,60)', width=2),
        layer='below',
    )
    fig.add_trace(go.Scatter(
        x=[dist_zone['outer_start'], dist_zone['outer_end']],
        y=[c5_top_center, c5_top_center],
        mode='lines', name='C5 TOP center',
        line=dict(color='rgb(251,146,60)', width=2),
        hovertemplate='C5 TOP center: $%{y:,.0f}<extra></extra>',
        showlegend=False,
    ))
    # C5 TOP marker (triangle-down) at distribution zone midpoint
    dist_mid_date = (pd.to_datetime(dist_zone['base_start'])
                     + (pd.to_datetime(dist_zone['base_end'])
                        - pd.to_datetime(dist_zone['base_start'])) / 2)
    fig.add_trace(go.Scatter(
        x=[dist_mid_date.strftime('%Y-%m-%d')], y=[c5_top_center],
        mode='markers', name='C5 TOP proj',
        marker=dict(symbol='triangle-down', size=14, color='#facc15',
                    line=dict(color='white', width=1.5)),
        hovertemplate=f'C5 TOP predicted<br>${c5_top_center:,.0f}<br>'
                      f'band ${c5_top_low:,.0f}–${c5_top_high:,.0f}<extra></extra>',
        showlegend=False,
    ))
    fig.add_annotation(
        x=dist_zone['base_end'], y=c5_top_center,
        xref='x', yref='y',
        text=(f"<b>C5 TOP</b><br>"
              f"${c5_top_low:,.0f} – ${c5_top_high:,.0f}<br>"
              f"(center ${c5_top_center:,.0f})"),
        showarrow=True, arrowhead=2, arrowcolor='rgb(251,146,60)',
        ax=-60, ay=0,
        font=dict(size=10, color='#ffffff'),
        bgcolor='rgba(10,14,26,0.90)',
        borderpad=4,
        xanchor='right', yanchor='middle',
    )

    # --- B5 BOTTOM band rectangle (blue, spans exit zone dates) ---
    fig.add_shape(
        type='rect', xref='x', yref='y',
        x0=exit_zone['outer_start'], x1=exit_zone['outer_end'],
        y0=b5_low, y1=b5_high,
        fillcolor='rgba(96,165,250,0.25)',
        line=dict(color='rgb(96,165,250)', width=2),
        layer='below',
    )
    fig.add_trace(go.Scatter(
        x=[exit_zone['outer_start'], exit_zone['outer_end']],
        y=[b5_center, b5_center],
        mode='lines', name='B5 center',
        line=dict(color='rgb(96,165,250)', width=2),
        hovertemplate='B5 center: $%{y:,.0f}<extra></extra>',
        showlegend=False,
    ))
    fig.add_annotation(
        x=exit_zone['base_end'], y=b5_center,
        xref='x', yref='y',
        text=(f"<b>B5 (post-C5 bottom)</b><br>"
              f"${b5_low:,.0f} – ${b5_high:,.0f}<br>"
              f"(center ${b5_center:,.0f})"),
        showarrow=True, arrowhead=2, arrowcolor='rgb(96,165,250)',
        ax=-60, ay=0,
        font=dict(size=10, color='#ffffff'),
        bgcolor='rgba(10,14,26,0.90)',
        borderpad=4,
        xanchor='right', yanchor='middle',
    )

    # --- Observed C4 top marker ---
    fig.add_trace(go.Scatter(
        x=[observed_c4_top_date], y=[observed_c4_top_price],
        mode='markers', name='Observed C4 top',
        marker=dict(symbol='triangle-down', size=14, color='#facc15',
                    line=dict(color='white', width=1.5)),
        hovertemplate='Observed C4 top<br>%{x}<br>$%{y:,.0f}<extra></extra>',
        showlegend=False,
    ))
    fig.add_annotation(
        x=observed_c4_top_date, y=observed_c4_top_price,
        xref='x', yref='y',
        text=f'<b>C4 top ${observed_c4_top_price:,.0f}</b>',
        showarrow=True, arrowhead=2, arrowcolor='#facc15',
        ax=40, ay=30,
        font=dict(size=10, color='#facc15'),
        bgcolor='rgba(10,14,26,0.85)',
        borderpad=3,
    )

    # --- Projected B4 marker ---
    b4_zone = None
    if 'bear_bottom' in set(zones['zone'].values):
        b4_zone = zones[zones['zone'] == 'bear_bottom'].iloc[0]
        b4_base_start = pd.to_datetime(b4_zone['base_start'])
        b4_base_end = pd.to_datetime(b4_zone['base_end'])
        projected_b4_date = b4_base_start + (b4_base_end - b4_base_start) / 2
    else:
        legacy_exit = zones[zones['zone'] == 'exit'].iloc[0]
        legacy_start = pd.to_datetime(legacy_exit['base_start'])
        legacy_end = pd.to_datetime(legacy_exit['base_end'])
        projected_b4_date = legacy_start + (legacy_end - legacy_start) / 2
    projected_b4_date_str = projected_b4_date.strftime('%Y-%m-%d')
    fig.add_trace(go.Scatter(
        x=[projected_b4_date_str], y=[b4_proj],
        mode='markers', name='Projected B4',
        marker=dict(symbol='triangle-up', size=14, color='#22d3ee',
                    line=dict(color='white', width=1.5)),
        hovertemplate=f'Projected B4<br>%{{x}}<br>$%{{y:,.0f}}<br>band ${b4_proj_low:,.0f}-${b4_proj_high:,.0f}<extra></extra>',
        showlegend=False,
    ))
    fig.add_annotation(
        x=projected_b4_date_str, y=b4_proj,
        xref='x', yref='y',
        text=(f'<b>B4 ${b4_proj:,.0f}</b><br>'
              f'<span style="font-size:8px">band ${b4_proj_low:,.0f}–${b4_proj_high:,.0f}</span>'),
        showarrow=True, arrowhead=2, arrowcolor='#22d3ee',
        ax=-45, ay=-25,
        font=dict(size=10, color='#22d3ee'),
        bgcolor='rgba(10,14,26,0.85)',
        borderpad=3,
    )

    # --- B5 marker at exit zone midpoint ---
    exit_start = pd.to_datetime(exit_zone['base_start'])
    exit_end = pd.to_datetime(exit_zone['base_end'])
    b5_date = (exit_start + (exit_end - exit_start) / 2).strftime('%Y-%m-%d')
    fig.add_trace(go.Scatter(
        x=[b5_date], y=[b5_center],
        mode='markers', name='Projected B5',
        marker=dict(symbol='triangle-up', size=12, color='#60a5fa',
                    line=dict(color='white', width=1.5)),
        hovertemplate=f'Projected B5<br>%{{x}}<br>$%{{y:,.0f}}<br>band ${b5_low:,.0f}-${b5_high:,.0f}<extra></extra>',
        showlegend=False,
    ))

    # --- Qualitative cross-reference band: B4 + IQR(D_bottom_to_next_top) ---
    # Folk "1064-day bull" narrative anchored on B4. Shows the B4-anchored
    # C5 top window as a translucent purple rectangle, distinct from the
    # orange H5-anchored distribution band. NOTE: D_bottom_to_next_top is a
    # near-arithmetic identity (next cycle's D_prev_bottom_to_halving +
    # D_halving_to_top), so this is a qualitative consistency check against
    # a folk narrative, not independent statistical validation.
    if 'bear_bottom' in set(zones['zone'].values):
        try:
            b4_center_dt = pd.to_datetime(projected_b4_date_str)
            d_bnt_row = fwd[fwd['statistic'] == 'D_bottom_to_next_top']
            if not d_bnt_row.empty and pd.notna(d_bnt_row.iloc[0].get('median')):
                d_bnt = d_bnt_row.iloc[0]
                bnt_med = int(float(d_bnt['median']))
                bnt_q25 = int(float(d_bnt['q25']))
                bnt_q75 = int(float(d_bnt['q75']))
                bnt_min = int(float(d_bnt['min']))
                bnt_max = int(float(d_bnt['max']))
                bnt_n = int(d_bnt['n'])
                b4_c5_center = (b4_center_dt + timedelta(days=bnt_med)).strftime('%Y-%m-%d')
                b4_c5_base_start = (b4_center_dt + timedelta(days=bnt_q25)).strftime('%Y-%m-%d')
                b4_c5_base_end = (b4_center_dt + timedelta(days=bnt_q75)).strftime('%Y-%m-%d')
                b4_c5_outer_start = (b4_center_dt + timedelta(days=bnt_min)).strftime('%Y-%m-%d')
                b4_c5_outer_end = (b4_center_dt + timedelta(days=bnt_max)).strftime('%Y-%m-%d')
                # Translucent purple vrect (distinguishable from orange distribution)
                fig.add_vrect(
                    x0=b4_c5_base_start, x1=b4_c5_base_end,
                    fillcolor='rgba(168, 85, 247, 0.15)',
                    line=dict(color='#a855f7', width=1, dash='dot'),
                    layer='below',
                )
                # Outer envelope (very faint)
                fig.add_vrect(
                    x0=b4_c5_outer_start, x1=b4_c5_outer_end,
                    fillcolor='rgba(168, 85, 247, 0.05)',
                    line=dict(color='#a855f7', width=0.5, dash='dot'),
                    opacity=0.45, layer='below',
                )
                # Top-of-chart label
                fig.add_annotation(
                    x=b4_c5_center, y=1.06, yref='paper',
                    text=f"<b>Qualitative cross-ref: folk bull rhythm (B4 + {bnt_med}d)</b>"
                         f"<br><span style='font-size:7px'>built from {bnt_n} cycles "
                         f"(range {bnt_min}-{bnt_max}d, ~{bnt_q75-bnt_q25}d IQR)</span>",
                    showarrow=False, font=dict(size=9, color='#a855f7'),
                    bgcolor='rgba(10,14,26,0.85)',
                    borderpad=3, xanchor='center',
                )
                # Qualitative cross-ref C5 top marker at the band center
                fig.add_trace(go.Scatter(
                    x=[b4_c5_center], y=[c5_top_center],
                    mode='markers',
                    marker=dict(symbol='diamond', size=12, color='#a855f7',
                                line=dict(color='white', width=1.5)),
                    name='Folk qualitative cross-ref (B4+1064d)',
                    hovertemplate=(f'Folk qualitative cross-ref (B4+{bnt_med}d)<br>%{{x}}<br>'
                                  f'$%{{y:,.0f}}<extra></extra>'),
                    showlegend=False,
                ))
        except Exception as e:
            print(f"  (folklore band skipped: {e})")

    # --- BTC event vertical lines ---
    btc_evts = []
    b3_d = str(events[(events['event_type'] == 'bottom') & (events['cycle_id'] == 'B3')].iloc[0]['date'])
    btc_evts.append((b3_d, '#60a5fa', 'dot', 'B3'))
    h4_d = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H4')].iloc[0]['date'])
    btc_evts.append((h4_d, '#4ade80', 'dash', 'H4'))
    h5_d = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H5')].iloc[0]['date'])
    btc_evts.append((h5_d, '#4ade80', 'dash', 'H5'))
    btc_evts.append((observed_c4_top_date, '#facc15', 'dot', 'C4 top'))
    btc_evts.append((projected_b4_date_str, '#22d3ee', 'dot', 'B4 proj'))

    for evt_date, evt_color, evt_dash, evt_label in btc_evts:
        fig.add_shape(type='line', x0=evt_date, x1=evt_date, y0=0, y1=1,
                      yref='paper',
                      line=dict(color=evt_color, dash=evt_dash, width=1.5), opacity=0.5)
        fig.add_annotation(x=evt_date, y=1.02, yref='paper',
                           text=f'<b>{evt_label}</b>', showarrow=False,
                           font=dict(size=8, color=evt_color), xanchor='center')

    # --- BTC today reference line ---
    fig.add_hline(y=btc_now, line_dash='dash', line_color='rgba(255,255,255,0.25)', line_width=1)
    fig.add_annotation(x='2031-06-01', y=btc_now, xref='x', yref='y',
                       text=f'BTC today ${btc_now:,.0f}',
                       showarrow=False, font=dict(size=9, color='rgba(255,255,255,0.5)'),
                       xanchor='right', yanchor='bottom')

    # --- Axes ---
    y_min = float(btc_zoom['close'].min()) * 0.8
    y_max = max(c5_top_high * 1.15, observed_c4_top_price * 1.3)
    y_ticks = log_to_usd_ticks(np.log(y_min), np.log(y_max), num_ticks=10)
    fig.update_yaxes(type='log', tickvals=y_ticks['tickvals'], ticktext=y_ticks['ticktext'],
                     gridcolor='#2a3349', title_text='Price (USD)',
                     tickfont=dict(size=11, color='#b0bdc7'),
                     title_font=dict(size=12, color='#b0bdc7'))
    fig.update_xaxes(type='date', range=['2022-09-01', '2031-06-01'],
                     dtick='M6', tickformat='%Y-%m', gridcolor='#2a3349')

    # --- Bottom notes ---
    ck_str = "OK" if cross_check_ok else "FAIL"
    anchor_note = (
        f"Chain: B3=${b3_price:,.0f} (obs) -> C4 top=${observed_c4_top_price:,.0f} (obs {observed_c4_top_date}) -> "
        f"B4=${b4_proj:,.0f} (band ${b4_proj_low:,.0f}-${b4_proj_high:,.0f}) -> "
        f"C5 top=${c5_top_center:,.0f} (B4 x mult_C5={mult_c5:.2f}). Cross-check {ck_str}."
    )
    notes = [
        anchor_note,
        f"Stage 1: ratio_n={ratio_a:.1f}*idx^{ratio_b:.2f}  R²={ratio_r2:.2f}  "
        f"-> B4/B3={proj['stage1']['projected_ratio']:.2f}  "
        f"(B4 via dd=${b4_via_drawdown:,.0f}, rel_diff={cross_check_rel_diff:+.1%})",
        f"Stage 2: mult_n={mult_a:.1f}*idx^{mult_b:.2f}  R²={mult_r2:.2f}  "
        f"-> C5 top band ${c5_top_low:,.0f}-${c5_top_high:,.0f}. "
        f"C4 dd={dd_c4:.1%}",
    ]
    if b4_zone is not None:
        notes.append(
            f"B4 (post-C4 bear): {b4_zone['base_start']} -> B5 (post-C5 bear): {exit_zone['base_start']} "
            f"band ${b5_low:,.0f}-${b5_high:,.0f}"
        )
    # Qualitative cross-reference note (purple-hued, drawn from D_bottom_to_next_top in forward_ranges.csv)
    if 'bear_bottom' in set(zones['zone'].values):
        d_bnt_row = fwd[fwd['statistic'] == 'D_bottom_to_next_top']
        if not d_bnt_row.empty and pd.notna(d_bnt_row.iloc[0].get('median')):
            d_bnt = d_bnt_row.iloc[0]
            bnt_med = int(float(d_bnt['median']))
            bnt_min = int(float(d_bnt['min']))
            bnt_max = int(float(d_bnt['max']))
            bnt_q25 = int(float(d_bnt['q25']))
            try:
                b4_dt = pd.to_datetime(projected_b4_date_str)
                b4_c5_center = (b4_dt + timedelta(days=bnt_med)).strftime('%Y-%m-%d')
                h5_c5_center = pd.to_datetime(projected_b4_date_str) + timedelta(days=0)
                # H5-anchored: H5_DATE + median(D_halving_to_top) -- see _load_h5_date() above.
                d_ht_row = fwd[fwd['statistic'] == 'D_halving_to_top']
                if not d_ht_row.empty:
                    dht_med = int(float(d_ht_row.iloc[0]['median']))
                    h5_c5_dt = H5_DATE + timedelta(days=dht_med)
                    diff_d = (pd.to_datetime(b4_c5_center) - h5_c5_dt).days
                    diff_str = f"{diff_d:+d}d"
                    notes.append(
                        f"Qualitative cross-reference (folk rhythm, not independent validation): "
                        f"'365-day bear / 1064-day bull'. D_bottom_to_next_top n=3, "
                        f"range {bnt_min}-{bnt_max}d, med={bnt_med}d -> B4-anchored C5 top "
                        f"{b4_c5_center} (base IQR {bnt_q25}d wide). "
                        f"H5-anchored C5 top {h5_c5_dt.strftime('%Y-%m-%d')} "
                        f"(base IQR ~{int(float(d_ht_row.iloc[0]['q75']) - float(d_ht_row.iloc[0]['q25']))}d). "
                        f"Centers {diff_str} apart; B4-anchored band ~6x tighter."
                    )
            except Exception as e:
                print(f"  (qualitative cross-ref note skipped: {e})")
    for i, note in enumerate(notes):
        fig.add_annotation(
            x=0.0, y=-0.06 - i * 0.035, xref='paper', yref='paper',
            text=note, showarrow=False,
            font=dict(size=9, color='#b0bdc7'),
            bgcolor='rgba(20,26,40,0.9)',
            align='left',
        )

    fig.update_layout(
        title=dict(text='C6 — BTC Next-Cycle (C5) Price Predictions — 2-stage model, observed C4 top',
                   font=dict(size=14, color='#e6edf3')),
        template='plotly_dark',
        paper_bgcolor='#0a0e1a', plot_bgcolor='#0a0e1a',
        font=dict(color='#e6edf3'),
        height=1000,
        showlegend=False,
        margin=dict(t=80, b=140, l=80),
    )

    _safe_write_html(fig, CHARTS_DIR / 'C6.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C6.png', scale=2)
    print("  C6 done")
    print(f"    {anchor_note}")
    print(f"    C5 TOP ${c5_top_low:,.0f}–${c5_top_high:,.0f} (center ${c5_top_center:,.0f})")
    print(f"    B5 ${b5_low:,.0f}–${b5_high:,.0f} (center ${b5_center:,.0f})")


# --- C7: Backtest-by-cycle error ---
def build_c7():
    bt = backtest[backtest['statistic'] == 'D_halving_to_top']

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=bt['actual_value'], y=bt['predicted_mean'],
        mode='markers+text', name='LOOCO predictions',
        text=bt['leave_out_cycle'], textposition='top center',
        marker=dict(size=12, color='#1f77b4'),
    ))

    # Perfect prediction line
    mn = min(bt['actual_value'].min(), bt['predicted_mean'].min()) - 20
    mx = max(bt['actual_value'].max(), bt['predicted_mean'].max()) + 20
    fig.add_trace(go.Scatter(
        x=[mn, mx], y=[mn, mx],
        mode='lines', name='Perfect prediction',
        line=dict(dash='dash', color='gray', width=1),
    ))

    fig.update_layout(
        title='C7 — LOOCO Backtest: D_halving_to_top',
        xaxis_title='Actual (days)', yaxis_title='Predicted (days)',
        template='plotly_dark', height=500,
    )
    _safe_write_html(fig, CHARTS_DIR / 'C7.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C7.png', scale=2)
    print("  C7 done")


# --- C8: Per-asset next-cycle zone map ---
ASSET_DISPLAY = {
    'eth': ('ETH', '#7952b3'),
    'xrp': ('XRP', '#e2725b'),
    'sol': ('SOL', '#3aa856'),
    'mstr': ('MSTR', '#ff6b35'),
    'wgmi': ('WGMI', '#eab308'),
    'spx': ('SPX', '#1f77b4'),
    'ndx': ('NDX', '#17becf'),
    'dxy': ('DXY', '#8c564b'),
    'tlt': ('TLT', '#bcbd22'),
    'gold': ('GOLD', '#d4af37'),
}


def _build_alt_chart(asset, filename, title, subtitle):
    """Build an individual alt-coin chart (like C6 for BTC) with zones + markers."""
    label, color = ASSET_DISPLAY[asset]
    # Resolve the latest raw snapshot per asset via globbing rather than
    # hard-coding stale file dates.
    _raw_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    cands = sorted(_raw_dir.glob(f'{asset}_yahoo_*.csv'))
    if not cands:
        raise FileNotFoundError(f"No raw snapshot for {asset}")
    asset_file = str(cands[-1])
    df = pd.read_csv(asset_file, parse_dates=['date']).sort_values('date')
    df = df[df['close'] > 0]
    sub = alt_zones[alt_zones['asset'] == asset]

    # Visible (zoomed) price window: matches x-axis range [2022-01-01, 2031-12-31].
    # The full pre-2022 history is NOT plotted (it dilates the log y-axis and
    # compresses the visible portion — see C8a/b/c layout fix).
    PRICE_ZOOM_START = '2022-01-01'
    df_zoom = df[df['date'] >= PRICE_ZOOM_START]
    if len(df_zoom) < 2:
        df_zoom = df.tail(200)
    zoom_min = df_zoom['close'].min()
    zoom_max = df_zoom['close'].max()
    # Explicit y-range so Plotly does not auto-scale to zone bands.
    # Base range tracks observed history. We extend the upper bound to
    # include the highest *meaningful* prediction band on the chart (C5 TOP
    # high edge) so the band + its marker are not clipped. Lower bound is
    # kept at 0.7 * zoom_min to leave room for the B4 marker below the
    # observed price axis.
    y_low = zoom_min * 0.7
    band_max = 0.0
    for _, z in sub.iterrows():
        try:
            ph = float(z.get('price_high', '') or 0)
            if z.get('zone') in ('distribution', 'bear_bottom', 'exit') and ph > 0:
                band_max = max(band_max, ph)
        except (ValueError, TypeError):
            pass
    y_high = max(zoom_max * 1.3, band_max * 1.05 if band_max > 0 else zoom_max * 1.3)

    fig = go.Figure()

    # BTC event vertical lines
    btc_evts = []
    h4_date = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H4')].iloc[0]['date'])
    btc_evts.append((h4_date, '#4ade80', 'dash', 'H4'))
    h5_date = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H5')].iloc[0]['date'])
    btc_evts.append((h5_date, '#4ade80', 'dash', 'H5'))
    btc_post_h4 = btc[btc['date'] >= '2024-04-20']
    if len(btc_post_h4) > 0:
        peak_idx = btc_post_h4['close'].idxmax()
        btc_peak_d = btc_post_h4.loc[peak_idx, 'date'].strftime('%Y-%m-%d')
        btc_evts.append((btc_peak_d, '#facc15', 'dot', 'BTC C4 top'))
    for evt_date, evt_color, evt_dash, evt_label in btc_evts:
        fig.add_shape(type='line', x0=evt_date, x1=evt_date, y0=0, y1=1,
                      yref='paper', line=dict(color=evt_color, dash=evt_dash, width=1),
                      opacity=0.45, layer='above')
        fig.add_annotation(x=evt_date, y=1.01, yref='paper', text=f'<b>{evt_label}</b>',
                           showarrow=False, font=dict(size=8, color=evt_color),
                           bgcolor='rgba(10,14,26,0.7)')

    # Projected B4 vertical line (when bear_bottom zone exists with valid dates)
    b4_row = sub[sub['zone'] == 'bear_bottom']
    if not b4_row.empty:
        b4_os = str(b4_row.iloc[0].get('outer_start', ''))
        b4_oe = str(b4_row.iloc[0].get('outer_end', ''))
        if b4_os and b4_oe and b4_os != 'nan' and b4_oe != 'nan':
            b4_mid = (pd.to_datetime(b4_os) + (pd.to_datetime(b4_oe) - pd.to_datetime(b4_os)) / 2)
            b4_mid_str = b4_mid.strftime('%Y-%m-%d')
            fig.add_shape(type='line', x0=b4_mid_str, x1=b4_mid_str, y0=0, y1=1,
                          yref='paper', line=dict(color='#22d3ee', dash='dot', width=1),
                          opacity=0.5, layer='above')
            fig.add_annotation(x=b4_mid_str, y=1.01, yref='paper',
                               text='<b>B4 proj</b>', showarrow=False,
                               font=dict(size=8, color='#22d3ee'),
                               bgcolor='rgba(10,14,26,0.7)')

    # Zone shading (vertical bands with top labels — matches C6)
    zone_fill = {'accumulation': 'rgba(74,222,128,0.06)',
                 'distribution': 'rgba(251,146,60,0.10)',
                 'exit': 'rgba(96,165,250,0.10)',
                 'bear_bottom': 'rgba(34,211,238,0.06)'}
    for _, z in sub.iterrows():
        zone = z['zone']
        os_ = str(z.get('outer_start', ''))
        oe_ = str(z.get('outer_end', ''))
        if os_ and oe_ and os_ != 'nan' and oe_ != 'nan':
            fig.add_vrect(x0=os_, x1=oe_, fillcolor=zone_fill.get(zone, 'gray'),
                          line_width=0, layer='below')
            fig.add_annotation(x=os_, y=0.97, yref='paper',
                               text=f"<b>{zone.upper()}</b>", showarrow=False,
                               font=dict(size=7, color='white'), xanchor='left', xshift=2)

    # Price band rectangles + triangle markers + arrow annotations (C6 style)
    def fmt_price(p):
        if p >= 1e6: return f'${p/1e6:.1f}M'
        if p >= 1e5: return f'${p/1e3:.0f}k'
        if p >= 1e3: return f'${p/1e3:.1f}k'
        if p >= 100: return f'${p:,.0f}'
        if p >= 1: return f'${p:,.2f}'
        return f'${p:.2f}'

    # (zone_name, color, marker_symbol, marker_size, band_label, arrow_color)
    _band_styles = {
        'bear_bottom': ('#22d3ee', 'triangle-up',  14, 'B4 (proj bear bottom)', '#22d3ee'),
        'distribution': ('#facc15', 'triangle-down', 14, 'C5 TOP (proj cycle peak)', '#facc15'),
        'exit':         ('#60a5fa', 'triangle-up',  12, 'B5 (proj next bear bottom)', '#60a5fa'),
    }

    for _, z in sub.iterrows():
        zone = z['zone']
        if not z.get('price_low') or not z.get('price_high'):
            continue
        try:
            p_lo = float(z['price_low'])
            p_hi = float(z['price_high'])
            if p_lo <= 0 or p_hi <= 0:
                continue
            if abs(p_hi - p_lo) / max(p_lo, 1e-10) < 0.01:
                continue
        except (ValueError, TypeError):
            continue
        x0 = str(z['outer_start'])
        x1 = str(z['outer_end'])
        if not x0 or not x1 or x0 == 'nan' or x1 == 'nan':
            continue
        if p_lo > y_high or p_hi < y_low:
            continue

        color, marker_sym, marker_sz, band_label, arrow_col = _band_styles.get(
            zone, ('#888', 'circle', 10, zone, '#888'))

        p_mid = (p_lo + p_hi) / 2

        # Band rectangle
        fig.add_shape(type='rect', x0=x0, x1=x1, y0=p_lo, y1=p_hi,
                      fillcolor=f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.25)',
                      line=dict(color=color, width=2), layer='below')

        # Center line
        fig.add_trace(go.Scatter(x=[x0, x1], y=[p_mid, p_mid], mode='lines',
                      line=dict(color=color, width=2), showlegend=False,
                      hovertemplate=f'{band_label}<br>${p_mid:,.2f}<extra></extra>'))

        # Triangle marker at zone midpoint
        mid_dt = (pd.to_datetime(x0) + (pd.to_datetime(x1) - pd.to_datetime(x0)) / 2)
        mid_str = mid_dt.strftime('%Y-%m-%d')
        fig.add_trace(go.Scatter(
            x=[mid_str], y=[p_mid], mode='markers', name=band_label,
            marker=dict(symbol=marker_sym, size=marker_sz, color=color,
                        line=dict(color='white', width=1.5)),
            hovertemplate=f'{band_label}<br>{mid_str}<br>${p_mid:,.2f}<br>'
                          f'band {fmt_price(p_lo)}–{fmt_price(p_hi)}<extra></extra>',
            showlegend=False))

        # Arrow annotation at band right edge
        fit_used = z.get('compression_fit_used', '')
        fit_note = ''
        if fit_used == 'naive_median':
            fit_note = ' <i>(naive med)</i>'
        cross_chk = z.get('cross_check_ok', '')
        chk_note = ''
        if cross_chk in ('True', 'False'):
            chk_note = f" <i>x-check {'OK' if cross_chk=='True' else 'FAIL'}</i>"
        fig.add_annotation(
            x=x1, y=p_mid, xref='x', yref='y',
            text=(f"<b>{band_label}</b><br>"
                  f"{fmt_price(p_lo)} – {fmt_price(p_hi)}<br>"
                  f"(center {fmt_price(p_mid)}){fit_note}{chk_note}"),
            showarrow=True, arrowhead=2, arrowcolor=arrow_col,
            ax=-55, ay=0,
            font=dict(size=10, color='#ffffff'),
            bgcolor='rgba(10,14,26,0.90)', borderpad=4,
            xanchor='right', yanchor='middle')

    # Gold-specific: bull market support band (20-mo SMA / 21-mo EMA) overlay.
    # Populated only for gold (support_band_low/high columns on the bear_bottom
    # row of alt_next_cycle_zones.csv). Rendered as a horizontal shaded rect
    # spanning the chart's x-range so the projected B4 can be visually compared
    # against gold's validated support floor (docs/gold_seasonality.md).
    bb_row = sub[sub['zone'] == 'bear_bottom']
    if not bb_row.empty:
        sb_lo = bb_row.iloc[0].get('support_band_low', '')
        sb_hi = bb_row.iloc[0].get('support_band_high', '')
        if sb_lo and sb_hi:
            try:
                sb_lo_f, sb_hi_f = float(sb_lo), float(sb_hi)
                fig.add_shape(type='rect', x0='2022-01-01', x1='2031-12-31',
                              y0=sb_lo_f, y1=sb_hi_f,
                              fillcolor='rgba(212,175,55,0.10)',
                              line=dict(color='#d4af37', width=2, dash='dot'),
                              layer='below')
                sb_mid = (sb_lo_f + sb_hi_f) / 2
                fig.add_trace(go.Scatter(
                    x=['2022-01-01', '2031-12-31'], y=[sb_mid, sb_mid],
                    mode='lines', name='Gold support band (20-mo SMA/21-mo EMA)',
                    line=dict(color='#d4af37', width=1.5, dash='dot'),
                    hovertemplate='Gold support band<br>20-mo SMA / 21-mo EMA<br>'
                                  f'${sb_lo_f:,.2f} – ${sb_hi_f:,.2f}<extra></extra>',
                    showlegend=False))
                fig.add_annotation(
                    x='2022-01-01', y=sb_hi_f, xref='x', yref='y',
                    text=f'<b>Support band ${sb_lo_f:,.0f}–${sb_hi_f:,.0f}</b>',
                    showarrow=False, font=dict(size=9, color='#d4af37'),
                    bgcolor='rgba(10,14,26,0.85)', xanchor='left', xshift=4, yshift=4)
            except (ValueError, TypeError):
                pass

    # Asset price line (zoomed to visible window — full pre-2022 history omitted)
    fig.add_trace(go.Scatter(
        x=df_zoom['date'].dt.strftime('%Y-%m-%d'), y=df_zoom['close'],
        customdata=df_zoom['close'], mode='lines', name=label,
        line=dict(color=color, width=2.5),
        hovertemplate=f'{label} %{{x}}<br>$%{{customdata:,.2f}}<extra></extra>'))

    # Observed C4 top only (the only confirmed cycle event so far)
    c4_row = alt_metrics[(alt_metrics['asset'] == asset) & (alt_metrics['cycle_id'] == 'C4')]
    c4_top_date = None
    c4_top_price = None
    if not c4_row.empty:
        tp = _to_float(c4_row.iloc[0].get('asset_local_top_price'))
        td = c4_row.iloc[0].get('asset_local_top_date', '')
        if tp and tp > 0 and td:
            c4_top_date = td
            c4_top_price = tp
            fig.add_trace(go.Scatter(x=[td], y=[tp], mode='markers',
                marker=dict(symbol='triangle-down', size=10, color=color,
                            line=dict(color='white', width=1)),
                hovertemplate=f"C4 top (observed)<br>{td}<br>${tp:,.2f}<extra></extra>",
                showlegend=False))
            fig.add_annotation(x=td, y=tp, text=f'<b>C4 top ${tp:,.0f}</b>',
                showarrow=True, arrowhead=2, arrowcolor=color,
                ax=40, ay=-20, font=dict(size=9, color=color),
                bgcolor='rgba(10,14,26,0.85)', borderpad=2)

    # Observed bear bottom (B4) — when the cycle metrics already detected the
    # post-C4-top bear bottom, plot it as a distinct green diamond so the chart
    # makes it visually clear that the bottom is in (vs only showing the B4
    # *projection* band). Sourced from alt_cycle_metrics.csv's
    # asset_next_bear_bottom_date/price on the C4 row.
    # Skip for assets in FORCE_BORROW_ASSETS (e.g. WGMI) whose "detected" bottom
    # is premature/unconfirmed — the asset is still actively falling and the
    # local minimum found so far is not a confirmed bear bottom.
    # NOTE (2026-08-04): MSTR removed — its naive_median_own_dd model now
    # publishes a B4 band from its own dd series, so the detected B4 marker
    # (if still flagged by Rule B) can be shown alongside the projection.
    FORCE_BORROW_ASSETS = {"wgmi"}
    if (c4_row is not None and not c4_row.empty
            and asset not in FORCE_BORROW_ASSETS):
        bd = c4_row.iloc[0].get('asset_next_bear_bottom_date', '')
        bp = _to_float(c4_row.iloc[0].get('asset_next_bear_bottom_price'))
        if bd and bp and bp > 0:
            fig.add_trace(go.Scatter(x=[bd], y=[bp], mode='markers',
                marker=dict(symbol='diamond', size=11, color='#22c55e',
                            line=dict(color='white', width=1.5)),
                hovertemplate=f"B4 detected<br>{bd}<br>${bp:,.2f}<extra></extra>",
                showlegend=False))
            fig.add_annotation(x=bd, y=bp, text=f'<b>B4 detected ${bp:,.0f}</b>',
                showarrow=True, arrowhead=2, arrowcolor='#22c55e',
                ax=-40, ay=25, font=dict(size=9, color='#22c55e'),
                bgcolor='rgba(10,14,26,0.85)', borderpad=2)

    # Y-axis — log scale with dollar-formatted ticks + explicit range
    # (explicit range prevents Plotly auto-scaling to zone bands / outliers)
    y_ticks = log_to_usd_ticks(np.log(y_low), np.log(y_high), num_ticks=10)
    fig.update_layout(
        yaxis=dict(type='log', range=[np.log10(y_low), np.log10(y_high)],
                   tickvals=y_ticks['tickvals'], ticktext=y_ticks['ticktext'],
                   tickfont=dict(size=11, color='#b0bdc7'), gridcolor='#2a3349',
                   showgrid=True, zeroline=False, automargin=True,
                   title_text='Price (USD)',
                   title_font=dict(size=12, color='#b0bdc7')),
        xaxis=dict(type='date', range=['2022-01-01', '2031-12-31'],
                   dtick='M24', tickformat='%Y', tickangle=-45,
                   gridcolor='#2a3349', showgrid=True,
                   tickfont=dict(size=10, color='#b0bdc7')),
    )

    # --- Bottom anchor / model notes (mirrors C6 BTC chart) ---
    fit_used = ''
    if not sub.empty:
        fit_used = str(sub.iloc[0].get('compression_fit_used', '') or '')
    cross_chk = ''
    if not sub.empty:
        cross_chk = str(sub.iloc[0].get('cross_check_ok', '') or '')

    notes = []
    # Note 1: data window
    notes.append(
        f"{label} price shown: {PRICE_ZOOM_START} to {df_zoom['date'].max().strftime('%Y-%m-%d')} "
        f"(pre-2022 history omitted — dilates log axis). "
        f"Visible range: ${y_low:,.2f} – ${y_high:,.2f}."
    )
    # Note 2: model used
    if fit_used == '2_stage_with_observed_c4':
        ck = 'OK' if cross_chk == 'True' else 'FAIL'
        notes.append(
            "Model: 2-stage projection anchored on observed C4 top. "
            "Stage 1 fits B/B ratio (power-law) -> B4; Stage 2 fits multiplier -> C5 top. "
            f"Cross-check: {ck}."
        )
    elif fit_used == 'borrowed_2_stage_from_BTC':
        notes.append(
            "Model: borrowed 2-stage from BTC. Asset's own history (n_bear_bottoms < 4 "
            "or n_mults < 3 or n_drawdowns < 3) is insufficient for a power-law fit. "
            "Anchor = asset's observed C4 top. Relative shape (drawdown depth at C4, "
            "bottom-to-peak multiplier at C5) borrowed from BTC's 3 observed cycles."
        )
    elif fit_used == 'naive_median':
        notes.append(
            "Model: naive median (insufficient bear-bottom history for power-law fit). "
            "No B4 (bear bottom) band available; only distribution zone envelope shown."
        )
    elif fit_used == 'macro_2_stage_own_shape':
        notes.append(
            "Model: I-19 macro cycle-tied 2-stage. Anchor = own observed C4 top. "
            "Shape (drawdown depth at C4, bottom-to-peak multiplier at C5) fit "
            "on the macro's OWN series (n=3 from C1-C3). Economic floors relaxed "
            "to macro levels (dd>=5%, mult>=1.05x); B4 band drawdown clamped to "
            "the macro's observed dd range. See docs/blockers/I-19-macro-2stage.md."
        )
    elif fit_used == 'macro_not_cycle_tied':
        notes.append(
            "Model: historical envelope only (macro asset, NOT cycle-tied). "
            "No B4 / C5 projection."
        )
    else:
        notes.append(f"Model: {fit_used or 'n/a'}.")
    # Gold support band note (bull market 20-mo SMA / 21-mo EMA floor)
    if not bb_row.empty:
        sb_lo = bb_row.iloc[0].get('support_band_low', '')
        sb_hi = bb_row.iloc[0].get('support_band_high', '')
        if sb_lo and sb_hi:
            notes.append(
                "Gold bull-market support band (validated in docs/gold_seasonality.md): "
                f"20-mo SMA + 21-mo EMA = ${float(sb_lo):,.2f} – ${float(sb_hi):,.2f}. "
                "Held every gold correction since 2015; the projected B4 (drawdown "
                "path) is cross-checked against this floor."
            )
    # Note 3: zones summary
    zone_summary_parts = []
    for _, z in sub.iterrows():
        zname = z['zone']
        pl = z.get('price_low')
        ph = z.get('price_high')
        os_ = str(z.get('outer_start', '') or '')
        oe_ = str(z.get('outer_end', '') or '')
        if os_ and oe_ and os_ != 'nan' and oe_ != 'nan':
            if pd.notna(pl) and pd.notna(ph):
                try:
                    plf, phf = float(pl), float(ph)
                except (TypeError, ValueError):
                    plf, phf = 0.0, 0.0
                if plf > 0 and phf > 0:
                    zone_summary_parts.append(
                        f"{zname}({os_[:10]}–{oe_[:10]}): ${plf:,.2f}–${phf:,.2f}"
                    )
                else:
                    zone_summary_parts.append(f"{zname}({os_[:10]}–{oe_[:10]}): envelope only")
            else:
                zone_summary_parts.append(f"{zname}({os_[:10]}–{oe_[:10]}): envelope only")
    if zone_summary_parts:
        notes.append("Zones: " + " | ".join(zone_summary_parts))

    # Note 4: B4 detected vs BTC projection — alt-leads-BTC pattern
    # When the asset's bear bottom has already been detected (alt_cycle_metrics
    # has asset_next_bear_bottom_date on the C4 row), surface a note comparing
    # it to BTC's projected B4 zone center. Historically alts have bottomed
    # 1-5 months before BTC (e.g. C3: ETH/XRP bottomed Jun-2022, BTC Nov-2022,
    # ~156d lead). This makes it visually clear why the alt's bottom is already
    # in even though BTC's B4 is still projected.
    if (c4_row is not None and not c4_row.empty
            and c4_top_date and c4_top_price):
        bd = c4_row.iloc[0].get('asset_next_bear_bottom_date', '')
        bp = _to_float(c4_row.iloc[0].get('asset_next_bear_bottom_price'))
        if bd and bp and bp > 0:
            d_tnb_actual = None
            try:
                d_tnb_actual = (pd.to_datetime(bd) - pd.to_datetime(c4_top_date)).days
            except Exception:
                pass
            # BTC projected B4 zone center (median of next_cycle_zones bear_bottom)
            btc_zones_df = zones  # 'zones' is the BTC next_cycle_zones DataFrame
            btc_bb = btc_zones_df[btc_zones_df['zone'] == 'bear_bottom']
            if not btc_bb.empty:
                btc_b4_start = pd.to_datetime(btc_bb.iloc[0]['base_start'])
                btc_b4_end = pd.to_datetime(btc_bb.iloc[0]['base_end'])
                btc_b4_center = btc_b4_start + (btc_b4_end - btc_b4_start) / 2
                btc_b4_str = btc_b4_center.strftime('%Y-%m-%d')
                lead_days = (pd.to_datetime(bd) - btc_b4_center).days
                lead_txt = (f"{abs(lead_days)}d earlier" if lead_days < 0
                            else f"{lead_days}d later")
                notes.append(
                    f"B4 detected: {bd} @ ${bp:,.2f}"
                    f"{' (' + str(d_tnb_actual) + 'd after C4 top)' if d_tnb_actual else ''}. "
                    f"BTC B4 projected: {btc_b4_str} ({label} leads BTC by {lead_txt}). "
                    f"Historical pattern: alts bottom 1-5 months before BTC (C3: "
                    f"ETH/XRP ~156d before BTC)."
                )

    for i, note in enumerate(notes):
        fig.add_annotation(
            x=0.0, y=-0.05 - i * 0.04, xref='paper', yref='paper',
            text=note, showarrow=False,
            font=dict(size=9, color='#b0bdc7'),
            bgcolor='rgba(20,26,40,0.9)',
            align='left',
        )

    fig.update_layout(
        title=dict(text=title + '<br><sub>' + subtitle + '</sub>',
                   font=dict(size=14, color='#e6edf3')),
        template='plotly_dark', paper_bgcolor='#0a0e1a', plot_bgcolor='#0a0e1a',
        font=dict(color='#e6edf3'), height=700,
        autosize=True,
        showlegend=False, margin=dict(t=80, b=170, l=90, r=40),
    )
    _safe_write_html(fig, CHARTS_DIR / filename, config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / filename.replace('.html', '.png'), scale=2)
    print(f"  {filename.replace('.html','')} done")


def build_c8_eth():
    """C8a — ETH individual next-cycle projection chart."""
    _build_alt_chart('eth', 'C8.html',
        'C8a — ETH Next-Cycle (C5) Price Prediction',
        'Borrowed 2-stage from BTC: anchor = observed C4 top ($4,836); shape (drawdown, multiplier) borrowed from BTC cycles 1-3.')


def build_c8_xrp():
    """C8b — XRP individual next-cycle projection chart."""
    _build_alt_chart('xrp', 'C8b.html',
        'C8b — XRP Next-Cycle (C5) Price Prediction',
        'Borrowed 2-stage from BTC: anchor = observed C4 top ($3.55); shape (drawdown, multiplier) borrowed from BTC cycles 1-3 (XRP has <3 own bear bottoms).')


def build_c8_sol():
    """C8c — SOL individual next-cycle projection chart."""
    _build_alt_chart('sol', 'C8c.html',
        'C8c — SOL Next-Cycle (C5) Price Prediction',
        'Borrowed 2-stage from BTC: anchor = observed C4 top ($261.82); shape (drawdown, multiplier) borrowed from BTC cycles 1-3 (SOL has <3 own bear bottoms).')


def build_c8_mstr():
    """C8e — MSTR individual next-cycle projection chart."""
    _build_alt_chart('mstr', 'C8e.html',
        'C8e — MSTR Next-Cycle (C5) Price Prediction',
        'Naive median on own dd/mult series (n=2 cycles C3+C4). Anchor = observed C4 top ($473.83); B4 via own dd median [0.826, 0.893]; C5 via own mult median [13.8, 34.7]. BTC borrowed shape retired for MSTR (its compressing dd curve under-estimates MSTR\'s higher volatility).')


def build_c8_wgmi():
    """C8f — WGMI individual next-cycle projection chart."""
    _build_alt_chart('wgmi', 'C8f.html',
        'C8f — WGMI Next-Cycle (C5) Price Prediction',
        'Borrowed 2-stage from BTC: anchor = observed C4 top; shape (drawdown, multiplier) borrowed from BTC cycles 1-3. MARA proxy for pre-launch cycles C1-C3 (WGMI is the CoinShares Bitcoin Miners ETF; MARA is the largest full-cycle-history miner in the basket).')


def build_c8_gold():
    """C8g — GOLD (GC=F) individual next-cycle projection chart.

    Gold joins the macro asset set (I-19 macro 2-stage, mode='macro_2_stage_own_shape').
    Rendered like the crypto single-asset C8a-c charts (log y-axis; gold spans
    ~$270 in 2000 to ~$5,500 in 2026), with an extra overlay: the validated
    bull-market support band (20-month SMA / 21-month EMA on monthly closes)
    shown as a shaded horizontal rectangle so the projected B4 can be compared
    against gold's empirical floor. See docs/gold_seasonality.md.
    """
    _build_alt_chart('gold', 'C8g.html',
        'C8g — GOLD (GC=F) Next-Cycle (C5) Price Prediction',
        'I-19 macro 2-stage (own shape): anchor = observed C4 top; shape fit on gold\'s own dd/mult series. Overlay: validated bull-market support band (20-mo SMA + 21-mo EMA).')


def build_c8_macro():
    """C8d — Macro assets (SPX/NDX/DXY/TLT) cycle-tied projection (I-19).

    Each macro gets its own panel with the full 4-zone map
    (B4 bear_bottom -> accumulation -> distribution = C5 top -> exit = B5)
    rendered the same way as the crypto C8a-c charts, but with LINEAR y-axis
    (macros historically range 1.1x-2.8x multipliers and 8-50% drawdowns, so
    log scale would compress the action). Reuses _project_asset_chain
    output: mode='macro_2_stage_own_shape' since I-19.
    """
    from plotly.subplots import make_subplots
    assets = ['spx', 'ndx', 'dxy', 'tlt']
    fig = make_subplots(rows=len(assets), cols=1, shared_xaxes=False,
                        subplot_titles=[f"<b>{ASSET_DISPLAY[a][0]}</b> — Cycle-tied 2-stage (I-19)" for a in assets],
                        vertical_spacing=0.06)

    # Resolve the latest raw snapshot per asset (mirror the pattern used by
    # _build_alt_chart). We glob rather than hard-code a date so refreshes
    # never produce a stale-source chart.
    RAW_DIR = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    asset_files = {}
    for a in assets:
        cands = sorted(RAW_DIR.glob(f'{a}_yahoo_*.csv'))
        if not cands:
            raise FileNotFoundError(f"No raw snapshot for {a}")
        asset_files[a] = str(cands[-1])

    btc_evts = []
    h4_date = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H4')].iloc[0]['date'])
    btc_evts.append((h4_date, '#4ade80', 'dash', 'H4'))
    h5_date = str(events[(events['event_type'] == 'halving') & (events['cycle_id'] == 'H5')].iloc[0]['date'])
    btc_evts.append((h5_date, '#4ade80', 'dash', 'H5'))
    btc_post_h4 = btc[btc['date'] >= '2024-04-20']
    if len(btc_post_h4) > 0:
        peak_idx = btc_post_h4['close'].idxmax()
        btc_peak_d = btc_post_h4.loc[peak_idx, 'date'].strftime('%Y-%m-%d')
        btc_evts.append((btc_peak_d, '#facc15', 'dot', 'BTC C4 top'))

    zone_fill = {'accumulation': 'rgba(74,222,128,0.06)',
                 'distribution': 'rgba(251,146,60,0.10)',
                 'exit': 'rgba(96,165,250,0.10)',
                 'bear_bottom': 'rgba(34,211,238,0.06)'}
    _band_styles = {
        'bear_bottom': ('#22d3ee', 'triangle-up',  12, 'B4 (proj bear bottom)'),
        'distribution': ('#facc15', 'triangle-down', 12, 'C5 TOP (proj cycle peak)'),
        'exit':         ('#60a5fa', 'triangle-up',  10, 'B5 (proj next bear bottom)'),
    }

    def fmt_price_macro(p):
        if p >= 1e5: return f'${p/1e3:.0f}k'
        if p >= 1e3: return f'${p/1e3:.1f}k'
        if p >= 100: return f'${p:,.0f}'
        if p >= 1:   return f'${p:,.2f}'
        return f'${p:.2f}'

    notes_per_asset = {}
    for row_idx, asset in enumerate(assets, start=1):
        label, color = ASSET_DISPLAY[asset]
        df = pd.read_csv(asset_files[asset], parse_dates=['date']).sort_values('date')
        df = df[df['close'] > 0]
        PRICE_ZOOM_START = '2022-01-01'
        df_zoom = df[df['date'] >= PRICE_ZOOM_START]
        if len(df_zoom) < 2:
            df_zoom = df.tail(200)
        sub = alt_zones[alt_zones['asset'] == asset]
        xref = f'x{row_idx}' if row_idx > 1 else 'x'
        yref = f'y{row_idx}' if row_idx > 1 else 'y'

        zoom_min = df_zoom['close'].min() if len(df_zoom) > 0 else df['close'].min()
        zoom_max = df_zoom['close'].max() if len(df_zoom) > 0 else df['close'].max()
        # Extend y-range to include the highest distribution/exit band.
        band_max = 0.0
        band_min_positive = float('inf')
        for _, z in sub.iterrows():
            try:
                ph = float(z.get('price_high', '') or 0)
                pl = float(z.get('price_low', '') or 0)
                if z.get('zone') in ('distribution', 'bear_bottom', 'exit') and ph > 0:
                    band_max = max(band_max, ph)
                if z.get('zone') in ('bear_bottom', 'exit') and pl > 0:
                    band_min_positive = min(band_min_positive, pl)
            except (ValueError, TypeError):
                pass
        y_low = min(zoom_min * 0.7, band_min_positive * 0.85 if band_min_positive != float('inf') else zoom_min * 0.7)
        y_high = max(zoom_max * 1.3, band_max * 1.05 if band_max > 0 else zoom_max * 1.3)

        # Zone shading (vertical bands)
        for _, z in sub.iterrows():
            zone = z['zone']
            os_ = str(z.get('outer_start', ''))
            oe_ = str(z.get('outer_end', ''))
            if os_ and oe_ and os_ != 'nan' and oe_ != 'nan':
                fig.add_vrect(x0=os_, x1=oe_, row=row_idx, col=1,
                              fillcolor=zone_fill.get(zone, 'gray'),
                              line_width=0, layer='below')
                fig.add_annotation(x=os_, y=0.97, yref='paper', row=row_idx, col=1,
                                   text=f"<b>{zone.upper()}</b>", showarrow=False,
                                   font=dict(size=7, color='white'), xanchor='left', xshift=2)

        # Price band rectangles + triangle markers
        for _, z in sub.iterrows():
            zone = z['zone']
            if not z.get('price_low') or not z.get('price_high'):
                continue
            try:
                p_lo = float(z['price_low'])
                p_hi = float(z['price_high'])
                if p_lo <= 0 or p_hi <= 0:
                    continue
                if abs(p_hi - p_lo) / max(p_lo, 1e-10) < 0.01:
                    continue
            except (ValueError, TypeError):
                continue
            x0 = str(z['outer_start'])
            x1 = str(z['outer_end'])
            if not x0 or not x1 or x0 == 'nan' or x1 == 'nan':
                continue
            if p_lo > y_high or p_hi < y_low:
                continue

            color, marker_sym, marker_sz, band_label = _band_styles.get(
                zone, ('#888', 'circle', 8, zone))
            p_mid = (p_lo + p_hi) / 2
            r_, g_, b_ = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

            # Band rectangle (per-subplot via xref/yref)
            fig.add_shape(type='rect', xref=xref, yref=yref,
                          x0=x0, x1=x1, y0=p_lo, y1=p_hi,
                          fillcolor=f'rgba({r_},{g_},{b_},0.25)',
                          line=dict(color=color, width=2), layer='below')
            # Center line
            fig.add_trace(go.Scatter(x=[x0, x1], y=[p_mid, p_mid], mode='lines',
                          line=dict(color=color, width=2), showlegend=False,
                          hovertemplate=f'{band_label}<br>${p_mid:,.2f}<extra></extra>',
                          xaxis=xref, yaxis=yref))
            # Triangle marker at zone midpoint
            mid_dt = (pd.to_datetime(x0) + (pd.to_datetime(x1) - pd.to_datetime(x0)) / 2)
            mid_str = mid_dt.strftime('%Y-%m-%d')
            fig.add_trace(go.Scatter(
                x=[mid_str], y=[p_mid], mode='markers', name=band_label,
                marker=dict(symbol=marker_sym, size=marker_sz, color=color,
                            line=dict(color='white', width=1.5)),
                hovertemplate=f'{band_label}<br>{mid_str}<br>${p_mid:,.2f}<br>'
                              f'band {fmt_price_macro(p_lo)}-{fmt_price_macro(p_hi)}<extra></extra>',
                showlegend=False, xaxis=xref, yaxis=yref))
            # Arrow annotation at band right edge
            fig.add_annotation(
                x=x1, y=p_mid, xref=xref, yref=yref,
                text=(f"<b>{band_label}</b><br>"
                      f"{fmt_price_macro(p_lo)} - {fmt_price_macro(p_hi)}<br>"
                      f"(center {fmt_price_macro(p_mid)})"),
                showarrow=True, arrowhead=2, arrowcolor=color,
                ax=-55, ay=0,
                font=dict(size=10, color='#ffffff'),
                bgcolor='rgba(10,14,26,0.90)', borderpad=4,
                xanchor='right', yanchor='middle')

        # Price line
        fig.add_trace(go.Scatter(
            x=df_zoom['date'].dt.strftime('%Y-%m-%d'), y=df_zoom['close'],
            customdata=df_zoom['close'], mode='lines', name=label,
            line=dict(color=color, width=2.5),
            hovertemplate=f'{label} %{{x}}<br>$%{{customdata:,.2f}}<extra></extra>',
            showlegend=False), row=row_idx, col=1)

        # Observed C4 top marker (the only confirmed cycle event so far for macros)
        c4_row = alt_metrics[(alt_metrics['asset'] == asset) & (alt_metrics['cycle_id'] == 'C4')]
        tp = None
        td = None
        if not c4_row.empty:
            tp = _to_float(c4_row.iloc[0].get('asset_local_top_price'))
            td = c4_row.iloc[0].get('asset_local_top_date', '')
            if tp and tp > 0 and td:
                fig.add_trace(go.Scatter(
                    x=[td], y=[tp], mode='markers',
                    marker=dict(symbol='triangle-down', size=10, color=color,
                                line=dict(color='white', width=1)),
                    hovertemplate=f"C4 top (observed)<br>{td}<br>${tp:,.2f}<extra></extra>",
                    showlegend=False), row=row_idx, col=1)
                fig.add_annotation(x=td, y=tp, xref=xref, yref=yref,
                    text=f'<b>C4 top ${tp:,.0f}</b>',
                    showarrow=True, arrowhead=2, arrowcolor=color,
                    ax=40, ay=-20, font=dict(size=9, color=color),
                    bgcolor='rgba(10,14,26,0.85)', borderpad=2)

        # BTC event lines on each subplot
        for evt_date, evt_color, evt_dash, evt_label in btc_evts:
            fig.add_shape(type='line', xref=xref, yref='paper',
                          x0=evt_date, x1=evt_date, y0=0, y1=1,
                          line=dict(color=evt_color, dash=evt_dash, width=1),
                          opacity=0.35, layer='above')

        # Y-axis (linear for macros)
        fig.update_layout(**{
            f'yaxis{row_idx}' if row_idx > 1 else 'yaxis': dict(
                type='linear', range=[y_low, y_high],
                tickfont=dict(size=10, color='#b0bdc7'),
                gridcolor='#2a3349', showgrid=True, zeroline=False, automargin=True,
                title_text='Price (USD)' if row_idx == 1 else '',
                title_font=dict(size=10, color='#b0bdc7'))
        })
        fig.update_layout(**{
            f'xaxis{row_idx}' if row_idx > 1 else 'xaxis': dict(
                type='date', range=['2022-01-01', '2031-12-31'],
                dtick='M24', tickformat='%Y', tickangle=-45,
                gridcolor='#2a3349', showgrid=True,
                tickfont=dict(size=9, color='#b0bdc7'))
        })

        # Collect zone summary note for this asset (printed once at bottom)
        fit_used = str(sub.iloc[0].get('compression_fit_used', '') or '') if not sub.empty else ''
        asset_zones = []
        for _, z in sub.iterrows():
            zname = z['zone']
            pl = z.get('price_low'); ph = z.get('price_high')
            os_ = str(z.get('outer_start', '') or '')
            oe_ = str(z.get('outer_end', '') or '')
            if os_ and oe_ and os_ != 'nan' and oe_ != 'nan':
                try:
                    plf, phf = float(pl), float(ph)
                    if plf > 0 and phf > 0:
                        asset_zones.append(f"{zname}({os_[:10]}-{oe_[:10]}): ${plf:,.2f}-${phf:,.2f}")
                        continue
                except (TypeError, ValueError):
                    pass
                asset_zones.append(f"{zname}({os_[:10]}-{oe_[:10]}): envelope only")
        notes_per_asset[asset] = {
            'fit_used': fit_used,
            'zones': asset_zones,
            'c4_top': (tp, td) if (tp and td) else None,
        }

    # Bottom-of-chart summary notes (one block, summarizing all 4 macros)
    summary_lines = [
        "<b>I-19 macro cycle-tied 2-stage projection (NEW):</b> "
        "macros pivot around BTC halving events (all 4 macro tops fall 0-3y after "
        "each halving). Anchor = each macro's observed C4 top; shape (drawdown@idx=4, "
        "multiplier@idx=5) fit on the macro's OWN series (n=3 from C1-C3). "
        "Economic floors relaxed to macro levels (dd>=5%, mult>=1.05x) and B4 band "
        "clamped to the macro's observed dd range. See docs/blockers/I-19-macro-2stage.md.",
    ]
    for a in assets:
        nb = notes_per_asset.get(a, {})
        zs = nb.get('zones', [])
        c4 = nb.get('c4_top')
        line = f"<b>{ASSET_DISPLAY[a][0]}</b> [{nb.get('fit_used','?')}]: "
        if c4:
            line += f"C4 top {c4[1]} @ ${c4[0]:,.2f}. "
        if zs:
            line += " | ".join(zs)
        summary_lines.append(line)

    for i, note in enumerate(summary_lines):
        fig.add_annotation(
            x=0.0, y=-0.04 - i * 0.025, xref='paper', yref='paper',
            text=note, showarrow=False,
            font=dict(size=8, color='#b0bdc7'),
            bgcolor='rgba(20,26,40,0.9)',
            align='left',
        )

    fig.update_layout(
        title=dict(text='C8d — Macro Assets Cycle-Tied Projection (I-19)',
                   font=dict(size=14, color='#e6edf3')),
        template='plotly_dark', paper_bgcolor='#0a0e1a', plot_bgcolor='#0a0e1a',
        font=dict(color='#e6edf3'), height=2000,
        autosize=True,
        showlegend=False, margin=dict(t=80, b=160, l=90, r=40))
    fig.update_xaxes(title_text='Date', row=len(assets), col=1)
    _safe_write_html(fig, CHARTS_DIR / 'C8d.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C8d.png', scale=2)
    print("  C8d (macro, I-19) done")


# --- C9: BTC log price with per-asset local-top overlays on halving calendar ---
def build_c9():
    """C9 — BTC log price (background) with vertical markers showing each panel
    asset's detected halving-cycle-local-top date, colored by asset, with
    day-count from the most recent BTC halving (D_asset_halving_to_top).
    Demonstrates that other assets' tops also fall on a recognizable
    day-from-halving schedule relative to the BTC calendar."""
    fig = go.Figure()

    # 1. BTC log price background
    fig.add_trace(go.Scatter(
        x=btc['date'].dt.strftime('%Y-%m-%d'),
        y=np.log(btc['close']),
        customdata=btc['close'],
        mode='lines', name='BTC log price',
        line=dict(color='#999', width=1),
        hovertemplate='BTC %{x}: $%{customdata:,.0f}<extra></extra>',
    ))

    # 2. Asset local-top markers — use mode='markers' (no text overlay to avoid clutter)
    # Text shown only on hover; markers are color-coded by asset
    for asset in ['eth', 'xrp', 'sol', 'mstr', 'wgmi', 'spx', 'ndx', 'dxy', 'tlt']:
        label, color = ASSET_DISPLAY[asset]
        sub = alt_metrics[(alt_metrics['asset'] == asset) &
                          (alt_metrics['asset_local_top_date'] != '')]
        sub = sub[~sub['cycle_source'].astype(str).str.startswith('ETH_proxy')]
        if sub.empty:
            continue
        x_vals = sub['asset_local_top_date'].tolist()
        y_vals = []
        hover_text = []
        for _, r in sub.iterrows():
            p = r.get('asset_local_top_price', '')
            try:
                y_vals.append(np.log(float(p)) if p and float(p) > 0 else None)
            except (ValueError, TypeError):
                y_vals.append(None)
            d = r.get('D_asset_halving_to_top', '')
            cid = r['cycle_id']
            txt = f"{label} {cid}: {d}d" if d != '' else f"{label} {cid}"
            hover_text.append(txt)

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            customdata=[float(r.get('asset_local_top_price', 0) or 0) for _, r in sub.iterrows()],
            mode='markers', name=f"{label}",
            marker=dict(size=9, color=color, line=dict(width=1, color='#000')),
            hovertemplate='%{text}<br>$%{customdata:,.0f}<extra></extra>',
            text=hover_text,
        ))

    # 3. BTC halving anchors — simplified, no annotation overlap
    for _, m in metrics.iterrows():
        cid = m['cycle_id']
        if pd.notna(m['halving_date']) and m['halving_date']:
            fig.add_shape(type='line', x0=str(m['halving_date']), x1=str(m['halving_date']),
                          y0=0, y1=1, yref='paper',
                          line=dict(color='green', dash='dash', width=1), opacity=0.35)
            fig.add_annotation(x=str(m['halving_date']), y=0.97, yref='paper',
                               text=f"H {cid}", showarrow=False,
                               font=dict(size=8, color='#4ade80'),
                               bgcolor='rgba(10,14,26,0.7)')

    y_ticks = log_to_usd_ticks(float(np.log(btc['close'].min())),
                                float(np.log(btc['close'].max())), num_ticks=10)
    fig.update_layout(
        title='C9 — BTC Price with Per-Asset Local-Top Markers',
        xaxis_title='Date', yaxis_title='Price (USD)',
        template='plotly_dark', height=600,
        xaxis=dict(range=['2010-01-01', '2031-01-01']),
        yaxis=dict(type='log', **y_ticks),
        legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5,
                    font=dict(size=9)),
        margin=dict(t=60, b=80),
    )
    _safe_write_html(fig, CHARTS_DIR / 'C9.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C9.png', scale=2)
    print("  C9 done")


def build_c_sma():
    """C-SMA - BTC weekly close with 50w and 200w SMA valuation floors (I-18a).

    Per Cowen July-2026 memo: 200w SMA = "date with destiny" deep-value region;
    50w SMA = transition-confirmation level (2-close reclaim rule).
    Overlays colored strips showing below-200w regions (light red) and
    below-50w regions (light orange), plus callout markers for break-below
    and reclaim transitions.
    """
    if sma_floors is None:
        print("  C-SMA skipped (btc_sma_floors.csv missing)")
        return
    df = sma_floors.copy()
    # Numeric coercion (empty strings for early weeks)
    for col in ['close', 'sma_50w', 'sma_200w']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['close'], mode='lines',
        name='BTC weekly close',
        line=dict(color='#666', width=1.4),
    ))
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['sma_50w'], mode='lines',
        name='50-week SMA (transition confirm)',
        line=dict(color='#facc15', width=1.4, dash='dot'),
        connectgaps=False,
    ))
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['sma_200w'], mode='lines',
        name='200-week SMA (date with destiny)',
        line=dict(color='#22d3ee', width=1.6, dash='dash'),
        connectgaps=False,
    ))

    # Break-below / reclaim transition markers
    event_specs = [
        ('event_first_below_200w', '200w break',   '#ef4444', 'triangle-down'),
        ('event_reclaim_200w',     '200w reclaim', '#10b981', 'triangle-up'),
        ('event_first_below_50w',  '50w break',    '#f59e0b', 'triangle-down'),
        ('event_reclaim_50w',      '50w reclaim',  '#3b82f6', 'triangle-up'),
    ]
    for col, label, color, symbol in event_specs:
        evt = df[df[col] == 'True']
        if evt.empty:
            continue
        fig.add_trace(go.Scatter(
            x=evt['date'], y=evt['close'], mode='markers',
            name=label,
            marker=dict(symbol=symbol, size=10, color=color,
                        line=dict(width=1, color='#0a0e1a')),
            hovertext=[f"{label} @ {d}<br>${c:,.0f}"
                       for d, c in zip(evt['date'], evt['close'])],
            hoverinfo='text',
        ))

    # Mark the most recent (live) state for context
    last = df.iloc[-1]
    fig.add_annotation(
        x=last['date'], y=float(last['close']),
        text=(
            f"Latest wk {last['date']}<br>"
            f"close ${float(last['close']):,.0f}<br>"
            f"200w ${float(last['sma_200w']):,.0f}<br>"
            f"50w  ${float(last['sma_50w']):,.0f}"
        ),
        showarrow=True, arrowhead=1, arrowcolor='#94a3b8',
        ax=40, ay=-40,
        font=dict(size=10, color='#e2e8f0'),
        bgcolor='rgba(10,14,26,0.85)', borderpad=3,
    )

    y_ticks = log_to_usd_ticks(
        float(np.log(df['close'].min() * 0.5)),
        float(np.log(df['close'].max() * 1.5)),
    )
    fig.update_layout(
        title='C-SMA — BTC weekly close vs 50w & 200w SMA floors (I-18a)',
        xaxis_title='Date (ISO week start)', yaxis_title='Price (USD, log)',
        template='plotly_dark', height=520,
        yaxis=dict(type='log', **y_ticks),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    _safe_write_html(fig, CHARTS_DIR / 'C-SMA.html', config={'responsive': True})
    _safe_write_image(fig, CHARTS_DIR / 'C-SMA.png', scale=2)
    print("  C-SMA done")


# Build all charts
if __name__ == "__main__":
    print("Building charts...")
    build_c1()
    build_c2()
    build_c3()
    build_c4()
    build_c5()
    build_c6()
    build_c7()
    build_c8_eth()
    build_c8_xrp()
    build_c8_sol()
    build_c8_mstr()
    build_c8_wgmi()
    build_c8_macro()
    build_c8_gold()
    build_c9()
    build_c_sma()
    print("All charts built in assets/charts/")

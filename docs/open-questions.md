# Open Questions — Future Increment Candidates

These indicators are tracked as candidate future increments per
`DESIGN.md` §11 (Open Questions). They are **not** currently ingested by
the framework; this page documents what the Cowen July-2026 memo adds that
the framework does not yet reproduce, so the gap is auditable.

## 1. On-chain risk suite

MVRV Z-Score, Puell multiple, RHODL, supply in profit/loss, realized
price, balanced price. Would let us directly test our power-law-projected
B4 dates against the on-chain resets that have accompanied every prior
cycle bottom. Highest estimated value per effort.

## 2. Macro-policy overlay

Fed funds probability strip, QT-end alignment, WTI/Brent energy tail. Would
extend I-12 regime robustness to grade by real-rate direction rather than
just CPI bucket.

## 3. BTC ETF holdings

640k → 1.25M → rollover. Structural-demand bid/ask flow; needs
single-vendor data, flagged for v2.

## 4. BTC dominance ex-stables

Derivable from existing alt OHLC + a stable-coin tickers list;
rotation-vs-apathy gauge.

## 5. Midterm-year seasonality table

Trivially derivable from our existing raw BTC closes; would let us
reproduce the memo's "Aug/Sep always red" claim from our own data.

---

*Source: [Benjamin Cowen, *Bitcoin Cycle Memo* (July
2026)](https://benjamincowen.com/reports/bitcoin-cycle-memo-july-2026).
Memo-to-framework reconciliation matrix preserved in
`docs/memo-reconciliation.md`. Open indicators tracked here for v2.*

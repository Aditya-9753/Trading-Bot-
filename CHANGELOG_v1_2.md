# TradeBot Hybrid Algorithm — Change Log v1.1 → v1.2

v1.1 is kept unchanged in code as `V1_1` for regression and comparison. `V1_2` is the default.
All changes are switchable in `app/strategies/params.py` and each has a proof test.

| # | Problem in v1.1 | Fix in v1.2 | Evidence (synthetic, 2000 bars) | Test |
|---|---|---|---|---|
| 1 | Entry ±0.55 structurally unreachable: in TRENDING, contrarian RSI + MeanRev pull against Trend/Momentum; max S ≈ 0.50 | New regime weights; reversion weight 0.05 in TRENDING, 0.65 in SIDEWAYS. Entry threshold **unchanged** at 0.55 | bars with \|S\| ≥ 0.55: 0.2% → 8.8%; trades: 0 → 14 | `test_v1_2_entry_threshold_reachable` (5 seeds), `test_v1_2_trades_at_spec_thresholds...` |
| 2 | Momentum divides a 20-bar return by a 1-bar std → ≈√20 too large, saturated | `tanh(R_20 / (STD(R,20)·√20))` | saturated bars: 69.5% → 10.7% | `test_v1_2_momentum_not_saturated` |
| 3 | `tanh(VolRatio−1)` added to directional S: high vol = bullish, calm = bearish | Volatility removed from S. Still used in regime, Risk_vol, ATR stops; still computed for UI | S invariant to volatility_score | `test_v1_2_volatility_does_not_move_S` |
| 4 | ConfidenceFactor (S+1)/2 gives a strong short 0.10 → near-zero size | Short conviction = 1 − CF (symmetric) | short risk-per-trade comparable to longs | `test_short_conviction_v1_1_vs_v1_2`, `test_shorts_get_real_size_when_enabled` |
| 5 | RSI and Mean-Reversion ~0.87 correlated, double-counted | Merged: `Reversion = 0.5·RSIScore + 0.5·MeanRevScore` | components 6 → 4 | `test_v1_2_has_no_directional_volatility...` |
| 6 | PRD sandbox spec assumed user code, but users only set parameters | Process-isolated evaluation with wall timeout, CPU-seconds and memory limits; NSE market-hours calendar | timeout / crash / 4 GB alloc all caught | `tests/unit/test_bots.py` |

## v1.2 regime weights

| Component | Trending | Sideways | High Vol |
|---|---|---|---|
| Trend | 0.45 | 0.10 | 0.30 |
| Momentum | 0.35 | 0.10 | 0.25 |
| Reversion (RSI + MeanRev) | 0.05 | 0.65 | 0.30 |
| Volume | 0.15 | 0.15 | 0.15 |

(High Vol weights only matter for display — entries are blocked in that regime.)

## Previously unspecified values, now explicit parameters

MaxAllowedDrawdown = 20% · ADV window = 20 bars · RSI = Wilder smoothing ·
buying-power cap = 98% · fill at next bar open · same-bar stop+target → stop first.

## Still to be done on REAL data (cannot be solved in code)

The v1.2 weights were chosen to make the entry threshold *reachable*, not to maximise returns —
tuning on synthetic data would be meaningless. Before v1.2 moves to paper trading, run
`python -m scripts.demo_backtest your_nse_data.csv` on several NSE instruments and follow
Section 17: robustness → walk-forward → holdout (once). Synthetic results so far are ~flat/negative,
as expected on data with no real edge.

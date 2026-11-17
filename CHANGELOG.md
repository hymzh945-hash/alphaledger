# Changelog

## 0.1.0 — first public release

### Free tier
- `alphaledger report` — one-command HTML tearsheet from a CSV of returns or an equity curve
- `alphaledger serve` — zero-dependency local web UI (drag & drop CSV, report opens in a new tab)
- `alphaledger demo` — synthetic dataset + sample report so the tool can be tried instantly
- `alphaledger fetch` — public OKX and Binance candle download (no API key)
- Charts: equity & drawdown, monthly heatmap, rolling Sharpe / volatility, return distribution, calendar years
- 14 core metrics + optional benchmark comparison (alpha, beta, information ratio)
- Colour-blind-safe dark theme, fully self-contained HTML (no external JS/CSS)

### Pro tier
- 30+ additional metrics: probabilistic Sharpe, Sharpe standard error, skew, kurtosis,
  VaR 95, CVaR 95, Ulcer, Pain, tail ratio, common-sense ratio, recovery factor, gain-to-pain,
  Omega, Kelly, payoff ratio, avg win / loss, drawdown duration and count, streaks,
  exposure, yearly consistency
- Walk-forward audit with per-fold table, stability score and a robustness verdict
- Monte Carlo block-bootstrap stress test (probability of loss, DD > 20%, DD > 40%, ruin)
- Multi-strategy comparison: ranking table, correlation heatmap, equal-weight blend,
  diversification ratio
- CSV export of the metric set
- Ed25519 offline license verification (`alphaledger license`)

### Fixes
- Annualisation now infers observation frequency from the index span, so business-day,
  weekly, monthly and intraday series annualise correctly (pandas 2.x `datetime64[us]`
  produced a 1000x error in Sharpe / CAGR)

# AlphaLedger Pro — Gumroad listing copy

## Product name
AlphaLedger Pro — offline strategy performance audit

## Short description (one line)
Turn a CSV of returns into a walk-forward-verified tearsheet in one command. No cloud, no database, no subscription.

## Price
$39 one-time (lifetime updates) · launch price $29 for the first 100 buyers

## What's inside
- **AlphaLedger Pro key** — unlocks Pro features in the same open-source tool, verified offline (Ed25519). No activation server.
- **Walk-forward audit** — history split into consecutive folds, per-fold return/Sharpe/drawdown, stability score, plain-language verdict: robust / uneven / fragile.
- **Monte Carlo stress test** — 2,000 block-bootstrapped alternate histories; probability of loss, of a 20% drawdown, of a 40% drawdown, of ruin.
- **Strategy comparison** — rank any number of strategies, correlation heatmap, equal-weight blend metrics, diversification ratio.
- **30+ pro metrics** — probabilistic Sharpe, Sharpe standard error, skew, kurtosis, VaR95, CVaR95, Ulcer, Pain, tail ratio, common-sense ratio, recovery factor, gain-to-pain, Omega, Kelly, payoff ratio, streaks, exposure, yearly consistency.
- **CSV export** of the full metric set for your own pipeline.
- HTML reports are single files — attach to a client email, drop in a Notion log, archive with your backtest.

## Who it's for
- Retail quants and algo traders who already have a backtest and need to prove (to themselves) that the edge is not one lucky regime.
- Prop-firm applicants who need a clean performance sheet.
- Anyone running strategies on a laptop with no cloud budget.

## Requirements
Python 3.10+, a CSV of returns or an equity curve. Runs on macOS, Windows, Linux. Works fully offline after install.

## FAQ
**Is this the open-source repo?** The core engine is open source (Apache-2.0) on GitHub. The Pro key unlocks the robustness and comparison layer, and funds maintenance.

**Does my data leave my machine?** No. Reports are generated locally; the license check is offline.

**Refunds?** 14 days, no questions, if the reports do not fit your workflow.

**Do I need an API key?** Only for live candle downloads (OKX/Binance public endpoints work without keys).

**Is this financial advice?** No. It is an analysis tool.

# AlphaLedger

**Offline strategy performance audit — one command, one HTML file, zero data leaving your machine.**

AlphaLedger turns a CSV of returns (or an equity curve) into an institutional-grade tearsheet:
equity and drawdown, monthly heatmap, rolling Sharpe, tail-risk metrics, fold-by-fold
walk-forward verdicts, Monte Carlo drawdown stress, and side-by-side strategy comparison.

No database. No cloud account. No telemetry. Nothing is uploaded — the report is a single
self-contained HTML file you can send to a client or drop into a research log.

```bash
pip install alphaledger
alphaledger demo          # synthetic data + a full sample report, 3 seconds
alphaledger serve         # local web UI at http://127.0.0.1:8765 (drag & drop a CSV)
alphaledger report -i returns.csv -o report.html
```

---

## Why not just use QuantStats?

QuantStats (Apache-2.0, ~7.9k stars) is an excellent library and AlphaLedger is built on top of
that engine — we credit it in `NOTICE` and ship the license with the source. What it does **not**
give you is a product: no CLI, no UI, no fold-based robustness verdict, no cross-strategy
comparison, no way to tell a paying customer apart from a free user.

| | QuantStats | AlphaLedger |
|---|---|---|
| One-command HTML tearsheet | call Python yourself | `alphaledger report -i file.csv` |
| Local drag-and-drop UI | — | `alphaledger serve` |
| Data loading (CSV / parquet / OKX / Binance) | — | built in |
| Walk-forward consistency verdict | — | fold table + robustness score |
| Side-by-side strategy comparison + correlation | — | ranking table, corr heatmap, blend metrics |
| Tail risk (VaR, CVaR, Ulcer, Pain, PSR) | partial | full set, in report |
| Offline license gating for a paid tier | — | Ed25519 license, verified offline |
| Export metrics to CSV | — | `--csv metrics.csv` |

Everything runs on pandas + numpy + matplotlib. Python 3.10+.

---

## What you get

### Free tier (this repository, Apache-2.0)
- Full tearsheet: equity & drawdown, monthly heatmap, rolling Sharpe / volatility, return distribution, calendar years
- 14 core metrics: total return, CAGR, volatility, Sharpe, Sortino, Calmar, max / average drawdown, time under water, win rate, profit factor, expectancy, best / worst period
- Benchmark comparison (alpha, beta, information ratio)
- CLI + local web UI + CSV / parquet / OKX / Binance loaders

### Pro tier (unlocked by an offline license key)
- **30+ pro metrics** — probabilistic Sharpe, Sharpe standard error, skew, kurtosis, VaR 95, CVaR 95,
  Ulcer index, Pain index, tail ratio, common-sense ratio, recovery factor, gain-to-pain, Omega,
  Kelly fraction, payoff ratio, streak length, exposure, yearly consistency
- **Walk-forward audit** — history split into consecutive folds, per-fold return / Sharpe / drawdown,
  stability score, and a plain-language verdict: *robust · uneven · fragile*
- **Monte Carlo stress** — block-bootstrap 2,000+ alternate histories, probability of loss,
  probability of a 20% / 40% drawdown, probability of ruin
- **Strategy comparison** — unlimited strategies, ranking table, correlation heatmap, equal-weight blend,
  diversification ratio
- **Metrics export** to CSV for your own pipeline

The license is a small signed JSON file. Verification is Ed25519 against a baked-in public key —
offline, instant, no activation server, no phone-home.

```bash
alphaledger license           # show tier, expiry, source
export ALPHALEDGER_LICENSE=/path/to/license.json   # or drop it in ~/alphaledger-license.json
```

Get a Pro key → **https://alphaledger.gumroad.com**

---

## Use it from Python

```python
import alphaledger as al

al.report_file(
    "returns.csv",
    name="BTC 4h momentum",
    benchmark_path="btc_hold.csv",
    out="report.html",
    walkforward=True,
    montecarlo=True,
)
```

Or go one level down:

```python
from alphaledger import data, metrics, audit

r = metrics.prepare_returns(data.load_series("returns.csv"))
metrics.advanced_metrics(r)          # dict of 45+ metrics
audit.walk_forward(r, folds=4)       # per-fold table + verdict
audit.monte_carlo(r, runs=2000)      # bootstrap distribution
audit.compare({"A": r_a, "B": r_b})  # ranking + correlation + blend
```

## Input formats

A CSV with a date column and either returns or an equity / price column. Columns are auto-detected
(`date`, `datetime`, `time`, `timestamp`, `index`; `return`, `ret`, `pnl`, `equity`, `close`, `nav`),
and a price series is converted to returns automatically.

```csv
date,return
2024-01-02,0.0121
2024-01-03,-0.0044
```

## Fetching candles

```bash
alphaledger fetch -s okx --symbol BTC-USDT --bar 1H --limit 100 -o btc.csv
alphaledger fetch -s binance --symbol BTCUSDT --bar 1h --limit 500 -o btc.csv
```

Public endpoints only, no API keys. Rate limits and regional blocks are the exchange's call, not ours.

## Install from source

```bash
git clone https://github.com/<your-account>/alphaledger.git
cd alphaledger
python -m venv .venv && source .venv/bin/activate
pip install -e ".[license,dev]"
pytest -q
```

## Project layout

```
alphaledger/
├── alphaledger/
│   ├── metrics.py      # core + advanced metric engine
│   ├── charts.py       # matplotlib renderers -> inline PNG
│   ├── audit.py        # walk-forward, Monte Carlo, comparison  (Pro)
│   ├── report.py       # HTML report builder
│   ├── licensing.py    # Ed25519 offline license verification
│   ├── data.py         # CSV / parquet / OKX / Binance loaders
│   ├── cli.py          # argparse CLI
│   ├── server.py       # stdlib local web UI
│   └── engine/         # vendored QuantStats engine (Apache-2.0)
├── examples/           # sample data + generated reports
├── docs/               # pricing, listing copy, launch material
└── tests/
```

## License and attribution

AlphaLedger is released under the **Apache License 2.0**. It includes code derived from
[QuantStats](https://github.com/ranaroussi/quantstats) by Ran Aroussi, also Apache-2.0 — see
`NOTICE` for the attribution and the list of modifications.

Pro features are unlocked by a license key; the paid tier funds maintenance. The public
source stays open, which means you can audit exactly what the report does with your data.

## Disclaimer

AlphaLedger is an analysis tool, not investment advice. Backtested and audited performance is
not indicative of future results. Trade with money you can afford to lose.

## Pro edition

The paid edition adds the HTML report templates, CSV exports, and an offline-verified signed
licence — no server check, no telemetry. $39 once, yours to keep:

https://hymz.gumroad.com/l/alphaledger


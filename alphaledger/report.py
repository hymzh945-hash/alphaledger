"""HTML report builder (self-contained file, no JS dependencies, no telemetry)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from . import charts
from . import metrics as m
from . import licensing
from .version import version

CSS = """
:root{--bg:#0d1117;--panel:#111827;--line:#1f2937;--fg:#e5e7eb;--muted:#9ca3af;
--green:#34d399;--red:#f87171;--blue:#60a5fa;--amber:#fbbf24}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
font-size:14px;line-height:1.5}
.wrap{max-width:1080px;margin:0 auto;padding:36px 22px 64px}
.brand{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px;
letter-spacing:.14em;text-transform:uppercase}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green)}
h1{font-size:30px;margin:14px 0 6px;letter-spacing:-.02em}
.meta{color:var(--muted);font-size:13px}
.badge{display:inline-block;padding:3px 9px;border:1px solid var(--line);border-radius:999px;
font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.badge.pro{color:var(--amber);border-color:#4b3a12;background:#1a1408}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0 8px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .label{color:var(--muted);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.kpi .value{font-size:22px;font-weight:600;margin-top:6px;letter-spacing:-.01em}
.pos{color:var(--green)}.neg{color:var(--red)}.neutral{color:var(--fg)}
h2{font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
margin:38px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
.chart{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;
margin-bottom:14px}
.chart img{width:100%;display:block;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:500;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
td:first-child,th:first-child{text-align:left}
.two{display:grid;grid-template-columns:1fr 1fr;gap:0 26px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:0 16px}
.note{background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:16px 18px;
color:var(--muted);font-size:13px}
.note b{color:var(--fg)}
.cta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}
.btn{display:inline-block;background:var(--green);color:#062b1e;font-weight:600;
padding:9px 16px;border-radius:9px;text-decoration:none;font-size:13px}
.verdict{font-size:22px;font-weight:700;letter-spacing:-.01em}
footer{margin-top:56px;color:#6b7280;font-size:12px;border-top:1px solid var(--line);padding-top:18px}
@media(max-width:760px){.kpis{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}}
"""


def _fmt(value, kind: str = "num") -> str:
    if value is None:
        return "—"
    try:
        if kind == "pct":
            return f"{value * 100:.2f}%"
        if kind == "num":
            if value in (float("inf"),) or (isinstance(value, float) and value == float("inf")):
                return "∞"
            return f"{value:.2f}"
        if kind == "int":
            return f"{int(value)}"
    except (TypeError, ValueError):
        return "—"
    return str(value)


def _cls(value, invert: bool = False) -> str:
    try:
        good = value <= 0 if invert else value >= 0
        if value == 0:
            return "neutral"
        return "pos" if good else "neg"
    except Exception:
        return "neutral"


def _kpi(label: str, value: str, cls: str = "neutral") -> str:
    return f'<div class="kpi"><div class="label">{label}</div><div class="value {cls}">{value}</div></div>'


def _rows(metrics: Dict[str, float], keys) -> str:
    out = []
    for key in keys:
        if key not in metrics:
            continue
        label, kind = m.METRIC_LABELS.get(key, (key.replace("_", " ").title(), "num"))
        out.append(f"<tr><td>{label}</td><td>{_fmt(metrics[key], kind)}</td></tr>")
    return "".join(out)


CORE_KEYS = ["total_return", "cagr", "volatility", "sharpe", "sortino", "calmar",
             "max_drawdown", "avg_drawdown", "time_in_drawdown", "win_rate",
             "profit_factor", "expectancy", "best_period", "worst_period"]

PRO_KEYS = ["psr_vs_zero", "sharpe_stderr", "skew", "kurtosis", "var_95", "cvar_95",
            "ulcer_index", "pain_index", "tail_ratio", "common_sense_ratio",
            "recovery_factor", "gain_to_pain", "omega", "kelly", "payoff_ratio",
            "avg_win", "avg_loss", "max_dd_duration", "max_win_streak",
            "max_loss_streak", "exposure", "yearly_return_avg", "yearly_return_worst",
            "yearly_positive_ratio"]

PRO_LABELS = {
    "psr_vs_zero": ("Probabilistic Sharpe (vs 0)", "num"),
    "sharpe_stderr": ("Sharpe standard error", "num"),
    "skew": ("Return skew", "num"),
    "kurtosis": ("Return kurtosis", "num"),
    "var_95": ("VaR 95% (per period)", "pct"),
    "cvar_95": ("CVaR 95% (expected shortfall)", "pct"),
    "ulcer_index": ("Ulcer index", "num"),
    "pain_index": ("Pain index", "pct"),
    "tail_ratio": ("Tail ratio", "num"),
    "common_sense_ratio": ("Common sense ratio", "num"),
    "recovery_factor": ("Recovery factor", "num"),
    "gain_to_pain": ("Gain-to-pain ratio", "num"),
    "omega": ("Omega ratio", "num"),
    "kelly": ("Kelly fraction", "pct"),
    "payoff_ratio": ("Payoff ratio", "num"),
    "avg_win": ("Average win", "pct"),
    "avg_loss": ("Average loss", "pct"),
    "max_dd_duration": ("Longest drawdown (periods)", "int"),
    "max_win_streak": ("Longest win streak", "int"),
    "max_loss_streak": ("Longest loss streak", "int"),
    "exposure": ("Exposure (non-zero returns)", "pct"),
    "yearly_return_avg": ("Average calendar year", "pct"),
    "yearly_return_worst": ("Worst calendar year", "pct"),
    "yearly_positive_ratio": ("Positive calendar years", "pct"),
}
m.METRIC_LABELS.update(PRO_LABELS)


def _locked(message: str) -> str:
    return (
        '<div class="note"><b>Pro analysis locked.</b><br>' + message +
        '<div class="cta"><a class="btn" href="https://alphaledger.gumroad.com">Get AlphaLedger Pro</a>'
        '<span>Offline license, no subscription, no data leaves your machine.</span></div></div>'
    )


def _metrics_table(metrics: Dict[str, float]) -> str:
    left = _rows(metrics, CORE_KEYS)
    right = _rows(metrics, PRO_KEYS)
    return (
        '<div class="two">'
        f'<div class="card"><table><tbody>{left}</tbody></table></div>'
        f'<div class="card"><table><tbody>{right}</tbody></table></div>'
        "</div>"
    )


def _walkforward_block(wf: Dict[str, object]) -> str:
    s = wf["summary"]
    tbl = wf["table"]
    head = "".join(f"<th>{c}</th>" for c in ["Fold", "Start", "End", "Return", "Sharpe", "Max DD", "Win rate"])
    body = ""
    for name, row in tbl.iterrows():
        body += (
            f"<tr><td>{name}</td><td>{row['start']}</td><td>{row['end']}</td>"
            f"<td class='{_cls(row['total_return'])}'>{_fmt(row['total_return'], 'pct')}</td>"
            f"<td>{_fmt(row['sharpe'])}</td>"
            f"<td class='neg'>{_fmt(row['max_drawdown'], 'pct')}</td>"
            f"<td>{_fmt(row['win_rate'], 'pct')}</td></tr>"
        )
    return (
        f'<div class="note"><div class="verdict" style="color:{s["verdict_color"]}">{s["verdict"]}</div>'
        f'<div style="margin-top:6px">Positive folds {_fmt(s["positive_ratio"], "pct")} · '
        f'mean Sharpe {_fmt(s["mean_sharpe"])} · dispersion {_fmt(s["sharpe_dispersion"])} · '
        f'worst fold DD {_fmt(s["worst_fold_drawdown"], "pct")}</div></div>'
        f'<div class="chart"><img src="{charts.walkforward_bars(tbl)}" alt="walk-forward folds"></div>'
        f'<div class="card" style="margin-top:12px"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _montecarlo_block(mc: Dict[str, object]) -> str:
    s = mc["stats"]
    cards = "".join(
        [
            _kpi("Median return", _fmt(s["median_return"], "pct"), _cls(s["median_return"])),
            _kpi("5th pct return", _fmt(s["return_p05"], "pct"), _cls(s["return_p05"])),
            _kpi("Prob. of loss", _fmt(s["prob_loss"], "pct"), _cls(1 - s["prob_loss"])),
            _kpi("Median max DD", _fmt(s["median_max_dd"], "pct"), "neg"),
            _kpi("Worst max DD", _fmt(s["worst_max_dd"], "pct"), "neg"),
            _kpi("P(DD > 20%)", _fmt(s["prob_dd_over_20"], "pct"), _cls(1 - s["prob_dd_over_20"])),
            _kpi("P(DD > 40%)", _fmt(s["prob_dd_over_40"], "pct"), _cls(1 - s["prob_dd_over_40"])),
            _kpi("P(ruin)", _fmt(s["prob_ruin"], "pct"), _cls(1 - s["prob_ruin"])),
        ]
    )
    return f'<div class="kpis">{cards}</div><div class="chart"><img src="{charts.montecarlo_paths(mc["paths"])}" alt="monte carlo"></div>'


def _compare_block(cmp: Dict[str, object]) -> str:
    table: pd.DataFrame = cmp["table"]
    names = list(table.index)
    head = "<th>Strategy</th>" + "".join(
        f"<th>{c}</th>" for c in ["Return", "CAGR", "Sharpe", "Max DD", "Win rate", "PSR"]
    )
    body = ""
    for name in names:
        row = table.loc[name]
        body += (
            f"<tr><td>{name}</td><td class='{_cls(row['total_return'])}'>{_fmt(row['total_return'], 'pct')}</td>"
            f"<td>{_fmt(row['cagr'], 'pct')}</td><td>{_fmt(row['sharpe'])}</td>"
            f"<td class='neg'>{_fmt(row['max_drawdown'], 'pct')}</td>"
            f"<td>{_fmt(row['win_rate'], 'pct')}</td>"
            f"<td>{_fmt(row.get('psr_vs_zero'))}</td></tr>"
        )
    port = cmp.get("portfolio", {})
    extra = ""
    if port.get("equal_weight_portfolio"):
        p = port["equal_weight_portfolio"]
        extra = (
            f'<div class="note" style="margin-top:12px">Equal-weight blend: '
            f'Sharpe {_fmt(p["sharpe"])} · Max DD {_fmt(p["max_drawdown"], "pct")} · '
            f'Diversification ratio {_fmt(port.get("diversification_ratio"))}</div>'
        )
    return (
        f'<div class="card"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
        f'<div class="chart" style="margin-top:12px"><img src="{charts.compare_curves(cmp["frame"].to_dict("series"))}" alt="comparison"></div>'
        f'<div class="chart"><img src="{charts.correlation_heatmap(cmp["corr"])}" alt="correlation"></div>{extra}'
    )


def build_report(
    returns,
    name: str = "Strategy",
    benchmark=None,
    benchmark_name: str = "benchmark",
    walkforward: Optional[Dict[str, object]] = None,
    montecarlo: Optional[Dict[str, object]] = None,
    comparison: Optional[Dict[str, object]] = None,
    meta: Optional[Dict[str, str]] = None,
    pro: Optional[bool] = None,
) -> str:
    """Render the full HTML report for one strategy plus optional Pro sections."""
    pro = licensing.is_pro() if pro is None else pro
    r = m.prepare_returns(returns)
    metrics = m.advanced_metrics(r, benchmark) if pro else m.core_metrics(r, benchmark)
    lic = licensing.get_license()

    start = r.index[0].date().isoformat() if len(r) else "—"
    end = r.index[-1].date().isoformat() if len(r) else "—"
    periods = len(r)

    kpis = "".join(
        [
            _kpi("Total return", _fmt(metrics.get("total_return"), "pct"), _cls(metrics.get("total_return", 0))),
            _kpi("CAGR", _fmt(metrics.get("cagr"), "pct"), _cls(metrics.get("cagr", 0))),
            _kpi("Sharpe", _fmt(metrics.get("sharpe")), _cls(metrics.get("sharpe", 0))),
            _kpi("Sortino", _fmt(metrics.get("sortino")), _cls(metrics.get("sortino", 0))),
            _kpi("Max drawdown", _fmt(metrics.get("max_drawdown"), "pct"), "neg"),
            _kpi("Volatility", _fmt(metrics.get("volatility"), "pct"), "neutral"),
            _kpi("Win rate", _fmt(metrics.get("win_rate"), "pct"), "neutral"),
            _kpi("Profit factor", _fmt(metrics.get("profit_factor")), "neutral"),
        ]
    )

    badge = '<span class="badge pro">Pro license</span>' if pro else '<span class="badge">Free tier</span>'
    meta_rows = "".join(
        f"<span>{k}: <b style='color:#e5e7eb;font-weight:500'>{v}</b></span>"
        for k, v in (meta or {}).items()
    )

    sections = []
    sections.append(f'<h2>Performance</h2><div class="kpis">{kpis}</div>')
    sections.append(f'<div class="chart"><img src="{charts.equity_drawdown(r, name)}" alt="equity"></div>')
    sections.append(f'<div class="chart"><img src="{charts.monthly_heatmap(r)}" alt="monthly"></div>')
    sections.append(f'<div class="chart"><img src="{charts.rolling_profile(r)}" alt="rolling"></div>')
    sections.append(f'<div class="chart"><img src="{charts.return_distribution(r)}" alt="distribution"></div>')
    yearly = charts.yearly_bars(r)
    if yearly:
        sections.append(f'<div class="chart"><img src="{yearly}" alt="yearly"></div>')

    sections.append('<h2>Metric breakdown</h2>')
    if pro:
        sections.append(_metrics_table(metrics))
    else:
        sections.append(f'<div class="card"><table><tbody>{_rows(metrics, CORE_KEYS)}</tbody></table></div>')
        sections.append(
            '<div style="margin-top:14px">' +
            _locked("30+ additional metrics — VaR / CVaR, Ulcer and Pain index, probabilistic Sharpe, "
                    "Kelly, recovery factor, streaks, yearly consistency — are part of Pro.") +
            "</div>"
        )

    sections.append("<h2>Walk-forward audit</h2>")
    if walkforward is None:
        sections.append(_locked("Split your history into consecutive folds and see whether the edge survives "
                                "every regime, not just the full sample."))
    else:
        sections.append(_walkforward_block(walkforward))

    sections.append("<h2>Monte Carlo stress test</h2>")
    if montecarlo is None:
        sections.append(_locked("Block-bootstrap 2,000+ alternative histories to estimate the drawdown you "
                                "have not lived through yet."))
    else:
        sections.append(_montecarlo_block(montecarlo))

    if comparison is not None:
        sections.append("<h2>Strategy comparison</h2>")
        sections.append(_compare_block(comparison))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} · AlphaLedger</title><style>{CSS}</style></head>
<body><div class="wrap">
<div class="brand"><span class="dot"></span>AlphaLedger · Strategy performance audit {badge}</div>
<h1>{name}</h1>
<div class="meta">{start} → {end} · {periods} observations · {lic.describe()}</div>
<div class="meta" style="margin-top:6px">{meta_rows}</div>
{''.join(sections)}
<footer>
Generated locally by AlphaLedger {version} on {datetime.now():%Y-%m-%d %H:%M}.
Past performance is not indicative of future results. This report is an analytical tool,
not investment advice. AlphaLedger includes code derived from QuantStats (Apache-2.0).
</footer>
</div></body></html>"""

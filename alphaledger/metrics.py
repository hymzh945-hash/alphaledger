"""Core performance metrics for AlphaLedger.

Everything here is computed locally with pandas / numpy only.  The functions
accept either a return series (fractions, e.g. 0.01 == +1%) or a price / equity
series, which is converted to returns automatically.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

__all__ = [
    "prepare_returns",
    "periods_per_year",
    "core_metrics",
    "advanced_metrics",
    "METRIC_LABELS",
]


# --------------------------------------------------------------------------- #
# input handling
# --------------------------------------------------------------------------- #
def _looks_like_prices(values: pd.Series) -> bool:
    """Heuristic: positive, non-trivial values that are clearly not fractions."""
    if values.empty:
        return False
    v = values.dropna()
    if v.empty:
        return False
    if (v <= 0).any():
        return False
    if v.abs().max() < 50 and v.abs().median() < 5:
        return False  # already looks like returns
    return True


def prepare_returns(data, rf: float = 0.0) -> pd.Series:
    """Normalise input into a clean, sorted return series indexed by date."""
    if isinstance(data, list):
        data = pd.Series(data)
    if not isinstance(data, pd.Series):
        raise TypeError("input must be a pandas Series, list or 1-D array")

    s = data.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        if pd.api.types.is_numeric_dtype(s.index):
            s.index = pd.to_datetime(s.index, unit="D", errors="coerce")
        else:
            s.index = pd.to_datetime(s.index, errors="coerce")

    s = s[~s.index.isna()]
    s = s.groupby(level=0).last().sort_index()
    s = pd.to_numeric(s, errors="coerce").dropna()

    if _looks_like_prices(s):
        s = s.pct_change()
        s = s.replace([np.inf, -np.inf], np.nan).dropna()

    if not rf:
        return s.astype(float)
    # daily risk-free rate from annual percentage
    ppy = periods_per_year(s.index)
    return (s - rf / ppy).astype(float)


def periods_per_year(index: pd.DatetimeIndex) -> float:
    """Infer the number of observations per year from the index spacing."""
    if len(index) < 2:
        return 252.0
    # dtype-agnostic: always measure the gap in seconds
    deltas = np.diff(index.astype("datetime64[ns]").astype("int64")) / 1e9
    deltas = deltas[np.isfinite(deltas) & (deltas > 0)]
    if deltas.size == 0:
        return 252.0
    median = float(np.median(deltas))
    if median < 86400:  # intraday
        return round(365.0 * 24 * 3600 / median, 0)

    span_days = (index[-1] - index[0]).total_seconds() / 86400
    if span_days <= 0:
        return 252.0
    raw = (len(index) - 1) / (span_days / 365.25)
    for candidate in (365.0, 252.0, 52.0, 12.0, 4.0, 1.0):
        if abs(raw - candidate) / candidate < 0.15:
            return candidate
    return round(raw, 0)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _drawdown_series(returns: pd.Series) -> pd.Series:
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    return equity / peak - 1


def _dd_stats(returns: pd.Series) -> Dict[str, float]:
    dd = _drawdown_series(returns)
    if dd.empty:
        return {"max_drawdown": 0.0, "max_dd_duration": 0, "avg_drawdown": 0.0,
                "time_in_drawdown": 0.0, "drawdown_count": 0}

    max_dd = float(dd.min())
    # longest stretch below high-water mark, measured in observations
    under = dd < -1e-12
    longest = cur = 0
    for flag in under.to_numpy():
        cur = cur + 1 if flag else 0
        longest = max(longest, cur)

    durations = []
    start = None
    for ts, flag in under.items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            durations.append((ts - start).days or 1)
            start = None
    if start is not None:
        durations.append((dd.index[-1] - start).days or 1)

    return {
        "max_drawdown": max_dd,
        "max_dd_duration": int(longest),
        "avg_drawdown": float(dd[under].mean()) if under.any() else 0.0,
        "time_in_drawdown": float(under.mean()),
        "drawdown_count": int((under.astype(int).diff() == 1).sum() + (1 if under.iloc[0] else 0)),
    }


def _streaks(returns: pd.Series) -> Dict[str, int]:
    pos = returns > 0
    neg = returns < 0
    best = worst = cur_pos = cur_neg = 0
    for p, n in zip(pos.to_numpy(), neg.to_numpy()):
        cur_pos = cur_pos + 1 if p else 0
        cur_neg = cur_neg + 1 if n else 0
        best = max(best, cur_pos)
        worst = max(worst, cur_neg)
    return {"max_win_streak": best, "max_loss_streak": worst}


def _cvar(returns: pd.Series, level: float = 0.05) -> float:
    if returns.empty:
        return 0.0
    q = returns.quantile(level)
    tail = returns[returns <= q]
    return float(tail.mean()) if len(tail) else float(q)


def _psr(returns: pd.Series, benchmark_sr: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio (Bailey & Lopez de Prado)."""
    n = len(returns)
    if n < 3:
        return float("nan")
    sr = returns.mean() / returns.std(ddof=1) if returns.std(ddof=1) else 0.0
    skew = returns.skew()
    kurt = returns.kurtosis()
    denom = 1 - skew * sr + ((kurt - 1) / 4) * sr ** 2
    if denom <= 0:
        return float("nan")
    z = (sr - benchmark_sr) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(0.5 * (1 + math.erf(z / math.sqrt(2))))


def _ulcer(returns: pd.Series) -> float:
    dd = _drawdown_series(returns)
    return float(np.sqrt((dd ** 2).mean())) if len(dd) else 0.0


def _pain(returns: pd.Series) -> float:
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    return float(((peak - equity) / peak).mean()) if len(equity) else 0.0


def _omega(returns: pd.Series, threshold: float = 0.0) -> float:
    gains = (returns - threshold).clip(lower=0).sum()
    losses = (threshold - returns).clip(lower=0).sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


# --------------------------------------------------------------------------- #
# public metric sets
# --------------------------------------------------------------------------- #
METRIC_LABELS = {
    "total_return": ("Total return", "pct"),
    "cagr": ("CAGR", "pct"),
    "volatility": ("Annualised volatility", "pct"),
    "sharpe": ("Sharpe ratio", "num"),
    "sortino": ("Sortino ratio", "num"),
    "calmar": ("Calmar ratio", "num"),
    "max_drawdown": ("Max drawdown", "pct"),
    "avg_drawdown": ("Average drawdown", "pct"),
    "time_in_drawdown": ("Time under water", "pct"),
    "win_rate": ("Win rate", "pct"),
    "profit_factor": ("Profit factor", "num"),
    "expectancy": ("Expectancy per period", "pct"),
    "best_period": ("Best period", "pct"),
    "worst_period": ("Worst period", "pct"),
}


def core_metrics(returns: pd.Series, benchmark: Optional[pd.Series] = None) -> Dict[str, float]:
    """Free tier: the 14 numbers most traders actually check first."""
    r = prepare_returns(returns) if not isinstance(returns, pd.Series) else returns
    if r.empty:
        return {}

    ppy = periods_per_year(r.index)
    total = float((1 + r).prod() - 1)
    years = len(r) / ppy
    cagr = float((1 + total) ** (1 / years) - 1) if years > 0 and total > -1 else float(total)
    vol = float(r.std(ddof=1) * math.sqrt(ppy))
    downside = r[r < 0]
    dstd = float(downside.std(ddof=1) * math.sqrt(ppy)) if len(downside) > 1 else 0.0

    dd = _dd_stats(r)
    wins = r[r > 0]
    losses = r[r < 0]
    gross_win = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    win_rate = float(len(wins) / len(r))

    metrics = {
        "total_return": total,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": float((r.mean() * ppy) / vol) if vol else 0.0,
        "sortino": float((r.mean() * ppy) / dstd) if dstd else 0.0,
        "calmar": float(cagr / abs(dd["max_drawdown"])) if dd["max_drawdown"] else 0.0,
        "max_drawdown": dd["max_drawdown"],
        "avg_drawdown": dd["avg_drawdown"],
        "time_in_drawdown": dd["time_in_drawdown"],
        "win_rate": win_rate,
        "profit_factor": float(gross_win / gross_loss) if gross_loss else float("inf"),
        "expectancy": float(r.mean()),
        "best_period": float(r.max()),
        "worst_period": float(r.min()),
        "periods": int(len(r)),
        "periods_per_year": float(ppy),
    }

    if benchmark is not None and not benchmark.empty:
        b = benchmark.reindex(r.index).dropna()
        aligned = r.reindex(b.index)
        if len(aligned) > 2:
            te = float((aligned - b).std(ddof=1) * math.sqrt(ppy))
            metrics["alpha_vs_benchmark"] = float(
                (aligned.mean() - b.mean()) * ppy
            )
            metrics["information_ratio"] = (
                float(((aligned - b).mean() * ppy) / te) if te else 0.0
            )
            metrics["beta"] = float(np.cov(aligned, b)[0, 1] / np.var(b, ddof=1)) if b.var(ddof=1) else 0.0
    return metrics


def advanced_metrics(returns: pd.Series, benchmark: Optional[pd.Series] = None) -> Dict[str, float]:
    """Pro tier: tail risk, consistency and statistical-confidence metrics."""
    base = core_metrics(returns, benchmark)
    if not base:
        return {}
    r = prepare_returns(returns) if not isinstance(returns, pd.Series) else returns
    ppy = periods_per_year(r.index)

    wins = r[r > 0]
    losses = r[r < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    payoff = float(abs(avg_win / avg_loss)) if avg_loss else float("inf")
    dd = _dd_stats(r)
    streaks = _streaks(r)

    pro = {
        "sharpe_stderr": float(
            math.sqrt((1 + 0.5 * base["sharpe"] ** 2) / max(len(r), 2))
        ),
        "psr_vs_zero": _psr(r, 0.0),
        "skew": float(r.skew()),
        "kurtosis": float(r.kurtosis()),
        "var_95": float(r.quantile(0.05)),
        "cvar_95": _cvar(r, 0.05),
        "ulcer_index": _ulcer(r),
        "pain_index": _pain(r),
        "tail_ratio": float(abs(r.quantile(0.95) / r.quantile(0.05)))
        if r.quantile(0.05) else float("inf"),
        "common_sense_ratio": float(
            base["profit_factor"] * (abs(r.quantile(0.95) / r.quantile(0.05)) if r.quantile(0.05) else 1)
        ),
        "recovery_factor": float(base["total_return"] / abs(dd["max_drawdown"]))
        if dd["max_drawdown"] else float("inf"),
        "gain_to_pain": float(r.sum() / abs(r[r < 0].sum())) if r[r < 0].sum() else float("inf"),
        "omega": _omega(r),
        "kelly": float(base["win_rate"] - (1 - base["win_rate"]) / payoff) if payoff else 0.0,
        "payoff_ratio": payoff,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_dd_duration": dd["max_dd_duration"],
        "drawdown_count": dd["drawdown_count"],
        "max_win_streak": streaks["max_win_streak"],
        "max_loss_streak": streaks["max_loss_streak"],
        "exposure": float((r != 0).mean()),
        "yearly_return_avg": float(
            (1 + r).groupby(r.index.year).prod().sub(1).mean()
        ) if len(r) else 0.0,
        "yearly_return_worst": float(
            (1 + r).groupby(r.index.year).prod().sub(1).min()
        ) if len(r) else 0.0,
        "yearly_positive_ratio": float(
            ((1 + r).groupby(r.index.year).prod().sub(1) > 0).mean()
        ) if len(r) else 0.0,
    }
    base.update(pro)
    return base

"""Pro analyses: walk-forward audit, Monte Carlo stress test, multi-strategy compare."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from . import metrics as m


# --------------------------------------------------------------------------- #
# multi-strategy comparison
# --------------------------------------------------------------------------- #
def combine(series_map: Dict[str, pd.Series], weights: Optional[Dict[str, float]] = None) -> pd.Series:
    """Align several return series and blend them into one portfolio series."""
    frame = pd.DataFrame({k: m.prepare_returns(v) for k, v in series_map.items()})
    frame = frame.dropna(how="all").fillna(0.0)
    if weights:
        raw = np.array([float(weights.get(k, 0.0)) for k in frame.columns])
        if raw.sum() == 0:
            raw = np.ones(len(frame.columns))
        w = raw / raw.sum()
    else:
        w = np.repeat(1.0 / frame.shape[1], frame.shape[1])
    return pd.Series(frame.to_numpy() @ w, index=frame.index, name="portfolio")


def compare(
    series_map: Dict[str, pd.Series],
    benchmark: Optional[pd.Series] = None,
    include_portfolio: bool = True,
) -> Dict[str, object]:
    """Side-by-side metric table, correlation matrix and a blended portfolio."""
    if len(series_map) < 2:
        raise ValueError("compare() needs at least two return series")

    frame = pd.DataFrame({k: m.prepare_returns(v) for k, v in series_map.items()}).dropna(how="all")
    rows = {}
    for name in frame.columns:
        r = frame[name].dropna()
        if len(r) < 2:
            continue
        rows[name] = m.advanced_metrics(r, benchmark)

    table = pd.DataFrame(rows).T
    table = table.sort_values("sharpe", ascending=False)

    corr = frame.corr()

    extra = {}
    if include_portfolio and len(frame.columns) > 1:
        port = combine(series_map)
        extra["equal_weight_portfolio"] = m.advanced_metrics(port, benchmark)

    # diversification ratio = weighted avg vol / portfolio vol
    vols = {k: float(frame[k].std()) for k in frame.columns if frame[k].notna().sum() > 2}
    if vols:
        port_vol = float(combine(series_map).std())
        dr = (np.mean(list(vols.values())) / port_vol) if port_vol else float("nan")
        extra["diversification_ratio"] = float(dr)

    return {"table": table, "corr": corr, "portfolio": extra, "frame": frame}


# --------------------------------------------------------------------------- #
# walk-forward consistency
# --------------------------------------------------------------------------- #
def walk_forward(
    returns: pd.Series,
    folds: int = 4,
    benchmark: Optional[pd.Series] = None,
) -> Dict[str, object]:
    """Split the history into consecutive folds and score each one separately.

    A strategy that only works in one regime shows up here as a large spread
    between fold Sharpes, even when the full-sample Sharpe looks healthy.
    """
    r = m.prepare_returns(returns)
    if len(r) < folds * 10:
        raise ValueError("not enough observations for the requested number of folds")

    chunks = np.array_split(np.arange(len(r)), folds)
    rows = {}
    for i, idx in enumerate(chunks, start=1):
        part = r.iloc[idx]
        if len(part) < 3:
            continue
        item = m.core_metrics(part, benchmark.reindex(part.index) if benchmark is not None else None)
        item["start"] = part.index[0].date().isoformat()
        item["end"] = part.index[-1].date().isoformat()
        item["periods"] = len(part)
        rows[f"F{i}"] = item

    table = pd.DataFrame(rows).T
    sharpe_std = float(table["sharpe"].std(ddof=1)) if len(table) > 1 else 0.0
    mean_sharpe = float(table["sharpe"].mean())

    positive = int((table["total_return"] > 0).sum())
    summary = {
        "folds": len(table),
        "mean_sharpe": mean_sharpe,
        "sharpe_dispersion": sharpe_std,
        "positive_folds": positive,
        "positive_ratio": positive / max(len(table), 1),
        "worst_fold_return": float(table["total_return"].min()),
        "worst_fold_drawdown": float(table["max_drawdown"].min()),
        "best_fold_sharpe": float(table["sharpe"].max()),
        "worst_fold_sharpe": float(table["sharpe"].min()),
        "stability_score": float(mean_sharpe / sharpe_std) if sharpe_std else float("inf"),
    }
    summary["verdict"], summary["verdict_color"] = _verdict(summary)
    return {"table": table, "summary": summary}


def _verdict(s: Dict[str, float]) -> tuple[str, str]:
    if s["positive_ratio"] >= 0.75 and s["mean_sharpe"] >= 1.0 and s["sharpe_dispersion"] <= 0.8:
        return "Robust — consistent across regimes", "#34d399"
    if s["positive_ratio"] >= 0.5 and s["mean_sharpe"] >= 0.5:
        return "Usable but uneven — check the weakest fold", "#fbbf24"
    return "Fragile — performance depends on one regime", "#f87171"


# --------------------------------------------------------------------------- #
# Monte Carlo stress
# --------------------------------------------------------------------------- #
def monte_carlo(
    returns: pd.Series,
    runs: int = 2000,
    block: Optional[int] = None,
    horizon: Optional[int] = None,
    seed: int = 7,
    ruin_threshold: float = -0.5,
) -> Dict[str, object]:
    """Block-bootstrap the return stream to see what the drawdown *could* be."""
    r = m.prepare_returns(returns)
    if len(r) < 20:
        raise ValueError("need at least 20 observations for a Monte Carlo run")

    n = horizon or len(r)
    block = block or max(3, min(20, len(r) // 20))
    rng = np.random.default_rng(seed)
    vals = r.to_numpy(dtype=float)

    starts = rng.integers(0, len(vals), size=(runs,))
    paths = np.empty((runs, n))
    for i in range(runs):
        # contiguous blocks keep autocorrelation somewhat intact
        block_id = np.arange(n) // block
        idx = (starts[i] + block_id * block + np.arange(n) % block) % len(vals)
        paths[i] = vals[idx]

    equity = np.cumprod(1 + paths, axis=1)
    peak = np.maximum.accumulate(equity, axis=1)
    dd = equity / peak - 1

    final_ret = equity[:, -1] - 1
    max_dd = dd.min(axis=1)

    stats = {
        "runs": runs,
        "horizon": n,
        "median_return": float(np.median(final_ret)),
        "return_p05": float(np.percentile(final_ret, 5)),
        "return_p95": float(np.percentile(final_ret, 95)),
        "prob_loss": float((final_ret < 0).mean()),
        "median_max_dd": float(np.median(max_dd)),
        "worst_max_dd": float(max_dd.min()),
        "dd_p05": float(np.percentile(max_dd, 5)),
        "prob_dd_over_20": float((max_dd < -0.2).mean()),
        "prob_dd_over_40": float((max_dd < -0.4).mean()),
        "prob_ruin": float((max_dd < ruin_threshold).mean()),
        "actual_return": float(np.prod(1 + vals) - 1),
        "actual_max_dd": float((np.minimum.accumulate(np.cumprod(1 + vals)) /
                                np.maximum.accumulate(np.cumprod(1 + vals)) - 1).min()),
    }
    return {"stats": stats, "paths": equity, "drawdowns": dd}

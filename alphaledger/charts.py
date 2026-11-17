"""Chart rendering: matplotlib -> inline base64 PNG, dark theme."""

from __future__ import annotations

import base64
import io
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BG = "#0d1117"
PANEL = "#111827"
FG = "#e5e7eb"
MUTED = "#9ca3af"
ACCENT = "#34d399"
DANGER = "#f87171"
NEUTRAL = "#60a5fa"
GRID = "#1f2937"

plt.rcParams.update(
    {
        "figure.facecolor": BG,
        "axes.facecolor": PANEL,
        "axes.edgecolor": GRID,
        "axes.labelcolor": FG,
        "text.color": FG,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "grid.color": GRID,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": FG,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.facecolor": BG,
        "figure.autolayout": True,
    }
)


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _monthly(returns: pd.Series) -> pd.Series:
    try:
        return (1 + returns).resample("ME").prod() - 1
    except Exception:  # older pandas
        return (1 + returns).resample("M").prod() - 1


def equity_drawdown(returns: pd.Series, title: str = "Equity & drawdown") -> str:
    equity = (1 + returns).cumprod()
    dd = equity / equity.cummax() - 1

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1.2]}
    )
    ax1.plot(equity.index, equity.values, color=ACCENT, lw=1.6)
    ax1.fill_between(equity.index, 1.0, equity.values, color=ACCENT, alpha=0.08)
    ax1.set_title(title, loc="left")
    ax1.set_ylabel("Growth of $1")
    ax1.grid(alpha=0.25)
    ax1.axhline(1.0, color=MUTED, lw=0.8, ls="--")

    ax2.fill_between(dd.index, dd.values * 100, 0, color=DANGER, alpha=0.55)
    ax2.plot(dd.index, dd.values * 100, color=DANGER, lw=0.9)
    ax2.set_ylabel("Drawdown %")
    ax2.grid(alpha=0.2)
    return _b64(fig)


def monthly_heatmap(returns: pd.Series) -> str:
    m = _monthly(returns)
    table = pd.DataFrame(
        {
            "year": m.index.year,
            "month": m.index.month,
            "val": m.values * 100,
        }
    ).pivot_table(index="year", columns="month", values="val")

    fig, ax = plt.subplots(figsize=(10, max(2.2, 0.42 * len(table) + 1.2)))
    data = table.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(data)) if np.isfinite(data).any() else 1.0
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(table.shape[1]))
    ax.set_xticklabels(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][
            : table.shape[1]
        ]
    )
    ax.set_yticks(range(table.shape[0]))
    ax.set_yticklabels(table.index)
    cmap = plt.get_cmap("RdYlGn")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i, j]):
                norm_val = (data[i, j] + vmax) / (2 * vmax) if vmax else 0.5
                rgba = cmap(np.clip(norm_val, 0, 1))
                lum = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                ax.text(
                    j, i, f"{data[i, j]:.1f}",
                    ha="center", va="center", fontsize=7.5,
                    color="#111827" if lum > 0.55 else "#f8fafc",
                )
    ax.set_title("Monthly returns (%)", loc="left")
    fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    return _b64(fig)


def rolling_profile(returns: pd.Series, window: int = 63) -> str:
    ppy = 252 if len(returns) > 300 else 52
    roll_sharpe = (
        returns.rolling(window).mean() / returns.rolling(window).std(ddof=1)
    ) * np.sqrt(ppy)
    roll_vol = returns.rolling(window).std(ddof=1) * np.sqrt(ppy)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True)
    ax1.plot(roll_sharpe.index, roll_sharpe.values, color=NEUTRAL, lw=1.2)
    ax1.axhline(0, color=MUTED, lw=0.8, ls="--")
    ax1.axhline(1, color=ACCENT, lw=0.8, ls=":")
    ax1.set_title(f"Rolling Sharpe ({window} periods)", loc="left")
    ax1.grid(alpha=0.25)

    ax2.plot(roll_vol.index, roll_vol.values * 100, color="#fbbf24", lw=1.2)
    ax2.set_title(f"Rolling volatility ({window} periods)", loc="left")
    ax2.set_ylabel("%")
    ax2.grid(alpha=0.25)
    return _b64(fig)


def return_distribution(returns: pd.Series) -> str:
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.hist(returns.values * 100, bins=60, color=NEUTRAL, alpha=0.75)
    var95 = returns.quantile(0.05) * 100
    ax.axvline(var95, color=DANGER, lw=1.4, ls="--", label=f"VaR 95%: {var95:.2f}%")
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_title("Period return distribution", loc="left")
    ax.set_xlabel("Return %")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(alpha=0.25, axis="y")
    return _b64(fig)


def yearly_bars(returns: pd.Series) -> str:
    yearly = (1 + returns).groupby(returns.index.year).prod() - 1
    if yearly.empty:
        return ""
    fig, ax = plt.subplots(figsize=(11, 3.4))
    colors = [ACCENT if v >= 0 else DANGER for v in yearly.values]
    ax.bar([str(y) for y in yearly.index], yearly.values * 100, color=colors)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_title("Calendar-year returns (%)", loc="left")
    ax.grid(alpha=0.2, axis="y")
    for i, v in enumerate(yearly.values * 100):
        ax.text(i, v + (1.2 if v >= 0 else -3.0), f"{v:.1f}", ha="center", fontsize=8)
    return _b64(fig)


def compare_curves(stack: Dict[str, pd.Series], title: str = "Cumulative growth") -> str:
    fig, ax = plt.subplots(figsize=(11, 4.6))
    palette = [ACCENT, NEUTRAL, "#fbbf24", "#c084fc", "#22d3ee", DANGER, "#a3e635"]
    for i, (label, r) in enumerate(stack.items()):
        equity = (1 + r).cumprod()
        ax.plot(equity.index, equity.values, lw=1.4, label=label, color=palette[i % len(palette)])
    ax.axhline(1.0, color=MUTED, lw=0.8, ls="--")
    ax.set_title(title, loc="left")
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=8)
    ax.grid(alpha=0.25)
    return _b64(fig)


def correlation_heatmap(corr: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(max(5, 1.0 * len(corr)), max(4, 0.9 * len(corr))))
    im = ax.imshow(corr.to_numpy(), cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr)))
    ax.set_yticklabels(corr.index, fontsize=8)
    cmap = plt.get_cmap("coolwarm")
    for i in range(len(corr)):
        for j in range(len(corr)):
            rgba = cmap((corr.iloc[i, j] + 1) / 2)
            lum = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7.5,
                    color="#111827" if lum > 0.55 else "#f8fafc")
    ax.set_title("Return correlation", loc="left")
    fig.colorbar(im, ax=ax, shrink=0.75, pad=0.02)
    return _b64(fig)


def walkforward_bars(folds: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(11, 3.6))
    labels = [f"F{i+1}" for i in range(len(folds))]
    ax.bar(labels, folds["total_return"].values * 100,
           color=[ACCENT if v >= 0 else DANGER for v in folds["total_return"].values])
    ax2 = ax.twinx()
    ax2.plot(labels, folds["sharpe"].values, color="#fbbf24", marker="o", lw=1.2)
    ax2.axhline(0, color=MUTED, lw=0.7, ls=":")
    ax.set_title("Walk-forward folds: return (bars) vs Sharpe (line)", loc="left")
    ax.set_ylabel("Return %")
    ax2.set_ylabel("Sharpe")
    ax.grid(alpha=0.2, axis="y")
    return _b64(fig)


def montecarlo_paths(paths: np.ndarray, actual: Optional[pd.Series] = None) -> str:
    fig, ax = plt.subplots(figsize=(11, 4.2))
    n_show = min(120, paths.shape[0])
    for i in range(n_show):
        ax.plot(paths[i], color="#374151", lw=0.6, alpha=0.6)
    if actual is not None:
        ax.plot(actual.values, color=ACCENT, lw=2.0, label="Actual")
        ax.legend(frameon=False, loc="upper left")
    ax.set_title(f"Monte Carlo equity paths ({paths.shape[0]} runs)", loc="left")
    ax.set_ylabel("Growth of $1")
    ax.grid(alpha=0.15)
    return _b64(fig)

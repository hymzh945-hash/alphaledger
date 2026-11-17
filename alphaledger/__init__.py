"""AlphaLedger — offline strategy performance audit, built for retail quants.

Public API
----------
>>> import alphaledger as al
>>> al.report("returns.csv", name="BTC momentum", out="report.html")
"""

from __future__ import annotations

from . import audit, charts, data, licensing, metrics, report
from .licensing import LicenseError
from .metrics import advanced_metrics, core_metrics, prepare_returns
from .version import version

__version__ = version
__all__ = [
    "audit",
    "charts",
    "core_metrics",
    "advanced_metrics",
    "data",
    "licensing",
    "metrics",
    "prepare_returns",
    "report",
    "LicenseError",
    "__version__",
]


def report_file(
    path,
    name: str | None = None,
    benchmark_path: str | None = None,
    out: str = "alphaledger-report.html",
    walkforward: bool = False,
    montecarlo: bool = False,
) -> str:
    """Convenience wrapper: load a file and write an HTML report."""
    r = prepare_returns(data.load_series(path))
    bench = prepare_returns(data.load_series(benchmark_path)) if benchmark_path else None
    wf = audit.walk_forward(r) if walkforward else None
    mc = audit.monte_carlo(r) if montecarlo else None
    html = report.build_report(r, name=name or str(path), benchmark=bench,
                               walkforward=wf, montecarlo=mc)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out

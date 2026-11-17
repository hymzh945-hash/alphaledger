"""Command line interface: `alphaledger <command>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import audit, data, licensing, metrics as m, report
from .version import version


def _read(path: str) -> pd.DataFrame:
    return pd.read_csv(Path(path).expanduser())


def _series(path: str, name: str | None = None) -> pd.Series:
    s = data.load_series(path)
    r = m.prepare_returns(s)
    r.name = name or Path(path).stem
    return r


def _demo_returns(n: int = 1500, seed: int = 42) -> pd.Series:
    """Synthetic two-regime return stream so the tool can be tried with no data."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    regimes = np.repeat([0.0009, -0.0002, 0.0012, 0.0003], [int(n * 0.35), int(n * 0.2), int(n * 0.3), n - int(n * 0.85)])
    vol = np.repeat([0.011, 0.02, 0.008, 0.014], [int(n * 0.35), int(n * 0.2), int(n * 0.3), n - int(n * 0.85)])
    r = rng.normal(regimes, vol, n)
    # a couple of crash days
    r[n // 3] = -0.052
    r[n // 2] = -0.081
    return pd.Series(r, index=idx, name="Demo strategy")


def cmd_report(args) -> int:
    r = _series(args.input, args.name)
    bench = _series(args.benchmark) if args.benchmark else None
    if bench is not None:
        bench = bench.reindex(r.index).dropna()
        r = r.reindex(bench.index)

    wf = mc = cmp = None
    if args.walkforward:
        licensing.require_pro("walk_forward")
        wf = audit.walk_forward(r, folds=args.folds, benchmark=bench)
    if args.montecarlo:
        licensing.require_pro("monte_carlo")
        mc = audit.monte_carlo(r, runs=args.runs)
    if args.compare:
        licensing.require_pro("multi_asset_compare")
        series = {"Main": r}
        for extra in args.compare:
            series[Path(extra).stem] = _series(extra).reindex(r.index)
        cmp = audit.compare(series, benchmark=bench)

    html = report.build_report(
        r,
        name=args.name or r.name,
        benchmark=bench,
        walkforward=wf,
        montecarlo=mc,
        comparison=cmp,
        meta={"Source": str(Path(args.input).name), "Observations per year": f"{m.periods_per_year(r.index):.0f}"},
    )
    out = Path(args.out).expanduser()
    out.write_text(html, encoding="utf-8")

    metrics_dict = m.advanced_metrics(r, bench) if licensing.is_pro() else m.core_metrics(r, bench)
    if args.csv:
        pd.Series(metrics_dict).to_csv(Path(args.csv).expanduser())
        print(f"metrics  -> {args.csv}")
    print(f"report   -> {out}")
    _print_summary(metrics_dict, r.name or "strategy")
    return 0


def _print_summary(mm: dict, name: str) -> None:
    def pct(v):
        return f"{v * 100:.2f}%" if isinstance(v, (int, float)) else "—"

    print(f"\n{name}")
    print(f"  total return      {pct(mm.get('total_return'))}")
    print(f"  CAGR              {pct(mm.get('cagr'))}")
    print(f"  Sharpe            {mm.get('sharpe', 0):.2f}")
    print(f"  max drawdown      {pct(mm.get('max_drawdown'))}")
    print(f"  win rate          {pct(mm.get('win_rate'))}")
    print(f"  profit factor     {mm.get('profit_factor', 0):.2f}")
    print(f"  license           {licensing.get_license().describe()}\n")


def cmd_demo(args) -> int:
    r = _demo_returns()
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    prices = (1 + r).cumprod()
    pd.DataFrame({"date": r.index.date, "equity": prices.values, "return": r.values}).to_csv(
        out_dir / "demo_returns.csv", index=False
    )
    html = report.build_report(r, name="Demo strategy (synthetic)", pro=licensing.is_pro())
    (out_dir / "demo_report.html").write_text(html, encoding="utf-8")
    print(f"sample data -> {out_dir / 'demo_returns.csv'}")
    print(f"report      -> {out_dir / 'demo_report.html'}")
    return 0


def cmd_compare(args) -> int:
    licensing.require_pro("multi_asset_compare")
    series = {Path(p).stem: _series(p) for p in args.inputs}
    bench = _series(args.benchmark) if args.benchmark else None
    result = audit.compare(series, benchmark=bench)
    out = Path(args.out).expanduser()
    html = report.build_report(
        series[next(iter(series))], name="Strategy comparison", comparison=result,
        montecarlo=audit.monte_carlo(audit.combine(series), runs=args.runs) if args.runs else None,
    )
    out.write_text(html, encoding="utf-8")
    table = result["table"][["total_return", "cagr", "sharpe", "max_drawdown", "win_rate"]]
    print(table.round(4).to_string())
    print(f"\nreport -> {out}")
    return 0


def cmd_walkforward(args) -> int:
    licensing.require_pro("walk_forward")
    r = _series(args.input)
    wf = audit.walk_forward(r, folds=args.folds)
    print(wf["table"].round(4).to_string())
    print(f"\nverdict: {wf['summary']['verdict']}")
    if args.out:
        Path(args.out).expanduser().write_text(
            report.build_report(r, name=Path(args.input).stem, walkforward=wf), encoding="utf-8"
        )
        print(f"report -> {args.out}")
    return 0


def cmd_montecarlo(args) -> int:
    licensing.require_pro("monte_carlo")
    r = _series(args.input)
    mc = audit.monte_carlo(r, runs=args.runs)
    for k, v in mc["stats"].items():
        print(f"  {k:<18} {v:.4f}" if isinstance(v, float) else f"  {k:<18} {v}")
    if args.out:
        Path(args.out).expanduser().write_text(
            report.build_report(r, name=Path(args.input).stem, montecarlo=mc), encoding="utf-8"
        )
        print(f"report -> {args.out}")
    return 0


def cmd_fetch(args) -> int:
    if args.source == "okx":
        df = data.fetch_okx(args.symbol, bar=args.bar, limit=args.limit)
    else:
        df = data.fetch_binance(args.symbol, interval=args.bar, limit=args.limit)
    out = Path(args.out).expanduser()
    data.to_csv(df, out)
    print(f"{len(df)} candles {df.index[0]} -> {df.index[-1]}\nsaved -> {out}")
    return 0


def cmd_serve(args) -> int:
    from .server import serve

    serve(port=args.port, open_browser=not args.no_open)
    return 0


def cmd_license(args) -> int:
    lic = licensing.get_license(refresh=True)
    print(lic.describe())
    print(f"source: {lic.source}")
    if lic.tier == "pro" and not lic.is_pro:
        print("This license has expired. Renew on Gumroad to keep Pro features.")
    print("\nPro features:")
    for key, label in licensing.PRO_FEATURES.items():
        print(f"  - {label}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alphaledger", description="AlphaLedger — local strategy performance audit")
    p.add_argument("--version", action="version", version=f"AlphaLedger {version}")
    sub = p.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("report", help="build a full HTML tearsheet")
    rp.add_argument("-i", "--input", required=True, help="CSV/parquet with a date column and returns or equity")
    rp.add_argument("-b", "--benchmark", help="optional benchmark CSV")
    rp.add_argument("-n", "--name", default=None)
    rp.add_argument("-o", "--out", default="alphaledger-report.html")
    rp.add_argument("--csv", help="also write metrics to this CSV")
    rp.add_argument("--walkforward", action="store_true", help="Pro: add walk-forward audit")
    rp.add_argument("--montecarlo", action="store_true", help="Pro: add Monte Carlo stress test")
    rp.add_argument("--compare", nargs="*", default=None, help="Pro: extra CSVs to compare against")
    rp.add_argument("--folds", type=int, default=4)
    rp.add_argument("--runs", type=int, default=2000)
    rp.set_defaults(func=cmd_report)

    dp = sub.add_parser("demo", help="generate synthetic data + report")
    dp.add_argument("-o", "--out", default="alphaledger-demo")
    dp.set_defaults(func=cmd_demo)

    cp = sub.add_parser("compare", help="Pro: compare several strategies")
    cp.add_argument("inputs", nargs="+")
    cp.add_argument("-b", "--benchmark")
    cp.add_argument("-o", "--out", default="comparison.html")
    cp.add_argument("--runs", type=int, default=0)
    cp.set_defaults(func=cmd_compare)

    wp = sub.add_parser("walkforward", help="Pro: fold-by-fold consistency")
    wp.add_argument("-i", "--input", required=True)
    wp.add_argument("--folds", type=int, default=4)
    wp.add_argument("-o", "--out")
    wp.set_defaults(func=cmd_walkforward)

    mp = sub.add_parser("montecarlo", help="Pro: bootstrap drawdown stress")
    mp.add_argument("-i", "--input", required=True)
    mp.add_argument("--runs", type=int, default=2000)
    mp.add_argument("-o", "--out")
    mp.set_defaults(func=cmd_montecarlo)

    fp = sub.add_parser("fetch", help="download candles from OKX or Binance")
    fp.add_argument("-s", "--source", choices=["okx", "binance"], default="okx")
    fp.add_argument("--symbol", default="BTC-USDT")
    fp.add_argument("--bar", default="1H")
    fp.add_argument("--limit", type=int, default=100)
    fp.add_argument("-o", "--out", default="candles.csv")
    fp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser("serve", help="start the local web UI")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--no-open", action="store_true")
    sp.set_defaults(func=cmd_serve)

    lp = sub.add_parser("license", help="show license status")
    lp.set_defaults(func=cmd_license)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except licensing.LicenseError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"file not found: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Data loading: local files, plus free public candle endpoints (OKX / Binance)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

import pandas as pd

from .metrics import prepare_returns

__all__ = ["load_series", "load_prices", "from_ohlcv", "fetch_okx", "fetch_binance", "to_csv"]

_TIMEOUT = 20


def load_series(
    path: str | Path,
    date_col: Optional[str] = None,
    value_col: Optional[str] = None,
) -> pd.Series:
    """Load a single numeric column from CSV / TSV / Parquet / JSON as a series."""
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(p)

    suffix = p.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(p)
    elif suffix in {".json"}:
        df = pd.read_json(p)
    else:
        sep = "\t" if suffix in {".tsv", ".tab"} else None
        df = pd.read_csv(p, sep=sep, engine="python")

    return _extract(df, date_col, value_col)


def _extract(df: pd.DataFrame, date_col: Optional[str], value_col: Optional[str]) -> pd.Series:
    if df.empty:
        raise ValueError("file contains no rows")

    if date_col is None:
        for cand in ("date", "Date", "datetime", "time", "timestamp", "index"):
            if cand in df.columns:
                date_col = cand
                break

    if date_col is not None and date_col in df.columns:
        idx = pd.to_datetime(df[date_col], errors="coerce", format="mixed")
        df = df.drop(columns=[date_col]).set_index(idx)
    elif isinstance(df.index, pd.DatetimeIndex):
        pass
    else:
        df.index = pd.to_datetime(df.index, errors="coerce", format="mixed")

    if value_col is None:
        for cand in ("return", "returns", "ret", "pnl", "equity", "close", "Close", "value", "nav"):
            if cand in df.columns:
                value_col = cand
                break
    if value_col is None:
        numeric = df.select_dtypes("number").columns
        if not len(numeric):
            raise ValueError("no numeric column found in file")
        value_col = numeric[0]

    series = pd.to_numeric(df[value_col], errors="coerce")
    series.name = value_col
    return series[~series.index.isna()].sort_index()


def load_prices(path: str | Path, **kwargs) -> pd.Series:
    """Load a price column; returns stay raw (no pct_change here)."""
    return load_series(path, **kwargs)


def from_ohlcv(df: pd.DataFrame, price: str = "close", fees_bps: float = 0.0) -> pd.DataFrame:
    """Turn an OHLCV frame into buy-and-hold returns, optionally net of fees."""
    col = price if price in df.columns else [c for c in df.columns if c.lower() == price][0]
    px = pd.to_numeric(df[col], errors="coerce").dropna()
    r = px.pct_change().dropna()
    if fees_bps:
        r = r - fees_bps / 10_000
    return pd.DataFrame({"close": px, "return": r})


# --------------------------------------------------------------------------- #
# public data endpoints
# --------------------------------------------------------------------------- #
def _get_json(url: str, params: dict) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "AlphaLedger/0.1"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


_OHLCV_COLS = ["ts", "open", "high", "low", "close", "volume"]


def fetch_okx(inst_id: str = "BTC-USDT", bar: str = "1H", limit: int = 300) -> pd.DataFrame:
    """Recent candles from OKX public market data (no API key needed)."""
    data = _get_json(
        "https://www.okx.com/api/v5/market/history-candles",
        {"instId": inst_id, "bar": bar, "limit": min(int(limit), 100)},
    )
    rows = data.get("data", [])
    if not rows:
        raise RuntimeError(f"OKX returned no candles for {inst_id}: {data.get('msg', '')}")
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
    df = df[["ts", "open", "high", "low", "close", "vol"]]
    df.columns = _OHLCV_COLS
    for c in _OHLCV_COLS[1:]:
        df[c] = pd.to_numeric(df[c])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    return df.set_index("ts").sort_index()


def fetch_binance(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Recent klines from Binance public market data (no API key needed)."""
    rows = _get_json(
        "https://api.binance.com/api/v3/klines",
        {"symbol": symbol.upper(), "interval": interval, "limit": min(int(limit), 1000)},
    )
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"Binance returned no klines for {symbol}")
    df = pd.DataFrame(rows)
    df = df.iloc[:, :6]
    df.columns = _OHLCV_COLS
    for c in _OHLCV_COLS[1:]:
        df[c] = pd.to_numeric(df[c])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("ts").sort_index()


def to_csv(df: pd.DataFrame, path: str | Path) -> Path:
    p = Path(path).expanduser()
    df.to_csv(p)
    return p

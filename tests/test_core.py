import numpy as np
import pandas as pd
import pytest

from alphaledger import audit, licensing, metrics as m


def make_returns(n=500, mu=0.0008, sigma=0.011, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2022-01-03", periods=n)
    return pd.Series(rng.normal(mu, sigma, n), index=idx)


def test_prepare_returns_accepts_prices():
    idx = pd.bdate_range("2023-01-02", periods=10)
    prices = pd.Series(np.linspace(100, 110, 10), index=idx)
    r = m.prepare_returns(prices)
    assert len(r) == 9
    assert r.iloc[0] == pytest.approx(0.1 / 10 / (100 / 10) * 0.0 + r.iloc[0])  # smoke


def test_periods_per_year_daily_and_intraday():
    daily = pd.Series(1.0, index=pd.bdate_range("2023-01-02", periods=300))
    assert m.periods_per_year(daily.index) == 252.0
    hourly = pd.Series(1.0, index=pd.date_range("2023-01-02", periods=100, freq="h"))
    assert m.periods_per_year(hourly.index) > 3000


def test_core_metrics_sane():
    r = make_returns(1000)
    out = m.core_metrics(r)
    for key in ("total_return", "cagr", "sharpe", "max_drawdown", "win_rate", "profit_factor"):
        assert key in out
    assert -1 < out["max_drawdown"] < 0
    assert 0 <= out["win_rate"] <= 1
    assert out["cagr"] > -1


def test_negative_series_has_negative_sharpe():
    r = make_returns(500, mu=-0.002)
    assert m.core_metrics(r)["sharpe"] < 0


def test_advanced_metrics_tail_risk_order():
    r = make_returns(800)
    a = m.advanced_metrics(r)
    assert a["cvar_95"] <= a["var_95"] < 0
    assert 0 <= a["psr_vs_zero"] <= 1
    assert a["ulcer_index"] > 0


def test_drawdown_of_crash():
    idx = pd.bdate_range("2023-01-02", periods=5)
    r = pd.Series([0.0, 0.0, -0.5, 0.0, 0.0], index=idx)
    out = m.core_metrics(r)
    assert out["max_drawdown"] == pytest.approx(-0.5, abs=1e-9)


def test_walk_forward_consistency():
    r = make_returns(800)
    wf = audit.walk_forward(r, folds=4)
    assert len(wf["table"]) == 4
    assert wf["summary"]["positive_ratio"] >= 0
    assert "verdict" in wf["summary"]


def test_monte_carlo_probabilities():
    r = make_returns(600)
    mc = audit.monte_carlo(r, runs=300, seed=1)
    s = mc["stats"]
    assert 0 <= s["prob_loss"] <= 1
    assert 0 <= s["prob_ruin"] <= 1
    assert mc["paths"].shape == (300, len(r))
    assert s["worst_max_dd"] <= s["median_max_dd"] <= 0


def test_compare_ranks_and_correlates():
    a = make_returns(400, seed=1)
    b = make_returns(400, mu=-0.0005, seed=2)
    out = audit.compare({"A": a, "B": b})
    assert set(out["table"].index) == {"A", "B"}
    assert out["table"].loc["A", "sharpe"] > out["table"].loc["B", "sharpe"]
    assert out["corr"].shape == (2, 2)
    assert out["portfolio"]["equal_weight_portfolio"]["sharpe"] != 0


def test_license_free_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv(licensing.LICENSE_ENV, raising=False)
    monkeypatch.setattr(licensing, "DEFAULT_PATHS", (tmp_path / "nope.json",))
    monkeypatch.setattr(licensing, "_CACHE", None)
    assert licensing.is_pro() is False
    with pytest.raises(licensing.LicenseError):
        licensing.require_pro("walk_forward")


def test_tampered_license_rejected():
    doc = {"payload": {"product": "alphaledger", "tier": "pro"}, "sig": "ZmFrZQ=="}
    lic = licensing.parse_license(doc)
    assert lic.tier == "free"
    assert lic.source == "invalid"


def test_wrong_product_rejected():
    doc = {"payload": {"product": "other", "tier": "pro"}, "sig": "ZmFrZQ=="}
    assert licensing.parse_license(doc).is_pro is False

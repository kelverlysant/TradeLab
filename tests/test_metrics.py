import math

import numpy as np
import pandas as pd
import pytest

from tradelab.analytics import (
    annualized_return,
    annualized_volatility,
    compute_metrics,
    drawdown_series,
    exposure,
    max_drawdown,
    sharpe_ratio,
    total_return,
)
from tradelab.backtesting import run_backtest


def test_total_return():
    assert total_return(pd.Series([100, 120, 150])) == pytest.approx(0.5)


def test_first_row_is_ignored_in_annualization():
    # 1 registro inicial + 252 períodos de 0.1% -> anualizado = 1.001^252 - 1
    returns = pd.Series([0.0] + [0.001] * 252)
    assert annualized_return(returns) == pytest.approx(1.001**252 - 1)


def test_annualized_return_total_loss():
    assert annualized_return(pd.Series([0.0, -1.0, 0.0])) == -1.0


def test_volatility_of_constant_returns_is_zero():
    assert annualized_volatility(pd.Series([0.0, 0.01, 0.01, 0.01])) == pytest.approx(0.0)


def test_volatility_annualization():
    r = pd.Series([0.0, 0.01, -0.01, 0.02, -0.02])
    expected = r.iloc[1:].std(ddof=1) * np.sqrt(252)
    assert annualized_volatility(r) == pytest.approx(expected)


def test_sharpe_value():
    r = pd.Series([0.0, 0.01, 0.02, -0.01, 0.015])
    eff = r.iloc[1:]
    expected = eff.mean() / eff.std(ddof=1) * np.sqrt(252)
    assert sharpe_ratio(r) == pytest.approx(expected)


def test_sharpe_with_zero_volatility_is_nan():
    assert math.isnan(sharpe_ratio(pd.Series([0.0, 0.0, 0.0, 0.0])))


def test_drawdown_and_max_drawdown():
    equity = pd.Series([100, 120, 90, 130, 117])
    dd = drawdown_series(equity)
    assert dd.tolist() == pytest.approx([0, 0, -0.25, 0, -0.1])
    assert max_drawdown(equity) == pytest.approx(-0.25)


def test_max_drawdown_monotonic_up_is_zero():
    assert max_drawdown(pd.Series([1, 2, 3])) == 0


def test_exposure_ignores_first_row():
    assert exposure(pd.Series([0, 1, 1, 0, 1])) == pytest.approx(0.75)


def test_metrics_require_two_rows():
    with pytest.raises(ValueError):
        annualized_return(pd.Series([0.0]))


def test_compute_metrics_from_backtest(ohlcv_factory):
    df = ohlcv_factory([100, 110, 99, 120])
    df["signal"] = 1
    metrics = compute_metrics(run_backtest(df, initial_capital=1_000).frame)
    assert metrics["total_return"] == pytest.approx(0.2)
    assert metrics["final_equity"] == pytest.approx(1_200)
    assert metrics["max_drawdown"] == pytest.approx(-0.1)
    assert metrics["exposure"] == pytest.approx(1.0)
    assert metrics["n_trades"] == 1

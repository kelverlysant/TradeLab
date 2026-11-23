"""Testes da camada visual. São pulados se o extra [ui] não estiver instalado."""

from pathlib import Path

import pytest

pytest.importorskip("plotly")

from tradelab.analytics import Experiment, compare_experiments  # noqa: E402
from tradelab.backtesting import run_backtest  # noqa: E402
from tradelab.data import generate_synthetic_ohlcv  # noqa: E402
from tradelab.risk import apply_stop_loss  # noqa: E402
from tradelab.strategies import BuyAndHold, SMACrossover  # noqa: E402
from tradelab.visualization import (  # noqa: E402
    distribution_figure,
    drawdown_figure,
    equity_figure,
    price_and_signals_figure,
    scenario_bar_figure,
)


@pytest.fixture
def backtest():
    data = generate_synthetic_ohlcv("bear", seed=42)
    stop = apply_stop_loss(SMACrossover(10, 30).generate_signals(data), 0.03)
    return run_backtest(stop.data), stop.events


def test_price_figure_marks_every_stop(backtest):
    result, events = backtest
    fig = price_and_signals_figure(result.frame, events)
    stop_trace = next(t for t in fig.data if t.name == "Stop")
    assert len(stop_trace.x) == len(events) > 0


def test_price_figure_buys_match_engine_entries(backtest):
    result, events = backtest
    fig = price_and_signals_figure(result.frame, events)
    buys = next(t for t in fig.data if t.name == "Compra")
    entries = int((result.frame["position"].diff() == 1).sum())
    assert len(buys.x) == entries


def test_equity_and_drawdown_have_one_trace_per_strategy(backtest):
    result, _ = backtest
    equities = {"A": result.equity, "B": result.equity * 1.1}
    assert len(equity_figure(equities).data) == 2
    assert len(drawdown_figure(equities).data) == 2


def test_scenario_figures():
    exps = [Experiment("SMA", SMACrossover(10, 30)), Experiment("B&H", BuyAndHold())]
    raw = compare_experiments(exps, seeds=[1, 2])
    summary = raw.groupby(["scenario", "experiment"], sort=False).mean(numeric_only=True).reset_index()
    assert len(scenario_bar_figure(summary, "sharpe").data) == 2
    assert len(distribution_figure(raw, "total_return", "bull").data) == 2


def test_streamlit_app_runs_without_errors():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    app_path = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"
    at = AppTest.from_file(str(app_path), default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) == 3

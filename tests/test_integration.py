"""Testes de integração: dados -> estratégia -> risco -> motor -> métricas -> comparação."""

import numpy as np
import pytest

from tradelab.analytics import Experiment, compare_experiments, compute_metrics, summarize_by_scenario
from tradelab.backtesting import run_backtest
from tradelab.data import generate_synthetic_ohlcv
from tradelab.risk import apply_stop_loss
from tradelab.strategies import BuyAndHold, SMACrossover


@pytest.mark.parametrize("scenario", ["bull", "bear", "sideways"])
def test_full_pipeline_runs(scenario):
    data = generate_synthetic_ohlcv(scenario, seed=42)
    signals = SMACrossover(10, 30).generate_signals(data)
    stopped = apply_stop_loss(signals, 0.03)
    result = run_backtest(stopped.data, cost_bps=5)
    metrics = compute_metrics(result.frame)
    assert np.isfinite(metrics["total_return"])
    assert metrics["max_drawdown"] <= 0
    assert 0 <= metrics["exposure"] <= 1


def test_buy_and_hold_matches_asset_return():
    data = generate_synthetic_ohlcv("bull", seed=7)
    result = run_backtest(BuyAndHold().generate_signals(data))
    asset_return = data["Close"].iloc[-1] / data["Close"].iloc[0] - 1
    assert compute_metrics(result.frame)["total_return"] == pytest.approx(asset_return)


def test_stop_never_increases_exposure():
    data = generate_synthetic_ohlcv("bear", seed=3)
    signals = SMACrossover(10, 30).generate_signals(data)
    stopped = apply_stop_loss(signals, 0.03).data
    assert (stopped["signal"] <= stopped["raw_signal"]).all()


def test_every_stop_event_is_reflected_in_engine():
    data = generate_synthetic_ohlcv("sideways", seed=11)
    res = apply_stop_loss(SMACrossover(10, 30).generate_signals(data), 0.02)
    frame = run_backtest(res.data).frame
    assert res.n_stops > 0
    for _, ev in res.events.iterrows():
        assert frame.loc[ev["execution_date"], "position"] == 1
        if ev["flat_position_date"] is not None:
            assert frame.loc[ev["flat_position_date"], "position"] == 0
        assert ev["trigger_price"] <= ev["stop_price"]


def test_compare_experiments_shape_and_reproducibility():
    sma = SMACrossover(10, 30)
    exps = [Experiment("SMA", sma), Experiment("SMA+Stop", sma, 0.03), Experiment("B&H", BuyAndHold())]
    a = compare_experiments(exps, seeds=[1, 2])
    b = compare_experiments(exps, seeds=[1, 2])
    assert len(a) == 3 * 2 * 3
    assert a.equals(b)
    summary = summarize_by_scenario(a)
    assert len(summary) == 9

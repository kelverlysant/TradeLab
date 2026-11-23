import pytest

from tradelab.backtesting import BacktestError, run_backtest


def with_signal(df, signal):
    out = df.copy()
    out["signal"] = signal
    return out


def test_position_is_signal_shifted(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 101, 102, 103]), [1, 0, 1, 1])
    frame = run_backtest(df).frame
    assert frame["position"].tolist() == [0, 1, 0, 1]


def test_no_look_ahead_first_period_has_no_exposure(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 200]), [1, 1])
    frame = run_backtest(df).frame
    assert frame["gross_return"].iloc[0] == 0
    assert frame["gross_return"].iloc[1] == pytest.approx(1.0)


def test_signal_on_last_bar_has_no_effect(ohlcv_factory):
    """Mudar o sinal da última barra não pode alterar nenhum resultado já calculado."""
    base = ohlcv_factory([100, 105, 103, 108])
    a = run_backtest(with_signal(base, [1, 1, 1, 0])).frame
    b = run_backtest(with_signal(base, [1, 1, 1, 1])).frame
    assert a["equity"].equals(b["equity"])


def test_market_return_values(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 110, 99]), [0, 0, 0])
    frame = run_backtest(df).frame
    assert frame["market_return"].tolist() == pytest.approx([0.0, 0.10, -0.10])


def test_buy_and_hold_equity_tracks_price(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 110, 121]), [1, 1, 1])
    result = run_backtest(df, initial_capital=1_000)
    assert result.final_equity == pytest.approx(1_210)


def test_flat_strategy_keeps_capital(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 50, 200]), [0, 0, 0])
    result = run_backtest(df, initial_capital=1_000, cost_bps=10)
    assert result.final_equity == pytest.approx(1_000)


def test_turnover_counts_entries_and_exits(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 101, 102, 103, 104]), [1, 1, 0, 1, 1])
    frame = run_backtest(df).frame
    # position = [0,1,1,0,1]
    assert frame["turnover"].tolist() == [0, 1, 0, 1, 1]
    assert run_backtest(df).n_trades == 3


def test_costs_charged_when_position_starts(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 100, 100]), [1, 1, 1])
    frame = run_backtest(df, cost_bps=10, slippage_bps=5).frame
    assert frame["cost"].tolist() == pytest.approx([0.0, 0.0015, 0.0])
    assert frame["net_return"].iloc[1] == pytest.approx(-0.0015)


def test_costs_reduce_equity(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 101, 102, 101, 103]), [1, 0, 1, 0, 1])
    no_cost = run_backtest(df).final_equity
    with_cost = run_backtest(df, cost_bps=20).final_equity
    assert with_cost < no_cost


def test_equity_is_compounded_net_return(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 105, 102, 110]), [1, 1, 0, 1])
    frame = run_backtest(df, initial_capital=500, cost_bps=7).frame
    expected = 500 * (1 + frame["net_return"]).cumprod()
    assert frame["equity"].tolist() == pytest.approx(expected.tolist())


def test_input_is_not_mutated(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 101]), [1, 1])
    cols = list(df.columns)
    run_backtest(df)
    assert list(df.columns) == cols


@pytest.mark.parametrize("signal", [[1, 2, 0], [1, -1, 0], [1, None, 0]])
def test_invalid_signal_values(ohlcv_factory, signal):
    df = with_signal(ohlcv_factory([100, 101, 102]), signal)
    with pytest.raises(BacktestError):
        run_backtest(df)


def test_missing_signal_column(ohlcv_factory):
    with pytest.raises(BacktestError, match="signal"):
        run_backtest(ohlcv_factory([100, 101]))


def test_single_row_fails(ohlcv_factory):
    with pytest.raises(BacktestError, match="2 observações"):
        run_backtest(with_signal(ohlcv_factory([100]), [1]))


def test_unsorted_index_fails(ohlcv_factory):
    df = with_signal(ohlcv_factory([100, 101, 102]), [1, 1, 1]).iloc[::-1]
    with pytest.raises(BacktestError, match="crescente"):
        run_backtest(df)


@pytest.mark.parametrize("kwargs", [{"initial_capital": 0}, {"cost_bps": -1}, {"slippage_bps": -1}])
def test_invalid_parameters(ohlcv_factory, kwargs):
    df = with_signal(ohlcv_factory([100, 101]), [1, 1])
    with pytest.raises(BacktestError):
        run_backtest(df, **kwargs)

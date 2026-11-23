import pytest

from tradelab.strategies import BuyAndHold, SMACrossover, Strategy


def test_sma_signal_only_zero_or_one(ohlcv_factory):
    data = ohlcv_factory(list(range(100, 160)))
    out = SMACrossover(3, 5).generate_signals(data)
    assert set(out["signal"].unique()) <= {0, 1}


def test_sma_warmup_is_zero(ohlcv_factory):
    data = ohlcv_factory(list(range(100, 120)))
    out = SMACrossover(3, 5).generate_signals(data)
    assert (out["signal"].iloc[:4] == 0).all()


def test_sma_uptrend_gives_long(ohlcv_factory):
    data = ohlcv_factory(list(range(100, 120)))
    out = SMACrossover(3, 5).generate_signals(data)
    assert (out["signal"].iloc[5:] == 1).all()


def test_sma_downtrend_gives_flat(ohlcv_factory):
    data = ohlcv_factory(list(range(120, 100, -1)))
    out = SMACrossover(3, 5).generate_signals(data)
    assert (out["signal"] == 0).all()


def test_sma_equal_averages_gives_zero(ohlcv_factory):
    data = ohlcv_factory([100.0] * 15)
    out = SMACrossover(3, 5).generate_signals(data)
    assert (out["signal"] == 0).all()


def test_sma_values_are_correct(ohlcv_factory):
    data = ohlcv_factory([1, 2, 3, 4, 5, 6])
    out = SMACrossover(2, 3).generate_signals(data)
    assert out["sma_short"].iloc[-1] == pytest.approx(5.5)
    assert out["sma_long"].iloc[-1] == pytest.approx(5.0)


def test_sma_does_not_mutate_input(ohlcv_factory):
    data = ohlcv_factory(list(range(100, 120)))
    cols = list(data.columns)
    SMACrossover(3, 5).generate_signals(data)
    assert list(data.columns) == cols


@pytest.mark.parametrize("short,long_", [(5, 5), (10, 3), (0, 5)])
def test_sma_invalid_windows(short, long_):
    with pytest.raises(ValueError):
        SMACrossover(short, long_)


def test_sma_missing_price_column(ohlcv_factory):
    with pytest.raises(KeyError):
        SMACrossover(2, 3).generate_signals(ohlcv_factory([1, 2, 3]).drop(columns=["Close"]))


def test_buy_and_hold_always_one(ohlcv_factory):
    out = BuyAndHold().generate_signals(ohlcv_factory([100, 90, 80]))
    assert (out["signal"] == 1).all()


def test_strategies_share_interface():
    assert isinstance(SMACrossover(), Strategy)
    assert isinstance(BuyAndHold(), Strategy)
    assert SMACrossover(10, 30).params() == {"short_window": 10, "long_window": 30}

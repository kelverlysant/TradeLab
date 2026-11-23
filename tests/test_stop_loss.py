"""Auditoria temporal do Stop-Loss.

Convenção verificada:
    entrada no fechamento da barra do sinal -> gatilho no fechamento da barra t
    -> execução presumida em t -> position == 0 a partir de t+1 no motor.
"""

import pandas as pd
import pytest

from tradelab.backtesting import run_backtest
from tradelab.risk import apply_stop_loss


def with_signal(df, signal):
    out = df.copy()
    out["signal"] = signal
    return out


@pytest.fixture
def drop_case(ohlcv_factory):
    # Entrada em t0 (Close 100). Queda para 98 (-2%) e 96 (-4%): stop de 3% dispara em t2.
    df = ohlcv_factory([100, 98, 96, 97, 99, 101])
    return with_signal(df, [1, 1, 1, 1, 1, 1])


def test_stop_triggers_on_correct_bar(drop_case):
    res = apply_stop_loss(drop_case, 0.03)
    assert res.n_stops == 1
    ev = res.events.iloc[0]
    idx = drop_case.index
    assert ev["entry_signal_date"] == idx[0]
    assert ev["entry_price"] == pytest.approx(100)
    assert ev["stop_price"] == pytest.approx(97)
    assert ev["trigger_date"] == idx[2]
    assert ev["trigger_price"] == pytest.approx(96)


def test_execution_and_flat_dates(drop_case):
    ev = apply_stop_loss(drop_case, 0.03).events.iloc[0]
    idx = drop_case.index
    assert ev["execution_date"] == idx[2]
    assert ev["flat_position_date"] == idx[3]


def test_observed_loss_can_exceed_stop(drop_case):
    ev = apply_stop_loss(drop_case, 0.03).events.iloc[0]
    assert ev["observed_loss"] == pytest.approx(-0.04)
    assert ev["observed_loss"] < -ev["stop_pct"]


def test_engine_position_matches_event_dates(drop_case):
    """Integração: o motor precisa mostrar posição zerada exatamente em flat_position_date."""
    res = apply_stop_loss(drop_case, 0.03)
    frame = run_backtest(res.data).frame
    ev = res.events.iloc[0]
    assert frame.loc[ev["execution_date"], "position"] == 1   # ainda exposto à queda até o fechamento do gatilho
    assert frame.loc[ev["flat_position_date"], "position"] == 0


def test_engine_loss_equals_observed_loss(drop_case):
    """Sem custos, a perda acumulada no motor até a execução = observed_loss do evento."""
    res = apply_stop_loss(drop_case, 0.03)
    frame = run_backtest(res.data, initial_capital=1.0).frame
    ev = res.events.iloc[0]
    assert frame.loc[ev["execution_date"], "equity"] - 1 == pytest.approx(ev["observed_loss"])
    # depois da execução, o patrimônio não muda mais (fora do mercado e bloqueado)
    assert frame["equity"].iloc[-1] == pytest.approx(frame.loc[ev["execution_date"], "equity"])


def test_reentry_blocked_until_new_crossover(ohlcv_factory):
    df = ohlcv_factory([100, 96, 97, 98, 99, 100, 101, 102])
    raw = [1, 1, 1, 1, 0, 1, 1, 1]
    res = apply_stop_loss(with_signal(df, raw), 0.03)
    # stop em t1; bloqueado em t2, t3; reset em t4 (raw=0); nova entrada em t5
    assert res.data["signal"].tolist() == [1, 0, 0, 0, 0, 1, 1, 1]
    assert res.data["stop_blocked"].tolist() == [0, 0, 1, 1, 0, 0, 0, 0]
    assert res.data["raw_signal"].tolist() == raw


def test_new_entry_resets_entry_price(ohlcv_factory):
    # 1ª operação: entra 100, stop em 96. Reset em t2, reentra em t3 a 90.
    # 90 * 0.97 = 87.3 -> 88 não dispara, 87 dispara.
    df = ohlcv_factory([100, 96, 95, 90, 88, 87])
    res = apply_stop_loss(with_signal(df, [1, 1, 0, 1, 1, 1]), 0.03)
    assert res.n_stops == 2
    assert res.events["entry_price"].tolist() == pytest.approx([100, 90])
    assert res.events["trigger_date"].tolist() == [df.index[1], df.index[5]]


def test_no_block_when_raw_signal_already_zero(ohlcv_factory):
    df = ohlcv_factory([100, 96, 100, 101])
    res = apply_stop_loss(with_signal(df, [1, 0, 1, 1]), 0.03)
    assert res.data["signal"].tolist() == [1, 0, 1, 1]
    assert res.data["stop_blocked"].sum() == 0


def test_normal_exit_without_stop(ohlcv_factory):
    df = ohlcv_factory([100, 101, 102, 103])
    res = apply_stop_loss(with_signal(df, [1, 1, 0, 0]), 0.03)
    assert res.n_stops == 0
    assert res.data["signal"].tolist() == [1, 1, 0, 0]


def test_stop_exactly_at_level_triggers(ohlcv_factory):
    df = ohlcv_factory([100, 97])
    res = apply_stop_loss(with_signal(df, [1, 1]), 0.03)
    assert res.n_stops == 1


def test_stop_on_last_bar_has_no_flat_date(ohlcv_factory):
    df = ohlcv_factory([100, 99, 95])
    ev = apply_stop_loss(with_signal(df, [1, 1, 1]), 0.03).events.iloc[0]
    assert ev["flat_position_date"] is None or pd.isna(ev["flat_position_date"])


def test_entry_bar_is_not_checked(ohlcv_factory):
    """O preço de entrada é o próprio fechamento: a barra de entrada nunca dispara stop."""
    df = ohlcv_factory([100, 50, 51])
    res = apply_stop_loss(with_signal(df, [0, 1, 1]), 0.03)
    assert res.n_stops == 0
    assert res.events.empty


def test_input_not_mutated(drop_case):
    original = drop_case.copy()
    apply_stop_loss(drop_case, 0.03)
    pd.testing.assert_frame_equal(drop_case, original)


@pytest.mark.parametrize("pct", [0, 1, -0.1, 1.5])
def test_invalid_stop_pct(drop_case, pct):
    with pytest.raises(ValueError):
        apply_stop_loss(drop_case, pct)


def test_empty_events_has_expected_columns(ohlcv_factory):
    res = apply_stop_loss(with_signal(ohlcv_factory([100, 101]), [1, 1]), 0.05)
    assert "execution_date" in res.events.columns
    assert "flat_position_date" in res.events.columns

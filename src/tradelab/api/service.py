"""Camada de serviço: transforma requisições em chamadas da biblioteca.

Não depende do FastAPI, então pode ser testada (e reaproveitada) sozinha.
Toda a lógica quantitativa continua no motor; aqui só há orquestração e
conversão para JSON (datas em ISO e NaN -> null).
"""

from __future__ import annotations

import math
from io import StringIO

import pandas as pd

from tradelab.analytics import Experiment, compare_experiments, compute_metrics
from tradelab.analytics.metrics import drawdown_series
from tradelab.api.schemas import (
    MAX_CSV_ROWS,
    MIN_CSV_ROWS,
    BacktestRequest,
    CompareRequest,
    DataParams,
)
from tradelab.backtesting import run_backtest
from tradelab.data import DataValidationError, generate_synthetic_ohlcv, validate_ohlcv
from tradelab.risk import apply_stop_loss
from tradelab.strategies import BuyAndHold, SMACrossover


def _clean(value):
    """Converte valores numpy/pandas para tipos JSON (NaN/inf viram None)."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _series(s: pd.Series, digits: int = 6) -> list:
    return [None if pd.isna(v) else round(float(v), digits) for v in s]


def _dates(index: pd.Index) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in index]


def load_request_data(params: DataParams, long_window: int) -> pd.DataFrame:
    """Dados do backtest: CSV enviado pelo usuário ou série sintética."""
    if params.csv is None:
        return generate_synthetic_ohlcv(params.scenario, n_periods=params.periods, seed=params.seed)

    try:
        raw = pd.read_csv(StringIO(params.csv))
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataValidationError(f"Não foi possível ler o CSV: {exc}") from exc

    n = len(raw)
    if n < MIN_CSV_ROWS or n > MAX_CSV_ROWS:
        raise DataValidationError(f"O CSV precisa ter entre {MIN_CSV_ROWS} e {MAX_CSV_ROWS} linhas (recebido: {n}).")
    data = validate_ohlcv(raw)
    if len(data) <= long_window:
        raise DataValidationError(
            f"O CSV tem {len(data)} linhas, menos do que a média longa ({long_window}) precisa."
        )
    return data


def run_backtest_payload(req: BacktestRequest) -> dict:
    data = load_request_data(req.data, req.sma.long_window)
    sma = SMACrossover(req.sma.short_window, req.sma.long_window)
    signals = sma.generate_signals(data)
    kwargs = req.costs.model_dump()

    label = f"SMA {sma.short_window}/{sma.long_window}"
    runs: dict[str, tuple[pd.DataFrame, int]] = {}
    events = pd.DataFrame()

    if req.stop_pct is not None:
        stop = apply_stop_loss(signals, req.stop_pct)
        events = stop.events
        main_name = f"{label} + Stop {req.stop_pct:.1%}"
        runs[main_name] = (run_backtest(stop.data, **kwargs).frame, stop.n_stops)
    else:
        main_name = label
    runs[label] = (run_backtest(signals, **kwargs).frame, 0)
    runs["Buy and Hold"] = (run_backtest(BuyAndHold().generate_signals(data), **kwargs).frame, 0)

    main_frame = runs[main_name][0]
    change = main_frame["position"].diff().shift(-1)   # mudança em t+1 => execução no fechamento de t
    stop_dates = set(events["execution_date"]) if not events.empty else set()
    buys = main_frame.index[change == 1]
    sells = [d for d in main_frame.index[change == -1] if d not in stop_dates]

    strategies = []
    for name, (frame, n_stops) in runs.items():
        metrics = compute_metrics(frame)
        metrics["n_stops"] = n_stops
        strategies.append({
            "name": name,
            "metrics": {k: _clean(v) for k, v in metrics.items()},
            "equity": _series(frame["equity"], 2),
            "drawdown": _series(drawdown_series(frame["equity"])),
        })

    return {
        "main": main_name,
        "dates": _dates(data.index),
        "price": {
            "close": _series(signals["Close"], 4),
            "sma_short": _series(signals["sma_short"], 4),
            "sma_long": _series(signals["sma_long"], 4),
        },
        "markers": {
            "buys": {"dates": _dates(buys), "prices": _series(main_frame.loc[buys, "Close"], 4)},
            "sells": {"dates": _dates(pd.Index(sells)), "prices": _series(main_frame.loc[sells, "Close"], 4)},
        },
        "strategies": strategies,
        "stop_events": [{k: _clean(v) for k, v in row.items()} for row in events.to_dict("records")],
    }


def run_compare_payload(req: CompareRequest) -> dict:
    sma = SMACrossover(req.sma.short_window, req.sma.long_window)
    label = f"SMA {sma.short_window}/{sma.long_window}"
    experiments = [Experiment(label, sma)]
    experiments += [Experiment(f"SMA + Stop {s:.0%}", sma, stop_pct=s) for s in sorted(set(req.stops))]
    experiments.append(Experiment("Buy and Hold", BuyAndHold()))

    raw = compare_experiments(experiments, seeds=list(range(1, req.n_seeds + 1)),
                              n_periods=req.periods, **req.costs.model_dump())
    summary = (raw.drop(columns="seed")
                  .groupby(["scenario", "experiment"], sort=False)
                  .mean(numeric_only=True)
                  .reset_index())

    def records(df: pd.DataFrame) -> list[dict]:
        return [{k: _clean(v) for k, v in row.items()} for row in df.to_dict("records")]

    return {
        "experiments": [e.name for e in experiments],
        "scenarios": ["bull", "bear", "sideways"],
        "n_seeds": req.n_seeds,
        "summary": records(summary),
        "runs": records(raw),
    }

"""Comparação de estratégias e cenários.

Um "experimento" = estratégia + (opcional) Stop-Loss, executado sobre um conjunto
de dados. A função compare_experiments roda vários experimentos em vários
cenários e devolve uma tabela de métricas pronta para relatório.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tradelab.analytics.metrics import compute_metrics
from tradelab.backtesting.engine import run_backtest
from tradelab.data.market_data import generate_synthetic_ohlcv
from tradelab.risk.stop_loss import apply_stop_loss
from tradelab.strategies.base import Strategy


@dataclass(frozen=True)
class Experiment:
    name: str
    strategy: Strategy
    stop_pct: float | None = None


def run_experiment(
    experiment: Experiment,
    data: pd.DataFrame,
    initial_capital: float = 100_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict:
    """Executa um experimento e devolve métricas + quantidade de stops."""
    signals = experiment.strategy.generate_signals(data)
    n_stops = 0
    if experiment.stop_pct is not None:
        stop_result = apply_stop_loss(signals, experiment.stop_pct)
        signals = stop_result.data
        n_stops = stop_result.n_stops

    result = run_backtest(
        signals,
        initial_capital=initial_capital,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
    )
    metrics = compute_metrics(result.frame)
    metrics["n_stops"] = n_stops
    return metrics


def compare_experiments(
    experiments: list[Experiment],
    scenarios: list[str] = ("bull", "bear", "sideways"),
    seeds: list[int] = (42,),
    n_periods: int = 504,
    initial_capital: float = 100_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> pd.DataFrame:
    """Roda todos os experimentos em todos os cenários e seeds."""
    rows = []
    for scenario in scenarios:
        for seed in seeds:
            data = generate_synthetic_ohlcv(scenario=scenario, n_periods=n_periods, seed=seed)
            for exp in experiments:
                metrics = run_experiment(exp, data, initial_capital, cost_bps, slippage_bps)
                rows.append({"scenario": scenario, "seed": seed, "experiment": exp.name, **metrics})
    return pd.DataFrame(rows)


def summarize_by_scenario(results: pd.DataFrame) -> pd.DataFrame:
    """Média das métricas por cenário e experimento (útil com várias seeds)."""
    numeric = results.drop(columns=["seed"]).groupby(["scenario", "experiment"]).mean(numeric_only=True)
    return numeric.round(4)

"""Motor de backtesting vetorizado.

Convenção temporal (central para evitar look-ahead bias):

    - O sinal da barra t é calculado com informações disponíveis até o FECHAMENTO de t.
    - A execução presumida acontece no fechamento de t.
    - Portanto, a exposição só existe a partir do retorno de t -> t+1:

          position_{t+1} = signal_t        (position = signal.shift(1))

    - O retorno de mercado da barra t é Close_t / Close_{t-1} - 1.
    - O custo de uma troca de posição é cobrado na mesma barra em que a nova
      posição começa a render (a barra seguinte à execução), descontado do
      retorno daquela barra. Assim, custo e exposição ficam alinhados.

Colunas produzidas:
    market_return, position, gross_return, turnover, cost, net_return, equity
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tradelab.strategies.base import SIGNAL_COLUMN


class BacktestError(ValueError):
    """Erro de entrada inválida no motor de backtesting."""


@dataclass
class BacktestResult:
    """Resultado de uma execução de backtest."""

    frame: pd.DataFrame
    initial_capital: float
    cost_bps: float
    slippage_bps: float
    metadata: dict = field(default_factory=dict)

    @property
    def equity(self) -> pd.Series:
        return self.frame["equity"]

    @property
    def returns(self) -> pd.Series:
        return self.frame["net_return"]

    @property
    def final_equity(self) -> float:
        return float(self.frame["equity"].iloc[-1])

    @property
    def n_trades(self) -> int:
        """Quantidade de mudanças de posição (entradas + saídas)."""
        return int((self.frame["turnover"] > 0).sum())


def _validate_inputs(data: pd.DataFrame, signal_column: str, price_column: str) -> None:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise BacktestError("Os dados precisam ser um DataFrame não vazio.")
    for col in (signal_column, price_column):
        if col not in data.columns:
            raise BacktestError(f"Coluna obrigatória ausente: '{col}'.")
    if len(data) < 2:
        raise BacktestError("São necessárias pelo menos 2 observações para calcular retornos.")
    if not data.index.is_monotonic_increasing or data.index.has_duplicates:
        raise BacktestError("O índice precisa estar em ordem crescente e sem duplicidades.")

    signal = data[signal_column]
    if signal.isna().any():
        raise BacktestError("A coluna de sinal contém valores ausentes.")
    if not signal.isin([0, 1]).all():
        raise BacktestError("O sinal precisa conter apenas 0 (fora) ou 1 (comprado).")

    price = data[price_column]
    if price.isna().any() or (price <= 0).any():
        raise BacktestError("Os preços precisam ser positivos e sem valores ausentes.")


def run_backtest(
    data: pd.DataFrame,
    initial_capital: float = 100_000.0,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    signal_column: str = SIGNAL_COLUMN,
    price_column: str = "Close",
) -> BacktestResult:
    """Simula uma estratégia long/flat a partir de uma coluna de sinais.

    Args:
        data: DataFrame com preços e a coluna de sinal (0/1).
        initial_capital: patrimônio inicial.
        cost_bps: custo de transação por unidade de turnover, em pontos-base (1 bp = 0,01%).
        slippage_bps: deslizamento de preço por unidade de turnover, em pontos-base.
    """
    _validate_inputs(data, signal_column, price_column)
    if initial_capital <= 0:
        raise BacktestError("initial_capital precisa ser positivo.")
    if cost_bps < 0 or slippage_bps < 0:
        raise BacktestError("Custos e slippage não podem ser negativos.")

    out = data.copy()
    price = out[price_column].astype(float)
    signal = out[signal_column].astype(int)

    out["market_return"] = price.pct_change().fillna(0.0)

    # Sinal de t só vale em t+1: evita look-ahead bias.
    out["position"] = signal.shift(1, fill_value=0).astype(int)

    out["gross_return"] = out["position"] * out["market_return"]

    # Turnover: quanto a posição mudou. Entrar ou sair = 1.
    out["turnover"] = out["position"].diff().abs().fillna(out["position"].abs())

    cost_rate = (cost_bps + slippage_bps) / 10_000
    out["cost"] = out["turnover"] * cost_rate
    out["net_return"] = out["gross_return"] - out["cost"]

    out["equity"] = initial_capital * (1 + out["net_return"]).cumprod()

    if not np.isfinite(out["equity"]).all():
        raise BacktestError("Patrimônio resultou em valores não finitos.")

    return BacktestResult(
        frame=out,
        initial_capital=initial_capital,
        cost_bps=cost_bps,
        slippage_bps=slippage_bps,
    )

"""Interface comum para estratégias.

Toda estratégia recebe dados OHLCV e devolve uma cópia com a coluna 'signal':
    1 -> deseja estar comprado
    0 -> deseja estar fora do mercado

A estratégia NÃO decide quando a posição é aplicada. Quem faz isso é o motor
de backtesting, que desloca o sinal em um período para evitar look-ahead bias.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

SIGNAL_COLUMN = "signal"


class Strategy(ABC):
    """Classe base para todas as estratégias do TradeLab."""

    name: str = "strategy"

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Devolve uma cópia de `data` com a coluna 'signal' (0 ou 1)."""

    def params(self) -> dict:
        """Parâmetros da estratégia, úteis para registrar experimentos."""
        return {}

    def __repr__(self) -> str:
        params = ", ".join(f"{k}={v}" for k, v in self.params().items())
        return f"{self.__class__.__name__}({params})"

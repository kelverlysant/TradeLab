"""Estratégia de cruzamento de médias móveis simples (SMA Crossover).

Regra:
    signal_t = 1  se SMA_curta_t > SMA_longa_t
    signal_t = 0  caso contrário (inclusive enquanto a média longa ainda não existe)
"""

from __future__ import annotations

import pandas as pd

from tradelab.strategies.base import SIGNAL_COLUMN, Strategy


class SMACrossover(Strategy):
    name = "sma_crossover"

    def __init__(self, short_window: int = 10, long_window: int = 30, price_column: str = "Close"):
        if short_window < 1 or long_window < 1:
            raise ValueError("As janelas precisam ser inteiros positivos.")
        if short_window >= long_window:
            raise ValueError("A janela curta precisa ser menor que a janela longa.")
        self.short_window = short_window
        self.long_window = long_window
        self.price_column = price_column

    def params(self) -> dict:
        return {"short_window": self.short_window, "long_window": self.long_window}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        if self.price_column not in data.columns:
            raise KeyError(f"Coluna de preço '{self.price_column}' não encontrada.")

        out = data.copy()
        price = out[self.price_column]
        out["sma_short"] = price.rolling(window=self.short_window, min_periods=self.short_window).mean()
        out["sma_long"] = price.rolling(window=self.long_window, min_periods=self.long_window).mean()

        # Comparações com NaN resultam em False -> sinal 0 durante o aquecimento.
        out[SIGNAL_COLUMN] = (out["sma_short"] > out["sma_long"]).astype(int)
        return out

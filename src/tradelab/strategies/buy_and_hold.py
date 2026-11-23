"""Buy and Hold: compra e mantém exposição durante toda a simulação.

Serve como referência (benchmark) para saber se uma estratégia mais elaborada
realmente agrega valor.
"""

from __future__ import annotations

import pandas as pd

from tradelab.strategies.base import SIGNAL_COLUMN, Strategy


class BuyAndHold(Strategy):
    name = "buy_and_hold"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        out = data.copy()
        out[SIGNAL_COLUMN] = 1
        return out

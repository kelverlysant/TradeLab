"""Visualização (requer o extra de interface: pip install -e ".[ui]")."""

from tradelab.visualization.charts import (
    distribution_figure,
    drawdown_figure,
    equity_figure,
    price_and_signals_figure,
    scenario_bar_figure,
)

__all__ = [
    "distribution_figure",
    "drawdown_figure",
    "equity_figure",
    "price_and_signals_figure",
    "scenario_bar_figure",
]

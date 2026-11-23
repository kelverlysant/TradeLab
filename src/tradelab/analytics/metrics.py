"""Métricas de desempenho.

O primeiro registro de uma série de retornos não tem preço anterior, então
não é tratado como período efetivo de negociação: as métricas usam returns.iloc[1:].
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _effective_returns(returns: pd.Series) -> pd.Series:
    if len(returns) < 2:
        raise ValueError("São necessários pelo menos 2 registros para calcular métricas.")
    return returns.iloc[1:].astype(float)


def total_return(equity: pd.Series) -> float:
    """Variação total do patrimônio no período."""
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def annualized_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Retorno composto anualizado (CAGR) a partir de retornos periódicos."""
    r = _effective_returns(returns)
    growth = float((1 + r).prod())
    if growth <= 0:
        return -1.0
    return growth ** (periods_per_year / len(r)) - 1


def annualized_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Desvio padrão amostral dos retornos, anualizado."""
    r = _effective_returns(returns)
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Sharpe anualizado: média do retorno excedente / desvio padrão.

    Devolve NaN quando a volatilidade é zero (ex.: estratégia sempre fora).
    """
    r = _effective_returns(returns)
    excess = r - risk_free_rate / periods_per_year
    std = excess.std(ddof=1)
    if len(excess) < 2 or not np.isfinite(std) or std == 0:
        return float("nan")
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Queda percentual do patrimônio em relação ao pico anterior."""
    running_max = equity.cummax()
    return equity / running_max - 1


def max_drawdown(equity: pd.Series) -> float:
    """Maior queda desde um pico (valor negativo ou zero)."""
    return float(drawdown_series(equity).min())


def exposure(position: pd.Series) -> float:
    """Fração dos períodos efetivos em que a estratégia estava exposta."""
    p = _effective_returns(position)
    return float((p != 0).mean())


def compute_metrics(
    frame: pd.DataFrame,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> dict[str, float]:
    """Calcula todas as métricas a partir do frame de um BacktestResult."""
    returns = frame["net_return"]
    equity = frame["equity"]
    return {
        "total_return": total_return(equity),
        "annualized_return": annualized_return(returns, periods_per_year),
        "volatility": annualized_volatility(returns, periods_per_year),
        "sharpe": sharpe_ratio(returns, risk_free_rate, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "exposure": exposure(frame["position"]),
        "n_trades": int((frame["turnover"] > 0).sum()),
        "final_equity": float(equity.iloc[-1]),
    }

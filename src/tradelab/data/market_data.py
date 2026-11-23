"""Carregamento, validação e geração de dados de mercado no formato OHLCV.

OHLCV = Open, High, Low, Close, Volume.

Regras de validação:
    - Colunas obrigatórias presentes (nomes normalizados para Open/High/Low/Close/Volume).
    - Índice de datas (DatetimeIndex), em ordem crescente e sem duplicidades.
    - Valores numéricos e sem ausentes.
    - Preços estritamente positivos e volume não negativo.
    - Coerência de máximas e mínimas: High >= max(Open, Close, Low) e Low <= min(Open, Close).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: list[str] = ["Open", "High", "Low", "Close", "Volume"]
PRICE_COLUMNS: list[str] = ["Open", "High", "Low", "Close"]

Scenario = Literal["bull", "bear", "sideways"]

# Drift anual (log) por cenário. Sideways tem drift esperado igual a zero.
SCENARIO_DRIFT: dict[str, float] = {
    "bull": 0.15,
    "bear": -0.15,
    "sideways": 0.0,
}


class DataValidationError(ValueError):
    """Erro levantado quando os dados de mercado não passam nas validações."""


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de colunas: ' close ' -> 'Close', 'VOLUME' -> 'Volume'."""
    renamed = {col: str(col).strip().capitalize() for col in df.columns}
    return df.rename(columns=renamed)


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Valida um DataFrame OHLCV e devolve uma cópia normalizada.

    Raises:
        DataValidationError: se qualquer regra for violada.
    """
    if not isinstance(df, pd.DataFrame):
        raise DataValidationError("Os dados precisam ser um pandas.DataFrame.")
    if df.empty:
        raise DataValidationError("O DataFrame está vazio.")

    data = _normalize_columns(df.copy())

    # Se a data vier como coluna, transforma em índice.
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        if data["Date"].isna().any():
            raise DataValidationError("Existem datas inválidas na coluna 'Date'.")
        data = data.set_index("Date")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise DataValidationError("O índice precisa ser de datas (DatetimeIndex) ou existir uma coluna 'Date'.")

    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise DataValidationError(f"Colunas obrigatórias ausentes: {missing}")

    data = data[REQUIRED_COLUMNS]

    if data.index.has_duplicates:
        dups = data.index[data.index.duplicated()].unique().tolist()
        raise DataValidationError(f"Datas duplicadas encontradas: {dups[:5]}")

    if not data.index.is_monotonic_increasing:
        raise DataValidationError("As datas precisam estar em ordem crescente.")

    for col in REQUIRED_COLUMNS:
        converted = pd.to_numeric(data[col], errors="coerce")
        if converted.isna().any():
            raise DataValidationError(f"A coluna '{col}' contém valores não numéricos ou ausentes.")
        data[col] = converted.astype(float)

    if (data[PRICE_COLUMNS] <= 0).any().any():
        raise DataValidationError("Todos os preços precisam ser positivos.")

    if (data["Volume"] < 0).any():
        raise DataValidationError("O volume não pode ser negativo.")

    max_oc = data[["Open", "Close"]].max(axis=1)
    min_oc = data[["Open", "Close"]].min(axis=1)
    if (data["High"] < max_oc).any() or (data["High"] < data["Low"]).any():
        raise DataValidationError("High precisa ser maior ou igual a Open, Close e Low.")
    if (data["Low"] > min_oc).any():
        raise DataValidationError("Low precisa ser menor ou igual a Open e Close.")

    data.index.name = "Date"
    return data


def load_csv(path: str | Path) -> pd.DataFrame:
    """Lê um CSV OHLCV (com coluna Date) e devolve os dados já validados."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    raw = pd.read_csv(path)
    return validate_ohlcv(raw)


def generate_synthetic_ohlcv(
    scenario: Scenario = "sideways",
    n_periods: int = 504,
    seed: int | None = 42,
    start_price: float = 100.0,
    annual_volatility: float = 0.20,
    start_date: str = "2020-01-01",
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Gera uma série OHLCV sintética com Movimento Browniano Geométrico.

    Os log-retornos diários seguem N(mu/ppy, sigma/sqrt(ppy)), em que mu é o
    drift do cenário. A mesma seed produz sempre a mesma trajetória.

    Importante: dados sintéticos servem para testar o sistema em condições
    controladas. Eles NÃO comprovam que uma estratégia funciona no mercado real.
    """
    if scenario not in SCENARIO_DRIFT:
        raise ValueError(f"Cenário inválido: {scenario!r}. Use um de {list(SCENARIO_DRIFT)}.")
    if n_periods < 2:
        raise ValueError("n_periods precisa ser pelo menos 2.")
    if start_price <= 0:
        raise ValueError("start_price precisa ser positivo.")

    rng = np.random.default_rng(seed)
    mu = SCENARIO_DRIFT[scenario] / periods_per_year
    sigma = annual_volatility / np.sqrt(periods_per_year)

    log_returns = rng.normal(loc=mu, scale=sigma, size=n_periods)
    log_returns[0] = 0.0
    close = start_price * np.exp(np.cumsum(log_returns))

    prev_close = np.concatenate([[start_price], close[:-1]])
    open_ = prev_close * (1 + rng.normal(0, sigma / 4, size=n_periods))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, sigma / 2, size=n_periods)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, sigma / 2, size=n_periods)))
    volume = rng.lognormal(mean=13, sigma=0.4, size=n_periods).round()

    index = pd.bdate_range(start=start_date, periods=n_periods, name="Date")
    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=index,
    )
    return validate_ohlcv(df)

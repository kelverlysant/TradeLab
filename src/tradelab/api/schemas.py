"""Modelos de entrada da API (Pydantic).

Os limites (ge/le) protegem o servidor: nenhuma requisição consegue pedir
uma simulação gigante ou parâmetros sem sentido.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Scenario = Literal["bull", "bear", "sideways"]


class DataParams(BaseModel):
    scenario: Scenario = "bull"
    seed: int = Field(42, ge=0, le=1_000_000)
    periods: int = Field(504, ge=60, le=2520, description="Quantidade de pregões")


class SMAParams(BaseModel):
    short_window: int = Field(10, ge=2, le=200)
    long_window: int = Field(30, ge=3, le=400)

    @model_validator(mode="after")
    def check_windows(self):
        if self.short_window >= self.long_window:
            raise ValueError("short_window precisa ser menor que long_window")
        return self


class CostParams(BaseModel):
    initial_capital: float = Field(100_000.0, gt=0, le=1e12)
    cost_bps: float = Field(0.0, ge=0, le=500)
    slippage_bps: float = Field(0.0, ge=0, le=500)


class BacktestRequest(BaseModel):
    data: DataParams = DataParams()
    sma: SMAParams = SMAParams()
    costs: CostParams = CostParams()
    stop_pct: float | None = Field(0.03, gt=0, lt=1, description="Ex.: 0.03 = 3%. null desliga o Stop")


class CompareRequest(BaseModel):
    sma: SMAParams = SMAParams()
    costs: CostParams = CostParams()
    stops: list[float] = Field(default_factory=lambda: [0.03, 0.05], max_length=5)
    n_seeds: int = Field(10, ge=1, le=30)
    periods: int = Field(504, ge=60, le=1260)

    @model_validator(mode="after")
    def check_stops(self):
        if any(not 0 < s < 1 for s in self.stops):
            raise ValueError("cada stop precisa estar entre 0 e 1")
        return self

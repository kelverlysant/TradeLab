"""API HTTP do TradeLab (FastAPI).

Rodar localmente (na raiz do projeto):
    python -m uvicorn main:app --reload

Documentação interativa: http://localhost:8000/docs
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tradelab import __version__
from tradelab.api.schemas import BacktestRequest, CompareRequest
from tradelab.api.service import run_backtest_payload, run_compare_payload
from tradelab.backtesting import BacktestError
from tradelab.data import DataValidationError

PUBLIC_DIR = Path(__file__).resolve().parents[3] / "public"

app = FastAPI(
    title="TradeLab API",
    version=__version__,
    description="Laboratório quantitativo: backtests de estratégias com Stop-Loss, custos e métricas.",
)


@app.exception_handler(DataValidationError)
@app.exception_handler(BacktestError)
@app.exception_handler(ValueError)
async def domain_error_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


if not os.environ.get("VERCEL"):
    # Na Vercel, a pasta public/ é servida pelo CDN da própria plataforma
    # (index.html em "/" e o Plotly em /vendor). Localmente, a API serve esses arquivos.
    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(PUBLIC_DIR / "index.html")

    app.mount("/vendor", StaticFiles(directory=PUBLIC_DIR / "vendor"), name="vendor")


@app.get("/api/health", tags=["status"])
def health():
    return {"status": "ok", "version": __version__}


@app.get("/api/strategies", tags=["estratégias"])
def strategies():
    return [
        {"name": "sma_crossover", "params": {"short_window": "int", "long_window": "int"},
         "rule": "1 quando SMA curta > SMA longa, senão 0"},
        {"name": "buy_and_hold", "params": {}, "rule": "sempre 1 (benchmark)"},
    ]


@app.post("/api/backtest", tags=["backtests"])
def backtest(req: BacktestRequest):
    """Executa SMA (com Stop opcional), SMA pura e Buy and Hold sobre dados sintéticos."""
    return run_backtest_payload(req)


@app.post("/api/compare", tags=["backtests"])
def compare(req: CompareRequest):
    """Compara experimentos nos cenários Bull, Bear e Sideways com várias seeds."""
    return run_compare_payload(req)

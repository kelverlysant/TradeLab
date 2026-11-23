"""Testes da API HTTP (FastAPI TestClient)."""

import io

import pandas as pd
import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from tradelab.analytics import compute_metrics  # noqa: E402
from tradelab.backtesting import run_backtest  # noqa: E402
from tradelab.data import generate_synthetic_ohlcv, validate_ohlcv  # noqa: E402
from tradelab.risk import apply_stop_loss  # noqa: E402
from tradelab.strategies import SMACrossover  # noqa: E402

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_home_serves_frontend():
    res = client.get("/")
    assert res.status_code == 200
    assert "TradeLab" in res.text


def test_openapi_docs_available():
    assert client.get("/docs").status_code == 200
    assert "/api/backtest" in client.get("/openapi.json").json()["paths"]


def test_strategies_list():
    names = [s["name"] for s in client.get("/api/strategies").json()]
    assert names == ["sma_crossover", "buy_and_hold"]


def test_backtest_default_shape():
    res = client.post("/api/backtest", json={})
    assert res.status_code == 200
    d = res.json()
    n = len(d["dates"])
    assert n == 504
    assert len(d["price"]["close"]) == n
    assert [s["name"] for s in d["strategies"]] == ["SMA 10/30 + Stop 3.0%", "SMA 10/30", "Buy and Hold"]
    for s in d["strategies"]:
        assert len(s["equity"]) == n and len(s["drawdown"]) == n
    assert d["main"] == "SMA 10/30 + Stop 3.0%"


def test_backtest_metrics_match_library():
    """A API não pode recalcular nada diferente da biblioteca."""
    payload = {"data": {"scenario": "bear", "seed": 7}, "stop_pct": 0.05, "costs": {"cost_bps": 5}}
    d = client.post("/api/backtest", json=payload).json()

    data = generate_synthetic_ohlcv("bear", seed=7)
    stop = apply_stop_loss(SMACrossover(10, 30).generate_signals(data), 0.05)
    expected = compute_metrics(run_backtest(stop.data, cost_bps=5).frame)

    got = d["strategies"][0]["metrics"]
    assert got["total_return"] == pytest.approx(expected["total_return"])
    assert got["max_drawdown"] == pytest.approx(expected["max_drawdown"])
    assert got["n_stops"] == stop.n_stops == len(d["stop_events"])


def test_backtest_without_stop():
    d = client.post("/api/backtest", json={"stop_pct": None}).json()
    assert d["main"] == "SMA 10/30"
    assert d["stop_events"] == []
    assert len(d["strategies"]) == 2


def test_stop_events_are_json_friendly():
    d = client.post("/api/backtest", json={"data": {"scenario": "bear", "seed": 42}}).json()
    ev = d["stop_events"][0]
    assert isinstance(ev["execution_date"], str)
    assert ev["observed_loss"] <= -ev["stop_pct"] + 1e-12


@pytest.mark.parametrize("payload", [
    {"sma": {"short_window": 30, "long_window": 10}},
    {"stop_pct": 1.5},
    {"data": {"scenario": "crash"}},
    {"data": {"periods": 10}},
    {"costs": {"cost_bps": -1}},
])
def test_backtest_invalid_input_returns_422(payload):
    assert client.post("/api/backtest", json=payload).status_code == 422


def test_compare_shape():
    res = client.post("/api/compare", json={"n_seeds": 2, "stops": [0.03]})
    assert res.status_code == 200
    d = res.json()
    assert d["experiments"] == ["SMA 10/30", "SMA + Stop 3%", "Buy and Hold"]
    assert len(d["summary"]) == 3 * 3
    assert len(d["runs"]) == 3 * 3 * 2


def test_compare_limits_seeds():
    assert client.post("/api/compare", json={"n_seeds": 500}).status_code == 422


# ---------------------------------------------------------------- CSV próprio

def _csv(n=300, scenario="bull", seed=3):
    return generate_synthetic_ohlcv(scenario, n_periods=n, seed=seed).to_csv()


def test_backtest_with_csv_matches_library():
    text = _csv()
    res = client.post("/api/backtest", json={"data": {"csv": text}, "stop_pct": 0.05})
    assert res.status_code == 200
    d = res.json()
    assert len(d["dates"]) == 300

    data = validate_ohlcv(pd.read_csv(io.StringIO(text)))
    stop = apply_stop_loss(SMACrossover(10, 30).generate_signals(data), 0.05)
    expected = compute_metrics(run_backtest(stop.data).frame)
    got = d["strategies"][0]["metrics"]
    assert got["total_return"] == pytest.approx(expected["total_return"])
    assert got["sharpe"] == pytest.approx(expected["sharpe"])


def test_csv_overrides_synthetic_params():
    text = _csv(n=120)
    d = client.post("/api/backtest", json={"data": {"csv": text, "scenario": "bear", "periods": 900}}).json()
    assert len(d["dates"]) == 120
    assert d["dates"][0] == "2020-01-01"


def test_csv_lowercase_columns_accepted():
    text = _csv(n=100).replace("Date,Open,High,Low,Close,Volume", "date,open,high,low,close,volume")
    assert client.post("/api/backtest", json={"data": {"csv": text}}).status_code == 200


@pytest.mark.parametrize("text, fragment", [
    (_csv(n=100).replace(",Volume", ",Vol"), "Colunas obrigatórias ausentes"),
    (_csv(n=30), "entre 60 e 2520 linhas"),
    (_csv(n=2600), "entre 60 e 2520 linhas"),
    ("", "Não foi possível ler o CSV"),
    (_csv(n=100).replace("2020-01-02", "ontem"), "datas inválidas"),
])
def test_invalid_csv_returns_422(text, fragment):
    res = client.post("/api/backtest", json={"data": {"csv": text}})
    assert res.status_code == 422
    assert fragment in str(res.json()["detail"])


def test_csv_shorter_than_long_window():
    res = client.post("/api/backtest", json={"data": {"csv": _csv(n=80)}, "sma": {"short_window": 20, "long_window": 100}})
    assert res.status_code == 422
    assert "média longa" in res.json()["detail"]


def test_csv_too_large_rejected():
    big = "x" * 1_000_001
    assert client.post("/api/backtest", json={"data": {"csv": big}}).status_code == 422

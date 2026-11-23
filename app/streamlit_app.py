"""Dashboard do TradeLab (Streamlit).

Executar na raiz do projeto, com o ambiente virtual ativo:
    streamlit run app/streamlit_app.py

A interface só chama a biblioteca `tradelab`. Toda a lógica quantitativa
continua no motor, coberta pelos testes.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tradelab.analytics import Experiment, compare_experiments, compute_metrics
from tradelab.backtesting import run_backtest
from tradelab.data import DataValidationError, generate_synthetic_ohlcv, validate_ohlcv
from tradelab.risk import apply_stop_loss
from tradelab.strategies import BuyAndHold, SMACrossover
from tradelab.visualization import (
    distribution_figure,
    drawdown_figure,
    equity_figure,
    price_and_signals_figure,
    scenario_bar_figure,
)

st.set_page_config(page_title="TradeLab", page_icon="📈", layout="wide")

METRIC_LABELS = {
    "total_return": "Retorno total",
    "annualized_return": "Retorno anualizado",
    "volatility": "Volatilidade",
    "sharpe": "Sharpe",
    "max_drawdown": "Max Drawdown",
    "exposure": "Exposição",
    "n_trades": "Trades",
    "n_stops": "Stops",
    "final_equity": "Patrimônio final",
}
PERCENT_METRICS = {"total_return", "annualized_return", "volatility", "max_drawdown", "exposure"}


# ---------------------------------------------------------------- helpers
def fmt(metric: str, value: float) -> str:
    if pd.isna(value):
        return "—"
    if metric in PERCENT_METRICS:
        return f"{value:.2%}"
    if metric == "final_equity":
        return f"{value:,.2f}"
    if metric in {"n_trades", "n_stops"}:
        return f"{value:.0f}"
    return f"{value:.2f}"


def metrics_table(rows: dict[str, dict]) -> pd.DataFrame:
    table = pd.DataFrame(rows).T
    table = table[[c for c in METRIC_LABELS if c in table.columns]]
    shown = table.apply(lambda col: col.map(lambda v: fmt(col.name, v)))
    return shown.rename(columns=METRIC_LABELS)


@st.cache_data(show_spinner=False)
def load_synthetic(scenario: str, seed: int, periods: int) -> pd.DataFrame:
    return generate_synthetic_ohlcv(scenario=scenario, n_periods=periods, seed=seed)


@st.cache_data(show_spinner=False)
def load_uploaded(file_bytes: bytes) -> pd.DataFrame:
    from io import BytesIO
    return validate_ohlcv(pd.read_csv(BytesIO(file_bytes)))


@st.cache_data(show_spinner="Rodando experimentos...")
def run_comparison(short: int, long_: int, stops: tuple[float, ...], seeds: tuple[int, ...],
                   periods: int, cost_bps: float, slippage_bps: float) -> pd.DataFrame:
    sma = SMACrossover(short, long_)
    experiments = [Experiment(f"SMA {short}/{long_}", sma)]
    experiments += [Experiment(f"SMA + Stop {s:.0%}", sma, stop_pct=s) for s in stops]
    experiments.append(Experiment("Buy and Hold", BuyAndHold()))
    return compare_experiments(experiments, seeds=list(seeds), n_periods=periods,
                               cost_bps=cost_bps, slippage_bps=slippage_bps)


# ---------------------------------------------------------------- sidebar
st.sidebar.title("📈 TradeLab")
st.sidebar.caption("Construir. Simular. Medir. Avaliar.")

st.sidebar.subheader("Dados")
source = st.sidebar.radio("Fonte", ["Sintéticos", "CSV próprio"], horizontal=True)
scenario, seed = "sideways", 42
periods = st.sidebar.slider("Períodos (pregões)", 120, 1260, 504, step=21)
if source == "Sintéticos":
    scenario = st.sidebar.selectbox("Cenário", ["bull", "bear", "sideways"], index=0)
    seed = st.sidebar.number_input("Seed", min_value=0, value=42, step=1)
else:
    uploaded = st.sidebar.file_uploader("CSV OHLCV (colunas Date, Open, High, Low, Close, Volume)", type="csv")

st.sidebar.subheader("Estratégia SMA")
c1, c2 = st.sidebar.columns(2)
short = c1.number_input("Curta", min_value=2, value=10, step=1)
long_ = c2.number_input("Longa", min_value=3, value=30, step=1)

st.sidebar.subheader("Risco e custos")
use_stop = st.sidebar.toggle("Usar Stop-Loss", value=True)
stop_pct = st.sidebar.slider("Stop (%)", 1.0, 15.0, 3.0, step=0.5, disabled=not use_stop) / 100
cost_bps = st.sidebar.number_input("Custo (bps)", min_value=0.0, value=0.0, step=1.0)
slippage_bps = st.sidebar.number_input("Slippage (bps)", min_value=0.0, value=0.0, step=1.0)
capital = st.sidebar.number_input("Capital inicial", min_value=1_000.0, value=100_000.0, step=10_000.0)

if short >= long_:
    st.error("A janela curta precisa ser menor que a janela longa.")
    st.stop()

# ---------------------------------------------------------------- dados
try:
    if source == "Sintéticos":
        data = load_synthetic(scenario, int(seed), periods)
        data_label = f"Sintético · {scenario} · seed {seed}"
    else:
        if uploaded is None:
            st.info("Envie um CSV na barra lateral para começar.")
            st.stop()
        data = load_uploaded(uploaded.getvalue())
        data_label = f"CSV · {uploaded.name}"
except DataValidationError as exc:
    st.error(f"Os dados não passaram na validação: {exc}")
    st.stop()

# ---------------------------------------------------------------- backtest
sma = SMACrossover(int(short), int(long_))
signals = sma.generate_signals(data)
events = None
if use_stop:
    stop_result = apply_stop_loss(signals, stop_pct)
    strat_signals, events = stop_result.data, stop_result.events
else:
    strat_signals = signals

kwargs = dict(initial_capital=capital, cost_bps=cost_bps, slippage_bps=slippage_bps)
strategy_name = f"SMA {short}/{long_}" + (f" + Stop {stop_pct:.1%}" if use_stop else "")
results = {strategy_name: run_backtest(strat_signals, **kwargs)}
if use_stop:
    results[f"SMA {short}/{long_}"] = run_backtest(signals, **kwargs)
results["Buy and Hold"] = run_backtest(BuyAndHold().generate_signals(data), **kwargs)

metrics = {}
for name, res in results.items():
    m = compute_metrics(res.frame)
    m["n_stops"] = len(events) if (name == strategy_name and events is not None) else 0
    metrics[name] = m

# ---------------------------------------------------------------- layout
st.title("TradeLab Platform")
st.caption(f"{data_label} · {len(data)} pregões · {data.index[0]:%d/%m/%Y} → {data.index[-1]:%d/%m/%Y}")

tab_bt, tab_cmp, tab_data = st.tabs(["Backtest", "Comparação de cenários", "Dados"])

with tab_bt:
    main, bench = metrics[strategy_name], metrics["Buy and Hold"]
    cols = st.columns(5)
    for col, key in zip(cols, ["total_return", "annualized_return", "sharpe", "max_drawdown", "exposure"]):
        delta = main[key] - bench[key]
        col.metric(METRIC_LABELS[key], fmt(key, main[key]),
                   delta=f"{fmt(key, delta)} vs B&H" if pd.notna(delta) else None,
                   delta_color="off" if key == "exposure" else "normal")

    st.plotly_chart(price_and_signals_figure(results[strategy_name].frame, events), use_container_width=True)

    left, right = st.columns(2)
    equities = {name: res.equity for name, res in results.items()}
    left.plotly_chart(equity_figure(equities), use_container_width=True)
    right.plotly_chart(drawdown_figure(equities), use_container_width=True)

    st.subheader("Métricas")
    st.dataframe(metrics_table(metrics), use_container_width=True)

    if events is not None:
        st.subheader(f"Eventos de Stop ({len(events)})")
        if events.empty:
            st.caption("Nenhum Stop foi acionado neste período.")
        else:
            shown = events.copy()
            for c in ("entry_signal_date", "trigger_date", "execution_date", "flat_position_date"):
                shown[c] = pd.to_datetime(shown[c]).dt.strftime("%d/%m/%Y")
            shown["observed_loss"] = shown["observed_loss"].map("{:.2%}".format)
            shown["stop_pct"] = shown["stop_pct"].map("{:.1%}".format)
            st.dataframe(shown, use_container_width=True, hide_index=True)
            st.caption("Com preços de fechamento, a perda observada pode ser maior que o nível do Stop.")

    st.download_button("Baixar resultado do backtest (CSV)",
                       results[strategy_name].frame.to_csv().encode("utf-8"),
                       file_name="tradelab_backtest.csv", mime="text/csv")

with tab_cmp:
    st.write("Roda SMA, SMA + Stops e Buy and Hold nos cenários Bull, Bear e Sideways, com várias seeds.")
    c1, c2 = st.columns(2)
    n_seeds = c1.slider("Quantidade de seeds", 1, 50, 10)
    stops = c2.multiselect("Níveis de Stop", [0.02, 0.03, 0.05, 0.08, 0.10], default=[0.03, 0.05],
                           format_func=lambda s: f"{s:.0%}")
    raw = run_comparison(int(short), int(long_), tuple(sorted(stops)), tuple(range(1, n_seeds + 1)),
                         periods, cost_bps, slippage_bps)
    summary = raw.drop(columns="seed").groupby(["scenario", "experiment"], sort=False).mean(numeric_only=True)
    summary = summary.reset_index()

    metric = st.selectbox("Métrica", ["total_return", "sharpe", "max_drawdown", "annualized_return", "volatility"],
                          format_func=METRIC_LABELS.get)
    left, right = st.columns(2)
    left.plotly_chart(scenario_bar_figure(summary, metric, f"{METRIC_LABELS[metric]} médio por cenário"),
                      use_container_width=True)
    scen = right.radio("Distribuição no cenário", ["bull", "bear", "sideways"], horizontal=True)
    right.plotly_chart(distribution_figure(raw, metric, scen, f"{METRIC_LABELS[metric]} entre seeds — {scen}"),
                       use_container_width=True)

    st.subheader("Médias por cenário e experimento")
    table = summary.set_index(["scenario", "experiment"])
    st.dataframe(table.apply(lambda col: col.map(lambda v: fmt(col.name, v))).rename(columns=METRIC_LABELS),
                 use_container_width=True)
    st.caption("Resultados em dados sintéticos são observações experimentais, não conclusões estatísticas.")
    st.download_button("Baixar todas as execuções (CSV)", raw.to_csv(index=False).encode("utf-8"),
                       file_name="tradelab_comparacao.csv", mime="text/csv")

with tab_data:
    st.write("Dados validados (OHLCV) usados no backtest.")
    st.dataframe(data, use_container_width=True)

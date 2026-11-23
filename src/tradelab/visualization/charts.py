"""Gráficos do TradeLab (Plotly).

As funções só montam figuras a partir de DataFrames já calculados pelo motor:
nenhuma lógica quantitativa mora aqui. Assim a interface pode mudar sem
risco de alterar posição, retorno ou patrimônio.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from tradelab.analytics.metrics import drawdown_series

# Paleta neutra; cada série mantém a mesma cor em todos os gráficos.
COLORS = {
    "price": "#5B6472",
    "sma_short": "#2F7DE1",
    "sma_long": "#E8A33D",
    "entry": "#2BA36B",
    "exit": "#D9534F",
    "stop": "#8E44AD",
}
SERIES_COLORS = ["#2F7DE1", "#E8A33D", "#2BA36B", "#8E44AD", "#D9534F", "#5B6472"]

_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=10, r=10, t=50, b=10),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0),
)


def price_and_signals_figure(frame: pd.DataFrame, events: pd.DataFrame | None = None) -> go.Figure:
    """Preço, médias móveis, entradas/saídas executadas e gatilhos de Stop.

    As marcações usam a mudança de POSIÇÃO do motor, deslocada para a barra de
    execução (fechamento anterior), para mostrar onde a ordem foi presumida.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame.index, y=frame["Close"], name="Close",
                             line=dict(color=COLORS["price"], width=1.5)))
    for col, label in (("sma_short", "SMA curta"), ("sma_long", "SMA longa")):
        if col in frame.columns:
            fig.add_trace(go.Scatter(x=frame.index, y=frame[col], name=label,
                                     line=dict(color=COLORS[col], width=1.2)))

    if "position" in frame.columns:
        change = frame["position"].diff().shift(-1)  # mudança em t+1 => execução em t
        entries = frame[change == 1]
        exits = frame[change == -1]
        if events is not None and not events.empty:
            exits = exits[~exits.index.isin(events["execution_date"])]
        fig.add_trace(go.Scatter(x=entries.index, y=entries["Close"], mode="markers", name="Compra",
                                 marker=dict(symbol="triangle-up", size=10, color=COLORS["entry"])))
        fig.add_trace(go.Scatter(x=exits.index, y=exits["Close"], mode="markers", name="Venda (sinal)",
                                 marker=dict(symbol="triangle-down", size=10, color=COLORS["exit"])))

    if events is not None and not events.empty:
        fig.add_trace(go.Scatter(
            x=events["execution_date"], y=events["trigger_price"], mode="markers", name="Stop",
            marker=dict(symbol="x", size=11, color=COLORS["stop"]),
            customdata=events[["entry_price", "stop_price", "observed_loss"]].to_numpy(),
            hovertemplate="Stop<br>entrada %{customdata[0]:.2f}<br>nível %{customdata[1]:.2f}"
                          "<br>gatilho %{y:.2f}<br>perda %{customdata[2]:.2%}<extra></extra>",
        ))

    fig.update_layout(title="Preço, médias e execuções", yaxis_title="Preço", **_LAYOUT)
    return fig


def equity_figure(equities: dict[str, pd.Series]) -> go.Figure:
    """Curvas de patrimônio de uma ou mais estratégias."""
    fig = go.Figure()
    for i, (name, equity) in enumerate(equities.items()):
        fig.add_trace(go.Scatter(x=equity.index, y=equity, name=name,
                                 line=dict(color=SERIES_COLORS[i % len(SERIES_COLORS)], width=1.8)))
    fig.update_layout(title="Evolução do patrimônio", yaxis_title="Patrimônio", **_LAYOUT)
    return fig


def drawdown_figure(equities: dict[str, pd.Series]) -> go.Figure:
    """Drawdown (queda desde o pico) de uma ou mais estratégias."""
    fig = go.Figure()
    for i, (name, equity) in enumerate(equities.items()):
        dd = drawdown_series(equity)
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name=name, line=dict(color=SERIES_COLORS[i % len(SERIES_COLORS)], width=1.4)))
    fig.update_layout(title="Drawdown", yaxis_title="Queda desde o pico", yaxis_tickformat=".0%", **_LAYOUT)
    return fig


def scenario_bar_figure(summary: pd.DataFrame, metric: str, title: str | None = None) -> go.Figure:
    """Barras agrupadas: uma métrica por cenário e experimento.

    `summary` deve ter colunas 'scenario', 'experiment' e a métrica escolhida.
    """
    fig = go.Figure()
    for i, (exp, group) in enumerate(summary.groupby("experiment", sort=False)):
        fig.add_trace(go.Bar(x=group["scenario"], y=group[metric], name=exp,
                             marker_color=SERIES_COLORS[i % len(SERIES_COLORS)]))
    fig.update_layout(title=title or metric, barmode="group", **{**_LAYOUT, "hovermode": "closest"})
    return fig


def distribution_figure(results: pd.DataFrame, metric: str, scenario: str, title: str | None = None) -> go.Figure:
    """Box plot da métrica entre seeds, por experimento, em um cenário."""
    data = results[results["scenario"] == scenario]
    fig = go.Figure()
    for i, (exp, group) in enumerate(data.groupby("experiment", sort=False)):
        fig.add_trace(go.Box(y=group[metric], name=exp, boxpoints="all", jitter=0.3,
                             marker_color=SERIES_COLORS[i % len(SERIES_COLORS)]))
    fig.update_layout(title=title or f"{metric} entre seeds — {scenario}", showlegend=False,
                      **{**_LAYOUT, "hovermode": "closest"})
    return fig

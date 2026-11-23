"""Stop-Loss baseado em preço de fechamento.

Linha do tempo de uma operação (mesma convenção do motor):

    entry_signal_date  : barra em que o sinal vai de 0 para 1.
                         Execução presumida da compra no fechamento dessa barra.
                         entry_price = Close dessa barra.
    trigger_date       : primeira barra, depois da entrada, em que
                         Close <= entry_price * (1 - stop_pct).
    execution_date     : execução presumida da venda = fechamento da trigger_date
                         (com dados diários de fechamento não dá para sair antes).
    flat_position_date : primeira barra em que o motor mostra position = 0
                         (a barra seguinte à execução), ou None se o gatilho
                         ocorreu na última barra.

Como o Stop observa apenas fechamentos, a perda observada pode ser MAIOR que
stop_pct (gaps e quedas fortes atravessam o nível do stop). Por isso o evento
registra stop_price, trigger_price e observed_loss separadamente.

Depois de um Stop, novas entradas ficam bloqueadas até que o sinal original
volte a 0 e gere um NOVO cruzamento de alta (0 -> 1).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from tradelab.strategies.base import SIGNAL_COLUMN

EVENT_COLUMNS = [
    "entry_signal_date",
    "entry_price",
    "stop_price",
    "trigger_date",
    "trigger_price",
    "execution_date",
    "flat_position_date",
    "observed_loss",
    "stop_pct",
]


@dataclass(frozen=True)
class StopEvent:
    entry_signal_date: pd.Timestamp
    entry_price: float
    stop_price: float
    trigger_date: pd.Timestamp
    trigger_price: float
    execution_date: pd.Timestamp
    flat_position_date: pd.Timestamp | None
    observed_loss: float
    stop_pct: float


@dataclass
class StopLossResult:
    """Dados com sinal ajustado + tabela de eventos de Stop."""

    data: pd.DataFrame
    events: pd.DataFrame

    @property
    def n_stops(self) -> int:
        return len(self.events)


def apply_stop_loss(
    data: pd.DataFrame,
    stop_pct: float,
    signal_column: str = SIGNAL_COLUMN,
    price_column: str = "Close",
) -> StopLossResult:
    """Aplica Stop-Loss sobre um sinal long/flat.

    Retorna uma cópia dos dados em que:
        - 'raw_signal' guarda o sinal original da estratégia;
        - 'signal' passa a ser o sinal ajustado pelo Stop;
        - 'stop_triggered' marca (1) as barras de gatilho;
        - 'stop_blocked' marca (1) as barras com reentrada bloqueada.
    """
    if not 0 < stop_pct < 1:
        raise ValueError("stop_pct precisa estar entre 0 e 1 (ex.: 0.03 para 3%).")
    for col in (signal_column, price_column):
        if col not in data.columns:
            raise KeyError(f"Coluna obrigatória ausente: '{col}'.")

    out = data.copy()
    raw = out[signal_column].astype(int).to_numpy()
    close = out[price_column].astype(float).to_numpy()
    index = out.index
    n = len(out)

    adjusted = [0] * n
    triggered = [0] * n
    blocked_flags = [0] * n
    events: list[StopEvent] = []

    holding = False          # sinal ajustado da barra anterior era 1?
    blocked = False          # aguardando novo cruzamento de alta?
    entry_price = 0.0
    entry_date = None

    for i in range(n):
        if blocked:
            if raw[i] == 0:
                blocked = False      # sinal original "resetou": a próxima subida é um cruzamento novo
            else:
                blocked_flags[i] = 1
            adjusted[i] = 0
            holding = False
            continue

        if not holding:
            if raw[i] == 1:
                holding = True
                entry_price = close[i]
                entry_date = index[i]
                adjusted[i] = 1
            continue

        # Já posicionado: verificar Stop antes de seguir o sinal original.
        stop_price = entry_price * (1 - stop_pct)
        if close[i] <= stop_price:
            triggered[i] = 1
            adjusted[i] = 0
            holding = False
            blocked = raw[i] == 1
            events.append(
                StopEvent(
                    entry_signal_date=entry_date,
                    entry_price=float(entry_price),
                    stop_price=float(stop_price),
                    trigger_date=index[i],
                    trigger_price=float(close[i]),
                    execution_date=index[i],
                    flat_position_date=index[i + 1] if i + 1 < n else None,
                    observed_loss=float(close[i] / entry_price - 1),
                    stop_pct=stop_pct,
                )
            )
            continue

        adjusted[i] = raw[i]
        holding = raw[i] == 1

    out["raw_signal"] = raw
    out[signal_column] = adjusted
    out["stop_triggered"] = triggered
    out["stop_blocked"] = blocked_flags

    events_df = pd.DataFrame([asdict(e) for e in events], columns=EVENT_COLUMNS)
    return StopLossResult(data=out, events=events_df)

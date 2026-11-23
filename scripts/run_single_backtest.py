"""Executa um único backtest (SMA + Stop opcional) e mostra métricas e eventos de risco.

Uso:
    python scripts/run_single_backtest.py --scenario bear --stop 0.03
    python scripts/run_single_backtest.py --csv data/raw/meu_ativo.csv --short 20 --long 50
"""

from __future__ import annotations

import argparse

from tradelab.analytics import compute_metrics
from tradelab.backtesting import run_backtest
from tradelab.data import generate_synthetic_ohlcv, load_csv
from tradelab.risk import apply_stop_loss
from tradelab.strategies import SMACrossover


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default=None, help="CSV OHLCV com coluna Date")
    parser.add_argument("--scenario", choices=["bull", "bear", "sideways"], default="sideways")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--short", type=int, default=10)
    parser.add_argument("--long", type=int, default=30)
    parser.add_argument("--stop", type=float, default=None, help="ex.: 0.03 para 3%%")
    parser.add_argument("--cost-bps", type=float, default=0.0)
    args = parser.parse_args()

    data = load_csv(args.csv) if args.csv else generate_synthetic_ohlcv(args.scenario, seed=args.seed)
    signals = SMACrossover(args.short, args.long).generate_signals(data)

    events = None
    if args.stop is not None:
        stop_result = apply_stop_loss(signals, args.stop)
        signals, events = stop_result.data, stop_result.events

    result = run_backtest(signals, cost_bps=args.cost_bps)

    print("\nMétricas")
    for key, value in compute_metrics(result.frame).items():
        print(f"  {key:<18} {value:,.4f}" if isinstance(value, float) else f"  {key:<18} {value}")

    if events is not None:
        print(f"\nEventos de Stop ({len(events)})")
        if not events.empty:
            print(events.to_string(index=False))


if __name__ == "__main__":
    main()

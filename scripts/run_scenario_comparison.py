"""Compara SMA 10/30, SMA + Stop 3%, SMA + Stop 5% e Buy and Hold
nos cenários sintéticos Bull, Bear e Sideways.

Uso (na raiz do projeto, com o ambiente virtual ativo):
    python scripts/run_scenario_comparison.py
    python scripts/run_scenario_comparison.py --seeds 1 2 3 4 5 --cost-bps 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tradelab.analytics import Experiment, compare_experiments, summarize_by_scenario
from tradelab.strategies import BuyAndHold, SMACrossover

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def build_experiments() -> list[Experiment]:
    sma = SMACrossover(short_window=10, long_window=30)
    return [
        Experiment("SMA 10/30", sma),
        Experiment("SMA + Stop 3%", sma, stop_pct=0.03),
        Experiment("SMA + Stop 5%", sma, stop_pct=0.05),
        Experiment("Buy and Hold", BuyAndHold()),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparação de cenários do TradeLab")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--periods", type=int, default=504)
    parser.add_argument("--cost-bps", type=float, default=0.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    args = parser.parse_args()

    results = compare_experiments(
        build_experiments(),
        scenarios=["bull", "bear", "sideways"],
        seeds=args.seeds,
        n_periods=args.periods,
        cost_bps=args.cost_bps,
        slippage_bps=args.slippage_bps,
    )

    summary = summarize_by_scenario(results)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print(f"\nSeeds: {args.seeds} | períodos: {args.periods} | custo: {args.cost_bps} bps | slippage: {args.slippage_bps} bps\n")
    cols = ["total_return", "annualized_return", "volatility", "sharpe", "max_drawdown", "exposure", "n_trades", "n_stops"]
    print(summary[cols].to_string())

    REPORTS_DIR.mkdir(exist_ok=True)
    results.to_csv(REPORTS_DIR / "scenario_comparison_raw.csv", index=False)
    summary.to_csv(REPORTS_DIR / "scenario_comparison_summary.csv")
    print(f"\nRelatórios salvos em: {REPORTS_DIR}")
    print("Observação: resultados em dados sintéticos são observações experimentais, não conclusões estatísticas.")


if __name__ == "__main__":
    main()

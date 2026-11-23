"""Gera arquivos CSV OHLCV sintéticos em data/raw/ para os três cenários.

Uso:
    python scripts/generate_synthetic_data.py
    python scripts/generate_synthetic_data.py --seed 7 --periods 756
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tradelab.data import generate_synthetic_ohlcv, load_csv

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--periods", type=int, default=504)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in ("bull", "bear", "sideways"):
        df = generate_synthetic_ohlcv(scenario=scenario, n_periods=args.periods, seed=args.seed)
        path = RAW_DIR / f"synthetic_{scenario}_seed{args.seed}.csv"
        df.to_csv(path)
        load_csv(path)  # garante que o arquivo salvo volta a passar na validação
        print(f"{scenario:<9} -> {path.name}  ({len(df)} linhas, Close final {df['Close'].iloc[-1]:.2f})")


if __name__ == "__main__":
    main()

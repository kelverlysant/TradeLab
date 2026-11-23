"""Ponto de entrada da API (usado pela Vercel e pelo uvicorn local).

A Vercel procura um objeto FastAPI chamado `app` em main.py na raiz.
O src/ é adicionado ao caminho para o pacote ser encontrado mesmo sem
instalação (pip install -e .).
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tradelab.api.app import app  # noqa: E402

__all__ = ["app"]

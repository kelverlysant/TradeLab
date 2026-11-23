# TradeLab Platform

**Laboratório quantitativo e plataforma de simulação de estratégias financeiras.**

> Construir. Simular. Medir. Avaliar.

O TradeLab permite criar estratégias de investimento, testá-las com dados de mercado,
simular operações com custos e gerenciamento de risco e avaliar os resultados com
métricas de desempenho.

O projeto **não** negocia dinheiro real nem envia ordens para corretoras.

---

## Arquitetura

```
Dados de mercado (CSV / sintéticos)
        │
        ▼
data/market_data.py ── validação OHLCV
        │
        ▼
strategies/ ─────────── SMA Crossover, Buy and Hold  → coluna "signal" (0/1)
        │
        ▼
risk/stop_loss.py ───── ajusta o sinal + registra eventos de Stop
        │
        ▼
backtesting/engine.py ─ posição, retornos, turnover, custos, patrimônio
        │
        ▼
analytics/ ──────────── métricas + comparação de cenários
```

```
TradeLab/
├── data/
│   ├── raw/                  # CSVs de entrada (ignorados pelo git)
│   └── processed/
├── reports/                  # relatórios gerados pelos scripts
├── app/streamlit_app.py      # dashboard local (Streamlit)
├── main.py                   # entrada da API (Vercel / uvicorn)
├── public/                   # página web + Plotly.js
├── scripts/
│   ├── generate_synthetic_data.py
│   ├── run_single_backtest.py
│   └── run_scenario_comparison.py
├── src/tradelab/
│   ├── data/market_data.py
│   ├── strategies/           # base.py, sma.py, buy_and_hold.py
│   ├── backtesting/engine.py
│   ├── risk/stop_loss.py
│   ├── analytics/            # metrics.py, comparison.py
│   ├── visualization/        # gráficos Plotly (Streamlit)
│   └── api/                  # FastAPI: schemas, service, app
├── tests/                    # pytest
├── pyproject.toml
└── ROADMAP.md
```

## Instalação (Windows / PowerShell)

Requisitos: Python 3.10+ e Git.

```powershell
git clone https://github.com/kelverlysant/TradeLab.git
cd TradeLab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,ui]"
```

> Se o PowerShell bloquear a ativação do ambiente:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

No Linux/macOS, ative com `source .venv/bin/activate`.

## Plataforma web (FastAPI + Vercel)

A API expõe o motor por HTTP e serve uma página web com os gráficos.

```powershell
python -m uvicorn main:app --reload
```

- Página: `http://localhost:8000`
- Documentação interativa da API (Swagger): `http://localhost:8000/docs`

| Método | Rota             | O que faz                                              |
|--------|------------------|--------------------------------------------------------|
| GET    | `/api/health`    | Status e versão                                        |
| GET    | `/api/strategies`| Estratégias disponíveis                                |
| POST   | `/api/backtest`  | SMA (com Stop opcional), SMA pura e Buy and Hold       |
| POST   | `/api/compare`   | Comparação em Bull, Bear e Sideways com várias seeds   |

Entradas validadas com Pydantic: parâmetros inválidos retornam **422** com a mensagem do erro.

**Dados próprios:** na página, escolha "CSV próprio" e envie um arquivo com as colunas
`Date, Open, High, Low, Close, Volume`. O navegador lê o arquivo e manda o conteúdo no campo
`data.csv` de `/api/backtest`; a API aplica a mesma validação OHLCV da biblioteca. Limites:
de 60 a 2.520 linhas (cerca de 10 anos de pregões) e até 1 MB. A comparação de cenários
continua usando dados sintéticos.

```json
{ "data": { "csv": "Date,Open,High,Low,Close,Volume\n2024-01-02,10.1,10.4,9.9,10.3,1200\n..." },
  "sma": { "short_window": 10, "long_window": 30 }, "stop_pct": 0.03 }
```

### Deploy na Vercel

O projeto já está pronto para a Vercel (zero configuração):

- `main.py` na raiz expõe o objeto `app` do FastAPI, que a Vercel transforma em uma função Python;
- `pyproject.toml` define as dependências e `[tool.vercel] entrypoint = "main:app"`;
- `public/` (página e Plotly.js) é servido pelo CDN da Vercel.

Passos: em [vercel.com/new](https://vercel.com/new), importe o repositório do GitHub,
mantenha o preset **FastAPI** detectado e clique em **Deploy**. Cada `git push`
na branch principal gera um novo deploy automaticamente.

## Dashboard local (Streamlit)

```powershell
streamlit run app/streamlit_app.py
```

O navegador abre em `http://localhost:8501`. Na barra lateral você escolhe os dados
(sintéticos ou um CSV próprio), as janelas da SMA, o Stop, os custos e o capital.

- **Backtest:** indicadores contra o Buy and Hold, preço com médias, compras, vendas e
  Stops marcados, curvas de patrimônio, drawdown, tabela de métricas e eventos de Stop.
- **Comparação de cenários:** várias seeds e níveis de Stop, médias por cenário e
  a distribuição dos resultados entre seeds (box plot).
- **Dados:** a tabela OHLCV validada.

A interface só chama a biblioteca `tradelab`: nenhuma regra quantitativa mora nela.

## Como usar

```powershell
# Rodar todos os testes
python -m pytest

# Comparar SMA 10/30, SMA + Stop 3%, SMA + Stop 5% e Buy and Hold (Bull, Bear, Sideways)
python scripts/run_scenario_comparison.py

# Mesma comparação, com 10 seeds e custo de 5 bps
python scripts/run_scenario_comparison.py --seeds 1 2 3 4 5 6 7 8 9 10 --cost-bps 5

# Um backtest isolado com Stop de 3%, mostrando os eventos de risco
python scripts/run_single_backtest.py --scenario bear --stop 0.03

# Gerar CSVs sintéticos em data/raw/
python scripts/generate_synthetic_data.py --seed 42
```

Uso como biblioteca:

```python
from tradelab.data import generate_synthetic_ohlcv
from tradelab.strategies import SMACrossover
from tradelab.risk import apply_stop_loss
from tradelab.backtesting import run_backtest
from tradelab.analytics import compute_metrics

data = generate_synthetic_ohlcv("bull", seed=42)
signals = SMACrossover(10, 30).generate_signals(data)
stopped = apply_stop_loss(signals, stop_pct=0.03)
result = run_backtest(stopped.data, initial_capital=100_000, cost_bps=5)

print(compute_metrics(result.frame))
print(stopped.events)
```

---

## Decisões técnicas

### 1. Sem look-ahead bias

O sinal da barra `t` usa informações até o fechamento de `t`. A execução presumida
acontece nesse fechamento, então a exposição só começa no retorno `t → t+1`:

```python
position = signal.shift(1, fill_value=0)
```

Há um teste específico garantindo que alterar o sinal da última barra não muda
nenhum resultado (`test_signal_on_last_bar_has_no_effect`).

### 2. Custos alinhados à execução

`turnover = |position_t − position_{t−1}|`. O custo (`cost_bps + slippage_bps`) é
descontado do retorno da barra em que a nova posição passa a valer — ou seja, junto
com a primeira exposição gerada pela troca.

### 3. Linha do tempo do Stop-Loss

| Campo                | Significado                                                       |
|----------------------|-------------------------------------------------------------------|
| `entry_signal_date`  | Barra em que o sinal vai de 0 para 1 (compra no fechamento)        |
| `entry_price`        | Fechamento da barra de entrada                                    |
| `stop_price`         | `entry_price × (1 − stop_pct)`                                     |
| `trigger_date`       | Primeiro fechamento `<= stop_price` depois da entrada             |
| `execution_date`     | Venda presumida no fechamento do gatilho (= `trigger_date`)       |
| `flat_position_date` | Primeira barra com `position = 0` no motor (barra seguinte)       |
| `observed_loss`      | `trigger_price / entry_price − 1`                                  |

Como o Stop observa só fechamentos, **a perda observada pode ser maior que o
`stop_pct`** (ex.: Stop de 3% com perda real de 4,8%). Os testes de integração
verificam que a perda acumulada no motor até `execution_date` é exatamente o
`observed_loss` do evento, e que a posição está zerada em `flat_position_date`.

Depois de um Stop, a reentrada fica bloqueada até o sinal original voltar a 0 e
gerar um novo cruzamento de alta.

### 4. Métricas

O primeiro registro não tem retorno anterior e não é tratado como período de
negociação. Métricas: Total Return, Annualized Return (CAGR), Volatility,
Sharpe Ratio, Maximum Drawdown, Exposure, nº de trades e nº de stops.

### 5. Dados sintéticos

Movimento Browniano Geométrico com drift por cenário (Bull +15% a.a., Bear −15% a.a.,
Sideways 0) e volatilidade de 20% a.a. A seed torna as trajetórias reproduzíveis.

> Dados sintéticos testam o comportamento do sistema em condições controladas.
> Eles **não** comprovam que uma estratégia funciona no mercado real.

---

## Status

| Fase | Conteúdo                                   | Status        |
|------|--------------------------------------------|---------------|
| 1    | Estrutura do projeto                       | Concluída     |
| 2    | Validação de dados e dados sintéticos      | Concluída     |
| 3    | Estratégias (SMA, Buy and Hold)            | Concluída     |
| 4    | Motor de backtesting                       | Concluída     |
| 5    | Métricas de desempenho                     | Concluída     |
| 6    | Stop-Loss com eventos auditados            | Concluída     |
| 7    | Comparação de cenários (multi-seed)        | Concluída     |
| 8    | Testes automatizados (115 testes)          | Em evolução   |
| 7*   | Dashboard em Streamlit (primeira versão)   | Concluída     |
| 6*   | API FastAPI + página web na Vercel         | Concluída     |

Próximos passos em [ROADMAP.md](ROADMAP.md).

---

## Aviso

Projeto educacional e de pesquisa. Nada aqui é recomendação de investimento;
resultados de backtest não garantem resultados futuros.

# Roadmap do TradeLab

Ordem recomendada:

**Confiabilidade quantitativa → avaliação estatística → persistência → API → interface → paper trading → deploy.**

Uma interface bonita não compensa um motor que calcula incorretamente a posição ou o
patrimônio. Primeiro o núcleo precisa pensar corretamente.

## 1. Consolidar o motor quantitativo — *em andamento*
- [x] Auditoria do Stop-Loss (`execution_date`, `flat_position_date`)
- [x] Eventos de risco com preço de entrada, stop, gatilho e perda observada
- [x] Custos e slippage alinhados ao momento de execução
- [x] Validações de entrada do motor
- [x] Testes integrados de posições, custos e patrimônio
- [ ] Stop intradiário opcional (usar `Low` e simular execução no preço do stop ou no gap)

**Conclusão:** sinais, eventos, execuções presumidas e retornos temporalmente consistentes.

## 2. Aprimorar a avaliação quantitativa
- [x] Várias seeds por cenário (`--seeds`)
- [ ] Distribuição dos resultados (média, desvio, percentis) por estratégia
- [ ] Análise de sensibilidade dos parâmetros (grade de janelas SMA e níveis de Stop)
- [x] Slippage e custos parametrizados
- [x] Métrica de exposição
- [ ] Separar amostras de desenvolvimento e avaliação (in-sample / out-of-sample)

## 3. Ampliar o universo de estratégias
- [x] Interface comum (`Strategy`)
- [ ] RSI
- [ ] MACD
- [ ] Reversão à média
- [ ] Momentum
- [ ] Configuração de experimentos via arquivo (YAML/TOML)

## 4. Integrar dados históricos reais
- [ ] Escolher fonte e criar importador/normalizador
- [ ] Calendário de negociação, ausentes e duplicados
- [ ] Eventos corporativos e preços ajustados
- [ ] Documentar origem e limitações (sem misturar com sintéticos)

## 5. Persistência com PostgreSQL
- [ ] Ativos, séries históricas, estratégias e parâmetros
- [ ] Execuções de backtest, métricas e eventos de risco
- [ ] Migrações (Alembic)

## 6. API com FastAPI
- [ ] Endpoints de estratégias, backtests e métricas
- [ ] Validação (Pydantic), tratamento de erros, documentação OpenAPI

## 7. Interface da plataforma
- [x] Dashboard em Streamlit: patrimônio, preço e indicadores, drawdown, comparação entre estratégias, eventos de risco
- [x] Configuração de novos experimentos pela barra lateral
- [ ] Histórico de backtests (depende da etapa 5 — PostgreSQL)
- [ ] Front-end web consumindo a API (depende da etapa 6 — FastAPI)

## 8. Simulador de paper trading
- [ ] Broker Simulator, ordens, livro de posições, saldo
- [ ] Ciclo de vida das ordens, rejeições e cancelamentos

## 9. Infraestrutura de produção
- [ ] Docker, CI/CD (GitHub Actions), logs estruturados, monitoramento, deploy

## 10. Documentação e apresentação
- [ ] Diagramas, exemplos reproduzíveis, relatórios e demonstração completa

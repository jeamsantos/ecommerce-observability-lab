# Mini Order API

API simples de pedidos em Python/FastAPI para estudar observabilidade com Prometheus e Grafana.

## O que este projeto monitora

- Requisicoes HTTP por rota e status.
- Latencia HTTP geral e p95.
- Pedidos criados, pagos e cancelados.
- Pedidos ativos por status.
- Falhas simuladas de pagamento.
- Latencia simulada do pagamento.
- Logs em JSON para facilitar leitura em ferramentas de observabilidade.

## Como subir tudo

```bash
docker compose up --build
```

Depois acesse:

- API: http://localhost:8000/docs
- Metricas Prometheus: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Loki: http://localhost:3100/ready
- Grafana: http://localhost:3000
- cAdvisor: http://localhost:8080

Login do Grafana:

- Usuario: `admin`
- Senha: `admin`

O dashboard `Mini Order API` sera carregado automaticamente na pasta `Observability Studies`.

## Consultar logs no Grafana

Com a stack rodando, acesse o Grafana e va em `Explore`. Selecione a fonte `Loki` e use uma consulta como:

```logql
{service="ecommerce-api"}
```

Para procurar falhas de pagamento:

```logql
{service="ecommerce-api", event="payment_failed"}
```

Para investigar uma requisicao especifica, use o `X-Request-ID` retornado pela API:

```logql
{service="ecommerce-api"} | json | request_id="ID_DA_REQUISICAO"
```

Para investigar um pedido especifico:

```logql
{service="ecommerce-api"} | json | order_id="ID_DO_PEDIDO"
```

Um diagnostico mais detalhado do laboratorio esta em `OBSERVABILITY_DIAGNOSTIC.md`.

## Rodar apenas a API localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Gerar trafego para o dashboard

Com a stack rodando, execute em outro terminal:

```bash
python scripts/generate_traffic.py
```

Esse script cria pedidos e tenta pagar/cancelar alguns deles. A rota de pagamento tem atraso e falha aleatoria de proposito para gerar graficos interessantes.

## Teste rapido da API

Com a stack rodando, execute:

```bash
python scripts/smoke_test.py
```

Esse teste chama `/health`, cria um pedido, consulta o pedido, tenta pagar e valida se `/metrics` esta expondo dados.

## Simular incidentes

Com a stack rodando, use:

```bash
python3 scripts/incident_scenarios.py payment-failures
python3 scripts/incident_scenarios.py slow-response
python3 scripts/incident_scenarios.py unhandled-error
```

O roteiro de investigacao esta em `INCIDENT_PLAYBOOK.md`.

## Endpoints principais

```http
GET /health
GET /metrics
POST /orders
GET /orders
GET /orders/{order_id}
POST /orders/{order_id}/pay
POST /orders/{order_id}/cancel
```

Exemplo de criacao de pedido:

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"customer-1","product_id":"product-1","quantity":2,"unit_price":49.90}'
```

## Ideias para estudar depois

- Criar alertas no Grafana para taxa de erro e latencia alta.
- Adicionar banco PostgreSQL no lugar da memoria.
- Criar um worker com fila para simular processamento assincrono.

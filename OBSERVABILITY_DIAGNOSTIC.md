# Diagnostico do E-commerce Observability Lab

## Estado atual

- Linguagem e framework: Python com FastAPI.
- Aplicacao: API simples de pedidos de e-commerce.
- Banco de dados: nao ha banco persistente; os pedidos ficam em memoria.
- Containers principais: API, Prometheus, Grafana, Loki e Grafana Alloy.
- Logs: JSON em stdout/stderr, coletados pelo Docker e encaminhados pelo Alloy ao Loki.
- Metricas: endpoint `/metrics` exposto pela API e coletado pelo Prometheus.
- Grafana: datasources de Prometheus e Loki provisionados por arquivos.
- Testes: ha scripts manuais de smoke test e geracao de trafego.

## Endpoints atuais

- `GET /health`
- `GET /metrics`
- `POST /orders`
- `GET /orders`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/pay`
- `POST /orders/{order_id}/cancel`

## Variaveis de ambiente principais

- `APP_NAME`: nome tecnico da aplicacao.
- `SERVICE_NAME`: nome usado nos logs estruturados.
- `ENVIRONMENT`: ambiente simulado.
- `APP_VERSION`: versao exposta no health check.
- `LOG_LEVEL`: nivel minimo de log.
- `PAYMENT_FAILURE_RATE`: chance de falha no pagamento simulado.
- `PAYMENT_MIN_DELAY_MS`: menor latencia simulada do pagamento.
- `PAYMENT_MAX_DELAY_MS`: maior latencia simulada do pagamento.

## Riscos de regressao observados

- O estado em memoria e perdido quando o container da API reinicia.
- IDs de pedido continuam sendo dados de alta cardinalidade e devem ficar no corpo JSON do log, nao como labels do Loki.
- O Alloy precisa acessar `/var/run/docker.sock`; em alguns ambientes Docker Desktop pode exigir permissao adicional.
- Health checks usam `wget` dentro das imagens. Se alguma imagem nao disponibilizar o binario, o servico pode funcionar mesmo com health check falhando.

## Consultas iniciais de troubleshooting

Todos os logs da API:

```logql
{service="ecommerce-api"}
```

Falhas de pagamento:

```logql
{service="ecommerce-api", event="payment_failed"}
```

Fluxo por request ID:

```logql
{service="ecommerce-api"} | json | request_id="COLE_O_REQUEST_ID"
```

Fluxo por pedido:

```logql
{service="ecommerce-api"} | json | order_id="COLE_O_ORDER_ID"
```

Requisicoes HTTP com erro:

```logql
{service="ecommerce-api", event="http_request_completed"} | json | status_code >= 400
```

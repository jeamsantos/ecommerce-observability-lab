# Incident Playbook

Use este guia para treinar troubleshooting com metricas e logs.

## Cenario 1: Falhas de pagamento

Gerar incidente:

```bash
python3 scripts/incident_scenarios.py payment-failures
```

Metricas para consultar:

```promql
increase(ecommerce_payments_total{status="failed"}[5m])
```

```promql
rate(ecommerce_external_request_errors_total{dependency="fake-payment-provider"}[1m])
```

Logs para consultar:

```logql
{service="ecommerce-api", event="payment_failed"}
```

## Cenario 2: Latencia alta

Gerar incidente:

```bash
python3 scripts/incident_scenarios.py slow-response
```

Metricas para consultar:

```promql
histogram_quantile(0.95, sum(rate(ecommerce_http_request_duration_seconds_bucket[5m])) by (le))
```

Logs para consultar:

```logql
{service="ecommerce-api", event="incident_slow_response_simulated"}
```

## Cenario 3: Erro inesperado

Gerar incidente:

```bash
python3 scripts/incident_scenarios.py unhandled-error
```

Metricas para consultar:

```promql
increase(ecommerce_application_errors_total{error_type="RuntimeError"}[5m])
```

Logs para consultar:

```logql
{service="ecommerce-api", event="unhandled_exception"}
```

## Fluxo de investigacao

1. Identifique o sintoma no dashboard.
2. Valide a metrica no Prometheus.
3. Copie o `request_id` da resposta ou dos logs HTTP.
4. Procure o fluxo completo no Loki:

```logql
{service="ecommerce-api"} | json | request_id="COLE_O_REQUEST_ID"
```

5. Registre causa provavel, impacto, evidencias e acao corretiva.

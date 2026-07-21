import asyncio
import json
import logging
import os
import random
import time
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field


APP_NAME = os.getenv("APP_NAME", "mini-order-api")
SERVICE_NAME = os.getenv("SERVICE_NAME", "ecommerce-api")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PAYMENT_FAILURE_RATE = float(os.getenv("PAYMENT_FAILURE_RATE", "0.25"))
PAYMENT_MIN_DELAY_MS = int(os.getenv("PAYMENT_MIN_DELAY_MS", "80"))
PAYMENT_MAX_DELAY_MS = int(os.getenv("PAYMENT_MAX_DELAY_MS", "900"))

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class OrderStatus(str, Enum):
    created = "created"
    paid = "paid"
    cancelled = "cancelled"


class OrderCreate(BaseModel):
    customer_id: str = Field(..., examples=["customer-123"])
    product_id: str = Field(..., examples=["product-abc"])
    quantity: int = Field(..., ge=1, le=20, examples=[2])
    unit_price: float = Field(..., gt=0, examples=[49.9])


class Order(BaseModel):
    id: str
    customer_id: str
    product_id: str
    quantity: int
    unit_price: float
    total_amount: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


orders: Dict[str, Order] = {}

http_requests_total = Counter(
    "http_requests_total",
    "Total de requisicoes HTTP recebidas.",
    ["method", "path", "status_code"],
)
ecommerce_http_requests_total = Counter(
    "ecommerce_http_requests_total",
    "Total de requisicoes HTTP da aplicacao de e-commerce.",
    ["method", "route", "status_code"],
)
ecommerce_http_request_duration_seconds = Histogram(
    "ecommerce_http_request_duration_seconds",
    "Duracao das requisicoes HTTP da aplicacao de e-commerce em segundos.",
    ["method", "route", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
ecommerce_application_errors_total = Counter(
    "ecommerce_application_errors_total",
    "Total de erros da aplicacao por tipo e rota.",
    ["error_type", "route"],
)
ecommerce_orders_total = Counter(
    "ecommerce_orders_total",
    "Total de pedidos processados por status.",
    ["status"],
)
ecommerce_payments_total = Counter(
    "ecommerce_payments_total",
    "Total de pagamentos por status e provedor.",
    ["status", "provider"],
)
ecommerce_external_request_duration_seconds = Histogram(
    "ecommerce_external_request_duration_seconds",
    "Duracao de chamadas simuladas a dependencias externas em segundos.",
    ["dependency", "operation", "status_code"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
ecommerce_external_request_errors_total = Counter(
    "ecommerce_external_request_errors_total",
    "Total de erros em dependencias externas simuladas.",
    ["dependency", "operation", "status_code"],
)
ecommerce_application_info = Gauge(
    "ecommerce_application_info",
    "Informacoes estaticas da aplicacao.",
    ["version", "environment"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP em segundos.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
orders_created_total = Counter("orders_created_total", "Total de pedidos criados.")
orders_paid_total = Counter("orders_paid_total", "Total de pedidos pagos.")
orders_cancelled_total = Counter("orders_cancelled_total", "Total de pedidos cancelados.")
payment_failures_total = Counter("payment_failures_total", "Total de falhas no pagamento.")
active_orders = Gauge("active_orders", "Pedidos ainda nao finalizados.")
orders_by_status = Gauge("orders_by_status", "Quantidade atual de pedidos por status.", ["status"])
payment_duration_seconds = Histogram(
    "payment_duration_seconds",
    "Duracao da simulacao de pagamento em segundos.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)


class JsonLogFormatter(logging.Formatter):
    default_fields = {
        "event": None,
        "request_id": None,
        "correlation_id": None,
        "trace_id": None,
        "method": None,
        "route": None,
        "path": None,
        "status_code": None,
        "duration_ms": None,
        "response_size_bytes": None,
        "user_id": None,
        "order_id": None,
        "transaction_id": None,
        "payment_provider": None,
        "payment_status": None,
        "error_type": None,
        "error_code": None,
        "stack_trace": None,
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": now_utc().isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "environment": ENVIRONMENT,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field, default in self.default_fields.items():
            payload[field] = getattr(record, field, default)

        payload["request_id"] = payload["request_id"] or request_id_context.get()
        payload["correlation_id"] = payload["correlation_id"] or correlation_id_context.get()
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


configure_logging()
logger = logging.getLogger(APP_NAME)
ecommerce_application_info.labels(version=APP_VERSION, environment=ENVIRONMENT).set(1)

app = FastAPI(
    title="Mini Order API",
    description="API simples de pedidos para estudar observabilidade com Prometheus e Grafana.",
    version="1.0.0",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_uuid(value: str | None) -> str:
    if not value:
        return str(uuid4())
    try:
        return str(UUID(value))
    except ValueError:
        return str(uuid4())


def log_event(level: int, event: str, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"event": event, **fields})


def refresh_order_gauges() -> None:
    counts = {status.value: 0 for status in OrderStatus}
    for order in orders.values():
        counts[order.status.value] += 1

    for status, count in counts.items():
        orders_by_status.labels(status=status).set(count)

    active_orders.set(counts[OrderStatus.created.value])


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    route = request.url.path
    request_id = safe_uuid(request.headers.get("X-Request-ID"))
    correlation_id = safe_uuid(request.headers.get("X-Correlation-ID")) if request.headers.get("X-Correlation-ID") else request_id
    request_token = request_id_context.set(request_id)
    correlation_token = correlation_id_context.set(correlation_id)

    try:
        response = await call_next(request)
        status_code = response.status_code
        if request.scope.get("route"):
            route = request.scope["route"].path
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        duration = time.perf_counter() - start
        http_requests_total.labels(
            method=request.method,
            path=route,
            status_code=str(status_code),
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            path=route,
        ).observe(duration)
        ecommerce_http_requests_total.labels(
            method=request.method,
            route=route,
            status_code=str(status_code),
        ).inc()
        ecommerce_http_request_duration_seconds.labels(
            method=request.method,
            route=route,
            status_code=str(status_code),
        ).observe(duration)
        log_event(
            logging.INFO,
            "http_request_completed",
            "HTTP request completed",
            method=request.method,
            route=route,
            path=request.url.path,
            status_code=status_code,
            duration_ms=round(duration * 1000, 2),
            user_id="anonymous",
        )
        request_id_context.reset(request_token)
        correlation_id_context.reset(correlation_token)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = request_id_context.get() or safe_uuid(request.headers.get("X-Request-ID"))
    correlation_id = correlation_id_context.get() or request_id
    route = request.scope["route"].path if request.scope.get("route") else request.url.path
    ecommerce_application_errors_total.labels(
        error_type="HTTPException",
        route=route,
    ).inc()
    payload = {"detail": exc.detail, "request_id": request_id}
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request_id_context.get() or safe_uuid(request.headers.get("X-Request-ID"))
    correlation_id = correlation_id_context.get() or request_id
    route = request.scope["route"].path if request.scope.get("route") else request.url.path
    ecommerce_application_errors_total.labels(
        error_type=type(exc).__name__,
        route=route,
    ).inc()
    stack_trace = traceback.format_exc() if ENVIRONMENT == "development" else None
    log_event(
        logging.ERROR,
        "unhandled_exception",
        "Unexpected error while processing request",
        method=request.method,
        route=route,
        path=request.url.path,
        status_code=500,
        error_type=type(exc).__name__,
        error_code="UNHANDLED_EXCEPTION",
        stack_trace=stack_trace,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred", "request_id": request_id},
        headers={"X-Request-ID": request_id, "X-Correlation-ID": correlation_id},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME, "environment": ENVIRONMENT, "version": APP_VERSION, "time": now_utc()}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/orders", response_model=Order, status_code=201)
def create_order(payload: OrderCreate):
    created_at = now_utc()
    order = Order(
        id=str(uuid4()),
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        total_amount=round(payload.quantity * payload.unit_price, 2),
        status=OrderStatus.created,
        created_at=created_at,
        updated_at=created_at,
    )
    orders[order.id] = order
    orders_created_total.inc()
    ecommerce_orders_total.labels(status=OrderStatus.created.value).inc()
    refresh_order_gauges()

    log_event(
        logging.INFO,
        "order_created",
        "Order created successfully",
        order_id=order.id,
        user_id="anonymous",
    )
    return order


@app.get("/orders", response_model=list[Order])
def list_orders():
    return list(orders.values())


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders/{order_id}/pay", response_model=Order)
async def pay_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.created:
        raise HTTPException(status_code=409, detail=f"Order is already {order.status.value}")

    transaction_id = str(uuid4())
    provider = "fake-pay"
    delay = random.randint(PAYMENT_MIN_DELAY_MS, PAYMENT_MAX_DELAY_MS) / 1000
    start = time.perf_counter()
    log_event(
        logging.INFO,
        "payment_started",
        "Payment started",
        order_id=order.id,
        transaction_id=transaction_id,
        payment_provider=provider,
        payment_status="started",
    )
    await asyncio.sleep(delay)
    payment_duration = time.perf_counter() - start
    payment_duration_seconds.observe(payment_duration)

    if random.random() < PAYMENT_FAILURE_RATE:
        payment_failures_total.inc()
        ecommerce_payments_total.labels(status="failed", provider=provider).inc()
        ecommerce_external_request_duration_seconds.labels(
            dependency="fake-payment-provider",
            operation="charge",
            status_code="402",
        ).observe(payment_duration)
        ecommerce_external_request_errors_total.labels(
            dependency="fake-payment-provider",
            operation="charge",
            status_code="402",
        ).inc()
        log_event(
            logging.WARNING,
            "payment_failed",
            "Payment failed",
            order_id=order.id,
            transaction_id=transaction_id,
            payment_provider=provider,
            payment_status="failed",
            duration_ms=round(payment_duration * 1000, 2),
            error_type="PaymentDeclined",
            error_code="PAYMENT_DECLINED",
        )
        raise HTTPException(status_code=402, detail="Payment failed")

    order.status = OrderStatus.paid
    order.updated_at = now_utc()
    orders_paid_total.inc()
    ecommerce_orders_total.labels(status=OrderStatus.paid.value).inc()
    ecommerce_payments_total.labels(status="succeeded", provider=provider).inc()
    ecommerce_external_request_duration_seconds.labels(
        dependency="fake-payment-provider",
        operation="charge",
        status_code="200",
    ).observe(payment_duration)
    refresh_order_gauges()

    log_event(
        logging.INFO,
        "payment_succeeded",
        "Payment succeeded",
        order_id=order.id,
        transaction_id=transaction_id,
        payment_provider=provider,
        payment_status="succeeded",
        duration_ms=round(payment_duration * 1000, 2),
    )
    return order


@app.post("/orders/{order_id}/cancel", response_model=Order)
def cancel_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == OrderStatus.paid:
        raise HTTPException(status_code=409, detail="Paid orders cannot be cancelled")
    if order.status == OrderStatus.cancelled:
        raise HTTPException(status_code=409, detail="Order is already cancelled")

    order.status = OrderStatus.cancelled
    order.updated_at = now_utc()
    orders_cancelled_total.inc()
    ecommerce_orders_total.labels(status=OrderStatus.cancelled.value).inc()
    refresh_order_gauges()

    log_event(
        logging.INFO,
        "order_cancelled",
        "Order cancelled successfully",
        order_id=order.id,
        user_id="anonymous",
    )
    return order


@app.get("/incidents/slow-response")
async def simulate_slow_response(delay_ms: int = Query(1500, ge=100, le=5000)):
    await asyncio.sleep(delay_ms / 1000)
    log_event(
        logging.WARNING,
        "incident_slow_response_simulated",
        "Slow response incident simulated",
        duration_ms=delay_ms,
    )
    return {"status": "simulated", "incident": "slow_response", "delay_ms": delay_ms}


@app.get("/incidents/unhandled-error")
def simulate_unhandled_error():
    raise RuntimeError("Simulated unhandled exception for observability training")

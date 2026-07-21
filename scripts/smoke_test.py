import json
from urllib import error, request


BASE_URL = "http://localhost:8000"


def call(method, path, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=5) as response:
            payload = response.read().decode("utf-8")
            return response.status, payload
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main():
    checks = []

    status, body = call("GET", "/health")
    checks.append(("health", status == 200, status, body))

    status, body = call(
        "POST",
        "/orders",
        {
            "customer_id": "customer-smoke",
            "product_id": "product-smoke",
            "quantity": 2,
            "unit_price": 49.9,
        },
    )
    checks.append(("create order", status == 201, status, body))
    order = json.loads(body)

    status, body = call("GET", f"/orders/{order['id']}")
    checks.append(("get order", status == 200, status, body))

    status, body = call("POST", f"/orders/{order['id']}/pay")
    checks.append(("pay order", status in (200, 402), status, body))

    status, body = call("GET", "/metrics")
    checks.append(("metrics", status == 200 and "http_requests_total" in body, status, body[:120]))

    for name, ok, status, body in checks:
        result = "OK" if ok else "FAIL"
        print(f"{result} {name} -> HTTP {status}")
        if not ok:
            print(body)

    if not all(ok for _, ok, _, _ in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

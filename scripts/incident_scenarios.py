import json
import sys
import time
from urllib import error, parse, request


BASE_URL = "http://localhost:8000"


def call(method, path, body=None, headers=None):
    data = None
    req_headers = headers or {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=req_headers)
    try:
        with request.urlopen(req, timeout=8) as response:
            return response.status, response.headers, response.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8")


def create_order():
    status, headers, body = call(
        "POST",
        "/orders",
        {
            "customer_id": "incident-user",
            "product_id": "incident-product",
            "quantity": 1,
            "unit_price": 99.9,
        },
    )
    print(f"create_order -> HTTP {status} request_id={headers.get('X-Request-ID')}")
    return json.loads(body)["id"]


def payment_failures(rounds=15):
    for _ in range(rounds):
        order_id = create_order()
        status, headers, body = call("POST", f"/orders/{order_id}/pay")
        print(f"payment_attempt order_id={order_id} -> HTTP {status} request_id={headers.get('X-Request-ID')}")
        if status >= 400:
            print(body)
        time.sleep(0.3)


def slow_response(delay_ms=2500, rounds=5):
    query = parse.urlencode({"delay_ms": delay_ms})
    for _ in range(rounds):
        status, headers, body = call("GET", f"/incidents/slow-response?{query}")
        print(f"slow_response -> HTTP {status} request_id={headers.get('X-Request-ID')} body={body}")


def unhandled_error(rounds=3):
    for _ in range(rounds):
        status, headers, body = call("GET", "/incidents/unhandled-error")
        print(f"unhandled_error -> HTTP {status} request_id={headers.get('X-Request-ID')} body={body}")


def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "payment-failures"
    if scenario == "payment-failures":
        payment_failures()
    elif scenario == "slow-response":
        slow_response()
    elif scenario == "unhandled-error":
        unhandled_error()
    else:
        print("Use: payment-failures | slow-response | unhandled-error")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

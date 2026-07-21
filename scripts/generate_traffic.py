import random
import json
import time
from urllib import error, request


BASE_URL = "http://localhost:8000"


def post_json(path, body=None):
    data = b"{}" if body is None else body.encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=3) as response:
            return response.status, response.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except error.URLError as exc:
        return 0, str(exc)


def main():
    created_orders = []

    while True:
        quantity = random.randint(1, 5)
        price = round(random.uniform(15, 250), 2)
        payload = (
            "{"
            f'"customer_id":"customer-{random.randint(1, 20)}",'
            f'"product_id":"product-{random.randint(1, 8)}",'
            f'"quantity":{quantity},'
            f'"unit_price":{price}'
            "}"
        )

        status, body = post_json("/orders", payload)
        print(f"POST /orders -> {status}")

        if status == 201:
            order_id = json.loads(body)["id"]
            created_orders.append(order_id)

        if created_orders and random.random() < 0.75:
            order_id = random.choice(created_orders)
            action = "pay" if random.random() < 0.8 else "cancel"
            status, _ = post_json(f"/orders/{order_id}/{action}")
            print(f"POST /orders/{order_id}/{action} -> {status}")

        time.sleep(random.uniform(0.3, 1.2))


if __name__ == "__main__":
    main()

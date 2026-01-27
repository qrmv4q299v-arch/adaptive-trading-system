import time

RECONCILE_INTERVAL = 5
STUCK_TIMEOUT = 30

class OrderReconciliation:
    def __init__(self, api_client):
        self.api = api_client
        self.open_orders = {}

    def track_order(self, order):
        self.open_orders[order["exchange_order_id"]] = order

    def reconcile(self):
        now = time.time()
        fill_events = []

        for oid, order in list(self.open_orders.items()):
            status = self.api.get_order_status(oid)

            order["status"] = status["status"]
            new_filled = status["filled_size"]

            if new_filled > order["filled_size"]:
                fill_size = new_filled - order["filled_size"]
                order["filled_size"] = new_filled

                fill_events.append({
                    "symbol": order["symbol"],
                    "side": order["side"],
                    "size": fill_size,
                    "price": status.get("avg_price", 0),
                    "timestamp": now
                })

            if status["status"] == "FILLED":
                self.open_orders.pop(oid, None)

            elif status["status"] == "PARTIALLY_FILLED" and now - order["timestamp"] > STUCK_TIMEOUT:
                self.api.cancel_order(oid)

            elif status["status"] == "NEW" and now - order["timestamp"] > STUCK_TIMEOUT:
                self.api.cancel_order(oid)

            elif status["status"] == "CANCELED":
                self.open_orders.pop(oid, None)

        return fill_events

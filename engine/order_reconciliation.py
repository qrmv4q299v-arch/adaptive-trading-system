import time

RECONCILE_INTERVAL = 5
STUCK_TIMEOUT = 30  # seconds before we consider order stuck

class OrderReconciliation:
    def __init__(self, api_client):
        self.api = api_client
        self.open_orders = {}

    def track_order(self, order):
        self.open_orders[order["exchange_order_id"]] = order

    def reconcile(self):
        now = time.time()

        for oid, order in list(self.open_orders.items()):
            status = self.api.get_order_status(oid)

            order["status"] = status["status"]
            order["filled_size"] = status["filled_size"]

            if status["status"] == "FILLED":
                self._handle_filled(order)

            elif status["status"] == "PARTIALLY_FILLED":
                self._handle_partial(order, now)

            elif status["status"] == "NEW" and now - order["timestamp"] > STUCK_TIMEOUT:
                self._handle_stuck(order)

            elif status["status"] == "CANCELED":
                self._handle_canceled(order)

    def _handle_filled(self, order):
        print(f"Order FILLED: {order['exchange_order_id']}")
        self.open_orders.pop(order["exchange_order_id"], None)

    def _handle_partial(self, order, now):
        print(f"Order PARTIAL: {order['exchange_order_id']} size {order['filled_size']}")

        if now - order["timestamp"] > STUCK_TIMEOUT:
            print("Partial fill stuck — canceling remainder")
            self.api.cancel_order(order["exchange_order_id"])

    def _handle_stuck(self, order):
        print(f"Order STUCK: {order['exchange_order_id']} — canceling")
        self.api.cancel_order(order["exchange_order_id"])

    def _handle_canceled(self, order):
        print(f"Order CANCELED: {order['exchange_order_id']}")
        self.open_orders.pop(order["exchange_order_id"], None)

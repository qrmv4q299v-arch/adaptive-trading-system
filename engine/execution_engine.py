import time
from engine.order_reconciliation import OrderReconciliation

class ExecutionEngine:
    def __init__(self, api_client):
        self.api = api_client
        self.reconciler = OrderReconciliation(api_client)

    def execute(self, proposal):
        side = "BUY" if proposal["direction"] == "LONG" else "SELL"

        exchange_order_id = self.api.place_order(
            symbol=proposal["symbol"],
            side=side,
            size=proposal["size"]
        )

        order = {
            "proposal_id": proposal.get("id"),
            "exchange_order_id": exchange_order_id,
            "symbol": proposal["symbol"],
            "side": side,
            "requested_size": proposal["size"],
            "filled_size": 0.0,
            "status": "NEW",
            "timestamp": time.time()
        }

        self.reconciler.track_order(order)
        return order

from engine.position_manager import PositionManager

class ExecutionEngine:
    def __init__(self, api_client):
        self.api = api_client
        self.position_manager = PositionManager(api_client)
        self.reconciler = None

    def execute(self, proposal):
        order = {
            "symbol": proposal["symbol"],
            "side": "buy" if proposal["direction"] == "LONG" else "sell",
            "size": proposal["size"],
            "stop_loss": proposal["stop_loss"],
            "take_profit": proposal["take_profit"]
        }

        fill = self.api.place_order(order)

        if fill:
            self.position_manager.on_fill({
                "symbol": proposal["symbol"],
                "price": fill["price"],
                "size": proposal["size"],
                "direction": proposal["direction"],
                "stop_loss": proposal["stop_loss"],
                "take_profit": proposal["take_profit"]
            })

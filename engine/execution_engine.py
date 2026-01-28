from engine.position_manager import PositionManager
from execution.execution_optimizer import ExecutionOptimizer

class ExecutionEngine:
    def __init__(self, api_client):
        self.api = api_client
        self.position_manager = PositionManager(api_client)
        self.optimizer = ExecutionOptimizer()

    def execute(self, proposal, market_state):
        order = {
            "symbol": proposal["symbol"],
            "side": "buy" if proposal["direction"] == "LONG" else "sell",
            "size": proposal["size"],
        }

        fill = self.optimizer.execute_order(self.api, order, market_state)

        if fill:
            self.position_manager.on_fill({
                "symbol": proposal["symbol"],
                "price": fill["price"],
                "size": proposal["size"],
                "direction": proposal["direction"],
                "stop_loss": proposal["stop_loss"],
                "take_profit": proposal["take_profit"]
            })

import time
import math
from execution.smart_order_router import SmartOrderRouter

class ExecutionOptimizer:
    def __init__(self):
        self.base_duration = 20
        self.min_slice_size = 0.001
        self.router = SmartOrderRouter()

    def execute_order(self, api, order, market_state):
        total_size = order["size"]
        symbol = order["symbol"]
        side = order["side"]

        slices = max(1, int(math.sqrt(total_size) * 3))
        slice_size = total_size / slices

        if slice_size < self.min_slice_size:
            slices = max(1, int(total_size / self.min_slice_size))
            slice_size = total_size / slices

        delay = self.base_duration / slices

        print(f"🧩 TWAP execution: {slices} slices | {slice_size:.4f} each")

        fills = []
        for i in range(slices):
            order_type = self.router.choose_order_type(market_state)

            slice_order = {
                "symbol": symbol,
                "side": side,
                "size": slice_size,
                "type": order_type
            }

            fill = api.place_order(slice_order)
            if fill:
                fills.append(fill)

            time.sleep(delay)

        if fills:
            avg_price = sum(f["price"] for f in fills) / len(fills)
            return {"price": avg_price}

        return None

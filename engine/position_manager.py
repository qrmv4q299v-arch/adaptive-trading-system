from risk.trailing_stop_model import TrailingStopModel

class PositionManager:
    def __init__(self, api_client):
        self.api = api_client
        self.trailing_model = TrailingStopModel()
        self.positions = {}  # symbol -> position dict

    def on_fill(self, fill):
        symbol = fill["symbol"]
        self.positions[symbol] = {
            "entry_price": fill["price"],
            "size": fill["size"],
            "direction": fill["direction"],
            "stop_loss": fill.get("stop_loss"),
            "take_profit": fill.get("take_profit"),
            "trailing_active": False
        }

    def update_market_price(self, symbol, price, regime):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]

        if not pos["trailing_active"]:
            if self.trailing_model.should_activate(
                pos["entry_price"], price, pos["direction"], regime
            ):
                pos["trailing_active"] = True

        if pos["trailing_active"]:
            new_sl = self.trailing_model.new_stop(
                pos["entry_price"], price, pos["direction"], regime
            )

            # Only move stop in favorable direction
            if pos["direction"] == "LONG":
                if new_sl > pos["stop_loss"]:
                    pos["stop_loss"] = new_sl
                    self.api.modify_stop(symbol, new_sl)
            else:
                if new_sl < pos["stop_loss"]:
                    pos["stop_loss"] = new_sl
                    self.api.modify_stop(symbol, new_sl)

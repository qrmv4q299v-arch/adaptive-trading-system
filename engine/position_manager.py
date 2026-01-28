from risk.trailing_stop_model import TrailingStopModel

class PositionManager:
    def __init__(self, api_client):
        self.api = api_client
        self.trailing_model = TrailingStopModel()
        self.positions = {}

    def on_fill(self, fill):
        symbol = fill["symbol"]
        self.positions[symbol] = {
            "entry_price": fill["price"],
            "size": fill["size"],
            "direction": fill["direction"],
            "stop_loss": fill.get("stop_loss"),
            "take_profit": fill.get("take_profit"),
            "break_even_set": False,
            "trailing_active": False
        }

    def update_market_price(self, symbol, price, regime):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        entry = pos["entry_price"]
        direction = pos["direction"]

        # ---- BREAK EVEN JUMP ----
        if not pos["break_even_set"]:
            if self.trailing_model.should_move_to_break_even(entry, price, direction, regime):
                be_price = self.trailing_model.break_even_price(entry, direction)

                if direction == "LONG" and be_price > pos["stop_loss"]:
                    pos["stop_loss"] = be_price
                    pos["break_even_set"] = True
                    self.api.modify_stop(symbol, be_price)

                elif direction == "SHORT" and be_price < pos["stop_loss"]:
                    pos["stop_loss"] = be_price
                    pos["break_even_set"] = True
                    self.api.modify_stop(symbol, be_price)

        # ---- TRAILING ACTIVATION ----
        if not pos["trailing_active"]:
            if self.trailing_model.should_activate_trailing(entry, price, direction, regime):
                pos["trailing_active"] = True

        # ---- TRAILING STOP UPDATES ----
        if pos["trailing_active"]:
            new_sl = self.trailing_model.new_trailing_stop(price, direction, regime)

            if direction == "LONG" and new_sl > pos["stop_loss"]:
                pos["stop_loss"] = new_sl
                self.api.modify_stop(symbol, new_sl)

            elif direction == "SHORT" and new_sl < pos["stop_loss"]:
                pos["stop_loss"] = new_sl
                self.api.modify_stop(symbol, new_sl)

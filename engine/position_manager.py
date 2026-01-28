import time
from risk.trailing_stop_model import TrailingStopModel
from risk.position_exit_model import PositionExitModel
from risk.time_stop_model import TimeStopModel

class PositionManager:
    def __init__(self, api_client):
        self.api = api_client
        self.trailing_model = TrailingStopModel()
        self.exit_model = PositionExitModel()
        self.time_model = TimeStopModel()
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
            "trailing_active": False,
            "tp1_hit": False,
            "entry_time": time.time()
        }

    def update_market_price(self, symbol, price, regime):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        entry = pos["entry_price"]
        direction = pos["direction"]

        # ---- TIME STOP ----
        if self.time_model.should_time_exit(entry, price, pos["entry_time"], regime):
            print(f"⏳ Time stop exit on {symbol}")
            self.api.close_partial(symbol, pos["size"])
            del self.positions[symbol]
            return

        # ---- PARTIAL TAKE PROFIT ----
        if not pos["tp1_hit"]:
            tp1 = self.exit_model.tp1_price(entry, direction, regime)

            if (direction == "LONG" and price >= tp1) or \
               (direction == "SHORT" and price <= tp1):

                close_size = pos["size"] * self.exit_model.partial_close_fraction
                self.api.close_partial(symbol, close_size)
                pos["size"] -= close_size
                pos["tp1_hit"] = True

                print(f"💰 TP1 hit on {symbol}, closed {close_size}")

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

        # ---- TRAILING STOP ----
        if pos["trailing_active"]:
            new_sl = self.trailing_model.new_trailing_stop(price, direction, regime)

            if direction == "LONG" and new_sl > pos["stop_loss"]:
                pos["stop_loss"] = new_sl
                self.api.modify_stop(symbol, new_sl)

            elif direction == "SHORT" and new_sl < pos["stop_loss"]:
                pos["stop_loss"] = new_sl
                self.api.modify_stop(symbol, new_sl)

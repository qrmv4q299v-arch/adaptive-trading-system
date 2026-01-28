class TrailingStopModel:
    def __init__(self):
        # Move required before break-even trigger
        self.break_even_trigger = {
            "TREND": 0.008,
            "CHOP": 0.004,
            "CRASH": 0.006,
            "NEUTRAL": 0.005
        }

        # Move required before trailing activates
        self.activation_move = {
            "TREND": 0.015,
            "CHOP": 0.007,
            "CRASH": 0.01,
            "NEUTRAL": 0.012
        }

        self.trailing_distance = {
            "TREND": 0.01,
            "CHOP": 0.004,
            "CRASH": 0.007,
            "NEUTRAL": 0.006
        }

    def should_move_to_break_even(self, entry_price, current_price, direction, regime):
        move_pct = abs(current_price - entry_price) / entry_price
        return move_pct >= self.break_even_trigger.get(regime, 0.005)

    def should_activate_trailing(self, entry_price, current_price, direction, regime):
        move_pct = abs(current_price - entry_price) / entry_price
        return move_pct >= self.activation_move.get(regime, 0.01)

    def break_even_price(self, entry_price, direction):
        return entry_price  # could add fee buffer later

    def new_trailing_stop(self, current_price, direction, regime):
        dist = self.trailing_distance.get(regime, 0.006)
        if direction == "LONG":
            return current_price * (1 - dist)
        else:
            return current_price * (1 + dist)

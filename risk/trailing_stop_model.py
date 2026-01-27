class TrailingStopModel:
    def __init__(self):
        # % move required before trailing activates
        self.activation_move = {
            "TREND": 0.01,
            "CHOP": 0.005,
            "CRASH": 0.008,
            "NEUTRAL": 0.007
        }

        # How tight trailing becomes after activation
        self.trailing_distance = {
            "TREND": 0.008,   # give trends room
            "CHOP": 0.004,    # tight, lock gains fast
            "CRASH": 0.006,
            "NEUTRAL": 0.005
        }

    def should_activate(self, entry_price, current_price, direction, regime):
        move_pct = abs(current_price - entry_price) / entry_price
        return move_pct >= self.activation_move.get(regime, 0.007)

    def new_stop(self, entry_price, current_price, direction, regime):
        dist = self.trailing_distance.get(regime, 0.005)

        if direction == "LONG":
            return current_price * (1 - dist)
        else:
            return current_price * (1 + dist)

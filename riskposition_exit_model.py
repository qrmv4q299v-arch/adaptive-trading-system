class PositionExitModel:
    def __init__(self):
        # Portion to close at TP1
        self.partial_close_fraction = 0.5

        # TP1 distance by regime
        self.tp1_distance = {
            "TREND": 0.02,
            "CHOP": 0.01,
            "CRASH": 0.015,
            "NEUTRAL": 0.015
        }

    def tp1_price(self, entry_price, direction, regime):
        dist = self.tp1_distance.get(regime, 0.015)
        if direction == "LONG":
            return entry_price * (1 + dist)
        else:
            return entry_price * (1 - dist)

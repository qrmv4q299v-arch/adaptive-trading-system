class StopModel:
    def __init__(self):
        # Base stop distances as % of price
        self.base_stop_pct = {
            "TREND": 0.015,     # wider stops, let trends breathe
            "CHOP": 0.007,      # tight stops, avoid chop bleed
            "CRASH": 0.01,      # defensive but not too tight
            "NEUTRAL": 0.012
        }

        self.risk_reward_ratio = {
            "TREND": 2.5,
            "CHOP": 1.2,
            "CRASH": 1.5,
            "NEUTRAL": 2.0
        }

    def compute_stops(self, price: float, direction: str, regime: str, vol_multiplier: float):
        stop_pct = self.base_stop_pct.get(regime, 0.012)

        # Widen stops slightly in high volatility
        stop_pct *= (1 + (vol_multiplier - 1) * 0.5)

        rr = self.risk_reward_ratio.get(regime, 2.0)

        if direction == "LONG":
            stop_loss = price * (1 - stop_pct)
            take_profit = price * (1 + stop_pct * rr)
        else:
            stop_loss = price * (1 + stop_pct)
            take_profit = price * (1 - stop_pct * rr)

        return stop_loss, take_profit

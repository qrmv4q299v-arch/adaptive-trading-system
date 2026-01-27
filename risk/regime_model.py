import numpy as np

class RegimeModel:
    def __init__(self):
        self.prices = []
        self.window = 50

        self.current_regime = "NEUTRAL"

    def update(self, price):
        self.prices.append(price)
        if len(self.prices) > self.window:
            self.prices.pop(0)

        self.detect_regime()

    def detect_regime(self):
        if len(self.prices) < 20:
            return

        prices = np.array(self.prices)
        returns = np.diff(prices) / prices[:-1]

        volatility = np.std(returns)
        trend_strength = abs(prices[-1] - prices[0]) / prices[0]

        # --- REGIME RULES ---
        if volatility > 0.05 and prices[-1] < np.mean(prices):
            self.current_regime = "CRASH"
        elif trend_strength > 0.03:
            self.current_regime = "TREND"
        elif volatility < 0.01:
            self.current_regime = "CHOP"
        else:
            self.current_regime = "NEUTRAL"

    def get_regime(self):
        return self.current_regime

    def risk_multiplier(self):
        if self.current_regime == "TREND":
            return 1.2
        elif self.current_regime == "CHOP":
            return 0.7
        elif self.current_regime == "CRASH":
            return 0.4
        return 1.0

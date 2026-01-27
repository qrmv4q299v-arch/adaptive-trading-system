class VolatilityModel:
    def __init__(self):
        self.volatility = 0.0
        self.low_vol_threshold = 0.01
        self.high_vol_threshold = 0.05

    def update(self, market_data):
        """
        market_data expected format:
        {
            "returns": [list of recent returns]
        }
        """
        returns = market_data.get("returns", [])
        if len(returns) < 2:
            return

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        self.volatility = variance ** 0.5

    def risk_multiplier(self):
        """
        Returns a size multiplier based on volatility.
        """
        if self.volatility >= self.high_vol_threshold:
            return 0.4  # heavy reduction
        elif self.volatility >= self.low_vol_threshold:
            return 0.7  # moderate reduction
        return 1.0

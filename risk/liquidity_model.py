class LiquidityModel:
    def __init__(self):
        # Estimated notional liquidity per symbol (can later be real order book depth)
        self.liquidity_estimates = {
            "BTC-PERP": 10_000_000,
            "ETH-PERP": 5_000_000,
            "SOL-PERP": 1_500_000
        }

        self.max_participation_rate = 0.02  # Max % of liquidity per trade

    def liquidity_multiplier(self, symbol, proposed_size, price):
        notional = proposed_size * price
        liquidity = self.liquidity_estimates.get(symbol, 1_000_000)

        max_allowed = liquidity * self.max_participation_rate

        if notional <= max_allowed:
            return 1.0

        return max_allowed / notional

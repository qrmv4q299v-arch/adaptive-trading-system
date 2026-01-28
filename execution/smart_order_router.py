class SmartOrderRouter:
    def __init__(self):
        self.max_passive_spread = 0.0005   # 0.05%
        self.high_volatility_threshold = 0.02

    def choose_order_type(self, market_state):
        spread = market_state.get("spread", 0.0004)
        volatility = market_state.get("volatility", 0.01)
        urgency = market_state.get("urgency", "normal")

        if urgency == "high":
            return "MARKET"

        if volatility > self.high_volatility_threshold:
            return "MARKET"

        if spread < self.max_passive_spread:
            return "LIMIT_PASSIVE"

        return "LIMIT_AGGRESSIVE"

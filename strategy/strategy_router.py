class StrategyRouter:
    def __init__(self):
        self.regime_rules = {
            "TREND": ["trend_following", "breakout"],
            "CHOP": ["mean_reversion"],
            "CRASH": ["hedge", "mean_reversion_small"],
            "NEUTRAL": ["trend_following", "mean_reversion"]
        }

    def is_strategy_allowed(self, strategy_name: str, regime: str) -> bool:
        allowed = self.regime_rules.get(regime, [])
        return strategy_name in allowed

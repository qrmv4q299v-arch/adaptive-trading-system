from analytics.performance_tracker import PerformanceTracker

class AdaptiveAllocator:
    def __init__(self):
        self.tracker = PerformanceTracker()
        self.disabled_strategies = {}

    def adjust_size(self, strategy_name, base_size):
        health = self.tracker.get_health(strategy_name)

        if health == "DISABLED":
            return 0, 0.0, health

        score = self.tracker.get_score(strategy_name)

        if health == "WEAK":
            score *= 0.5

        adjusted = base_size * score
        return adjusted, score, health

    def record_result(self, strategy_name, pnl):
        self.tracker.record_trade(strategy_name, pnl)

from analytics.performance_tracker import PerformanceTracker

class AdaptiveAllocator:
    def __init__(self):
        self.tracker = PerformanceTracker()

    def adjust_size(self, strategy_name, base_size):
        score = self.tracker.get_score(strategy_name)
        adjusted = base_size * score
        return adjusted, score

    def record_result(self, strategy_name, pnl):
        self.tracker.record_trade(strategy_name, pnl)

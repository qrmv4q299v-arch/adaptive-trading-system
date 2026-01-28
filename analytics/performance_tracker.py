class PerformanceTracker:
    def __init__(self):
        self.stats = {}

    def record_trade(self, strategy, pnl):
        if strategy not in self.stats:
            self.stats[strategy] = {
                "trades": 0,
                "wins": 0,
                "pnl": 0.0
            }

        s = self.stats[strategy]
        s["trades"] += 1
        s["pnl"] += pnl
        if pnl > 0:
            s["wins"] += 1

    def get_score(self, strategy):
        s = self.stats.get(strategy)
        if not s or s["trades"] < 5:
            return 1.0  # Neutral weight until enough data

        win_rate = s["wins"] / s["trades"]
        avg_pnl = s["pnl"] / s["trades"]

        return max(0.5, min(1.5, win_rate + avg_pnl))

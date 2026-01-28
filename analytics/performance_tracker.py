class PerformanceTracker:
    def __init__(self):
        self.stats = {}

    def record_trade(self, strategy, pnl):
        if strategy not in self.stats:
            self.stats[strategy] = {
                "trades": 0,
                "wins": 0,
                "pnl": 0.0,
                "peak_pnl": 0.0,
                "drawdown": 0.0
            }

        s = self.stats[strategy]
        s["trades"] += 1
        s["pnl"] += pnl
        s["peak_pnl"] = max(s["peak_pnl"], s["pnl"])
        s["drawdown"] = s["peak_pnl"] - s["pnl"]

        if pnl > 0:
            s["wins"] += 1

    def get_score(self, strategy):
        s = self.stats.get(strategy)
        if not s or s["trades"] < 5:
            return 1.0

        win_rate = s["wins"] / s["trades"]
        avg_pnl = s["pnl"] / s["trades"]

        return max(0.5, min(1.5, win_rate + avg_pnl))

    def get_health(self, strategy):
        s = self.stats.get(strategy)
        if not s or s["trades"] < 10:
            return "HEALTHY"

        win_rate = s["wins"] / s["trades"]
        dd = s["drawdown"]

        if dd > 5 or win_rate < 0.35:
            return "DISABLED"
        if win_rate < 0.45:
            return "WEAK"
        return "HEALTHY"

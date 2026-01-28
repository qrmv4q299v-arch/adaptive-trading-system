from collections import deque
from typing import Dict


class PerformanceTracker:
    def __init__(self, recent_window: int = 30):
        self.stats: Dict[str, dict] = {}
        self.recent_window = recent_window

    def record_trade(self, strategy: str, pnl: float):
        if strategy not in self.stats:
            self.stats[strategy] = {
                "trades": 0,
                "wins": 0,
                "pnl": 0.0,
                "peak_pnl": 0.0,
                "drawdown": 0.0,
                "recent": deque(maxlen=self.recent_window),  # store last N pnls
            }

        s = self.stats[strategy]
        s["trades"] += 1
        s["pnl"] += pnl
        s["peak_pnl"] = max(s["peak_pnl"], s["pnl"])
        s["drawdown"] = s["peak_pnl"] - s["pnl"]

        if pnl > 0:
            s["wins"] += 1

        s["recent"].append(pnl)

    def get_score(self, strategy: str) -> float:
        """
        Score in [0.5..1.5] using:
          - global win_rate
          - recent average pnl
        """
        s = self.stats.get(strategy)
        if not s or s["trades"] < 5:
            return 1.0

        win_rate = s["wins"] / s["trades"]
        recent = list(s["recent"])
        recent_avg = sum(recent) / len(recent) if recent else 0.0

        # Basic blending: win_rate contributes most, recent_avg nudges it
        # (Keep it conservative for now.)
        raw = win_rate + (recent_avg * 0.05)  # scale down pnl effect
        return max(0.5, min(1.5, raw))

    def get_health(self, strategy: str) -> str:
        """
        HEALTHY / WEAK / DISABLED based on:
          - drawdown
          - win rate
          - recent window collapse
        """
        s = self.stats.get(strategy)
        if not s or s["trades"] < 10:
            return "HEALTHY"

        win_rate = s["wins"] / s["trades"]
        dd = s["drawdown"]

        recent = list(s["recent"])
        recent_wins = sum(1 for x in recent if x > 0)
        recent_wr = (recent_wins / len(recent)) if recent else 1.0

        # Hard disable conditions
        if dd > 5 or win_rate < 0.35 or recent_wr < 0.30:
            return "DISABLED"

        # Weak conditions
        if win_rate < 0.45 or recent_wr < 0.40:
            return "WEAK"

        return "HEALTHY"

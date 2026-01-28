from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# We reuse your tracker/allocator logic
from analytics.performance_tracker import PerformanceTracker


@dataclass(frozen=True)
class StrategyCandidate:
    name: str
    base_priority: float = 1.0  # your manual preference per regime


class MetaStrategyManager:
    """
    Meta-layer that selects which strategy to run given the current regime,
    while respecting:
      - frozen strategy logic (this only selects, does not modify entries)
      - performance health (disable/avoid bad strategies)
    """

    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker

        # Regime → ordered strategy candidates (you can expand later)
        self.regime_playbook: Dict[str, List[StrategyCandidate]] = {
            "TREND_UP": [
                StrategyCandidate("trend_following", 1.20),
                StrategyCandidate("trend_continuation", 1.10),
                StrategyCandidate("mean_reversion", 0.70),
            ],
            "TREND_DOWN": [
                StrategyCandidate("trend_following", 1.10),
                StrategyCandidate("trend_continuation", 1.00),
                StrategyCandidate("mean_reversion", 0.75),
            ],
            "BALANCED": [
                StrategyCandidate("mean_reversion", 1.15),
                StrategyCandidate("trend_continuation", 1.00),
                StrategyCandidate("trend_following", 0.90),
            ],
            "HIGH_VOLATILITY": [
                # In high vol we prefer either ultra-selective MR or stand down
                StrategyCandidate("mean_reversion", 1.00),
                StrategyCandidate("trend_following", 0.80),
            ],
            "TRANSITION": [
                # Transition is dangerous → conservative ordering
                StrategyCandidate("mean_reversion", 0.90),
                StrategyCandidate("trend_continuation", 0.85),
            ],
        }

        # When regime is very risky, we can force "no-trade" if all are weak/disabled
        self.allow_no_trade: bool = True

    def rank_strategies(self, regime: str) -> List[Tuple[str, float, str]]:
        """
        Returns list of (strategy_name, meta_score, health) sorted by meta_score desc.
        meta_score combines:
          - base_priority (manual regime preference)
          - tracker.get_score() (data-driven)
        and penalizes WEAK, blocks DISABLED.
        """
        candidates = self.regime_playbook.get(regime, [])
        ranked: List[Tuple[str, float, str]] = []

        for c in candidates:
            health = self.tracker.get_health(c.name)
            if health == "DISABLED":
                continue

            perf_score = self.tracker.get_score(c.name)  # 0.5..1.5 (from your tracker)
            meta_score = c.base_priority * perf_score

            if health == "WEAK":
                meta_score *= 0.5  # conservative

            ranked.append((c.name, meta_score, health))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def pick_strategy(self, regime: str) -> Optional[str]:
        """
        Picks the best strategy for the regime.
        Returns None if no safe strategy exists.
        """
        ranked = self.rank_strategies(regime)
        if not ranked:
            return None if self.allow_no_trade else (self.regime_playbook.get(regime, [None])[0].name if self.regime_playbook.get(regime) else None)

        best_name, best_score, best_health = ranked[0]
        return best_name

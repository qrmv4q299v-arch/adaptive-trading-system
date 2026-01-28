# portfolio/portfolio_state.py
from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Dict, Any


@dataclass
class PortfolioState:
    timestamp: float = field(default_factory=lambda: float(time()))
    positions: Dict[str, Any] = field(default_factory=dict)
    balances: Dict[str, Any] = field(default_factory=dict)
    pnl: Dict[str, float] = field(default_factory=lambda: {"realized": 0.0, "unrealized": 0.0})
    exposure_usd: float = 0.0
    api_failure_streak: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "positions": self.positions,
            "balances": self.balances,
            "pnl": self.pnl,
            "exposure_usd": self.exposure_usd,
            "api_failure_streak": self.api_failure_streak,
        }
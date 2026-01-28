# engine/position_manager.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ManagedPosition:
    symbol: str
    direction: str
    size: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_ts: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


class PositionManager:
    """
    v1:
    - This module should NOT invent fills.
    - Positions should come from PortfolioState updated from exchange snapshots.
    - Keep PositionManager for exit logic later; for now it is a thin holder.
    """

    def __init__(self):
        self.positions: Dict[str, ManagedPosition] = {}

    def sync_from_portfolio(self, portfolio_positions: Dict[str, Dict[str, Any]]) -> None:
        new: Dict[str, ManagedPosition] = {}
        for sym, p in portfolio_positions.items():
            try:
                new[sym] = ManagedPosition(
                    symbol=sym,
                    direction=str(p["direction"]),
                    size=float(p["size"]),
                    entry_price=float(p["entry_price"]),
                )
            except Exception:
                continue
        self.positions = new

    def get(self, symbol: str) -> Optional[ManagedPosition]:
        return self.positions.get(symbol)

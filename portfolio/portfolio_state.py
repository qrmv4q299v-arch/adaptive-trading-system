# portfolio/portfolio_state.py
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    size: float
    direction: str  # LONG/SHORT
    entry_price: float


@dataclass
class PortfolioState:
    """
    v1: minimal, but real.
    - updated from exchange account snapshots (truth)
    - can be used by risk brain / router (read-only)
    """
    positions: Dict[str, Position] = field(default_factory=dict)
    last_account_snapshot: Dict[str, Any] = field(default_factory=dict)
    last_pnl_snapshot: Dict[str, Any] = field(default_factory=dict)

    def update_from_account_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.last_account_snapshot = snapshot or {}

        # Best-effort extraction: positions could be under different keys per SDK
        raw_positions = (
            snapshot.get("positions")
            or snapshot.get("open_positions")
            or snapshot.get("account_positions")
            or snapshot.get("raw", {}).get("positions")
            or []
        )

        new_positions: Dict[str, Position] = {}
        if isinstance(raw_positions, list):
            for p in raw_positions:
                if not isinstance(p, dict):
                    continue
                symbol = str(p.get("symbol") or p.get("ticker") or "")
                if not symbol:
                    continue
                size = float(p.get("size") or p.get("position_size") or 0.0)
                if size == 0:
                    continue
                entry = float(p.get("entry_price") or p.get("avg_entry_price") or 0.0)
                direction = "LONG" if size > 0 else "SHORT"
                new_positions[symbol] = Position(symbol=symbol, size=abs(size), direction=direction, entry_price=entry)

        self.positions = new_positions

    def update_from_pnl_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.last_pnl_snapshot = snapshot or {}

    def open_positions(self) -> Dict[str, Dict[str, Any]]:
        return {
            s: {"symbol": p.symbol, "size": p.size, "direction": p.direction, "entry_price": p.entry_price}
            for s, p in self.positions.items()
        }

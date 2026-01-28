# engine/position_manager.py
from __future__ import annotations

from typing import Any, Dict
from time import time

from engine.api_client import LighterApiClient


class PositionManager:
    """
    v1: provides a minimal portfolio_state dict for RiskBrain.
    Later: use AccountApi.account() + pnl() in real Lighter mode.
    """

    def __init__(self, client: LighterApiClient) -> None:
        self.client = client

    async def sync(self) -> Dict[str, Any]:
        # DRY_RUN: just return a minimal state
        return {
            "timestamp": float(time()),
            "positions": {},
            "balances": {},
            "pnl": {"realized": 0.0, "unrealized": 0.0},
            "exposure_usd": 0.0,
            "api_failure_streak": 0,
            "kill_switch": False,
        }
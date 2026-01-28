# engine/order_reconciliation.py
from __future__ import annotations

from typing import Any, Dict, Optional
from engine.api_client import LighterApiClient


class OrderReconciler:
    """
    v1: placeholder reconciliation loop.
    Later: poll order status and update tracker/portfolio.
    """

    def __init__(self, client: LighterApiClient) -> None:
        self.client = client
        self.last_status: Dict[str, Any] = {}

    async def sync_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        status = await self.client.get_order_status(symbol, order_id)
        self.last_status[order_id] = status
        return status

    async def sync(self) -> None:
        # no-op by default (needs tracker integration)
        return
# engine/order_reconciliation.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any, List

from engine.api_client import LighterApiClient

logger = logging.getLogger(__name__)


class OrderState(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    STUCK = "STUCK"
    UNKNOWN = "UNKNOWN"


@dataclass
class TrackedOrder:
    proposal_id: str
    symbol: str
    client_order_id: str
    order_id: Optional[str] = None
    state: OrderState = OrderState.PENDING
    last_status: str = "UNKNOWN"
    filled_size: float = 0.0
    avg_price: float = 0.0
    last_update_ts: float = 0.0


class OrderReconciler:
    """
    Poll-based reconciliation (safe v1).
    - Never resubmits orders.
    - Only updates state based on exchange truth.
    """

    def __init__(self, api: LighterApiClient, poll_interval: float = 2.0, stuck_after_sec: float = 30.0):
        self.api = api
        self.poll_interval = poll_interval
        self.stuck_after_sec = stuck_after_sec
        self._orders: Dict[str, TrackedOrder] = {}
        self._lock = asyncio.Lock()

    async def track_submitted(self, proposal_id: str, symbol: str, client_order_id: str, order_id: str) -> None:
        async with self._lock:
            self._orders[proposal_id] = TrackedOrder(
                proposal_id=proposal_id,
                symbol=symbol,
                client_order_id=client_order_id,
                order_id=order_id,
                state=OrderState.SUBMITTED,
            )

    async def get(self, proposal_id: str) -> Optional[TrackedOrder]:
        async with self._lock:
            return self._orders.get(proposal_id)

    async def all(self) -> List[TrackedOrder]:
        async with self._lock:
            return list(self._orders.values())

    async def reconcile_once(self, now_ts: float) -> None:
        orders = await self.all()
        for t in orders:
            try:
                raw = await self.api.get_order_by_client_id(t.client_order_id)
                if not raw:
                    continue

                status = str(raw.get("status", "UNKNOWN")).upper()
                filled = abs(float(raw.get("filled_size", 0.0) or 0.0))
                avg = float(raw.get("avg_price", 0.0) or 0.0)

                new_state = self._map_status(status, filled)

                async with self._lock:
                    cur = self._orders.get(t.proposal_id)
                    if not cur:
                        continue
                    cur.last_status = status
                    cur.filled_size = filled
                    cur.avg_price = avg
                    cur.last_update_ts = now_ts
                    cur.order_id = cur.order_id or raw.get("order_id")

                    # stuck detection for SUBMITTED/PARTIAL only
                    if cur.state in (OrderState.SUBMITTED, OrderState.PARTIAL) and (now_ts - cur.last_update_ts) > self.stuck_after_sec:
                        cur.state = OrderState.STUCK
                    else:
                        cur.state = new_state

            except Exception as e:
                logger.warning("Reconcile error for %s: %s", t.proposal_id, e)

    async def run_forever(self, clock_fn, kill_event: asyncio.Event) -> None:
        while not kill_event.is_set():
            now_ts = float(clock_fn())
            await self.reconcile_once(now_ts)
            await asyncio.sleep(self.poll_interval)

    @staticmethod
    def _map_status(status: str, filled: float) -> OrderState:
        s = status.upper()
        if "CANCEL" in s:
            return OrderState.CANCELLED
        if "REJECT" in s:
            return OrderState.REJECTED
        if "FILL" in s:
            return OrderState.FILLED
        if "PART" in s:
            return OrderState.PARTIAL
        # If exchange doesn't say partial but filled_size>0, treat as PARTIAL
        if filled > 0:
            return OrderState.PARTIAL
        if s in ("OPEN", "NEW", "PENDING", "LIVE", "WORKING"):
            return OrderState.SUBMITTED
        return OrderState.UNKNOWN

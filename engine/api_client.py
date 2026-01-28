# engine/api_client.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional


class APIError(Exception):
    pass


@dataclass
class OrderResult:
    order_id: str
    status: str
    filled_size: float
    avg_price: float
    raw: Dict[str, Any]


class LighterApiClient:
    """
    Safe wrapper skeleton.
    For now: supports DRY_RUN mode.
    Later: replace internals with real Lighter SDK calls.
    """

    def __init__(
        self,
        key: str = "",
        secret: str = "",
        account_index: int = 0,
        api_key_index: int = 0,
        base_url: str = "",
        dry_run: bool = True,
    ) -> None:
        self.key = key
        self.secret = secret
        self.account_index = account_index
        self.api_key_index = api_key_index
        self.base_url = base_url
        self.dry_run = dry_run

        self._init_lock = asyncio.Lock()
        self._initialized = False

        self._sdk = None  # real SDK later

    async def init(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return

            if self.dry_run:
                self._initialized = True
                return

            # TODO: real init with Lighter SDK
            # from lighter_sdk.lighter import Lighter
            # self._sdk = Lighter(...)
            # await self._sdk.init_client()
            raise APIError("Live init not implemented yet. Set DRY_RUN=1 for now.")

    async def create_market_order(self, symbol: str, amount: float, client_order_id: str) -> OrderResult:
        await self.init()

        if self.dry_run:
            # simulate immediate fill
            raw = {
                "order_id": f"DRY_{client_order_id}",
                "status": "FILLED",
                "filled_size": abs(float(amount)),
                "avg_price": 100.0,
            }
            return OrderResult(
                order_id=raw["order_id"],
                status=raw["status"],
                filled_size=float(raw["filled_size"]),
                avg_price=float(raw["avg_price"]),
                raw=raw,
            )

        raise APIError("Live market order not implemented yet.")

    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        await self.init()
        if self.dry_run:
            return {"order_id": order_id, "status": "FILLED"}
        raise APIError("Live get_order_status not implemented yet.")

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        await self.init()
        if self.dry_run:
            return {"order_id": order_id, "status": "CANCELLED"}
        raise APIError("Live cancel_order not implemented yet.")
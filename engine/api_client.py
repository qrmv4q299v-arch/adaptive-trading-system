# engine/api_client.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


class APIError(Exception):
    pass


@dataclass(frozen=True)
class LighterConfig:
    key: str
    secret: str
    account_index: int
    api_key_index: int
    base_url: str


class LighterApiClient:
    """
    Async-safe wrapper over Lighter SDK.

    Goals:
    - Serialized init (no races)
    - Defensive API calls (schema checks)
    - Provide minimal primitives needed by execution/reconciliation:
        - market_order()
        - cancel_order()
        - get_order_by_client_id()
        - get_open_orders()
        - get_inactive_orders()
        - get_account_state()
        - get_pnl()
    """

    def __init__(self, cfg: LighterConfig):
        self.cfg = cfg
        self._client = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def init(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return

            # Try common SDK entrypoints. You may need to adjust imports to match your installed package.
            try:
                from lighter_sdk.lighter import Lighter  # type: ignore
            except Exception:
                try:
                    from lighter.lighter import Lighter  # type: ignore
                except Exception as e:
                    raise APIError(
                        "Cannot import Lighter SDK. Install/verify package name (lighter-sdk / lighter-python)."
                    ) from e

            try:
                self._client = Lighter(
                    key=self.cfg.key,
                    secret=self.cfg.secret,
                    account_index=self.cfg.account_index,
                    api_key_index=self.cfg.api_key_index,
                    url=self.cfg.base_url,
                )
                # Some SDKs require async init_client()
                init_fn = getattr(self._client, "init_client", None)
                if callable(init_fn):
                    maybe = init_fn()
                    if asyncio.iscoroutine(maybe):
                        await maybe

                self._initialized = True
                logger.info("Lighter API client initialized")
            except Exception as e:
                logger.exception("Failed to initialize Lighter client")
                raise APIError(f"Client initialization failed: {e}") from e

    def _require(self) -> Any:
        if not self._initialized or self._client is None:
            raise APIError("Client not initialized. Call await client.init() first.")
        return self._client

    # -----------------------------
    # Orders
    # -----------------------------

    async def market_order(self, symbol: str, amount: float, client_order_id: str) -> Dict[str, Any]:
        """
        amount: + for LONG, - for SHORT
        """
        await self.init()
        c = self._require()
        try:
            fn = getattr(c, "market_order", None)
            if not callable(fn):
                # fallback: some SDKs use OrderApi
                order_api = getattr(c, "order_api", None) or getattr(c, "OrderApi", None)
                if order_api and hasattr(order_api, "market_order"):
                    fn = order_api.market_order
                else:
                    raise APIError("SDK missing market_order(). Map this method to your SDK.")

            resp = fn(ticker=symbol, amount=amount, client_order_id=client_order_id)
            if asyncio.iscoroutine(resp):
                resp = await resp

            order = self._extract_first_order(resp)
            self._validate_order_fields(order, required=("order_id", "status", "filled_size", "avg_price"))
            return order
        except Exception as e:
            logger.exception("market_order failed")
            raise APIError(f"market_order failed: {e}") from e

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        await self.init()
        c = self._require()
        try:
            fn = getattr(c, "cancel_order", None)
            if not callable(fn):
                order_api = getattr(c, "order_api", None) or getattr(c, "OrderApi", None)
                if order_api and hasattr(order_api, "cancel_order"):
                    fn = order_api.cancel_order
                else:
                    raise APIError("SDK missing cancel_order(). Map this method to your SDK.")

            resp = fn(ticker=symbol, order_id=order_id)
            if asyncio.iscoroutine(resp):
                resp = await resp
            return resp if isinstance(resp, dict) else {"raw": resp}
        except Exception as e:
            logger.exception("cancel_order failed")
            raise APIError(f"cancel_order failed: {e}") from e

    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Best-effort: returns list of open orders.
        """
        await self.init()
        c = self._require()
        try:
            # Common names in SDKs
            fn = getattr(c, "order_book_orders", None)
            if not callable(fn):
                order_api = getattr(c, "order_api", None) or getattr(c, "OrderApi", None)
                if order_api and hasattr(order_api, "order_book_orders"):
                    fn = order_api.order_book_orders
                else:
                    return []

            resp = fn(account_index=self.cfg.account_index)
            if asyncio.iscoroutine(resp):
                resp = await resp
            if isinstance(resp, dict) and "orders" in resp and isinstance(resp["orders"], list):
                return resp["orders"]
            if isinstance(resp, list):
                return resp
            return []
        except Exception:
            logger.exception("get_open_orders failed (returning empty)")
            return []

    async def get_inactive_orders(self) -> List[Dict[str, Any]]:
        """
        filled/cancelled history, best-effort.
        """
        await self.init()
        c = self._require()
        try:
            fn = getattr(c, "account_inactive_orders", None)
            if not callable(fn):
                order_api = getattr(c, "order_api", None) or getattr(c, "OrderApi", None)
                if order_api and hasattr(order_api, "account_inactive_orders"):
                    fn = order_api.account_inactive_orders
                else:
                    return []

            resp = fn(account_index=self.cfg.account_index)
            if asyncio.iscoroutine(resp):
                resp = await resp
            if isinstance(resp, dict) and "orders" in resp and isinstance(resp["orders"], list):
                return resp["orders"]
            if isinstance(resp, list):
                return resp
            return []
        except Exception:
            logger.exception("get_inactive_orders failed (returning empty)")
            return []

    async def get_order_by_client_id(self, client_order_id: str) -> Optional[Dict[str, Any]]:
        """
        Best-effort:
        - search open orders first
        - then inactive orders
        """
        open_orders = await self.get_open_orders()
        for o in open_orders:
            if str(o.get("client_order_id")) == str(client_order_id):
                return o
        inactive = await self.get_inactive_orders()
        for o in inactive:
            if str(o.get("client_order_id")) == str(client_order_id):
                return o
        return None

    # -----------------------------
    # Account / PnL
    # -----------------------------

    async def get_account_state(self) -> Dict[str, Any]:
        await self.init()
        c = self._require()
        try:
            fn = getattr(c, "account", None)
            if not callable(fn):
                account_api = getattr(c, "account_api", None) or getattr(c, "AccountApi", None)
                if account_api and hasattr(account_api, "account"):
                    fn = account_api.account
                else:
                    raise APIError("SDK missing account() / AccountApi.account(). Map this method to your SDK.")

            resp = fn(account_index=self.cfg.account_index)
            if asyncio.iscoroutine(resp):
                resp = await resp
            return resp if isinstance(resp, dict) else {"raw": resp}
        except Exception as e:
            logger.exception("get_account_state failed")
            raise APIError(f"get_account_state failed: {e}") from e

    async def get_pnl(self) -> Dict[str, Any]:
        await self.init()
        c = self._require()
        try:
            fn = getattr(c, "pnl", None)
            if not callable(fn):
                account_api = getattr(c, "account_api", None) or getattr(c, "AccountApi", None)
                if account_api and hasattr(account_api, "pnl"):
                    fn = account_api.pnl
                else:
                    return {}

            resp = fn(account_index=self.cfg.account_index)
            if asyncio.iscoroutine(resp):
                resp = await resp
            return resp if isinstance(resp, dict) else {"raw": resp}
        except Exception:
            logger.exception("get_pnl failed (returning empty)")
            return {}

    # -----------------------------
    # Helpers
    # -----------------------------

    @staticmethod
    def _extract_first_order(resp: Any) -> Dict[str, Any]:
        if isinstance(resp, dict) and "orders" in resp and isinstance(resp["orders"], list) and resp["orders"]:
            o = resp["orders"][0]
            return o if isinstance(o, dict) else {"raw": o}
        if isinstance(resp, dict):
            # some SDKs return a single order dict
            return resp
        raise APIError(f"Invalid order response: {resp}")

    @staticmethod
    def _validate_order_fields(order: Dict[str, Any], required: tuple[str, ...]) -> None:
        for f in required:
            if f not in order:
                raise APIError(f"Order missing required field '{f}': {order}")

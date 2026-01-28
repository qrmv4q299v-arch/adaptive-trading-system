# engine/execution_engine.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Callable, List, Tuple

from engine.api_client import LighterApiClient, APIError
from engine.order_reconciliation import OrderReconciler, OrderState
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain

logger = logging.getLogger(__name__)


# --------------------------
# Frozen contract (minimal)
# --------------------------

@dataclass(frozen=True)
class ExecutionProposal:
    proposal_id: str
    symbol: str
    direction: str  # LONG/SHORT
    size: float

    entry_price: float
    stop_loss: float
    take_profit: float

    # frozen tags (as strings to avoid import cycles)
    basket: str
    module: str
    htf_regime: str
    auction_context: Dict[str, Any]

    def validate(self) -> Tuple[bool, str]:
        if self.direction not in ("LONG", "SHORT"):
            return False, f"Invalid direction={self.direction}"
        if self.size <= 0:
            return False, f"Invalid size={self.size}"
        if not self.symbol:
            return False, "Missing symbol"
        if not self.proposal_id:
            return False, "Missing proposal_id"
        # frozen tags must exist
        if not self.basket or not self.module or not self.htf_regime:
            return False, "FROZEN_CONTRACT_VIOLATION: missing basket/module/htf_regime"
        if not isinstance(self.auction_context, dict):
            return False, "FROZEN_CONTRACT_VIOLATION: auction_context must be dict"
        return True, ""


# --------------------------
# Execution
# --------------------------

@dataclass
class ExecutionResult:
    proposal_id: str
    symbol: str
    client_order_id: str
    order_id: str
    status: str
    allocated_size: float
    executed_size: float
    executed_price: float
    allocation_multiplier: float
    ts: str
    frozen: Dict[str, Any]


class ExecutionEngine:
    """
    v1 execution:
    - idempotent client_order_id = proposal_id
    - strict allocation enforcement
    - exceptions contained; api failure streak reported to risk brain
    - reconciliation handled by OrderReconciler in parallel
    """

    def __init__(
        self,
        api: LighterApiClient,
        portfolio: PortfolioState,
        risk: RiskBrain,
        reconciler: OrderReconciler,
        store_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.api = api
        self.portfolio = portfolio
        self.risk = risk
        self.reconciler = reconciler
        self.store_fn = store_fn

    async def execute(self, proposal: ExecutionProposal, reference_price: float) -> Optional[ExecutionResult]:
        ok, err = proposal.validate()
        if not ok:
            logger.error("Proposal invalid: %s | %s", proposal.proposal_id, err)
            return None

        decision = self.risk.assess_proposal(proposal.symbol)
        if not decision.allow:
            logger.warning("Risk rejected proposal %s: %s", proposal.proposal_id, decision.reason)
            return None

        allocation_multiplier = decision.allocation_multiplier
        allocated_size = proposal.size * allocation_multiplier
        min_size = 1e-8
        if allocated_size < min_size:
            logger.warning("Skip tiny order %s size=%.2e", proposal.proposal_id, allocated_size)
            return None

        client_order_id = proposal.proposal_id
        amount = allocated_size if proposal.direction == "LONG" else -allocated_size

        try:
            order = await self.api.market_order(proposal.symbol, amount, client_order_id=client_order_id)
            self.risk.register_api_success()
        except APIError as e:
            logger.error("APIError execute %s: %s", proposal.proposal_id, e)
            self.risk.register_api_failure()
            return None
        except Exception as e:
            logger.exception("Unexpected execute error %s", proposal.proposal_id)
            self.risk.register_api_failure()
            return None

        order_id = str(order.get("order_id"))
        status = str(order.get("status", "UNKNOWN")).upper()
        executed_size = abs(float(order.get("filled_size", 0.0) or 0.0))
        executed_price = float(order.get("avg_price", reference_price) or reference_price)

        # Allocation enforcement
        tol = 0.01
        max_allowed = allocated_size * (1 + tol)
        if executed_size > max_allowed:
            logger.critical(
                "ALLOCATION_VIOLATION proposal=%s allocated=%.8f executed=%.8f",
                proposal.proposal_id, allocated_size, executed_size
            )
            # kill-switch v1: pause + cancel open orders only (no flatten)
            self.risk.state.kill_switch = True
            self.risk.state.risk_level = "CIRCUIT"
            try:
                await self.api.cancel_order(proposal.symbol, order_id)
            except Exception:
                pass
            return None

        # track + reconcile
        await self.reconciler.track_submitted(proposal.proposal_id, proposal.symbol, client_order_id, order_id)

        res = ExecutionResult(
            proposal_id=proposal.proposal_id,
            symbol=proposal.symbol,
            client_order_id=client_order_id,
            order_id=order_id,
            status=status,
            allocated_size=allocated_size,
            executed_size=executed_size,
            executed_price=executed_price,
            allocation_multiplier=allocation_multiplier,
            ts=datetime.utcnow().isoformat(),
            frozen={
                "basket": proposal.basket,
                "module": proposal.module,
                "htf_regime": proposal.htf_regime,
                "auction_context": proposal.auction_context,
            },
        )

        # optional store
        if self.store_fn:
            try:
                maybe = self.store_fn(res.__dict__)
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception:
                logger.exception("store_fn failed (non-fatal)")

        return res

# engine/execution_engine.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from core.contracts import ExecutionProposal
from engine.api_client import LighterApiClient, APIError


class FrozenContractViolation(Exception):
    pass


class AllocationViolation(Exception):
    pass


@dataclass
class ExecutionResult:
    record: Dict[str, Any]


class ExecutionEngine:
    """
    v1 execution engine:
    - validates frozen contract
    - uses allocation multiplier
    - calls API client
    - returns structured execution record
    """

    def __init__(self, client: LighterApiClient) -> None:
        self.client = client

    async def execute(self, proposal: ExecutionProposal, allocation_mult: float, reference_price: float) -> Optional[Dict[str, Any]]:
        ok, err = proposal.validate()
        if not ok:
            raise FrozenContractViolation(err)

        m = max(0.0, min(1.0, float(allocation_mult)))
        allocated_size = proposal.size * m

        if allocated_size <= 0:
            return None

        client_order_id = proposal.proposal_id
        amount = allocated_size if proposal.direction == "LONG" else -allocated_size

        try:
            order = await self.client.create_market_order(
                symbol=proposal.symbol,
                amount=amount,
                client_order_id=client_order_id,
            )
        except APIError:
            return None

        executed_size = abs(float(order.filled_size))
        executed_price = float(order.avg_price)

        # enforce no overfill beyond 1% tolerance
        tol = 0.01
        if executed_size > allocated_size * (1 + tol):
            raise AllocationViolation(
                f"ALLOCATION_VIOLATION: allocated={allocated_size} executed={executed_size}"
            )

        record = {
            "timestamp": datetime.now().isoformat(),
            "proposal_id": proposal.proposal_id,
            "symbol": proposal.symbol,
            "direction": proposal.direction,
            "allocated_size": allocated_size,
            "executed_size": executed_size,
            "reference_price": reference_price,
            "executed_price": executed_price,
            "status": order.status,
            "order_id": order.order_id,
            "basket": proposal.basket.value,
            "module": proposal.module.value,
            "htf_regime": proposal.htf_regime.value,
            "auction_context": proposal.auction_context.to_dict(),
            "allocation_multiplier": m,
        }
        return record
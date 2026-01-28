# risk/risk_brain.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.contracts import ExecutionProposal


@dataclass
class RiskDecision:
    action: str  # EXECUTE | PAUSE_TRADES | CIRCUIT_BREAK | REJECT
    allocation_multiplier: float
    reason: str


class RiskBrain:
    """
    v1 RiskBrain (minimal, safe defaults)
    - blocks if portfolio kill conditions are set (via portfolio_state)
    - clamps allocation multiplier to [0,1]
    """

    def assess(self, proposal: ExecutionProposal, portfolio_state: Dict[str, Any]) -> Tuple[str, float, str]:
        # basic sanity
        ok, err = proposal.validate()
        if not ok:
            return "REJECT", 0.0, f"Invalid proposal: {err}"

        # kill-switch hooks (portfolio_state can be fed by volatility kill switch etc.)
        if portfolio_state.get("kill_switch") is True:
            return "CIRCUIT_BREAK", 0.0, "Kill-switch active"

        # if API failing repeatedly, pause
        api_streak = int(portfolio_state.get("api_failure_streak", 0) or 0)
        if api_streak >= 5:
            return "PAUSE_TRADES", 0.0, f"API failure streak={api_streak}"

        # base allow
        return "EXECUTE", 1.0, "GREEN"
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional

from portfolio.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    allow: bool
    allocation_multiplier: float
    reason: str


@dataclass
class RiskState:
    kill_switch: bool = False
    api_failure_streak: int = 0
    risk_level: str = "GREEN"  # GREEN/YELLOW/RED/CIRCUIT
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0
    vol_spike: bool = False


class RiskBrain:
    """
    v1: practical + safe.
    - kill-switch: pause + cancel only (no auto-flatten)
    - uses portfolio snapshots (positions + pnl) when available
    """

    def __init__(
        self,
        portfolio: PortfolioState,
        max_api_failures: int = 5,
        max_drawdown_pct: float = 0.15,
        base_allocation_mult: float = 1.0,
    ):
        self.portfolio = portfolio
        self.state = RiskState()
        self.max_api_failures = max_api_failures
        self.max_drawdown_pct = max_drawdown_pct
        self.base_allocation_mult = base_allocation_mult

    def register_api_failure(self) -> None:
        self.state.api_failure_streak += 1
        if self.state.api_failure_streak >= self.max_api_failures:
            self.state.kill_switch = True
            self.state.risk_level = "CIRCUIT"
            logger.error("KILL SWITCH: api_failure_streak=%d", self.state.api_failure_streak)

    def register_api_success(self) -> None:
        # decay quickly on success
        self.state.api_failure_streak = max(0, self.state.api_failure_streak - 1)

    def update_from_pnl_snapshot(self) -> None:
        pnl = self.portfolio.last_pnl_snapshot or {}
        # Best-effort extraction
        daily = pnl.get("daily_pnl") or pnl.get("pnl") or pnl.get("raw", {}).get("daily_pnl") or 0.0
        dd = pnl.get("drawdown_pct") or pnl.get("raw", {}).get("drawdown_pct") or 0.0
        try:
            self.state.daily_pnl = float(daily)
        except Exception:
            self.state.daily_pnl = 0.0
        try:
            self.state.drawdown_pct = float(dd)
        except Exception:
            self.state.drawdown_pct = 0.0

        if self.state.drawdown_pct >= self.max_drawdown_pct:
            self.state.kill_switch = True
            self.state.risk_level = "CIRCUIT"
            logger.error("KILL SWITCH: drawdown_pct=%.4f", self.state.drawdown_pct)

    def assess_proposal(self, symbol: str) -> RiskDecision:
        if self.state.kill_switch or self.state.risk_level in ("CIRCUIT", "CIRCUIT_BREAK"):
            return RiskDecision(False, 0.0, "KILL_SWITCH_ACTIVE")

        # v1 sizing: if already exposed in symbol, reduce.
        open_pos = self.portfolio.open_positions()
        mult = self.base_allocation_mult
        if symbol in open_pos:
            mult *= 0.5

        # (placeholder) vol spike hook
        if self.state.vol_spike:
            mult *= 0.5

        mult = max(0.0, min(1.0, mult))
        return RiskDecision(True, mult, f"OK mult={mult:.2f}")

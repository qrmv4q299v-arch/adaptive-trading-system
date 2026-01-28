# strategy/strategy_router.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol, Any, List, Tuple

from core.contracts import Basket, HTFRegime, ExecutionProposal


class Strategy(Protocol):
    name: str

    def propose(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Dict[str, Any],
    ) -> Optional[ExecutionProposal]:
        ...


@dataclass
class RiskState:
    kill_switch: bool = False
    risk_level: str = "GREEN"  # GREEN/YELLOW/RED/CIRCUIT
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0
    vol_spike: bool = False
    api_failure_streak: int = 0


@dataclass
class RouterConfig:
    allow_liquidity_raid: bool = True
    disable_liquidity_raid_in: Tuple[HTFRegime, ...] = (HTFRegime.HIGH_VOLATILITY, HTFRegime.TRANSITION)
    basket3_soft_block: bool = True
    no_trade_regimes: Tuple[HTFRegime, ...] = ()

    regime_priority: Dict[HTFRegime, List[str]] = field(default_factory=lambda: {
        HTFRegime.TREND_UP: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.TREND_DOWN: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.BALANCED: ["mean_reversion", "trend_continuation", "liquidity_raid"],
        HTFRegime.HIGH_VOLATILITY: ["mean_reversion", "trend_continuation"],
        HTFRegime.TRANSITION: ["mean_reversion"],
    })


class StrategyRouter:
    def __init__(self, strategies: Dict[str, Strategy], config: Optional[RouterConfig] = None) -> None:
        self.strategies = strategies
        self.config = config or RouterConfig()

    def route(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Optional[Dict[str, Any]] = None,
        risk_state: Optional[RiskState] = None,
        prev_regime: Optional[HTFRegime] = None,
    ) -> Optional[ExecutionProposal]:
        ctx = dict(context or {})
        rs = risk_state or RiskState()

        if rs.kill_switch or rs.risk_level in ("CIRCUIT", "CIRCUIT_BREAK"):
            return None

        if regime in self.config.no_trade_regimes:
            return None

        if prev_regime is not None:
            dangerous_transition = (
                (prev_regime == HTFRegime.TREND_UP and regime == HTFRegime.HIGH_VOLATILITY)
                or (prev_regime == HTFRegime.BALANCED and regime == HTFRegime.TRANSITION)
            )
            priority = ["mean_reversion"] if dangerous_transition else self.config.regime_priority.get(regime, [])
        else:
            priority = self.config.regime_priority.get(regime, [])

        if (not self.config.allow_liquidity_raid) or (regime in self.config.disable_liquidity_raid_in):
            priority = [p for p in priority if p != "liquidity_raid"]

        basket3_candidate: Optional[ExecutionProposal] = None

        for strat_key in priority:
            strat = self.strategies.get(strat_key)
            if strat is None:
                continue

            proposal = strat.propose(symbol=symbol, snapshot=snapshot, regime=regime, context=ctx)
            if proposal is None:
                continue

            ok, _ = proposal.validate()
            if not ok:
                continue

            if self.config.basket3_soft_block and proposal.basket == Basket.BASKET_3:
                basket3_candidate = proposal
                continue

            return proposal

        return basket3_candidate
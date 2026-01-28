# strategy/strategy_router.py
"""
strategy/strategy_router.py

HARS Strategy Router
- Regime-based strategy switching
- Frozen contract safe: does NOT change entry logic inside strategies
- Output is an ExecutionProposal (with mandatory frozen tags) or None

Key ideas:
- Router decides WHICH strategy gets to propose a trade
- Strategy itself produces ExecutionProposal with frozen tags
- Risk layer / execution layer can later size/pause, but router stays pure

Integrations:
- Provide `regime` from your HTF regime engine
- Provide `risk_state` from risk brain (optional)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Protocol, Any, List, Tuple

from core.contracts import Basket, Module, HTFRegime, AuctionContext, ExecutionProposal


# =========================
# Strategy interface
# =========================

class Strategy(Protocol):
    name: str

    def propose(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Dict[str, Any],
    ) -> Optional[ExecutionProposal]:
        """
        Return ExecutionProposal or None.
        Must embed frozen tags (basket/module/regime/auction_context).
        """
        ...


# =========================
# Risk state interface (optional)
# =========================

@dataclass
class RiskState:
    """
    Minimal risk state used ONLY for router decisions.
    The actual kill-switch/sizing is handled by RiskGate/Execution layer.
    """
    kill_switch: bool = False
    risk_level: str = "GREEN"  # GREEN/YELLOW/RED/CIRCUIT
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0
    vol_spike: bool = False
    api_failure_streak: int = 0


# =========================
# Router config
# =========================

@dataclass
class RouterConfig:
    """
    Router preferences only (NOT risk enforcement).
    Encodes which strategies are preferred per regime, plus some safe defaults.
    """
    allow_liquidity_raid: bool = True
    disable_liquidity_raid_in: Tuple[HTFRegime, ...] = (HTFRegime.HIGH_VOLATILITY, HTFRegime.TRANSITION)

    basket3_soft_block: bool = True  # router prefers others first

    # Optional: router-level “no trade” regimes (soft gate)
    no_trade_regimes: Tuple[HTFRegime, ...] = ()

    # Strategy priority by regime (names must exist in registry)
    regime_priority: Dict[HTFRegime, List[str]] = field(default_factory=lambda: {
        HTFRegime.TREND_UP: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.TREND_DOWN: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.BALANCED: ["mean_reversion", "trend_continuation", "liquidity_raid"],
        HTFRegime.HIGH_VOLATILITY: ["mean_reversion", "trend_continuation"],  # no liquidity_raid by default
        HTFRegime.TRANSITION: ["mean_reversion"],  # very conservative
    })


# =========================
# Strategy Router
# =========================

class StrategyRouter:
    """
    Chooses a strategy based on regime and optional risk_state.
    Does NOT alter strategy internals. Only chooses which strategy gets a chance.
    """

    def __init__(
        self,
        strategies: Dict[str, Strategy],
        config: Optional[RouterConfig] = None,
    ) -> None:
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
        ctx = dict(context or {})  # copy so we don't mutate caller state
        rs = risk_state or RiskState()

        # Hard router block: kill-switch (execution layer should also block)
        if rs.kill_switch or rs.risk_level in ("CIRCUIT", "CIRCUIT_BREAK"):
            return None

        # Optional router “no-trade” regimes
        if regime in self.config.no_trade_regimes:
            return None

        # Transition soft block (real enforcement can live in RiskBrain)
        if prev_regime is not None:
            dangerous_transition = (
                (prev_regime == HTFRegime.TREND_UP and regime == HTFRegime.HIGH_VOLATILITY)
                or (prev_regime == HTFRegime.BALANCED and regime == HTFRegime.TRANSITION)
            )
            if dangerous_transition:
                priority = ["mean_reversion"]
            else:
                priority = self.config.regime_priority.get(regime, [])
        else:
            priority = self.config.regime_priority.get(regime, [])

        # Apply liquidity-raid disable for selected regimes
        if (not self.config.allow_liquidity_raid) or (regime in self.config.disable_liquidity_raid_in):
            priority = [p for p in priority if p != "liquidity_raid"]

        basket3_candidate: Optional[ExecutionProposal] = None

        # Try strategies in order, return first valid proposal
        for strat_key in priority:
            strat = self.strategies.get(strat_key)
            if strat is None:
                continue

            proposal = strat.propose(
                symbol=symbol,
                snapshot=snapshot,
                regime=regime,
                context=ctx,
            )
            if proposal is None:
                continue

            ok, err = proposal.validate()
            if not ok:
                # Strategy violated frozen contract => treat as bug => ignore it.
                # Upstream should log.
                continue

            # Router-level basket3 soft block
            if self.config.basket3_soft_block and proposal.basket == Basket.BASKET_3:
                basket3_candidate = proposal
                continue

            return proposal

        # Fallback: return basket3 candidate if nothing else worked
        return basket3_candidate

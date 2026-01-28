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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Protocol, Any, List, Tuple


# =========================
# Frozen contract enums
# =========================

class Basket(Enum):
    BASKET_1 = "BASKET_1"  # BTC, ETH
    BASKET_2 = "BASKET_2"  # SOL, MATIC, ADA
    BASKET_3 = "BASKET_3"  # AVAX, DOT, LUNA


class Module(Enum):
    MEAN_REVERSION = "MEAN_REVERSION"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    LIQUIDITY_RAID = "LIQUIDITY_RAID"


class HTFRegime(Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    BALANCED = "BALANCED"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True)
class AuctionContext:
    # Frozen: market microstructure tags at entry
    entry_at_val: bool = False
    entry_at_vah: bool = False
    entry_at_value_mid: bool = False
    outside_value_area: bool = False
    sfp_present: bool = False
    delta_aligned: bool = False
    absorption_detected: bool = False
    htf_filter_passed: bool = False
    no_trade_zone_active: bool = False

    def to_dict(self) -> dict:
        return {
            "entry_at_val": self.entry_at_val,
            "entry_at_vah": self.entry_at_vah,
            "entry_at_value_mid": self.entry_at_value_mid,
            "outside_value_area": self.outside_value_area,
            "sfp_present": self.sfp_present,
            "delta_aligned": self.delta_aligned,
            "absorption_detected": self.absorption_detected,
            "htf_filter_passed": self.htf_filter_passed,
            "no_trade_zone_active": self.no_trade_zone_active,
        }


@dataclass(frozen=True)
class ExecutionProposal:
    """
    Frozen contract object your execution layer expects.
    Router does not mutate it.
    """
    proposal_id: str
    symbol: str
    direction: str  # LONG | SHORT
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float

    basket: Basket
    module: Module
    htf_regime: HTFRegime
    auction_context: AuctionContext

    def validate(self) -> Tuple[bool, str]:
        if self.direction not in ("LONG", "SHORT"):
            return False, f"Invalid direction={self.direction}"
        if self.size <= 0:
            return False, f"Invalid size={self.size}"
        if self.entry_price <= 0:
            return False, f"Invalid entry_price={self.entry_price}"
        if not isinstance(self.basket, Basket):
            return False, "FROZEN_CONTRACT_VIOLATION: basket must be Basket"
        if not isinstance(self.module, Module):
            return False, "FROZEN_CONTRACT_VIOLATION: module must be Module"
        if not isinstance(self.htf_regime, HTFRegime):
            return False, "FROZEN_CONTRACT_VIOLATION: htf_regime must be HTFRegime"
        if not isinstance(self.auction_context, AuctionContext):
            return False, "FROZEN_CONTRACT_VIOLATION: auction_context must be AuctionContext"
        return True, ""


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
    Encodes known constraints and safe defaults:
    - Liquidity Raid often unstable in HIGH_VOLATILITY / TRANSITION
    - Basket 3 soft-block to prefer more liquid baskets first
    - Optional "no trade" regimes at router level (soft gate)
    """
    allow_liquidity_raid: bool = True
    disable_liquidity_raid_in: Tuple[HTFRegime, ...] = (
        HTFRegime.HIGH_VOLATILITY,
        HTFRegime.TRANSITION,
    )

    basket3_soft_block: bool = True

    # Soft no-trade regimes (router-level). Risk layer still enforces hard blocks.
    no_trade_regimes: Tuple[HTFRegime, ...] = ()

    # Transition shock filters (soft) — treat these transitions as "danger mode"
    danger_transitions: Tuple[Tuple[HTFRegime, HTFRegime], ...] = (
        (HTFRegime.TREND_UP, HTFRegime.HIGH_VOLATILITY),
        (HTFRegime.BALANCED, HTFRegime.TRANSITION),
    )

    # Strategy priority by regime (names must exist in registry)
    regime_priority: Dict[HTFRegime, List[str]] = field(default_factory=lambda: {
        HTFRegime.TREND_UP: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.TREND_DOWN: ["trend_continuation", "mean_reversion", "liquidity_raid"],
        HTFRegime.BALANCED: ["mean_reversion", "trend_continuation", "liquidity_raid"],
        HTFRegime.HIGH_VOLATILITY: ["mean_reversion", "trend_continuation"],
        HTFRegime.TRANSITION: ["mean_reversion"],
    })

    # Conservative priority list when "danger transition" is detected
    danger_priority: List[str] = field(default_factory=lambda: ["mean_reversion"])

    # Extra conservative router filters based on risk_state (soft selection filters)
    max_api_failure_streak_for_aggressive: int = 2
    block_aggressive_on_vol_spike: bool = True

    # Which strategies are considered "aggressive" (router may skip them under stress)
    aggressive_strategies: Tuple[str, ...] = ("liquidity_raid",)


# =========================
# Strategy Router
# =========================

class StrategyRouter:
    """
    Chooses a strategy based on regime and risk_state.
    Does NOT alter strategy internals.
    Returns the first valid ExecutionProposal by priority.
    """

    def __init__(
        self,
        strategies: Dict[str, Strategy],
        config: Optional[RouterConfig] = None,
    ) -> None:
        self.strategies = strategies
        self.config = config or RouterConfig()

    def _priority_for_regime(
        self,
        regime: HTFRegime,
        prev_regime: Optional[HTFRegime],
    ) -> List[str]:
        if prev_regime is not None and (prev_regime, regime) in self.config.danger_transitions:
            return list(self.config.danger_priority)
        return list(self.config.regime_priority.get(regime, []))

    def _apply_rule_gates(
        self,
        priority: List[str],
        regime: HTFRegime,
        risk_state: RiskState,
    ) -> List[str]:
        # Liquidity raid disabled by regime config
        if (not self.config.allow_liquidity_raid) or (regime in self.config.disable_liquidity_raid_in):
            priority = [p for p in priority if p != "liquidity_raid"]

        # If volatility spike, optionally block aggressive strategies
        if self.config.block_aggressive_on_vol_spike and risk_state.vol_spike:
            priority = [p for p in priority if p not in self.config.aggressive_strategies]

        # If API failures are stacking, block aggressive strategies
        if risk_state.api_failure_streak > self.config.max_api_failure_streak_for_aggressive:
            priority = [p for p in priority if p not in self.config.aggressive_strategies]

        return priority

    def route(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Optional[Dict[str, Any]] = None,
        risk_state: Optional[RiskState] = None,
        prev_regime: Optional[HTFRegime] = None,
    ) -> Optional[ExecutionProposal]:
        ctx = context or {}
        rs = risk_state or RiskState()

        # Hard router block: kill-switch (execution layer should also block)
        if rs.kill_switch or rs.risk_level in ("CIRCUIT", "CIRCUIT_BREAK"):
            return None

        # Optional router “no-trade” regimes
        if regime in self.config.no_trade_regimes:
            return None

        # Strategy priority list
        priority = self._priority_for_regime(regime, prev_regime)
        priority = self._apply_rule_gates(priority, regime, rs)

        basket3_fallback: Optional[ExecutionProposal] = None

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

            ok, _err = proposal.validate()
            if not ok:
                # Strategy produced invalid frozen contract proposal → skip (bug upstream)
                continue

            # Safety: enforce module-based constraints too (not only strategy name)
            if (proposal.module == Module.LIQUIDITY_RAID) and (regime in self.config.disable_liquidity_raid_in):
                continue

            # Basket 3 soft block: keep as fallback, keep scanning for better
            if self.config.basket3_soft_block and proposal.basket == Basket.BASKET_3:
                basket3_fallback = proposal
                continue

            return proposal

        return basket3_fallback

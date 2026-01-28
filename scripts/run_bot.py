# scripts/run_bot.py
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import ExecutionProposal, HTFRegime

from strategy.strategy_router import StrategyRouter, RouterConfig, RiskState

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logger = logging.getLogger("run_bot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


# ---------------------------------------------------------------------
# Minimal strategy stubs (until you implement real strategies)
# - These belong in strategies/ later, but we keep them here so run_bot runs now.
# ---------------------------------------------------------------------

class NoopStrategy:
    name = "noop"

    def propose(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Dict[str, Any],
    ) -> Optional[ExecutionProposal]:
        return None


# ---------------------------------------------------------------------
# Optional imports from your repo modules
# We import them if they exist + match expected interface.
# If your current files are stubs, this still works.
# ---------------------------------------------------------------------

def _safe_import_engine():
    """
    Returns (lighter_client, execution_engine, order_reconciliation, position_manager)
    If a module doesn't match expected interface, returns None for it.
    """
    lighter_client = None
    execution_engine = None
    order_reconciliation = None
    position_manager = None

    try:
        from engine.api_client import LighterApiClient  # type: ignore
        lighter_client = LighterApiClient
    except Exception as e:
        logger.warning(f"Could not import engine.api_client.LighterApiClient: {e}")

    try:
        from engine.execution_engine import ExecutionEngine  # type: ignore
        execution_engine = ExecutionEngine
    except Exception as e:
        logger.warning(f"Could not import engine.execution_engine.ExecutionEngine: {e}")

    try:
        from engine.order_reconciliation import OrderReconciler  # type: ignore
        order_reconciliation = OrderReconciler
    except Exception as e:
        logger.warning(f"Could not import engine.order_reconciliation.OrderReconciler: {e}")

    try:
        from engine.position_manager import PositionManager  # type: ignore
        position_manager = PositionManager
    except Exception as e:
        logger.warning(f"Could not import engine.position_manager.PositionManager: {e}")

    return lighter_client, execution_engine, order_reconciliation, position_manager


def _safe_import_risk():
    """
    Returns RiskBrain class if present.
    Expected method: assess(proposal, portfolio_state) -> (action:str, allocation_mult:float, reason:str)
    """
    try:
        from risk.risk_brain import RiskBrain  # type: ignore
        return RiskBrain
    except Exception as e:
        logger.warning(f"Could not import risk.risk_brain.RiskBrain: {e}")
        return None


def _safe_import_portfolio():
    """
    Returns PortfolioState class if present.
    """
    try:
        from portfolio.portfolio_state import PortfolioState  # type: ignore
        return PortfolioState
    except Exception as e:
        logger.warning(f"Could not import portfolio.portfolio_state.PortfolioState: {e}")
        return None


# ---------------------------------------------------------------------
# Minimal fallbacks (so bot can run even if your modules are not ready)
# ---------------------------------------------------------------------

class FallbackPortfolioState:
    def __init__(self) -> None:
        self.timestamp = time.time()
        self.positions: Dict[str, Any] = {}
        self.pnl: float = 0.0
        self.exposure: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "positions": self.positions,
            "pnl": self.pnl,
            "exposure": self.exposure,
        }


class FallbackRiskBrain:
    def assess(self, proposal: ExecutionProposal, portfolio_state: Dict[str, Any]) -> Tuple[str, float, str]:
        # minimal default: allow execution at full size
        return "EXECUTE", 1.0, "Fallback risk brain"


class FallbackExecutionEngine:
    async def execute(self, proposal: ExecutionProposal, allocation_mult: float, reference_price: float) -> Optional[Dict[str, Any]]:
        # dry-run: do not place real orders; return a fake execution record
        ok, err = proposal.validate()
        if not ok:
            logger.error(f"Proposal invalid: {err}")
            return None

        allocated_size = proposal.size * allocation_mult
        return {
            "timestamp": time.time(),
            "proposal_id": proposal.proposal_id,
            "symbol": proposal.symbol,
            "direction": proposal.direction,
            "allocated_size": allocated_size,
            "executed_size": allocated_size,
            "reference_price": reference_price,
            "executed_price": reference_price,
            "status": "DRY_RUN_FILLED",
            "basket": proposal.basket.value,
            "module": proposal.module.value,
            "htf_regime": proposal.htf_regime.value,
            "auction_context": proposal.auction_context.to_dict(),
            "allocation_multiplier": allocation_mult,
        }


class FallbackMarketData:
    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        # stub snapshot
        return {"symbol": symbol, "ts": time.time()}

    async def get_price(self, symbol: str) -> float:
        # stub price
        return 100.0


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

@dataclass
class BotConfig:
    symbols: List[str]
    loop_interval_sec: float = 3.0
    dry_run: bool = True


async def run_bot(cfg: BotConfig) -> None:
    # Imports
    LighterApiClient, ExecutionEngine, OrderReconciler, PositionManager = _safe_import_engine()
    RiskBrain = _safe_import_risk()
    PortfolioState = _safe_import_portfolio()

    # Instantiate portfolio
    if PortfolioState is not None:
        portfolio_state_obj = PortfolioState()
        portfolio_state = getattr(portfolio_state_obj, "to_dict", lambda: {})()
    else:
        portfolio_state_obj = FallbackPortfolioState()
        portfolio_state = portfolio_state_obj.to_dict()

    # Instantiate risk
    risk_brain = RiskBrain() if RiskBrain is not None else FallbackRiskBrain()

    # Instantiate execution
    if cfg.dry_run or ExecutionEngine is None:
        execution_engine = FallbackExecutionEngine()
        lighter_client = None
        order_reconciler = None
        position_manager = None
    else:
        # Real live mode (only if your engine classes exist)
        # NOTE: We keep config minimal and env-driven.
        key = os.getenv("LIGHTER_KEY", "")
        secret = os.getenv("LIGHTER_SECRET", "")
        base_url = os.getenv("LIGHTER_URL", "")
        account_index = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "0"))
        api_key_index = int(os.getenv("LIGHTER_API_KEY_INDEX", "0"))

        if not key or not secret or not base_url:
            raise RuntimeError("Missing LIGHTER_KEY / LIGHTER_SECRET / LIGHTER_URL env vars for live mode.")

        lighter_client = LighterApiClient(key=key, secret=secret, account_index=account_index, api_key_index=api_key_index, base_url=base_url)  # type: ignore
        execution_engine = ExecutionEngine(lighter_client)  # type: ignore
        order_reconciler = OrderReconciler(lighter_client) if OrderReconciler is not None else None  # type: ignore
        position_manager = PositionManager(lighter_client) if PositionManager is not None else None  # type: ignore

    market_data = FallbackMarketData()

    # Strategies registry (currently noop placeholders)
    strategies = {
        "mean_reversion": NoopStrategy(),
        "trend_continuation": NoopStrategy(),
        "liquidity_raid": NoopStrategy(),
    }

    router = StrategyRouter(
        strategies=strategies,
        config=RouterConfig(),
    )

    prev_regime_by_symbol: Dict[str, Optional[HTFRegime]] = {s: None for s in cfg.symbols}

    logger.info(f"Bot starting. symbols={cfg.symbols} dry_run={cfg.dry_run} interval={cfg.loop_interval_sec}s")

    while True:
        iteration_start = time.time()

        # Refresh portfolio state if a manager exists
        try:
            if position_manager is not None:
                # expected: await position_manager.sync() returns portfolio dict or updates internal state
                maybe = await position_manager.sync()  # type: ignore
                if isinstance(maybe, dict):
                    portfolio_state = maybe
        except Exception as e:
            logger.warning(f"Position sync failed: {e}")

        for symbol in cfg.symbols:
            try:
                snapshot = await market_data.get_snapshot(symbol)

                # Regime model wiring (stub now)
                # Later: replace with risk/regime_model.get_regime(snapshot)
                regime = HTFRegime.BALANCED

                risk_state = RiskState(
                    kill_switch=False,
                    risk_level="GREEN",
                )

                proposal = router.route(
                    symbol=symbol,
                    snapshot=snapshot,
                    regime=regime,
                    context={},
                    risk_state=risk_state,
                    prev_regime=prev_regime_by_symbol.get(symbol),
                )

                prev_regime_by_symbol[symbol] = regime

                if proposal is None:
                    continue

                ok, err = proposal.validate()
                if not ok:
                    logger.error(f"Router produced invalid proposal: {err}")
                    continue

                # Risk assess (size / pause decision)
                try:
                    action, alloc_mult, reason = risk_brain.assess(proposal, portfolio_state)  # type: ignore
                except Exception as e:
                    logger.warning(f"Risk assess failed for {proposal.proposal_id}: {e}")
                    continue

                if action in ("PAUSE_TRADES", "CIRCUIT_BREAK", "REJECT"):
                    logger.info(f"Risk blocked proposal {proposal.proposal_id}: {action} reason={reason}")
                    continue

                # Price reference
                price = await market_data.get_price(symbol)

                # Execute
                exec_record = await execution_engine.execute(proposal, alloc_mult, price)  # type: ignore
                if exec_record:
                    logger.info(f"EXEC: {exec_record.get('proposal_id')} {exec_record.get('symbol')} {exec_record.get('status')}")

                # Reconcile orders
                try:
                    if order_reconciler is not None:
                        await order_reconciler.sync()  # type: ignore
                except Exception as e:
                    logger.warning(f"Order reconciliation failed: {e}")

            except Exception as e:
                logger.exception(f"Error processing symbol={symbol}: {e}")

        elapsed = time.time() - iteration_start
        sleep_for = max(0.5, cfg.loop_interval_sec - elapsed)
        await asyncio.sleep(sleep_for)


def main() -> None:
    symbols = os.getenv("SYMBOLS", "BTC/USD,ETH/USD").split(",")
    symbols = [s.strip() for s in symbols if s.strip()]

    dry_run = os.getenv("DRY_RUN", "1").strip() in ("1", "true", "TRUE", "yes", "YES")
    interval = float(os.getenv("LOOP_INTERVAL_SEC", "3.0"))

    cfg = BotConfig(symbols=symbols, loop_interval_sec=interval, dry_run=dry_run)
    asyncio.run(run_bot(cfg))


if __name__ == "__main__":
    main()

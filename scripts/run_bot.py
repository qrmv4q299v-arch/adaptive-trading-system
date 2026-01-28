# scripts/run_bot.py
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import ExecutionProposal, HTFRegime, Basket, Module, AuctionContext
from engine.api_client import LighterApiClient
from engine.execution_engine import ExecutionEngine
from engine.order_reconciliation import OrderReconciler
from engine.position_manager import PositionManager
from risk.risk_brain import RiskBrain
from risk.regime_model import RegimeModel
from strategy.strategy_router import StrategyRouter, RouterConfig, RiskState

# ---------------------------------------------------------
# logging
# ---------------------------------------------------------
logger = logging.getLogger("run_bot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(ch)

# ---------------------------------------------------------
# Minimal strategies (real ones later in strategies/)
# ---------------------------------------------------------
class NoopStrategy:
    name = "noop"
    def propose(self, symbol: str, snapshot: Dict[str, Any], regime: HTFRegime, context: Dict[str, Any]) -> Optional[ExecutionProposal]:
        return None

# Example "toy" strategy that occasionally proposes (so you can see flow works).
# You can delete later.
class DemoMeanReversionStrategy:
    name = "mean_reversion"

    def __init__(self) -> None:
        self._n = 0

    def propose(self, symbol: str, snapshot: Dict[str, Any], regime: HTFRegime, context: Dict[str, Any]) -> Optional[ExecutionProposal]:
        self._n += 1
        if self._n % 20 != 0:
            return None

        return ExecutionProposal(
            proposal_id=f"{symbol.replace('/','_')}_{int(time.time())}",
            symbol=symbol,
            direction="LONG",
            size=0.01,
            entry_price=float(snapshot.get("price", 100.0)),
            stop_loss=float(snapshot.get("price", 100.0)) * 0.99,
            take_profit=float(snapshot.get("price", 100.0)) * 1.01,
            basket=Basket.BASKET_1,
            module=Module.MEAN_REVERSION,
            htf_regime=regime,
            auction_context=AuctionContext(htf_filter_passed=True),
        )

# ---------------------------------------------------------
# Market data stub
# ---------------------------------------------------------
class MarketData:
    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "ts": time.time(), "price": 100.0}

    async def get_price(self, symbol: str) -> float:
        return 100.0

# ---------------------------------------------------------
# bot config
# ---------------------------------------------------------
@dataclass
class BotConfig:
    symbols: List[str]
    loop_interval_sec: float = 3.0
    dry_run: bool = True

# ---------------------------------------------------------
async def run_bot(cfg: BotConfig) -> None:
    client = LighterApiClient(dry_run=cfg.dry_run)
    execution_engine = ExecutionEngine(client)
    order_reconciler = OrderReconciler(client)
    position_manager = PositionManager(client)

    risk_brain = RiskBrain()
    regime_model = RegimeModel()
    market = MarketData()

    strategies = {
        "mean_reversion": DemoMeanReversionStrategy(),
        "trend_continuation": NoopStrategy(),
        "liquidity_raid": NoopStrategy(),
    }

    router = StrategyRouter(strategies=strategies, config=RouterConfig())

    prev_regime: Dict[str, Optional[HTFRegime]] = {s: None for s in cfg.symbols}

    logger.info(f"Starting bot. dry_run={cfg.dry_run} symbols={cfg.symbols}")

    while True:
        start = time.time()

        portfolio_state = await position_manager.sync()

        for symbol in cfg.symbols:
            snapshot = await market.get_snapshot(symbol)
            regime = regime_model.get_regime(snapshot)

            rs = RiskState(kill_switch=bool(portfolio_state.get("kill_switch", False)))
            proposal = router.route(
                symbol=symbol,
                snapshot=snapshot,
                regime=regime,
                context={},
                risk_state=rs,
                prev_regime=prev_regime.get(symbol),
            )
            prev_regime[symbol] = regime

            if proposal is None:
                continue

            ok, err = proposal.validate()
            if not ok:
                logger.warning(f"Invalid proposal: {err}")
                continue

            action, alloc_mult, reason = risk_brain.assess(proposal, portfolio_state)
            if action != "EXECUTE":
                logger.info(f"Risk blocked {proposal.proposal_id}: {action} reason={reason}")
                continue

            price = await market.get_price(symbol)
            try:
                exec_record = await execution_engine.execute(proposal, alloc_mult, price)
            except Exception as e:
                logger.error(f"Execution error: {e}")
                continue

            if exec_record:
                logger.info(f"EXEC OK: {exec_record.get('proposal_id')} order_id={exec_record.get('order_id')}")
                # reconcile placeholder
                await order_reconciler.sync()

        elapsed = time.time() - start
        await asyncio.sleep(max(0.5, cfg.loop_interval_sec - elapsed))

def main() -> None:
    symbols = os.getenv("SYMBOLS", "BTC/USD,ETH/USD").split(",")
    symbols = [s.strip() for s in symbols if s.strip()]
    dry_run = os.getenv("DRY_RUN", "1").strip().lower() in ("1", "true", "yes")
    interval = float(os.getenv("LOOP_INTERVAL_SEC", "3.0"))

    cfg = BotConfig(symbols=symbols, loop_interval_sec=interval, dry_run=dry_run)
    asyncio.run(run_bot(cfg))

if __name__ == "__main__":
    main()
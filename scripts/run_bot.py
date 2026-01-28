# scripts/run_bot.py
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional, List

from engine.api_client import LighterApiClient, LighterConfig
from engine.order_reconciliation import OrderReconciler
from engine.execution_engine import ExecutionEngine, ExecutionProposal
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_bot")


async def price_feed_stub(symbol: str) -> float:
    # Replace with your real feed later.
    return 100.0


async def store_trade_jsonl(rec: Dict[str, Any]) -> None:
    os.makedirs("data", exist_ok=True)
    path = os.path.join("data", f"trades_{time.strftime('%Y%m%d')}.jsonl")
    import json
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


async def main() -> None:
    cfg = LighterConfig(
        key=os.environ.get("LIGHTER_KEY", ""),
        secret=os.environ.get("LIGHTER_SECRET", ""),
        account_index=int(os.environ.get("LIGHTER_ACCOUNT_INDEX", "0")),
        api_key_index=int(os.environ.get("LIGHTER_API_KEY_INDEX", "0")),
        base_url=os.environ.get("LIGHTER_BASE_URL", ""),
    )

    if not cfg.key or not cfg.secret or not cfg.base_url:
        logger.error("Missing env vars: LIGHTER_KEY / LIGHTER_SECRET / LIGHTER_BASE_URL")
        return

    api = LighterApiClient(cfg)
    portfolio = PortfolioState()
    risk = RiskBrain(portfolio=portfolio)
    reconciler = OrderReconciler(api=api, poll_interval=2.0, stuck_after_sec=30.0)
    engine = ExecutionEngine(api=api, portfolio=portfolio, risk=risk, reconciler=reconciler, store_fn=store_trade_jsonl)

    kill_event = asyncio.Event()

    async def reconcile_task():
        await reconciler.run_forever(clock_fn=time.time, kill_event=kill_event)

    async def sync_portfolio_task():
        while not kill_event.is_set():
            try:
                acct = await api.get_account_state()
                portfolio.update_from_account_snapshot(acct)

                pnl = await api.get_pnl()
                portfolio.update_from_pnl_snapshot(pnl)
                risk.update_from_pnl_snapshot()
            except Exception as e:
                logger.warning("Portfolio sync failed: %s", e)
                risk.register_api_failure()
            await asyncio.sleep(3.0)

    # Demo proposal (replace with router output)
    proposals: List[ExecutionProposal] = [
        ExecutionProposal(
            proposal_id="DEMO_PROP_001",
            symbol="BTC-PERP",
            direction="LONG",
            size=0.001,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            basket="BASKET_1",
            module="MEAN_REVERSION",
            htf_regime="BALANCED",
            auction_context={"htf_filter_passed": True},
        )
    ]

    async def trading_loop():
        while not kill_event.is_set():
            if risk.state.kill_switch:
                logger.error("KILL SWITCH ACTIVE: stop submitting new orders.")
                await asyncio.sleep(2.0)
                continue

            for p in proposals:
                ref = await price_feed_stub(p.symbol)
                _ = await engine.execute(p, reference_price=ref)

            await asyncio.sleep(3.0)

    tasks = [
        asyncio.create_task(reconcile_task()),
        asyncio.create_task(sync_portfolio_task()),
        asyncio.create_task(trading_loop()),
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        kill_event.set()
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())

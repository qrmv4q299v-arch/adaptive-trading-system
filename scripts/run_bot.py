import time

from engine.api_client import APIClient
from engine.execution_engine import ExecutionEngine
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain
from risk.volatility_model import VolatilityModel

from analytics.performance_tracker import PerformanceTracker
from strategy.strategy_router import StrategyRouter
from strategy.adaptive_allocator import AdaptiveAllocator
from strategy.meta_strategy_manager import MetaStrategyManager


RECONCILE_INTERVAL = 5


def main():
    api = APIClient()
    engine = ExecutionEngine(api)

    portfolio = PortfolioState()
    vol_model = VolatilityModel()
    risk = RiskBrain(portfolio, vol_model)

    router = StrategyRouter()

    tracker = PerformanceTracker(recent_window=30)
    allocator = AdaptiveAllocator(tracker=tracker)
    meta = MetaStrategyManager(tracker=tracker)

    print("🚀 Bot started... (Meta-Strategy enabled)")

    while True:
        symbol = "BTC-PERP"
        market_price = 50000  # TODO: replace with your real price feed

        market_state = {
            "spread": 0.0004,
            "volatility": vol_model.current_volatility(),
            "urgency": "normal",
        }

        # 1) Risk updates & regime
        risk.update_market_state({"symbol": symbol, "price": market_price})
        regime = risk.regime_model.get_regime()

        # 2) Kill switch
        if risk.kill_switch.is_active():
            engine.position_manager.emergency_close_all()
            time.sleep(RECONCILE_INTERVAL)
            continue

        # 3) Manage open positions (regime-aware)
        engine.position_manager.update_market_price(symbol, market_price, regime)

        # 4) META: choose best strategy for this regime
        chosen = meta.pick_strategy(regime)
        if not chosen:
            print(f"🟡 No safe strategy for regime={regime}. No-trade.")
            time.sleep(RECONCILE_INTERVAL)
            continue

        # 5) Router allows/blocks
        if not router.is_strategy_allowed(chosen, regime):
            time.sleep(RECONCILE_INTERVAL)
            continue

        # 6) Allocation (strategy health aware)
        base_size = 1.5
        adjusted_size, score, health = allocator.adjust_size(chosen, base_size)

        if adjusted_size <= 0:
            print(f"🛑 Strategy {chosen} DISABLED (health={health})")
            time.sleep(RECONCILE_INTERVAL)
            continue

        # 7) Build execution proposal (still “frozen contract safe”: meta only selects + sizes)
        proposal = {
            "symbol": symbol,
            "direction": "LONG",      # TODO: from your signal layer
            "size": adjusted_size,
            "strategy": chosen,
            "regime": regime,
        }

        approved, adj_size, sl, tp, reason = risk.evaluate_trade(proposal, market_price)

        if approved and adj_size > 0:
            proposal["size"] = adj_size
            proposal["stop_loss"] = sl
            proposal["take_profit"] = tp

            # Execute
            engine.execute(proposal, market_state)
            print(f"✅ {chosen} | regime={regime} | health={health} | score={score:.2f}")

        portfolio.print_summary()
        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

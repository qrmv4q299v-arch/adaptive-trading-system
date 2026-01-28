import time
from engine.api_client import APIClient
from engine.execution_engine import ExecutionEngine
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain
from risk.volatility_model import VolatilityModel
from strategy.strategy_router import StrategyRouter
from strategy.adaptive_allocator import AdaptiveAllocator

RECONCILE_INTERVAL = 5

def main():
    api = APIClient()
    engine = ExecutionEngine(api)
    portfolio = PortfolioState()
    vol_model = VolatilityModel()
    risk = RiskBrain(portfolio, vol_model)
    router = StrategyRouter()
    allocator = AdaptiveAllocator()

    print("🚀 Bot started...")

    while True:
        symbol = "BTC-PERP"
        market_price = 50000

        market_state = {
            "spread": 0.0004,
            "volatility": vol_model.current_volatility(),
            "urgency": "normal"
        }

        risk.update_market_state({"symbol": symbol, "price": market_price})
        regime = risk.regime_model.get_regime()

        if risk.kill_switch.is_active():
            engine.position_manager.emergency_close_all()
            time.sleep(RECONCILE_INTERVAL)
            continue

        engine.position_manager.update_market_price(symbol, market_price, regime)

        strategy_name = "trend_following"

        if not router.is_strategy_allowed(strategy_name, regime):
            time.sleep(RECONCILE_INTERVAL)
            continue

        base_size = 1.5
        adjusted_size, score, health = allocator.adjust_size(strategy_name, base_size)

        if adjusted_size == 0:
            print(f"🛑 Strategy {strategy_name} DISABLED")
            time.sleep(RECONCILE_INTERVAL)
            continue

        proposal = {
            "symbol": symbol,
            "direction": "LONG",
            "size": adjusted_size,
            "strategy": strategy_name
        }

        approved, adj_size, sl, tp, reason = risk.evaluate_trade(proposal, market_price)

        if approved and adj_size > 0:
            proposal["size"] = adj_size
            proposal["stop_loss"] = sl
            proposal["take_profit"] = tp
            engine.execute(proposal, market_state)
            print(f"✅ {strategy_name} | Health={health} | Score={score:.2f}")

        portfolio.print_summary()
        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

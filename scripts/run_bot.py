import time
from engine.api_client import APIClient
from engine.execution_engine import ExecutionEngine
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain
from risk.volatility_model import VolatilityModel
from strategy.strategy_router import StrategyRouter

RECONCILE_INTERVAL = 5

def main():
    api = APIClient()
    engine = ExecutionEngine(api)
    portfolio = PortfolioState()
    vol_model = VolatilityModel()
    risk = RiskBrain(portfolio, vol_model)
    router = StrategyRouter()

    print("🚀 Bot started...")

    while True:
        fills = engine.reconciler.reconcile()
        for fill in fills:
            portfolio.process_fill(fill)

        portfolio.mark_to_market({})

        # Fake market price input
        market_price = 50000
        risk.update_market_state({"price": market_price})

        proposal = {
            "symbol": "BTC-PERP",
            "direction": "LONG",
            "size": 1.5,
            "strategy": "trend_following"
        }

        regime = risk.regime_model.get_regime()

        if not router.is_strategy_allowed(proposal["strategy"], regime):
            print(f"⛔ Strategy {proposal['strategy']} disabled in {regime} regime")
            time.sleep(RECONCILE_INTERVAL)
            continue

        approved, adj_size, reason = risk.evaluate_trade(proposal)

        if approved and adj_size > 0:
            proposal["size"] = adj_size
            engine.execute(proposal)
            print(f"✅ Trade approved: {proposal} | {reason}")
        else:
            print(f"⛔ Trade blocked: {reason}")

        portfolio.print_summary()
        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

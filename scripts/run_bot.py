import time
from engine.api_client import APIClient
from engine.execution_engine import ExecutionEngine
from portfolio.portfolio_state import PortfolioState
from risk.risk_brain import RiskBrain

RECONCILE_INTERVAL = 5

def main():
    api = APIClient()
    engine = ExecutionEngine(api)
    portfolio = PortfolioState()
    risk = RiskBrain(portfolio)

    print("🚀 Bot started...")

    while True:
        fills = engine.reconciler.reconcile()

        for fill in fills:
            portfolio.process_fill(fill)

        portfolio.mark_to_market({})

        proposal = {
            "symbol": "BTC-PERP",
            "direction": "LONG",
            "size": 1.5
        }

        approved, adj_size, reason = risk.evaluate_trade(proposal)

        if approved and adj_size > 0:
            proposal["size"] = adj_size
            engine.execute(proposal)
            print(f"✅ Trade approved: {proposal}")
        else:
            print(f"⛔ Trade blocked: {reason}")

        print(f"📉 Drawdown: {risk.drawdown:.2f} | Peak: {risk.equity_peak:.2f}")
        portfolio.print_summary()

        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

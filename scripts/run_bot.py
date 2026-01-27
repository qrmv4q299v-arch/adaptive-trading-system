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
        # 1️⃣ Reconcile orders → get fills
        fills = engine.reconciler.reconcile()

        # 2️⃣ Update portfolio
        for fill in fills:
            portfolio.process_fill(fill)

        # 3️⃣ Update PnL
        portfolio.mark_to_market({})

        # 4️⃣ Example incoming proposal (stub for now)
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

        portfolio.print_summary()
        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

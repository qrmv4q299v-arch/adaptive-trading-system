import time
from engine.api_client import APIClient
from engine.execution_engine import ExecutionEngine
from portfolio.portfolio_state import PortfolioState

RECONCILE_INTERVAL = 5

def main():
    api = APIClient()
    engine = ExecutionEngine(api)
    portfolio = PortfolioState()

    print("🚀 Bot started...")

    while True:
        # 1️⃣ Reconcile open orders
        fills = engine.reconciler.reconcile()

        # 2️⃣ Update portfolio from fills
        for fill in fills:
            portfolio.process_fill(fill)

        # 3️⃣ Mark-to-market PnL update (stub market prices for now)
        portfolio.mark_to_market({})  # later: real price feed

        # 4️⃣ Debug output
        portfolio.print_summary()

        time.sleep(RECONCILE_INTERVAL)


if __name__ == "__main__":
    main()

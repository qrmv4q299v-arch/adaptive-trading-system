from strategies.trend_following import TrendFollowingStrategy
from risk.risk_brain import RiskBrain
from allocation.strategy_allocator import StrategyAllocator
from engine.execution_engine import ExecutionEngine

def main():
    strategy = TrendFollowingStrategy()
    risk = RiskBrain()
    allocator = StrategyAllocator()
    engine = ExecutionEngine()

    # Stub example flow
    signal = {"symbol": "BTC-PERP", "direction": "LONG", "size": 1, "timestamp": 0}
    proposal = strategy.build_proposal(signal)

    proposal = allocator.adjust_size(proposal, "LOW_VOL", 1.0)
    approved, size, reason = risk.evaluate_trade(proposal, {}, {})
    
    if approved:
        proposal["size"] = size
        engine.execute(proposal)

if __name__ == "__main__":
    main()

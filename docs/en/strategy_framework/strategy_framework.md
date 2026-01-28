📈 Strategy Framework

1. Purpose

The strategy framework defines how trading ideas are:
	•	Designed
	•	Integrated
	•	Evaluated
	•	Allocated capital

Strategies are modular, replaceable, and risk-contained.

A key principle:

Strategies generate opportunity. The system controls risk.

No strategy can bypass the Risk Brain or execution safeguards.

⸻

2. Strategy Design Philosophy

Strategies in this system should be:

✔ Simple and explainable
✔ Focused on one market behavior
✔ Robust across time, not optimized for one period
✔ Designed assuming risk controls will adjust sizing

We prefer multiple modest, diversified edges rather than one highly optimized model.

⸻

3. Strategy Lifecycle

Each strategy goes through the same pipeline:

1️⃣ Research

Identify a market behavior:
	•	Trend persistence
	•	Mean reversion
	•	Volatility expansion
	•	Funding rate imbalance
	•	Liquidity shocks

2️⃣ Backtesting

Test for:
	•	Stability across regimes
	•	Reasonable drawdowns
	•	Realistic costs and slippage

3️⃣ Paper/Demo Trading

Validate:
	•	Execution behavior
	•	Signal timing in live markets
	•	Interaction with risk layer

4️⃣ Limited Capital Deployment

Start with small allocation.
The adaptive system then evaluates performance.

5️⃣ Ongoing Evaluation

The system tracks strategy fitness by regime and adjusts allocation gradually.

Poorly performing strategies naturally lose capital allocation over time.

⸻

4. Strategy Interface (Technical Structure)

Each strategy module outputs a trade proposal object.

Required Proposal Fields

Field	Description
symbol	Market instrument
direction	Long or short
size	Suggested position size
strategy_name	Identifier for tracking
timestamp	Signal generation time

Optional:
	•	Confidence score
	•	Signal strength metric

The proposal then passes through:
Allocation → Risk Brain → Execution

⸻

5. What Strategies Do NOT Control

Strategies cannot:

❌ Set leverage directly
❌ Override risk limits
❌ Force execution
❌ Bypass allocation rules
❌ Modify portfolio exposure caps

This separation ensures strategy errors do not become system-level failures.

⸻

6. Strategy Categories (Initial Set)

To ensure diversification, strategies should represent different behaviors:

Category	Behavior Type	Example Use
Trend Following	Momentum continuation	Strong directional markets
Mean Reversion	Short-term pullbacks	Range-bound markets
Volatility Expansion	Breakout after compression	Regime transitions
Carry/Funding	Structural edge	Passive yield capture
Liquidity/Flow	Order book imbalances	Short-term microstructure

Each category tends to perform best in different regimes, enabling adaptive capital rotation.

⸻

7. Strategy Fitness Tracking

The system tracks performance of each strategy within each market regime.

Metrics include:
	•	Average PnL per trade
	•	Win/loss stability
	•	Drawdown contribution

This data feeds the allocation layer, not the strategy itself.

⸻

8. Capital Allocation Process

Allocation is influenced by:
	1.	Strategy historical fitness in the current regime
	2.	Confidence weighting based on data size
	3.	Meta-Risk Governor limits on allocation speed

This ensures capital shifts are:
	•	Data-driven
	•	Gradual
	•	Risk-aware

⸻

9. Adding a New Strategy

To integrate a new strategy:
	1.	Create a module in strategies/
	2.	Ensure it outputs valid proposal objects
	3.	Backtest and paper trade
	4.	Start with small allocation
	5.	Let the system evaluate its fitness

No changes are required in the risk engine for new strategies.

⸻

10. Removing or Disabling Strategies

A strategy may be disabled if:
	•	It consistently underperforms across regimes
	•	Market structure changes invalidate its edge
	•	Risk contribution becomes excessive

Disabling a strategy does not impact the rest of the system due to modular design.

⸻

11. Strategy Risk Boundaries

Even strong strategies are constrained by:
	•	Portfolio exposure limits
	•	Drawdown protection
	•	Volatility scaling
	•	Incident and crisis controls

This prevents a single strategy from dominating system risk.

⸻

12. Summary

The strategy framework ensures:

✔ Modular, replaceable alpha sources
✔ Strict separation between alpha and risk
✔ Data-driven capital allocation
✔ Natural scaling of successful strategies
✔ Automatic capital reduction for weak strategies

This creates a system where strategies compete for capital based on measured performance, not assumptions.

🛡 Risk Management Framework

1. Philosophy

The system is built on a risk-first principle:

Capital survival is mandatory. Profitability is conditional.

No trade, strategy, or market opportunity is allowed to override core capital protection rules.
Risk controls are multi-layered, independent, and hierarchical — meaning that failure of one layer does not disable the others.

⸻

2. Risk Control Architecture

Risk protection is divided into five tiers:

Tier	Purpose	Scope
Tier 1	Trade-Level Controls	Individual position risk
Tier 2	Portfolio Risk Controls	Total exposure and drawdown
Tier 3	Market Condition Controls	Environment-based scaling
Tier 4	Incident & Crisis Controls	Extreme event handling
Tier 5	Meta-Risk Governance	Controls the risk system itself


⸻

3. Tier 1 — Trade-Level Risk Controls

These rules apply to every trade proposal before execution.

Position Size Scaling

Trade size is dynamically reduced based on:
	•	Current volatility
	•	Strategy confidence (optional)
	•	Capital Preservation Mode
	•	Regime risk bias

Per-Trade Exposure Limits

Each trade is checked against:
	•	Maximum allowed position size per symbol
	•	Maximum leverage per position
	•	Distance to liquidation threshold

If a proposal violates these limits, it is scaled down or rejected.

⸻

4. Tier 2 — Portfolio Risk Controls

These monitor total system exposure.

Maximum Portfolio Exposure

Limits:
	•	Gross exposure
	•	Net directional bias
	•	Per-symbol concentration

Drawdown Protection

If daily drawdown exceeds predefined thresholds:
	•	Trade size reductions begin
	•	Risk becomes progressively defensive
	•	Severe drawdowns can trigger a kill-switch

Value-at-Risk (VaR) Cap

The system estimates portfolio tail risk.
If VaR exceeds limits:
	•	New trades are reduced or blocked
	•	Exposure must decline before risk resumes

⸻

5. Tier 3 — Market Condition Controls

Risk adjusts based on the market environment.

Volatility Scaling

When market volatility rises:
	•	Position sizes are reduced
	•	Risk limits tighten
	•	Strategy aggressiveness decreases

Regime-Based Risk Bias

Using historical regime memory:
	•	Risk increases slightly in historically favorable environments
	•	Risk decreases in historically adverse regimes

These adjustments are gradual and governed.

⸻

6. Tier 4 — Incident & Crisis Management

This layer activates during abnormal or dangerous situations.

Incident Triggers

An incident may open when:
	•	Rapid drawdown occurs
	•	API failures repeat
	•	Exposure breaches critical thresholds
	•	Abnormal market volatility spikes

During an Active Incident
	•	Trading activity is reduced or halted
	•	Capital Preservation Mode activates
	•	System stability is continuously evaluated

Incident Closure

An incident closes only after:
	•	Risk metrics return to safe levels
	•	Market conditions stabilize for a defined period
	•	No ongoing anomalies exist

A post-incident report is generated for review.

⸻

7. Capital Preservation Mode (CPM)

This is a post-stress defensive state.

When activated:
	•	Position sizes are reduced
	•	Risk thresholds tighten
	•	VaR limits are lowered
	•	System gradually ramps back to normal

This prevents loss clustering, a major cause of system failure.

⸻

8. Kill-Switch Mechanisms

Multiple independent kill-switches exist:

Type	Trigger
Manual	Operator intervention
Risk	Drawdown or VaR breach
Infrastructure	Repeated API errors
Margin	Dangerous liquidation proximity

When triggered:
	•	New trades stop immediately
	•	Existing exposure is managed defensively

⸻

9. Adaptive Risk Controls

The system includes controlled learning mechanisms:

Risk Effectiveness Scoring

Measures whether past risk interventions:
	•	Prevented losses
	•	Were overly restrictive

Self-Tuning Risk Limits

Risk thresholds adjust slowly based on long-term effectiveness.

Regime Memory

The system learns which environments are historically risky or favorable.

⸻

10. Meta-Risk Governor

This is the safety system for the risk system.

It ensures:
	•	Risk parameters change slowly
	•	Strategy allocations cannot swing abruptly
	•	Total daily adaptation is limited
	•	Learning is disabled during crises

This prevents feedback loops and overreaction.

⸻

11. Monitoring & Transparency

All risk decisions are:
	•	Logged with timestamps and reasoning
	•	Visible in the dashboard
	•	Included in periodic reports

Incidents produce structured post-mortem summaries.

The system is designed to be explainable, auditable, and supervised.

⸻

12. Summary

The risk framework combines:

✔ Real-time protection
✔ Portfolio-level oversight
✔ Market-aware scaling
✔ Crisis containment
✔ Controlled adaptive learning
✔ Governance against overreaction

This creates a system designed not just to trade — but to survive long enough to compound.

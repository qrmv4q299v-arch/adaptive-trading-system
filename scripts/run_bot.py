"""
scripts/run_bot.py

HARS Bot Runner (Lighter)
- StrategyRouter -> ExecutionProposal
- RiskGate -> allocation multiplier / pause / circuit-break
- Execution (Lighter) -> idempotent, allocation-enforced, state-tracked
- Portfolio accounting -> exposure + realized PnL (minimal, safe)
- Kill-switch -> repeated API failures
- Dashboard -> FastAPI read-only endpoints
- Alerts -> Telegram (optional)

This file is orchestration only. It does NOT change frozen strategy logic.
"""

from __future__ import annotations

import os
import json
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List, Tuple

# =========================
# LOGGING
# =========================

logger = logging.getLogger("hars.run_bot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    # Optional file log
    log_path = os.getenv("HARS_LOG_PATH", "run_bot.log")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    logger.addHandler(fh)

# =========================
# IMPORTS (project)
# =========================

from strategy.strategy_router import (
    StrategyRouter,
    RouterConfig,
    RiskState,
    HTFRegime,
    ExecutionProposal,
    Basket,
    Module,
    AuctionContext,
)

# ---- EXECUTION MODULE IMPORTS ----
# Change these imports if your execution module path differs.
# Example: from execution.lighter_execution import ...
try:
    from execution.lighter_execution import (  # <-- adjust if needed
        LighterApiClient,
        ExecutionTracker,
        ProposalState,
        execute_trade_lighter,
        APIError,
    )
except Exception as e:
    raise ImportError(
        "Could not import execution layer. "
        "Expected: execution/lighter_execution.py with LighterApiClient, ExecutionTracker, ProposalState, execute_trade_lighter.\n"
        f"Import error: {e}"
    )

# =========================
# OPTIONAL: FASTAPI DASHBOARD
# =========================

FASTAPI_AVAILABLE = True
try:
    from fastapi import FastAPI
    import uvicorn
except Exception:
    FASTAPI_AVAILABLE = False

# =========================
# OPTIONAL: TELEGRAM ALERTS
# =========================

def _safe_env(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    return v.strip() if v else default

@dataclass
class TelegramAlerter:
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False

    def __post_init__(self) -> None:
        self.enabled = bool(self.bot_token and self.chat_id)

    async def send(self, text: str) -> None:
        if not self.enabled:
            return
        # Avoid adding new deps: do a simple HTTP call in a thread.
        def _send_blocking() -> None:
            import urllib.parse
            import urllib.request
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = urllib.parse.urlencode({"chat_id": self.chat_id, "text": text}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()

        try:
            await asyncio.to_thread(_send_blocking)
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")

# =========================
# CONFIG
# =========================

@dataclass
class BotConfig:
    # Symbols
    symbols: List[str] = field(default_factory=lambda: ["BTC/USD", "ETH/USD"])

    # Loop timing
    loop_interval_sec: float = 2.0
    price_timeout_sec: float = 2.0
    execution_timeout_sec: float = 7.0

    # Risk / kill-switch
    api_failure_kill_threshold: int = 6  # consecutive failures before kill-switch
    api_failure_decay_sec: float = 60.0  # decay failure streak over time

    # Dashboard
    dashboard_enabled: bool = True
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000

    # Lighter
    lighter_url: str = "https://api.lighter.xyz"
    lighter_key: str = ""
    lighter_secret: str = ""
    account_index: int = 0
    api_key_index: int = 0

    # Telegram alerts
    telegram_token: str = ""
    telegram_chat_id: str = ""

    @staticmethod
    def from_env() -> "BotConfig":
        # Symbols: "BTC/USD,ETH/USD"
        sym_raw = _safe_env("HARS_SYMBOLS", "BTC/USD,ETH/USD")
        symbols = [s.strip() for s in sym_raw.split(",") if s.strip()]

        cfg = BotConfig(
            symbols=symbols,
            loop_interval_sec=float(_safe_env("HARS_LOOP_INTERVAL_SEC", "2.0")),
            price_timeout_sec=float(_safe_env("HARS_PRICE_TIMEOUT_SEC", "2.0")),
            execution_timeout_sec=float(_safe_env("HARS_EXEC_TIMEOUT_SEC", "7.0")),
            api_failure_kill_threshold=int(_safe_env("HARS_API_FAIL_KILL", "6")),
            api_failure_decay_sec=float(_safe_env("HARS_API_FAIL_DECAY_SEC", "60.0")),
            dashboard_enabled=_safe_env("HARS_DASHBOARD", "1") in ("1", "true", "True"),
            dashboard_host=_safe_env("HARS_DASHBOARD_HOST", "0.0.0.0"),
            dashboard_port=int(_safe_env("HARS_DASHBOARD_PORT", "8000")),
            lighter_url=_safe_env("LIGHTER_URL", "https://api.lighter.xyz"),
            lighter_key=_safe_env("LIGHTER_KEY", ""),
            lighter_secret=_safe_env("LIGHTER_SECRET", ""),
            account_index=int(_safe_env("LIGHTER_ACCOUNT_INDEX", "0")),
            api_key_index=int(_safe_env("LIGHTER_API_KEY_INDEX", "0")),
            telegram_token=_safe_env("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=_safe_env("TELEGRAM_CHAT_ID", ""),
        )
        return cfg

# =========================
# PORTFOLIO STATE (minimal)
# =========================

@dataclass
class Position:
    symbol: str
    direction: str  # LONG/SHORT
    size: float
    entry_price: float
    entry_time: str

@dataclass
class PortfolioState:
    """
    Minimal safe accounting:
    - Exposure: sum(size * price) per symbol + total
    - Realized PnL: tracked from closed trades if you feed exits later
    - For now: we track entry-only executions + exposure snapshot
    """
    positions: Dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    exposure_usd: float = 0.0
    last_update_iso: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def update_exposure(self, prices: Dict[str, float]) -> None:
        exp = 0.0
        for sym, pos in self.positions.items():
            px = float(prices.get(sym, pos.entry_price))
            exp += abs(pos.size) * px
        self.exposure_usd = exp
        self.last_update_iso = datetime.utcnow().isoformat()

# =========================
# MARKET DATA (simple price fetch)
# =========================

class PriceFeed:
    """
    Keep this minimal. Replace with real Lighter websocket/REST later.
    For now, we rely on the execution layer reference price only for logs/risk.
    """
    async def get_latest_price(self, symbol: str) -> float:
        # Placeholder: you should replace with real price feed.
        # If you already have a price feed module, import and use it here.
        raise NotImplementedError("Implement PriceFeed.get_latest_price()")

# =========================
# REGIME ENGINE (stub)
# =========================

class RegimeEngine:
    """
    Replace with your actual HTF regime engine.
    Output MUST be HTFRegime enum.
    """
    def __init__(self) -> None:
        self.prev: Dict[str, HTFRegime] = {}

    def get_prev(self, symbol: str) -> Optional[HTFRegime]:
        return self.prev.get(symbol)

    def set_prev(self, symbol: str, regime: HTFRegime) -> None:
        self.prev[symbol] = regime

    async def compute_regime(self, symbol: str, snapshot: Dict[str, Any]) -> HTFRegime:
        # Minimal placeholder: always BALANCED
        return HTFRegime.BALANCED

# =========================
# STRATEGIES (stub registry)
# =========================

class BaseStrategy:
    name: str = "base"

    def propose(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Dict[str, Any],
    ) -> Optional[ExecutionProposal]:
        return None

class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def propose(self, symbol: str, snapshot: Dict[str, Any], regime: HTFRegime, context: Dict[str, Any]) -> Optional[ExecutionProposal]:
        # Stub: no trade
        return None

class TrendContinuationStrategy(BaseStrategy):
    name = "trend_continuation"

    def propose(self, symbol: str, snapshot: Dict[str, Any], regime: HTFRegime, context: Dict[str, Any]) -> Optional[ExecutionProposal]:
        # Stub: no trade
        return None

class LiquidityRaidStrategy(BaseStrategy):
    name = "liquidity_raid"

    def propose(self, symbol: str, snapshot: Dict[str, Any], regime: HTFRegime, context: Dict[str, Any]) -> Optional[ExecutionProposal]:
        # Stub: no trade
        return None

def build_strategy_registry() -> Dict[str, Any]:
    """
    Replace these with your real strategies as you implement them.
    Keys MUST match RouterConfig priority names.
    """
    return {
        "mean_reversion": MeanReversionStrategy(),
        "trend_continuation": TrendContinuationStrategy(),
        "liquidity_raid": LiquidityRaidStrategy(),
    }

# =========================
# RISK GATE (minimal safe stub)
# =========================

class RiskGate:
    """
    Replace with your real RiskBrain/RiskGate.
    Must return: (action: str, allocation_multiplier: float, reason: str)
    """
    def assess_proposal(self, proposal: ExecutionProposal, active_trades: List[Any], portfolio_state: Dict[str, Any]) -> Tuple[str, float, str]:
        # Minimal safe default: execute with 1.0
        return ("EXECUTE", 1.0, "default")

# =========================
# SHARED RUNTIME STATE (for dashboard)
# =========================

@dataclass
class RuntimeState:
    started_iso: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_tick_iso: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    kill_switch: bool = False
    api_failure_streak: int = 0
    last_api_failure_iso: Optional[str] = None

    last_regime: Dict[str, str] = field(default_factory=dict)
    last_proposal: Dict[str, Optional[Dict[str, Any]]] = field(default_factory=dict)

    last_executions: List[Dict[str, Any]] = field(default_factory=list)
    portfolio: PortfolioState = field(default_factory=PortfolioState)

    def push_execution(self, rec: Dict[str, Any], max_keep: int = 200) -> None:
        self.last_executions.append(rec)
        if len(self.last_executions) > max_keep:
            self.last_executions = self.last_executions[-max_keep:]

# =========================
# DASHBOARD
# =========================

def build_dashboard_app(state: RuntimeState) -> "FastAPI":
    app = FastAPI(title="HARS Dashboard (read-only)")

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "ok": True,
            "started": state.started_iso,
            "last_tick": state.last_tick_iso,
            "kill_switch": state.kill_switch,
            "api_failure_streak": state.api_failure_streak,
        }

    @app.get("/state")
    def get_state() -> Dict[str, Any]:
        return {
            "started": state.started_iso,
            "last_tick": state.last_tick_iso,
            "kill_switch": state.kill_switch,
            "api_failure_streak": state.api_failure_streak,
            "last_api_failure": state.last_api_failure_iso,
            "last_regime": state.last_regime,
            "portfolio": {
                "exposure_usd": state.portfolio.exposure_usd,
                "realized_pnl": state.portfolio.realized_pnl,
                "positions": {k: vars(v) for k, v in state.portfolio.positions.items()},
                "last_update": state.portfolio.last_update_iso,
            },
        }

    @app.get("/proposals")
    def proposals() -> Dict[str, Any]:
        return state.last_proposal

    @app.get("/executions")
    def executions(limit: int = 50) -> Dict[str, Any]:
        limit = max(1, min(500, int(limit)))
        return {"executions": state.last_executions[-limit:]}

    return app

async def run_dashboard(state: RuntimeState, host: str, port: int) -> None:
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI/uvicorn not installed. Dashboard disabled.")
        return

    app = build_dashboard_app(state)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    # uvicorn is blocking; run it in a thread
    await asyncio.to_thread(server.run)

# =========================
# BOT LOOP
# =========================

def _now_iso() -> str:
    return datetime.utcnow().isoformat()

async def hars_main_loop(
    cfg: BotConfig,
    lighter: LighterApiClient,
    router: StrategyRouter,
    risk_gate: RiskGate,
    price_feed: PriceFeed,
    regime_engine: RegimeEngine,
    tracker: ExecutionTracker,
    state: RuntimeState,
    alerter: TelegramAlerter,
) -> None:
    logger.info(f"Bot loop starting for symbols={cfg.symbols}, interval={cfg.loop_interval_sec}s")

    # Initialize tracking for proposals as they appear (dynamic proposals)
    # Tracker already maintains states per proposal_id.

    last_failure_decay_ts = time.time()

    while True:
        tick_start = time.time()
        state.last_tick_iso = _now_iso()

        # Decay API failure streak slowly (so we recover after a calm period)
        now_ts = time.time()
        if cfg.api_failure_streak_decay_sec := cfg.api_failure_decay_sec:
            if (now_ts - last_failure_decay_ts) >= cfg.api_failure_decay_sec and state.api_failure_streak > 0:
                state.api_failure_streak = max(0, state.api_failure_streak - 1)
                last_failure_decay_ts = now_ts

        # Kill-switch hard stop (router will also refuse, but we stop loop actions)
        if state.kill_switch:
            await asyncio.sleep(cfg.loop_interval_sec)
            continue

        # Per-symbol processing
        prices: Dict[str, float] = {}

        for symbol in cfg.symbols:
            try:
                # 1) market snapshot (placeholder)
                snapshot: Dict[str, Any] = {}

                # 2) regime
                prev_reg = regime_engine.get_prev(symbol)
                regime = await regime_engine.compute_regime(symbol, snapshot)
                regime_engine.set_prev(symbol, regime)
                state.last_regime[symbol] = regime.value

                # 3) risk_state for router selection (not sizing)
                router_risk = RiskState(
                    kill_switch=state.kill_switch,
                    risk_level="CIRCUIT_BREAK" if state.kill_switch else "GREEN",
                    vol_spike=False,
                    api_failure_streak=state.api_failure_streak,
                )

                # 4) route -> proposal
                proposal = router.route(
                    symbol=symbol,
                    snapshot=snapshot,
                    regime=regime,
                    context={},
                    risk_state=router_risk,
                    prev_regime=prev_reg,
                )

                state.last_proposal[symbol] = vars(proposal) if proposal else None

                if proposal is None:
                    continue

                # Ensure proposal_id exists and is unique (strategies should set it; we enforce fallback)
                if not proposal.proposal_id:
                    # frozen dataclass may be frozen in your strategies; so ideally strategies set proposal_id themselves
                    # If you want auto IDs, do it inside strategies at proposal creation time.
                    continue

                # 5) risk gate (sizing / pause)
                action, alloc_mult, reason = risk_gate.assess_proposal(proposal, [], {
                    "exposure_usd": state.portfolio.exposure_usd,
                    "realized_pnl": state.portfolio.realized_pnl,
                })

                if action in ("PAUSE_TRADES", "CIRCUIT_BREAK"):
                    logger.warning(f"RiskGate blocked {proposal.proposal_id}: action={action} reason={reason}")
                    continue

                # 6) price (for reference only)
                try:
                    px = await asyncio.wait_for(
                        price_feed.get_latest_price(symbol),
                        timeout=cfg.price_timeout_sec,
                    )
                except Exception:
                    # If you don't have price feed yet, allow execution to continue only if proposal.entry_price exists.
                    px = float(proposal.entry_price)

                prices[symbol] = px

                # 7) execute (idempotent via proposal_id in your execution layer)
                exec_rec = await asyncio.wait_for(
                    execute_trade_lighter(
                        proposal=proposal,
                        allocation_multiplier=float(alloc_mult),
                        reference_price=float(px),
                        lighter_client=lighter,
                        execution_tracker=tracker,
                    ),
                    timeout=cfg.execution_timeout_sec,
                )

                if exec_rec:
                    state.push_execution(exec_rec)

                    # Minimal portfolio tracking: treat each execution as opening/adding position
                    # (When you add exits, you’ll update realized_pnl and remove positions.)
                    side = exec_rec.get("direction", proposal.direction)
                    executed_size = float(exec_rec.get("executed_size", 0.0))
                    executed_price = float(exec_rec.get("executed_price", proposal.entry_price))

                    if executed_size > 0:
                        state.portfolio.positions[symbol] = Position(
                            symbol=symbol,
                            direction=side,
                            size=executed_size,
                            entry_price=executed_price,
                            entry_time=exec_rec.get("timestamp", _now_iso()),
                        )
                        state.portfolio.update_exposure(prices)

            except APIError as e:
                # Count API failures and kill-switch if too many
                state.api_failure_streak += 1
                state.last_api_failure_iso = _now_iso()
                logger.error(f"APIError for {symbol}: {e}")

                if state.api_failure_streak >= cfg.api_failure_kill_threshold:
                    state.kill_switch = True
                    msg = f"🛑 KILL SWITCH: API failures streak={state.api_failure_streak} threshold={cfg.api_failure_kill_threshold}"
                    logger.critical(msg)
                    await alerter.send(msg)

            except Exception as e:
                logger.error(f"Unexpected error in loop for {symbol}: {e}", exc_info=True)

        # Adaptive sleep
        elapsed = time.time() - tick_start
        sleep_for = max(0.25, cfg.loop_interval_sec - elapsed)
        await asyncio.sleep(sleep_for)

# =========================
# BOOTSTRAP
# =========================

async def main() -> None:
    cfg = BotConfig.from_env()

    if not cfg.lighter_key or not cfg.lighter_secret:
        logger.warning("LIGHTER_KEY / LIGHTER_SECRET not set. Execution will fail in live mode.")
        # You can still run dashboard + dry components.

    alerter = TelegramAlerter(
        bot_token=cfg.telegram_token,
        chat_id=cfg.telegram_chat_id,
    )

    # Strategies + router
    strategies = build_strategy_registry()
    router = StrategyRouter(
        strategies=strategies,
        config=RouterConfig(),  # you can tune this later or load from json/env
    )

    # Risk gate & regime engine & price feed
    risk_gate = RiskGate()
    regime_engine = RegimeEngine()

    # IMPORTANT: replace with your real price feed module when ready
    # For now this will raise NotImplemented unless you implement it.
    price_feed = PriceFeed()

    # Lighter client
    lighter = LighterApiClient(
        key=cfg.lighter_key,
        secret=cfg.lighter_secret,
        account_index=cfg.account_index,
        api_key_index=cfg.api_key_index,
        base_url=cfg.lighter_url,
    )

    tracker = ExecutionTracker()
    runtime_state = RuntimeState()

    # Dashboard task
    tasks = []
    if cfg.dashboard_enabled:
        tasks.append(asyncio.create_task(run_dashboard(
            runtime_state, host=cfg.dashboard_host, port=cfg.dashboard_port
        )))
        logger.info(f"Dashboard enabled on http://{cfg.dashboard_host}:{cfg.dashboard_port}")

    # Bot task
    tasks.append(asyncio.create_task(hars_main_loop(
        cfg=cfg,
        lighter=lighter,
        router=router,
        risk_gate=risk_gate,
        price_feed=price_feed,
        regime_engine=regime_engine,
        tracker=tracker,
        state=runtime_state,
        alerter=alerter,
    )))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Shutdown requested by user (Ctrl+C).")

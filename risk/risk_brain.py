from risk.volatility_model import VolatilityModel
import time

class RiskBrain:
    def __init__(self, portfolio_state):
        self.portfolio = portfolio_state
        self.vol_model = VolatilityModel()

        # Exposure limits
        self.max_position_per_symbol = 5.0
        self.max_total_exposure = 10.0
        self.daily_loss_limit = -1000.0

        # Drawdown tracking
        self.equity_peak = 0.0
        self.drawdown = 0.0
        self.drawdown_soft_limit = -500.0
        self.drawdown_hard_limit = -1500.0

        # Kill switch
        self.kill_switch_active = False

        # --- CPM STATE ---
        self.cpm_active = False
        self.cpm_trigger_level = -800.0      # Enter CPM
        self.cpm_recovery_level = -300.0     # Exit CPM
        self.cpm_size_multiplier = 0.3       # Trade at 30% size
        self.cpm_start_time = None
        self.cpm_min_duration = 3600         # 1 hour minimum

    # ------------------------
    # MARKET & DRAW DOWN UPDATES
    # ------------------------

    def update_market_state(self, market_data):
        self.vol_model.update(market_data)

    def update_drawdown(self):
        equity = self.portfolio.total_pnl()

        if equity > self.equity_peak:
            self.equity_peak = equity

        self.drawdown = equity - self.equity_peak

    # ------------------------
    # CPM LOGIC
    # ------------------------

    def update_cpm_state(self):
        if not self.cpm_active and self.drawdown <= self.cpm_trigger_level:
            self.cpm_active = True
            self.cpm_start_time = time.time()
            print("🛑 Entering CAPITAL PRESERVATION MODE")

        if self.cpm_active:
            time_in_cpm = time.time() - self.cpm_start_time
            if (
                self.drawdown >= self.cpm_recovery_level
                and time_in_cpm >= self.cpm_min_duration
            ):
                self.cpm_active = False
                print("✅ Exiting CAPITAL PRESERVATION MODE")

    def cpm_multiplier(self):
        return self.cpm_size_multiplier if self.cpm_active else 1.0

    # ------------------------
    # DRAWDOWN SCALING
    # ------------------------

    def drawdown_multiplier(self):
        if self.drawdown <= self.drawdown_hard_limit:
            self.kill_switch_active = True
            return 0.0

        if self.drawdown <= self.drawdown_soft_limit:
            range_dd = self.drawdown_hard_limit - self.drawdown_soft_limit
            progress = (self.drawdown - self.drawdown_soft_limit) / range_dd
            return max(0.2, 1.0 + progress)

        return 1.0

    # ------------------------
    # MAIN RISK EVALUATION
    # ------------------------

    def evaluate_trade(self, proposal):
        self.update_drawdown()
        self.update_cpm_state()

        if self.kill_switch_active:
            return False, 0.0, "Kill switch active"

        total_pnl = self.portfolio.total_pnl()
        if total_pnl <= self.daily_loss_limit:
            self.kill_switch_active = True
            return False, 0.0, "Daily loss limit breached"

        symbol = proposal["symbol"]
        direction = proposal["direction"]
        size = proposal["size"]

        # --- Combine ALL risk multipliers ---
        dd_mult = self.drawdown_multiplier()
        vol_mult = self.vol_model.risk_multiplier()
        cpm_mult = self.cpm_multiplier()

        combined_mult = dd_mult * vol_mult * cpm_mult
        size *= combined_mult

        if size <= 0:
            return False, 0.0, "Risk scaling reduced size to zero"

        signed_size = size if direction == "LONG" else -size
        current_positions = self.portfolio.exposure()
        current_symbol_size = current_positions.get(symbol, 0.0)

        # Symbol cap
        new_symbol_size = current_symbol_size + signed_size
        if abs(new_symbol_size) > self.max_position_per_symbol:
            allowed_size = self.max_position_per_symbol - abs(current_symbol_size)
            if allowed_size <= 0:
                return False, 0.0, "Symbol exposure limit reached"
            size = min(size, allowed_size)

        # Portfolio cap
        total_exposure = sum(abs(v) for v in current_positions.values())
        if total_exposure + abs(size) > self.max_total_exposure:
            allowed = self.max_total_exposure - total_exposure
            if allowed <= 0:
                return False, 0.0, "Total exposure limit reached"
            size = min(size, allowed)

        mode = "CPM" if self.cpm_active else "NORMAL"
        return True, size, f"{mode} (DD x{dd_mult:.2f} * VOL x{vol_mult:.2f} * CPM x{cpm_mult:.2f})"

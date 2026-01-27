class RiskBrain:
    def __init__(self, portfolio_state):
        self.portfolio = portfolio_state

        # --- Risk Limits (configurable later) ---
        self.max_position_per_symbol = 5.0
        self.max_total_exposure = 10.0
        self.daily_loss_limit = -1000.0  # stop trading after this loss

        self.kill_switch_active = False

    def evaluate_trade(self, proposal):
        """
        Returns:
            approved (bool),
            adjusted_size (float),
            reason (str)
        """

        if self.kill_switch_active:
            return False, 0.0, "Kill switch active"

        total_pnl = self.portfolio.total_pnl()
        if total_pnl <= self.daily_loss_limit:
            self.kill_switch_active = True
            return False, 0.0, "Daily loss limit breached — kill switch activated"

        symbol = proposal["symbol"]
        direction = proposal["direction"]
        size = proposal["size"]

        signed_size = size if direction == "LONG" else -size

        current_positions = self.portfolio.exposure()
        current_symbol_size = current_positions.get(symbol, 0.0)

        # --- Per-symbol limit ---
        new_symbol_size = current_symbol_size + signed_size
        if abs(new_symbol_size) > self.max_position_per_symbol:
            allowed_size = self.max_position_per_symbol - abs(current_symbol_size)
            if allowed_size <= 0:
                return False, 0.0, "Symbol exposure limit reached"
            size = min(size, allowed_size)

        # --- Total exposure limit ---
        total_exposure = sum(abs(v) for v in current_positions.values())
        if total_exposure + abs(size) > self.max_total_exposure:
            allowed = self.max_total_exposure - total_exposure
            if allowed <= 0:
                return False, 0.0, "Total exposure limit reached"
            size = min(size, allowed)

        return True, size, "Approved"

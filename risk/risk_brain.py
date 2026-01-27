from risk.regime_model import RegimeModel
from risk.stop_model import StopModel

class RiskBrain:
    def __init__(self, portfolio_state, vol_model):
        self.portfolio = portfolio_state
        self.vol_model = vol_model
        self.regime_model = RegimeModel()
        self.stop_model = StopModel()

        self.max_position_per_symbol = 5.0
        self.max_total_exposure = 10.0
        self.daily_loss_limit = -1000.0

        self.kill_switch_active = False
        self.peak_equity = 0.0
        self.max_drawdown_limit = 0.2
        self.cpm_active = False

    def update_market_state(self, market_data):
        self.vol_model.update(market_data)
        self.regime_model.update(market_data["price"])

    def update_equity_peak(self):
        equity = self.portfolio.total_pnl()
        self.peak_equity = max(self.peak_equity, equity)

    def drawdown_multiplier(self):
        equity = self.portfolio.total_pnl()
        if self.peak_equity == 0:
            return 1.0
        dd = (self.peak_equity - equity) / abs(self.peak_equity)
        if dd > self.max_drawdown_limit:
            self.cpm_active = True
            return 0.3
        elif dd > self.max_drawdown_limit * 0.5:
            return 0.6
        return 1.0

    def cpm_multiplier(self):
        return 0.5 if self.cpm_active else 1.0

    def evaluate_trade(self, proposal, market_price: float):
        if self.kill_switch_active:
            return False, 0.0, None, None, "Kill switch active"

        total_pnl = self.portfolio.total_pnl()
        if total_pnl <= self.daily_loss_limit:
            self.kill_switch_active = True
            return False, 0.0, None, None, "Daily loss limit breached"

        symbol = proposal["symbol"]
        direction = proposal["direction"]
        size = proposal["size"]

        dd_mult = self.drawdown_multiplier()
        vol_mult = self.vol_model.risk_multiplier()
        cpm_mult = self.cpm_multiplier()
        regime_mult = self.regime_model.risk_multiplier()

        combined_mult = dd_mult * vol_mult * cpm_mult * regime_mult
        size *= combined_mult

        signed_size = size if direction == "LONG" else -size
        current_positions = self.portfolio.exposure()
        current_symbol_size = current_positions.get(symbol, 0.0)

        new_symbol_size = current_symbol_size + signed_size
        if abs(new_symbol_size) > self.max_position_per_symbol:
            allowed_size = self.max_position_per_symbol - abs(current_symbol_size)
            if allowed_size <= 0:
                return False, 0.0, None, None, "Symbol exposure limit reached"
            size = min(size, allowed_size)

        total_exposure = sum(abs(v) for v in current_positions.values())
        if total_exposure + abs(size) > self.max_total_exposure:
            allowed = self.max_total_exposure - total_exposure
            if allowed <= 0:
                return False, 0.0, None, None, "Total exposure limit reached"
            size = min(size, allowed)

        regime = self.regime_model.get_regime()

        stop_loss, take_profit = self.stop_model.compute_stops(
            price=market_price,
            direction=direction,
            regime=regime,
            vol_multiplier=vol_mult
        )

        mode = "CPM" if self.cpm_active else "NORMAL"

        return True, size, stop_loss, take_profit, f"{mode} | Regime={regime} | Mult={combined_mult:.2f}"

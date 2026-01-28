from risk.regime_model import RegimeModel
from risk.volatility_kill_switch import VolatilityKillSwitch
from risk.correlation_model import CorrelationModel
from risk.liquidity_model import LiquidityModel

class RiskBrain:
    def __init__(self, portfolio, vol_model):
        self.portfolio = portfolio
        self.vol_model = vol_model
        self.regime_model = RegimeModel()
        self.kill_switch = VolatilityKillSwitch()
        self.correlation_model = CorrelationModel()
        self.liquidity_model = LiquidityModel()
        self.cpm_active = False

    def update_market_state(self, market_data):
        symbol = market_data.get("symbol", "BTC-PERP")
        price = market_data["price"]

        self.vol_model.update(market_data)
        self.regime_model.update(price)
        self.kill_switch.update(price)
        self.correlation_model.update_price(symbol, price)

    def evaluate_trade(self, proposal, market_price):
        if self.kill_switch.is_active():
            return False, 0, None, None, "VOLATILITY KILL SWITCH ACTIVE"

        base_size = proposal["size"]
        symbol = proposal["symbol"]

        dd_mult = self.drawdown_multiplier()
        vol_mult = self.vol_model.risk_multiplier()
        cpm_mult = self.cpm_multiplier()
        regime_mult = self.regime_model.risk_multiplier()

        corr_exposure = self.correlation_model.correlated_exposure(
            symbol, self.portfolio.open_positions()
        )
        corr_mult = 0.5 if corr_exposure > self.correlation_model.max_cluster_exposure else 1.0

        liquidity_mult = self.liquidity_model.liquidity_multiplier(symbol, base_size, market_price)

        combined_mult = dd_mult * vol_mult * cpm_mult * regime_mult * corr_mult * liquidity_mult
        size = base_size * combined_mult

        sl, tp = self.compute_stops(proposal["direction"], market_price)

        regime = self.regime_model.get_regime()
        mode = "CPM" if self.cpm_active else "NORMAL"

        reason = f"{mode} | Regime={regime} | Size x{combined_mult:.2f}"
        return True, size, sl, tp, reason

    def drawdown_multiplier(self): return 1.0
    def cpm_multiplier(self): return 1.0

    def compute_stops(self, direction, price):
        return (price * 0.98, price * 1.03) if direction == "LONG" else (price * 1.02, price * 0.97)

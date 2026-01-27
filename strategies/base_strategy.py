class BaseStrategy:
    def generate_signal(self, market_data):
        raise NotImplementedError

    def build_proposal(self, signal):
        return {
            "symbol": signal["symbol"],
            "direction": signal["direction"],
            "size": signal["size"],
            "strategy_name": self.__class__.__name__,
            "timestamp": signal["timestamp"],
        }

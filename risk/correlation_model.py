import numpy as np
from collections import defaultdict

class CorrelationModel:
    def __init__(self):
        self.price_history = defaultdict(list)
        self.window = 50

        self.high_corr_threshold = 0.75
        self.max_cluster_exposure = 2.0  # Max combined exposure for correlated assets

    def update_price(self, symbol, price):
        hist = self.price_history[symbol]
        hist.append(price)
        if len(hist) > self.window:
            hist.pop(0)

    def correlation(self, sym1, sym2):
        h1 = self.price_history[sym1]
        h2 = self.price_history[sym2]

        if len(h1) < 10 or len(h2) < 10:
            return 0

        r1 = np.diff(h1) / h1[:-1]
        r2 = np.diff(h2) / h2[:-1]

        min_len = min(len(r1), len(r2))
        if min_len < 5:
            return 0

        return np.corrcoef(r1[-min_len:], r2[-min_len:])[0, 1]

    def correlated_exposure(self, symbol, portfolio_positions):
        total = 0
        for sym, pos in portfolio_positions.items():
            if sym == symbol:
                continue
            corr = self.correlation(symbol, sym)
            if corr >= self.high_corr_threshold:
                total += abs(pos["size"])
        return total

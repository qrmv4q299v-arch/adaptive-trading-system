class PortfolioState:
    def __init__(self):
        self.positions = {}

    def process_fill(self, fill):
        symbol = fill["symbol"]
        self.positions[symbol] = {
            "size": fill["size"],
            "entry_price": fill["price"],
            "direction": fill["direction"]
        }

    def open_positions(self):
        return self.positions

    def print_summary(self):
        print("📊 Portfolio Positions:")
        for s, p in self.positions.items():
            print(f"  {s} | Size {p['size']} @ {p['entry_price']}")

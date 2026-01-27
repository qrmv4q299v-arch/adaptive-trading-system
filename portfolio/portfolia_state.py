class PortfolioState:
    def __init__(self):
        self.positions = {}  # symbol -> {size, avg_price}
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0

    def process_fill(self, fill):
        symbol = fill["symbol"]
        side = fill["side"]
        size = fill["size"]
        price = fill["price"]

        if symbol not in self.positions:
            self.positions[symbol] = {"size": 0.0, "avg_price": 0.0}

        pos = self.positions[symbol]

        signed_size = size if side == "BUY" else -size

        # If same direction → increase position
        if pos["size"] * signed_size >= 0:
            new_total_size = pos["size"] + signed_size
            if new_total_size != 0:
                pos["avg_price"] = (
                    (pos["avg_price"] * abs(pos["size"]) + price * abs(signed_size))
                    / abs(new_total_size)
                )
            pos["size"] = new_total_size

        # If reducing or flipping
        else:
            closing_size = min(abs(pos["size"]), abs(signed_size))
            pnl = closing_size * (price - pos["avg_price"]) * (1 if pos["size"] > 0 else -1)
            self.realized_pnl += pnl

            pos["size"] += signed_size

            if pos["size"] == 0:
                pos["avg_price"] = 0.0

    def mark_to_market(self, price_feed):
        self.unrealized_pnl = 0.0

        for symbol, pos in self.positions.items():
            if symbol in price_feed and pos["size"] != 0:
                current_price = price_feed[symbol]
                pnl = (current_price - pos["avg_price"]) * pos["size"]
                self.unrealized_pnl += pnl

    def total_pnl(self):
        return self.realized_pnl + self.unrealized_pnl

    def exposure(self):
        return {s: p["size"] for s, p in self.positions.items() if p["size"] != 0}

    def print_summary(self):
        print("\n📊 Portfolio Summary")
        print("Positions:", self.positions)
        print(f"Realized PnL: {self.realized_pnl:.2f}")
        print(f"Unrealized PnL: {self.unrealized_pnl:.2f}")
        print(f"Total PnL: {self.total_pnl():.2f}")

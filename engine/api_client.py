class APIClient:
    def place_order(self, order):
        print(f"📤 Executing slice: {order}")
        return {"price": 50000}  # Simulated fill

    def modify_stop(self, symbol, new_stop):
        print(f"🔄 Updating stop for {symbol} → {new_stop:.2f}")

    def close_partial(self, symbol, size):
        print(f"📉 Closing {size} on {symbol}")

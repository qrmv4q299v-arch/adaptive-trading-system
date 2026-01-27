class APIClient:
    def place_order(self, symbol, side, size, price=None, order_type="market"):
        """
        Sends order to exchange.
        Returns exchange_order_id.
        """
        raise NotImplementedError

    def get_order_status(self, exchange_order_id):
        """
        Returns:
        {
            "status": "NEW | PARTIALLY_FILLED | FILLED | CANCELED",
            "filled_size": float,
            "avg_price": float
        }
        """
        raise NotImplementedError

    def cancel_order(self, exchange_order_id):
        raise NotImplementedError

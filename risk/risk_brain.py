class RiskBrain:
    def evaluate_trade(self, proposal, portfolio_state, market_state):
        """
        Returns:
            approved (bool),
            adjusted_size (float),
            reason (str)
        """
        return True, proposal["size"], "Approved (stub)"

class StrategyAllocator:
    def adjust_size(self, proposal, regime, fitness_score):
        proposal["size"] *= fitness_score
        return proposal

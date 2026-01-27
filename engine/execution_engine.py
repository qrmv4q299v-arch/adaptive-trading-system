class ExecutionEngine:
    def execute(self, approved_proposal):
        print(f"Executing trade: {approved_proposal}")
        return {"status": "FILLED", "filled_size": approved_proposal["size"]}

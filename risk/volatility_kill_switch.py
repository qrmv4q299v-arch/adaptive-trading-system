import numpy as np

class VolatilityKillSwitch:
    def __init__(self):
        self.prices = []
        self.window = 30

        self.trigger_multiple = 3.0   # Spike vs baseline
        self.cooldown_cycles = 20     # Loops before re-enable

        self.kill_active = False
        self.cooldown_left = 0

    def update(self, price):
        self.prices.append(price)
        if len(self.prices) > self.window:
            self.prices.pop(0)

        if len(self.prices) < 10:
            return

        returns = np.diff(self.prices) / self.prices[:-1]
        recent_vol = np.std(returns[-5:])
        baseline_vol = np.std(returns[:-5]) if len(returns) > 5 else recent_vol

        if baseline_vol > 0 and recent_vol > baseline_vol * self.trigger_multiple:
            self.kill_active = True
            self.cooldown_left = self.cooldown_cycles

        if self.kill_active:
            self.cooldown_left -= 1
            if self.cooldown_left <= 0:
                self.kill_active = False

    def is_active(self):
        return self.kill_active

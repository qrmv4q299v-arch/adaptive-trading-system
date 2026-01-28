import time

class TimeStopModel:
    def __init__(self):
        # Max lifetime in seconds before forced exit
        self.max_duration = {
            "TREND": 60 * 60 * 6,      # 6 hours
            "CHOP": 60 * 60 * 2,       # 2 hours
            "CRASH": 60 * 30,          # 30 min
            "NEUTRAL": 60 * 60 * 3     # 3 hours
        }

        # Minimum favorable move expected before timeout
        self.min_progress = {
            "TREND": 0.003,
            "CHOP": 0.002,
            "CRASH": 0.004,
            "NEUTRAL": 0.0025
        }

    def should_time_exit(self, entry_price, current_price, entry_time, regime):
        now = time.time()
        duration = now - entry_time

        max_dur = self.max_duration.get(regime, 60 * 60 * 3)
        if duration < max_dur:
            return False

        progress = abs(current_price - entry_price) / entry_price
        min_prog = self.min_progress.get(regime, 0.002)

        return progress < min_prog

# risk/volatility_kill_switch.py
from __future__ import annotations

from typing import Dict, Any


class VolatilityKillSwitch:
    """
    Placeholder for a rule that sets portfolio_state['kill_switch']=True on extreme vol.
    """

    def check(self, snapshot: Dict[str, Any]) -> bool:
        return False
# risk/regime_model.py
from __future__ import annotations

from typing import Dict, Any

from core.contracts import HTFRegime


class RegimeModel:
    """
    Placeholder: later you’ll compute HTF regime from data.
    For now: BALANCED.
    """

    def get_regime(self, snapshot: Dict[str, Any]) -> HTFRegime:
        return HTFRegime.BALANCED
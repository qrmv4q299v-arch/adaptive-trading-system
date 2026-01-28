# strategies/base_strategy.py
from __future__ import annotations

from typing import Dict, Any, Optional

from core.contracts import ExecutionProposal, HTFRegime


class BaseStrategy:
    name: str = "base"

    def propose(
        self,
        symbol: str,
        snapshot: Dict[str, Any],
        regime: HTFRegime,
        context: Dict[str, Any],
    ) -> Optional[ExecutionProposal]:
        raise NotImplementedError
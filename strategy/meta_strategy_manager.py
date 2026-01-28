# strategy/meta_strategy_manager.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class StrategyScore:
    name: str
    score: float


class MetaStrategyManager:
    """
    Placeholder for future learning-based strategy weighting.
    For now, it's a thin registry container.
    """

    def __init__(self) -> None:
        self.scores: Dict[str, float] = {}

    def set_score(self, name: str, score: float) -> None:
        self.scores[name] = float(score)

    def get_score(self, name: str, default: float = 0.0) -> float:
        return float(self.scores.get(name, default))
# strategy/adaptive_allocator.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AllocationDecision:
    allocation_multiplier: float
    reason: str


class AdaptiveAllocator:
    """
    Lightweight sizing helper (NOT risk brain).
    RiskBrain still has final authority.
    """

    def decide(self, base_size: float, multiplier: float) -> AllocationDecision:
        m = max(0.0, min(1.0, float(multiplier)))
        return AllocationDecision(allocation_multiplier=m, reason=f"Allocator multiplier={m}")
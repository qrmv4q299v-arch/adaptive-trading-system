# core/contracts.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Basket(Enum):
    BASKET_1 = "BASKET_1"  # BTC, ETH
    BASKET_2 = "BASKET_2"  # SOL, MATIC, ADA
    BASKET_3 = "BASKET_3"  # AVAX, DOT, LUNA


class Module(Enum):
    MEAN_REVERSION = "MEAN_REVERSION"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    LIQUIDITY_RAID = "LIQUIDITY_RAID"


class HTFRegime(Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    BALANCED = "BALANCED"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True)
class AuctionContext:
    entry_at_val: bool = False
    entry_at_vah: bool = False
    entry_at_value_mid: bool = False
    outside_value_area: bool = False
    sfp_present: bool = False
    delta_aligned: bool = False
    absorption_detected: bool = False
    htf_filter_passed: bool = False
    no_trade_zone_active: bool = False

    def to_dict(self) -> dict:
        return {
            "entry_at_val": self.entry_at_val,
            "entry_at_vah": self.entry_at_vah,
            "entry_at_value_mid": self.entry_at_value_mid,
            "outside_value_area": self.outside_value_area,
            "sfp_present": self.sfp_present,
            "delta_aligned": self.delta_aligned,
            "absorption_detected": self.absorption_detected,
            "htf_filter_passed": self.htf_filter_passed,
            "no_trade_zone_active": self.no_trade_zone_active,
        }


@dataclass(frozen=True)
class ExecutionProposal:
    proposal_id: str
    symbol: str
    direction: str  # "LONG" | "SHORT"
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float

    basket: Basket
    module: Module
    htf_regime: HTFRegime
    auction_context: AuctionContext

    def validate(self) -> Tuple[bool, str]:
        if self.direction not in ("LONG", "SHORT"):
            return False, f"Invalid direction={self.direction} (must be LONG/SHORT)"
        if self.size <= 0:
            return False, f"Invalid size={self.size} (must be > 0)"
        if self.entry_price <= 0:
            return False, f"Invalid entry_price={self.entry_price} (must be > 0)"
        if self.stop_loss <= 0:
            return False, f"Invalid stop_loss={self.stop_loss} (must be > 0)"
        if self.take_profit <= 0:
            return False, f"Invalid take_profit={self.take_profit} (must be > 0)"
        if not isinstance(self.basket, Basket):
            return False, "FROZEN_CONTRACT_VIOLATION: basket must be Basket"
        if not isinstance(self.module, Module):
            return False, "FROZEN_CONTRACT_VIOLATION: module must be Module"
        if not isinstance(self.htf_regime, HTFRegime):
            return False, "FROZEN_CONTRACT_VIOLATION: htf_regime must be HTFRegime"
        if not isinstance(self.auction_context, AuctionContext):
            return False, "FROZEN_CONTRACT_VIOLATION: auction_context must be AuctionContext"
        return True, ""
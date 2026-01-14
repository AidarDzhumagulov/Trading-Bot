from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class FeeInfo:
    """Represents fee information from exchange"""
    cost: Decimal
    currency: str
    
    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["FeeInfo"]:
        if not data or not isinstance(data, dict):
            return None
        return cls(
            cost=Decimal(str(data.get("cost", 0))),
            currency=data.get("currency", "").upper()
        )


@dataclass(frozen=True)
class FillResult:
    """Result of order fill processing"""
    filled_qty: Decimal
    fee_qty: Decimal
    net_qty: Decimal
    order_cost: Decimal


@dataclass(frozen=True)
class CycleStats:
    """Current cycle statistics"""
    total_base_qty: Decimal
    total_quote_spent: Decimal
    avg_price: Decimal


@dataclass(frozen=True)
class BalanceCheckResult:
    """Result of balance validation"""
    available: float
    expected: float
    amount_to_sell: float
    deviation_pct: float
    is_valid: bool
    warning: Optional[str] = None


@dataclass(frozen=True)
class TakeProfitParams:
    """Calculated take profit parameters"""
    effective_tp_pct: float
    tp_price: float
    min_tp_pct: float
    overhead_usd: float


@dataclass(frozen=True)
class DustResult:
    """Result of dust calculation"""
    sellable_amount: float
    new_dust: float

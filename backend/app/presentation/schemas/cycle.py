from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )


class CycleResponse(BaseSchema):
    cycle_id: UUID
    status: str
    filled_orders_count: int
    average_price: float
    tp_order_price: Optional[float] = None
    effective_tp_pct: Optional[float] = Field(None, description="Effective TP %")
    expected_profit: Optional[float] = Field(None, description="Expected profit USDT")
    tp_order_volume: float
    total_quote_spent: float
    current_market_price: Optional[float] = None
    unrealized_profit: Optional[float] = Field(None, description="Unrealized profit USDT")
    accumulated_dust: Optional[float] = Field(None, description="Accumulated dust")


class StatsResponse(BaseSchema):
    total_profit_usdt: float
    completed_cycles: int
    current_cycle: Optional[CycleResponse] = None


class EnhancedStatsResponse(StatsResponse):
    total_invested: float = Field(description="Total USDT invested")
    roi_pct: float = Field(description="Return on Investment %")
    win_rate: float = Field(description="Percentage of profitable cycles")
    avg_profit_per_cycle: float = Field(description="Average profit per cycle USDT")
    avg_cycle_duration_hours: float = Field(description="Average cycle duration in hours")
    best_cycle_profit: float = Field(description="Best cycle profit USDT")
    worst_cycle_profit: float = Field(description="Worst cycle profit USDT")
    current_unrealized_profit: Optional[float] = Field(None, description="Current unrealized profit")
    current_expected_profit: Optional[float] = Field(None, description="Expected profit when TP hits")

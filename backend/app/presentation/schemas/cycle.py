from uuid import UUID
from pydantic import BaseModel, ConfigDict
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
    tp_order_price: float | None
    tp_order_volume: float
    total_quote_spent: float
    current_market_price: float | None = None


class StatsResponse(BaseSchema):
    total_profit_usdt: float
    completed_cycles: int
    current_cycle: CycleResponse | None = None

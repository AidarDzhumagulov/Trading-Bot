from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BotConfigCreate(BaseModel):
    binance_api_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["mWIM2Oyuj26cFgRnZbEeL1ommLyWVZbEhAxGI3o4b2xnkHB901FpvgtHaXtkHO7a"]
    )
    binance_api_secret: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["TIwEZbwUQRz4ywXuzxC9a83ZG4nEZxVqwqCL0nNJCteHfiuxlCiYMyPI1YDhWPQy"]
    )
    symbol: Literal["BTC/USDT", "ETH/USDT"] = Field(
        ...,
        description="Торговая пара. Разрешены только BTC/USDT или ETH/USDT"
    )
    total_budget: float = Field(
        ..., 
        gt=10, 
        description="Сумма USDT для торговли. Минимум 10 USDT. Не должна превышать доступный баланс на бирже."
    )

    grid_length_pct: float = Field(..., gt=0, le=100)
    first_order_offset_pct: float = Field(..., ge=0)
    safety_orders_count: int = Field(..., gt=0, le=50)
    volume_scale_pct: float = Field(..., ge=0)

    grid_shift_threshold_pct: float
    take_profit_pct: float = Field(..., gt=0)


class BotConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool

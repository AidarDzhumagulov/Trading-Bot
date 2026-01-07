from uuid import UUID
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BotConfigCreate(BaseModel):
    binance_api_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["mWIM2Oyuj26cFgRnZbEeL1ommLyWVZbEhAxGI3o4b2xnkHB901FpvgtHaXtkHO7a"],
    )
    binance_api_secret: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["TIwEZbwUQRz4ywXuzxC9a83ZG4nEZxVqwqCL0nNJCteHfiuxlCiYMyPI1YDhWPQy"],
    )
    symbol: Literal["BTC/USDT", "ETH/USDT"] = Field(
        ..., description="Торговая пара. Разрешены только BTC/USDT или ETH/USDT"
    )
    total_budget: float = Field(
        ...,
        gt=10,
        description="Сумма USDT для торговли. Минимум 10 USDT. Не должна превышать доступный баланс на бирже.",
    )

    grid_length_pct: float = Field(..., gt=0, le=100)
    first_order_offset_pct: float = Field(..., ge=0)
    safety_orders_count: int = Field(..., gt=0, le=50)
    volume_scale_pct: float = Field(..., ge=0)

    grid_shift_threshold_pct: float
    take_profit_pct: float = Field(..., gt=0)

    trailing_enabled: bool = Field(
        default=False,
        description="Включить Trailing Take Profit для максимизации прибыли",
    )
    trailing_callback_pct: float = Field(
        default=0.8,
        gt=0,
        le=5.0,
        description=(
            "Процент отката от максимума для продажи. "
            "Рекомендуется: 0.5-1.2%. "
            "Автоматически адаптируется к волатильности (ATR)."
        ),
    )
    trailing_min_profit_pct: float = Field(
        default=1.0,
        gt=0,
        le=10.0,
        description=(
            "Минимальная гарантированная прибыль (защита от убытков). "
            "Если цена падает ниже этого уровня - emergency exit."
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "binance_api_key": "YOUR_API_KEY",
                "binance_api_secret": "YOUR_API_SECRET",
                "symbol": "ETH/USDT",
                "total_budget": 85,
                "grid_length_pct": 5.0,
                "first_order_offset_pct": 0.5,
                "safety_orders_count": 4,
                "volume_scale_pct": 40,
                "grid_shift_threshold_pct": 0.6,
                "take_profit_pct": 1.2,
                "trailing_enabled": True,
                "trailing_callback_pct": 0.8,
                "trailing_min_profit_pct": 1.0,
            }
        }


class BotConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool


class BotConfigUpdate(BaseModel):
    total_budget: Optional[float] = Field(None, gt=10)
    grid_length_pct: Optional[float] = Field(None, gt=0, le=100)
    first_order_offset_pct: Optional[float] = Field(None, ge=0)
    safety_orders_count: Optional[int] = Field(None, gt=0, le=50)
    volume_scale_pct: Optional[float] = Field(None, ge=0)
    grid_shift_threshold_pct: Optional[float] = None
    take_profit_pct: Optional[float] = Field(None, gt=0)

    trailing_enabled: Optional[bool] = None
    trailing_callback_pct: Optional[float] = Field(None, gt=0, le=5.0)
    trailing_min_profit_pct: Optional[float] = Field(None, gt=0, le=10.0)

    class Config:
        json_schema_extra = {
            "example": {
                "trailing_enabled": True,
                "trailing_callback_pct": 0.8,
                "trailing_min_profit_pct": 1.0,
            }
        }


class TrailingStatsResponse(BaseModel):

    trailing_enabled: bool
    config: Optional[dict] = None
    statistics: Optional[dict] = None
    current_cycle: Optional[dict] = None
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "trailing_enabled": True,
                "config": {"callback_pct": 0.8, "min_profit_pct": 1.0},
                "statistics": {
                    "total_cycles_with_trailing": 15,
                    "closed_cycles": 12,
                    "emergency_exits": 1,
                    "success_rate_pct": 91.67,
                    "avg_improvement_pct": 0.75,
                },
                "current_cycle": {
                    "cycle_id": "123e4567-e89b-12d3-a456-426614174000",
                    "activation_price": 3149.26,
                    "max_price_tracked": 3200.00,
                    "current_tp_price": 3174.40,
                    "potential_profit_pct": 5.67,
                },
            }
        }

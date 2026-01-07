from typing import TYPE_CHECKING, List
from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import DcaCycle


class BotConfig(Base):
    __tablename__ = "bot_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    is_active: Mapped[bool] = mapped_column(default=False)

    binance_api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    binance_api_secret: Mapped[str] = mapped_column(Text, nullable=False)

    symbol: Mapped[str] = mapped_column(String(20), default="BTC/USDT")
    total_budget: Mapped[float] = mapped_column(nullable=False)
    grid_length_pct: Mapped[float] = mapped_column(nullable=False)
    first_order_offset_pct: Mapped[float] = mapped_column(nullable=False)
    safety_orders_count: Mapped[int] = mapped_column(nullable=False)
    volume_scale_pct: Mapped[float] = mapped_column(nullable=False)
    grid_shift_threshold_pct: Mapped[float] = mapped_column(nullable=False)
    take_profit_pct: Mapped[float] = mapped_column(nullable=False)

    trailing_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    trailing_callback_pct: Mapped[float] = mapped_column(default=0.8, nullable=False)
    trailing_min_profit_pct: Mapped[float] = mapped_column(default=1.0, nullable=False)

    cycles: Mapped[List["DcaCycle"]] = relationship(back_populates="config")

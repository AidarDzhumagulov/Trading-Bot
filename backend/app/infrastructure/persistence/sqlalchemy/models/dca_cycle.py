from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.infrastructure.persistence.sqlalchemy.models.bot_config import BotConfig
    from app.infrastructure.persistence.sqlalchemy.models.order import Order


class CycleStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"


class DcaCycle(Base):
    __tablename__ = "dca_cycles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    config_id: Mapped[UUID] = mapped_column(ForeignKey("bot_configs.id"))
    status: Mapped[CycleStatus] = mapped_column(default=CycleStatus.OPEN)

    total_base_qty: Mapped[float] = mapped_column(default=0.0)
    total_quote_spent: Mapped[float] = mapped_column(default=0.0)
    avg_price: Mapped[float] = mapped_column(default=0.0)
    current_tp_order_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    initial_first_order_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    profit_usdt: Mapped[Optional[float]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    accumulated_dust: Mapped[float] = mapped_column(default=0.0, nullable=False)

    trailing_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_price_tracked: Mapped[Optional[float]] = mapped_column(nullable=True)
    trailing_activation_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    trailing_activation_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    emergency_exit: Mapped[bool] = mapped_column(default=False, nullable=False)
    emergency_exit_reason: Mapped[Optional[str]] = mapped_column(nullable=True)
    emergency_exit_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    config: Mapped["BotConfig"] = relationship(back_populates="cycles")
    orders: Mapped[List["Order"]] = relationship(back_populates="cycle")

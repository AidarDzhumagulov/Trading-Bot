from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import DcaCycle


class OrderStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FILLED = "filled"
    CANCELED = "canceled"
    PARTIAL = "partial"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("dca_cycles.id"))
    binance_order_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)

    order_type: Mapped[str] = mapped_column(String(20))
    order_index: Mapped[int] = mapped_column(nullable=False)

    price: Mapped[float] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    cycle: Mapped["DcaCycle"] = relationship(back_populates="orders")

from typing import List, TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, update as sa_update, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_api_key
from app.domain.bot_config.repositories import BotConfigRepository
from app.infrastructure.persistence.sqlalchemy.models import BotConfig, DcaCycle
from app.infrastructure.persistence.sqlalchemy.models.dca_cycle import CycleStatus
from app.presentation.schemas.bot_config import BotConfigCreate, BotConfigUpdate

if TYPE_CHECKING:
    from app.infrastructure.persistence.sqlalchemy.models import User


class SqlAlchemyBotConfigRepository(BotConfigRepository):
    def __init__(self, session: AsyncSession, current_user: "User" = None):
        self.session = session
        self.current_user = current_user

    def to_model(self, data: BotConfigCreate) -> BotConfig:
        config_dict = data.model_dump()
        config_dict["binance_api_key"] = encrypt_api_key(config_dict["binance_api_key"])
        config_dict["binance_api_secret"] = encrypt_api_key(
            config_dict["binance_api_secret"]
        )
        return BotConfig(**config_dict)

    async def create(self, bot_config: BotConfigCreate) -> BotConfig:
        bot_config = self.to_model(bot_config)
        bot_config.user = self.current_user
        self.session.add(bot_config)
        try:
            await self.session.commit()
        except SQLAlchemyError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await self.session.refresh(bot_config)
        return bot_config

    async def get(self, id_: UUID) -> BotConfig | None:
        bot_config = await self.session.get(BotConfig, id_)
        if not bot_config:
            raise HTTPException(status_code=404, detail="BotConfig not found")
        return bot_config

    async def delete(self, id_: UUID) -> None:
        await self.session.execute(delete(BotConfig).where(BotConfig.id == id_))
        await self.session.commit()

    async def update(self, id_: UUID, bot_config: BotConfigUpdate) -> BotConfig:
        config = await self.get(id_)
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        stmt = await self.session.execute(
            sa_update(BotConfig)
            .where(BotConfig.id == id_)
            .values(**bot_config.model_dump(exclude_unset=True))
            .returning(BotConfig)
        )
        response = stmt.scalar_one()

        await self.session.commit()
        await self.session.refresh(config)
        return response

    async def exists(self, id_: UUID) -> bool:
        bot_config = await self.session.get(BotConfig, id_)
        return bot_config is not None

    async def list(self) -> List[BotConfig]:
        if not self.current_user:
            raise HTTPException(status_code=401, detail="User not authenticated")

        stmt = (
            select(BotConfig)
            .where(BotConfig.user_id == self.current_user.id)
            .order_by(BotConfig.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_last_active(self) -> BotConfig | None:
        if not self.current_user:
            raise HTTPException(status_code=401, detail="User not authenticated")

        stmt = (
            select(BotConfig)
            .where(
                BotConfig.user_id == self.current_user.id, BotConfig.is_active.is_(True)
            )
            .order_by(BotConfig.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, id_: UUID) -> BotConfig | None:
        if not self.current_user:
            raise HTTPException(status_code=401, detail="User not authenticated")

        bot_config = await self.session.get(BotConfig, id_)
        if not bot_config:
            raise HTTPException(status_code=404, detail="BotConfig not found")

        if bot_config.user_id != self.current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return bot_config

    async def get_trailing_stats(self, config_id: UUID) -> dict:
        config = await self.get(config_id)

        if not config.trailing_enabled:
            return {
                "trailing_enabled": False,
                "message": "Trailing TP отключен для этой конфигурации",
            }

        stmt = select(DcaCycle).where(
            DcaCycle.config_id == config_id, DcaCycle.trailing_active.is_(True)
        )
        result = await self.session.execute(stmt)
        trailing_cycles = result.scalars().all()

        total_with_trailing = len(trailing_cycles)
        emergency_exits = [c for c in trailing_cycles if c.emergency_exit]
        closed_trailing = [c for c in trailing_cycles if c.status == CycleStatus.CLOSED]

        improvements: list[float] = []
        for cycle in closed_trailing:
            if cycle.avg_price and cycle.profit_usdt and cycle.total_quote_spent:
                actual_profit_pct = (cycle.profit_usdt / cycle.total_quote_spent) * 100
                expected_profit_pct = config.take_profit_pct
                improvement = actual_profit_pct - expected_profit_pct
                improvements.append(improvement)

        avg_improvement = sum(improvements) / len(improvements) if improvements else 0

        stmt_active = select(DcaCycle).where(
            DcaCycle.config_id == config_id, DcaCycle.status == CycleStatus.OPEN
        )
        result = await self.session.execute(stmt_active)
        current_cycle = result.scalar_one_or_none()

        current_trailing_status = None
        if current_cycle and current_cycle.trailing_active:
            potential_profit_pct = None
            if current_cycle.max_price_tracked and current_cycle.avg_price:
                potential_profit_pct = (
                    (current_cycle.max_price_tracked / current_cycle.avg_price) - 1
                ) * 100

            current_trailing_status = {
                "cycle_id": str(current_cycle.id),
                "activation_price": current_cycle.trailing_activation_price,
                "max_price_tracked": current_cycle.max_price_tracked,
                "current_tp_price": current_cycle.current_tp_price,
                "potential_profit_pct": potential_profit_pct,
            }

        return {
            "trailing_enabled": True,
            "config": {
                "callback_pct": config.trailing_callback_pct,
                "min_profit_pct": config.trailing_min_profit_pct,
            },
            "statistics": {
                "total_cycles_with_trailing": total_with_trailing,
                "closed_cycles": len(closed_trailing),
                "emergency_exits": len(emergency_exits),
                "success_rate_pct": (
                    (len(closed_trailing) - len(emergency_exits))
                    / len(closed_trailing)
                    * 100
                    if closed_trailing
                    else 0
                ),
                "avg_improvement_pct": round(avg_improvement, 2),
            },
            "current_cycle": current_trailing_status,
        }

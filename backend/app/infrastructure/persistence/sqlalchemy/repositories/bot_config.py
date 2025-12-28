from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.bot_config.repositories import BotConfigRepository
from app.infrastructure.persistence.sqlalchemy.models import BotConfig
from app.presentation.schemas.bot_config import BotConfigCreate


class SqlAlchemyBotConfigRepository(BotConfigRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def to_model(self, data: BotConfigCreate) -> BotConfig:
        return BotConfig(**data.model_dump())

    async def create(self, bot_config: BotConfigCreate) -> BotConfig:
        bot_config = self.to_model(bot_config)
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

    async def update(self, id_: UUID, bot_config: BotConfigCreate) -> BotConfig:
        ...

    async def exists(self, id_: UUID) -> bool:
        ...

    async def list(self) -> List[BotConfig]:
        ...

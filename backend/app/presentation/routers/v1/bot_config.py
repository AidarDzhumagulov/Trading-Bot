from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.domain.bot_manager import BotManager
from app.infrastructure.persistence.sqlalchemy.repositories.bot_config import SqlAlchemyBotConfigRepository
from app.presentation.schemas.bot_config import BotConfigCreate, BotConfigResponse
from app.shared.websocket_registry import websocket_registry

router = APIRouter(prefix="/bot_config", tags=["bot"])


@router.post("/setup/", response_model=BotConfigResponse)
async def setup_bot(config_data: BotConfigCreate, session: AsyncSession = Depends(get_session)):
    repo = SqlAlchemyBotConfigRepository(session)
    try:
        bot_config = await repo.create(bot_config=config_data)
        return BotConfigResponse.model_validate(bot_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/start/")
async def start_bot(config_id: UUID, session: AsyncSession = Depends(get_session)):
    repo = SqlAlchemyBotConfigRepository(session)

    config = await repo.get(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    try:
        result = await BotManager(session).start_first_cycle(config)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/stop/")
async def stop_bot(config_id: UUID, session: AsyncSession = Depends(get_session)):
    repo = SqlAlchemyBotConfigRepository(session)

    config = await repo.get(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    ws_manager = websocket_registry.get(config_id)
    if not ws_manager:
        raise HTTPException(status_code=404, detail="WebSocket manager not found. Bot may not be running.")

    try:
        await ws_manager.stop()
        await websocket_registry.remove(config_id)
        
        config.is_active = False
        await session.commit()

        return {
            "message": "Bot stopped successfully",
            "config_id": str(config_id)
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

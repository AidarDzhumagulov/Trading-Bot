from typing import TYPE_CHECKING, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session, get_current_user
from app.domain.bot_manager import BotManager
from app.infrastructure.persistence.sqlalchemy.repositories.bot_config import (
    SqlAlchemyBotConfigRepository,
)
from app.presentation.schemas.bot_config import (
    BotConfigCreate,
    BotConfigResponse,
    BotConfigUpdate,
    TrailingStatsResponse,
)
from app.shared.websocket_registry import websocket_registry

if TYPE_CHECKING:
    from app.infrastructure.persistence.sqlalchemy.models import User

router = APIRouter(prefix="/bot_config", tags=["bot"])


@router.get("/", response_model=List[BotConfigResponse])
async def list_configs(
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    configs = await repo.list()
    return [BotConfigResponse.model_validate(c) for c in configs]


@router.get("/last-active/", response_model=BotConfigResponse | None)
async def get_last_active_config(
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    config = await repo.get_last_active()
    if not config:
        return None
    return BotConfigResponse.model_validate(config)


@router.get("/{config_id}/", response_model=BotConfigResponse)
async def get_config(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    config = await repo.get_by_id_for_user(config_id)
    return BotConfigResponse.model_validate(config)


@router.post("/setup/", response_model=BotConfigResponse)
async def setup_bot(
        config_data: BotConfigCreate, session: AsyncSession = Depends(get_session),
        current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    try:
        bot_config = await repo.create(bot_config=config_data)
        return BotConfigResponse.model_validate(bot_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/start/")
async def start_bot(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    config = await repo.get_by_id_for_user(config_id)

    try:
        result = await BotManager(session).start_first_cycle(config)
        config.is_active = True
        await session.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{config_id}/stop/")
async def stop_bot(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    config = await repo.get_by_id_for_user(config_id)

    ws_manager = websocket_registry.get(config_id)
    if not ws_manager:
        raise HTTPException(
            status_code=404,
            detail="WebSocket manager not found. Bot may not be running.",
        )

    try:
        await ws_manager.stop()
        await websocket_registry.remove(config_id)

        config.is_active = False
        await session.commit()

        return {"message": "Bot stopped successfully", "config_id": str(config_id)}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{config_id}/", response_model=BotConfigResponse)
async def update_bot_config(
    config_id: UUID,
    config_update: BotConfigUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    await repo.get_by_id_for_user(config_id)

    try:
        bot_config = await repo.update(id_=config_id, bot_config=config_update)
        return BotConfigResponse.model_validate(bot_config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{config_id}/trailing-stats/", response_model=TrailingStatsResponse)
async def get_trailing_stats(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: "User" = Depends(get_current_user)
):
    repo = SqlAlchemyBotConfigRepository(session=session, current_user=current_user)
    await repo.get_by_id_for_user(config_id)

    try:
        raw_stats = await repo.get_trailing_stats(config_id)
        return TrailingStatsResponse(**raw_stats)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

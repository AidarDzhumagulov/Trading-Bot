from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import logger
from app.shared.websocket_registry import websocket_registry
from app.shared.clients.redis import RedisConnectionPool
from app.domain.services.bot_recovery import bot_recovery_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Trading Bot API...")
    await RedisConnectionPool.init_redis_pool()
    recovery_stats = await bot_recovery_service.recover_all_active_bots()
    logger.info("BACKEND STARTUP COMPLETED")
    if recovery_stats:
        logger.info(f"Bots recovered: {recovery_stats.get('recovered', 0)}")
        logger.info(f"Bots failed: {recovery_stats.get('failed', 0)}")

    yield

    logger.info("Shutting down... Stopping all WebSocket managers")
    await websocket_registry.stop_all(timeout=15)
    await RedisConnectionPool.close_connections()
    logger.info("All WebSocket managers stopped")

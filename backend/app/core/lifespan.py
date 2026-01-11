from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import logger
from app.shared.websocket_registry import websocket_registry
from app.shared.clients.redis import RedisConnectionPool


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Trading Bot API...")
    await RedisConnectionPool.init_redis_pool()
    yield

    logger.info("Shutting down... Stopping all WebSocket managers")
    await websocket_registry.stop_all(timeout=15)
    await RedisConnectionPool.close_connections()
    logger.info("All WebSocket managers stopped")

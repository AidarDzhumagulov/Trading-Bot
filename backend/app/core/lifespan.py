from contextlib import asynccontextmanager
from app.core.config import settings

from fastapi import FastAPI

from app.core.logging import logger
from app.shared.websocket_registry import websocket_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Trading Bot API...")
    yield
    
    logger.info("Shutting down... Stopping all WebSocket managers")
    await websocket_registry.stop_all()
    logger.info("All WebSocket managers stopped")

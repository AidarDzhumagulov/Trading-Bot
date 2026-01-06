from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.lifespan import lifespan
from app.core.config import settings
from app.presentation.routers.v1.user import router as user_router
from app.presentation.routers.v1.bot_config import router as bot_config_router
from app.presentation.routers.v1.cycle import router as cycle_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Bot API",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = (
        ["*"]
        if settings.CORS_ORIGINS == "*"
        else [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(user_router, prefix="/api/v1")
    app.include_router(bot_config_router, prefix="/api/v1")
    app.include_router(cycle_router, prefix="/api/v1")
    return app

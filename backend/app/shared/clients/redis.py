from datetime import datetime, UTC
from typing import Optional

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import logger


class RedisConnectionPool:
    MIN_CONNECTIONS = 1
    MAX_CONNECTIONS = 10

    redis: Optional[Redis] = None

    @classmethod
    async def init_redis_pool(cls) -> None:
        cls.redis = Redis.from_url(
            url=settings.redis_url,
            max_connections=cls.MAX_CONNECTIONS,
            decode_responses=True,  # Чтобы получать строки вместо байтов
        )
        logger.info(
            f"Opened connections pool with max = {cls.MAX_CONNECTIONS} connections"
        )

    @classmethod
    async def close_connections(cls) -> None:
        if cls.redis:
            await cls.redis.close()
        logger.info("Connections pool closed")


class RedisClient:
    @staticmethod
    async def revoke_refresh_token(jti: str, exp: int) -> Optional[str]:
        """Add refresh token to blacklist"""
        ttl = exp - int(datetime.now(UTC).timestamp())
        if ttl <= 0:
            await RedisConnectionPool.redis.setex(f"blacklist:{jti}", ttl, "revoked")

    @staticmethod
    async def is_token_revoked(jti: str) -> bool:
        """Check if refresh token is revoked"""
        return await RedisConnectionPool.redis.exists(f"blacklist:{jti}") > 0

from typing import Annotated, AsyncIterator, Callable

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionMaker
from app.infrastructure.persistence.sqlalchemy.models import User
from app.core.auth import verify_token
from app.shared.clients.redis import RedisClient, RedisConnectionPool

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionMaker() as session:
        yield session


def get_session_factory() -> Callable[[], AsyncSession]:
    return AsyncSessionMaker


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    """Get current user"""
    payload = verify_token(token=token)

    user_id = payload.get("sub", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await session.get(entity=User, ident=user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    return user


async def get_redis_client() -> RedisClient:
    if not RedisConnectionPool.redis:
        message = "Redis pool is not initialized"
        raise RuntimeError(message)
    return RedisClient()


DBSession = Annotated[AsyncSession, Depends(get_session)]

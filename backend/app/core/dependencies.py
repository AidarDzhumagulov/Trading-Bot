from typing import Annotated, AsyncIterator, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionMaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionMaker() as session:
        yield session


def get_session_factory() -> Callable[[], AsyncSession]:
    return AsyncSessionMaker


DBSession = Annotated[AsyncSession, Depends(get_session)]

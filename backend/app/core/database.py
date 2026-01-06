from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.conn_str_async)

AsyncSessionMaker = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

convention = {
    "ix": "%(table_name)s_%(column_0_name)s_index",
    "fk": "%(table_name)s_%(column_0_name)s_foreign",
    "uq": "%(table_name)s_%(column_0_name)s_unique",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    metadata = metadata

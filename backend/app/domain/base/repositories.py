from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence, TypeVar
from uuid import UUID

TCreate = TypeVar("TCreate")
TUpdate = TypeVar("TUpdate")
TRead = TypeVar("TRead")
TModel = TypeVar("TModel")
TID = TypeVar("TID", bound=UUID)


class BaseRepository(ABC):
    @abstractmethod
    def to_model(self, data: TCreate) -> TModel:
        ...

    @abstractmethod
    async def create(self, data: TCreate) -> TRead:
        ...

    @abstractmethod
    async def get(self, id_: TID) -> TRead | None:
        ...

    @abstractmethod
    async def list(self) -> Sequence[TRead]:
        ...

    @abstractmethod
    async def update(self, id_: TID, data: TUpdate) -> TRead:
        ...

    @abstractmethod
    async def delete(self, id_: TID) -> None:
        ...

    @abstractmethod
    async def exists(self, id_: TID) -> bool:
        ...

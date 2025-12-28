from abc import ABC

from app.domain.base.repositories import BaseRepository


class UserRepository(BaseRepository, ABC):
    ...

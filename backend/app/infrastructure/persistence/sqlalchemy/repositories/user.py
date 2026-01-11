from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, exists
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.user.repositories import UserRepository
from app.infrastructure.persistence.sqlalchemy.models import User
from app.presentation.schemas.auth import UserRegister


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def to_model(self, data: UserRegister) -> User:
        return User(**data.model_dump())

    async def create(self, user_data: UserRegister) -> User:
        hashed_password = hash_password(user_data.password)
        user = User(email=user_data.email, hashed_password=hashed_password)
        self.session.add(user)
        try:
            await self.session.commit()
        except SQLAlchemyError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await self.session.refresh(user)
        return user

    async def get(self, id_: UUID) -> User | None:
        return await self.session.get(entity=User, ident=id_)

    async def delete(self, id_: UUID) -> None:
        ...

    async def update(self, id_: UUID, user) -> User:
        ...

    async def exists(self, email: str) -> bool:
        stmt = select(exists().where(User.email == email))
        result = await self.session.execute(stmt)
        return result.scalar()

    async def list(self) -> List[User]:
        ...

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return await self.session.scalar(stmt)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, EmailStr


class BalanceCheckRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    api_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["mWIM2Oyuj26cFgRnZbEeL1ommLyWVZbEhAxGI3o4b2xnkHB901FpvgtHaXtkHO7a"],
    )
    api_secret: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["TIwEZbwUQRz4ywXuzxC9a83ZG4nEZxVqwqCL0nNJCteHfiuxlCiYMyPI1YDhWPQy"],
    )


class BalanceResponse(BaseModel):
    free_usdt: float
    total_usdt: float


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

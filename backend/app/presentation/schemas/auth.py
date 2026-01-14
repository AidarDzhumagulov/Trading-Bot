import re

from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import field_validator
from pydantic import ConfigDict


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValueError("Password must contain at least one digit")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123",
            }
        }
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        ..., description="Refresh token для обновления access token"
    )


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token для отзыва")

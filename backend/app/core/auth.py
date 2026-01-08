from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4

from fastapi import HTTPException
from jose import jwt, JWTError

from app.core.config import settings


def create_access_token(user_id: UUID, email: str) -> str:
    """Create JWT access token"""

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "email": email,
        "iat": datetime.now(UTC),
        "type": "access",
    }

    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(user_id: UUID) -> str:
    """Create JWT refresh token"""
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(UTC),
        "type": "refresh",
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=401, detail=f"Could not validate credentials: {str(e)}"
        )

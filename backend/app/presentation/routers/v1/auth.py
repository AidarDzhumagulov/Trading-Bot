from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token, create_refresh_token, verify_token
from app.core.dependencies import get_session, get_redis_client
from app.core.security import verify_password
from app.infrastructure.persistence.sqlalchemy.repositories.user import (
    SqlAlchemyUserRepository,
)
from app.presentation.schemas.auth import TokenResponse, UserRegister, RefreshTokenRequest, LogoutRequest
from app.presentation.schemas.user import UserLogin
from app.shared.clients.redis import RedisClient

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register/", response_model=TokenResponse)
async def register(
    user_data: UserRegister, session: AsyncSession = Depends(get_session)
):
    """
    Register a new user
    :param user_data:
    :param session:
    :return:
    """
    repo = SqlAlchemyUserRepository(session)

    is_user_exist = await repo.exists(email=user_data.email)
    if is_user_exist:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await repo.create(user_data=user_data)

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login/", response_model=TokenResponse)
async def login(user_data: UserLogin, session: AsyncSession = Depends(get_session)):
    """
    Login a user
    :param user_data:
    :param session:
    :return:
    """
    repo = SqlAlchemyUserRepository(session)
    user = await repo.get_by_email(email=user_data.email)
    print(f"THIS IS USER{user}, user_id={user.id}")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(
        plain_password=user_data.password, hashed_password=user.hashed_password
    ):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout/")
async def logout(
    request: LogoutRequest,
    redis_client: RedisClient = Depends(get_redis_client),
):
    """Logout user by revoking refresh token"""
    payload = verify_token(request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    jti = payload.get("jti")
    exp = payload.get("exp")

    await redis_client.revoke_refresh_token(jti, exp)

    return {"message": "Successfully logged out"}


@router.post("/refresh/", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
    redis_client: RedisClient = Depends(get_redis_client)
):
    """
    Refresh access token

    :param request:
    :param session:
    :param redis_client:
    :return:
    """
    payload = verify_token(token=request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    jti = payload.get("jti")
    if await redis_client.is_token_revoked(jti=jti):
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    user_id = UUID(payload.get("sub"))

    repo = SqlAlchemyUserRepository(session)

    user = await repo.get(id_=user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user.id, user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token
    )

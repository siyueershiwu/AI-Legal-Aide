"""用户认证路由 - 真正的 JWT 鉴权"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: DbSession) -> AuthResponse:
    repo = UserRepository(db)
    if await repo.get_by_username(req.username):
        raise BadRequestError("用户名已存在")
    user_id = str(uuid.uuid4())
    await repo.create(
        user_id=user_id,
        username=req.username,
        password_hash=hash_password(req.password),
        email=req.email,
    )
    await db.commit()
    token = create_access_token(subject=user_id, extra={"username": req.username})
    return AuthResponse(
        access_token=token, user_id=user_id, username=req.username
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: DbSession) -> AuthResponse:
    repo = UserRepository(db)
    user = await repo.get_by_username(req.username)
    # 统一文案，避免暴露"用户存在与否"，同时用 401 而非 400
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise UnauthorizedError("用户名或密码错误")
    token = create_access_token(subject=user.id, extra={"username": user.username})
    return AuthResponse(
        access_token=token, user_id=user.id, username=user.username
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        avatar=current_user.avatar,
        created_at=current_user.created_at,
    )


@router.post("/logout")
async def logout() -> dict:
    # 客户端删 token 即可
    return {"success": True}

"""Admin authentication with RBAC — email+password, JWT, permission guards."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.admin.deps import get_db
from src.config.settings import Settings
from src.db.admin_models import AdminRole, AdminUser

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])
security = HTTPBearer()


# ---------------------------------------------------------------------------
# Settings helper
# ---------------------------------------------------------------------------


def _get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UserInfo(BaseModel):
    id: str
    email: str
    name: str
    role: str
    permissions: dict[str, list[str]]


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserInfo


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role_id: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = None
    password: str | None = None
    role_id: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role_id: str
    role_name: str
    is_active: bool
    last_login: str | None
    created_at: str


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str | None
    permissions: dict[str, list[str]]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def _create_token(
    user: AdminUser, role_name: str, permissions: dict, settings: Settings
) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": role_name,
        "permissions": permissions,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Current user dependency
# ---------------------------------------------------------------------------


class CurrentUser:
    """Authenticated user extracted from JWT."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.id: str = payload["sub"]
        self.email: str = payload["email"]
        self.name: str = payload["name"]
        self.role: str = payload["role"]
        self.permissions: dict[str, list[str]] = payload.get("permissions", {})

    def has_permission(self, resource: str, action: str) -> bool:
        actions = self.permissions.get(resource, [])
        return action in actions


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(_get_settings),
) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.admin_jwt_secret, algorithms=["HS256"]
        )
        return CurrentUser(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


# Backward-compatible alias (returns user name string for activity logs)
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(_get_settings),
) -> str:
    user = await get_current_user(credentials, settings)
    return user.name


# ---------------------------------------------------------------------------
# Permission dependency factory
# ---------------------------------------------------------------------------


def require_permission(resource: str, action: str):
    """FastAPI dependency that checks if user has a specific permission."""

    async def _check(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.has_permission(resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissao negada: {resource}.{action}",
            )
        return user

    return _check


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@auth_router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(_get_settings),
):
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user or not _bcrypt.checkpw(request.password.encode(), user.password_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha invalidos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta desativada",
        )

    # Get role
    role_result = await db.execute(
        select(AdminRole).where(AdminRole.id == user.role_id)
    )
    role = role_result.scalar_one()

    # Update last_login
    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == user.id)
        .values(last_login=datetime.now(timezone.utc))
    )
    await db.commit()

    token = _create_token(user, role.name, role.permissions, settings)
    return LoginResponse(
        token=token,
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=role.name,
            permissions=role.permissions,
        ),
    )


@auth_router.get("/me", response_model=UserInfo)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(user.id))
    )
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    role_result = await db.execute(
        select(AdminRole).where(AdminRole.id == db_user.role_id)
    )
    role = role_result.scalar_one()

    return UserInfo(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        role=role.name,
        permissions=role.permissions,
    )


@auth_router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(user.id))
    )
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if not _bcrypt.checkpw(request.current_password.encode(), db_user.password_hash.encode()):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == db_user.id)
        .values(
            password_hash=_bcrypt.hashpw(
                request.new_password.encode(), _bcrypt.gensalt()
            ).decode()
        )
    )
    await db.commit()
    return {"message": "Senha alterada com sucesso"}


# ---------------------------------------------------------------------------
# User management endpoints (admin only)
# ---------------------------------------------------------------------------


@users_router.get("", response_model=list[UserResponse])
async def list_users(
    _user: CurrentUser = Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminUser, AdminRole.name)
        .join(AdminRole, AdminUser.role_id == AdminRole.id)
        .order_by(AdminUser.name)
    )
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role_id=str(u.role_id),
            role_name=rn,
            is_active=u.is_active,
            last_login=u.last_login.isoformat() if u.last_login else None,
            created_at=u.created_at.isoformat(),
        )
        for u, rn in result.all()
    ]


@users_router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    _user: CurrentUser = Depends(require_permission("users", "create")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email ja cadastrado")

    role_result = await db.execute(
        select(AdminRole).where(AdminRole.id == uuid.UUID(body.role_id))
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=400, detail="Role nao encontrada")

    new_user = AdminUser(
        email=body.email,
        name=body.name,
        password_hash=_bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode(),
        role_id=uuid.UUID(body.role_id),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        name=new_user.name,
        role_id=str(new_user.role_id),
        role_name=role.name,
        is_active=new_user.is_active,
        last_login=None,
        created_at=new_user.created_at.isoformat(),
    )


@users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdate,
    _user: CurrentUser = Depends(require_permission("users", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(user_id))
    )
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if body.email is not None:
        db_user.email = body.email
    if body.name is not None:
        db_user.name = body.name
    if body.password is not None:
        db_user.password_hash = _bcrypt.hashpw(body.password.encode(), _bcrypt.gensalt()).decode()
    if body.role_id is not None:
        db_user.role_id = uuid.UUID(body.role_id)
    if body.is_active is not None:
        db_user.is_active = body.is_active

    await db.commit()
    await db.refresh(db_user)

    role_result = await db.execute(
        select(AdminRole).where(AdminRole.id == db_user.role_id)
    )
    role = role_result.scalar_one()

    return UserResponse(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        role_id=str(db_user.role_id),
        role_name=role.name,
        is_active=db_user.is_active,
        last_login=(
            db_user.last_login.isoformat() if db_user.last_login else None
        ),
        created_at=db_user.created_at.isoformat(),
    )


@users_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission("users", "delete")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current.id:
        raise HTTPException(
            status_code=400, detail="Nao pode deletar voce mesmo"
        )

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(user_id))
    )
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    await db.delete(db_user)
    await db.commit()
    return {"message": "Usuario removido"}


# ---------------------------------------------------------------------------
# Roles endpoints (read-only)
# ---------------------------------------------------------------------------


@roles_router.get("", response_model=list[RoleResponse])
async def list_roles(
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AdminRole).order_by(AdminRole.name))
    return [
        RoleResponse(
            id=str(r.id),
            name=r.name,
            description=r.description,
            permissions=r.permissions,
        )
        for r in result.scalars().all()
    ]

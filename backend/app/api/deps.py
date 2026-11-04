import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import Asset, Project, Role, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != payload.get("tv"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores")
    return user


def get_owned_project(project_id: uuid.UUID, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    # Admin pode acessar qualquer projeto; usuários só os próprios. 404 evita enumeração.
    if project is None or (project.owner_id != user.id and user.role != Role.admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado")
    return project


def get_accessible_asset(db: Session, asset_id: uuid.UUID, user: User, allow_system: bool = True) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado")
    if asset.owner_id is None and allow_system:
        return asset
    if asset.owner_id != user.id and user.role != Role.admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado")
    return asset


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd and get_settings().environment != "development":
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

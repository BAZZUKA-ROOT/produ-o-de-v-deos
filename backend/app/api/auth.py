from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.api.serializers import user_out
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, needs_rehash, verify_password
from app.models import Role, User
from app.schemas import LoginIn, PasswordChangeIn, ProfileIn, RegisterIn
from app.services import runtime_settings
from app.services.jobs import get_redis

router = APIRouter(prefix="/auth", tags=["auth"])
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _rate_key(ip: str, email: str) -> str:
    return f"forja:login:{ip}:{email.lower()}"


def _check_rate(ip: str, email: str) -> None:
    s = get_settings()
    try:
        attempts = int(get_redis().get(_rate_key(ip, email)) or 0)
    except redis.RedisError:
        return
    if attempts >= s.login_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Aguarde alguns minutos.")


def _register_failure(ip: str, email: str) -> None:
    try:
        r = get_redis()
        k = _rate_key(ip, email)
        r.incr(k)
        r.expire(k, get_settings().login_window_seconds)
    except redis.RedisError:
        pass


def _token_response(user: User) -> dict:
    return {"access_token": create_access_token(user.id, user.token_version, user.role.value), "token_type": "bearer",
            "user": user_out(user)}


@router.post("/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    allowed = runtime_settings.get_section(db, "general")["allow_registration"]
    first_user = db.query(User).count() == 0
    if not allowed and not first_user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cadastro desabilitado pelo administrador")
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado")
    user = User(name=data.name, email=email, password_hash=hash_password(data.password),
                role=Role.admin if first_user else Role.user)
    db.add(user)
    db.commit()
    return _token_response(user)


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    _check_rate(ip, data.email)
    user = db.query(User).filter(User.email == data.email.lower()).first()
    ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        _register_failure(ip, data.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    try:
        get_redis().delete(_rate_key(ip, data.email))
    except redis.RedisError:
        pass
    return _token_response(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.name = data.name
    db.commit()
    return user_out(user)


@router.post("/change-password")
def change_password(data: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta")
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1  # invalida sessões anteriores
    db.commit()
    return _token_response(user)


@router.post("/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    return {"ok": True}

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_ph = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, token_version: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_expire_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def _media_sig(asset_id: str, exp: int, download: int) -> str:
    key = hashlib.sha256(("media:" + get_settings().secret_key).encode()).digest()
    return hmac.new(key, f"{asset_id}:{exp}:{download}".encode(), hashlib.sha256).hexdigest()[:40]


def sign_media(asset_id: uuid.UUID | str, download: bool = False) -> str:
    s = get_settings()
    # Bucketed expiry keeps URLs stable across polls (browser cache friendly).
    bucket = s.media_url_expire_seconds
    exp = (int(time.time()) // bucket + 2) * bucket
    d = 1 if download else 0
    sig = _media_sig(str(asset_id), exp, d)
    return f"/api/media/{asset_id}?exp={exp}&dl={d}&sig={sig}"


def verify_media(asset_id: str, exp: int, download: int, sig: str) -> bool:
    if exp < time.time():
        return False
    return hmac.compare_digest(_media_sig(asset_id, exp, download), sig)

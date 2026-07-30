"""JWT creation and verification with no HTTP or persistence dependency."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

_jwt_secret = os.getenv("SECRET_KEY", "")
if not _jwt_secret:
    _jwt_secret = secrets.token_urlsafe(32)
    print("[auth] WARNING: SECRET_KEY not set, using random key. Tokens will not survive restarts.")


def create_access_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["username"],
        "role": user.get("role", "user"),
        "pid": user.get("participant_id"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _jwt_secret, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _jwt_secret, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


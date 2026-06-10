"""Session auth and Google login."""

from __future__ import annotations

from datetime import datetime

import requests
from fastapi import HTTPException, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User

SESSION_COOKIE = "partifi_session"
SESSION_MAX_AGE = 30 * 24 * 3600
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret, salt="session")


def create_session_token(user_id: str) -> str:
    return _session_serializer().dumps({"user_id": user_id})


def parse_session_token(token: str) -> str | None:
    try:
        data = _session_serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    user_id = data.get("user_id")
    return user_id if isinstance(user_id, str) and user_id else None


def set_session_cookie(response: Response, user_id: str) -> None:
    secure = get_settings().app_env != "development"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user_id),
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        secure=secure,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, httponly=True, samesite="lax")


def get_user_id_from_cookie(cookie_value: str | None) -> str | None:
    if not cookie_value:
        return None
    return parse_session_token(cookie_value)


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def upsert_user(db: Session, user_id: str, name: str | None) -> User:
    user = db.get(User, user_id)
    if user:
        if name and user.name != name:
            user.name = name
    else:
        user = User(id=user_id, name=name, ts=datetime.utcnow())
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def validate_google_access_token(token: str) -> dict[str, str]:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google login is not configured")

    try:
        response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=401, detail="Invalid Google access token") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google access token")

    data = response.json()
    sub = data.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid Google access token")

    return {"id": str(sub), "name": data.get("name")}


def validate_google_id_token(token: str) -> dict[str, str]:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google login is not configured")

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google ID token") from exc

    if idinfo.get("iss") not in _GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Invalid Google ID token issuer")

    sub = idinfo.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid Google ID token")

    return {"id": str(sub), "name": idinfo.get("name")}

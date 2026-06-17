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


def upsert_user(
    db: Session,
    user_id: str,
    name: str | None,
    given_name: str | None = None,
) -> User:
    user = db.get(User, user_id)
    if user:
        if name and user.name != name:
            user.name = name
        if given_name and user.given_name != given_name:
            user.given_name = given_name
    else:
        user = User(
            id=user_id,
            name=name,
            given_name=given_name,
            ts=datetime.utcnow(),
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def google_profile(data: dict) -> dict[str, str | None]:
    sub = data.get("sub")
    if not sub:
        return {}
    return {
        "id": str(sub),
        "name": data.get("name"),
        "given_name": data.get("given_name"),
    }


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

    return google_profile(data)


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

    return google_profile(idinfo)


def exchange_google_auth_code(code: str, redirect_uri: str | None = None) -> dict[str, str]:
    """Exchange a GIS authorization code for a verified user profile (via id_token)."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google login is not configured")

    uri = redirect_uri if redirect_uri is not None else settings.google_oauth_redirect_uri

    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": uri,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=401, detail="Invalid Google authorization code") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google authorization code")

    token_payload = response.json()
    id_token_str = token_payload.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=401, detail="Google did not return an ID token")

    return validate_google_id_token(id_token_str)

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps.auth import get_current_user, get_current_user_id, require_user_id
from app.models import User
from app.schemas.auth import (
    AuthMeResponse,
    DevLoginRequest,
    GoogleLoginRequest,
    UserResponse,
)
from app.schemas.library import (
    FavoriteActionRequest,
    FavoriteStatusResponse,
    LibraryResponse,
)
from app.services.auth import (
    clear_session_cookie,
    exchange_google_auth_code,
    set_session_cookie,
    upsert_user,
    validate_google_access_token,
    validate_google_id_token,
)
from app.services.library import favorite_status, list_library, update_favorite
from app.routers.v1 import verify_csrf

router = APIRouter(prefix="/api/v1", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, name=user.name)


@router.get("/auth/me", response_model=AuthMeResponse)
def auth_me(user: User | None = Depends(get_current_user)) -> AuthMeResponse:
    if not user:
        return AuthMeResponse(user=None)
    return AuthMeResponse(user=_user_response(user))


@router.post("/auth/google", response_model=AuthMeResponse)
def auth_google(
    body: GoogleLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    if body.code:
        profile = exchange_google_auth_code(body.code, body.redirect_uri)
    elif body.id_token:
        profile = validate_google_id_token(body.id_token)
    elif body.access_token:
        profile = validate_google_access_token(body.access_token)
    else:
        raise HTTPException(status_code=400, detail="Missing Google credential")
    user = upsert_user(db, profile["id"], profile.get("name"))
    set_session_cookie(response, user.id)
    return AuthMeResponse(user=_user_response(user))


@router.post("/auth/dev-login", response_model=AuthMeResponse)
def auth_dev_login(
    body: DevLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    if get_settings().app_env != "development":
        raise HTTPException(status_code=404, detail="Not found")
    user = upsert_user(db, body.user_id.strip(), body.name.strip())
    set_session_cookie(response, user.id)
    return AuthMeResponse(user=_user_response(user))


@router.post("/auth/logout")
def auth_logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/library", response_model=LibraryResponse)
def get_library(
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
) -> LibraryResponse:
    return LibraryResponse(items=list_library(db, user_id))


@router.get("/library/favorites/{access_id}", response_model=FavoriteStatusResponse)
def get_favorite_status(
    access_id: str,
    user_id: str | None = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FavoriteStatusResponse:
    if not user_id:
        return FavoriteStatusResponse(favorite=False)
    return FavoriteStatusResponse(favorite=favorite_status(db, user_id, access_id))


@router.post("/library/favorites/{access_id}", response_model=FavoriteStatusResponse)
def set_favorite_status(
    access_id: str,
    body: FavoriteActionRequest,
    user_id: str = Depends(require_user_id),
    db: Session = Depends(get_db),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> FavoriteStatusResponse:
    verify_csrf(x_csrf_token)
    if body.action not in {"add", "remove"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        update_favorite(db, user_id, access_id, action=body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FavoriteStatusResponse(favorite=body.action == "add")

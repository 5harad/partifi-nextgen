from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth import SESSION_COOKIE, get_user, get_user_id_from_cookie


def get_current_user_id(
    request: Request,
    db: Session = Depends(get_db),
) -> str | None:
    user_id = get_user_id_from_cookie(request.cookies.get(SESSION_COOKIE))
    if not user_id:
        return None
    if not get_user(db, user_id):
        return None
    return user_id


def require_user_id(user_id: str | None = Depends(get_current_user_id)) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_current_user(
    user_id: str | None = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User | None:
    if not user_id:
        return None
    return get_user(db, user_id)

from fastapi import APIRouter, Depends, HTTPException
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Partset

router = APIRouter(prefix="/api/v1", tags=["v1"])


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class ImportStatusResponse(BaseModel):
    private_id: str
    status: str | None
    import_progress: float
    convert_progress: float
    analysis_progress: float
    cut_progress: float
    paste_progress: float
    parts_ready: bool | None
    error: str | None


def _csrf_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret, salt="csrf")


@router.get("/csrf-token", response_model=CsrfTokenResponse)
def csrf_token() -> CsrfTokenResponse:
    token = _csrf_serializer().dumps({"nonce": "partifi"})
    return CsrfTokenResponse(csrf_token=token)


def verify_csrf(token: str) -> None:
    try:
        _csrf_serializer().loads(token, max_age=3600)
    except BadSignature as exc:
        raise HTTPException(status_code=403, detail="Invalid CSRF token") from exc


@router.get(
    "/partsets/{private_id}/import-status",
    response_model=ImportStatusResponse,
)
def import_status(private_id: str, db: Session = Depends(get_db)) -> ImportStatusResponse:
    partset = db.query(Partset).filter(Partset.private_id == private_id).first()
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")

    return ImportStatusResponse(
        private_id=private_id,
        status=partset.status,
        import_progress=partset.import_progress,
        convert_progress=partset.convert_progress,
        analysis_progress=partset.analysis_progress,
        cut_progress=partset.cut_progress,
        paste_progress=partset.paste_progress,
        parts_ready=partset.parts_ready,
        error=partset.error,
    )

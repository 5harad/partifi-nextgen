from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Partset
from app.schemas.partset import ImportProgressResponse, PartsetCreateResponse
from app.services.partsets import create_pdf_partset, import_progress_payload

router = APIRouter(prefix="/api/v1", tags=["v1"])

COPYRIGHT_VALUES = {"before 1923", "after 1923", "unknown"}


class CsrfTokenResponse(dict):
    pass


def _csrf_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().app_secret, salt="csrf")


@router.get("/csrf-token")
def csrf_token() -> dict:
    token = _csrf_serializer().dumps({"nonce": "partifi"})
    return {"csrf_token": token}


def verify_csrf(token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=403, detail="Missing CSRF token")
    try:
        _csrf_serializer().loads(token, max_age=3600)
    except BadSignature as exc:
        raise HTTPException(status_code=403, detail="Invalid CSRF token") from exc


@router.post("/partsets", response_model=PartsetCreateResponse)
async def create_partset(
    title: str = Form(...),
    composer: str = Form(...),
    publisher: str = Form(""),
    copyright: str = Form(...),
    file_hash: str = Form(...),
    score: UploadFile = File(...),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> PartsetCreateResponse:
    verify_csrf(x_csrf_token)

    if copyright not in COPYRIGHT_VALUES:
        raise HTTPException(status_code=400, detail="Invalid copyright value")

    pdf_bytes = await score.read()
    try:
        partset, action = create_pdf_partset(
            db,
            title=title.strip(),
            composer=composer.strip(),
            publisher=publisher.strip(),
            copyright=copyright,
            file_hash=file_hash.strip(),
            pdf_bytes=pdf_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PartsetCreateResponse(
        status="ok",
        id=partset.private_id or "",
        action=action,
    )


@router.get(
    "/partsets/{private_id}/import-status",
    response_model=ImportProgressResponse,
)
def import_status(private_id: str, db: Session = Depends(get_db)) -> ImportProgressResponse:
    partset = db.query(Partset).filter(Partset.private_id == private_id).first()
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")

    return ImportProgressResponse(**import_progress_payload(partset))

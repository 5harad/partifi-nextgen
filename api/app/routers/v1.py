from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Partset
from app.schemas.partset import ImportProgressResponse, PartsetCreateResponse
from app.schemas.segment import (
    SavePageSegmentsRequest,
    SavePageSegmentsResponse,
    SegmentDataResponse,
)
from app.services.partsets import create_pdf_partset, import_progress_payload
from app.schemas.preview import (
    CombinePartsRequest,
    CombinePartsResponse,
    GeneratePartsResponse,
    PartgenProgressResponse,
    PartsDataResponse,
    PreviewDataResponse,
    SaveLayoutRequest,
    SaveLayoutResponse,
)
from app.services.preview import (
    combine_parts,
    get_parts_data,
    get_preview_data,
    partgen_progress_payload,
    save_layout,
    start_part_generation,
)

from app.services.segments import (
    get_partset_by_private_id,
    get_segments_data,
    save_page_segments,
)

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


@router.get(
    "/partsets/{private_id}/segment-data",
    response_model=SegmentDataResponse,
)
def segment_data(private_id: str, db: Session = Depends(get_db)) -> SegmentDataResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        payload = get_segments_data(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SegmentDataResponse(**payload)


@router.put(
    "/partsets/{private_id}/pages/{page}/segments",
    response_model=SavePageSegmentsResponse,
)
def save_segments(
    private_id: str,
    page: int,
    body: SavePageSegmentsRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> SavePageSegmentsResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        save_page_segments(
            db,
            partset,
            page,
            body.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SavePageSegmentsResponse(status="success")


@router.get(
    "/partsets/{private_id}/preview-data",
    response_model=PreviewDataResponse,
)
def preview_data(private_id: str, db: Session = Depends(get_db)) -> PreviewDataResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        payload = get_preview_data(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PreviewDataResponse(**payload)


@router.put(
    "/partsets/{private_id}/layout",
    response_model=SaveLayoutResponse,
)
def save_partset_layout(
    private_id: str,
    body: SaveLayoutRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> SaveLayoutResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    save_layout(db, partset, body.breaks, body.spacings)
    return SaveLayoutResponse()


@router.post(
    "/partsets/{private_id}/parts/combine",
    response_model=CombinePartsResponse,
)
def combine_partset_parts(
    private_id: str,
    body: CombinePartsRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> CombinePartsResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        combine_parts(db, partset, body.action, body.tag)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CombinePartsResponse()


@router.post(
    "/partsets/{private_id}/generate",
    response_model=GeneratePartsResponse,
)
def generate_parts(
    private_id: str,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> GeneratePartsResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    job_id = start_part_generation(db, partset)
    return GeneratePartsResponse(status="success", job_id=job_id)


@router.get(
    "/partsets/{private_id}/partgen-status",
    response_model=PartgenProgressResponse,
)
def partgen_status(private_id: str, db: Session = Depends(get_db)) -> PartgenProgressResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    return PartgenProgressResponse(**partgen_progress_payload(partset))


@router.get(
    "/partsets/{private_id}/parts",
    response_model=PartsDataResponse,
)
def parts_data(private_id: str, db: Session = Depends(get_db)) -> PartsDataResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        payload = get_parts_data(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsDataResponse(**payload)

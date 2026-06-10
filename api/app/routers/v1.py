from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

import asyncio

from app.config import get_settings
from app.db import get_db
from app.models import Partset
from app.schemas.partset import (
    DeletePartsetResponse,
    ImportProgressResponse,
    PartsetCreateResponse,
    UpdateMetadataRequest,
    UpdateMetadataResponse,
)
from app.schemas.imslp import CreateFromImslpRequest, ImslpInfoResponse
from app.schemas.search import CreateFromScoreRequest, SearchResponse
from app.schemas.segment import (
    SavePageSegmentsRequest,
    SavePageSegmentsResponse,
    SegmentDataResponse,
)
from app.services.partsets import (
    create_imslp_partset,
    create_partset_from_score,
    create_pdf_partset,
    import_progress_payload,
)
from app.services.imslp import lookup_imslp_info_remote
from app.services.search import search_partsets
from app.services.partset_admin import (
    delete_partset,
    resolve_partset_access,
    update_partset_metadata,
)
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


@router.get("/search", response_model=SearchResponse)
def search(q: str = "", db: Session = Depends(get_db)) -> SearchResponse:
    results = search_partsets(db, q)
    return SearchResponse(results=results)


@router.get("/imslp/{imslp_id}/info", response_model=ImslpInfoResponse)
async def imslp_info(imslp_id: str) -> ImslpInfoResponse:
    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(lookup_imslp_info_remote, imslp_id),
            timeout=20.0,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="IMSLP lookup timed out. Try again in a moment.",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="IMSLP lookup timed out. Try again in a moment.",
        ) from exc
    if not info:
        raise HTTPException(status_code=404, detail="IMSLP score not found or not a PDF")
    return ImslpInfoResponse(**info)


@router.post("/partsets/imslp", response_model=PartsetCreateResponse)
def create_partset_from_imslp(
    body: CreateFromImslpRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> PartsetCreateResponse:
    verify_csrf(x_csrf_token)
    if body.copyright not in COPYRIGHT_VALUES:
        raise HTTPException(status_code=400, detail="Invalid copyright value")
    title = body.title.strip()
    composer = body.composer.strip()
    if not title or not composer:
        raise HTTPException(status_code=400, detail="Title and composer are required")
    try:
        partset, action = create_imslp_partset(
            db,
            imslp_id=body.imslp_id.strip(),
            title=title,
            composer=composer,
            publisher=body.publisher.strip(),
            copyright=body.copyright,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsetCreateResponse(status="ok", id=partset.private_id or "", action=action)


@router.post("/partsets/from-score", response_model=PartsetCreateResponse)
def create_partset_from_library_score(
    body: CreateFromScoreRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> PartsetCreateResponse:
    verify_csrf(x_csrf_token)
    if body.copyright not in COPYRIGHT_VALUES:
        raise HTTPException(status_code=400, detail="Invalid copyright value")
    title = body.title.strip()
    composer = body.composer.strip()
    if not title or not composer:
        raise HTTPException(status_code=400, detail="Title and composer are required")
    try:
        partset = create_partset_from_score(
            db,
            score_id=body.score_id.strip(),
            title=title,
            composer=composer,
            publisher=body.publisher.strip(),
            copyright=body.copyright,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsetCreateResponse(status="ok", id=partset.private_id or "", action="continue")


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
    "/access/{access_id}/parts",
    response_model=PartsDataResponse,
)
def parts_by_access_id(access_id: str, db: Session = Depends(get_db)) -> PartsDataResponse:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, mode = resolved
    try:
        payload = get_parts_data(db, partset, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsDataResponse(**payload)


@router.get(
    "/partsets/{private_id}/parts",
    response_model=PartsDataResponse,
)
def parts_data(private_id: str, db: Session = Depends(get_db)) -> PartsDataResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        payload = get_parts_data(db, partset, mode="owner")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsDataResponse(**payload)


@router.put(
    "/partsets/{private_id}/metadata",
    response_model=UpdateMetadataResponse,
)
def update_metadata(
    private_id: str,
    body: UpdateMetadataRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> UpdateMetadataResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    title = body.title.strip()
    composer = body.composer.strip()
    if not title or not composer:
        raise HTTPException(status_code=400, detail="Title and composer are required")
    update_partset_metadata(
        db,
        partset,
        title=title,
        composer=composer,
        publisher=body.publisher.strip(),
    )
    return UpdateMetadataResponse()


@router.delete(
    "/partsets/{private_id}",
    response_model=DeletePartsetResponse,
)
def delete_partset_route(
    private_id: str,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> DeletePartsetResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    delete_partset(db, partset)
    return DeletePartsetResponse()

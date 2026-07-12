import asyncio
import logging
import re
import threading

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps.auth import get_current_user_id
from app.db import get_db
from app.models import Partset, Score
from app.schemas.partset import (
    DeletePartsetResponse,
    ImportProgressResponse,
    PartsetCreateResponse,
    RetryPipelineResponse,
    UpdateMetadataRequest,
    UpdateMetadataResponse,
)
from app.schemas.imslp import CreateFromImslpRequest, ImslpInfoResponse
from app.schemas.search import CreateFromScoreRequest, SearchResponse
from app.schemas.segment import (
    SaveAllPageSegmentsRequest,
    SavePageSegmentsRequest,
    SavePageSegmentsResponse,
    SegmentDataResponse,
)
from app.services.imslp import (
    ImslpLookupCancelled,
    ImslpLookupError,
    ImslpLookupUnavailableError,
    lookup_imslp_info_remote,
    normalize_imslp_id,
)
from app.services.partsets import (
    create_imslp_partset,
    create_partset_from_score,
    create_pdf_partset,
    import_progress_payload,
)
from app.services.retry import ensure_import_if_needed, retry_partset_pipeline
from app.services.search import search_partsets
from app.services.partset_admin import (
    delete_partset,
    resolve_partset_access,
    update_partset_metadata,
)
from app.schemas.orientation import (
    OrientationDataResponse,
    ReorientRequest,
    ReorientResponse,
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
from app.services.orientation_preview import render_orientation_preview_png
from app.services.partset_pages import (
    ensure_page_image_path,
    orientation_data_payload,
    start_reorient,
)
from app.services.partset_touch import touch_partset_access
from app.services.preview import (
    combine_parts,
    ensure_parts_if_needed,
    get_parts_data,
    get_preview_data,
    partgen_progress_payload,
    save_layout,
    start_part_generation,
)
from app.services.downloads import (
    record_part_download,
    resolve_part_cache_filename,
    safe_cached_part_path,
)
from app.services.local_cache import get_local_cache
from app.services.segments import (
    get_partset_by_private_id,
    get_segments_data,
    save_all_page_segments,
    save_page_segments,
)
from pipeline.partset_orientation import normalize_rotation_degrees

router = APIRouter(prefix="/api/v1", tags=["v1"])
logger = logging.getLogger(__name__)

COPYRIGHT_VALUES = {"before 1923", "after 1923", "unknown"}
PART_FILE_PATTERN = re.compile(r"^[A-Za-z0-9._+\-]+\.pdf$")
SCORE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PAGE_IMAGE_RES = {"lowres", "thumbs"}


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


def _serve_cached_part(
    partset: Partset,
    filename: str,
    db: Session,
    *,
    access_id: str,
    download_path: str,
    user_id: str | None = None,
) -> FileResponse:
    del access_id, download_path  # kept for stable call sites
    if not PART_FILE_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    cache_filename = resolve_part_cache_filename(db, partset, filename)
    if not cache_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    cache = get_local_cache()
    path = safe_cached_part_path(cache, partset.id, cache_filename)
    if not path:
        from app.services.preview import _partgen_in_progress

        if _partgen_in_progress(partset):
            raise HTTPException(status_code=409, detail="generating")
        if partset.parts_ready:
            logger.error(
                "parts_ready but cached part missing partset_id=%s filename=%s",
                partset.id,
                cache_filename,
            )
        raise HTTPException(status_code=404, detail="Part file not found")
    record_part_download(db, partset, filename, user_id=user_id)
    return FileResponse(path, media_type="application/pdf", filename=filename)


def _serve_score_pdf(score_id: str) -> FileResponse:
    if not SCORE_ID_PATTERN.match(score_id):
        raise HTTPException(status_code=400, detail="Invalid score id")
    try:
        path = get_local_cache().ensure_score_pdf(score_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Score PDF not found") from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{score_id}_score.pdf",
    )


@router.get("/partsets/{private_id}/preview-segment/{ndx}.png")
def preview_segment_image(
    private_id: str,
    ndx: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    cache = get_local_cache()
    path = cache.preview_segment_path(partset.id, ndx)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Preview segment not found")
    return FileResponse(path, media_type="image/png")


@router.get("/partsets/{private_id}/page-image/{page}.png")
def page_image(
    private_id: str,
    page: int,
    res: str = Query("lowres"),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _page_image_response(private_id, page, res, db)


@router.get("/partsets/{private_id}/page-image/{page}")
def page_image_legacy(
    private_id: str,
    page: int,
    res: str = Query("lowres"),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Backward-compatible path without .png suffix (pre-483c1d1 segment-data URLs)."""
    return _page_image_response(private_id, page, res, db)


def _page_image_response(
    private_id: str,
    page: int,
    res: str,
    db: Session,
) -> FileResponse:
    if res not in PAGE_IMAGE_RES:
        raise HTTPException(status_code=400, detail="Invalid res")
    if page < 1:
        raise HTTPException(status_code=400, detail="Invalid page")
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    if not partset.score_id:
        raise HTTPException(status_code=400, detail="Partset has no score")
    score = db.get(Score, partset.score_id)
    if not score:
        raise HTTPException(status_code=400, detail="Partset has no score")
    try:
        path = ensure_page_image_path(partset, score, res, page)  # type: ignore[arg-type]
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Page image not found") from exc
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "private, no-cache"},
    )


@router.get("/scores/{score_id}/score.pdf")
def score_pdf(score_id: str) -> FileResponse:
    return _serve_score_pdf(score_id)


@router.get("/access/{access_id}/score.pdf")
def score_pdf_access(access_id: str, db: Session = Depends(get_db)) -> FileResponse:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, _mode = resolved
    if not partset.score_id:
        raise HTTPException(status_code=404, detail="Score PDF not found")
    touch_partset_access(db, partset)
    return _serve_score_pdf(partset.score_id)


@router.get("/partsets/{private_id}/score.pdf")
def score_pdf_owner(private_id: str, db: Session = Depends(get_db)) -> FileResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset or not partset.score_id:
        raise HTTPException(status_code=404, detail="Score PDF not found")
    touch_partset_access(db, partset)
    return _serve_score_pdf(partset.score_id)


@router.get("/partsets/{private_id}/part-file/{filename}", response_model=None)
def part_file_owner(
    private_id: str,
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    return _serve_cached_part(
        partset,
        filename,
        db,
        access_id=private_id,
        download_path=request.url.path,
        user_id=user_id,
    )


@router.get("/access/{access_id}/part-file/{filename}", response_model=None)
def part_file_access(
    access_id: str,
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
):
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, _mode = resolved
    return _serve_cached_part(
        partset,
        filename,
        db,
        access_id=access_id,
        download_path=request.url.path,
        user_id=user_id,
    )


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
    user_id: str | None = Depends(get_current_user_id),
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
            user_id=user_id,
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


_IMSLP_LOOKUP_DRAIN_SECONDS = 5.0


def _discard_imslp_lookup_task(task: asyncio.Task) -> None:
    """Retrieve an orphaned lookup task exception so asyncio does not warn."""
    if task.cancelled():
        return
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if isinstance(exc, ImslpLookupCancelled):
        return
    if isinstance(exc, TimeoutError):
        logger.info("IMSLP metadata lookup timed out (background task): %s", exc)
        return
    if exc is not None:
        logger.warning("IMSLP lookup task ended with unexpected error: %s", exc)


async def _drain_imslp_lookup_task(
    task: asyncio.Task,
    *,
    cancel: threading.Event | None = None,
    timeout: float = _IMSLP_LOOKUP_DRAIN_SECONDS,
) -> None:
    """Wait for a lookup thread to finish; swallow only expected terminal errors."""
    if task.done():
        try:
            await task
        except (ImslpLookupCancelled, TimeoutError):
            pass
        return

    if cancel is not None:
        cancel.set()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except ImslpLookupCancelled:
        pass
    except TimeoutError:
        pass
    except asyncio.TimeoutError:
        if not task.done():
            task.add_done_callback(_discard_imslp_lookup_task)


@router.get("/imslp/{imslp_id}/info", response_model=ImslpInfoResponse)
async def imslp_info(request: Request, imslp_id: str) -> ImslpInfoResponse:
    cancel = threading.Event()
    task = asyncio.create_task(
        asyncio.to_thread(lookup_imslp_info_remote, imslp_id, cancel=cancel),
    )
    try:
        while not task.done():
            if await request.is_disconnected():
                cancel.set()
                break
            await asyncio.sleep(0.05)

        if await request.is_disconnected():
            await _drain_imslp_lookup_task(task, cancel=cancel)
            raise HTTPException(status_code=499, detail="Client disconnected")

        info = await asyncio.wait_for(task, timeout=20.0)
    except asyncio.TimeoutError as exc:
        logger.info("IMSLP metadata lookup timed out imslp_id=%s", imslp_id)
        await _drain_imslp_lookup_task(task, timeout=_IMSLP_LOOKUP_DRAIN_SECONDS)
        raise HTTPException(
            status_code=504,
            detail="IMSLP lookup timed out. Try again in a moment.",
        ) from exc
    except TimeoutError as exc:
        logger.info("IMSLP metadata lookup timed out imslp_id=%s", imslp_id)
        await _drain_imslp_lookup_task(task, timeout=_IMSLP_LOOKUP_DRAIN_SECONDS)
        raise HTTPException(
            status_code=504,
            detail="IMSLP lookup timed out. Try again in a moment.",
        ) from exc
    except ImslpLookupCancelled as exc:
        raise HTTPException(status_code=499, detail="Client disconnected") from exc
    except ImslpLookupUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ImslpLookupError as exc:
        raise HTTPException(
            status_code=400 if exc.not_pdf else 404,
            detail=str(exc),
        ) from exc
    return ImslpInfoResponse(**info)


@router.post("/partsets/imslp", response_model=PartsetCreateResponse)
def create_partset_from_imslp(
    body: CreateFromImslpRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
) -> PartsetCreateResponse:
    verify_csrf(x_csrf_token)
    imslp_id = body.imslp_id.strip()
    normalized = normalize_imslp_id(imslp_id) or imslp_id
    if body.copyright not in COPYRIGHT_VALUES:
        logger.warning(
            "IMSLP import rejected (validation) imslp_id=%s: Invalid copyright value",
            normalized,
        )
        raise HTTPException(status_code=400, detail="Invalid copyright value")
    title = body.title.strip()
    composer = body.composer.strip()
    if not title or not composer:
        logger.warning(
            "IMSLP import rejected (validation) imslp_id=%s: Title and composer are required",
            normalized,
        )
        raise HTTPException(status_code=400, detail="Title and composer are required")
    try:
        partset, action = create_imslp_partset(
            db,
            imslp_id=imslp_id,
            title=title,
            composer=composer,
            publisher=body.publisher.strip(),
            copyright=body.copyright,
            user_id=user_id,
        )
    except ValueError as exc:
        normalized = normalize_imslp_id(imslp_id) or imslp_id
        logger.warning("IMSLP import rejected imslp_id=%s: %s", normalized, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PartsetCreateResponse(status="ok", id=partset.private_id or "", action=action)


@router.post("/partsets/from-score", response_model=PartsetCreateResponse)
def create_partset_from_library_score(
    body: CreateFromScoreRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
    user_id: str | None = Depends(get_current_user_id),
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
            user_id=user_id,
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
    touch_partset_access(db, partset)
    return ImportProgressResponse(**import_progress_payload(partset))


@router.post(
    "/partsets/{private_id}/ensure-import",
    response_model=GeneratePartsResponse,
)
def ensure_import(
    private_id: str,
    db: Session = Depends(get_db),
) -> GeneratePartsResponse:
    partset = db.query(Partset).filter(Partset.private_id == private_id).first()
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    job_id = ensure_import_if_needed(db, partset)
    return GeneratePartsResponse(status="success", job_id=job_id)


@router.post(
    "/partsets/{private_id}/retry-pipeline",
    response_model=RetryPipelineResponse,
)
def retry_pipeline(
    private_id: str,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> RetryPipelineResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        stage, job_id = retry_partset_pipeline(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RetryPipelineResponse(stage=stage, job_id=job_id)


@router.get(
    "/partsets/{private_id}/orientation-data",
    response_model=OrientationDataResponse,
)
def orientation_data(private_id: str, db: Session = Depends(get_db)) -> OrientationDataResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    if not partset.score_id:
        raise HTTPException(status_code=400, detail="Partset has no score")
    score = db.get(Score, partset.score_id)
    if not score:
        raise HTTPException(status_code=400, detail="Partset has no score")
    if not partset.import_complete:
        raise HTTPException(status_code=400, detail="Import not complete")
    touch_partset_access(db, partset)
    return OrientationDataResponse(**orientation_data_payload(db, partset, score))


@router.get("/partsets/{private_id}/orientation-preview/{degrees}.png")
def orientation_preview_image(
    private_id: str,
    degrees: int,
    db: Session = Depends(get_db),
) -> Response:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    if not partset.score_id:
        raise HTTPException(status_code=400, detail="Partset has no score")
    score = db.get(Score, partset.score_id)
    if not score:
        raise HTTPException(status_code=400, detail="Partset has no score")
    try:
        rotation_degrees = normalize_rotation_degrees(degrees)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        png = render_orientation_preview_png(partset, score, rotation_degrees)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Preview not available") from exc
    return Response(content=png, media_type="image/png")


@router.post(
    "/partsets/{private_id}/reorient",
    response_model=ReorientResponse,
)
def reorient_partset(
    private_id: str,
    body: ReorientRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> ReorientResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        job_id = start_reorient(db, partset, body.rotation_degrees)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReorientResponse(status="started", job_id=job_id)


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
    "/partsets/{private_id}/segments",
    response_model=SavePageSegmentsResponse,
)
def save_all_segments(
    private_id: str,
    body: SaveAllPageSegmentsRequest,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> SavePageSegmentsResponse:
    verify_csrf(x_csrf_token)
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    try:
        save_all_page_segments(
            db,
            partset,
            {key: page.model_dump() for key, page in body.pages.items()},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SavePageSegmentsResponse(status="success")


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
    try:
        job_id = start_part_generation(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GeneratePartsResponse(status="success", job_id=job_id)


@router.get(
    "/partsets/{private_id}/partgen-status",
    response_model=PartgenProgressResponse,
)
def partgen_status(private_id: str, db: Session = Depends(get_db)) -> PartgenProgressResponse:
    partset = get_partset_by_private_id(db, private_id)
    if not partset:
        raise HTTPException(status_code=404, detail="Partset not found")
    return PartgenProgressResponse(**partgen_progress_payload(partset, db))


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
    if not partset.parts_ready and payload["parts"]:
        ensure_parts_if_needed(db, partset)
    return PartsDataResponse(**payload)


@router.post(
    "/access/{access_id}/ensure-parts",
    response_model=GeneratePartsResponse,
)
def ensure_parts(access_id: str, db: Session = Depends(get_db)) -> GeneratePartsResponse:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, _mode = resolved
    job_id = ensure_parts_if_needed(db, partset)
    return GeneratePartsResponse(status="success", job_id=job_id)


@router.get(
    "/access/{access_id}/partgen-status",
    response_model=PartgenProgressResponse,
)
def partgen_status_by_access(
    access_id: str, db: Session = Depends(get_db)
) -> PartgenProgressResponse:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, _mode = resolved
    return PartgenProgressResponse(**partgen_progress_payload(partset, db))


@router.post(
    "/access/{access_id}/retry-pipeline",
    response_model=RetryPipelineResponse,
)
def retry_pipeline_by_access(
    access_id: str,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> RetryPipelineResponse:
    verify_csrf(x_csrf_token)
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Partset not found")
    partset, _mode = resolved
    try:
        stage, job_id = retry_partset_pipeline(db, partset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RetryPipelineResponse(stage=stage, job_id=job_id)


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

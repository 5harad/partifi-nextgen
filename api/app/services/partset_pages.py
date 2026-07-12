"""Resolve per-partset page images and layout orientation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Page, Partset, Score, Segment
from app.services.import_lock import try_acquire_import_lock
from app.services.partset_cache_status import (
    clear_partset_cache_error,
    get_partset_cache_error,
)
from app.services.local_cache import get_local_cache
from app.services.partsets import import_progress_payload
from app.services.queue import enqueue_job
from app.services.score_pages import ensure_score_pages_warming
from pipeline.local_cache import ScoreKind
from pipeline.partset_orientation import (
    ROTATION_OPTIONS,
    effective_partset_orientation,
    layout_orientation,
    normalize_rotation_degrees,
    partset_uses_custom_pages,
)


def effective_orientation(partset: Partset, score: Score | None) -> str:
    return effective_partset_orientation(
        score_orientation=score.orientation if score and score.orientation else "portrait",
        orientation_override=partset.orientation_override,
        rotation_degrees=int(partset.rotation_degrees or 0),
    )


def uses_custom_pages(partset: Partset) -> bool:
    return partset_uses_custom_pages(int(partset.rotation_degrees or 0))


def ensure_page_image_path(
    partset: Partset,
    score: Score,
    kind: ScoreKind,
    page: int,
) -> Path:
    cache = get_local_cache()
    if uses_custom_pages(partset):
        return cache.ensure_partset_page(partset.id, kind, page)
    return cache.ensure_score_page(score.id, kind, page)


def _image_status_payload(
    *,
    images_ready: bool,
    images_warming: bool,
    image_progress: float,
    image_cache_error_message: str | None = None,
) -> dict[str, bool | float | str | None]:
    return {
        "images_ready": images_ready,
        "images_warming": images_warming,
        "image_progress": image_progress,
        "image_cache_error_message": image_cache_error_message,
    }


def _enqueue_warm_partset_pages(db: Session, partset: Partset) -> bool:
    """Enqueue a cache-only rebuild for rotated pages. Returns True if a job was enqueued."""
    if not partset.score_id:
        return False
    if not try_acquire_import_lock(partset.id):
        return False
    clear_partset_cache_error(partset.id)
    enqueue_job(
        "warm_partset_pages",
        {
            "partset_id": partset.id,
            "score_id": partset.score_id,
            "rotation_degrees": int(partset.rotation_degrees or 0),
        },
    )
    db.commit()
    return True


def _rotated_partset_images_ready(partset_id: str) -> bool:
    cache = get_local_cache()
    return cache.partset_has_kind(partset_id, "lowres") and cache.partset_has_kind(
        partset_id, "highres"
    )


def ensure_page_images_status(
    db: Session, partset: Partset, score: Score
) -> dict[str, bool | float | str | None]:
    if uses_custom_pages(partset):
        if _rotated_partset_images_ready(partset.id):
            clear_partset_cache_error(partset.id)
            return _image_status_payload(
                images_ready=True,
                images_warming=False,
                image_progress=100.0,
            )
        progress = import_progress_payload(partset)
        if progress["is_complete"]:
            cache_error = get_partset_cache_error(partset.id)
            if cache_error:
                return _image_status_payload(
                    images_ready=False,
                    images_warming=False,
                    image_progress=0.0,
                    image_cache_error_message=cache_error,
                )
            _enqueue_warm_partset_pages(db, partset)
            return _image_status_payload(
                images_ready=False,
                images_warming=True,
                image_progress=0.0,
            )
        clear_partset_cache_error(partset.id)
        return _image_status_payload(
            images_ready=False,
            images_warming=True,
            image_progress=float(progress["total_progress"]),
        )
    return ensure_score_pages_warming(db, score.id)


def retry_partset_page_cache(db: Session, partset: Partset) -> None:
    if not partset.score_id:
        raise ValueError("Partset has no score")
    if not uses_custom_pages(partset):
        raise ValueError("Partset does not use rotated page images")
    clear_partset_cache_error(partset.id)
    if not _enqueue_warm_partset_pages(db, partset):
        raise ValueError("Page images are already being prepared for this partset")


def reset_partset_for_reorient(db: Session, partset: Partset) -> None:
    """Clear segment/analysis state so the UI shows re-orient in progress immediately."""
    db.query(Segment).filter(Segment.partset_id == partset.id).delete()
    db.query(Page).filter(Page.partset_id == partset.id).delete()

    now = datetime.utcnow()
    partset.status = "convert"
    partset.convert_start = now
    partset.convert_complete = None
    partset.convert_progress = 0.0
    partset.analysis_start = None
    partset.analysis_complete = None
    partset.analysis_progress = 0.0
    partset.cut_start = None
    partset.cut_complete = None
    partset.cut_progress = 0.0
    partset.paste_start = None
    partset.paste_complete = None
    partset.paste_progress = 0.0
    partset.parts_ready = False
    partset.error = None
    partset.error_message = None
    partset.error_ts = None

    cache = get_local_cache()
    cache.invalidate_preview(partset.id)
    cache.invalidate_parts(partset.id)
    cache.invalidate_partset_pages(partset.id)


def start_reorient(db: Session, partset: Partset, rotation_degrees: int) -> str:
    if not partset.score_id:
        raise ValueError("Partset has no score")
    if not partset.import_complete:
        raise ValueError("Import not complete")
    score = db.get(Score, partset.score_id)
    if not score:
        raise ValueError("Partset has no score")
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    if not try_acquire_import_lock(partset.id):
        raise ValueError("A re-orient is already in progress for this partset")

    reset_partset_for_reorient(db, partset)

    score_orientation = score.orientation if score.orientation else "portrait"
    partset.rotation_degrees = rotation_degrees
    partset.orientation_override = layout_orientation(score_orientation, rotation_degrees)  # type: ignore[arg-type]

    job_id = enqueue_job(
        "reorient_partset",
        {
            "partset_id": partset.id,
            "score_id": partset.score_id,
            "rotation_degrees": rotation_degrees,
        },
    )
    db.commit()
    return job_id


def orientation_option_payload(
    private_id: str,
    degrees: int,
    score_orientation: str,
) -> dict[str, str | int]:
    layout = layout_orientation(score_orientation, degrees)  # type: ignore[arg-type]
    return {
        "degrees": degrees,
        "orientation": layout,
        "preview_url": f"/api/v1/partsets/{private_id}/orientation-preview/{degrees}.png",
    }


def orientation_data_payload(db: Session, partset: Partset, score: Score) -> dict:
    score_orientation = score.orientation if score.orientation else "portrait"
    current_degrees = int(partset.rotation_degrees or 0)
    reimport = import_progress_payload(partset)
    reimport_in_progress = bool(
        partset.import_complete
        and not reimport["is_complete"]
        and not reimport["error"]
    )
    return {
        "private_id": partset.private_id or "",
        "score_orientation": score_orientation,
        "current_rotation_degrees": current_degrees,
        "current_orientation": effective_orientation(partset, score),
        "rotation_options": [
            orientation_option_payload(partset.private_id or "", degrees, score_orientation)
            for degrees in ROTATION_OPTIONS
        ],
        "reimport_in_progress": reimport_in_progress,
        "reimport_progress": float(reimport["total_progress"]),
        "reimport_error": reimport["error"],
        "reimport_error_message": reimport["error_message"],
    }

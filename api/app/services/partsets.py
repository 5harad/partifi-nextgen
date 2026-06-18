import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Partset, Score
from app.services.library import claim_partset_for_user
from app.services.import_lock import try_acquire_import_lock
from app.services.queue import enqueue_job
from app.services.s3 import score_pdf_s3_key, upload_bytes
from app.services.score_cache import (
    copy_score_segs_to_partset,
    mark_import_pipeline_complete,
    score_analysis_complete,
)
from app.score_limits import MAX_SCORE_BYTES, reject_score_too_large
from app.utils.ids import gen_partset_ids, gen_score_id
from pipeline.pdf_validate import PDF_MAGIC, validate_pdf_bytes
from pipeline.score_pdf import score_has_archived_pdf, score_ready_for_reuse

logger = logging.getLogger(__name__)


def total_progress(status: str | None, progress: float) -> float:
    if not status:
        return 0.0
    if status == "import":
        return min(round(progress / 3), 33)
    if status == "convert":
        return min(round(100 / 3 + progress / 3), 66)
    if status == "analysis":
        return min(round(200 / 3 + progress / 3), 100)
    return 0.0


def import_progress_payload(partset: Partset) -> dict:
    is_complete = bool(
        partset.import_complete
        and partset.convert_complete
        and partset.analysis_complete
        and not partset.error
    )
    progress_key = f"{partset.status}_progress" if partset.status else "import_progress"
    stage_progress = getattr(partset, progress_key, 0.0) or 0.0
    return {
        "error": partset.error,
        "status": partset.status,
        "progress": stage_progress,
        "total_progress": 100.0 if is_complete else total_progress(partset.status, stage_progress),
        "is_complete": is_complete,
    }


def create_pdf_partset(
    db: Session,
    *,
    title: str,
    composer: str,
    publisher: str,
    copyright: str,
    file_hash: str,
    pdf_bytes: bytes,
    user_id: str | None = None,
) -> tuple[Partset, str]:
    if not pdf_bytes.startswith(PDF_MAGIC):
        raise ValueError("File is not a valid PDF")
    validate_pdf_bytes(pdf_bytes)
    if len(pdf_bytes) > MAX_SCORE_BYTES:
        raise reject_score_too_large(len(pdf_bytes), logger=logger)

    public_id, private_id = gen_partset_ids(db)
    now = datetime.utcnow()

    partset = Partset(
        id=public_id,
        private_id=private_id,
        title=title,
        composer=composer,
        publisher=publisher or None,
        copyright=copyright,
        create_ts=now,
        num_downloads=0,
        import_progress=0.0,
        convert_progress=0.0,
        analysis_progress=0.0,
        cut_progress=0.0,
        paste_progress=0.0,
    )
    db.add(partset)
    db.flush()

    existing = db.query(Score).filter(Score.file_hash == file_hash).first()
    if existing and score_ready_for_reuse(
        convert_complete=existing.convert_complete,
        num_pages=existing.num_pages,
    ):
        partset.score_id = existing.id
        partset.status = "import"
        partset.import_start = now
        partset.import_complete = now
        partset.import_progress = 100.0
        action = "continue"
        score_id = existing.id
    elif existing:
        score_id = existing.id
        partset.score_id = score_id
        partset.status = "import"
        partset.import_start = now
        partset.import_complete = now
        partset.import_progress = 100.0
        action = "continue"
        if not existing.s3:
            upload_bytes(score_pdf_s3_key(score_id), pdf_bytes, "application/pdf")
            existing.s3 = True
            existing.file_size = len(pdf_bytes)
    else:
        score_id = gen_score_id(db)
        score = Score(
            id=score_id,
            file_hash=file_hash,
            file_size=len(pdf_bytes),
            num_downloads=0,
            s3=False,
            import_start=now,
            import_complete=now,
        )
        db.add(score)
        partset.score_id = score_id
        partset.status = "import"
        partset.import_start = now
        partset.import_complete = now
        partset.import_progress = 100.0
        action = "upload"
        upload_bytes(score_pdf_s3_key(score_id), pdf_bytes, "application/pdf")

    if user_id:
        claim_partset_for_user(db, partset, user_id)

    db.commit()
    db.refresh(partset)

    if try_acquire_import_lock(public_id):
        enqueue_job(
            "import_pipeline",
            {"partset_id": public_id, "score_id": score_id},
        )

    return partset, action


def create_imslp_partset(
    db: Session,
    *,
    imslp_id: str,
    title: str,
    composer: str,
    publisher: str,
    copyright: str,
    user_id: str | None = None,
) -> tuple[Partset, str]:
    from app.services.imslp import (
        ImslpLookupError,
        ImslpLookupUnavailableError,
        ensure_imslp_info_for_import,
        normalize_imslp_id,
    )
    from app.services.imslp_pdf import ingest_imslp_pdf_bytes, resolve_imslp_pdf_for_import

    normalized = normalize_imslp_id(imslp_id)
    if not normalized:
        raise ValueError("Invalid IMSLP id")

    try:
        ensure_imslp_info_for_import(db, normalized)
    except ImslpLookupError as exc:
        raise ValueError(str(exc)) from exc
    except ImslpLookupUnavailableError as exc:
        raise ValueError(str(exc)) from exc

    existing_score = db.query(Score).filter(Score.imslp_id == normalized).first()
    if existing_score and existing_score.file_size and existing_score.file_size > MAX_SCORE_BYTES:
        raise reject_score_too_large(
            existing_score.file_size,
            logger=logger,
            imslp_id=normalized,
        )

    reuse_score = bool(
        existing_score
        and existing_score.file_size
        and score_ready_for_reuse(
            convert_complete=existing_score.convert_complete,
            num_pages=existing_score.num_pages,
        )
    )

    pdf_url: str | None = None
    pdf_bytes: bytes | None = None
    if not reuse_score:
        try:
            pdf_url, pdf_bytes = resolve_imslp_pdf_for_import(normalized)
        except ImslpLookupUnavailableError as exc:
            raise ValueError(str(exc)) from exc

    public_id, private_id = gen_partset_ids(db)
    now = datetime.utcnow()

    partset = Partset(
        id=public_id,
        private_id=private_id,
        imslp_id=normalized,
        title=title.strip(),
        composer=composer.strip(),
        publisher=publisher.strip() or None,
        copyright=copyright,
        create_ts=now,
        num_downloads=0,
        import_progress=0.0,
        convert_progress=0.0,
        analysis_progress=0.0,
        cut_progress=0.0,
        paste_progress=0.0,
    )
    db.add(partset)
    db.flush()

    if reuse_score:
        assert existing_score is not None
        partset.score_id = existing_score.id
        partset.status = "import"
        partset.import_start = now
        partset.import_complete = now
        partset.import_progress = 100.0
        if user_id:
            claim_partset_for_user(db, partset, user_id)
        db.commit()
        db.refresh(partset)
        if try_acquire_import_lock(public_id):
            enqueue_job(
                "import_pipeline",
                {"partset_id": public_id, "score_id": existing_score.id},
            )
        return partset, "continue"

    partset.status = "import"
    partset.import_start = now
    if user_id:
        claim_partset_for_user(db, partset, user_id)

    action = "continue"
    if pdf_bytes is not None:
        score_id, action = ingest_imslp_pdf_bytes(db, normalized, pdf_bytes)
        partset.score_id = score_id
        partset.import_complete = now
        partset.import_progress = 100.0
        db.commit()
        db.refresh(partset)
        if try_acquire_import_lock(public_id):
            enqueue_job(
                "import_pipeline",
                {"partset_id": public_id, "score_id": score_id},
            )
        return partset, action

    db.commit()
    db.refresh(partset)
    if try_acquire_import_lock(public_id):
        payload: dict[str, str] = {"partset_id": public_id, "imslp_id": normalized}
        if pdf_url:
            payload["pdf_url"] = pdf_url
        enqueue_job("imslp_import", payload)
    return partset, "continue"


def create_partset_from_score(
    db: Session,
    *,
    score_id: str,
    title: str,
    composer: str,
    publisher: str,
    copyright: str,
    user_id: str | None = None,
) -> Partset:
    score = db.get(Score, score_id)
    if not score:
        raise ValueError("Score not found")
    if not score_has_archived_pdf(s3=score.s3, file_size=score.file_size):
        raise ValueError("Score PDF is not available")

    public_id, private_id = gen_partset_ids(db)
    now = datetime.utcnow()

    partset = Partset(
        id=public_id,
        private_id=private_id,
        score_id=score_id,
        title=title.strip(),
        composer=composer.strip(),
        publisher=publisher.strip() or None,
        copyright=copyright,
        create_ts=now,
        num_downloads=0,
        import_progress=0.0,
        convert_progress=0.0,
        analysis_progress=0.0,
        cut_progress=0.0,
        paste_progress=0.0,
    )
    db.add(partset)
    db.flush()

    if score_analysis_complete(db, score_id):
        mark_import_pipeline_complete(db, partset, score)
        copy_score_segs_to_partset(db, score_id, public_id)
        if user_id:
            claim_partset_for_user(db, partset, user_id)
        db.commit()
        db.refresh(partset)
        return partset

    partset.status = "import"
    partset.import_start = now
    partset.import_complete = now
    partset.import_progress = 100.0
    if user_id:
        claim_partset_for_user(db, partset, user_id)
    db.commit()
    db.refresh(partset)

    if try_acquire_import_lock(public_id):
        enqueue_job(
            "import_pipeline",
            {"partset_id": public_id, "score_id": score_id},
        )
    return partset

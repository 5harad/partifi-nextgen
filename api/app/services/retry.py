"""Re-enqueue failed or interrupted pipeline jobs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Partset
from app.services.gen_parts_lock import try_acquire_gen_parts_lock
from app.services.import_lock import try_acquire_import_lock
from app.services.partset_failure import clear_partset_failure
from app.services.queue import enqueue_job


def import_pipeline_complete(partset: Partset) -> bool:
    return bool(
        partset.import_complete
        and partset.convert_complete
        and partset.analysis_complete
    )


def ensure_import_if_needed(db: Session, partset: Partset) -> str | None:
    """Enqueue import work when the pipeline is incomplete. Idempotent while a job holds the lock."""
    if import_pipeline_complete(partset):
        return None
    if partset.error:
        return None
    if not partset.score_id and not partset.imslp_id:
        return None

    if not try_acquire_import_lock(partset.id):
        return None

    now = datetime.utcnow()
    if partset.import_start is None:
        partset.import_start = now
    if partset.status is None:
        partset.status = "import"

    if partset.score_id:
        job_id = enqueue_job(
            "import_pipeline",
            {"partset_id": partset.id, "score_id": partset.score_id},
        )
    else:
        job_id = enqueue_job(
            "imslp_import",
            {"partset_id": partset.id, "imslp_id": partset.imslp_id},
        )
    db.commit()
    return job_id


def retry_partset_pipeline(db: Session, partset: Partset) -> tuple[str, str | None]:
    """Clear error and enqueue import or partgen work. Returns (stage, job_id)."""
    clear_partset_failure(partset)

    if not import_pipeline_complete(partset):
        if partset.score_id:
            if not try_acquire_import_lock(partset.id):
                db.commit()
                return "import", None
            job_id = enqueue_job(
                "import_pipeline",
                {"partset_id": partset.id, "score_id": partset.score_id},
            )
            db.commit()
            return "import", job_id
        if partset.imslp_id:
            if not try_acquire_import_lock(partset.id):
                db.commit()
                return "import", None
            job_id = enqueue_job(
                "imslp_import",
                {"partset_id": partset.id, "imslp_id": partset.imslp_id},
            )
            db.commit()
            return "import", job_id
        raise ValueError("Partset has no score to import")

    if partset.parts_ready:
        raise ValueError("Nothing to retry")

    if not try_acquire_gen_parts_lock(partset.id):
        db.commit()
        return "partgen", None

    job_id = enqueue_job("gen_parts", {"partset_id": partset.id})
    db.commit()
    return "partgen", job_id

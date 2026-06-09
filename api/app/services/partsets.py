from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Partset, Score
from app.services.queue import enqueue_job
from app.services.s3 import upload_bytes
from app.utils.ids import gen_partset_ids, gen_score_id

MAX_UPLOAD_BYTES = 60_000_000
PDF_MAGIC = b"%PDF"


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
    bcookie: str | None = None,
    ip_address: str | None = None,
) -> tuple[Partset, str]:
    if not pdf_bytes.startswith(PDF_MAGIC):
        raise ValueError("File is not a valid PDF")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 60 MB limit")

    public_id, private_id = gen_partset_ids(db)
    now = datetime.utcnow()

    partset = Partset(
        id=public_id,
        private_id=private_id,
        title=title,
        composer=composer,
        publisher=publisher or None,
        copyright=copyright,
        bcookie=bcookie,
        ip_address=ip_address,
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
    if existing:
        partset.score_id = existing.id
        partset.status = "import"
        partset.import_start = now
        partset.import_complete = now
        partset.import_progress = 100.0
        action = "continue"
        score_id = existing.id
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
        upload_bytes(f"scores/{score_id}/score.pdf", pdf_bytes, "application/pdf")

    db.commit()
    db.refresh(partset)

    enqueue_job(
        "import_pipeline",
        {"partset_id": public_id, "score_id": score_id},
    )

    return partset, action

"""Seed a landscape score with visible content for local UI audit (run in worker container)."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import db_conn
from jobs.import_pipeline import run_import_pipeline
from pipeline.ids import rand_partifi_id
from s3_storage import get_s3_client, score_pdf_s3_key, upload_file
from config import get_settings


def _new_id(table: str) -> str:
    while True:
        candidate = rand_partifi_id()
        row = db_conn.fetchone(f"SELECT id FROM {table} WHERE id = :id", {"id": candidate})
        if not row:
            return candidate


def _make_landscape_audit_pdf(path: Path) -> None:
    pagesize = landscape(letter)
    width, height = pagesize
    c = canvas.Canvas(str(path), pagesize=pagesize)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 48, "Landscape audit score")

    # Three visible "systems" of staff lines for segment tagging.
    system_tops = [height - 140, height - 280, height - 420]
    for system_idx, top in enumerate(system_tops, start=1):
        c.setFont("Helvetica", 11)
        c.drawString(72, top + 28, f"System {system_idx}")
        for line in range(5):
            y = top - line * 10
            c.line(72, y, width - 72, y)

    c.setFont("Helvetica", 10)
    c.drawString(72, 48, "Partifi landscape UI audit — tag systems as separate parts")
    c.showPage()
    c.save()


def _ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)


def main() -> None:
    workdir = Path("/tmp/partifi/landscape-audit")
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_path = workdir / "landscape-audit.pdf"
    _make_landscape_audit_pdf(pdf_path)
    _ensure_bucket()

    score_id = _new_id("scores")
    partset_id = _new_id("partsets")
    private_id = _new_id("partsets")
    now = datetime.utcnow()
    pdf_bytes = pdf_path.read_bytes()
    file_hash = hashlib.sha1(pdf_bytes).hexdigest()

    upload_file(pdf_path, score_pdf_s3_key(score_id), "application/pdf")

    db_conn.execute(
        """
        INSERT INTO scores (
            id, file_hash, file_size, import_start, import_complete,
            num_downloads, s3, orientation
        ) VALUES (
            :id, :file_hash, :file_size, :now, :now, 0, 1, 'portrait'
        )
        """,
        {
            "id": score_id,
            "file_hash": file_hash,
            "file_size": len(pdf_bytes),
            "now": now,
        },
    )
    db_conn.execute(
        """
        INSERT INTO partsets (
            id, private_id, score_id, create_ts, status,
            import_start, import_complete, import_progress
        ) VALUES (
            :id, :private_id, :score_id, :now, 'import',
            :now, :now, 100
        )
        """,
        {
            "id": partset_id,
            "private_id": private_id,
            "score_id": score_id,
            "now": now,
        },
    )

    print(f"Importing landscape audit score...")
    print(f"  score_id={score_id}")
    print(f"  partset_id={partset_id}")
    print(f"  private_id={private_id}")
    run_import_pipeline(partset_id, score_id, job_id="landscape-audit")

    score = db_conn.fetchone(
        "SELECT orientation, num_pages FROM scores WHERE id = :id",
        {"id": score_id},
    )
    if not score or score.orientation != "landscape":
        raise SystemExit(f"expected landscape orientation, got {getattr(score, 'orientation', None)}")

    print(f"  orientation={score.orientation} pages={score.num_pages}")
    print()
    print("Open in browser:")
    print(f"  http://localhost:5173/{private_id}/segment")
    print(f"  http://localhost:5173/{private_id}/preview  (after tagging parts)")


if __name__ == "__main__":
    main()

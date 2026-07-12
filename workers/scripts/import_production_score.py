"""Import a production score PDF into local Docker for UI audit.

Downloads from https://partifi.org/api/v1/scores/{score_id}/score.pdf,
uploads to local MinIO, creates score/partset rows, and runs import_pipeline.

Usage (inside worker container):
  python scripts/import_production_score.py rcype-ncnsf
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import httpx

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import db_conn
from jobs.import_pipeline import run_import_pipeline
from pipeline.ids import rand_partifi_id
from s3_storage import get_s3_client, score_pdf_s3_key, upload_file
from config import get_settings

PRODUCTION_API = "https://partifi.org"


def _new_id(table: str) -> str:
    while True:
        candidate = rand_partifi_id()
        row = db_conn.fetchone(f"SELECT id FROM {table} WHERE id = :id", {"id": candidate})
        if not row:
            return candidate


def _ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)


def _download_production_pdf(score_id: str, dest: Path) -> None:
    url = f"{PRODUCTION_API}/api/v1/scores/{score_id}/score.pdf"
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"Expected PDF from {url}")
        dest.write_bytes(response.content)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(__file__).name} <production_score_id>")

    source_score_id = sys.argv[1].strip()
    workdir = Path("/tmp/partifi/import-production")
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_path = workdir / f"{source_score_id}.pdf"

    print(f"Downloading {source_score_id} from {PRODUCTION_API}...")
    _download_production_pdf(source_score_id, pdf_path)
    print(f"  saved {pdf_path} ({pdf_path.stat().st_size:,} bytes)")

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

    print(f"Importing (source={source_score_id})...")
    print(f"  local score_id={score_id}")
    print(f"  partset_id={partset_id}")
    print(f"  private_id={private_id}")
    run_import_pipeline(partset_id, score_id, job_id="audit-import")

    score = db_conn.fetchone(
        "SELECT orientation, num_pages FROM scores WHERE id = :id",
        {"id": score_id},
    )
    seg_count = db_conn.fetchone(
        "SELECT COUNT(*) AS n FROM segments WHERE partset_id = :id",
        {"id": partset_id},
    )
    print(
        f"  orientation={score.orientation} pages={score.num_pages} "
        f"segments={seg_count.n if seg_count else 0}"
    )
    print()
    print("Open in browser:")
    print(f"  http://localhost:5173/{private_id}/segment")
    print(f"  http://localhost:5173/{private_id}/preview  (after tagging parts)")


if __name__ == "__main__":
    main()

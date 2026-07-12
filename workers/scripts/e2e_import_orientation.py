"""End-to-end import test for portrait and landscape scores (run inside worker container)."""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from PIL import Image
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

import db_conn
from jobs.import_pipeline import run_import_pipeline
from local_cache import get_local_cache
from pipeline.ids import rand_partifi_id
from s3_storage import get_s3_client, score_pdf_s3_key, upload_file
from config import get_settings

CASES = [
    ("portrait", letter, "portrait", (600, 776)),
    ("landscape", landscape(letter), "landscape", (776, 600)),
]


def _new_id(table: str) -> str:
    while True:
        candidate = rand_partifi_id()
        row = db_conn.fetchone(f"SELECT id FROM {table} WHERE id = :id", {"id": candidate})
        if not row:
            return candidate


def _make_pdf(path: Path, pagesize) -> None:
    c = canvas.Canvas(str(path), pagesize=pagesize)
    _width, height = pagesize
    c.drawString(72, height - 72, "e2e test")
    c.showPage()
    c.save()


def _ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket)


def _setup_score_and_partset(label: str, pdf_path: Path) -> tuple[str, str]:
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
    print(f"  created score={score_id} partset={partset_id} ({label})")
    return score_id, partset_id


def _assert_import(score_id: str, partset_id: str, expected_orientation: str, expected_lowres: tuple[int, int]) -> None:
    score = db_conn.fetchone(
        "SELECT orientation, convert_complete, analysis_complete, num_pages FROM scores WHERE id = :id",
        {"id": score_id},
    )
    partset = db_conn.fetchone(
        "SELECT convert_complete, analysis_complete, error FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    if not score or not partset:
        raise SystemExit(f"missing rows for score={score_id} partset={partset_id}")
    if partset.error:
        row = db_conn.fetchone(
            "SELECT error, error_message FROM partsets WHERE id = :id",
            {"id": partset_id},
        )
        raise SystemExit(f"partset error={row.error} message={row.error_message}")
    if score.orientation != expected_orientation:
        raise SystemExit(f"orientation: {score.orientation} != {expected_orientation}")
    if not score.convert_complete or not score.analysis_complete:
        raise SystemExit("convert or analysis not complete on score")
    if not partset.convert_complete or not partset.analysis_complete:
        raise SystemExit("convert or analysis not complete on partset")
    if int(score.num_pages or 0) < 1:
        raise SystemExit("num_pages not set")

    cache = get_local_cache()
    lowres = cache.score_page_path(score_id, "lowres", 1)
    if not lowres.is_file():
        raise SystemExit(f"missing cached lowres: {lowres}")
    with Image.open(lowres) as im:
        if im.size != expected_lowres:
            raise SystemExit(f"lowres size {im.size} != {expected_lowres}")

    seg_count = db_conn.fetchone(
        "SELECT COUNT(*) AS n FROM segments WHERE partset_id = :id",
        {"id": partset_id},
    )
    if not seg_count or int(seg_count.n) < 1:
        raise SystemExit("no segments after analysis")

    print(
        f"  OK orientation={score.orientation} pages={score.num_pages} "
        f"lowres={expected_lowres} segments={seg_count.n}"
    )


def main() -> None:
    workdir = Path("/tmp/partifi/e2e-orientation")
    workdir.mkdir(parents=True, exist_ok=True)
    _ensure_bucket()

    for label, pagesize, expected_orientation, expected_lowres in CASES:
        print(f"Testing {label}...")
        pdf_path = workdir / f"{label}.pdf"
        _make_pdf(pdf_path, pagesize)
        score_id, partset_id = _setup_score_and_partset(label, pdf_path)
        run_import_pipeline(partset_id, score_id, job_id="e2e")
        _assert_import(score_id, partset_id, expected_orientation, expected_lowres)

    print("E2E import orientation test passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise

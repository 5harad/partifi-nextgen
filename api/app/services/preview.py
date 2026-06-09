"""Preview layout: lowres cut, breaks/spacings, combine parts, part generation."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Break, Part, Partset, Segment
from app.services.queue import enqueue_job
from app.services.s3 import get_s3_client, presigned_get_url
from app.services.segments import ensure_import_complete, get_partset_by_private_id
from app.utils.strings import tag_to_filename

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
for root in (APP_ROOT, REPO_ROOT):
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

from pipeline.cut_segments import cut_segment_tasks  # noqa: E402
from pipeline.cutpaste import (  # noqa: E402
    apply_combined_parts,
    build_part_segment_map,
    preview_left_margin,
    prct2pixel,
)

from app.config import get_settings


def _partgen_total_progress(status: str | None, progress: float) -> float:
    if status == "convert":
        return min(round(progress / 3), 33)
    if status == "cut":
        return min(round(33 + progress / 3), 66)
    if status == "paste":
        return min(round(66 + progress / 3), 99)
    return 0.0


def partgen_progress_payload(partset: Partset) -> dict:
    is_complete = bool(partset.parts_ready)
    progress = 0.0
    if partset.status == "cut":
        progress = partset.cut_progress or 0.0
    elif partset.status == "paste":
        progress = partset.paste_progress or 0.0
    elif partset.status == "convert":
        progress = partset.convert_progress or 0.0

    return {
        "error": partset.error,
        "status": partset.status,
        "progress": progress,
        "total_progress": 100.0 if is_complete else _partgen_total_progress(partset.status, progress),
        "is_complete": is_complete,
    }


def _fetch_segment_rows(db: Session, partset_id: str) -> list[dict]:
    from app.models import Page

    rows = (
        db.query(
            Page.page,
            Page.rotation,
            Page.left_margin,
            Page.right_margin,
            Segment.top,
            Segment.bottom,
            Segment.tags,
            Segment.label,
        )
        .join(
            Segment,
            (Page.partset_id == Segment.partset_id) & (Page.page == Segment.page),
        )
        .filter(
            Page.partset_id == partset_id,
            Segment.tags.isnot(None),
            Segment.tags != "",
        )
        .order_by(Page.page, Segment.top)
        .all()
    )
    return [
        {
            "page": row.page,
            "rotation": float(row.rotation or 0),
            "left_margin": float(row.left_margin or 0),
            "right_margin": float(row.right_margin or 100),
            "top": float(row.top or 0),
            "bottom": float(row.bottom or 0),
            "tags": row.tags,
            "label": row.label,
        }
        for row in rows
    ]


def _get_breaks(db: Session, partset_id: str) -> dict[str, list[int]]:
    breaks: dict[str, list[int]] = {}
    for row in db.query(Break).filter(Break.partset_id == partset_id).all():
        if row.break_ is not None:
            breaks.setdefault(row.tag, []).append(int(row.break_))
    return breaks


def _get_spacings(db: Session, partset_id: str) -> dict[str, float]:
    spacings: dict[str, float] = {}
    for row in db.query(Part).filter(Part.partset_id == partset_id).all():
        spacings[row.tag] = float(row.spacing if row.spacing is not None else 0.1)
    return spacings


def _cut_preview_segments(
    partset: Partset,
    segment_rows: list[dict],
    workdir: Path,
) -> None:
    settings = get_settings()
    client = get_s3_client()
    pages_dir = workdir / "pages"
    segments_dir = workdir / "segments"
    pages_dir.mkdir(parents=True)
    segments_dir.mkdir(parents=True)

    pages_needed = sorted({row["page"] for row in segment_rows})
    for page in pages_needed:
        key = f"scores/{partset.score_id}/lowres/page-{page}.png"
        local_page = pages_dir / f"page-{page}.png"
        local_page.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(settings.s3_bucket, key, str(local_page))

    cut_tasks: list[tuple[Path, float, float, float, float, float, Path]] = []
    for ndx, row in enumerate(segment_rows):
        page_path = pages_dir / f"page-{row['page']}.png"
        out_path = segments_dir / f"s{ndx}.png"
        cut_tasks.append(
            (
                page_path,
                row["rotation"],
                row["left_margin"],
                row["top"],
                row["right_margin"],
                row["bottom"],
                out_path,
            )
        )
    cut_segment_tasks(cut_tasks, pool_size=1)

    prefix = f"tmp/{partset.id}/preview"
    for ndx in range(len(segment_rows)):
        local_seg = segments_dir / f"s{ndx}.png"
        key = f"{prefix}/s{ndx}.png"
        client.upload_file(
            str(local_seg),
            settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": "image/png"},
        )


def get_preview_data(db: Session, partset: Partset) -> dict:
    ensure_import_complete(partset)
    if not partset.score_id:
        raise ValueError("Partset has no score")

    segment_rows = _fetch_segment_rows(db, partset.id)
    segments_map, heights_pct, widths_pct, labels = build_part_segment_map(segment_rows)

    combined_rows = (
        db.query(Part.tag)
        .filter(Part.partset_id == partset.id, Part.combined.is_(True))
        .all()
    )
    combined_part_names = [row.tag for row in combined_rows]
    apply_combined_parts(segments_map, combined_part_names)

    part_names = sorted(
        tag for tag in segments_map.keys() if tag not in combined_part_names
    )

    if not part_names and not combined_part_names:
        raise ValueError("No parts tagged")

    workdir = Path(f"/tmp/partifi/{partset.id}/preview")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    _cut_preview_segments(partset, segment_rows, workdir)
    shutil.rmtree(workdir, ignore_errors=True)

    segment_heights = [prct2pixel(h) for h in heights_pct]
    segment_widths = [prct2pixel(w, "width") for w in widths_pct]
    breaks = _get_breaks(db, partset.id)
    spacings = _get_spacings(db, partset.id)

    all_names = part_names + combined_part_names
    for name in all_names:
        breaks.setdefault(name, [])
        spacings.setdefault(name, 0.1)

    segment_urls = {
        str(ndx): presigned_get_url(f"tmp/{partset.id}/preview/s{ndx}.png")
        for ndx in range(len(segment_rows))
    }

    return {
        "partset_id": partset.id,
        "private_id": partset.private_id or "",
        "title": partset.title,
        "composer": partset.composer,
        "part_names": part_names,
        "combined_part_names": combined_part_names,
        "part_segments": segments_map,
        "segment_heights": segment_heights,
        "segment_widths": segment_widths,
        "segment_labels": labels,
        "breaks": breaks,
        "spacings": spacings,
        "left_margin": preview_left_margin(widths_pct),
        "segment_urls": segment_urls,
    }


def save_layout(db: Session, partset: Partset, breaks: dict[str, list[int]], spacings: dict[str, float]) -> None:
    partset.parts_ready = False
    partset.cut_start = None
    partset.cut_complete = None
    partset.cut_progress = 0.0
    partset.paste_start = None
    partset.paste_complete = None
    partset.paste_progress = 0.0
    partset.status = "analysis"

    db.query(Break).filter(Break.partset_id == partset.id).delete()
    for tag, breakpoints in breaks.items():
        for brk in breakpoints:
            db.add(Break(partset_id=partset.id, tag=tag, break_=int(brk)))

    for tag, spacing in spacings.items():
        part = (
            db.query(Part)
            .filter(Part.partset_id == partset.id, Part.tag == tag)
            .first()
        )
        if part:
            part.spacing = float(spacing)

    db.commit()


def combine_parts(db: Session, partset: Partset, action: str, tag: str) -> None:
    partset.parts_ready = False
    partset.cut_start = None
    partset.cut_complete = None
    partset.cut_progress = 0.0
    partset.paste_start = None
    partset.paste_complete = None
    partset.paste_progress = 0.0
    partset.status = "analysis"

    if action == "add":
        filename = tag_to_filename(tag)
        existing = (
            db.query(Part)
            .filter(Part.partset_id == partset.id, Part.tag == tag)
            .first()
        )
        if existing:
            existing.combined = True
            existing.spacing = 0.1
            existing.file_name = filename
        else:
            db.add(
                Part(
                    partset_id=partset.id,
                    tag=tag,
                    spacing=0.1,
                    combined=True,
                    file_name=filename,
                )
            )
    elif action == "remove":
        db.query(Part).filter(
            Part.partset_id == partset.id,
            Part.tag == tag,
            Part.combined.is_(True),
        ).delete()
    else:
        raise ValueError("Invalid combine action")

    db.commit()


def start_part_generation(db: Session, partset: Partset) -> str | None:
    if partset.parts_ready:
        return None

    num_parts = (
        db.query(Part)
        .filter(Part.partset_id == partset.id, Part.combined.is_(False))
        .count()
    )
    if num_parts == 0:
        partset.parts_ready = True
        db.commit()
        return None

    job_id = enqueue_job("gen_parts", {"partset_id": partset.id})
    return job_id


def get_parts_data(db: Session, partset: Partset) -> dict:
    ensure_import_complete(partset)
    parts = (
        db.query(Part)
        .filter(Part.partset_id == partset.id)
        .order_by(Part.combined, Part.tag)
        .all()
    )

    download_items = []
    for part in parts:
        letter_name = f"{partset.id}_{part.file_name}"
        a4_name = f"{partset.id}_a4_{part.file_name}"
        letter_key = f"parts/{partset.id}/{letter_name}"
        a4_key = f"parts/{partset.id}/{a4_name}"
        download_items.append(
            {
                "tag": part.tag,
                "file_name": part.file_name or "",
                "letter_url": presigned_get_url(letter_key, download_name=letter_name),
                "a4_url": presigned_get_url(a4_key, download_name=a4_name),
            }
        )

    score_pdf_url = None
    if partset.score_id:
        score_name = f"{partset.score_id}_score.pdf"
        score_pdf_url = presigned_get_url(
            f"scores/{partset.score_id}/score.pdf",
            download_name=score_name,
        )

    return {
        "partset_id": partset.id,
        "private_id": partset.private_id or "",
        "public_id": partset.id,
        "title": partset.title,
        "composer": partset.composer,
        "publisher": partset.publisher,
        "score_pdf_url": score_pdf_url,
        "parts": download_items,
        "parts_ready": bool(partset.parts_ready),
    }

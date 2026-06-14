from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Page, Part, Partset, Score, Segment
from app.services.local_cache import get_local_cache
from app.services.partset_touch import touch_partset_access
from app.services.score_pages import ensure_score_pages_warming
from app.utils.strings import rm_space, tag_to_filename

ScoreImageKind = str


def page_image_url(private_id: str, page: int, res: ScoreImageKind) -> str:
    return f"/api/v1/partsets/{private_id}/page-image/{page}.png?res={res}"


def _sync_part_rows_from_tags(db: Session, partset_id: str) -> None:
    tags_set: set[str] = set()
    rows = db.query(Segment.tags).filter(
        Segment.partset_id == partset_id,
        Segment.tags.isnot(None),
        Segment.tags != "",
    ).all()
    for (tag_row,) in rows:
        for tag in tag_row.split(","):
            cleaned = rm_space(tag)
            if cleaned and cleaned not in {"all", "All", "ALL", "(none)"}:
                tags_set.add(cleaned)

    parts_by_tag = {
        part.tag: part
        for part in db.query(Part).filter(Part.partset_id == partset_id).all()
    }

    for tag in tags_set:
        if tag in parts_by_tag:
            continue
        filename = tag_to_filename(tag)
        part = Part(
            partset_id=partset_id,
            tag=tag,
            spacing=0.1,
            combined=False,
            file_name=filename,
        )
        db.add(part)
        parts_by_tag[tag] = part

    for part in list(parts_by_tag.values()):
        part_tags = [t.strip() for t in part.tag.split(" + ")]
        if not all(t in tags_set for t in part_tags if t):
            db.delete(part)


def get_partset_by_private_id(db: Session, private_id: str) -> Partset | None:
    return db.query(Partset).filter(Partset.private_id == private_id).first()


def ensure_import_complete(partset: Partset) -> None:
    if not (partset.import_complete and partset.convert_complete and partset.analysis_complete):
        raise ValueError("Import not complete")


def get_num_pages(db: Session, partset_id: str, score_id: str | None) -> int:
    count = db.scalar(
        select(func.count()).select_from(Page).where(Page.partset_id == partset_id)
    )
    if count:
        return int(count)
    if score_id:
        score = db.get(Score, score_id)
        if score and score.num_pages:
            return int(score.num_pages)
    return 0


def get_segments_data(db: Session, partset: Partset) -> dict:
    ensure_import_complete(partset)
    if not partset.score_id:
        raise ValueError("Partset has no score")

    touch_partset_access(db, partset)

    data: dict[str, dict] = {}
    pages = (
        db.query(Page)
        .filter(Page.partset_id == partset.id)
        .order_by(Page.page)
        .all()
    )
    for row in pages:
        key = f"p{row.page}"
        data[key] = {
            "left_margin": float(row.left_margin or 0),
            "right_margin": float(row.right_margin or 100),
            "rotation": float(row.rotation or 0),
            "segments": [],
        }

    segments = (
        db.query(Segment)
        .filter(Segment.partset_id == partset.id)
        .order_by(Segment.page, Segment.top)
        .all()
    )
    for row in segments:
        key = f"p{row.page}"
        if key not in data:
            data[key] = {
                "left_margin": 0.0,
                "right_margin": 100.0,
                "rotation": 0.0,
                "segments": [],
            }
        data[key]["segments"].append(
            {
                "pos": [float(row.top or 0), float(row.bottom or 0)],
                "tags": row.tags or "",
                "tag_is_suggestion": bool(row.tag_is_suggestion),
                "label": row.label or "",
                "label_is_suggestion": bool(row.label_is_suggestion),
            }
        )

    num_pages = get_num_pages(db, partset.id, partset.score_id)
    private_id = partset.private_id or ""
    image_status = ensure_score_pages_warming(partset.score_id)
    image_urls: dict[str, dict[str, str]] = {"lowres": {}, "thumbs": {}}
    for page in range(1, num_pages + 1):
        image_urls["lowres"][str(page)] = page_image_url(private_id, page, "lowres")
        image_urls["thumbs"][str(page)] = page_image_url(private_id, page, "thumbs")

    return {
        "score_id": partset.score_id,
        "partset_id": partset.id,
        "private_id": private_id,
        "num_pages": num_pages,
        "pages": data,
        "image_urls": image_urls,
        **image_status,
    }


def sync_part_rows_from_tags(db: Session, partset_id: str) -> None:
    _sync_part_rows_from_tags(db, partset_id)


def _reset_partset_for_segment_edit(partset: Partset) -> None:
    partset.parts_ready = False
    partset.cut_start = None
    partset.cut_complete = None
    partset.cut_progress = 0.0
    partset.paste_start = None
    partset.paste_complete = None
    partset.paste_progress = 0.0
    partset.status = "analysis"


def _apply_page_segment_payload(
    db: Session,
    partset_id: str,
    page: int,
    payload: dict,
) -> None:
    db.query(Page).filter(Page.partset_id == partset_id, Page.page == page).update(
        {
            Page.left_margin: payload["left_margin"],
            Page.right_margin: payload["right_margin"],
            Page.rotation: payload["rotation"],
        }
    )

    db.query(Segment).filter(
        Segment.partset_id == partset_id, Segment.page == page
    ).delete()

    for segment in payload["segments"]:
        tags = rm_space(segment.get("tags", ""))
        tags = ", ".join(t for t in (x.strip() for x in tags.split(",")) if t)
        label = rm_space(segment.get("label", ""))
        db.add(
            Segment(
                partset_id=partset_id,
                page=page,
                top=segment["pos"][0],
                bottom=segment["pos"][1],
                tags=tags or None,
                tag_is_suggestion=segment.get("tag_is_suggestion", False),
                label=label or None,
                label_is_suggestion=segment.get("label_is_suggestion", False),
            )
        )


def _finalize_segment_save(db: Session, partset_id: str) -> None:
    # Session uses autoflush=False (see app.db); pending Segment inserts are not
    # visible to queries until flush, so sync must run after flush not before commit.
    db.flush()
    _sync_part_rows_from_tags(db, partset_id)
    cache = get_local_cache()
    cache.invalidate_preview(partset_id)
    cache.invalidate_parts(partset_id)
    db.commit()


def save_page_segments(
    db: Session,
    partset: Partset,
    page: int,
    payload: dict,
) -> None:
    _reset_partset_for_segment_edit(partset)
    _apply_page_segment_payload(db, partset.id, page, payload)
    _finalize_segment_save(db, partset.id)


def save_all_page_segments(
    db: Session,
    partset: Partset,
    pages: dict[str, dict],
) -> None:
    num_pages = get_num_pages(db, partset.id, partset.score_id)
    if num_pages <= 0:
        raise ValueError("Partset has no pages")

    for page_num in range(1, num_pages + 1):
        key = f"p{page_num}"
        if key not in pages:
            raise ValueError(f"Missing segment data for page {page_num}")

    _reset_partset_for_segment_edit(partset)
    for page_num in range(1, num_pages + 1):
        _apply_page_segment_payload(db, partset.id, page_num, pages[f"p{page_num}"])
    _finalize_segment_save(db, partset.id)

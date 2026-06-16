"""Build part PDFs from cut segment PNGs (Python 3 port of legacy paste_segments.py)."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import black, gray
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from pipeline.pdf_fonts import set_header_font, set_header_font_for_fields

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "scroll.png"
RESOLUTION = 300.0


@lru_cache
def _logo_image_reader() -> ImageReader | None:
    if not LOGO_PATH.is_file():
        return None
    im = Image.open(LOGO_PATH).convert("RGBA")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[3])
    return ImageReader(bg)


def _add_page_info(
    doc: canvas.Canvas,
    left: float,
    right: float,
    center: float,
    top: float,
    bottom: float,
    title: str,
    composer: str,
    part_name: str,
    partset_id: str,
    page_num: int,
) -> None:
    left_in = left * inch
    right_in = right * inch
    center_in = center * inch
    top_in = top * inch
    bottom_in = bottom * inch

    if reader := _logo_image_reader():
        doc.drawImage(reader, left_in, top_in - 24, 24, 24)

    part_name_text = str(part_name)
    page_label = f"Page {page_num}"
    set_header_font_for_fields(
        doc,
        title,
        composer,
        part_name_text,
        partset_id,
        f"partifi.org/{partset_id}",
        page_label,
        size=11,
    )
    doc.drawString(left_in + 28, top_in - 12, title)
    doc.drawString(left_in + 28, top_in - 24, composer)
    doc.drawRightString(right_in, top_in - 12, part_name_text)
    doc.drawRightString(right_in, top_in - 24, f"partifi.org/{partset_id}")
    doc.drawCentredString(center_in, bottom_in, page_label)
    doc.line(left_in, top_in - 36, right_in, top_in - 36)


def _max_segment_width(pages: list[list[dict]]) -> int:
    max_width = 0
    for page in pages:
        for seg in page:
            with Image.open(seg["file"]) as im:
                max_width = max(max_width, im.size[0])
    return max_width


def _add_images(
    doc: canvas.Canvas,
    images: list[dict],
    x: float,
    y: float,
    vspace: float,
) -> None:
    x_in = x * inch
    y_in = y * inch

    for image in images:
        with Image.open(image["file"]) as src:
            if image.get("cue"):
                im_white = Image.new("L", src.size, 255)
                im = Image.blend(src, im_white, 0.5)
            else:
                im = src

            w, h = [d / RESOLUTION * inch for d in im.size]
            y_in -= h
            doc.drawImage(ImageReader(im), x_in, y_in, width=w, height=h)

            label = image.get("label") or ""
            if label:
                if image.get("cue"):
                    doc.setStrokeColor(gray)
                    doc.setFillColor(gray)

                doc.rect(x_in - inch / 4, y_in + (h - inch / 2) / 2, inch / 5, inch / 2, stroke=1)
                doc.rotate(90)
                set_header_font(doc, label, 11)
                doc.drawCentredString(y_in + h / 2, -x_in + inch / 10, label)
                doc.rotate(-90)

                if image.get("cue"):
                    doc.setStrokeColor(black)
                    doc.setFillColor(black)

            y_in -= vspace * inch


def create_part(
    *,
    title: str,
    composer: str,
    part_name: str,
    partset_id: str,
    sep: float,
    pages: list[list[dict]],
    outfile: Path,
    pagesize: str = "letter",
) -> None:
    dims = {"letter": (8.5, 11), "a4": (8.27, 11.69)}
    page_w, page_h = dims[pagesize]

    header_left = 0.75
    header_right = page_w - 0.75
    center = page_w / 2

    max_width = _max_segment_width(pages)
    left_margin = max(0, (page_w - max_width / RESOLUTION) / 2)

    bottom_margin = (page_h - 10.5) / 2
    top_margin = bottom_margin + 10.5

    if pagesize == "letter":
        part = canvas.Canvas(str(outfile), pagesize=letter)
    else:
        part = canvas.Canvas(str(outfile))

    for ndx, page_segments in enumerate(pages):
        _add_page_info(
            part,
            header_left,
            header_right,
            center,
            top_margin,
            bottom_margin,
            title,
            composer,
            part_name,
            partset_id,
            ndx + 1,
        )
        _add_images(part, page_segments, left_margin, top_margin - 0.7, sep)
        part.showPage()

    part.save()


def _serialize_part_job(job: dict) -> dict:
    return {
        "title": job["title"],
        "composer": job["composer"],
        "part_name": job["part_name"],
        "partset_id": job["partset_id"],
        "sep": job["sep"],
        "pagesize": job["pagesize"],
        "outfile": str(job["outfile"]),
        "pages": [
            [
                {
                    "file": str(seg["file"]),
                    "label": seg.get("label") or "",
                    "cue": bool(seg.get("cue")),
                }
                for seg in page
            ]
            for page in job["pages"]
        ],
    }


def _create_part_job(serialized: dict) -> None:
    create_part(
        title=serialized["title"],
        composer=serialized["composer"],
        part_name=serialized["part_name"],
        partset_id=serialized["partset_id"],
        sep=serialized["sep"],
        pagesize=serialized["pagesize"],
        outfile=Path(serialized["outfile"]),
        pages=[
            [
                {
                    "file": Path(seg["file"]),
                    "label": seg.get("label") or "",
                    "cue": bool(seg.get("cue")),
                }
                for seg in page
            ]
            for page in serialized["pages"]
        ],
    )


def create_parts(
    jobs: list[dict],
    *,
    pool_size: int | None = None,
    on_part_done: Callable[[], None] | None = None,
) -> None:
    from pipeline.cut_segments import default_pool_size
    from pipeline.parallel import run_in_parallel

    if not jobs:
        return

    serialized_jobs = [_serialize_part_job(job) for job in jobs]
    workers = pool_size if pool_size is not None else default_pool_size(len(serialized_jobs))
    run_in_parallel(_create_part_job, serialized_jobs, workers=workers, on_done=on_part_done)

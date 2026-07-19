"""Build part PDFs from cut segment PNGs (Python 3 port of legacy paste_segments.py)."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import black, gray
from reportlab.lib.pagesizes import A4, letter, landscape as landscape_page
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from pipeline.page_dimensions import Orientation
from pipeline.part_names import display_part_name
from pipeline.paste_layout import (
    RESOLUTION,
    page_dims_inches,
    paste_packing_bottom_in,
    paste_packing_top_in,
    vertical_layout,
)
from pipeline.pdf_fonts import set_header_font, set_header_font_for_fields

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "scroll.png"
HEADER_FONT_SIZE = 11


def _draw_partifi_link(
    doc: canvas.Canvas,
    *,
    right_in: float,
    top_in: float,
    partset_id: str,
    font_name: str,
) -> None:
    label = f"partifi.org/{partset_id}"
    url = f"https://partifi.org/{partset_id}"
    y = top_in - 24
    doc.drawRightString(right_in, y, label)
    width = stringWidth(label, font_name, HEADER_FONT_SIZE)
    doc.linkURL(url, (right_in - width, y - 2, right_in, y + HEADER_FONT_SIZE), relative=1)


def _reportlab_pagesize(pagesize: str, orientation: Orientation):
    base = letter if pagesize == "letter" else A4
    return landscape_page(base) if orientation == "landscape" else base


def _draw_page_number(
    doc: canvas.Canvas,
    *,
    center: float,
    bottom: float,
    page_num: int,
) -> None:
    page_label = f"Page {page_num}"
    set_header_font(doc, page_label, HEADER_FONT_SIZE)
    doc.drawCentredString(center * inch, bottom * inch, page_label)


def _pdf_document_title(part_name: str, composer: str, title: str) -> str:
    part_name = part_name.strip()
    composer = composer.strip()
    title = title.strip()
    if title:
        return f"{part_name} — {title}"
    if composer:
        return f"{part_name} — {composer}"
    return part_name or "Partifi part"


def _pdf_document_subject(composer: str, title: str) -> str | None:
    composer = composer.strip()
    title = title.strip()
    if composer and title:
        return f"{composer}: {title}"
    if composer:
        return composer
    if title:
        return title
    return None


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
    header_font = set_header_font_for_fields(
        doc,
        title,
        composer,
        part_name_text,
        partset_id,
        f"partifi.org/{partset_id}",
        page_label,
        size=HEADER_FONT_SIZE,
    )
    doc.drawString(left_in + 28, top_in - 12, title)
    doc.drawString(left_in + 28, top_in - 24, composer)
    doc.drawRightString(right_in, top_in - 12, part_name_text)
    _draw_partifi_link(
        doc,
        right_in=right_in,
        top_in=top_in,
        partset_id=partset_id,
        font_name=header_font,
    )
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
    *,
    min_y_in: float,
) -> None:
    x_in = x * inch
    y_in = y * inch

    for i, image in enumerate(images):
        with Image.open(image["file"]) as src:
            if image.get("cue"):
                im_white = Image.new("L", src.size, 255)
                im = Image.blend(src, im_white, 0.5)
            else:
                im = src

            w, h = [d / RESOLUTION * inch for d in im.size]
            available_pt = y_in - min_y_in
            if h > available_pt:
                if available_pt <= 0:
                    raise RuntimeError(
                        "Part page layout overflow: segment image extends into the footer band"
                    )
                scale = available_pt / h
                w *= scale
                h = available_pt
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

            if i < len(images) - 1:
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
    orientation: Orientation = "portrait",
) -> None:
    displayed_part_name = display_part_name(part_name)
    page_w, page_h = page_dims_inches(pagesize, orientation)
    bottom_margin, top_margin = vertical_layout(page_h, orientation)
    packing_top_in = paste_packing_top_in(pagesize, orientation)
    packing_bottom_in = paste_packing_bottom_in(pagesize, orientation)

    header_left = 0.75
    header_right = page_w - 0.75
    center = page_w / 2

    max_width = _max_segment_width(pages)
    left_margin = max(0, (page_w - max_width / RESOLUTION) / 2)

    part = canvas.Canvas(str(outfile), pagesize=_reportlab_pagesize(pagesize, orientation))
    part.setTitle(_pdf_document_title(displayed_part_name, composer, title))
    if subject := _pdf_document_subject(composer, title):
        part.setSubject(subject)
    if composer:
        part.setAuthor(composer)

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
            displayed_part_name,
            partset_id,
            ndx + 1,
        )
        _add_images(
            part,
            page_segments,
            left_margin,
            packing_top_in,
            sep,
            min_y_in=packing_bottom_in * inch,
        )
        _draw_page_number(part, center=center, bottom=bottom_margin, page_num=ndx + 1)
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
        "orientation": job.get("orientation", "portrait"),
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
        orientation=serialized.get("orientation", "portrait"),
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

"""Orientation detection from native page aspect ratio."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from PIL import Image

from pipeline.page_dimensions import Orientation
from pipeline.page_render import burst_pdf, render_page_native_lowres

DEFAULT_SAMPLE_COUNT = 3
PAGE_ASPECT_TOLERANCE = 1.05
# Used by the labeling UI to show multiple pages for human review.
SAMPLE_BODY_START = 0.2
SAMPLE_BODY_END = 0.6
SAMPLE_FRACTIONS_DEFAULT = (0.2, 0.4, 0.6)


class PageKind(str, Enum):
    NATIVE_LANDSCAPE = "native_landscape"
    NATIVE_PORTRAIT = "native_portrait"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class PageVote:
    orientation: Orientation
    rotation_degrees: int

    def to_dict(self) -> dict:
        return {
            "orientation": self.orientation,
            "rotation_degrees": self.rotation_degrees,
        }


@dataclass
class PageOrientationResult:
    page_number: int
    native_width: int
    native_height: int
    page_kind: PageKind
    row_variance: float
    col_variance: float
    vote: PageVote
    confidence: float
    working_image: Image.Image | None = None
    rotation_candidates: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "native_width": self.native_width,
            "native_height": self.native_height,
            "page_kind": self.page_kind.value,
            "row_variance": round(self.row_variance, 6),
            "col_variance": round(self.col_variance, 6),
            "vote": self.vote.to_dict(),
            "confidence": round(self.confidence, 6),
            "rotation_candidates": [],
        }


@dataclass
class OrientationDetectionResult:
    orientation: Orientation
    rotation_degrees: int
    confidence: float
    num_pages: int
    sampled_pages: list[int]
    portrait_votes: int = 0
    landscape_votes: int = 0
    rotation_votes: dict[int, int] = field(default_factory=dict)
    disguised_pages: int = 0
    native_landscape_pages: int = 0
    native_portrait_pages: int = 0
    page_results: list[PageOrientationResult] = field(default_factory=list)
    uncertain: bool = False

    def to_dict(self) -> dict:
        return {
            "orientation": self.orientation,
            "rotation_degrees": self.rotation_degrees,
            "confidence": round(self.confidence, 6),
            "uncertain": self.uncertain,
            "num_pages": self.num_pages,
            "sampled_pages": self.sampled_pages,
            "portrait_votes": self.portrait_votes,
            "landscape_votes": self.landscape_votes,
            "rotation_votes": self.rotation_votes,
            "disguised_pages": self.disguised_pages,
            "native_landscape_pages": self.native_landscape_pages,
            "native_portrait_pages": self.native_portrait_pages,
            "pages": [page.to_dict() for page in self.page_results],
        }


def _sample_fractions(sample_count: int) -> list[float]:
    if sample_count <= 1:
        return [0.4]
    if sample_count == len(SAMPLE_FRACTIONS_DEFAULT):
        return list(SAMPLE_FRACTIONS_DEFAULT)
    return [
        SAMPLE_BODY_START + (SAMPLE_BODY_END - SAMPLE_BODY_START) * i / (sample_count - 1)
        for i in range(sample_count)
    ]


def sample_page_numbers(num_pages: int, sample_count: int = DEFAULT_SAMPLE_COUNT) -> list[int]:
    """Return 1-based page numbers sampled within the score body (≈20%, 40%, 60%).

    Used by the labeling UI. Detection itself uses page 1 only.
    """
    if num_pages <= 0:
        return []
    if num_pages <= sample_count:
        return list(range(1, num_pages + 1))

    pages: list[int] = []
    for fraction in _sample_fractions(sample_count):
        page = max(1, min(num_pages, round(num_pages * fraction)))
        if not pages or pages[-1] != page:
            pages.append(page)
    return pages


def apply_score_transform(
    native_im: Image.Image,
    orientation: Orientation,
    rotation_degrees: int,
) -> Image.Image:
    """Apply the score-level rotation (or none) to a natively rendered page."""
    if orientation == "portrait" or rotation_degrees == 0:
        return native_im.copy()
    return native_im.rotate(rotation_degrees, expand=True, fillcolor=255)


def _native_orientation_from_size(width: int, height: int) -> tuple[Orientation, PageKind]:
    if width > height * PAGE_ASPECT_TOLERANCE:
        return "landscape", PageKind.NATIVE_LANDSCAPE
    if height > width * PAGE_ASPECT_TOLERANCE:
        return "portrait", PageKind.NATIVE_PORTRAIT
    return "portrait", PageKind.AMBIGUOUS


def analyze_native_page(native_im: Image.Image, page_number: int) -> PageOrientationResult:
    """Classify one page from its native render dimensions."""
    width, height = native_im.size
    orientation, page_kind = _native_orientation_from_size(width, height)
    return PageOrientationResult(
        page_number=page_number,
        native_width=width,
        native_height=height,
        page_kind=page_kind,
        row_variance=0.0,
        col_variance=0.0,
        vote=PageVote(orientation=orientation, rotation_degrees=0),
        confidence=abs(width - height) / max(width, height),
        working_image=native_im.copy(),
    )


def detect_orientation_from_images(
    page_images: list[tuple[int, Image.Image]],
) -> OrientationDetectionResult:
    """Detect score orientation from page 1's native aspect ratio."""
    if not page_images:
        raise ValueError("No page images")

    page_number, native_im = min(page_images, key=lambda item: item[0])
    page_result = analyze_native_page(native_im, page_number)
    orientation = page_result.vote.orientation
    landscape = orientation == "landscape"

    return OrientationDetectionResult(
        orientation=orientation,
        rotation_degrees=0,
        confidence=page_result.confidence,
        num_pages=page_number,
        sampled_pages=[page_number],
        portrait_votes=0 if landscape else 1,
        landscape_votes=1 if landscape else 0,
        rotation_votes={0: 1},
        disguised_pages=0,
        native_landscape_pages=1 if page_result.page_kind == PageKind.NATIVE_LANDSCAPE else 0,
        native_portrait_pages=1 if page_result.page_kind == PageKind.NATIVE_PORTRAIT else 0,
        page_results=[page_result],
        uncertain=page_result.page_kind == PageKind.AMBIGUOUS,
    )


def detect_orientation(
    pdf_path: Path,
    *,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    workdir: Path | None = None,
) -> tuple[OrientationDetectionResult, Path]:
    """Detect score orientation from page 1's native aspect ratio."""
    del sample_count  # kept for CLI compatibility; detection uses page 1 only

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="partifi-orient-detect-"))
    else:
        workdir.mkdir(parents=True, exist_ok=True)

    burst_dir = workdir / "burst"
    render_dir = workdir / "render"
    burst_dir.mkdir(parents=True, exist_ok=True)
    render_dir.mkdir(parents=True, exist_ok=True)

    _, page_pdfs = burst_pdf(pdf_path, burst_dir)
    native_im = render_page_native_lowres(page_pdfs[0], render_dir)
    detection = detect_orientation_from_images([(1, native_im)])
    detection.num_pages = len(page_pdfs)
    detection.sampled_pages = [1]
    return detection, workdir

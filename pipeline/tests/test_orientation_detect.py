"""Tests for orientation detection from native page aspect ratio."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pipeline.orientation_detect import (
    PageKind,
    analyze_native_page,
    apply_score_transform,
    detect_orientation_from_images,
    sample_page_numbers,
)


def _blank_page(width: int, height: int) -> Image.Image:
    return Image.fromarray(np.full((height, width), 255, dtype=np.uint8), mode="L")


def test_sample_page_numbers_body_fractions() -> None:
    assert sample_page_numbers(100, 3) == [20, 40, 60]
    assert sample_page_numbers(10, 3) == [2, 4, 6]
    assert sample_page_numbers(5, 3) == [1, 2, 3]
    assert sample_page_numbers(3, 3) == [1, 2, 3]
    assert sample_page_numbers(2, 3) == [1, 2]


def test_sample_page_numbers_custom_count_spans_body() -> None:
    assert sample_page_numbers(100, 5) == [20, 30, 40, 50, 60]


def test_native_landscape_page() -> None:
    result = analyze_native_page(_blank_page(776, 600), 1)
    assert result.page_kind == PageKind.NATIVE_LANDSCAPE
    assert result.vote.orientation == "landscape"
    assert result.vote.rotation_degrees == 0


def test_native_portrait_page() -> None:
    result = analyze_native_page(_blank_page(600, 776), 1)
    assert result.page_kind == PageKind.NATIVE_PORTRAIT
    assert result.vote.orientation == "portrait"
    assert result.vote.rotation_degrees == 0


def test_square_page_defaults_to_portrait_and_marks_uncertain() -> None:
    detection = detect_orientation_from_images([(1, _blank_page(700, 700))])
    assert detection.orientation == "portrait"
    assert detection.rotation_degrees == 0
    assert detection.uncertain is True
    assert detection.page_results[0].page_kind == PageKind.AMBIGUOUS


def test_detection_uses_first_page_only() -> None:
    pages = [
        (1, _blank_page(776, 600)),
        (2, _blank_page(600, 776)),
        (3, _blank_page(600, 776)),
    ]
    detection = detect_orientation_from_images(pages)
    assert detection.orientation == "landscape"
    assert detection.sampled_pages == [1]
    assert len(detection.page_results) == 1


def test_apply_score_transform_keeps_native_image_without_rotation() -> None:
    native = _blank_page(600, 776)
    transformed = apply_score_transform(native, "portrait", 0)
    assert transformed.size == native.size

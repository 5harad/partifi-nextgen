"""Tests for per-partset orientation helpers."""

from __future__ import annotations

import pytest

from pipeline.partset_orientation import (
    effective_partset_orientation,
    layout_orientation,
    normalize_rotation_degrees,
    partset_uses_custom_pages,
)


def test_layout_orientation_swaps_on_90_and_270() -> None:
    assert layout_orientation("portrait", 90) == "landscape"
    assert layout_orientation("portrait", 270) == "landscape"
    assert layout_orientation("landscape", 90) == "portrait"
    assert layout_orientation("portrait", 180) == "portrait"


def test_normalize_rotation_degrees_accepts_cardinals() -> None:
    assert normalize_rotation_degrees(0) == 0
    assert normalize_rotation_degrees(90) == 90
    assert normalize_rotation_degrees(360) == 0


def test_normalize_rotation_degrees_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_rotation_degrees(45)


def test_effective_orientation_prefers_override() -> None:
    assert (
        effective_partset_orientation(
            score_orientation="portrait",
            orientation_override="landscape",
            rotation_degrees=0,
        )
        == "landscape"
    )


def test_partset_uses_custom_pages_only_when_rotated() -> None:
    assert partset_uses_custom_pages(0) is False
    assert partset_uses_custom_pages(90) is True

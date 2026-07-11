"""Page dimension constants and helpers for portrait and landscape scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Orientation = Literal["portrait", "landscape"]


@dataclass(frozen=True)
class PageDimensions:
    orientation: Orientation
    highres_width: int
    highres_height: int
    lowres_width: int
    lowres_height: int
    thumb_width: int
    thumb_height: int

    @property
    def highres_size(self) -> tuple[int, int]:
        return self.highres_width, self.highres_height

    @property
    def lowres_size(self) -> tuple[int, int]:
        return self.lowres_width, self.lowres_height

    @property
    def thumb_size(self) -> tuple[int, int]:
        return self.thumb_width, self.thumb_height

    @property
    def gs_canvas(self) -> str:
        return f"{self.highres_width}x{self.highres_height}"


PORTRAIT = PageDimensions(
    orientation="portrait",
    highres_width=2550,
    highres_height=3300,
    lowres_width=600,
    lowres_height=776,
    thumb_width=100,
    thumb_height=129,
)

LANDSCAPE = PageDimensions(
    orientation="landscape",
    highres_width=3300,
    highres_height=2550,
    lowres_width=776,
    lowres_height=600,
    thumb_width=129,
    thumb_height=100,
)


def get_dimensions(orientation: Orientation) -> PageDimensions:
    return LANDSCAPE if orientation == "landscape" else PORTRAIT


def prct2pixel(p: float, dim: str = "height", orientation: Orientation = "portrait") -> float:
    dims = get_dimensions(orientation)
    scale = dims.highres_height if dim == "height" else dims.highres_width
    return p / 100.0 * scale

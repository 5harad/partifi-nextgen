"""Score PDF size limits (upload + IMSLP import)."""

from __future__ import annotations

MAX_SCORE_BYTES = 100_000_000
MAX_SCORE_MB = 100


class ScoreTooLargeError(ValueError):
    def __init__(self, size_bytes: int | None = None) -> None:
        super().__init__(score_too_large_message(size_bytes))


def score_too_large_message(size_bytes: int | None = None) -> str:
    if size_bytes is not None:
        size_mb = size_bytes / 1_000_000
        return (
            f"This score PDF is too large ({size_mb:.0f} MB). "
            f"The maximum size is {MAX_SCORE_MB} MB."
        )
    return f"This score PDF is too large. The maximum size is {MAX_SCORE_MB} MB."

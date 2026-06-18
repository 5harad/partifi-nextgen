"""Score PDF size limits (upload + IMSLP import)."""

from __future__ import annotations

import logging

MAX_SCORE_BYTES = 200_000_000
MAX_SCORE_MB = 200


class ScoreTooLargeError(ValueError):
    def __init__(self, size_bytes: int | None = None) -> None:
        super().__init__(score_too_large_message(size_bytes))


def log_score_too_large(
    logger: logging.Logger,
    size_bytes: int,
    *,
    imslp_id: str | None = None,
) -> None:
    size_mb = size_bytes / 1_000_000
    if imslp_id:
        logger.warning(
            "IMSLP %s import rejected: score too large (%.0f MB, limit %d MB)",
            imslp_id,
            size_mb,
            MAX_SCORE_MB,
        )
    else:
        logger.warning(
            "Score import rejected: too large (%.0f MB, limit %d MB)",
            size_mb,
            MAX_SCORE_MB,
        )


def reject_score_too_large(
    size_bytes: int,
    *,
    logger: logging.Logger | None = None,
    imslp_id: str | None = None,
) -> ScoreTooLargeError:
    if logger is not None:
        log_score_too_large(logger, size_bytes, imslp_id=imslp_id)
    return ScoreTooLargeError(size_bytes)


def score_too_large_message(size_bytes: int | None = None) -> str:
    if size_bytes is not None:
        size_mb = size_bytes / 1_000_000
        return (
            f"This score PDF is too large ({size_mb:.0f} MB). "
            f"The maximum size is {MAX_SCORE_MB} MB."
        )
    return f"This score PDF is too large. The maximum size is {MAX_SCORE_MB} MB."

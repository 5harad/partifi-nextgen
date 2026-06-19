"""Score PDF size limits (upload + IMSLP import)."""

from __future__ import annotations

import logging

from app.config import get_settings


class ScoreTooLargeError(ValueError):
    def __init__(self, size_bytes: int | None = None) -> None:
        super().__init__(score_too_large_message(size_bytes))


def max_score_mb() -> int:
    return get_settings().partifi_max_score_mb


def max_score_bytes() -> int:
    return max_score_mb() * 1_000_000


def __getattr__(name: str):
    if name == "MAX_SCORE_MB":
        return max_score_mb()
    if name == "MAX_SCORE_BYTES":
        return max_score_bytes()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def log_score_too_large(
    logger: logging.Logger,
    size_bytes: int,
    *,
    imslp_id: str | None = None,
) -> None:
    size_mb = size_bytes / 1_000_000
    limit_mb = max_score_mb()
    if imslp_id:
        logger.warning(
            "IMSLP %s import rejected: score too large (%.0f MB, limit %d MB)",
            imslp_id,
            size_mb,
            limit_mb,
        )
    else:
        logger.warning(
            "Score import rejected: too large (%.0f MB, limit %d MB)",
            size_mb,
            limit_mb,
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
    limit_mb = max_score_mb()
    if size_bytes is not None:
        size_mb = size_bytes / 1_000_000
        return (
            f"This score PDF is too large ({size_mb:.0f} MB). "
            f"The maximum size is {limit_mb} MB."
        )
    return f"This score PDF is too large. The maximum size is {limit_mb} MB."

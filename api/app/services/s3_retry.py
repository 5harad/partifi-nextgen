"""Bounded retries for transient S3 errors (API)."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from botocore.exceptions import BotoCoreError, ClientError, ConnectionError, EndpointConnectionError

logger = logging.getLogger(__name__)

S3_RETRY_ATTEMPTS = 3
S3_RETRY_BASE_SECONDS = 2.0

T = TypeVar("T")


def is_retryable_s3_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, EndpointConnectionError, TimeoutError, OSError)):
        return True
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        if code in ("RequestTimeout", "SlowDown", "InternalError", "ServiceUnavailable", "Throttling"):
            return True
        return isinstance(status, int) and status >= 500
    if isinstance(exc, BotoCoreError):
        return True
    return False


def call_with_s3_retries(
    label: str,
    fn: Callable[[], T],
    *,
    max_attempts: int = S3_RETRY_ATTEMPTS,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not is_retryable_s3_error(exc):
                raise
            if attempt + 1 >= max_attempts:
                break
            delay = S3_RETRY_BASE_SECONDS * (3**attempt) + random.uniform(0, 0.5)
            logger.warning(
                "S3 %s attempt %d/%d failed, retry in %.1fs: %s",
                label,
                attempt + 1,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
    assert last_exc is not None
    logger.error("S3 %s failed after %d attempts", label, max_attempts)
    raise last_exc

"""Background worker — pulls jobs from Redis and dispatches to handlers."""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from collections.abc import Callable

import redis

from config import get_settings
from job_runner import JobOutcome, request_job_abort, run_job_with_timeout
from queue_ops import ack_job, claim_next_job, reap_stale_jobs, requeue_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("partifi.worker")

RUNNING = True
_reap_counter = 0

# Transient Redis errors we recover from (drop, restart, brief network blip).
_REDIS_CONNECTION_ERRORS = (
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
)
RECONNECT_BACKOFF_SECONDS = 2.0


def _handle_signal(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False
    logger.info("Shutdown requested")
    request_job_abort()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _maybe_reap_stale(client: redis.Redis) -> None:
    global _reap_counter
    _reap_counter += 1
    if _reap_counter >= 12:
        _reap_counter = 0
        reap_stale_jobs(client)


def _new_redis_client(settings) -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def should_reconnect_after_redis_error(
    *,
    running: bool,
    backoff_seconds: float = RECONNECT_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Decide what to do after a Redis connection drop.

    Returns True if the worker should reconnect and keep polling. Returns False
    when shutdown is in progress, so an expected drop during reboot/deploy exits
    quietly instead of logging a traceback.
    """
    if not running:
        return False
    logger.warning("Redis connection lost; reconnecting in %.1fs", backoff_seconds)
    sleep(backoff_seconds)
    return True


def main() -> None:
    settings = get_settings()
    client = _new_redis_client(settings)
    logger.info(
        "Worker started (redis=%s job_timeout=%ss)",
        settings.redis_url,
        settings.job_timeout_seconds,
    )

    try:
        reap_stale_jobs(client)
    except _REDIS_CONNECTION_ERRORS:
        logger.warning("Redis not ready at startup; will retry on first poll")

    while RUNNING:
        try:
            raw = claim_next_job(client, timeout=5)
            if raw is None:
                _maybe_reap_stale(client)
                continue

            try:
                job = json.loads(raw)
            except json.JSONDecodeError:
                logger.exception("Invalid job payload: %s", raw)
                ack_job(client, raw)
                continue

            logger.info("Dequeuing job %s type=%s", job.get("id"), job.get("type"))
            outcome = run_job_with_timeout(job)
            if outcome is JobOutcome.INTERRUPTED:
                requeue_job(client, raw)
                logger.info("Re-queued interrupted job %s", job.get("id"))
            else:
                ack_job(client, raw)
        except _REDIS_CONNECTION_ERRORS:
            if not should_reconnect_after_redis_error(running=RUNNING):
                break
            client = _new_redis_client(settings)
            continue

        if not RUNNING:
            break

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
    sys.exit(0)

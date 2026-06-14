"""Background worker — pulls jobs from Redis and dispatches to handlers."""

from __future__ import annotations

import json
import logging
import signal
import sys

import redis

from config import get_settings
from job_runner import JobOutcome, request_job_abort, run_job_with_timeout
from queue_ops import ack_job, claim_next_job, reap_stale_jobs, requeue_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("partifi.worker")

RUNNING = True
_reap_counter = 0


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


def main() -> None:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info(
        "Worker started (redis=%s job_timeout=%ss)",
        settings.redis_url,
        settings.job_timeout_seconds,
    )

    reap_stale_jobs(client)

    while RUNNING:
        raw = claim_next_job(client, timeout=5)
        if raw is None:
            _maybe_reap_stale(client)
            continue

        try:
            job = json.loads(raw)
            logger.info("Dequeuing job %s type=%s", job.get("id"), job.get("type"))
            outcome = run_job_with_timeout(job)
            if outcome is JobOutcome.INTERRUPTED:
                requeue_job(client, raw)
                logger.info("Re-queued interrupted job %s", job.get("id"))
            elif outcome is JobOutcome.SUCCESS:
                ack_job(client, raw)
            else:
                ack_job(client, raw)
        except json.JSONDecodeError:
            logger.exception("Invalid job payload: %s", raw)
            ack_job(client, raw)

        if not RUNNING:
            break

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
    sys.exit(0)

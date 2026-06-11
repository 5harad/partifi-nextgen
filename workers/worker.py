"""Background worker — pulls jobs from Redis and dispatches to handlers."""

from __future__ import annotations

import json
import logging
import signal
import sys

import redis

from config import get_settings
from job_runner import request_job_abort, run_job_with_timeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("partifi.worker")

QUEUE_KEY = "partifi:jobs"
RUNNING = True


def _handle_signal(_signum, _frame) -> None:
    global RUNNING
    RUNNING = False
    logger.info("Shutdown requested")
    request_job_abort()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def main() -> None:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    logger.info(
        "Worker started (redis=%s job_timeout=%ss)",
        settings.redis_url,
        settings.job_timeout_seconds,
    )

    while RUNNING:
        result = client.brpop(QUEUE_KEY, timeout=5)
        if result is None:
            continue
        _, raw = result
        try:
            job = json.loads(raw)
            logger.info("Dequeuing job %s type=%s", job.get("id"), job.get("type"))
            run_job_with_timeout(job)
        except json.JSONDecodeError:
            logger.exception("Invalid job payload: %s", raw)

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
    sys.exit(0)
